"""Revisión automática del vídeo final: lo que antes miraba una persona a ojo.

Cada comprobación nace de un fallo real que llegó (o casi) al canal:

| check            | caso real                                                     |
|------------------|---------------------------------------------------------------|
| formato          | renders con la resolución o sin pista de audio                |
| duracion         | 2026-09-27: el verificador dio ✓ a un vídeo al que faltaba 1 min |
| negro            | planos sin fondo que salían en negro                          |
| congelado        | b-roll que no se movía (2026-09-04: "6 clips" que no salían)  |
| silencio         | huecos de voz por TTS cortado                                 |
| volumen          | máster a −17 LUFS (2026-09-27); objetivo −14                  |
| parpadeo         | tween de brillo que hacía parpadear las escenas (2026-09-27)  |
| voz_guion        | la voz no dice lo que pone el guion (TTS que se salta frases) |
| tema             | 2026-09-27: título de OpenClaw con el guion del cine 4D       |
| miniatura        | posts y vídeos sin miniatura (2026-09-22)                     |

No usa Claude ni ningún servicio de pago: ffmpeg y faster-whisper en local.
Los umbrales están en `Umbrales` para que quien lo use los ajuste a su canal.
"""
from __future__ import annotations

import json
import re
import subprocess
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Umbrales:
    duracion_long: tuple[float, float] = (240, 720)
    duracion_short: tuple[float, float] = (15, 60)
    negro_max_s: float = 1.0          # un fundido corto vale; un plano negro no
    congelado_max_s: float = 8.0      # imagen fija con texto encima aguanta ~8 s
    silencio_max_s: float = 2.5
    silencio_db: float = -45
    lufs: tuple[float, float] = (-16.5, -12.5)
    parpadeo_salto: float = 25        # salto de luminancia (0-255) de un fotograma
    parpadeo_max: int = 3             # destellos de 1 fotograma tolerados
    voz_cobertura_min: float = 0.80   # palabras del guion que Whisper oye
    tema_cobertura_min: float = 0.5   # palabras clave del tema presentes en la voz
    desfase_audio_max_s: float = 1.5


@dataclass
class Resultado:
    fallos: list[str] = field(default_factory=list)
    medidas: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.fallos

    def a_dict(self) -> dict:
        return asdict(self)


# ------------------------------------------------------------------ utilidades
def _ffmpeg_stderr(args: list[str], timeout: int = 1800) -> str:
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *args],
                          capture_output=True, text=True, timeout=timeout).stderr


def _probe(video: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json",
                          str(video)], capture_output=True, text=True).stdout
    return json.loads(out or "{}")


def normalizar(t: str) -> list[str]:
    t = unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode()
    return re.findall(r"[a-z0-9]+", t)


# Palabras del formato de la serie y de relleno: no identifican el tema.
_VACIAS = set("""la el los las un una unos unas de del y o a en con por para que se su sus al
lo como mas pero sin ya cualquier tu te mi es son ha han letra pequena pequeña viral
virales nuevo nueva gratis claude code ia""".split())


def palabras_clave(tema: str) -> list[str]:
    return [w for w in dict.fromkeys(normalizar(tema)) if len(w) >= 3 and w not in _VACIAS]


def tramos(stderr: str, clave: str) -> list[float]:
    """Duraciones de los tramos que reportan blackdetect/freezedetect/silencedetect."""
    return [float(x) for x in re.findall(rf"{clave}[:=]\s*([\d.]+)", stderr)]


def destellos(luma: list[float], salto: float) -> int:
    """Destellos de UN fotograma: sube (o baja) de golpe y vuelve al siguiente.
    Un corte de plano cambia y se queda; un parpadeo cambia y vuelve."""
    n = 0
    for i in range(1, len(luma) - 1):
        if abs(luma[i] - luma[i - 1]) > salto and abs(luma[i + 1] - luma[i - 1]) < salto / 3:
            n += 1
    return n


def cobertura(referencia: list[str], oido: list[str], min_len: int = 5) -> float:
    """Fracción de palabras largas de la referencia que aparecen en lo oído."""
    ref = [w for w in referencia if len(w) >= min_len]
    if not ref:
        return 1.0
    oido_set = set(oido)
    return sum(1 for w in ref if w in oido_set) / len(ref)


def transcribir(video: Path, modelo: str = "small") -> str:
    from faster_whisper import WhisperModel
    m = WhisperModel(modelo, device="cpu", compute_type="int8")
    segs, _ = m.transcribe(str(video), language="es", vad_filter=True)
    return " ".join(s.text for s in segs)


# ------------------------------------------------------------------ revisión
def revisar(video: Path, *, guion: str, tema: str, modo: str = "long",
            miniatura: Path | None = None, u: Umbrales | None = None,
            transcripcion: str | None = None) -> Resultado:
    u = u or Umbrales()
    r = Resultado()
    video = Path(video)
    if not video.exists() or video.stat().st_size < 100_000:
        r.fallos.append("el vídeo no existe o está vacío")
        return r

    # formato y duración
    info = _probe(video)
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    dur = float(info.get("format", {}).get("duration", 0) or 0)
    r.medidas["duracion_s"] = round(dur, 1)
    esperado = (1080, 1920) if modo == "short" else (1920, 1080)
    if not v or (v.get("width"), v.get("height")) != esperado:
        r.fallos.append(f"resolución {v and (v.get('width'), v.get('height'))}, se esperaba {esperado}")
    if not a:
        r.fallos.append("no tiene pista de audio")
    else:
        da = float(a.get("duration", dur) or dur)
        if abs(da - dur) > u.desfase_audio_max_s:
            r.fallos.append(f"audio ({da:.1f}s) y vídeo ({dur:.1f}s) no duran lo mismo")
    lo, hi = u.duracion_short if modo == "short" else u.duracion_long
    if not lo <= dur <= hi:
        r.fallos.append(f"dura {dur:.0f}s, fuera de {lo:.0f}-{hi:.0f}s")

    # imagen: negro, congelado y luminancia por fotograma (una sola pasada)
    err = _ffmpeg_stderr(["-i", str(video), "-an", "-vf",
                          "scale=160:-2,blackdetect=d=0.3:pix_th=0.10,"
                          f"freezedetect=n=0.003:d={u.congelado_max_s},"
                          "signalstats,metadata=print:key=lavfi.signalstats.YAVG",
                          "-f", "null", "-"])
    negros = tramos(err, "black_duration")
    congelados = tramos(err, "lavfi.freezedetect.freeze_duration")
    luma = [float(x) for x in re.findall(r"lavfi\.signalstats\.YAVG=([\d.]+)", err)]
    r.medidas.update(negro_max_s=max(negros, default=0), congelado_max_s=max(congelados, default=0),
                     destellos=destellos(luma, u.parpadeo_salto), fotogramas=len(luma))
    if any(d > u.negro_max_s for d in negros):
        r.fallos.append(f"plano negro de {max(negros):.1f}s")
    # freezedetect solo informa de tramos >= d, así que cualquiera es fallo
    if congelados:
        r.fallos.append(f"imagen congelada {max(congelados):.1f}s")
    if not luma:
        r.fallos.append("no pude leer la luminancia de los fotogramas")
    elif r.medidas["destellos"] > u.parpadeo_max:
        r.fallos.append(f"parpadeo: {r.medidas['destellos']} destellos de un fotograma")

    # audio: silencios y volumen
    if a:
        err = _ffmpeg_stderr(["-i", str(video), "-vn", "-af",
                              f"silencedetect=n={u.silencio_db}dB:d={u.silencio_max_s},ebur128",
                              "-f", "null", "-"])
        sil = tramos(err, "silence_duration")
        lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
        r.medidas.update(silencio_max_s=max(sil, default=0),
                         lufs=float(lufs[-1]) if lufs else None)
        if sil:
            r.fallos.append(f"silencio de {max(sil):.1f}s")
        if r.medidas["lufs"] is None or not u.lufs[0] <= r.medidas["lufs"] <= u.lufs[1]:
            r.fallos.append(f"volumen {r.medidas['lufs']} LUFS, objetivo {u.lufs}")

        # voz contra guion y contra tema
        oido = normalizar(transcripcion if transcripcion is not None else transcribir(video))
        r.medidas["voz_cobertura"] = round(cobertura(normalizar(guion), oido), 3)
        if r.medidas["voz_cobertura"] < u.voz_cobertura_min:
            r.fallos.append(f"la voz solo dice el {r.medidas['voz_cobertura']:.0%} del guion")
        clave = palabras_clave(tema)
        r.medidas["tema_cobertura"] = round(cobertura(clave, oido, min_len=3), 3)
        if clave and r.medidas["tema_cobertura"] < u.tema_cobertura_min:
            faltan = [w for w in clave if w not in set(oido)]
            r.fallos.append(f"la voz no habla del tema del título (no se oye: {', '.join(faltan)})")

    # miniatura
    if miniatura is not None:
        if not Path(miniatura).exists() or Path(miniatura).stat().st_size < 30_000:
            r.fallos.append("falta la miniatura o está vacía")
        else:
            from PIL import Image
            w, h = Image.open(miniatura).size
            r.medidas["miniatura"] = f"{w}x{h}"
            if modo == "long" and abs(w / h - 16 / 9) > 0.02:
                r.fallos.append(f"miniatura {w}x{h} no es 16:9")
    return r

"""Short vertical cortado del largo ya revisado (mismo motor, mismas puertas).

Por qué del largo y no un render aparte: el short automático de antes
(scenes.py) salió dos veces sin precios y con rótulos en inglés; lo que sale
del largo ya pasó la verificación de hechos y la revisión. Francis lo aprobó
así a mano el 2026-10-02 (Universal Modder, 48 s).

1. Las frases del largo con sus tiempos reales (voz.json, alineada con Whisper).
2. Un LLM elige 2-4 tramos de frases seguidas: gancho + dato fuerte de la
   letra pequeña + veredicto, entre 40 y 55 s. Se valida en código.
3. ffmpeg corta en frase completa, junta y pasa a 1080x1920 (el 16:9 centrado
   sobre una copia desenfocada que llena la pantalla).
4. La misma puerta de revisión, en modo short.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ..contratos import Calidad, Guion, Short, Tema, Voz
from ..proyecto import Bloqueado, Proyecto, confirmar

NOMBRE = "short"
ENTRADAS = ["revision.json", "voz.json", "calidad.json", "render.json"]
SALIDA = "short.json"
MIN_S, MAX_S = 40.0, 55.0
COLA_S = 0.25  # margen tras la última palabra para no cortar la sílaba

PEDIDO = """Eres editor de YouTube Shorts. Del vídeo largo "{tema}" tienes estas
frases numeradas con su duración. Elige de 2 a 4 TRAMOS de frases SEGUIDAS que,
juntos, formen un short de {min_s:.0f} a {max_s:.0f} segundos que se entienda solo:
1º el gancho (la promesa del viral), 2º el dato más fuerte de la letra pequeña
(precio, límite o requisito concreto), y por último el veredicto EXPLICADO
(qué conviene hacer y por qué, no solo la palabra "veredicto").
OBLIGATORIO: alguna frase elegida tiene que NOMBRAR la herramienta del título
({clave}); sin eso, quien vea el short no sabe de qué hablamos.
No cortes una idea a medias. Usa solo frases que estén en la lista.{aviso}
Responde SOLO JSON: {{"tramos": [[primera, ultima], ...]}}

FRASES:
{frases}"""


def frases(tiempos: dict) -> list[dict]:
    """Agrupa las palabras alineadas en frases (terminan en . ? !)."""
    res, actual = [], []
    for w in tiempos.get("words", []):
        actual.append(w)
        if str(w["word"]).rstrip().endswith((".", "?", "!")):
            res.append(actual)
            actual = []
    if actual:
        res.append(actual)
    return [{"texto": " ".join(str(w["word"]) for w in f),
             "ini": f[0]["startMs"] / 1000, "fin": f[-1]["endMs"] / 1000} for f in res]


VEREDICTO_MIN_S = 6.0


def tramos_validos(tramos: list, fs: list[dict], clave: list[str] | None = None) -> list[tuple[float, float, str]]:
    """Comprueba la elección del LLM y la pasa a segundos. Lanza ValueError."""
    if not 2 <= len(tramos) <= 4:
        raise ValueError(f"{len(tramos)} tramos (tienen que ser 2-4)")
    res, ultimo = [], -1
    for t in tramos:
        a, b = int(t[0]), int(t[1])
        if not (0 <= a <= b < len(fs)) or a <= ultimo:
            raise ValueError(f"tramo {t} fuera de rango o desordenado")
        ultimo = b
        res.append((fs[a]["ini"], fs[b]["fin"] + COLA_S, " ".join(f["texto"] for f in fs[a:b + 1])))
    total = sum(fin - ini for ini, fin, _ in res)
    if not MIN_S <= total <= MAX_S:
        raise ValueError(f"dura {total:.1f}s (tiene que ser {MIN_S:.0f}-{MAX_S:.0f})")
    if res[-1][1] - res[-1][0] < VEREDICTO_MIN_S:
        raise ValueError(f"el cierre dura {res[-1][1] - res[-1][0]:.1f}s: el veredicto tiene que explicarse")
    if clave:
        from ..puertas.revision import normalizar
        dicho = set(normalizar(" ".join(t for _, _, t in res)))
        if not all(w in dicho for w in clave):
            raise ValueError(f"ninguna frase nombra la herramienta ({', '.join(clave)})")
    return res


def montar(origen: Path, tramos: list[tuple[float, float, str]], destino: Path) -> None:
    partes = []
    for i, (ini, fin, _) in enumerate(tramos):
        partes.append(f"[0:v]trim={ini:.3f}:{fin:.3f},setpts=PTS-STARTPTS[v{i}];"
                      f"[0:a]atrim={ini:.3f}:{fin:.3f},asetpts=PTS-STARTPTS[a{i}];")
    n = len(tramos)
    concat = "".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a];"
    vertical = ("[v]split[f][b];[b]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
                "gblur=sigma=30,eq=brightness=-0.15[fondo];[f]scale=1080:-2[frente];"
                "[fondo][frente]overlay=(W-w)/2:(H-h)/2[out];[a]loudnorm=I=-14:TP=-1.5:LRA=11[aout]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(origen), "-filter_complex",
                    "".join(partes) + concat + vertical, "-map", "[out]", "-map", "[aout]",
                    "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-c:a", "aac", "-b:a", "192k",
                    "-ar", "48000", "-movflags", "+faststart", str(destino)],
                   check=True, timeout=900)


def run(p: Proyecto) -> str:
    tema = p.leer("tema.json", Tema)
    fs = frases(p.leer("voz.json", Voz).tiempos)
    confirmar(len(fs) >= 6, f"solo {len(fs)} frases en la voz alineada")
    from ..proveedores import llm
    lista = "\n".join(f"{i}. ({f['fin'] - f['ini']:.1f}s) {f['texto']}" for i, f in enumerate(fs))
    from ..contratos import Dossier
    from ..puertas.revision import normalizar, palabras_clave
    import re
    # El NOMBRE de la herramienta (del dossier), no cualquier palabra del
    # título: con "juego" bastaba y el short no decía nunca "Universal Modder".
    m = re.search(r"DATOS VERIFICADOS DE (.+?) \(", p.leer("dossier.json", Dossier).texto)
    clave = normalizar(m.group(1)) if m else palabras_clave(tema.tema)
    errores = []
    for _ in range(4):
        aviso = f"\nTu intento anterior no valía: {errores[-1]}." if errores else ""
        d, prov = llm.json_de(PEDIDO.format(tema=tema.tema, min_s=MIN_S, max_s=MAX_S, frases=lista,
                                            clave=", ".join(clave), aviso=aviso), llm.ESCRIBIR, temp=0.4)
        try:
            tramos = tramos_validos(d.get("tramos", []), fs, clave)
            break
        except (ValueError, TypeError, IndexError) as e:
            errores.append(str(e))
    else:
        raise RuntimeError("el LLM no dio tramos válidos: " + " | ".join(errores))

    destino = p.ruta("short.mp4")
    # los tiempos de la voz empiezan tras la apertura (clip de su cara)
    from ..contratos import Render
    desfase = p.leer("render.json", Render).apertura_s
    tramos = [(a + desfase, b + desfase, t) for a, b, t in tramos]
    montar(Path(p.leer("calidad.json", Calidad).final), tramos, destino)

    # Misma puerta que el largo, en modo short; el "guion" es lo que se corta.
    from ..puertas.revision import revisar
    texto = " ".join(t for _, _, t in tramos)
    r = revisar(destino, guion=texto, tema=tema.tema, modo="short")
    p.ruta("short_revision.json").write_text(json.dumps(r.a_dict(), ensure_ascii=False, indent=1),
                                             encoding="utf-8")
    if not r.ok:
        raise Bloqueado("revisión del short: " + " | ".join(r.fallos))
    p.escribir(SALIDA, Short(mp4=str(destino), segundos=r.medidas["duracion_s"],
                             tramos=[[round(a, 2), round(b, 2)] for a, b, _ in tramos], texto=texto))
    return f"{r.medidas['duracion_s']}s · {len(tramos)} tramos · voz {r.medidas.get('voz_cobertura', 0):.0%} · {prov}"

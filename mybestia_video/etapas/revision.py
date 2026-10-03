"""Puerta de revisión: mira el vídeo final como lo vería una persona.

Va después de `calidad` (receta + presentador + miniatura) y antes de
`publicar`. Todo local (ffmpeg + faster-whisper), sin Claude: ver
puertas/revision.py para cada comprobación y el caso real del que nace.
"""
from pathlib import Path

from ..contratos import Calidad, Fondos, Guion, Revision, Tema
from ..proyecto import Bloqueado, Proyecto

NOMBRE = "revision"
ENTRADAS = ["calidad.json", "miniatura.json", "guion_verificado.json", "fondos.json"]
SALIDA = "revision.json"


def run(p: Proyecto) -> str:
    from ..puertas.revision import revisar
    tema = p.leer("tema.json", Tema)
    cal = p.leer("calidad.json", Calidad)
    g = p.leer("guion_verificado.json", Guion)
    mini = p.ruta("thumbnail.jpg")
    r = revisar(Path(cal.final), guion=g.texto(), tema=tema.tema, modo=tema.modo, miniatura=mini)
    # El informe se guarda SIEMPRE, también si bloquea: es lo que se mira.
    p.ruta("revision_informe.json").write_text(
        __import__("json").dumps(r.a_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
    # Clips de vídeo IA: ninguno puede haber salido ya en otro vídeo.
    from .. import huellas, legado
    pub = legado.carpeta_om(tema.pid) / "assets/public"
    clips = [pub / v["src"] for k, v in p.leer("fondos.json", Fondos).fondos.items()
             if v.get("type") == "video" and (k.startswith("veo_") or k.startswith("clip_ia"))]
    r.medidas["clips_ia"] = len(clips)
    repetidos = [c.name for c in clips if huellas.ya_usado(c, salvo_video=p.carpeta.name)]
    por_huella = {}
    for c in clips:
        por_huella.setdefault(huellas.huella(c), []).append(c.name)
    dobles = [" = ".join(v) for v in por_huella.values() if len(v) > 1]
    if dobles:
        r.fallos.append(f"el mismo clip dos veces en el vídeo: {'; '.join(dobles)}")
    if not clips:
        r.fallos.append("no lleva ningún clip de vídeo IA nuevo (la receta pide Veo)")
    if repetidos:
        r.fallos.append(f"clips de IA que ya salieron en otro vídeo: {', '.join(repetidos)}")
    p.ruta("revision_informe.json").write_text(
        __import__("json").dumps(r.a_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
    if not r.ok:
        raise Bloqueado("revisión: " + " | ".join(r.fallos))
    huellas.registrar(clips, p.carpeta.name)
    p.escribir(SALIDA, Revision(medidas=r.medidas))
    return f"{r.medidas.get('duracion_s')}s · voz {r.medidas.get('voz_cobertura'):.0%} · {r.medidas.get('lufs')} LUFS"

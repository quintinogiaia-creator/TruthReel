"""Clips de vídeo IA de Flow (Veo) para el gancho y el momento clave.

Si Flow no da NINGÚN clip (alta demanda, cuota del día), la etapa falla como
fallo pasajero: el proyecto se queda en pausa y `seguir` lo reintenta más
tarde. No se monta con clips gastados (ver huellas.py).
"""
from ..contratos import Clips, Guion, Tema
from ..proyecto import Proyecto
from .kit import CARPETA

NOMBRE = "clips"
ENTRADAS = ["tema.json", "guion_verificado.json"]
SALIDA = "clips.json"


def run(p: Proyecto) -> str:
    tema = p.leer("tema.json", Tema)
    g = p.leer("guion_verificado.json", Guion)
    from .. import huellas, legado  # noqa: F401
    from openmontage_run import clips_flow, prompts_veo
    prompts = prompts_veo(tema.tema, g.texto())
    if not prompts:
        raise RuntimeError("el LLM no dio prompts para Veo")
    hechos = [c for c in clips_flow(prompts, p.ruta(CARPETA), tema.modo == "short")
              if not huellas.ya_usado(c)]
    if not hechos:
        raise RuntimeError("Flow no dio ningún clip nuevo (¿alta demanda o cuota?): reintentar más tarde")
    p.escribir(SALIDA, Clips(clips=[str(c) for c in hechos], prompts=prompts))
    return f"flow · {len(hechos)} clips"


def limpiar(p: Proyecto) -> None:
    for c in p.ruta(CARPETA).glob("clip_ia_*.mp4"):
        c.unlink()

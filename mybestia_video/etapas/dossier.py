"""Datos verificados del tema (dossiers/*.json de La Letra Pequeña).

Es una puerta: sin dossier no hay vídeo. Sin datos contrastados el guionista
se inventa precios y porcentajes (pasó el 2026-09-04 y con Security Audit el
2026-09-29), y un desmentido que miente es peor que no publicar.
"""
from ..contratos import Dossier, Tema
from ..proyecto import Bloqueado, Proyecto

NOMBRE = "dossier"
ENTRADAS = ["tema.json"]
SALIDA = "dossier.json"


def run(p: Proyecto) -> str:
    tema = p.leer("tema.json", Tema)
    from .. import legado  # noqa: F401  (rutas del código de antes)
    from pipeline_hf_full import dossier_para
    texto = dossier_para(tema.tema)
    if len(texto) < 200:
        raise Bloqueado(f"no hay dossier verificado para «{tema.tema}» en pipeline_hf/dossiers/")
    p.escribir(SALIDA, Dossier(texto=texto))
    return "dossiers/"

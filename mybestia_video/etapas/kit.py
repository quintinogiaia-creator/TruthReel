"""Recursos propios de la receta: imágenes IA de ComfyUI (y grabación de la web).

Los clips de Flow van en su propia etapa (clips.py) para poder reintentarlos
sin repetir las imágenes.
"""
from ..contratos import Guion, Kit, Tema
from ..proyecto import Proyecto

NOMBRE = "kit"
ENTRADAS = ["tema.json", "guion_verificado.json"]
SALIDA = "kit.json"
CARPETA = "kit_openmontage"


def run(p: Proyecto) -> str:
    tema = p.leer("tema.json", Tema)
    g = p.leer("guion_verificado.json", Guion)
    from .. import legado  # noqa: F401
    from openmontage_run import _preparar_kit
    carpeta = p.ruta(CARPETA)
    bloque = _preparar_kit(tema.tema, tema.modo, g.texto(), carpeta, con_flow=False)
    imgs = [f.stem for f in sorted(carpeta.glob("img_ia_*.png"))]
    p.escribir(SALIDA, Kit(carpeta=str(carpeta), imagenes_ia=imgs, bloque_brief=bloque or ""))
    return f"{len(imgs)} imágenes IA"


def limpiar(p: Proyecto) -> None:
    # solo lo suyo: los clip_ia_*.mp4 de la carpeta son de la etapa clips
    for f in p.ruta(CARPETA).glob("img_ia_*.png"):
        f.unlink()

"""Puerta de calidad: la receta en el vídeo de verdad + presentador.

verificar_receta mira el vídeo y su proyecto (voz de Francis, clips de Veo,
imágenes IA, duración, volumen). Si falla algo, el proyecto queda bloqueado
con la lista de fallos y no se entrega.
"""
import shutil
from pathlib import Path

from ..contratos import Calidad, Kit, Render, Tema
from ..proyecto import Bloqueado, Proyecto

NOMBRE = "calidad"
ENTRADAS = ["render.json"]
SALIDA = "calidad.json"


def run(p: Proyecto) -> str:
    tema = p.leer("tema.json", Tema)
    render = p.leer("render.json", Render)
    kit = p.leer("kit.json", Kit)
    from .. import legado  # noqa: F401
    from openmontage_run import verificar_receta
    from om_sin_claude import _dur
    fallos = verificar_receta(Path(render.mp4), tema.pid, Path(kit.carpeta))
    if fallos:
        raise Bloqueado("no cumple la receta: " + " | ".join(fallos))
    from presentador_overlay import poner
    final = p.ruta("final.mp4")
    con_pres = poner(Path(render.mp4), p.ruta("final_con_presentador.mp4"), vertical=tema.modo == "short",
                     desde=render.apertura_s)
    if not con_pres:
        raise Bloqueado("falta el presentador (webcam de Francis en recuadro)")
    shutil.copy(con_pres, final)
    p.escribir(SALIDA, Calidad(final=str(final), segundos=_dur(final), fallos=[]))
    return "receta ok + presentador"

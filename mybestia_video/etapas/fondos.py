"""Fondos: stock de Pexels + imágenes y clips propios del kit."""
import shutil

from ..contratos import Fondos, Kit, Planos, Tema
from ..proyecto import Proyecto, confirmar

NOMBRE = "fondos"
ENTRADAS = ["planos.json", "kit.json", "clips.json"]
SALIDA = "fondos.json"


def run(p: Proyecto) -> str:
    tema = p.leer("tema.json", Tema)
    pl = p.leer("planos.json", Planos)
    kit = p.leer("kit.json", Kit)
    from pathlib import Path
    from .. import legado
    import om_sin_claude
    with legado.en_openmontage():
        bgs = om_sin_claude.fondos(pl.stock, legado.carpeta_om(tema.pid), Path(kit.carpeta))
    pedidos = {pl[3] for lista in p.leer("planos.json", Planos).planos.values() for pl in lista
               if isinstance(pl, list) and len(pl) > 3 and isinstance(pl[3], str)} - {"ink", "paper"}
    faltan = sorted(pedidos - set(bgs))
    # om_sin_claude.validar los cambiaría por fondo negro sin decir nada
    confirmar(not faltan, f"{len(faltan)} fondos pedidos por los planos no se descargaron: {', '.join(faltan[:8])}")
    p.escribir(SALIDA, Fondos(fondos=bgs))
    return f"{len(bgs)} fondos"


def limpiar(p: Proyecto) -> None:
    from .. import legado
    tema = p.leer("tema.json", Tema)
    shutil.rmtree(legado.carpeta_om(tema.pid) / "assets/public", ignore_errors=True)

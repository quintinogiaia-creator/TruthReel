"""Guion del largo (om_sin_claude.guion) con plan B: Groq y, si cae, Gemini."""
import re

from ..contratos import Dossier, Guion, Tema
from ..proyecto import Proyecto

NOMBRE = "guion"
ENTRADAS = ["tema.json", "dossier.json"]
SALIDA = "guion.json"


def limpiar_espacios(g: dict) -> dict:
    # Groq separa los miles con espacio fino ( ): "8 300" se leía
    # "ocho trescientos" y salía partido en los subtítulos.
    for s in g["secciones"]:
        s["parrafos"] = [re.sub(r"[   ]", " ", x) for x in s["parrafos"]]
    return g


def run(p: Proyecto) -> str:
    tema = p.leer("tema.json", Tema)
    datos = p.leer("dossier.json", Dossier).texto
    from .. import legado
    from ..proveedores import llm
    import om_sin_claude
    with legado.en_openmontage(), legado.con_llm(om_sin_claude, llm.Sesion(llm.ESCRIBIR)) as s:
        g = om_sin_claude.guion(tema.tema, datos)
    p.escribir(SALIDA, Guion.model_validate(limpiar_espacios(g)))
    # `hechos` lee este proveedor del estado para verificar con OTRO modelo
    return s.proveedor

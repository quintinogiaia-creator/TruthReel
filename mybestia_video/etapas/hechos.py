"""Puerta de hechos: Gemini revisa el guion contra el dossier.

Un modelo DISTINTO del que escribe (ARQUITECTURA.md §5): lo que no está en el
dossier se reescribe; si tras las vueltas sigue habiendo fallos graves, el
proyecto queda bloqueado y no hay vídeo.
"""
from ..contratos import Dossier, Guion
from ..proyecto import Bloqueado, Proyecto
from .guion import limpiar_espacios

NOMBRE = "hechos"
ENTRADAS = ["guion.json", "dossier.json"]
SALIDA = "guion_verificado.json"


def run(p: Proyecto) -> str:
    g = p.leer("guion.json", Guion).model_dump()
    datos = p.leer("dossier.json", Dossier).texto
    from .. import legado
    from ..proveedores import llm
    import verificar_hechos
    escritor = p.estado()["etapas"].get("guion", {}).get("proveedor", "groq")
    sesion = llm.Sesion(llm.VERIFICAR, excluir={escritor}, temp=0.1)
    try:
        with legado.con_llm(verificar_hechos, sesion):
            g = verificar_hechos.revisar_guion(g, datos)
    except verificar_hechos.FalloHechos as e:
        raise Bloqueado(f"verificación de hechos: {e}") from e
    verificado = Guion.model_validate(limpiar_espacios(g))
    p.escribir(SALIDA, verificado)
    # El SEO y la web leen script.txt: que diga lo que se narra de verdad.
    from ..contratos import Tema
    tema = p.leer("tema.json", Tema).tema
    p.ruta("script.txt").write_text(f"{tema}\n\n{verificado.texto()}\n", encoding="utf-8")
    return f"{sesion.proveedor} (escribió {escritor})"

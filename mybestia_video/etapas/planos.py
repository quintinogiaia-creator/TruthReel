"""Planos de cada párrafo (Groq) + revisión de rótulos contra el dossier (Gemini)."""
from ..contratos import Dossier, Guion, Kit, Planos
from ..proyecto import Bloqueado, Proyecto

NOMBRE = "planos"
ENTRADAS = ["guion_verificado.json", "kit.json", "dossier.json"]
SALIDA = "planos.json"


def run(p: Proyecto) -> str:
    g = p.leer("guion_verificado.json", Guion).model_dump()
    kit = p.leer("kit.json", Kit)
    datos = p.leer("dossier.json", Dossier).texto
    from .. import legado
    from ..proveedores import llm
    import om_sin_claude
    import verificar_hechos
    with legado.en_openmontage(), legado.con_llm(om_sin_claude, llm.Sesion(llm.ESCRIBIR)) as esc:
        B, stock = om_sin_claude.planos(g, kit.imagenes_ia)
    rev = llm.Sesion(llm.VERIFICAR, excluir={esc.proveedor}, temp=0.1)
    try:
        with legado.con_llm(verificar_hechos, rev):
            B = verificar_hechos.revisar_planos(B, g, datos)
    except verificar_hechos.FalloHechos as e:
        raise Bloqueado(f"rótulos con datos falsos: {e}") from e
    p.escribir(SALIDA, Planos(planos=B, stock=stock))
    return f"{esc.proveedor}+{rev.proveedor}"

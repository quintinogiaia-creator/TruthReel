"""Montaje: props de Remotion, mezcla a −14 LUFS y render 16:9."""
from ..contratos import Fondos, Guion, Planos, Render, Tema, Voz
from ..proyecto import Proyecto, confirmar

NOMBRE = "montaje"
ENTRADAS = ["guion_verificado.json", "planos.json", "voz.json", "fondos.json"]
SALIDA = "render.json"


def run(p: Proyecto) -> str:
    tema = p.leer("tema.json", Tema)
    g = p.leer("guion_verificado.json", Guion).model_dump()
    B = p.leer("planos.json", Planos).planos
    tim = p.leer("voz.json", Voz).tiempos
    bgs = p.leer("fondos.json", Fondos).fondos
    from .. import legado
    import om_sin_claude
    P = legado.carpeta_om(tema.pid)
    with legado.en_openmontage():
        B = om_sin_claude.validar(g, B, set(bgs))
        pr = om_sin_claude.props(g, B, tim, bgs, P)
        om_sin_claude.mezclar(P, pr["durationSeconds"], pr["beats"])
        mp4 = om_sin_claude.render(P, tema.pid)
    seg, voz_s = om_sin_claude._dur(mp4), tim["words"][-1]["endMs"] / 1000
    confirmar(voz_s <= seg <= voz_s + 15, f"el render dura {seg:.0f}s y la voz {voz_s:.0f}s: se cortó algo")
    p.escribir(SALIDA, Render(mp4=str(mp4), segundos=seg))
    return "remotion"

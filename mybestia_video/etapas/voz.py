"""Narración párrafo a párrafo y tiempos de cada palabra (Whisper).

VoiceStudio con la voz de Francis por defecto; OM_VOZ=sharvard usa Piper.
Si VoiceStudio cae a otro proveedor, om_sin_claude.narrar lanza error: un
vídeo con voz equivocada no cumple la receta.
"""
import json
import os
import shutil

from ..contratos import Guion, Tema, Voz
from ..proyecto import Proyecto, confirmar

NOMBRE = "voz"
ENTRADAS = ["tema.json", "guion_verificado.json"]
SALIDA = "voz.json"


def run(p: Proyecto) -> str:
    tema = p.leer("tema.json", Tema)
    g = p.leer("guion_verificado.json", Guion).model_dump()
    voz = os.environ.get("OM_VOZ", "francis").lower()
    proveedor = "sharvard" if voz == "sharvard" else "voicestudio"
    from .. import legado
    import om_sin_claude
    P = legado.carpeta_om(tema.pid)
    (P / "artifacts").mkdir(parents=True, exist_ok=True)
    # Lo que leen verificar_receta (qué voz se usó) y el SEO de antes.
    json.dump({"sections": [{"id": s["id"], "text": " ".join(s["parrafos"])} for s in g["secciones"]],
               "voz": proveedor},
              open(P / "artifacts/script.json", "w"), ensure_ascii=False, indent=1)
    with legado.en_openmontage():
        om_sin_claude.narrar(g, P, voz)
        tiempos = om_sin_claude.alinear(g, P)
    palabras = sum(len(x.split()) for s in g["secciones"] for x in s["parrafos"])
    confirmar(len(tiempos.get("words", [])) >= 0.95 * palabras,
              f"la voz alineada tiene {len(tiempos.get('words', []))} palabras y el guion {palabras}: falta audio")
    p.escribir(SALIDA, Voz(proveedor=proveedor, tiempos=tiempos))
    return proveedor


def limpiar(p: Proyecto) -> None:
    # narrar() reutiliza cualquier wav que ya exista: sin esto, rehacer la voz
    # tras cambiar el guion mezclaría audios del guion viejo.
    from .. import legado
    tema = p.leer("tema.json", Tema)
    shutil.rmtree(legado.carpeta_om(tema.pid) / "assets/audio", ignore_errors=True)

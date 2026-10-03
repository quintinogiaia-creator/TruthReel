"""Subida a YouTube + web + listas + cola social (tramo _publicar de antes).

Nunca se ejecuta sola: hay que pedirla con `mybestia-video seguir X --subir`
después de que Francis haya visto el vídeo y la miniatura.
"""
import argparse

from ..contratos import Calidad, Publicado, Tema
from ..proyecto import Proyecto

NOMBRE = "publicar"
ENTRADAS = ["calidad.json", "revision.json"]
SALIDA = "publicado.json"


def run(p: Proyecto) -> str:
    tema = p.leer("tema.json", Tema)
    cal = p.leer("calidad.json", Calidad)
    from .. import legado
    import pipeline_hf_full as hf
    marca = legado.PIPELINE_HF / ".last_long_url.txt"
    antes = marca.read_text().strip() if marca.exists() else ""
    from pathlib import Path
    rc = hf._publicar(argparse.Namespace(mode=tema.modo, no_upload=False), p.carpeta, Path(cal.final),
                      tema.tema, tema.tema, tema.categoria, Path(cal.final).stat().st_size / 1e6)
    url = marca.read_text().strip() if marca.exists() else ""
    if rc != 0 or not url or url == antes:
        raise RuntimeError("la subida no devolvió URL nueva (¿cuota? mira la cola de subida)")
    p.escribir(SALIDA, Publicado(youtube_url=url, titulo=tema.tema))
    return url

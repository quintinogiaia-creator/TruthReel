"""Elegir el siguiente tema para el modo automático.

Solo sirve un tema que (1) está en el plan (pipeline_hf/topics_plan.txt),
(2) no está publicado ni cubierto en el canal y (3) TIENE dossier verificado:
sin dossier el guion se inventa las cifras y la puerta de dossier lo bloquearía
igualmente, así que ni se empieza.
"""
from __future__ import annotations

from . import legado  # noqa: F401


def siguiente_tema() -> str:
    import pipeline_hf_full as hf
    try:
        lineas = hf.PLAN_TOPICS.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return ""
    try:
        from youtube_direct import titulos_del_canal
        del_canal = [t for t in titulos_del_canal() if t.strip()]
    except Exception:
        del_canal = []
    for linea in lineas:
        t = linea.strip()
        if not t or t.startswith("#"):
            continue
        if hf._title_already_published(t) or hf._title_already_published(t[:90]):
            continue
        if del_canal and hf._ya_esta_en_el_canal(t, del_canal):
            continue
        if len(hf.dossier_para(t)) >= 200:
            return t[:90]
    return ""

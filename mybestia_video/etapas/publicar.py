"""Subida a YouTube del largo y del short + web + listas + cola social.

Nunca se ejecuta sola: `mybestia-video seguir X --subir`, después de que
Francis haya visto el vídeo, el short y la miniatura.

No usa `_publicar` del pipeline viejo: ese REGENERA la miniatura con el
sistema antiguo (fondo fijo, foto repetida) y machacaba la que ya pasó la
puerta de miniatura (2026-10-03). Aquí se sube exactamente lo revisado.
"""
from pathlib import Path

from ..contratos import Calidad, Miniatura, Publicado, Short, Tema
from ..proyecto import Proyecto, confirmar

NOMBRE = "publicar"
ENTRADAS = ["calidad.json", "revision.json", "miniatura.json", "short.json"]
SALIDA = "publicado.json"
TAGS_BASE = ["mybestia", "francis quintino", "IA", "inteligencia artificial", "claude code",
             "la letra pequeña", "automatización"]


def _tags(seo: dict) -> list[str]:
    propios = [t.strip() for t in seo.get("tags", "").replace("#", "").split(",") if t.strip()]
    return (propios + TAGS_BASE)[:20]


def run(p: Proyecto) -> str:
    tema = p.leer("tema.json", Tema)
    cal = p.leer("calidad.json", Calidad)
    mini = p.leer("miniatura.json", Miniatura)
    corto = p.leer("short.json", Short)
    from .. import legado
    import pipeline_hf_full as hf
    from upload_youtube import upload_to_youtube

    guion = p.ruta("script.txt").read_text(encoding="utf-8") if p.ruta("script.txt").exists() else ""
    seo = hf.generate_seo_pack(tema.tema, guion=guion)
    titulo = (seo.get("title") or tema.tema)[:100]

    # 1) Largo, con SU miniatura revisada
    desc = hf.build_yt_description(seo, topic=tema.tema, category=tema.categoria, mode="long", yt_title=titulo)
    url = upload_to_youtube(cal.final, titulo, desc, tags=_tags(seo), thumbnail_path=mini.ruta,
                            category=tema.categoria, topic=tema.tema, mode="long")
    confirmar(bool(url), "YouTube no devolvió la URL del largo (¿cuota? mira la cola de subida)")
    (legado.PIPELINE_HF / ".last_long_url.txt").write_text(url, encoding="utf-8")
    yt_id = url.split("v=")[-1].split("&")[0].rsplit("/", 1)[-1]

    # 2) Short: la descripción enlaza el largo (build_yt_description lee .last_long_url)
    t_corto = titulo if len(titulo) <= 60 else titulo[:60].rsplit(" ", 1)[0]
    t_corto = f"{t_corto} #Shorts"[:100]
    desc_corto = hf.build_yt_description(seo, topic=tema.tema, category=tema.categoria, mode="short",
                                         yt_title=t_corto)
    url_corto = upload_to_youtube(corto.mp4, t_corto, desc_corto, tags=_tags(seo), thumbnail_path=None,
                                  category=tema.categoria, topic=tema.tema, mode="short")

    # 3) Web, listas y cola social (fallos aquí no deshacen la subida: se avisan)
    avisos = []
    try:
        from playlists import add_video_to_playlist
        if not add_video_to_playlist(yt_id, tema.categoria):
            from playlist_queue import enqueue
            enqueue(yt_id, tema.categoria, titulo)
    except Exception as e:
        avisos.append(f"lista: {e}")
    try:
        hf.publish_video(yt_id, titulo, desc)
        hf.publish_post(titulo, desc, category=tema.categoria, youtube_url=url)
    except Exception as e:
        avisos.append(f"web: {e}")
    try:
        hf._push_to_social_queue(title=titulo, description=desc, video_path=cal.final,
                                 youtube_url=url, thumbnail_path=mini.ruta)
    except Exception as e:
        avisos.append(f"redes: {e}")
    for t in (titulo, tema.tema, tema.tema + " "):
        hf._mark_title_published(t)

    p.escribir(SALIDA, Publicado(youtube_url=url, titulo=titulo, short_url=url_corto or "", avisos=avisos))
    return f"{url} · short {url_corto or 'NO subido'}" + (f" · avisos: {'; '.join(avisos)}" if avisos else "")

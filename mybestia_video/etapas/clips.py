"""Clips de vídeo IA de Flow (Veo) para el gancho y el momento clave.

Si Flow no da NINGÚN clip (alta demanda, cuota del día), la etapa falla como
fallo pasajero: el proyecto se queda en pausa y `seguir` lo reintenta más
tarde. No se monta con clips gastados (ver huellas.py).
"""
from ..contratos import Clips, Guion, Tema
from ..proyecto import Proyecto, confirmar
from .kit import CARPETA

NOMBRE = "clips"
CLIP_CARA = "clip_cara.mp4"   # apertura: su cara, con el sonido del propio clip
ENTRADAS = ["tema.json", "guion_verificado.json"]
SALIDA = "clips.json"


PEDIDO_CARA = """Escribe UN prompt para Veo (clip de 8 s) para el GANCHO de un vídeo sobre:
{tema}
El protagonista es "el hombre de la foto": bien vestido, seguro, transmite
confianza y control. Ponlo en una escena impactante y concreta que represente
el tema (qué pasa a su alrededor, qué hace él, qué siente quien lo ve).
1-2 frases en español, lenguaje natural, sin jerga de cámara, sin texto en
pantalla, sin logos ni marcas, sin personas famosas. Si el hombre habla, que
diga EN ESPAÑOL una sola frase corta de gancho, en forma de pregunta y fiel al
tema (nada de afirmar cifras ni resultados).
Responde SOLO JSON: {{"prompt": "..."}}"""


def run(p: Proyecto) -> str:
    tema = p.leer("tema.json", Tema)
    g = p.leer("guion_verificado.json", Guion)
    from .. import huellas, legado  # noqa: F401
    from ..proveedores import foto_persona, llm
    from openmontage_run import clips_flow, prompts_veo
    from PIL import Image
    # Gancho CON la cara de Francis (2026-10-03): foto nueva suya como
    # ingrediente de Flow. El segundo clip, el momento clave, sin foto.
    ref = p.ruta("clip_ref.png")
    foto_persona.generar(ref, video=p.carpeta.name)
    ref_jpg = p.ruta("clip_ref.jpg")
    im = Image.open(ref).convert("RGBA")
    fondo = Image.new("RGBA", im.size, (58, 58, 62, 255))
    fondo.alpha_composite(im)
    fondo.convert("RGB").save(ref_jpg, quality=92)
    d, _ = llm.json_de(PEDIDO_CARA.format(tema=tema.tema), llm.ESCRIBIR, temp=0.8)
    cara = str(d.get("prompt", "")).strip()
    otros = prompts_veo(tema.tema, g.texto())
    confirmar(bool(cara) and bool(otros), "el LLM no dio prompts para Veo")
    prompts = [cara, otros[-1]]
    hechos = [c for c in clips_flow(prompts, p.ruta(CARPETA), tema.modo == "short", imagenes=[ref_jpg, None])
              if not huellas.ya_usado(c)]
    if not hechos:
        raise RuntimeError("Flow no dio ningún clip nuevo (¿cuota del día?): reintentar más tarde")
    # El de su cara abre el vídeo con SU sonido (Francis 2026-10-03: "el vídeo
    # tiene sonido, que no lo pise"): se aparta de los fondos de Remotion.
    gancho = p.ruta(CARPETA) / "clip_ia_gancho.mp4"
    if gancho.exists():
        gancho.replace(p.ruta(CARPETA) / CLIP_CARA)
        hechos = [p.ruta(CARPETA) / CLIP_CARA if c == gancho else c for c in hechos]
    p.escribir(SALIDA, Clips(clips=[str(c) for c in hechos], prompts=prompts))
    return f"flow · {len(hechos)} clips (gancho con su cara)"


def limpiar(p: Proyecto) -> None:
    for c in list(p.ruta(CARPETA).glob("clip_ia_*.mp4")) + [p.ruta(CARPETA) / CLIP_CARA]:
        c.unlink(missing_ok=True)

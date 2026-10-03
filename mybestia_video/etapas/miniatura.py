"""Puerta de miniatura: gancho verificado contra el dossier + imagen.

Hasta 3 ganchos del LLM y, si ninguno pasa, el recorte del título; cada uno lo
revisa Gemini contra los datos y el guion. Si no pasa ninguno, no hay vídeo:
una miniatura que miente es lo primero que ve la gente.
"""
from ..contratos import Calidad, Dossier, Guion, Miniatura, Tema
from ..proyecto import Bloqueado, Proyecto

NOMBRE = "miniatura"
ENTRADAS = ["calidad.json", "guion_verificado.json", "dossier.json"]
SALIDA = "miniatura.json"


PEDIDO = """Escribe 3 textos GRANDES para la miniatura de YouTube de este vídeo.
Vídeo: {titulo}

Cada uno de 2 a 4 palabras en español, que den curiosidad, y que sean CIERTOS
según estos DATOS: si nombras lo que hace la herramienta, usa su verbo real (no
"crea" si modifica, no "gratis" si hay partes de pago). Puede llevar una cifra
de los DATOS o el nombre del producto. Si el vídeo matiza o desmiente la
promesa del viral, la promesa solo puede ir EN PREGUNTA ("¿Cualquier juego?",
"¿De verdad gratis?"), nunca afirmada como si fuera verdad. Sin acusaciones (estafa, timo, mienten),
sin comillas, sin emojis, sin dos puntos.
Responde SOLO JSON: {{"ganchos": ["...", "...", "..."]}}

DATOS:
{datos}"""


def candidatos(titulo: str, datos: str):
    """Ganchos escritos CON el dossier delante (antes solo veían el título y
    salió «CREA JUEGOS CON IA» para una herramienta que modifica juegos) y, al
    final, el recorte del propio título."""
    from ..proveedores import llm
    from .. import legado  # noqa: F401
    from thumb_bestia import _hook
    try:
        d, _ = llm.json_de(PEDIDO.format(titulo=titulo, datos=datos[:4000]), llm.ESCRIBIR, temp=0.8)
        for g in d.get("ganchos", [])[:3]:
            g = str(g).strip().strip('"«»').replace(":", "")
            if 1 < len(g.split()) <= 5 and len(g) <= 32:
                yield g
    except llm.SinProveedor as e:
        print(f"[miniatura] sin ganchos del LLM: {e}")
    yield _hook(titulo).replace("|", " ")


PEDIDO_FONDO = """Describe en inglés, en una sola frase para Stable Diffusion, el FONDO
de la miniatura de YouTube de este vídeo: una escena visual impactante y
concreta del TEMA (objetos, lugar, luz, color), distinta de un teclado o una
pantalla de código genéricos. Sin personas, sin texto, sin logos.
Vídeo: {titulo}
Responde SOLO JSON: {{"fondo": "..."}}"""
INTENTOS_FONDO = 3


def _gancho_verificado(tema, datos, guion) -> tuple[str, list[str]]:
    from .. import legado
    from ..proveedores import llm
    import verificar_hechos
    rechazados = []
    for g in candidatos(tema.tema, datos):
        with legado.con_llm(verificar_hechos, llm.Sesion(llm.VERIFICAR, temp=0.1)):
            fallos = verificar_hechos.revisar_gancho(g, datos, guion)
        if not fallos:
            return g, rechazados
        rechazados.append(f"«{g}»: {fallos[0].get('motivo', '')}")
    raise Bloqueado("ningún gancho de miniatura pasa la verificación: " + " | ".join(rechazados))


def run(p: Proyecto) -> str:
    tema = p.leer("tema.json", Tema)
    cal = p.leer("calidad.json", Calidad)
    datos = p.leer("dossier.json", Dossier).texto
    guion = p.leer("guion_verificado.json", Guion).texto()
    from .. import huellas, legado  # noqa: F401
    from ..proveedores import foto_persona, llm
    from thumb_bestia import generate_bestia_thumbnail
    gancho, rechazados = _gancho_verificado(tema, datos, guion)
    video = p.carpeta.name

    # Foto NUEVA de Francis (nunca repetida, ni rotando: 2026-10-03)
    foto = p.ruta("francis_foto.png")
    info_foto = foto_persona.generar(foto, video=video)

    destino, fondo = p.ruta("thumbnail.jpg"), p.ruta("thumbnail.iabg.png")
    for intento in range(INTENTOS_FONDO):
        d, _ = llm.json_de(PEDIDO_FONDO.format(titulo=tema.tema), llm.ESCRIBIR, temp=0.9)
        prompt_fondo = str(d.get("fondo", "")).strip() or None
        fondo.unlink(missing_ok=True)
        if not generate_bestia_thumbnail(tema.tema, str(destino), video_path=cal.final, etiqueta=tema.categoria,
                                         vertical=tema.modo == "short", gancho=gancho,
                                         prompt_fondo=prompt_fondo, fondo_nuevo=True, foto=str(foto)):
            raise RuntimeError("thumb_bestia no generó la imagen")
        # Puerta: ni el fondo ni la miniatura entera pueden parecerse a una ya usada
        ya = (fondo.exists() and huellas.imagen_parecida(fondo, "fondo", salvo_video=video)) \
            or huellas.imagen_parecida(destino, "miniatura", salvo_video=video)
        if not ya:
            break
        print(f"[miniatura] se parece a la de {ya}; otro fondo")
    else:
        raise Bloqueado(f"tras {INTENTOS_FONDO} fondos, la miniatura sigue pareciéndose a una ya usada")
    if fondo.exists():
        huellas.registrar_imagen(fondo, "fondo", video)
    huellas.registrar_imagen(destino, "miniatura", video, {"foto": info_foto["ref"]})
    p.escribir(SALIDA, Miniatura(ruta=str(destino), gancho=gancho, rechazados=rechazados,
                                 foto=info_foto, prompt_fondo=prompt_fondo or ""))
    return f"«{gancho}» · foto nueva (parecido {info_foto['parecido']}) · fondo nuevo"

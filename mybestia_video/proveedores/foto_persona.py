"""Fotos NUEVAS de Francis para cada miniatura, generadas en local con InstantID.

Francis, 2026-10-03: "genéralas por IA sin perder mis rasgos ni deformarme,
que parezca otra foto normal, con otra ropa y otra pose... bien vestido, bien
peinado, que transmita confianza". Y nunca repetida: "ni rotando".

Cómo:
  1. Una de sus fotos reales (las 37 del entrenamiento) como referencia de cara.
  2. ComfyUI + InstantID (RealVisXL) genera la foto con ropa y pose nuevas,
     sobre fondo liso para recortarla limpia.
  3. Puerta de parecido (cara_parecido, insightface): una sola cara y
     parecido >= UMBRAL con sus fotos reales; si no, otra semilla.
  4. Recorte con rembg -> PNG con transparencia, listo para la miniatura.

Todo gratis y en el PC (sin Flow ni APIs de pago). Usa el turno de GPU para no
coincidir con la voz ni con otro render (regla de un proceso pesado a la vez).
"""
from __future__ import annotations

import json
import random
import time
import urllib.request
import uuid
from pathlib import Path

from .. import legado  # noqa: F401

COMFY = "http://127.0.0.1:8188"
REFERENCIAS = Path.home() / "sd-scripts/train_data/francis_lora/20_francis"
INTENTOS = 4
# Solo referencias en las que su cara se reconoce bien (una sola cara, de
# frente): con cualquiera de las 37, el parecido de lo generado bajaba a 0,43.
REF_MIN = 0.78
CACHE_REFS = Path.home() / ".cache/mybestia/refs_francis.json"
# Sus rasgos en el prompt: sin ellos SDXL tiraba hacia "un hombre" genérico.
RASGOS = ("a 40 year old Spanish man with light olive skin, short dark hair with a fade on the sides, "
          "light stubble, slim build")

ROPA = [
    "a tailored navy blue suit with a crisp white shirt, no tie",
    "a charcoal grey blazer over a black t-shirt",
    "a smart black turtleneck sweater",
    "a light blue oxford shirt with rolled sleeves",
    "a dark green bomber jacket over a white shirt",
    "a beige linen blazer with an open-collar shirt",
    "a black leather jacket over a grey henley",
    "a white shirt and dark waistcoat, sleeves rolled up",
]
POSE = [
    "arms crossed, confident half smile, looking at the camera",
    "one hand in pocket, relaxed and confident, slight smile",
    "pointing to the side with one hand, enthusiastic expression",
    "hand on chin, thoughtful confident look at the camera",
    "leaning slightly forward, friendly genuine smile",
    "adjusting the jacket cuff, self-assured look",
]
FONDO = ["plain light grey", "plain dark grey", "plain white", "plain soft blue"]
NEGATIVO = ("deformed face, distorted features, asymmetric eyes, extra fingers, bad hands, "
            "cartoon, painting, illustration, 3d render, blurry, lowres, watermark, text, logo, "
            "messy hair, unkempt, frown, looking down, low angle selfie")


def _post(ruta: str, datos: dict) -> dict:
    req = urllib.request.Request(f"{COMFY}{ruta}", data=json.dumps(datos).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def _subir(foto: Path) -> str:
    """Sube la referencia a ComfyUI (input/) y devuelve su nombre allí."""
    import requests
    with open(foto, "rb") as f:
        r = requests.post(f"{COMFY}/upload/image", files={"image": (foto.name, f, "image/jpeg")},
                          data={"overwrite": "true"}, timeout=60)
    r.raise_for_status()
    return r.json()["name"]


def workflow(refs: list[str], positivo: str, semilla: int) -> dict:
    """Un solo grafo de ComfyUI en dos pasadas:
      A) SDXL normal con el prompt (sin cara de nadie): solo para sacar la POSE.
         Sin esto, InstantID copiaba el ángulo de selfie desde abajo de la
         foto de referencia.
      B) InstantID con la cara de 3 fotos suyas a la vez (la media es más fiel
         que una sola) y los puntos de la cara de la pasada A."""
    wf = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "realvisxl.safetensors"}},
        "2": {"class_type": "InstantIDModelLoader", "inputs": {"instantid_file": "ip-adapter.bin"}},
        "3": {"class_type": "InstantIDFaceAnalysis", "inputs": {"provider": "CUDA"}},
        "4": {"class_type": "ControlNetLoader",
              "inputs": {"control_net_name": "instantid/diffusion_pytorch_model.safetensors"}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": positivo, "clip": ["1", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": NEGATIVO, "clip": ["1", 1]}},
        "9": {"class_type": "EmptyLatentImage", "inputs": {"width": 896, "height": 1152, "batch_size": 1}},
        # A) pose
        "20": {"class_type": "KSampler",
               "inputs": {"model": ["1", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["9", 0],
                          "seed": semilla + 1, "steps": 20, "cfg": 5.0, "sampler_name": "dpmpp_2m",
                          "scheduler": "karras", "denoise": 1.0}},
        "21": {"class_type": "VAEDecode", "inputs": {"samples": ["20", 0], "vae": ["1", 2]}},
    }
    # caras de referencia, al mismo tamaño para poder juntarlas en un lote
    previo = None
    for i, ref in enumerate(refs):
        wf[f"3{i}"] = {"class_type": "LoadImage", "inputs": {"image": ref}}
        wf[f"4{i}"] = {"class_type": "ImageScale", "inputs": {"image": [f"3{i}", 0], "upscale_method": "lanczos",
                                                                "width": 1024, "height": 1024, "crop": "center"}}
        if previo is None:
            previo = [f"4{i}", 0]
        else:
            wf[f"5{i}"] = {"class_type": "ImageBatch", "inputs": {"image1": previo, "image2": [f"4{i}", 0]}}
            previo = [f"5{i}", 0]
    # B) cara
    wf["8"] = {"class_type": "ApplyInstantID",
               "inputs": {"instantid": ["2", 0], "insightface": ["3", 0], "control_net": ["4", 0],
                          "image": previo, "image_kps": ["21", 0], "model": ["1", 0],
                          "positive": ["6", 0], "negative": ["7", 0],
                          "weight": 1.0, "start_at": 0.0, "end_at": 1.0}}
    wf["10"] = {"class_type": "KSampler",
                "inputs": {"model": ["8", 0], "positive": ["8", 1], "negative": ["8", 2], "latent_image": ["9", 0],
                           "seed": semilla, "steps": 30, "cfg": 4.5, "sampler_name": "ddpm",
                           "scheduler": "karras", "denoise": 1.0}}
    wf["11"] = {"class_type": "VAEDecode", "inputs": {"samples": ["10", 0], "vae": ["1", 2]}}
    wf["12"] = {"class_type": "SaveImage", "inputs": {"images": ["11", 0], "filename_prefix": "francis_foto"}}
    return wf


def _render(wf: dict, timeout: int = 420) -> bytes | None:
    pid = _post("/prompt", {"prompt": wf, "client_id": uuid.uuid4().hex}).get("prompt_id")
    if not pid:
        return None
    t0 = time.time()
    while time.time() - t0 < timeout:
        h = json.loads(urllib.request.urlopen(f"{COMFY}/history/{pid}", timeout=10).read())
        if pid in h:
            imgs = h[pid].get("outputs", {}).get("12", {}).get("images", [])
            if not imgs:
                print(f"[foto] ComfyUI terminó sin imagen: {str(h[pid].get('status'))[-400:]}")
                return None
            i = imgs[0]
            return urllib.request.urlopen(
                f"{COMFY}/view?filename={i['filename']}&subfolder={i.get('subfolder', '')}&type=output",
                timeout=30).read()
        time.sleep(2)
    print("[foto] timeout esperando a ComfyUI")
    return None


def _menos_usada(opciones: list[str], campo: str, rnd: random.Random) -> str:
    """La ropa (o pose) que menos ha salido; empate al azar. Sin esto, dos
    fotos seguidas salieron con la misma camisa azul."""
    from .. import huellas
    usos = {o: 0 for o in opciones}
    for reg in huellas._imagenes().values():
        if reg.get(campo) in usos:
            usos[reg[campo]] += 1
    minimo = min(usos.values())
    return rnd.choice([o for o, n in usos.items() if n == minimo])


def referencias() -> list[Path]:
    """Sus fotos donde la cara se reconoce mejor (puntuadas una vez y guardadas)."""
    try:
        nombres = json.loads(CACHE_REFS.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        from cara_parecido import puntuar
        nombres = []
        for r in sorted(REFERENCIAS.glob("francis_*.jpg")):
            p = puntuar(r)
            if p["caras"] == 1 and p["parecido"] >= REF_MIN:
                nombres.append(r.name)
        CACHE_REFS.parent.mkdir(parents=True, exist_ok=True)
        CACHE_REFS.write_text(json.dumps(nombres))
    return [REFERENCIAS / n for n in nombres if (REFERENCIAS / n).exists()]


def _recortar(png: Path, destino: Path) -> None:
    from PIL import Image
    from rembg import new_session, remove
    out = remove(Image.open(png).convert("RGB"), session=new_session("u2net_human_seg"))
    out.save(destino)


def generar(destino: Path, *, video: str, rnd: random.Random | None = None) -> dict:
    """Deja en `destino` (PNG con transparencia) una foto nueva de Francis.
    Devuelve {ref, prompt, parecido, semilla}. Lanza RuntimeError si ninguna
    candidata pasa el parecido (mejor sin foto que una cara deformada)."""
    from cara_parecido import UMBRAL, puntuar
    from turno_gpu import turno
    from .. import huellas
    rnd = rnd or random.SystemRandom()
    refs = referencias()
    if not refs:
        raise RuntimeError(f"no hay fotos de referencia en {REFERENCIAS}")
    mejor = None
    for intento in range(INTENTOS):
        elegidas = rnd.sample(refs, min(3, len(refs)))
        ropa, pose = _menos_usada(ROPA, "ropa", rnd), _menos_usada(POSE, "pose", rnd)
        positivo = (f"professional photograph of {RASGOS}, wearing {ropa}, {pose}, "
                    "neatly styled hair, well groomed, trustworthy and approachable, medium shot from the waist up, "
                    f"{rnd.choice(FONDO)} studio background, soft studio lighting, 85mm lens, sharp focus, "
                    "photorealistic, natural skin")
        semilla = rnd.randrange(2 ** 31)
        with turno("imagenes"):
            datos = _render(workflow([_subir(r) for r in elegidas], positivo, semilla))
        if not datos:
            continue
        cand = destino.with_suffix(f".cand{intento}.png")
        cand.write_bytes(datos)
        p = puntuar(cand)
        print(f"[foto] intento {intento + 1}: parecido {p['parecido']:.2f}, caras {p['caras']}")
        if p["caras"] != 1 or p["parecido"] < UMBRAL:
            continue
        if huellas.imagen_parecida(cand, "foto", salvo_video=video):
            print("[foto] se parece a una foto ya usada; otra")
            continue
        if not mejor or p["parecido"] > mejor["parecido"]:
            mejor = {"cand": cand, "ropa": ropa, "pose": pose, "ref": "+".join(r.name for r in elegidas), "prompt": positivo, "parecido": round(p["parecido"], 3),
                     "semilla": semilla}
        if p["parecido"] >= UMBRAL + 0.07:
            break  # suficientemente fiel: no gastar más GPU
    if not mejor:
        raise RuntimeError(f"ninguna de {INTENTOS} fotos generadas se parece lo bastante a Francis")
    _recortar(mejor["cand"], destino)
    huellas.registrar_imagen(mejor["cand"], "foto", video,
                             {"ref": mejor["ref"], "ropa": mejor["ropa"], "pose": mejor["pose"]})
    return {k: v for k, v in mejor.items() if k != "cand"}

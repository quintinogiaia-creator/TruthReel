"""Registro de clips de vídeo IA ya usados: ninguno sale en dos vídeos.

Francis, 2026-10-03: "no subas nada con el mismo de Flow que ya hemos subido,
ninguno igual... ya es plantilla, si no lo variamos en cada vídeo se mata".
La huella es el sha256 del fichero del clip: una copia con otro nombre sigue
siendo el mismo clip. Lo leen la biblioteca (om_sin_claude.fondos) para no
ofrecer clips gastados y la puerta de revisión para bloquear si se coló uno.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

REGISTRO = Path(os.environ.get("MYBESTIA_HUELLAS", Path.home() / ".local/share/mybestia/clips_usados.json"))


def huella(f: Path) -> str:
    h = hashlib.sha256()
    with open(f, "rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def usados() -> dict:
    try:
        return json.loads(REGISTRO.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def ya_usado(f: Path, salvo_video: str = "") -> bool:
    """True si el clip salió en otro vídeo (`salvo_video`: el propio, que al
    repetir su revisión se encontraría a sí mismo en el registro)."""
    reg = usados().get(huella(f))
    return bool(reg) and reg.get("video") != salvo_video


def registrar(clips: list[Path], video: str) -> None:
    reg = usados()
    for c in clips:
        reg.setdefault(huella(c), {"clip": c.name, "video": video,
                                   "cuando": datetime.now().isoformat(timespec="seconds")})
    REGISTRO.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRO.with_suffix(".tmp")
    tmp.write_text(json.dumps(reg, ensure_ascii=False, indent=1))
    tmp.replace(REGISTRO)


# ---------------------------------------------------------------- imágenes
# Miniaturas: Francis, 2026-10-03, "esa miniatura ya la hemos utilizado".
# Una imagen re-generada nunca es idéntica byte a byte, así que aquí la
# huella es PERCEPTUAL (dHash de 64 bits): dos fondos que se ven iguales dan
# huellas a pocos bits de distancia.
REGISTRO_IMAGENES = REGISTRO.with_name("imagenes_usadas.json")
UMBRAL_PARECIDA = 10   # bits distintos de 64; por debajo, "es la misma imagen"


def dhash(f: Path) -> int:
    from PIL import Image
    im = Image.open(f).convert("L").resize((9, 8), Image.LANCZOS)
    px = list(im.getdata())
    bits = 0
    for fila in range(8):
        for col in range(8):
            bits = (bits << 1) | (px[fila * 9 + col] > px[fila * 9 + col + 1])
    return bits


def _imagenes() -> dict:
    try:
        return json.loads(REGISTRO_IMAGENES.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def imagen_parecida(f: Path, tipo: str, salvo_video: str = "") -> str | None:
    """Devuelve el vídeo donde ya salió una imagen parecida (o None)."""
    h = dhash(f)
    for clave, reg in _imagenes().items():
        if reg.get("tipo") == tipo and reg.get("video") != salvo_video \
                and bin(int(clave, 16) ^ h).count("1") <= UMBRAL_PARECIDA:
            return reg.get("video", "?")
    return None


def registrar_imagen(f: Path, tipo: str, video: str, extra: dict | None = None) -> None:
    reg = _imagenes()
    reg[f"{dhash(f):016x}"] = {"tipo": tipo, "video": video, "fichero": f.name,
                               "cuando": datetime.now().isoformat(timespec="seconds"), **(extra or {})}
    REGISTRO_IMAGENES.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRO_IMAGENES.with_suffix(".tmp")
    tmp.write_text(json.dumps(reg, ensure_ascii=False, indent=1))
    tmp.replace(REGISTRO_IMAGENES)


def foto_menos_usada(fotos: list[Path]) -> Path:
    """La foto de Francis que hace más tiempo que no sale (nunca la última)."""
    usos = {}
    for reg in _imagenes().values():
        if reg.get("foto"):
            usos[reg["foto"]] = max(usos.get(reg["foto"], ""), reg.get("cuando", ""))
    return min(fotos, key=lambda f: usos.get(f.name, ""))

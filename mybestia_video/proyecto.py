"""Carpeta de un vídeo, su estado y los puntos de control.

Un proyecto es una carpeta en `proyectos/` con un JSON por etapa y un
`estado.json` que dice qué etapa se hizo, con qué entradas (hash), cuánto tardó
y por qué falló. Con eso:

- `seguir` salta todo lo que ya está hecho y con las mismas entradas;
- `rehacer --desde voz` borra la voz y lo que depende de ella, y nada más.

Por qué ficheros y no una base de datos: ver ARQUITECTURA.md, §5.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

RAIZ = Path(os.environ.get("MYBESTIA_PROYECTOS", Path(__file__).resolve().parent.parent / "proyectos"))

M = TypeVar("M", bound=BaseModel)


class Bloqueado(RuntimeError):
    """Una puerta de calidad no pasa (hechos falsos, receta incumplida).

    No es un fallo pasajero: `seguir` NO lo reintenta. Hay que mirar el motivo
    y lanzar `rehacer --desde <etapa>` a propósito."""


def confirmar(condicion: bool, motivo: str) -> None:
    """Cada etapa confirma su salida antes de darla por hecha: si no cumple lo
    que necesita la siguiente, falla AQUÍ con el motivo (nada de seguir con un
    sustituto escondido, como el fondo negro cuando no llegaba una imagen)."""
    if not condicion:
        raise RuntimeError(motivo)


class Proyecto:
    def __init__(self, carpeta: Path):
        self.carpeta = Path(carpeta)
        self._estado_path = self.carpeta / "estado.json"

    # ------------------------------------------------------------ creación
    @classmethod
    def crear(cls, slug: str) -> "Proyecto":
        carpeta = RAIZ / f"{slug}_{datetime.now():%Y%m%d_%H%M%S}"
        carpeta.mkdir(parents=True)
        p = cls(carpeta)
        p._guardar_estado({"creado": datetime.now().isoformat(timespec="seconds"), "etapas": {}})
        return p

    @classmethod
    def abrir(cls, nombre: str) -> "Proyecto":
        """Por ruta, por nombre exacto o por el principio del nombre."""
        ruta = Path(nombre)
        if not ruta.is_dir():
            ruta = RAIZ / nombre
        if not ruta.is_dir():
            candidatos = sorted(RAIZ.glob(f"{nombre}*"))
            if len(candidatos) != 1:
                raise FileNotFoundError(f"proyecto '{nombre}': {len(candidatos)} coincidencias")
            ruta = candidatos[0]
        return cls(ruta)

    # ------------------------------------------------------------ contratos
    def ruta(self, fichero: str) -> Path:
        return self.carpeta / fichero

    def escribir(self, fichero: str, datos: BaseModel) -> None:
        # Escritura atómica: un corte a mitad no deja un JSON a medias que
        # luego parezca una etapa terminada.
        tmp = self.ruta(fichero + ".tmp")
        tmp.write_text(datos.model_dump_json(indent=1), encoding="utf-8")
        tmp.replace(self.ruta(fichero))

    def leer(self, fichero: str, modelo: type[M]) -> M:
        return modelo.model_validate_json(self.ruta(fichero).read_text(encoding="utf-8"))

    def hash_de(self, ficheros: list[str]) -> str:
        h = hashlib.sha256()
        for f in ficheros:
            h.update(f.encode())
            h.update(self.ruta(f).read_bytes())
        return h.hexdigest()[:16]

    # ------------------------------------------------------------ estado
    def estado(self) -> dict:
        return json.loads(self._estado_path.read_text(encoding="utf-8"))

    def _guardar_estado(self, est: dict) -> None:
        tmp = self._estado_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(est, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self._estado_path)

    def marcar(self, etapa: str, **campos) -> None:
        est = self.estado()
        reg = est["etapas"].setdefault(etapa, {})
        reg.update(campos, cuando=datetime.now().isoformat(timespec="seconds"))
        self._guardar_estado(est)

    def olvidar(self, etapa: str) -> None:
        est = self.estado()
        est["etapas"].pop(etapa, None)
        self._guardar_estado(est)

    def hecha(self, etapa: str, salida: str, hash_entradas: str) -> bool:
        reg = self.estado()["etapas"].get(etapa, {})
        return (reg.get("resultado") == "ok" and reg.get("entradas") == hash_entradas
                and self.ruta(salida).exists())


class Cronometro:
    def __enter__(self):
        self.t0 = time.monotonic()
        return self

    def __exit__(self, *exc):
        self.segundos = round(time.monotonic() - self.t0, 1)
        return False

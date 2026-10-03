"""Contratos entre etapas: qué fichero deja cada una y qué tiene que llevar.

Cada etapa escribe UN fichero JSON en la carpeta del proyecto y la siguiente
solo lee ese fichero (nunca variables en memoria de otra etapa). El esquema se
valida al escribir y al leer: si una etapa deja un JSON mal formado, falla
ella, no tres etapas después (ver ARQUITECTURA.md, §3.1).

`extra="allow"` en los modelos que envuelven salidas de los LLM: el guion de
Groq trae campos que el montaje usa (fonética, capítulos) y que no merece la
pena enumerar aquí; lo que SÍ se exige es lo que rompe el vídeo si falta.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Contrato(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Tema(Contrato):
    tema: str = Field(min_length=5)
    categoria: str = "IA"
    modo: Literal["long", "short"] = "long"
    # id del proyecto de OpenMontage donde om_sin_claude deja audio y render
    pid: str


class Dossier(Contrato):
    # Texto con los datos verificados que manda al guionista. Vacío no vale:
    # sin dossier el guion se inventa las cifras (2026-09-04, 2026-09-29).
    texto: str = Field(min_length=200)


class Seccion(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    parrafos: list[str] = Field(min_length=1)

    @field_validator("parrafos")
    @classmethod
    def _sin_vacios(cls, v: list[str]) -> list[str]:
        if any(not p.strip() for p in v):
            raise ValueError("hay un párrafo vacío")
        return v


class Guion(BaseModel):
    model_config = ConfigDict(extra="allow")
    secciones: list[Seccion] = Field(min_length=3)

    def palabras(self) -> int:
        return sum(len(p.split()) for s in self.secciones for p in s.parrafos)

    def texto(self) -> str:
        return "\n".join(p for s in self.secciones for p in s.parrafos)


class Kit(Contrato):
    """Recursos propios de la receta (clips de Veo, imágenes de ComfyUI)."""
    carpeta: str
    # la receta pide imágenes propias: con menos de 4, ComfyUI falló
    imagenes_ia: list[str] = Field(min_length=4)
    bloque_brief: str = ""


class Clips(Contrato):
    clips: list[str] = Field(min_length=1)
    prompts: list[str]


class Planos(Contrato):
    # párrafo ("s1_00") -> lista de planos [ancla, tipo, props, fondo]
    planos: dict[str, list]
    # búsquedas de stock [tipo, clave, consulta]
    stock: list[list]


class Voz(Contrato):
    proveedor: Literal["voicestudio", "sharvard"]
    # tiempos de alinear(): palabras con inicio/fin, lo que usa props()
    tiempos: dict


class Fondos(Contrato):
    # clave -> {"type": "image"|"video", "src": ..., "clipDur"?: ...}
    fondos: dict[str, dict]


class Render(Contrato):
    mp4: str
    segundos: float = Field(gt=60)
    estilo: str = ""


class Calidad(Contrato):
    final: str
    segundos: float
    fallos: list[str]


class Miniatura(Contrato):
    ruta: str
    gancho: str
    # ganchos descartados por el verificador, con el motivo (para ver qué pasó)
    rechazados: list[str] = []
    # foto nueva de Francis (referencia, prompt, parecido) y prompt del fondo
    foto: dict = {}
    prompt_fondo: str = ""


class Publicado(Contrato):
    youtube_url: str
    titulo: str


class Revision(Contrato):
    medidas: dict

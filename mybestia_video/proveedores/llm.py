"""LLM gratuitos con plan B: si uno cae (429, cuota, modelo retirado), el siguiente.

Regla que no se negocia: quien VERIFICA no puede ser quien ESCRIBIÓ. Si Groq
cae y el guion lo escribe Gemini, la verificación la hace Groq (un modelo que
revisa su propio texto repite sus mismos errores; ARQUITECTURA.md §5).

Cada proveedor es una función prompt -> texto. Añadir uno = una entrada en
PROVEEDORES; el orden de las cadenas se cambia sin tocar las etapas.
"""
from __future__ import annotations

import re
import json
from typing import Callable

from .. import legado  # noqa: F401  (rutas de pipeline/ y pipeline_hf/)


class SinProveedor(RuntimeError):
    """Todos los proveedores de la cadena fallaron: la etapa se reintenta luego."""


def _groq(prompt: str, temp: float, max_tokens: int) -> str:
    from letra_pequena import groq
    return groq(prompt, temp=temp, max_tokens=max_tokens)


def _gemini(prompt: str, temp: float, max_tokens: int) -> str:
    from generate_script import _call_gemini
    return _call_gemini(prompt, temperature=temp)


PROVEEDORES: dict[str, Callable[[str, float, int], str]] = {"groq": _groq, "gemini": _gemini}
ESCRIBIR = ["groq", "gemini"]
VERIFICAR = ["gemini", "groq"]


def extraer_json(raw: str) -> dict | None:
    """El primer objeto JSON del texto (los LLM a veces lo envuelven en ```)."""
    m = re.search(r"\{.*\}", raw or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return d if isinstance(d, dict) else None


def json_de(prompt: str, cadena: list[str], *, excluir: set[str] = frozenset(),
            temp: float = 0.5, max_tokens: int = 6000, intentos: int = 2) -> tuple[dict, str]:
    """Pide JSON a la cadena en orden. Devuelve (datos, proveedor que respondió)."""
    errores = []
    for nombre in (n for n in cadena if n not in excluir):
        for i in range(intentos):
            try:
                d = extraer_json(PROVEEDORES[nombre](prompt, temp, max_tokens))
            except Exception as e:  # red, cuota, clave: se apunta y se pasa al siguiente
                errores.append(f"{nombre}: {type(e).__name__}: {str(e)[:120]}")
                break
            if d:
                return d, nombre
            errores.append(f"{nombre}: sin JSON (intento {i + 1})")
    raise SinProveedor("ningún LLM respondió: " + " | ".join(errores))


class Sesion:
    """Fija un proveedor como escritor y deja al verificador fuera de él.

    Se usa como gancho de las funciones de antes (om_sin_claude._groq y
    verificar_hechos._gemini) mientras no se muevan al paquete nuevo."""

    def __init__(self, cadena: list[str], excluir: set[str] = frozenset(), temp: float = 0.5):
        self.cadena, self.excluir, self.temp = cadena, set(excluir), temp
        self.usados: list[str] = []

    def __call__(self, prompt: str, max_tokens: int = 6000) -> dict:
        d, nombre = json_de(prompt, self.cadena, excluir=self.excluir, temp=self.temp, max_tokens=max_tokens)
        self.usados.append(nombre)
        return d

    @property
    def proveedor(self) -> str:
        """El que más ha respondido (normalmente uno solo)."""
        return max(set(self.usados), key=self.usados.count) if self.usados else ""

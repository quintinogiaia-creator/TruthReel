"""Puente con el código de antes (pipeline_hf, pipeline, OpenMontage).

Fase 1 de la migración (patrón strangler, ARQUITECTURA.md §4): las etapas
llaman a las funciones que ya funcionan en producción en vez de reescribirlas.
Todo el acoplamiento con rutas, sys.path y os.chdir vive AQUÍ, para que el día
que una función se mueva al paquete nuevo solo cambie este fichero.
"""
from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PIPELINE_HF = REPO / "pipeline_hf"
PIPELINE = REPO / "pipeline"
OM = Path(os.environ.get("OPENMONTAGE_DIR", Path.home() / "OpenMontage"))

for _p in (PIPELINE_HF, PIPELINE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


@contextlib.contextmanager
def en_openmontage():
    """om_sin_claude usa el registro de herramientas de OpenMontage, que se
    importa como `tools.*` y resuelve rutas relativas a su carpeta."""
    antes = os.getcwd()
    if str(OM) not in sys.path:
        sys.path.insert(0, str(OM))
    os.chdir(OM)
    try:
        yield
    finally:
        os.chdir(antes)


def carpeta_om(pid: str) -> Path:
    return OM / "projects" / pid


@contextlib.contextmanager
def con_llm(modulo, sesion):
    """Pone la cadena de LLM con plan B como gancho de un módulo de antes
    (om_sin_claude o verificar_hechos) solo durante el bloque."""
    antes = getattr(modulo, "LLM_JSON", None)
    modulo.LLM_JSON = sesion
    try:
        yield sesion
    finally:
        modulo.LLM_JSON = antes

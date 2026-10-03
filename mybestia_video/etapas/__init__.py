"""Las etapas del vídeo largo, en orden.

Cada etapa es un módulo con:
  NOMBRE     nombre corto (el que se usa en `rehacer --desde`)
  ENTRADAS   ficheros del proyecto que lee (su hash decide si hay que repetirla)
  SALIDA     fichero que escribe (su contrato está en contratos.py)
  run(p)     hace el trabajo y escribe SALIDA; lanza Bloqueado si es una puerta
  limpiar(p) opcional: borra lo que dejó fuera de SALIDA (audios, descargas)
             para que un `rehacer` no reutilice restos de la versión anterior
"""
from . import (calidad, clips, dossier, fondos, guion, hechos, kit, miniatura, montaje,
               planos, publicar, revision, short, voz)

# `publicar` va aparte: solo se ejecuta si se pide (Francis revisa antes).
ORDEN = [dossier, guion, hechos, kit, planos, voz, clips, fondos, montaje, calidad, miniatura, revision, short]
TODAS = ORDEN + [publicar]
POR_NOMBRE = {e.NOMBRE: e for e in TODAS}

"""Avisos al dueño del canal (Telegram). Uno por proyecto y motivo, no spam.

Configuración: MYBESTIA_TELEGRAM_TOKEN y MYBESTIA_TELEGRAM_CHAT. Sin ellas,
el aviso solo sale por pantalla (quien use el motor sin Telegram no pierde nada).
Mientras dure la migración, si no están en el entorno se leen de
pipeline/config.py (fase 3: solo .env).
"""
from __future__ import annotations

import json
import os
import urllib.request


def _credenciales() -> tuple[str, str]:
    token, chat = os.environ.get("MYBESTIA_TELEGRAM_TOKEN", ""), os.environ.get("MYBESTIA_TELEGRAM_CHAT", "")
    if not (token and chat):
        try:
            from . import legado  # noqa: F401
            import config
            token, chat = token or config.TELEGRAM_TOKEN, chat or str(config.TELEGRAM_CHAT_ID)
        except Exception:
            pass
    return token, chat


def avisar(texto: str) -> bool:
    print(f"[aviso] {texto}", flush=True)
    token, chat = _credenciales()
    if not (token and chat):
        return False
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
                                 data=json.dumps({"chat_id": chat, "text": texto}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=15)
        return True
    except Exception as e:
        print(f"[aviso] Telegram falló: {e}")
        return False


def avisar_una_vez(p, clave: str, texto: str) -> None:
    """No repite el mismo aviso del mismo proyecto (el timer pasa cada hora)."""
    est = p.estado()
    hechos = est.setdefault("avisos", [])
    if clave in hechos:
        return
    if avisar(texto):
        hechos.append(clave)
        p._guardar_estado(est)

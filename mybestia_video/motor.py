"""Ejecuta las etapas en orden, saltando las hechas y parando en la que falla.

Reglas:
- Una etapa se salta si terminó bien, su salida existe y sus entradas tienen
  el mismo hash que la última vez.
- Si una etapa falla (red, cuota, proceso caído), se para ESE proyecto y se
  apunta el motivo; `seguir` la reintenta y reutiliza lo que ya dejó a medias
  (p. ej. los párrafos de voz ya narrados).
- Si una puerta bloquea, `seguir` no la reintenta: hace falta `rehacer`.
- Si las entradas de una etapa cambiaron, antes de repetirla se borran sus
  restos (limpiar) para no mezclar la versión vieja con la nueva.
"""
from __future__ import annotations

import json
import traceback
from datetime import datetime

from . import etapas
from .avisos import avisar_una_vez
from . import proyecto
from .proyecto import Bloqueado, Cronometro, Proyecto


def _registro(p: Proyecto, **campos) -> None:
    campos = {"hora": datetime.now().isoformat(timespec="seconds"), **campos}
    with open(p.ruta("registro.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(campos, ensure_ascii=False) + "\n")
    print(f"[mybestia-video] {campos.get('etapa', '')}: {campos.get('evento')} "
          f"{campos.get('detalle', '')}".rstrip(), flush=True)


def avanzar(p: Proyecto, hasta: str | None = None, subir: bool = False) -> str:
    """Devuelve el estado final: 'listo', 'publicado', 'bloqueado:<etapa>' o 'fallo:<etapa>'."""
    lista = etapas.TODAS if subir else etapas.ORDEN
    for et in lista:
        faltan = [f for f in et.ENTRADAS if not p.ruta(f).exists()]
        if faltan:
            raise RuntimeError(f"{et.NOMBRE}: faltan {faltan} (¿se saltó una etapa?)")
        h = p.hash_de(et.ENTRADAS)
        if p.hecha(et.NOMBRE, et.SALIDA, h):
            _registro(p, etapa=et.NOMBRE, evento="ya hecha")
        else:
            previo = p.estado()["etapas"].get(et.NOMBRE, {})
            if previo.get("resultado") == "bloqueado" and previo.get("entradas") == h:
                _registro(p, etapa=et.NOMBRE, evento="sigue bloqueada", detalle=previo.get("motivo", ""))
                return f"bloqueado:{et.NOMBRE}"
            if previo.get("entradas") not in (None, h) and hasattr(et, "limpiar"):
                et.limpiar(p)
            p.marcar(et.NOMBRE, resultado="en curso", entradas=h)
            _registro(p, etapa=et.NOMBRE, evento="empieza")
            try:
                with Cronometro() as c:
                    proveedor = et.run(p)
            except Bloqueado as e:
                p.marcar(et.NOMBRE, resultado="bloqueado", motivo=str(e))
                _registro(p, etapa=et.NOMBRE, evento="BLOQUEADA", detalle=str(e))
                avisar_una_vez(p, f"bloqueado:{et.NOMBRE}:{h}",
                               f"⛔ Vídeo bloqueado en «{et.NOMBRE}»: {p.carpeta.name}\n{str(e)[:600]}")
                return f"bloqueado:{et.NOMBRE}"
            except KeyboardInterrupt:
                # Ctrl+C o kill -INT: que `estado` no diga "en curso" para siempre
                p.marcar(et.NOMBRE, resultado="fallo", motivo="interrumpida a mano")
                _registro(p, etapa=et.NOMBRE, evento="INTERRUMPIDA")
                raise
            except Exception as e:
                p.marcar(et.NOMBRE, resultado="fallo", motivo=f"{type(e).__name__}: {e}")
                _registro(p, etapa=et.NOMBRE, evento="FALLO", detalle=f"{type(e).__name__}: {e}",
                          traza=traceback.format_exc()[-3000:])
                return f"fallo:{et.NOMBRE}"
            p.marcar(et.NOMBRE, resultado="ok", proveedor=proveedor, segundos=c.segundos)
            _registro(p, etapa=et.NOMBRE, evento="ok", detalle=f"{proveedor} · {c.segundos}s")
        if et.NOMBRE == hasta:
            return f"parado:{et.NOMBRE}"
    return "publicado" if subir else "listo"


def rehacer(p: Proyecto, desde: str) -> None:
    """Borra la etapa `desde` y todas las posteriores (salida, restos y estado)."""
    nombres = [e.NOMBRE for e in etapas.TODAS]
    if desde not in nombres:
        raise ValueError(f"etapa desconocida '{desde}'. Hay: {', '.join(nombres)}")
    for et in etapas.TODAS[nombres.index(desde):]:
        if hasattr(et, "limpiar"):
            et.limpiar(p)
        p.ruta(et.SALIDA).unlink(missing_ok=True)
        p.olvidar(et.NOMBRE)
    _registro(p, etapa=desde, evento="rehacer desde aquí")


# Fallos pasajeros: cuántas veces se reintenta una etapa antes de avisar.
REINTENTOS_ANTES_DE_AVISAR = 3


def pendientes() -> list[Proyecto]:
    """Proyectos parados por un fallo pasajero (ni listos ni bloqueados)."""
    res = []
    for d in sorted(proyecto.RAIZ.glob("*")):
        if not (d / "estado.json").exists():
            continue
        p = Proyecto(d)
        etapas_est = p.estado()["etapas"]
        if any(r.get("resultado") == "bloqueado" for r in etapas_est.values()):
            continue
        if etapas_est.get("revision", {}).get("resultado") == "ok":
            continue
        res.append(p)
    return res


def seguir_pendientes() -> dict[str, str]:
    """Lo que ejecuta el timer: reanuda cada proyecto en pausa una vez. Si una
    etapa ya falló varias veces seguidas, avisa (una vez) con el motivo."""
    resultados = {}
    for p in pendientes():
        res = avanzar(p)
        resultados[p.carpeta.name] = res
        if res.startswith("fallo:"):
            etapa = res.split(":", 1)[1]
            est = p.estado()
            reg = est["etapas"][etapa]
            reg["fallos_seguidos"] = reg.get("fallos_seguidos", 0) + 1
            p._guardar_estado(est)
            if reg["fallos_seguidos"] >= REINTENTOS_ANTES_DE_AVISAR:
                avisar_una_vez(p, f"fallo:{etapa}:{reg.get('entradas')}",
                               f"⚠️ «{etapa}» lleva {reg['fallos_seguidos']} intentos fallando en {p.carpeta.name}:\n"
                               f"{reg.get('motivo', '')[:600]}")
        elif res == "listo":
            avisar_una_vez(p, "listo", f"✅ Vídeo listo y revisado: {p.carpeta.name}\n{p.ruta('final.mp4')}")
    return resultados

"""mybestia-video: crear, seguir, rehacer y mirar proyectos de vídeo.

  python3 -m mybestia_video nuevo --tema "Claude Code ya modea..." [--hasta voz]
  python3 -m mybestia_video seguir <proyecto> [--hasta etapa] [--subir]
  python3 -m mybestia_video rehacer <proyecto> --desde voz
  python3 -m mybestia_video estado [<proyecto>]
  python3 -m mybestia_video seguir-pendientes     (lo lanza el timer cada hora)

<proyecto> puede ser la ruta, el nombre de la carpeta o su principio.
Sin --subir nunca se publica: el proceso acaba en 'listo' con final.mp4 y
thumbnail.jpg en la carpeta, para revisarlos.
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from datetime import datetime

from . import etapas
from .contratos import Tema
from .motor import avanzar, rehacer, seguir_pendientes
from .proyecto import RAIZ, Proyecto


def _slug(s: str, n: int = 50) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:n].strip("-")


def _resumen(p: Proyecto) -> str:
    est = p.estado()["etapas"]
    lineas = [p.carpeta.name]
    for et in etapas.TODAS:
        r = est.get(et.NOMBRE)
        if not r:
            lineas.append(f"  · {et.NOMBRE:<8} pendiente")
            continue
        marca = {"ok": "✓", "bloqueado": "⛔", "fallo": "✗", "en curso": "…"}.get(r["resultado"], "?")
        extra = r.get("proveedor") if r["resultado"] == "ok" else r.get("motivo", "")
        seg = f" {r['segundos']}s" if r.get("segundos") is not None and r["resultado"] == "ok" else ""
        lineas.append(f"  {marca} {et.NOMBRE:<8} {extra or ''}{seg}")
    return "\n".join(lineas)


def main(argv: list[str] | None = None) -> int:
    # Línea a línea también con la salida a un log: si no, los mensajes del
    # código viejo (Flow, voz) no se ven hasta que el proceso acaba.
    sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser(prog="mybestia-video", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="orden", required=True)
    nombres = [e.NOMBRE for e in etapas.TODAS]

    n = sub.add_parser("nuevo", help="crea un proyecto y lo avanza")
    n.add_argument("--tema", required=True)
    n.add_argument("--categoria", default="IA")
    n.add_argument("--hasta", choices=nombres)

    s = sub.add_parser("seguir", help="continúa desde la primera etapa sin hacer")
    s.add_argument("proyecto")
    s.add_argument("--hasta", choices=nombres)
    s.add_argument("--subir", action="store_true", help="publica al final (solo tras revisarlo)")

    r = sub.add_parser("rehacer", help="borra una etapa y las siguientes, y sigue")
    r.add_argument("proyecto")
    r.add_argument("--desde", required=True, choices=nombres)
    r.add_argument("--hasta", choices=nombres)

    sub.add_parser("seguir-pendientes", help="(timer) reanuda los proyectos en pausa por fallos pasajeros")

    e = sub.add_parser("estado", help="qué etapa está hecha en cada proyecto")
    e.add_argument("proyecto", nargs="?")

    a = ap.parse_args(argv)

    if a.orden == "estado":
        ps = [Proyecto.abrir(a.proyecto)] if a.proyecto else \
            [Proyecto(d) for d in sorted(RAIZ.glob("*")) if (d / "estado.json").exists()]
        print("\n\n".join(_resumen(p) for p in ps) or f"sin proyectos en {RAIZ}")
        return 0

    if a.orden == "seguir-pendientes":
        for nombre, res in seguir_pendientes().items():
            print(f"{nombre}: {res}")
        return 0

    if a.orden == "nuevo":
        slug = _slug(a.tema)
        p = Proyecto.crear(slug)
        p.escribir("tema.json", Tema(tema=a.tema, categoria=a.categoria, modo="long",
                                     pid=f"{slug[:40].strip('-')}-{datetime.now():%m%d%H%M}"))
        print(f"[mybestia-video] proyecto {p.carpeta}")
        res = avanzar(p, hasta=a.hasta)
    elif a.orden == "seguir":
        p = Proyecto.abrir(a.proyecto)
        res = avanzar(p, hasta=a.hasta, subir=a.subir)
    else:
        p = Proyecto.abrir(a.proyecto)
        rehacer(p, a.desde)
        res = avanzar(p, hasta=a.hasta)

    print(_resumen(p))
    print(f"[mybestia-video] resultado: {res}")
    return 0 if res in ("listo", "publicado") or res.startswith("parado:") else 1


if __name__ == "__main__":
    sys.exit(main())

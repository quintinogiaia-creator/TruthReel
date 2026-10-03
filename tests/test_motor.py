"""El motor salta lo hecho, reanuda tras un fallo y respeta las puertas.

Con etapas falsas: no tocan Groq, la voz ni Remotion, así que corre en
segundos y se puede pasar antes de cada cambio.
"""
import types

import pytest
from pydantic import BaseModel

from mybestia_video import motor
from mybestia_video.proyecto import Bloqueado, Proyecto


class Dato(BaseModel):
    v: str


def etapa(nombre, entradas, salida, comportamiento, llamadas):
    def run(p):
        llamadas.append(nombre)
        accion = comportamiento.get(nombre)
        if accion == "falla":
            raise RuntimeError("se cayó la red")
        if accion == "bloquea":
            raise Bloqueado("dato falso")
        previo = "".join(p.leer(e, Dato).v for e in entradas)
        p.escribir(salida, Dato(v=previo + nombre[0]))
        return "falso"

    def limpiar(p):
        llamadas.append(f"limpiar-{nombre}")

    return types.SimpleNamespace(NOMBRE=nombre, ENTRADAS=entradas, SALIDA=salida, run=run, limpiar=limpiar)


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    monkeypatch.setattr("mybestia_video.proyecto.RAIZ", tmp_path)
    comp, llamadas = {}, []
    ets = [etapa("guion", ["tema.json"], "guion.json", comp, llamadas),
           etapa("voz", ["guion.json"], "voz.json", comp, llamadas),
           etapa("montaje", ["voz.json"], "render.json", comp, llamadas)]
    monkeypatch.setattr(motor.etapas, "ORDEN", ets)
    monkeypatch.setattr(motor.etapas, "TODAS", ets)
    p = Proyecto.crear("prueba")
    p.escribir("tema.json", Dato(v="T"))
    return p, comp, llamadas


def test_completo_y_seguir_no_repite(entorno):
    p, _, llamadas = entorno
    assert motor.avanzar(p) == "listo"
    assert p.leer("render.json", Dato).v == "Tgvm"
    llamadas.clear()
    assert motor.avanzar(p) == "listo"
    assert llamadas == []


def test_fallo_y_reanudacion(entorno):
    p, comp, llamadas = entorno
    comp["voz"] = "falla"
    assert motor.avanzar(p) == "fallo:voz"
    assert p.estado()["etapas"]["voz"]["resultado"] == "fallo"
    comp.clear()
    llamadas.clear()
    assert motor.avanzar(p) == "listo"
    # el guion no se repite, y la voz reintenta SIN limpiar (aprovecha lo hecho)
    assert llamadas == ["voz", "montaje"]


def test_puerta_bloqueada_no_se_reintenta_sola(entorno):
    p, comp, llamadas = entorno
    comp["voz"] = "bloquea"
    assert motor.avanzar(p) == "bloqueado:voz"
    comp.clear()
    assert motor.avanzar(p) == "bloqueado:voz"
    motor.rehacer(p, "voz")
    assert motor.avanzar(p) == "listo"


def test_rehacer_limpia_desde_la_etapa(entorno):
    p, _, llamadas = entorno
    motor.avanzar(p)
    llamadas.clear()
    motor.rehacer(p, "voz")
    assert llamadas == ["limpiar-voz", "limpiar-montaje"]
    assert p.ruta("guion.json").exists() and not p.ruta("voz.json").exists()
    llamadas.clear()
    motor.avanzar(p)
    assert llamadas == ["voz", "montaje"]


def test_entrada_cambiada_repite_y_limpia(entorno):
    p, _, llamadas = entorno
    motor.avanzar(p)
    p.escribir("guion.json", Dato(v="OTRO"))
    llamadas.clear()
    motor.avanzar(p)
    assert llamadas == ["limpiar-voz", "voz", "limpiar-montaje", "montaje"]
    assert p.leer("render.json", Dato).v == "OTROvm"


def test_hasta_para_en_la_etapa(entorno):
    p, _, _ = entorno
    assert motor.avanzar(p, hasta="guion") == "parado:guion"
    assert not p.ruta("voz.json").exists()


def test_seguir_pendientes_reanuda_y_avisa_tras_varios_fallos(entorno, monkeypatch):
    p, comp, _ = entorno
    avisos = []
    monkeypatch.setattr(motor, "avisar_una_vez", lambda p, clave, texto: avisos.append(clave))
    comp["voz"] = "falla"
    for _ in range(motor.REINTENTOS_ANTES_DE_AVISAR):
        assert motor.seguir_pendientes() == {p.carpeta.name: "fallo:voz"}
    assert len(avisos) == 1 and avisos[0].startswith("fallo:voz")
    comp.clear()
    # en el test no hay etapa revision: "listo" lo da avanzar
    assert motor.seguir_pendientes()[p.carpeta.name] == "listo"


def test_bloqueado_avisa_y_no_entra_en_pendientes(entorno, monkeypatch):
    p, comp, _ = entorno
    avisos = []
    monkeypatch.setattr(motor, "avisar_una_vez", lambda p, clave, texto: avisos.append(clave))
    comp["voz"] = "bloquea"
    motor.avanzar(p)
    assert avisos and avisos[0].startswith("bloqueado:voz")
    assert motor.pendientes() == []

"""Plan B de los LLM y la regla de que verifica un modelo distinto del que escribe."""
import pytest

from mybestia_video.proveedores import llm


@pytest.fixture
def falsos(monkeypatch):
    llamadas = []

    def hace(nombre, respuesta):
        def f(prompt, temp, max_tokens):
            llamadas.append(nombre)
            if isinstance(respuesta, Exception):
                raise respuesta
            return respuesta
        return f

    def poner(**resp):
        monkeypatch.setattr(llm, "PROVEEDORES", {n: hace(n, r) for n, r in resp.items()})
    return poner, llamadas


def test_si_groq_cae_escribe_gemini(falsos):
    poner, llamadas = falsos
    poner(groq=RuntimeError("429"), gemini='```json {"ok": 1} ```')
    s = llm.Sesion(llm.ESCRIBIR)
    assert s("x") == {"ok": 1} and s.proveedor == "gemini"
    assert llamadas == ["groq", "gemini"]


def test_el_verificador_nunca_es_el_escritor(falsos):
    poner, llamadas = falsos
    poner(groq='{"fallos": []}', gemini='{"fallos": []}')
    rev = llm.Sesion(llm.VERIFICAR, excluir={"gemini"})
    rev("x")
    assert llamadas == ["groq"]


def test_si_no_queda_verificador_falla_pasajero_no_bloquea(falsos):
    poner, _ = falsos
    poner(groq=RuntimeError("caído"), gemini='{"fallos": []}')
    with pytest.raises(llm.SinProveedor):
        llm.Sesion(llm.VERIFICAR, excluir={"gemini"})("x")


def test_respuesta_sin_json_reintenta_y_pasa_al_siguiente(falsos):
    poner, llamadas = falsos
    poner(groq="no sé", gemini='{"a": 2}')
    assert llm.json_de("x", ["groq", "gemini"]) == ({"a": 2}, "gemini")
    assert llamadas == ["groq", "groq", "gemini"]

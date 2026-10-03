import pytest

from mybestia_video.etapas import short


def palabras(texto, inicio_ms=0, ms=400):
    res, t = [], inicio_ms
    for w in texto.split():
        res.append({"word": w, "startMs": t, "endMs": t + ms - 50})
        t += ms
    return res


def test_frases_se_cortan_en_punto():
    fs = short.frases({"words": palabras("Hola mundo. Esto es otra. ¿Y esta?")})
    assert [f["texto"] for f in fs] == ["Hola mundo.", "Esto es otra.", "¿Y esta?"]
    assert fs[1]["ini"] == pytest.approx(0.8)


def test_tramos_validos_exige_duracion_orden_y_rango():
    # 10 frases de 10 s cada una
    fs = [{"texto": f"f{i}.", "ini": i * 10.0, "fin": i * 10.0 + 9.9} for i in range(10)]
    ok = short.tramos_validos([[0, 1], [5, 6]], fs)          # ~40.4 s
    assert len(ok) == 2 and ok[1][0] == 50.0
    with pytest.raises(ValueError):
        short.tramos_validos([[0, 0], [5, 5]], fs)           # 20 s: corto
    with pytest.raises(ValueError):
        short.tramos_validos([[5, 6], [0, 1]], fs)           # desordenado
    with pytest.raises(ValueError):
        short.tramos_validos([[8, 12]], fs)                  # fuera de rango y 1 tramo

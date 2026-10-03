"""Comprobaciones puras de la revisión + un vídeo sintético hecho con ffmpeg."""
import subprocess

import pytest

from mybestia_video.puertas import revision as rv


def test_destellos_cuenta_parpadeos_no_cortes():
    corte = [50] * 10 + [200] * 10          # cambia de plano y se queda
    parpadeo = [50, 50, 200, 50, 50, 200, 50, 50]
    assert rv.destellos(corte, 25) == 0
    assert rv.destellos(parpadeo, 25) == 2


def test_cobertura_detecta_frases_que_faltan():
    guion = rv.normalizar("Universal Modder necesita Blender instalado y una cuenta de Meshy")
    assert rv.cobertura(guion, guion) == 1.0
    assert rv.cobertura(guion, rv.normalizar("Universal Modder necesita")) < 0.5


def test_palabras_clave_ignora_el_formato_de_la_serie():
    clave = rv.palabras_clave("Claude Code ya modea cualquier juego de PC: la Letra Pequena de Universal Modder")
    assert "universal" in clave and "modder" in clave
    assert "letra" not in clave and "claude" not in clave


def _sintetico(tmp_path, negro_s=0.0):
    """10 s 1920x1080: color con ruido (no congelado) + tono a buen volumen."""
    out = tmp_path / "v.mp4"
    vf = "noise=alls=40:allf=t"
    if negro_s:
        vf += f",drawbox=c=black:t=fill:enable='between(t,2,{2 + negro_s})'"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=1920x1080:d=10:r=25",
                    "-f", "lavfi", "-i", "sine=f=220:d=10", "-vf", vf, "-af", "volume=-6dB",
                    "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(out)], check=True)
    return out


@pytest.mark.lento
def test_video_sintetico_detecta_plano_negro(tmp_path):
    u = rv.Umbrales(duracion_long=(5, 20), lufs=(-30, 0))
    limpio = rv.revisar(_sintetico(tmp_path), guion="hola", tema="prueba", transcripcion="hola", u=u)
    assert not any("negro" in f for f in limpio.fallos), limpio.fallos
    con_negro = rv.revisar(_sintetico(tmp_path, negro_s=3), guion="hola", tema="prueba",
                           transcripcion="hola", u=u)
    assert any("negro" in f for f in con_negro.fallos), con_negro.fallos


def test_huellas_un_clip_no_sale_en_dos_videos(tmp_path, monkeypatch):
    from mybestia_video import huellas
    monkeypatch.setattr(huellas, "REGISTRO", tmp_path / "reg.json")
    clip = tmp_path / "a.mp4"
    clip.write_bytes(b"clip")
    copia = tmp_path / "otro_nombre.mp4"
    copia.write_bytes(b"clip")
    assert not huellas.ya_usado(clip)
    huellas.registrar([clip], "video1")
    assert huellas.ya_usado(copia)                       # mismo contenido, otro nombre
    assert not huellas.ya_usado(copia, salvo_video="video1")  # el propio vídeo no cuenta


def test_cobertura_aproximada_tolera_erratas_de_whisper():
    clave = ["universal", "modder"]
    oido = rv.normalizar("con universal moder puedes")
    assert rv.cobertura(clave, oido, min_len=3) == 0.5
    assert rv.cobertura(clave, oido, min_len=3, aproximada=True) == 1.0


def test_cobertura_aproximada_palabras_pegadas():
    oido = rv.normalizar("UniversalModder genera todo")
    assert rv.cobertura(["universal", "modder"], oido, min_len=3, aproximada=True) == 1.0

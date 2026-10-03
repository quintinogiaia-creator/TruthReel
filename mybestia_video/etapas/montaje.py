"""Montaje: props de Remotion, mezcla a −14 LUFS y render 16:9."""
import subprocess
from pathlib import Path

from ..contratos import Fondos, Guion, Kit, Planos, Render, Tema, Voz
from .clips import CLIP_CARA
from ..proyecto import Proyecto, confirmar

NOMBRE = "montaje"
ENTRADAS = ["guion_verificado.json", "planos.json", "voz.json", "fondos.json"]
SALIDA = "render.json"


def poner_apertura(clip: Path, video: Path, destino: Path) -> Path:
    """Clip de su cara (con SU audio, sin narración encima) + el vídeo."""
    fc = ("[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"
          "fps=30,format=yuv420p,setsar=1[v0];[0:a]aresample=48000,loudnorm=I=-14:TP=-1.5[a0];"
          "[1:v]fps=30,format=yuv420p,setsar=1[v1];[1:a]aresample=48000[a1];"
          "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(clip), "-i", str(video), "-filter_complex", fc,
                    "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
                    "-c:a", "aac", "-b:a", "192k", str(destino)], check=True, timeout=1800)
    return destino


def run(p: Proyecto) -> str:
    tema = p.leer("tema.json", Tema)
    g = p.leer("guion_verificado.json", Guion).model_dump()
    B = p.leer("planos.json", Planos).planos
    tim = p.leer("voz.json", Voz).tiempos
    bgs = p.leer("fondos.json", Fondos).fondos
    from .. import legado
    import om_sin_claude
    P = legado.carpeta_om(tema.pid)
    with legado.en_openmontage():
        B = om_sin_claude.validar(g, B, set(bgs))
        pr = om_sin_claude.props(g, B, tim, bgs, P)
        om_sin_claude.mezclar(P, pr["durationSeconds"], pr["beats"])
        mp4 = om_sin_claude.render(P, tema.pid)
    seg, voz_s = om_sin_claude._dur(mp4), tim["words"][-1]["endMs"] / 1000
    confirmar(voz_s <= seg <= voz_s + 15, f"el render dura {seg:.0f}s y la voz {voz_s:.0f}s: se cortó algo")
    cara = Path(p.leer("kit.json", Kit).carpeta) / CLIP_CARA
    apertura = 0.0
    if cara.exists():
        apertura = om_sin_claude._dur(cara)
        mp4 = poner_apertura(cara, Path(mp4), p.ruta("render_con_apertura.mp4"))
        seg = om_sin_claude._dur(mp4)
    p.escribir(SALIDA, Render(mp4=str(mp4), segundos=seg, apertura_s=round(apertura, 3)))
    return "remotion"

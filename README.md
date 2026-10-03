# TruthReel

**The YouTube video engine that refuses to publish lies — or repeat itself.**
*(Español más abajo)*

TruthReel turns a topic and a verified research dossier into a finished,
reviewed video. Every stage writes a validated JSON contract, so a failure
stops only that stage and `seguir` resumes from exactly where it broke. No
re-writing the script, no re-recording the voice.

What makes it different from other auto-video generators:

- **Fact gate.** One LLM writes and a *different* LLM checks every sentence,
  on-screen label and thumbnail hook against the dossier. If something false
  survives, the video is blocked. Nothing gets published unverified.
- **Automatic review gate, no human needed.** ffmpeg + faster-whisper check the
  final file: black frames, frozen frames, flicker, silences, loudness
  (−14 LUFS), whether the voice actually says the script, and whether the title
  matches what is said.
- **Never the same twice.** A fingerprint registry (sha256 for clips,
  perceptual hash for images) blocks any AI clip, background or thumbnail that
  already appeared in another video.
- **Plan B everywhere.** If an LLM provider fails, the next one takes over.
  Transient failures pause the project and `seguir-pendientes` (run by a timer)
  retries it. You get one notification, not spam.

## Status — honest

Phase 1–2 of the migration described in [ARQUITECTURA.md](ARQUITECTURA.md)
(Spanish). The engine (`motor.py`), contracts, gates, fingerprints, provider
chain and CLI are here and tested (`pytest`). Several stages still call our
older production pipeline through `legado.py` (strangler pattern), and that
pipeline is **not** in this repo yet. So today you can read, test and reuse the
architecture and the gates, but not render a video end to end without it.
The build is documented step by step, with the real failures, in
[docs/DIARIO.md](docs/DIARIO.md).

```bash
pip install -r requirements.txt
python3 -m pytest -q tests          # engine, contracts, gates, fingerprints, LLM plan B
python3 -m mybestia_video --help    # nuevo / seguir / rehacer --desde / estado / seguir-pendientes
```

---

## En español

**El motor de vídeos de YouTube que no publica mentiras ni se repite.**

Etapas independientes con contrato JSON validado: dossier → guion → hechos
(puerta) → kit → planos → voz → clips → fondos → montaje → calidad → miniatura
(puerta) → revisión (puerta) → publicar. Si una etapa falla, se para solo esa,
y `python3 -m mybestia_video seguir <proyecto>` continúa sin rehacer lo
anterior.

Lo hacemos en público: el diario con cada decisión y cada fallo real está en
[docs/DIARIO.md](docs/DIARIO.md). Canal: [MYBESTIA en YouTube](https://www.youtube.com/@fjqg)
· web: [mybestia.com](https://mybestia.com)

Licencia: [AGPL-3.0](LICENSE), porque usamos piezas de
[OpenMontage](https://github.com/calesthio/OpenMontage), que también lo es.

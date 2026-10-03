# Diario de construcción del motor

Qué se hizo, por qué y qué salió mal, en orden. Es la memoria del proyecto
para quien llegue después y el guion del vídeo del proceso para el canal.
Cada entrada apunta al commit donde está el cambio.

---

## 2026-10-02 · El punto de partida

- **Situación:** 112 ficheros de Python (~18.000 líneas) sin git, sin tests y
  sin documentación. `pipeline_hf_full.py` tenía una función `main()` de 750
  líneas que hacía todo seguido: si fallaba algo a mitad, vuelta a empezar con
  un guion nuevo.
- **Qué lo disparó:** Francis pilló a mano tres datos falsos que Groq había
  metido en el guion de Universal Modder. Su frase: *"no montarlo como fichas
  de dominó, que si se cae algo se cae todo lo demás"*.
- **Decisión:** git primero (`2dd9b8d`) y un documento de arquitectura antes de
  tocar código (`8adb202`, ARQUITECTURA.md).
- **Primera pieza:** verificador de hechos con un modelo distinto del que
  escribe: Gemini revisa lo que escribe Groq (`eede473`). Probado: pilló él
  solo los tres fallos del largo.

## 2026-10-03 00:54 · Fase 1: etapas con contrato

- **Qué:** paquete `mybestia_video/` (`9ae2b89`). Cada etapa lee ficheros JSON
  de las anteriores y escribe el suyo, validado con Pydantic. `estado.json`
  guarda el hash de las entradas de cada etapa: lo que ya está hecho no se
  repite.
- **Cómo se probó:** se lanzó Universal Modder por la CLI nueva, se **mató el
  proceso a propósito** con 5 párrafos de voz narrados y se ejecutó
  `seguir`. Se saltó dossier, guion, hechos, kit y planos, y también los 5
  audios: siguió en el párrafo 6. Sin guion nuevo y sin gastar Groq otra vez.
- **Patrón:** *strangler*. Las etapas llaman a las funciones que ya funcionaban
  (`legado.py`) en vez de reescribirlo todo de golpe.

## 2026-10-03 01:17 · La revisión sale de la cabeza y entra en el código

- **Qué lo disparó:** Francis: *"tú eres la revisión... lo tienes que
  programar, nada tiene que depender de ti"*. El motor se va a regalar en
  GitHub: tiene que funcionar sin nadie mirando.
- **Qué:** puerta `revision` (`60a1ff8`): planos negros, imagen congelada,
  parpadeo, silencios, −14 LUFS, Whisper comparando la voz con el guion y el
  tema del título con lo que se dice. Todo local: ffmpeg y faster-whisper.
- **Prueba en positivo:** Universal Modder la pasa (7:03, la voz dice el 92 %
  del guion, −14,0 LUFS).
- **Prueba en negativo:** el mismo vídeo con el título "OpenClaw 2.0: cine 4D"
  queda bloqueado (*"no se oye: openclaw, cine"*). Es el error real del
  2026-09-27.
- **Lo que la puerta NO vio:** la miniatura decía "CLAUDE CODE LO ROMPIÓ" y el
  vídeo no dice eso. El gancho se escribía mirando solo el título.

## 2026-10-03 01:21 · Los dos clips de siempre

- **Qué lo disparó:** Francis: *"sigue teniendo el mismo vídeo de Flow"*.
- **Causa real (dos fallos encadenados):**
  1. Flow rechazó los dos clips por "alta demanda" y el código siguió sin
     avisar.
  2. La biblioteca de clips solo tenía 2 y, si estaban gastados, los volvía a
     usar (`frescos = [...] or biblio`).
  Resultado: en **todo** lo montado hasta ese día solo había 2 clips de Veo
  distintos.
- **Arreglo** (`ae2b35f`):
  - `huellas.py`: registro con el sha256 de cada clip usado. Un clip nunca sale
    en dos vídeos, aunque lo copien con otro nombre.
  - La etapa `clips` va aparte: si Flow no da ninguno nuevo, el vídeo espera.
  - La revisión bloquea cualquier clip que ya esté en el registro.
  - El gancho de la miniatura lo verifica Gemini contra el dossier.

## 2026-10-03 01:23 · Cada módulo confirma lo que entrega

- **Qué lo disparó:** Francis: *"tiene que estar bien modulado, que cuando un
  módulo termine y confirme, el otro"*.
- **Qué:** cada etapa comprueba su salida antes de darla por buena (`a2e140d`):
  - el kit trae al menos 4 imágenes IA;
  - la voz alineada cubre el 95 % de las palabras del guion;
  - están todos los fondos que piden los planos (antes, el que faltaba se
    sustituía en silencio por un fondo negro);
  - el render dura lo que la voz.

## 2026-10-03 01:35 · Plan B en las IAs de texto y un timer que no se rinde

- **Plan B** (`de20082`): `proveedores/llm.py`. Si Groq cae, escribe Gemini.
  Regla: **verifica siempre un modelo distinto del que escribió** (si escribió
  Gemini, verifica Groq). Si no queda ningún verificador, el vídeo espera: es
  un fallo pasajero, no un guion falso, y nunca se publica sin verificar.
- **Que avance solo** (`65639ce`): `seguir-pendientes` es lo que lanzará el
  timer. Reanuda cada vídeo en pausa (por ejemplo, Flow saturado) y avisa por
  Telegram **una sola vez** si queda bloqueado, si una etapa lleva 3 intentos
  fallando o cuando un vídeo está listo y revisado.
- **Nombre de trabajo:** TruthReel.

## 2026-10-03 02:00 · Flow sí funcionaba: el que fallaba era el código

- **Qué lo disparó:** Francis: *"Flow no tarda tanto"*.
- **Dos fallos encadenados en `broll_nube.flow`:**
  1. Flow contestaba *"por la alta demanda, la tarea está en la cola"* y el
     código lo trataba como un error y abandonaba. Flow generaba el clip
     igualmente: había 3 clips hechos sin descargar.
  2. La cuadrícula de Flow ya no tiene `<video>`, solo miniaturas
     `flow-content.google/image/<id>`. El vídeo está en `/video/<id>`, pero solo
     con la URL firmada que carga el reproductor al pasar el ratón.
- Los 3 clips se rescataron y Universal Modder se montó con ellos.

## 2026-10-03 02:10 · Miniaturas: la misma frase para todo vídeo de IA

- **Qué lo disparó:** *"esa miniatura ya la hemos utilizado"*.
- **Causa:** el prompt del fondo era una frase fija para cualquier tema de IA y
  además iba con caché: el mismo teclado morado en todos los vídeos. Su foto
  salía de solo 5 recortes.
- **Arreglo:** fondo con un prompt propio del tema y sin caché; huella
  perceptual (dHash) de toda miniatura, fondo y foto usados; puerta que bloquea
  lo parecido. La foto de Francis ahora es **nueva en cada vídeo**: InstantID en
  local (gratis), en dos pasadas (pose sin cara + cara con 3 de sus fotos) y con
  filtro de parecido facial.
- **Ganchos honestos:** «CREA JUEGOS CON IA» (falso: modifica, no crea) y
  «Modifica cualquier juego» (la promesa que el vídeo desmiente) ya no pasan.
  Sale «¿Modifica cualquier juego?».

## 2026-10-03 02:30 · Publicado

- Repo público: <https://github.com/quintinogiaia-creator/TruthReel>,
  historial limpio (el privado tenía una clave antigua en un commit), AGPL-3.0.
- El enlace sale en cada descripción de YouTube y en cada publicación en redes.

## 2026-10-03 03:40 · Subido el primer vídeo del motor nuevo, y Flow con su cara

- **Publicado:** largo <https://youtu.be/bngFRqZPG9k> y short
  <https://youtu.be/Vv2r3E8XZ1A>. La etapa `publicar` ya no usa la del pipeline
  viejo, que regeneraba la miniatura con el sistema antiguo.
- **Dos fallos encontrados al subir:** la cuota de Maton estaba agotada (ahora
  va por la subida directa con OAuth propio) y el filtro anti-duplicados tomaba
  el vídeo por "gemelo" de otro solo por compartir "Claude" y "letra pequeña".
- **El short pasó por la puerta y lo paró dos veces, con razón:** no nombraba
  la herramienta y el veredicto duraba 4 s. Ahora la selección exige el nombre
  (sacado del dossier) y un cierre explicado. Whisper escribía
  "UniversalModder" junto: la comparación aproximada ya lo tolera.
- **Clips con la cara de Francis:** su foto nueva (InstantID) entra como
  ingrediente en Flow. Primer clip en 59 s.
- **Web:** demo de WhatsApp, enlaces clicables, menú de agencia, portada sin
  la esfera 3D, responsive comprobado a 5 anchos en 12 páginas.

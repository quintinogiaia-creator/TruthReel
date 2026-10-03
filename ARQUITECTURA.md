# Motor de vídeo MYBESTIA: arquitectura

> Estado: **propuesta** (2026-10-02). Aquí está cómo funciona hoy, por qué se
> rompe y cómo queda. No se toca código de producción hasta que Francis dé el OK
> a este documento.

## 1. Para qué existe

El motor saca, sin nadie delante, los vídeos del canal (3 por semana: martes y
viernes un short, el sábado un largo) y los publica en YouTube, la web y las
redes. Cada vídeo tiene que estar **comprobado**: cifras y frases sacadas de
fuentes reales, voz y montaje revisados. Un vídeo que miente le cuesta al canal
la credibilidad, que es justo lo que se vende.

Reglas que no se negocian:

- **0 tokens de Claude en automático.** Ningún timer, cola ni vigía lanza
  `claude -p`. Los LLM gratuitos (Groq, Gemini) escriben y verifican.
- **Nada de pago** aparte del plan de Claude.
- **Si una puerta de calidad falla, no se publica.** Avisa y punto.

## 2. Cómo está hoy (y por qué se cae)

```
cron_hourly.py ──► pipeline_hf_full.py main()  (750 líneas seguidas)
                     │ tema → dossier → guion (Groq) → verificación (Gemini)
                     │ ├─ largo:  openmontage_run → om_sin_claude (voz, planos, Pexels,
                     │ │          ComfyUI, Veo/Flow, Remotion) → presentador → receta
                     │ └─ short:  scenes.py (1.800 líneas) + HyperFrames + TTS por escena
                     │ miniatura → SEO → YouTube → web → Metricool
                     ▼
                 una sola pasada: si algo falla, se empieza desde cero
```

Puntos de dominó medidos el 2026-10-02:

| Problema | Consecuencia real |
|---|---|
| Todo es una sola función de 750 líneas | Un fallo a mitad obliga a rehacer el vídeo entero, con un guion NUEVO (hoy hubo que escribir un script a mano para volver a montar el largo corregido) |
| Sin puntos de control | Reintentar = otra llamada a Groq, otra voz, otro render: horas y cuotas |
| Dos caminos de render (OpenMontage para el largo, `scenes.py` para el short) | Cada arreglo hay que hacerlo dos veces, y el short no pasa por la misma receta |
| 39 variables de entorno sueltas + `config.py` con claves dentro | Nadie sabe qué configura qué; las claves no se pueden versionar |
| 112 módulos, muchos muertos (9 motores de voz, `generate_comic_*`, `montar_botnet`…) | El que llega no sabe qué se usa |
| Sin tests | Cada cambio se prueba en producción |
| Dependencias sin plan B declarado (Flow necesita el navegador del bot, Groq da 429…) | Depende de la suerte de cada pieza |
| Sin git hasta el 2026-10-02 | No había forma de deshacer un cambio |

## 3. Cómo queda

### 3.1 Etapas independientes con contrato

```
 tema ─► dossier ─► guion ─► verificación ─► voz ─► visuales ─► montaje ─► calidad ─► publicar
  │        │          │          │ (puerta)    │        │           │        │ (puerta)    │
  ▼        ▼          ▼          ▼             ▼        ▼           ▼        ▼             ▼
 tema.json dossier.json guion.json hechos.json voz/   planos.json  final.mp4 informe.json  publicado.json
```

Cada etapa:

1. **Lee** solo los ficheros de las etapas anteriores y **escribe** el suyo en
   la carpeta del proyecto. El contrato es un esquema (Pydantic) validado al
   escribir y al leer: si el JSON no cumple, la etapa falla ahí y no contamina
   las siguientes.
2. Es **idempotente**: si su salida existe y sus entradas no han cambiado
   (hash), no se repite. Así se puede **reanudar**:
   `mybestia-video seguir <proyecto>` o `mybestia-video rehacer <proyecto> --desde voz`.
3. Registra en `estado.json` qué hizo, con qué proveedor, cuánto tardó y por qué
   falló.

Las **puertas** (verificación de hechos y control de calidad) bloquean: si no
pasan, el proyecto queda en `bloqueado` con el motivo y llega un aviso. Las demás
etapas, si fallan, solo paran SU proyecto: el resto del sistema sigue.

### 3.2 Proveedores con plan B

Cada servicio externo va detrás de una interfaz y una cadena de alternativas,
declarada en un solo sitio:

| Necesidad | Primero | Plan B | Si caen todos |
|---|---|---|---|
| Escribir guion | Groq gpt-oss-120b | Gemini 2.5 Flash | la etapa falla y se reintenta más tarde |
| Verificar hechos | Gemini (un modelo distinto del que escribe) | Groq con otro prompt | puerta cerrada: no hay vídeo |
| Voz | VoiceStudio | Piper Sharvard | etapa falla |
| Clips de vídeo IA | Flow/Veo (navegador del bot) | biblioteca `veo_biblioteca/` | solo imágenes, se apunta en el informe |
| Imágenes | ComfyUI local | Pexels | etapa falla |
| Render | Remotion (una sola plantilla parametrizada, 16:9 y 9:16) | — | etapa falla |

Reintentos con espera creciente para los errores pasajeros (429, red); los
errores permanentes (clave caducada, modelo retirado) se cortan al instante y se
avisan.

### 3.3 Estructura del código

```
mybestia_video/
  config.py          # pydantic-settings: lee .env; config.example documentado
  contratos.py       # esquemas de cada fichero entre etapas
  proyecto.py        # carpeta, estado.json, hashes, reanudación
  etapas/            # una por fichero, cada una con run(proyecto) -> salida
  proveedores/       # llm/, voz/, imagen/, video_ia/, render/, publicar/
  puertas/           # hechos.py (hoy: verificar_hechos.py), calidad.py (receta)
  cli.py             # nuevo / seguir / rehacer --desde / estado
tests/               # pytest por etapa, proveedores falsos, dossier de ejemplo
docs/adr/            # una decisión por fichero: qué, por qué y qué se descartó
```

### 3.4 Observabilidad

Log estructurado (JSON por línea) por proyecto y una línea de resumen por etapa.
`mybestia-video estado` enseña qué proyectos hay, en qué etapa están y por qué se
paró cada uno. El vigía solo lee eso: no arregla nada él solo y nunca lanza Claude.

## 4. Cómo se migra sin romper el canal

Patrón *strangler*: lo nuevo envuelve lo viejo y lo va sustituyendo por partes,
nunca con un apagón.

| Fase | Entrega | Hecho cuando |
|---|---|---|
| 0 | git | ✅ commit `2dd9b8d` |
| 1 | `contratos.py` + `proyecto.py` + CLI; las etapas llaman a las funciones actuales | El vídeo de Universal Modder sale por la CLI nueva, se puede cortar en cualquier etapa y `seguir` lo termina sin rehacer lo anterior |
| 2 | Proveedores con plan B; un solo render para largo y short | Con Groq o Flow apagados a propósito, el vídeo sale igualmente (y el informe dice qué plan B usó) |
| 3 | `.env` + `config.example`, claves fuera del código, tests de cada etapa, código muerto archivado | `pytest` en verde; `grep` no encuentra ninguna clave en el repo; el timer apunta a la CLI nueva |
| 4 | Documentación final + ADR | Alguien que no ha visto el código saca un vídeo leyendo solo `docs/` |

Cada fase se prueba con un vídeo real de principio a fin antes de pasar a la siguiente.

## 5. Decisiones (resumen; el detalle irá en `docs/adr/`)

- **Ficheros JSON entre etapas, no una base de datos ni una cola**: un vídeo es
  un proyecto pequeño en disco; los JSON se leen a ojo y se versionan. Una cola
  (Celery, Redis) añadiría un servicio más que se puede caer.
- **Pydantic para los contratos**: valida al escribir, documenta el formato y es
  el estándar en Python.
- **Verificador con un modelo distinto del que escribe**: si escribe y revisa el
  mismo modelo, repite sus mismos errores. Probado el 2026-10-02: Gemini pilló
  solo los 3 fallos que Groq metió en el largo.
- **Un solo render (Remotion)**: dos motores = dos sitios donde arreglar cada
  cosa. El short pasa a ser la misma plantilla en vertical.

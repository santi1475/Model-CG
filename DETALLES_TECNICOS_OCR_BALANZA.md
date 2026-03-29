# Documento tecnico actualizado: reconocimiento de balanza por vision computacional

Fecha de actualizacion: 2026-03-29

## 1. Objetivo tecnico actual

El sistema procesa imagenes de balanza digital y extrae valores estructurados para integracion contable y operacion por WhatsApp.

Salida objetivo del backend:
- `peso` (float)
- `precio` (float)
- `producto` (string)
- `total` (float)

## 2. Estructura real del proyecto

Raiz:
- `main.py` (API FastAPI + integracion vision con Groq)
- `requirements.txt` (dependencias Python)
- `docker-compose.yml` (orquestacion `api` + `bot`)
- `balanza.jpg` (muestra de prueba)
- `DETALLES_TECNICOS_OCR_BALANZA.md` (este documento)
- `.env` (variables de entorno, incluyendo credenciales)

Contenedor de desarrollo:
- `.devcontainer/devcontainer.json`
- `.devcontainer/Dockerfile`

Bot de WhatsApp:
- `bot/bot.js`
- `bot/package.json`
- `bot/Dockerfile`

Pruebas OCR experimentales:
- `pruebas/test_ocr.py` (pipeline OpenCV + pytesseract)
- `pruebas/test_1.py` (experimento EasyOCR)

## 3. Stack tecnico vigente

### 3.1 Backend API

- Python 3.11
- FastAPI
- Uvicorn
- Pydantic
- Pillow
- `groq` SDK

### 3.2 Vision/OCR en entorno Python

- OpenCV (`opencv-python-headless`)
- EasyOCR (usado en pruebas, no en `requirements.txt` de raiz)
- pytesseract (usado en pruebas, no en `requirements.txt` de raiz)

### 3.3 Bot y mensajeria

- Node.js 20 (imagen `node:20-slim`)
- `whatsapp-web.js`
- `axios`
- `qrcode-terminal`
- Chromium en contenedor para sesion headless de WhatsApp Web

### 3.4 Dependencias en `requirements.txt` (estado actual)

- `fastapi`
- `uvicorn[standard]`
- `python-multipart`
- `opencv-python-headless`
- `Pillow`
- `groq`
- `requests`

Nota tecnica:
- `pytesseract` no esta en `requirements.txt` actual, pero si se usa en `pruebas/test_ocr.py`.

## 4. Virtualizacion y contenedores

## 4.1 Dev Container (VS Code)

Archivo: `.devcontainer/devcontainer.json`

Detalles:
- Build local con:
  - `dockerfile`: `Dockerfile`
  - `context`: `..`
- Inyeccion de variables con `runArgs`:
  - `--env-file ${localWorkspaceFolder}/.env`
- Configuracion editor:
  - `python.defaultInterpreterPath`: `/usr/local/bin/python`
  - extensiones: `ms-python.python`, `ms-python.vscode-pylance`
- Usuario remoto: `root`

Implicacion:
- El contenedor de desarrollo recibe variables de `.env` al iniciar, permitiendo usar `GROQ_API_KEY` sin hardcode.

## 4.2 Imagen Python de desarrollo/API

Archivo: `.devcontainer/Dockerfile`

Base:
- `python:3.11-slim`

Paquetes del sistema instalados:
- `libgl1`
- `libglib2.0-0`

Provisionamiento Python:
- copia `requirements.txt`
- ejecuta `pip install --no-cache-dir -r requirements.txt`

Observacion relevante:
- Actualmente este Dockerfile no instala binario `tesseract-ocr`; por tanto, las pruebas con `pytesseract` requieren extender imagen o usar otro entorno que tenga tesseract instalado.

## 4.3 Orquestacion con Docker Compose

Archivo: `docker-compose.yml`

Servicios:

1. `api`
- build desde `.devcontainer/Dockerfile`
- puerto publicado: `8000:8000`
- variable de entorno: `GROQ_API_KEY=${GROQ_API_KEY}`
- volumen: `.:/workspaces/backend`
- `working_dir`: `/workspaces/backend`
- comando: `uvicorn main:app --host 0.0.0.0 --port 8000`

2. `bot`
- build desde `./bot`
- variable: `API_URL=http://api:8000`
- volumen sesion: `./bot/session:/app/session`
- depende de `api`
- politica reinicio: `unless-stopped`

Implicacion operacional:
- `bot` consume API por red interna Docker usando hostname de servicio (`api`).

## 4.4 Contenedor del bot

Archivo: `bot/Dockerfile`

Base:
- `node:20-slim`

Paquetes del sistema:
- `chromium`
- `fonts-freefont-ttf`

Variables de entorno:
- `PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true`
- `PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium`

Flujo build:
- `WORKDIR /app`
- `COPY package.json .`
- `npm install`
- `COPY bot.js .`
- `CMD ["node", "bot.js"]`

## 5. API FastAPI: funciones y comportamiento exacto

Archivo: `main.py`

## 5.1 Modelo de salida

Clase Pydantic `ResultadoVision`:
- `peso: float`
- `precio: float`
- `producto: str`
- `total: float`

## 5.2 Funcion `analizar_imagen_con_groq(imagen_bytes: bytes) -> dict`

Responsabilidad:
- Enviar imagen codificada en base64 a modelo multimodal de Groq.

Secuencia interna:
1. Inicializa cliente `Groq` con `GROQ_API_KEY` tomada de entorno.
2. Convierte bytes de imagen a base64.
3. Llama `client.chat.completions.create(...)` con:
   - modelo: `meta-llama/llama-4-scout-17b-16e-instruct`
   - mensaje multimodal (`image_url` + prompt de texto estricto)
   - `max_tokens=150`
4. Parsea respuesta JSON desde `response.choices[0].message.content`.
5. Aplica regla de negocio:
   - recalcula `total_calculado = round(peso * precio, 2)`
   - si discrepancia con `total` OCR > `0.10`, reemplaza `total` con `total_calculado`
6. Retorna diccionario final.

Detalles del prompt vigente:
- define contexto de balanza GUERSA
- reglas por display (peso, precio unitario, total)
- rangos validos y formato decimal esperado
- validacion final `total / precio ≈ peso`
- salida estricta solo JSON: `{"peso": n, "precio": n, "producto": "sin dato", "total": n}`

## 5.3 Endpoint `POST /api/procesar-imagen`

Firma:
- `async def procesar_imagen(file: UploadFile = File(...))`

Validaciones y flujo:
1. Verifica que `file.content_type` inicie con `image/`; si no, `HTTP 400`.
2. Lee bytes de archivo subido.
3. Verifica integridad con `PIL.Image.verify()`.
4. Reabre imagen para procesamiento posterior.
5. Si el lado mayor > 1200 px:
   - redimensiona con `thumbnail((1200, 1200))`
   - recomprime a JPEG (`quality=85`)
6. Loguea nombre de archivo y tamano en KB.
7. Invoca `analizar_imagen_con_groq(contents)`.
8. Devuelve resultado con `response_model=ResultadoVision`.

Manejo de error:
- Cualquier excepcion cae en `HTTP 422` con detalle textual.

## 5.4 Endpoint `GET /health`

Salida:
- `status`: `ok`
- `groq_key`: booleano que indica presencia de `GROQ_API_KEY` en entorno

Uso:
- check de liveness y validacion rapida de configuracion de credenciales.

## 6. Bot de WhatsApp: funciones y flujo

Archivo: `bot/bot.js`

## 6.1 Inicializacion

- Cliente `whatsapp-web.js` con `LocalAuth` en `/app/session`
- Puppeteer en modo headless
- argumentos `--no-sandbox` y `--disable-setuid-sandbox`

Eventos implementados:
- `qr`: imprime QR en terminal para vincular sesion
- `ready`: confirma conexion del bot
- `message`: procesa mensajes entrantes

## 6.2 Flujo de procesamiento de imagen

En `client.on('message', async msg => {...})`:
1. Descarta mensajes sin media.
2. Descarta media que no sea imagen (`mimetype` no `image/*`).
3. Descarga imagen (`downloadMedia`).
4. Responde al usuario: "Procesando imagen de balanza...".
5. Convierte base64 a `Buffer`.
6. Escribe temporalmente archivo en `/tmp` (aunque luego no se usa para el request).
7. Construye `FormData` y `Blob` con la imagen.
8. Hace `POST` a `${API_URL}/api/procesar-imagen`.
9. Toma `peso`, `precio`, `total` de respuesta y envia mensaje formateado.
10. Elimina archivo temporal con `fs.unlinkSync`.

Manejo de error:
- log en consola y respuesta de fallo al usuario de WhatsApp.

## 6.3 Configuracion de entorno del bot

Variable `API_URL`:
- default local: `http://localhost:8000`
- en Compose: `http://api:8000`

Persistencia de sesion:
- volumen `./bot/session:/app/session`

## 7. Modulo de pruebas OCR (experimental)

## 7.1 `pruebas/test_ocr.py` (OpenCV + pytesseract)

Funciones:
- `detectar_displays(imagen, cfg)`
  - calcula perfil vertical de verde brillante
  - detecta zonas continuas y filtra por altura
  - genera `bbox` para 3 displays esperados
- `preprocesar_roi(imagen, bbox, cfg)`
  - usa canal verde
  - umbral adaptativo por percentil 15
  - `THRESH_BINARY_INV`, `MORPH_OPEN`, escalado y borde blanco
- `leer_numero(imagen_procesada, cfg)`
  - OCR con `pytesseract`
  - regex para extraer primer numero decimal/entero
- `procesar_balanza(ruta_imagen, cfg=CONFIG)`
  - pipeline completo
  - genera imagenes debug (`debug_peso.jpg`, etc.)
  - valida negocio con tolerancia `0.15`

Configuracion (`CONFIG`) centralizada:
- rangos HSV
- parametros de morfologia
- parametros OCR (`--oem 3 --psm 7`, whitelist numerica)
- tolerancia de validacion

## 7.2 `pruebas/test_1.py` (EasyOCR)

Comportamiento:
- inicializa `easyocr.Reader(['en'], gpu=False)`
- define ROIs fijas para `peso`, `precio`, `total`
- escala x2 cada ROI
- corre `readtext(..., allowlist='0123456789.')`
- imprime texto y confianza por deteccion

Uso:
- experimento alternativo para comparar OCR tradicional vs motor EasyOCR.

## 8. Interaccion extremo a extremo (operacion)

Flujo productivo actual:
1. Usuario envia foto de balanza por WhatsApp.
2. Bot recibe media y la envia al backend FastAPI.
3. Backend valida imagen y la ajusta (si es grande).
4. Backend consulta modelo con vision (Groq).
5. Backend normaliza y valida consistencia `peso x precio`.
6. Backend retorna JSON estructurado.
7. Bot responde al usuario con resumen legible.

Flujo alterno de laboratorio:
1. Ejecutar scripts de `pruebas/` sobre `balanza.jpg`.
2. Ajustar parametros de segmentacion/OCR.
3. Comparar precision y robustez.

## 9. Variables de entorno y configuracion

Variables usadas:
- `GROQ_API_KEY` (API backend)
- `API_URL` (bot)

Ubicaciones:
- `.env` para credenciales/parametros locales
- `docker-compose.yml` para inyeccion a servicios
- `.devcontainer/devcontainer.json` para pasar `.env` al contenedor de desarrollo

## 10. Comandos tecnicos de operacion

API en local/devcontainer:
- `uvicorn main:app --reload --host 0.0.0.0 --port 8000`

Stack completo con Docker Compose:
- `docker compose up --build`

Healthcheck:
- `GET /health`

Pruebas OCR (experimental):
- `python pruebas/test_ocr.py`
- `python pruebas/test_1.py`

## 11. Estado funcional actual

Implementado y operativo:
- Endpoint de procesamiento con vision externa (Groq), ya sin mock.
- Regla de negocio para corregir `total` por discrepancia.
- Endpoint de salud con verificacion de clave.
- Bot de WhatsApp integrado con backend.
- Orquestacion de servicios `api` + `bot`.

Limitaciones actuales (tecnicas, no bloqueantes):
- Dependencia de servicio externo para OCR/vision (latencia y costo por llamada).
- Scripts de `pruebas/` no estan integrados al endpoint principal.
- `pytesseract`/`easyocr` no forman parte cerrada del entorno backend segun `requirements.txt` actual.
- En `main.py` hay parseo JSON duplicado (`json.loads`) que no rompe flujo pero es redundante.
- En `pruebas/test_ocr.py` se imprime `d["area"]` en una rama donde ese campo no esta definido en `bbox` retornado.

## 12. Recomendaciones inmediatas

1. Unificar estrategia OCR:
- decidir entre pipeline CV local y vision externa, o esquema hibrido con fallback.

2. Endurecer contrato de respuesta:
- agregar `confidence`, `raw_text` y `warnings` en respuesta API.

3. Alinear dependencias:
- sincronizar `requirements.txt` con scripts reales de `pruebas/` o mover pruebas a entorno separado.

4. Observabilidad:
- agregar logs estructurados con tiempo de inferencia y codigo de resultado.

5. Calidad:
- agregar pruebas automatizadas de integracion para `/api/procesar-imagen` y `/health`.

from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
import io, os, base64, json
from PIL import Image
from groq import Groq

app = FastAPI(title="Backend Contabilidad WhatsApp")

class ResultadoVision(BaseModel):
    peso: float
    precio: float
    producto: str
    total: float

def analizar_imagen_con_groq(imagen_bytes: bytes) -> dict:
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    imagen_b64 = base64.b64encode(imagen_bytes).decode()

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",  # actual con visión
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{imagen_b64}"}
                },
                {
                    "type": "text",
                    "text": """Eres un lector especializado en balanzas digitales de mercado peruano.

                            Esta es una balanza GUERSA. Los displays LCD tienen dígitos oscuros sobre fondo verde brillante.

                            REGLAS ESTRICTAS por display:

                            Display SUPERIOR — PESO (kg):
                            - Formato: X.XXX (un dígito entero, punto decimal, tres decimales)
                            - Rango válido: 0.200 hasta 40.000 kg
                            - Ejemplo correcto: 3.125 — NO 31.25 NI 31.05
                            - El punto decimal SIEMPRE está después del PRIMER dígito

                            Display MEDIO — PRECIO UNITARIO (soles/kg):
                            - Formato: XX.XX (dos dígitos enteros, punto, dos decimales)  
                            - Rango válido: 1.00 hasta 99.00
                            - Ejemplo correcto: 13.00

                            Display INFERIOR — PRECIO TOTAL (soles):
                            - Formato: XX.XX
                            - Rango válido: 1.00 hasta 999.00
                            - DEBE ser aproximadamente igual a peso × precio
                            - Ejemplo: 3.125 × 13.00 = 40.63

                            VALIDACIÓN FINAL antes de responder:
                            - ¿peso está entre 0.2 y 40? Si no, relee el display
                            - ¿total ÷ precio ≈ peso? Si no, corrige el peso

                            Responde SOLO con este JSON sin markdown ni texto adicional:
                            {"peso": número, "precio": número, "producto": "sin dato", "total": número}"""
                }
            ]
        }],
        max_tokens=150,
    )

    texto = response.choices[0].message.content.strip()
    datos = json.loads(texto)

    datos = json.loads(texto)

    peso = datos.get("peso", 0)
    precio = datos.get("precio", 0)
    total_ocr = datos.get("total", 0)

    # Recalcular total si hay discrepancia mayor a 0.10
    if peso and precio:
        total_calculado = round(peso * precio, 2)
        if abs(total_ocr - total_calculado) > 0.10:
            print(f"[warn] Total corregido: {total_ocr} → {total_calculado}")
            datos["total"] = total_calculado

    return datos

@app.post("/api/procesar-imagen", response_model=ResultadoVision)
async def procesar_imagen(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo no es una imagen válida.")

    try:
        contents = await file.read()

        image = Image.open(io.BytesIO(contents))
        image.verify()

        # Comprimir si es muy grande
        image = Image.open(io.BytesIO(contents))
        if max(image.size) > 1200:
            image.thumbnail((1200, 1200))
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=85)
            contents = buffer.getvalue()

        print(f"Imagen recibida: {file.filename} ({len(contents)//1024}KB)")

        resultado = analizar_imagen_con_groq(contents)
        return resultado

    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Error procesando imagen: {str(e)}")

@app.get("/health")
def health():
    return {"status": "ok", "groq_key": bool(os.environ.get("GROQ_API_KEY"))}
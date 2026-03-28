from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
import io
from PIL import Image

app = FastAPI(title="Backend Contabilidad WhatsApp")

# Definimos el esquema estricto de lo que debe devolver la IA
# Basado en tu diagrama de arquitectura
class ResultadoVision(BaseModel):
    peso: float
    precio: float
    producto: str
    total: float

@app.post("/api/procesar-imagen", response_model=ResultadoVision)
async def procesar_imagen_local(file: UploadFile = File(...)):
    # 1. Validar el tipo de archivo (solo imágenes)
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo enviado no es una imagen válida.")

    try:
        # 2. Cargar en memoria y procesar localmente
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        
        # verify() comprueba que el archivo no esté corrupto a nivel de bytes
        image.verify() 
        
        # --- ZONA DE EXPANSIÓN FUTURA ---
        # Aquí más adelante podemos agregar una función que redimensione la imagen
        # a 800px o baje la calidad al 80% para ahorrar costos en la API de Claude.
        # --------------------------------

        # 3. Mock (Simulador) de la API de Claude
        # En lugar de llamar a la IA y gastar saldo, devolvemos un caso de prueba perfecto
        print(f"Imagen recibida correctamente: {file.filename}")
        
        return {
            "peso": 2.5,
            "precio": 12.0,
            "producto": "Pollo entero",
            "total": 30.0
        }

    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Error procesando la imagen localmente: {str(e)}")
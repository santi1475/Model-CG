FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

# Instalamos Tesseract OCR y las dependencias del sistema necesarias para OpenCV
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-spa \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Copiamos e instalamos los requerimientos de Python (FastAPI, OpenCV, etc.)
COPY requirements.txt /workspace/
RUN pip install --no-cache-dir -r requirements.txt
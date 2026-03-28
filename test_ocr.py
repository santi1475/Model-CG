import cv2
import numpy as np
import pytesseract
import re

# ─── Configuración centralizada ───────────────────────────────────────────────
CONFIG = {
    'hsv': {
        'bajo':  np.array([55, 60, 60]),
        'alto':  np.array([95, 255, 255]),
    },
    'morfologia': {
        'kernel_size': (3, 3),      # era (5,5) → demasiado agresivo
        'iteraciones_close': 1,     # era 2
        'iteraciones_dilate': 0,    # era 1 → esto los fusionaba
    },
    'deteccion_contornos': {
        'area_minima': 5000,        # era 8000
        'aspect_ratio_min': 1.5,
    },
    'ocr': {
        'escala': 3,
        'config': '--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789.',
    },
    'negocio': {
        'tolerancia_total': 0.15,
    }
}

# ─── Detección automática de displays ─────────────────────────────────────────
def detectar_displays(imagen, cfg):
    h_img, w_img = imagen.shape[:2]
    canal_g = imagen[:, :, 1]

    # ── Perfil vertical: % de píxeles verdes brillantes por fila ──
    # Solo analizar columnas centrales (evitar bordes laterales)
    x0 = int(w_img * 0.15)
    x1 = int(w_img * 0.75)
    franja = canal_g[:, x0:x1]

    # Verde brillante = canal G > 120
    perfil = (franja > 120).mean(axis=1)

    # ── Detectar zonas continuas con > 50% píxeles verdes ──
    zonas = []
    dentro = False
    inicio = 0
    for y in range(h_img):
        if perfil[y] > 0.50 and not dentro:
            inicio = y
            dentro = True
        elif perfil[y] <= 0.50 and dentro:
            zonas.append((inicio, y))
            dentro = False
    if dentro:
        zonas.append((inicio, h_img))

    # ── Filtrar: solo paneles con altura > 80px ──
    paneles = [(y0, y1) for y0, y1 in zonas if (y1 - y0) > 80]

    print(f'Paneles detectados por perfil: {len(paneles)}')
    for i, (y0, y1) in enumerate(paneles):
        print(f'  Panel {i}: y={y0}..{y1} altura={y1-y0}px')

    if len(paneles) < 3:
        print('⚠ Menos de 3 paneles. Ajustar umbral o imagen.')
        return []

    # Tomar los 3 primeros ordenados verticalmente
    paneles = sorted(paneles[:3], key=lambda p: p[0])

    displays = []
    for y0, y1 in paneles:
        displays.append({
            'bbox': (int(w_img * 0.15), y0, int(w_img * 0.57), y1 - y0)
        })
    return displays

# ─── Preprocesamiento de cada ROI ─────────────────────────────────────────────
def preprocesar_roi(imagen, bbox, cfg):
    x, y, w, h = bbox
    roi = imagen[y:y+h, x:x+w]

    if roi.size == 0:
        return None

    canal_g = roi[:, :, 1]

    # Percentil 15 captura los dígitos oscuros sin importar el brillo absoluto
    umbral = int(np.percentile(canal_g, 15))
    umbral = max(umbral, 20)   # mínimo para no capturar solo ruido
    print(f'    umbral adaptativo: {umbral}')

    _, binaria = cv2.threshold(canal_g, umbral, 255, cv2.THRESH_BINARY_INV)

    # Limpieza
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    binaria = cv2.morphologyEx(binaria, cv2.MORPH_OPEN, k, iterations=1)

    escala = cfg['ocr']['escala']
    resultado = cv2.resize(binaria, None, fx=escala, fy=escala,
                           interpolation=cv2.INTER_CUBIC)
    resultado = cv2.copyMakeBorder(resultado, 20, 20, 20, 20,
                                   cv2.BORDER_CONSTANT, value=255)
    return resultado

# ─── OCR ──────────────────────────────────────────────────────────────────────
def leer_numero(imagen_procesada, cfg):
    texto = pytesseract.image_to_string(imagen_procesada, config=cfg['ocr']['config'])
    numeros = re.findall(r'\d+[.,]\d+|\d+', texto)
    if numeros:
        return float(numeros[0].replace(',', '.'))
    return None

# ─── Pipeline principal ───────────────────────────────────────────────────────
def procesar_balanza(ruta_imagen, cfg=CONFIG):
    imagen = cv2.imread(ruta_imagen)
    if imagen is None:
        print('Error: No se encontró la imagen.')
        return None

    h, w = imagen.shape[:2]
    print(f'Imagen cargada: {w}x{h}px')

    displays = detectar_displays(imagen, cfg)
    print(f'Displays detectados: {len(displays)}')

    if len(displays) < 3:
        print('⚠ No se detectaron los 3 displays. Revisa debug_mascara.jpg')
        for i, d in enumerate(displays):
            print(f'  Display {i}: bbox={d["bbox"]}, area={d["area"]}')
        return None

    # Los 3 primeros ordenados verticalmente = peso, precio, total
    campos = ['peso', 'precio', 'total']
    resultados = {}
    imagen_debug = imagen.copy()

    for i, campo in enumerate(campos):
        bbox = displays[i]['bbox']
        procesada = preprocesar_roi(imagen, bbox, cfg)
        if procesada is not None:
            cv2.imwrite(f'debug_{campo}.jpg', procesada)
        else:
            print(f'  {campo}: preprocesamiento retornó None')

        # Dibujar bbox en imagen de debug
        x, y, ww, hh = bbox
        cv2.rectangle(imagen_debug, (x, y), (x+ww, y+hh), (0, 0, 255), 3)
        cv2.putText(imagen_debug, campo, (x, y-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        valor = leer_numero(procesada, cfg)
        resultados[campo] = valor
        print(f'{campo}: {valor}')

    cv2.imwrite('debug_deteccion.jpg', imagen_debug)

    # ─── Validación de negocio ─────────────────────────────────────────────
    peso   = resultados.get('peso')
    precio = resultados.get('precio')
    total  = resultados.get('total')

    print('\n=== RESULTADO ===')
    if peso and precio:
        total_calculado = round(peso * precio, 2)
        total_final     = total if total else total_calculado

        print(f'Peso:             {peso} kg')
        print(f'Precio unitario:  S/ {precio}')
        print(f'Total OCR:        S/ {total}')
        print(f'Total calculado:  S/ {total_calculado}')

        if total:
            diff = abs(total - total_calculado)
            tol  = cfg['negocio']['tolerancia_total']
            confianza = 'ALTA' if diff <= tol else 'BAJA'
            print(f'Confianza:        {confianza} (diff: S/ {diff:.2f})')
        else:
            print('Total OCR no leído → usando valor calculado')

        return {
            'peso': peso,
            'precio': precio,
            'total': total_final,
            'total_calculado': total_calculado,
        }
    else:
        print('No se pudieron leer peso y precio.')
        return resultados
    

if __name__ == '__main__':
    procesar_balanza('balanza.jpg')
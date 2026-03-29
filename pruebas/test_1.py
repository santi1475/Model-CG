import easyocr
import cv2
import numpy as np

reader = easyocr.Reader(['en'], gpu=False)
imagen = cv2.imread('balanza.jpg')

paneles = [
    ('peso',   730,  876),
    ('precio', 916, 1069),
    ('total', 1106, 1269),
]

for nombre, y0, y1 in paneles:
    roi = imagen[y0:y1, 200:740]
    
    # Sin binarizar — EasyOCR en color directamente
    # Solo escalar x2 para darle más resolución
    roi_grande = cv2.resize(roi, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    cv2.imwrite(f'easy_{nombre}.jpg', roi_grande)
    
    resultados = reader.readtext(roi_grande, allowlist='0123456789.', detail=1)
    
    print(f'\n{nombre}:')
    if resultados:
        for bbox, texto, conf in resultados:
            print(f'  "{texto}" conf={conf:.2f}')
    else:
        print('  sin lectura')
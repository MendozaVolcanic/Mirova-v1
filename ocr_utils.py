"""
OCR_UTILS V19 - DETECCIÓN MÚLTIPLES EVENTOS EN ROI
FIX: Detectar eventos superpuestos en misma hora (Lastarria 05:42 + 06:06)

CAMBIOS V19:
1. Detectar GRUPOS de píxeles rojos en ROI (clustering)
2. Asociar cada grupo a su evento correspondiente
3. Validar posición Y de cada grupo (dentro/fuera límite)
4. Mantener ROI temporal, sistema 3 fases, filtro estrella verde
"""

import cv2
import numpy as np
import pytesseract
from datetime import datetime
import pytz
import re
import os
from PIL import Image

# [Mantener todo el código anterior: ROI_CONFIG, LIMITES_Y_COORDENADAS, etc.]

# ========================================
# NUEVA FUNCIÓN V19: DETECTAR GRUPOS PÍXELES ROJOS
# ========================================

def detectar_grupos_pixeles_rojos(roi, umbral_area_minima=20):
    """
    Detecta grupos separados de píxeles rojos en ROI
    Útil para eventos superpuestos en misma hora
    
    Args:
        roi: ROI de imagen (numpy array RGB)
        umbral_area_minima: Área mínima en píxeles para considerar grupo válido
    
    Returns:
        list: [{'centro_y': int, 'area': int, 'bbox': (y1,y2,x1,x2)}, ...]
    """
    
    # Detectar píxeles rojos (mismo criterio que antes)
    mask_rojos = (
        (roi[:, :, 0] > 150) &  # Mucho rojo
        (roi[:, :, 1] < 100) &  # Poco verde
        (roi[:, :, 2] < 100)    # Poco azul
    ).astype(np.uint8) * 255
    
    # Encontrar contornos de grupos
    contours, _ = cv2.findContours(mask_rojos, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    grupos = []
    
    for contour in contours:
        area = cv2.contourArea(contour)
        
        if area < umbral_area_minima:
            continue  # Muy pequeño, probablemente ruido
        
        # Calcular bounding box
        y, x, h, w = cv2.boundingRect(contour)
        
        # Centro del grupo (coordenada Y)
        centro_y = y + h // 2
        
        grupos.append({
            'centro_y': centro_y,
            'area': area,
            'bbox': (y, y+h, x, x+w),
            'pixels': area
        })
    
    # Ordenar por Y (de arriba hacia abajo)
    grupos = sorted(grupos, key=lambda g: g['centro_y'])
    
    return grupos


def asociar_grupos_a_eventos(eventos, grupos, roi_y_start):
    """
    Asocia cada grupo de píxeles rojos a su evento correspondiente
    
    Args:
        eventos: Lista de eventos extraídos de Latest10NTI
        grupos: Lista de grupos detectados en ROI
        roi_y_start: Coordenada Y inicial del ROI en imagen completa
    
    Returns:
        dict: {evento_index: grupo_info}
    """
    
    if not grupos:
        return {}
    
    # Si hay 1 grupo y 1+ eventos → asociar al más reciente
    if len(grupos) == 1:
        return {0: grupos[0]}
    
    # Si hay múltiples grupos → asociar por posición Y
    # Eventos más recientes → Grupos más arriba (menor Y)
    
    asociaciones = {}
    
    for i, evento in enumerate(eventos):
        if i < len(grupos):
            # Asociar evento i al grupo i (ordenados por Y)
            asociaciones[i] = grupos[i]
    
    return asociaciones


# ========================================
# MODIFICACIÓN V19: analizar_puntos_distancia()
# ========================================

def analizar_puntos_distancia(eventos, img_dist_path, volcan_nombre):
    """
    V19: Detecta grupos de píxeles rojos y asocia a eventos individuales
    
    Mejora sobre V17:
    - Detecta múltiples grupos en ROI (no solo total)
    - Asocia cada grupo a su evento
    - Calcula ratio_rojos POR EVENTO
    """
    
    if not os.path.exists(img_dist_path):
        print(f"    Dist.png no encontrado")
        return
    
    img_dist = cv2.imread(img_dist_path)
    if img_dist is None:
        print(f"    Error cargando Dist.png")
        return
    
    img_rgb = cv2.cvtColor(img_dist, cv2.COLOR_BGR2RGB)
    
    # Extraer ROI temporal
    img_height, img_width = img_rgb.shape[:2]
    
    roi_x_start = int(img_width * ROI_CONFIG['x_start_pct'])
    roi_x_end = int(img_width * ROI_CONFIG['x_end_pct'])
    roi_y_start = int(img_height * ROI_CONFIG['y_start_pct'])
    roi_y_end = int(img_height * ROI_CONFIG['y_end_pct'])
    
    roi = img_rgb[roi_y_start:roi_y_end, roi_x_start:roi_x_end]
    
    print(f"\n🎯 V19 - Analizando píxeles con ROI TEMPORAL + GRUPOS")
    print(f"   📍 ROI temporal: X={roi_x_start}-{roi_x_end}, Y={roi_y_start}-{roi_y_end}")
    print(f"   📏 Tamaño ROI: {roi_x_end-roi_x_start}x{roi_y_end-roi_y_start} = {(roi_x_end-roi_x_start)*(roi_y_end-roi_y_start)} px²")
    print(f"   🔍 ROI temporal: {roi.shape}")
    
    # ===== NUEVO V19: DETECTAR GRUPOS =====
    grupos = detectar_grupos_pixeles_rojos(roi)
    
    print(f"   🔴 Grupos detectados: {len(grupos)}")
    for i, grupo in enumerate(grupos, 1):
        print(f"      Grupo {i}: Y={grupo['centro_y']}, área={grupo['area']} px²")
    
    # Asociar grupos a eventos
    asociaciones = asociar_grupos_a_eventos(eventos, grupos, roi_y_start)
    
    # Análisis global (mantener compatibilidad V17)
    mask_rojos = (
        (roi[:, :, 0] > 150) &
        (roi[:, :, 1] < 100) &
        (roi[:, :, 2] < 100)
    )
    mask_negros = (
        (roi[:, :, 0] < 100) &
        (roi[:, :, 1] < 100) &
        (roi[:, :, 2] < 100)
    )
    
    total_rojos = np.sum(mask_rojos)
    total_negros = np.sum(mask_negros)
    
    print(f"   🔴 Total rojos: {total_rojos} px")
    print(f"   ⚫ Total negros: {total_negros} px")
    
    # Estrella verde (mantener V16)
    mask_verde = (
        (img_rgb[:, :, 1] > 200) &
        (img_rgb[:, :, 0] < 150) &
        (img_rgb[:, :, 2] < 150)
    )
    mask_grafico = np.zeros_like(mask_verde)
    mask_grafico[100:, 250:] = mask_verde[100:, 250:]
    total_estrella = np.sum(mask_grafico)
    
    print(f"   🟢 Estrella: {total_estrella} px ({'SÍ' if total_estrella > 50 else 'NO'})")
    
    # Agregar datos a eventos
    for i, evento in enumerate(eventos):
        # Ratio global (compatibilidad V17)
        evento['ratio_rojos'] = total_rojos / roi.size if roi.size > 0 else 0
        evento['ratio_negros'] = total_negros / roi.size if roi.size > 0 else 0
        
        # ===== NUEVO V19: DATOS POR GRUPO =====
        if i in asociaciones:
            grupo = asociaciones[i]
            evento['grupo_pixeles'] = {
                'centro_y': grupo['centro_y'],
                'area': grupo['area'],
                'y_absoluto': roi_y_start + grupo['centro_y']
            }
            print(f"   ✅ Evento {i+1} asociado a grupo Y={grupo['centro_y']} ({grupo['area']} px²)")
        else:
            evento['grupo_pixeles'] = None
            print(f"   ⚠️ Evento {i+1} sin grupo asociado")


# ========================================
# MODIFICACIÓN V19: clasificar_confianza()
# ========================================

def clasificar_confianza(evento, img_dist_path, volcan_nombre):
    """
    V19: Valida GRUPOS de píxeles individuales antes de validar con estrella
    
    SISTEMA 3 FASES (mejorado):
    FASE 1: Píxeles rojos en ROI temporal (individual POR GRUPO)
    FASE 2: Estrella verde (mantener V16)
    FASE 3: Píxeles negros (fallback)
    """
    
    vrp_mw = evento.get('VRP_MW', 0)
    
    # Filtrar VRPs inválidos
    if vrp_mw == 0 or np.isnan(vrp_mw) or vrp_mw is None:
        return {
            'guardar': False,
            'guardar_imagenes': False,
            'tipo_registro': 'VRP_INVALIDO',
            'confianza': 'invalido',
            'Color_Punto': 'sin_punto',
            'Nota': f'VRP inválido: {vrp_mw}'
        }
    
    # ===== FASE 1: VALIDAR CON GRUPO INDIVIDUAL (NUEVO V19) =====
    
    grupo_info = evento.get('grupo_pixeles')
    
    if grupo_info:
        # Hay grupo asociado → validar posición Y
        y_absoluto = grupo_info['y_absoluto']
        area_grupo = grupo_info['area']
        
        limites = LIMITES_Y_COORDENADAS.get(volcan_nombre, {})
        y_limite_px = limites.get('Y_LIMITE_PX', 257)
        
        if y_absoluto >= y_limite_px:
            # Grupo DENTRO del límite → VRP REAL
            distancia_aprox = ((y_absoluto - y_limite_px) / (335 - y_limite_px)) * limites.get('LIMITE_KM', 5.0)
            
            return {
                'guardar': True,
                'guardar_imagenes': True,
                'tipo_registro': 'ALERTA_TERMICA_OCR',
                'confianza': 'alta',
                'Color_Punto': 'sin_punto',
                'Metodo_Deteccion': 'grupo_pixeles_v19',
                'Nota': f'Grupo píxeles rojos en Y={y_absoluto} (área={area_grupo} px², dist≈{distancia_aprox:.2f} km)'
            }
        else:
            # Grupo FUERA del límite → FALSO POSITIVO
            return {
                'guardar': False,
                'guardar_imagenes': False,
                'tipo_registro': 'FALSO_POSITIVO_OCR',
                'confianza': 'baja',
                'Color_Punto': 'sin_punto',
                'Nota': f'Grupo fuera límite: Y={y_absoluto} < {y_limite_px}'
            }
    
    # ===== FASE 2: ESTRELLA VERDE (MANTENER V16) =====
    
    # Si no hay grupo individual, validar con estrella verde
    confianza_estrella, tipo_estrella, nota_estrella = validar_con_estrella_verde(
        evento, img_dist_path, volcan_nombre
    )
    
    if confianza_estrella != 'desconocido':
        return {
            'guardar': tipo_estrella == 'ALERTA_TERMICA_OCR',
            'guardar_imagenes': tipo_estrella == 'ALERTA_TERMICA_OCR',
            'tipo_registro': tipo_estrella,
            'confianza': confianza_estrella,
            'Color_Punto': evento.get('Color_Punto', 'sin_punto'),
            'Metodo_Deteccion': 'estrella_verde_v16',
            'Nota': nota_estrella
        }
    
    # ===== FASE 3: PÍXELES NEGROS (FALLBACK) =====
    
    ratio_negros = evento.get('ratio_negros', 0)
    
    if ratio_negros > 0.70:
        return {
            'guardar': False,
            'guardar_imagenes': False,
            'tipo_registro': 'FALSO_POSITIVO_OCR',
            'confianza': 'baja',
            'Color_Punto': evento.get('Color_Punto', 'sin_punto'),
            'Nota': f'ROI mayormente negro (ratio={ratio_negros:.2f})'
        }
    
    # Sin señal clara → FALSO_POSITIVO
    return {
        'guardar': False,
        'guardar_imagenes': False,
        'tipo_registro': 'FALSO_POSITIVO_OCR',
        'confianza': 'baja',
        'Color_Punto': evento.get('Color_Punto', 'mixto'),
        'Nota': 'Sin grupo ni estrella clara'
    }


# [Mantener todas las demás funciones sin cambios: validar_con_estrella_verde, detectar_centro_estrella_verde, etc.]

"""
OCR_UTILS.PY V24 - Umbral área grupos reducido a 3 px²
BASE: V23 (umbral 10 px²) + FIX umbral más agresivo

CAMBIO V24 (QUIRÚRGICO):
- FIX: Reducir umbral_area_minima de 10 → 3 px²
- PROBLEMA: Lascar grupo real = 8 px² → descartado con umbral 10
- SOLUCIÓN: Umbral 3 px² captura grupos pequeños pero reales
- JUSTIFICACIÓN: Análisis muestra grupo compacto de 8 px² (dispersión Y=3.7, X=1.1)

PRESERVA V23-V17: Todas las funcionalidades
"""

import cv2
import numpy as np
import pytesseract
from datetime import datetime
import pytz
import re
import os
from PIL import Image

LIMITES_Y_COORDENADAS = {
    'Lastarria': {'Y_LIMITE_PX': 272, 'Y_EJE_X_PX': 335, 'LIMITE_KM': 3.0},
    'PlanchonPeteroa': {'Y_LIMITE_PX': 272, 'Y_EJE_X_PX': 335, 'LIMITE_KM': 3.0},
    'Peteroa': {'Y_LIMITE_PX': 272, 'Y_EJE_X_PX': 335, 'LIMITE_KM': 3.0},
    'Copahue': {'Y_LIMITE_PX': 266, 'Y_EJE_X_PX': 335, 'LIMITE_KM': 4.0},
    'Lascar': {'Y_LIMITE_PX': 257, 'Y_EJE_X_PX': 335, 'LIMITE_KM': 5.0},
    'Isluga': {'Y_LIMITE_PX': 257, 'Y_EJE_X_PX': 335, 'LIMITE_KM': 5.0},
    'Nevados de Chillan': {'Y_LIMITE_PX': 257, 'Y_EJE_X_PX': 335, 'LIMITE_KM': 5.0},
    'ChillanNevadosde': {'Y_LIMITE_PX': 257, 'Y_EJE_X_PX': 335, 'LIMITE_KM': 5.0},
    'Llaima': {'Y_LIMITE_PX': 257, 'Y_EJE_X_PX': 335, 'LIMITE_KM': 5.0},
    'Villarrica': {'Y_LIMITE_PX': 257, 'Y_EJE_X_PX': 335, 'LIMITE_KM': 5.0},
    'Chaiten': {'Y_LIMITE_PX': 257, 'Y_EJE_X_PX': 335, 'LIMITE_KM': 5.0},
    'Puyehue-Cordon Caulle': {'Y_LIMITE_PX': 148, 'Y_EJE_X_PX': 335, 'LIMITE_KM': 20.0},
    'PuyehueCordonCaulle': {'Y_LIMITE_PX': 148, 'Y_EJE_X_PX': 335, 'LIMITE_KM': 20.0},
    'Tupungatito': {'Y_LIMITE_PX': 257, 'Y_EJE_X_PX': 335, 'LIMITE_KM': 7.0}  # =====CAMBIO: 5→7 km=====
}

ROI_CONFIG = {
    'x_start_pct': 0.8424,
    'x_end_pct': 0.8635,
    'y_start_pct': 0.1817,
    'y_end_pct': 0.4933
}

def detectar_grupos_pixeles_rojos(roi, umbral_area_minima=3):
    # =====NUEVO V24: Umbral reducido 10 → 3 px²=====
    # PROBLEMA: Lascar grupo real 8 px² → descartado
    # EVIDENCIA: Grupo compacto (dispersión Y=3.7, X=1.1)
    # SOLUCIÓN: Umbral 3 px² captura grupos pequeños reales
    # ================================================
    """
    V24: Detecta grupos píxeles rojos (umbral 3 px²)
    """
    mask_rojos = (
        (roi[:, :, 0] > 150) &
        (roi[:, :, 1] < 100) &
        (roi[:, :, 2] < 100)
    ).astype(np.uint8) * 255
    
    contours, _ = cv2.findContours(mask_rojos, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    grupos = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < umbral_area_minima:
            continue
        
        x, y, w, h = cv2.boundingRect(contour)
        centro_y = y + h // 2
        
        grupos.append({
            'centro_y': centro_y,
            'area': int(area),
            'bbox': (y, y+h, x, x+w),
            'pixels': int(area)
        })
    
    return sorted(grupos, key=lambda g: g['centro_y'])


def asociar_grupos_a_eventos(eventos, grupos, roi_y_start):
    """V19: Sin cambios"""
    if not grupos:
        return {}
    
    if len(grupos) == 1:
        grupo = grupos[0].copy()
        grupo['y_absoluto'] = roi_y_start + grupo['centro_y']
        return {0: grupo}
    
    asociaciones = {}
    for i, evento in enumerate(eventos):
        if i < len(grupos):
            grupo = grupos[i].copy()
            grupo['y_absoluto'] = roi_y_start + grupo['centro_y']
            asociaciones[i] = grupo
    
    return asociaciones


def extraer_eventos_latest10nti(img_path):
    """V11: Sin cambios"""
    print(f"\n🔍 OCR V11 - Procesando: {img_path}")
    
    try:
        img = Image.open(img_path)
        img_array = np.array(img)
        print(f"   ✅ Imagen cargada: {img_array.shape}")
        
        configs = [
            r'--oem 3 --psm 6',
            r'--oem 3 --psm 4',
            r'--oem 3 --psm 11'
        ]
        
        texto = None
        for i, config in enumerate(configs):
            texto_temp = pytesseract.image_to_string(img_array, config=config)
            
            if texto_temp and len(texto_temp.strip()) > 50:
                texto = texto_temp
                print(f"   ✅ OCR exitoso con config {i+1} ({len(texto)} chars)")
                break
        
        if not texto:
            print(f"   ❌ NINGUNA configuración OCR funcionó")
            return []
        
        patron_fechas = r'(\d{2}-[A-Za-z]{3}-\d{4}\s+\d{2}:\d{2}:\d{2})'
        
        fechas = []
        for match in re.finditer(patron_fechas, texto):
            fecha_str = match.group(1)
            start_pos = match.start()
            texto_antes = texto[max(0, start_pos-20):start_pos]
            
            if 'Last Update' in texto_antes or 'update' in texto_antes.lower():
                print(f"   ⏭️ Saltando 'Last Update': {fecha_str}")
                continue
            
            fechas.append(fecha_str)
        
        print(f"\n📅 FECHAS EXTRAÍDAS: {len(fechas)}")
        for i, f in enumerate(fechas[:5]):
            print(f"   {i+1}. {f}")
        if len(fechas) > 5:
            print(f"   ... (+{len(fechas)-5} más)")
        
        patron_vrp = r'VRP\s*=?\s*([\d.]+|NaN)\s*MW'
        
        vrps = []
        for match in re.finditer(patron_vrp, texto, re.IGNORECASE):
            vrp_str = match.group(1)
            vrps.append(vrp_str)
        
        print(f"\n🔥 VRP EXTRAÍDOS: {len(vrps)}")
        for i, v in enumerate(vrps[:5]):
            print(f"   {i+1}. {v} MW")
        if len(vrps) > 5:
            print(f"   ... (+{len(vrps)-5} más)")
        
        n_min = min(len(fechas), len(vrps))
        eventos = []
        
        for i in range(n_min):
            try:
                dt_obj = datetime.strptime(fechas[i], "%d-%b-%Y %H:%M:%S")
                dt_utc = dt_obj.replace(tzinfo=pytz.utc)
                ts = int(dt_utc.timestamp())
                
                vrp_str = vrps[i]
                if vrp_str.lower() == 'nan':
                    vrp_mw = 0.0
                else:
                    vrp_mw = float(vrp_str)
                
                eventos.append({
                    'datetime': dt_utc,
                    'timestamp': ts,
                    'vrp_mw': vrp_mw
                })
            except Exception as e:
                print(f"   ⚠️ Error parseando evento {i+1}: {e}")
                continue
        
        print(f"\n✅ EVENTOS CREADOS: {len(eventos)}")
        return eventos
    
    except Exception as e:
        print(f"   ❌ ERROR en extraer_eventos_latest10nti: {e}")
        import traceback
        traceback.print_exc()
        return []


def analizar_puntos_distancia(img_dist_path, eventos, volcan_nombre):
    """V24: umbral 3 px²"""
    try:
        if not os.path.exists(img_dist_path):
            print(f"    ⚠️ Dist.png no encontrado: {img_dist_path}")
            return eventos
        
        img_dist = cv2.imread(img_dist_path)
        if img_dist is None:
            print(f"    ❌ Error cargando Dist.png")
            return eventos
        
        img_rgb = cv2.cvtColor(img_dist, cv2.COLOR_BGR2RGB)
        height, width = img_rgb.shape[:2]
        
        roi_x_start = int(width * ROI_CONFIG['x_start_pct'])
        roi_x_end = int(width * ROI_CONFIG['x_end_pct'])
        roi_y_start = int(height * ROI_CONFIG['y_start_pct'])
        roi_y_end = int(height * ROI_CONFIG['y_end_pct'])
        
        roi = img_rgb[roi_y_start:roi_y_end, roi_x_start:roi_x_end]
        
        print(f"\n🎯 V24 - ROI TEMPORAL + GRUPOS (umbral 3 px²)")
        print(f"   📍 ROI: X={roi_x_start}-{roi_x_end}, Y={roi_y_start}-{roi_y_end}")
        print(f"   📏 Tamaño: {roi.shape[1]}x{roi.shape[0]} = {roi.shape[0]*roi.shape[1]} px²")
        
        grupos = detectar_grupos_pixeles_rojos(roi)
        
        print(f"   🔴 Grupos detectados: {len(grupos)}")
        for i, grupo in enumerate(grupos, 1):
            y_abs = roi_y_start + grupo['centro_y']
            print(f"      Grupo {i}: Y_rel={grupo['centro_y']}, Y_abs={y_abs}, área={grupo['area']} px²")
        
        asociaciones = asociar_grupos_a_eventos(eventos, grupos, roi_y_start)
        
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
        
        pixeles_rojos = np.sum(mask_rojos)
        pixeles_negros = np.sum(mask_negros)
        total_roi = roi.size
        
        ratio_rojos = pixeles_rojos / total_roi if total_roi > 0 else 0
        ratio_negros = pixeles_negros / total_roi if total_roi > 0 else 0
        
        mask_verdes = cv2.inRange(
            cv2.cvtColor(roi, cv2.COLOR_RGB2HSV),
            (40, 80, 80),
            (80, 255, 255)
        )
        pixeles_verdes = np.sum(mask_verdes > 0)
        
        print(f"   🟢 Estrella ROI: {pixeles_verdes} px")
        print(f"   🔴 Rojos globales: {pixeles_rojos} px")
        print(f"   ⚫ Negros globales: {pixeles_negros} px")
        
        if ratio_rojos > 0.10:
            color_dominante = "rojo"
        elif ratio_negros > 0.70:
            color_dominante = "negro"
        else:
            color_dominante = "mixto"
        
        print(f"   🎯 Clasificación: {color_dominante}")
        
        for i, evento in enumerate(eventos):
            evento['color_punto'] = color_dominante
            evento['pixeles_rojos'] = int(pixeles_rojos)
            evento['pixeles_negros'] = int(pixeles_negros)
            evento['pixeles_verdes'] = int(pixeles_verdes)
            evento['ratio_rojos'] = float(ratio_rojos)
            evento['ratio_negros'] = float(ratio_negros)
            evento['metodo'] = 'roi_temporal_v24'
            
            if i in asociaciones:
                evento['grupo_pixeles'] = asociaciones[i]
                print(f"   ✅ Evento {i+1} → grupo Y={asociaciones[i]['centro_y']} ({asociaciones[i]['area']} px²)")
            else:
                evento['grupo_pixeles'] = None
                if len(grupos) > 0:
                    print(f"   ⚠️ Evento {i+1} sin grupo")
        
        return eventos
    
    except Exception as e:
        print(f"   ❌ ERROR V24: {e}")
        import traceback
        traceback.print_exc()
        return eventos


def detectar_centro_estrella_verde(img_dist):
    """V16: Sin cambios"""
    if img_dist is None or img_dist.size == 0:
        return None
    
    try:
        img_hsv = cv2.cvtColor(img_dist, cv2.COLOR_RGB2HSV)
        mask_verde = cv2.inRange(img_hsv, (40, 80, 80), (80, 255, 255))
        
        mask_grafico = np.zeros_like(mask_verde)
        mask_grafico[100:, 250:] = mask_verde[100:, 250:]
        
        contornos, _ = cv2.findContours(mask_grafico, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contornos) == 0:
            return None
        
        contornos_validos = [c for c in contornos if cv2.contourArea(c) > 50]
        
        if len(contornos_validos) == 0:
            return None
        
        contornos_estrella = []
        for c in contornos_validos:
            M = cv2.moments(c)
            if M['m00'] > 0:
                cy = int(M['m01'] / M['m00'])
                if 250 <= cy <= 450:
                    contornos_estrella.append(c)
        
        if contornos_estrella:
            contorno_max = max(contornos_estrella, key=cv2.contourArea)
        else:
            contorno_max = max(contornos_validos, key=cv2.contourArea)
        
        M = cv2.moments(contorno_max)
        if M['m00'] == 0:
            return None
        
        cy = int(M['m01'] / M['m00'])
        
        return cy
    
    except Exception as e:
        print(f"      Error estrella: {e}")
        return None


def validar_con_estrella_verde(img_dist, volcan_nombre):
    """V16: Sin cambios"""
    if volcan_nombre not in LIMITES_Y_COORDENADAS:
        return None, None, f"Volcán '{volcan_nombre}' sin coordenadas"
    
    coords = LIMITES_Y_COORDENADAS[volcan_nombre]
    
    y_estrella = detectar_centro_estrella_verde(img_dist)
    
    if y_estrella is None:
        return None, None, "No se detectó estrella verde"
    
    y_limite = coords['Y_LIMITE_PX']
    y_eje_x = coords['Y_EJE_X_PX']
    
    if y_estrella >= y_limite:
        if y_estrella >= y_eje_x:
            dist_km = 0.0
        else:
            proporcion = (y_eje_x - y_estrella) / (y_eje_x - y_limite)
            dist_km = proporcion * coords['LIMITE_KM']
        
        nota = f"Estrella Y={y_estrella} (dentro límite Y={y_limite}, dist≈{dist_km:.2f} km)"
        return 'alta', 'ALERTA_TERMICA_OCR', nota
    else:
        nota = f"Estrella Y={y_estrella} (fuera límite Y={y_limite})"
        return 'baja', 'FALSO_POSITIVO_OCR', nota


def clasificar_confianza(evento, img_dist_path, volcan_nombre):
    """V24: umbral 3 px²"""
    vrp_mw = evento.get('vrp_mw', 0)
    
    if vrp_mw == 0 or np.isnan(vrp_mw) or vrp_mw is None:
        return {
            'guardar': False,
            'guardar_imagenes': False,
            'tipo_registro': 'VRP_INVALIDO',
            'confianza': 'invalido',
            'requiere_verificacion': False,
            'Color_Punto': 'sin_punto',
            'nota': f'VRP inválido: {vrp_mw}'
        }
    
    grupo_info = evento.get('grupo_pixeles')
    
    if grupo_info:
        y_absoluto = grupo_info['y_absoluto']
        area_grupo = grupo_info['area']
        
        limites = LIMITES_Y_COORDENADAS.get(volcan_nombre, {})
        y_limite_px = limites.get('Y_LIMITE_PX', 257)
        y_eje_x = limites.get('Y_EJE_X_PX', 335)
        limite_km = limites.get('LIMITE_KM', 5.0)
        
        if y_absoluto >= y_limite_px:
            distancia_aprox = ((y_absoluto - y_limite_px) / (y_eje_x - y_limite_px)) * limite_km
            
            print(f"   ═════════════════════════════════════════════════════════")
            print(f"   🎯 FASE 1 V24 ({area_grupo} px²): Y={y_absoluto} >= {y_limite_px} ✅")
            print(f"      ✅ ALERTA_TERMICA_OCR")
            
            return {
                'guardar': True,
                'guardar_imagenes': True,
                'tipo_registro': 'ALERTA_TERMICA_OCR',
                'confianza': 'alta',
                'requiere_verificacion': False,
                'Color_Punto': 'sin_punto',
                'Metodo_Deteccion': 'grupo_pixeles_v24',
                'nota': f'Grupo píxeles Y={y_absoluto} (área={area_grupo} px², dist≈{distancia_aprox:.2f} km)'
            }
        else:
            print(f"   ═════════════════════════════════════════════════════════")
            print(f"   🎯 FASE 1 V24: Y={y_absoluto} < {y_limite_px} ❌")
            
            return {
                'guardar': False,
                'guardar_imagenes': False,
                'tipo_registro': 'FALSO_POSITIVO_OCR',
                'confianza': 'baja',
                'requiere_verificacion': False,
                'Color_Punto': 'sin_punto',
                'nota': f'Grupo fuera límite: Y={y_absoluto} < {y_limite_px}'
            }
    
    print(f"   ═════════════════════════════════════════════════════════")
    print(f"   🎯 FASE 1: Sin grupo → FASE 2 (estrella)")
    
    if img_dist_path and os.path.exists(img_dist_path):
        import cv2
        img_dist = cv2.imread(img_dist_path)
        
        if img_dist is not None:
            confianza_estrella, tipo_estrella, nota_estrella = validar_con_estrella_verde(
                img_dist, volcan_nombre
            )
        else:
            confianza_estrella = 'desconocido'
            tipo_estrella = 'DESCONOCIDO'
            nota_estrella = 'Error cargando Dist.png'
    else:
        confianza_estrella = 'desconocido'
        tipo_estrella = 'DESCONOCIDO'
        nota_estrella = 'Dist.png no disponible'
    
    if confianza_estrella != 'desconocido':
        return {
            'guardar': tipo_estrella == 'ALERTA_TERMICA_OCR',
            'guardar_imagenes': tipo_estrella == 'ALERTA_TERMICA_OCR',
            'tipo_registro': tipo_estrella,
            'confianza': confianza_estrella,
            'requiere_verificacion': False,
            'Color_Punto': evento.get('Color_Punto', 'sin_punto'),
            'Metodo_Deteccion': 'estrella_verde_v16',
            'nota': nota_estrella
        }
    
    ratio_negros = evento.get('ratio_negros', 0)
    
    if ratio_negros > 0.70:
        return {
            'guardar': False,
            'guardar_imagenes': False,
            'tipo_registro': 'FALSO_POSITIVO_OCR',
            'confianza': 'baja',
            'requiere_verificacion': False,
            'Color_Punto': evento.get('Color_Punto', 'sin_punto'),
            'nota': f'ROI negro (ratio={ratio_negros:.2f})'
        }
    
    return {
        'guardar': False,
        'guardar_imagenes': False,
        'tipo_registro': 'FALSO_POSITIVO_OCR',
        'confianza': 'baja',
        'requiere_verificacion': False,
        'Color_Punto': evento.get('Color_Punto', 'mixto'),
        'nota': 'Sin grupo ni estrella'
    }


def verificar_evento_no_existe(evento, volcan_nombre, sensor, df_consolidado, df_ocr):
    """Verifica duplicados"""
    ts = evento['timestamp']
    
    if not df_consolidado.empty:
        existe_consolidado = df_consolidado[
            (df_consolidado['timestamp'] == ts) &
            (df_consolidado['Volcan'] == volcan_nombre) &
            (df_consolidado['Sensor'] == sensor)
        ]
        
        if not existe_consolidado.empty:
            print(f"      ❌ DUPLICADO en latest.php")
            return False
    
    if not df_ocr.empty:
        existe_ocr = df_ocr[
            (df_ocr['timestamp'] == ts) &
            (df_ocr['Volcan'] == volcan_nombre) &
            (df_ocr['Sensor'] == sensor)
        ]
        
        if not existe_ocr.empty:
            print(f"      ❌ DUPLICADO en OCR")
            return False
    
    print(f"      ✅ NUEVO")
    return True


if __name__ == "__main__":
    print("="*70)
    print("OCR UTILS V24 - Umbral 3 px²")
    print("="*70)

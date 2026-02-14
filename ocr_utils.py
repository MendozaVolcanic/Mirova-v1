"""
OCR UTILS V17 - ROI TEMPORAL RESTAURADO + ESTRELLA VERDE + TUPUNGATITO

CAMBIOS V17:
1. ROI TEMPORAL restaurado (análisis de píxeles en columna último día)
2. Estrella verde con filtro de zona (V16)
3. Tupungatito agregado
4. Sistema 3 fases completo
"""

import cv2
import numpy as np
import pytesseract
from datetime import datetime
import pytz
import re
import os
from PIL import Image

# ========================================
# COORDENADAS DE LÍMITES
# ========================================
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
    # ===== NUEVO: TUPUNGATITO =====
    'Tupungatito': {'Y_LIMITE_PX': 257, 'Y_EJE_X_PX': 335, 'LIMITE_KM': 5.0}
}

# ========================================
# ROI TEMPORAL (RESTAURADO V17)
# ========================================
ROI_CONFIG = {
    'x_start_pct': 0.8424,  # 84.24% del ancho (último día)
    'x_end_pct': 0.8635,    # 86.35%
    'y_start_pct': 0.1817,  # 18.17% altura
    'y_end_pct': 0.4933     # 49.33%
}

# JUSTIFICACIÓN:
# - Máxima precisión temporal (sin mezcla de días)
# - Reduce área de análisis en 99.4% (3,162 px² vs 510,000 px²)
# - Ideal para monitoreo en tiempo real
# - Evita falsos positivos de días antiguos


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
        
        # ===== Extracción fechas =====
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
        
        # ===== Extracción VRP =====
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
        
        # ===== Emparejar fechas con VRP =====
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


def analizar_puntos_distancia(img_dist_path, eventos):
    """
    V17: RESTAURADO ROI TEMPORAL
    Analiza píxeles en COLUMNA DEL ÚLTIMO DÍA
    """
    print(f"\n🎯 V17 - Analizando píxeles con ROI TEMPORAL")
    
    try:
        img = cv2.imread(img_dist_path)
        if img is None or img.size == 0:
            print(f"   ❌ No se pudo cargar imagen")
            return eventos
        
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        height, width = img_rgb.shape[:2]
        
        # ===== EXTRAER ROI TEMPORAL (ÚLTIMO DÍA) =====
        roi_x_start = int(width * ROI_CONFIG['x_start_pct'])   # 716
        roi_x_end = int(width * ROI_CONFIG['x_end_pct'])       # 733
        roi_y_start = int(height * ROI_CONFIG['y_start_pct'])  # 109
        roi_y_end = int(height * ROI_CONFIG['y_end_pct'])      # 295
        
        roi = img_rgb[roi_y_start:roi_y_end, roi_x_start:roi_x_end]
        
        print(f"   📍 ROI temporal: X={roi_x_start}-{roi_x_end}, Y={roi_y_start}-{roi_y_end}")
        print(f"   📏 Tamaño ROI: {roi.shape[1]}x{roi.shape[0]} = {roi.shape[0]*roi.shape[1]} px²")
        
        # ===== DETECTAR PÍXELES ROJOS =====
        mask_rojos = (roi[:, :, 0] > 150) & \
                     ((roi[:, :, 0] - roi[:, :, 1]) > 50) & \
                     ((roi[:, :, 0] - roi[:, :, 2]) > 50)
        
        # ===== DETECTAR PÍXELES NEGROS =====
        mask_negros = (roi[:, :, 0] < 100) & \
                      (roi[:, :, 1] < 100) & \
                      (roi[:, :, 2] < 100)
        
        # ===== DETECTAR ESTRELLA VERDE (para mostrar en log) =====
        mask_verdes = cv2.inRange(
            cv2.cvtColor(roi, cv2.COLOR_RGB2HSV),
            (40, 80, 80),
            (80, 255, 255)
        )
        
        pixeles_rojos = np.sum(mask_rojos)
        pixeles_negros = np.sum(mask_negros)
        pixeles_verdes = np.sum(mask_verdes > 0)
        
        total_roi = roi.shape[0] * roi.shape[1]
        
        ratio_rojos = pixeles_rojos / total_roi if total_roi > 0 else 0
        ratio_negros = pixeles_negros / total_roi if total_roi > 0 else 0
        
        # ===== CLASIFICAR COLOR DOMINANTE =====
        if ratio_rojos > 0.10:
            color_dominante = "rojo"
        elif ratio_negros > 0.70:
            color_dominante = "negro"
        else:
            color_dominante = "mixto"
        
        print(f"   🔍 ROI temporal: ({roi.shape[1]}, {roi.shape[0]}, {roi.shape[2]})")
        print(f"   🟢 Estrella: {pixeles_verdes} px ({'SÍ' if pixeles_verdes > 0 else 'NO'})")
        print(f"   🔴 Rojos: {pixeles_rojos} px")
        print(f"   ⚫ Negros: {pixeles_negros} px")
        print(f"   📊 Ratio R/N: {ratio_rojos:.2f}")
        print(f"   🎯 Clasificación ROI: {color_dominante}")
        
        # ===== AGREGAR DATOS AL ÚLTIMO EVENTO (más reciente) =====
        if eventos:
            eventos[-1]['color_punto'] = color_dominante
            eventos[-1]['pixeles_rojos'] = int(pixeles_rojos)
            eventos[-1]['pixeles_negros'] = int(pixeles_negros)
            eventos[-1]['pixeles_verdes'] = int(pixeles_verdes)
            eventos[-1]['ratio_rojos'] = float(ratio_rojos)
            eventos[-1]['ratio_negros'] = float(ratio_negros)
            eventos[-1]['metodo'] = 'roi_temporal_v17'
        
        return eventos
    
    except Exception as e:
        print(f"   ❌ ERROR en analizar_puntos_distancia: {e}")
        import traceback
        traceback.print_exc()
        return eventos


def detectar_centro_estrella_verde(img_dist):
    """
    V16: Detecta centro de estrella verde con FILTRO DE ZONA
    FIX: Solo busca en gráfico (Y>100, X>250), NO en interfaz
    """
    if img_dist is None or img_dist.size == 0:
        return None
    
    try:
        img_hsv = cv2.cvtColor(img_dist, cv2.COLOR_RGB2HSV)
        
        # Detectar verde
        mask_verde = cv2.inRange(img_hsv, (40, 80, 80), (80, 255, 255))
        
        # ===== FIX V16: FILTRAR SOLO ZONA DEL GRÁFICO =====
        mask_grafico = np.zeros_like(mask_verde)
        mask_grafico[100:, 250:] = mask_verde[100:, 250:]  # Y>100, X>250
        
        # Encontrar contornos en ZONA FILTRADA
        contornos, _ = cv2.findContours(mask_grafico, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contornos) == 0:
            return None
        
        # Filtrar por área mínima
        contornos_validos = [c for c in contornos if cv2.contourArea(c) > 50]
        
        if len(contornos_validos) == 0:
            return None
        
        # ===== PRIORIZAR ZONA TÍPICA DE ESTRELLA (Y=250-450) =====
        contornos_estrella = []
        for c in contornos_validos:
            M = cv2.moments(c)
            if M['m00'] > 0:
                cy = int(M['m01'] / M['m00'])
                if 250 <= cy <= 450:  # Zona típica de estrella
                    contornos_estrella.append(c)
        
        # Usar zona estrella si existe, sino usar todos
        if contornos_estrella:
            contorno_max = max(contornos_estrella, key=cv2.contourArea)
        else:
            contorno_max = max(contornos_validos, key=cv2.contourArea)
        
        # Calcular centro
        M = cv2.moments(contorno_max)
        if M['m00'] == 0:
            return None
        
        cy = int(M['m01'] / M['m00'])
        
        return cy
    
    except Exception as e:
        print(f"      Error detectando estrella verde: {e}")
        return None


def validar_con_estrella_verde(img_dist, volcan_nombre):
    """
    V16: Valida si estrella verde está dentro del límite
    Compatible con V17 (puede usarse como FASE 2)
    """
    if volcan_nombre not in LIMITES_Y_COORDENADAS:
        return None, None, f"Volcán '{volcan_nombre}' sin coordenadas calibradas"
    
    coords = LIMITES_Y_COORDENADAS[volcan_nombre]
    
    y_estrella = detectar_centro_estrella_verde(img_dist)
    
    if y_estrella is None:
        return None, None, "No se detectó estrella verde"
    
    y_limite = coords['Y_LIMITE_PX']
    y_eje_x = coords['Y_EJE_X_PX']
    
    # REGLA: Si Y estrella >= Y límite → DENTRO
    if y_estrella >= y_limite:
        if y_estrella >= y_eje_x:
            dist_km = 0.0
        else:
            proporcion = (y_eje_x - y_estrella) / (y_eje_x - y_limite)
            dist_km = proporcion * coords['LIMITE_KM']
        
        nota = f"Estrella en Y={y_estrella} (dentro límite Y={y_limite}, dist≈{dist_km:.2f} km)"
        return 'alta', 'ALERTA_TERMICA_OCR', nota
    else:
        nota = f"Estrella en Y={y_estrella} (fuera límite Y={y_limite})"
        return 'baja', 'FALSO_POSITIVO_OCR', nota


def clasificar_confianza(evento, img_dist_path, volcan_nombre):
    """
    V17: CLASIFICACIÓN 3 FASES COMPLETA
    
    FASE 1: Píxeles rojos en ROI TEMPORAL (último día) ← RESTAURADO
    FASE 2: Estrella verde en gráfico (V16)
    FASE 3: Píxeles negros (fallback)
    """
    
    # ===== VALIDACIÓN VRP =====
    vrp_mw = evento.get('vrp_mw', 0)
    
    if vrp_mw <= 0 or vrp_mw != vrp_mw:  # NaN check
        return {
            'guardar': False,
            'guardar_imagenes': False,
            'tipo_registro': 'VRP_INVALIDO',
            'confianza': 'invalido',
            'requiere_verificacion': False,
            'metodo': 'vrp_invalido',
            'nota': f'VRP inválido: {vrp_mw}'
        }
    
    # ===== FASE 1: ROI TEMPORAL (PÍXELES ROJOS) =====
    ratio_rojos = evento.get('ratio_rojos', 0)
    
    print(f"   ═════════════════════════════════════════════════════════")
    print(f"   🎯 FASE 1 (ROI temporal): Ratio rojos = {ratio_rojos:.2f}")
    
    # Si >30% rojos → ALERTA (alta confianza)
    if ratio_rojos > 0.30:
        print(f"      ✅ ALERTA_TERMICA_OCR (>30% rojos en último día)")
        return {
            'guardar': True,
            'guardar_imagenes': True,
            'tipo_registro': 'ALERTA_TERMICA_OCR',
            'confianza': 'alta',
            'requiere_verificacion': False,
            'metodo': 'roi_temporal_rojos_dominantes',
            'nota': f'ROI temporal: {ratio_rojos*100:.1f}% píxeles rojos - Evento dentro del límite'
        }
    
    # Si 10-30% rojos → ALERTA (media confianza)
    if ratio_rojos > 0.10:
        print(f"      ✅ ALERTA_TERMICA_OCR (10-30% rojos en último día)")
        return {
            'guardar': True,
            'guardar_imagenes': True,
            'tipo_registro': 'ALERTA_TERMICA_OCR',
            'confianza': 'media',
            'requiere_verificacion': True,
            'metodo': 'roi_temporal_rojos_presentes',
            'nota': f'ROI temporal: {ratio_rojos*100:.1f}% píxeles rojos - Evento probable dentro del límite'
        }
    
    # ===== FASE 2: ESTRELLA VERDE =====
    print(f"   🎯 FASE 2 (estrella verde): Verificando posición...")
    
    if img_dist_path and os.path.exists(img_dist_path):
        try:
            img_dist = cv2.imread(img_dist_path)
            if img_dist is not None:
                img_dist_rgb = cv2.cvtColor(img_dist, cv2.COLOR_BGR2RGB)
                
                confianza_estrella, tipo_estrella, nota_estrella = validar_con_estrella_verde(
                    img_dist_rgb, volcan_nombre
                )
                
                if confianza_estrella is not None:
                    guardar = tipo_estrella == 'ALERTA_TERMICA_OCR'
                    
                    print(f"      {'✅' if guardar else '❌'} {tipo_estrella}: {nota_estrella}")
                    
                    return {
                        'guardar': guardar,
                        'guardar_imagenes': guardar,
                        'tipo_registro': tipo_estrella,
                        'confianza': confianza_estrella,
                        'requiere_verificacion': confianza_estrella != 'alta',
                        'metodo': 'estrella_verde_v16',
                        'nota': nota_estrella
                    }
        except Exception as e:
            print(f"      ⚠️ Error en FASE 2: {e}")
    
    # ===== FASE 3: PÍXELES NEGROS (FALLBACK) =====
    ratio_negros = evento.get('ratio_negros', 0)
    
    print(f"   🎯 FASE 3 (fallback): Ratio negros = {ratio_negros:.2f}")
    
    if ratio_negros > 0.70:
        print(f"      ❌ FALSO_POSITIVO_OCR (>70% negros)")
        return {
            'guardar': True,  # Guardar para auditoría
            'guardar_imagenes': False,  # NO descargar imágenes
            'tipo_registro': 'FALSO_POSITIVO_OCR',
            'confianza': 'baja',
            'requiere_verificacion': False,
            'metodo': 'roi_temporal_negros_dominantes',
            'nota': f'ROI temporal: {ratio_negros*100:.1f}% píxeles negros - Sin señal clara de evento térmico'
        }
    
    # Sin señal clara
    print(f"      ❌ Sin señal clara")
    return {
        'guardar': True,
        'guardar_imagenes': False,
        'tipo_registro': 'FALSO_POSITIVO_OCR',
        'confianza': 'baja',
        'requiere_verificacion': False,
        'metodo': 'sin_senal_clara',
        'nota': 'No se detectaron píxeles rojos ni estrella verde en ROI temporal'
    }


def verificar_evento_no_existe(evento, volcan_nombre, sensor, df_consolidado, df_ocr):
    """Verifica que evento NO exista en CSVs"""
    ts = evento['timestamp']
    
    # Verificar en consolidado (latest.php)
    if not df_consolidado.empty:
        existe_consolidado = df_consolidado[
            (df_consolidado['timestamp'] == ts) &
            (df_consolidado['Volcan'] == volcan_nombre) &
            (df_consolidado['Sensor'] == sensor)
        ]
        
        if not existe_consolidado.empty:
            print(f"      ❌ DUPLICADO: Ya existe en latest.php")
            return False
    
    # Verificar en OCR
    if not df_ocr.empty:
        existe_ocr = df_ocr[
            (df_ocr['timestamp'] == ts) &
            (df_ocr['Volcan'] == volcan_nombre) &
            (df_ocr['Sensor'] == sensor)
        ]
        
        if not existe_ocr.empty:
            print(f"      ❌ DUPLICADO: Ya existe en OCR")
            return False
    
    # Es nuevo
    print(f"      ✅ RESULTADO: ES NUEVO (no es duplicado)")
    return True


# ========================================
# TEST
# ========================================
if __name__ == "__main__":
    print("="*70)
    print("TEST: OCR UTILS V17")
    print("  - ROI temporal restaurado")
    print("  - Estrella verde V16")
    print("  - Tupungatito agregado")
    print("="*70)
    
    volcanes = list(LIMITES_Y_COORDENADAS.keys())
    print(f"\n✅ Volcanes configurados: {len(volcanes)}")
    for v in volcanes:
        print(f"   - {v}: {LIMITES_Y_COORDENADAS[v]['LIMITE_KM']} km")
    
    print(f"\n✅ ROI temporal configurado:")
    print(f"   X: {ROI_CONFIG['x_start_pct']:.4f} - {ROI_CONFIG['x_end_pct']:.4f}")
    print(f"   Y: {ROI_CONFIG['y_start_pct']:.4f} - {ROI_CONFIG['y_end_pct']:.4f}")
    
    # Calcular coordenadas absolutas
    width, height = 850, 600
    roi_x1 = int(width * ROI_CONFIG['x_start_pct'])
    roi_x2 = int(width * ROI_CONFIG['x_end_pct'])
    roi_y1 = int(height * ROI_CONFIG['y_start_pct'])
    roi_y2 = int(height * ROI_CONFIG['y_end_pct'])
    
    area_roi = (roi_x2 - roi_x1) * (roi_y2 - roi_y1)
    area_total = width * height
    
    print(f"\n✅ Coordenadas absolutas (850x600):")
    print(f"   X: {roi_x1} - {roi_x2} ({roi_x2 - roi_x1} px)")
    print(f"   Y: {roi_y1} - {roi_y2} ({roi_y2 - roi_y1} px)")
    print(f"   Área: {area_roi:,} px² ({(area_roi/area_total)*100:.2f}% del total)")
    print(f"   Reducción: {100 - (area_roi/area_total)*100:.2f}%")
    
    print("\n" + "="*70)
    print("✅ OCR UTILS V17 LISTO")
    print("="*70)

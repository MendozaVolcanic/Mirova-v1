"""
OCR UTILS V19 - DETECCIÓN GRUPOS PÍXELES + TODAS FUNCIONALIDADES V17

CAMBIOS V19:
5. **NUEVO V19:** Detección grupos píxeles rojos separados (eventos superpuestos)
6. **PRESERVA V17:** ROI temporal, Sistema 3 fases, 11 volcanes, Filtro estrella
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


# ========================================
# NUEVAS FUNCIONES V19: DETECCIÓN GRUPOS PÍXELES ROJOS
# ========================================

def detectar_grupos_pixeles_rojos(roi, umbral_area_minima=20):
    """
    V19: Detecta grupos separados de píxeles rojos en ROI
    Útil para eventos superpuestos (ej: Lastarria 05:42 + 06:06, Tupungatito 04:48 + 05:12 + 06:30)
    
    Args:
        roi: ROI de imagen (numpy array RGB)
        umbral_area_minima: Área mínima en píxeles para considerar grupo válido
    
    Returns:
        list: [{'centro_y': int, 'area': int, 'bbox': tuple}, ...]
              Ordenados por Y (grupos arriba primero)
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
    """
    V19: Asocia cada grupo de píxeles rojos a su evento correspondiente
    
    Estrategia:
    - Si 1 grupo + 1 evento → Asociación directa
    - Si múltiples grupos → Asociar por índice (grupo[i] → evento[i])
    
    Args:
        eventos: Lista de eventos extraídos de Latest10NTI
        grupos: Lista de grupos detectados en ROI
        roi_y_start: Coordenada Y inicial del ROI en imagen completa
    
    Returns:
        dict: {evento_index: grupo_info con y_absoluto}
    """
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


def analizar_puntos_distancia(eventos, img_dist_path, volcan_nombre):
    """
    V19: Detecta grupos de píxeles rojos y asocia a eventos individuales
    PRESERVA V17: ROI temporal (x: 0.8424-0.8635, y: 0.1817-0.4933)
    
    MEJORAS V19:
    - Detecta grupos separados de píxeles rojos
    - Asocia cada grupo a su evento correspondiente
    - Calcula datos POR EVENTO individual (y_absoluto, área)
    
    COMPATIBILIDAD V17:
    - Mantiene análisis global (ratio_rojos, ratio_negros)
    - Funciona igual para casos con 1 evento
    """
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
        
        # ========================================
        # ROI TEMPORAL (PRESERVADO V17)
        # ========================================
        roi_x_start = int(width * ROI_CONFIG['x_start_pct'])
        roi_x_end = int(width * ROI_CONFIG['x_end_pct'])
        roi_y_start = int(height * ROI_CONFIG['y_start_pct'])
        roi_y_end = int(height * ROI_CONFIG['y_end_pct'])
        
        roi = img_rgb[roi_y_start:roi_y_end, roi_x_start:roi_x_end]
        
        print(f"\n🎯 V19 - Analizando píxeles con ROI TEMPORAL + GRUPOS")
        print(f"   📍 ROI temporal: X={roi_x_start}-{roi_x_end}, Y={roi_y_start}-{roi_y_end}")
        print(f"   📏 Tamaño ROI: {roi.shape[1]}x{roi.shape[0]} = {roi.shape[0]*roi.shape[1]} px²")
        
        # ========================================
        # NUEVO V19: Detectar grupos separados
        # ========================================
        grupos = detectar_grupos_pixeles_rojos(roi)
        
        print(f"   🔴 Grupos detectados: {len(grupos)}")
        for i, grupo in enumerate(grupos, 1):
            y_abs = roi_y_start + grupo['centro_y']
            print(f"      Grupo {i}: Y_relativo={grupo['centro_y']}, Y_absoluto={y_abs}, área={grupo['area']} px²")
        
        # Asociar grupos a eventos
        asociaciones = asociar_grupos_a_eventos(eventos, grupos, roi_y_start)
        
        # ========================================
        # PRESERVADO V17: Análisis global de píxeles
        # ========================================
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
        print(f"   📊 Ratio R/N: {ratio_rojos:.2f}")
        
        # Clasificación global (PRESERVADO V17)
        if ratio_rojos > 0.10:
            color_dominante = "rojo"
        elif ratio_negros > 0.70:
            color_dominante = "negro"
        else:
            color_dominante = "mixto"
        
        print(f"   🎯 Clasificación ROI global: {color_dominante}")
        
        # ========================================
        # Agregar datos a eventos
        # ========================================
        for i, evento in enumerate(eventos):
            # Datos globales (COMPATIBILIDAD V17)
            evento['color_punto'] = color_dominante
            evento['pixeles_rojos'] = int(pixeles_rojos)
            evento['pixeles_negros'] = int(pixeles_negros)
            evento['pixeles_verdes'] = int(pixeles_verdes)
            evento['ratio_rojos'] = float(ratio_rojos)
            evento['ratio_negros'] = float(ratio_negros)
            evento['metodo'] = 'roi_temporal_v19'
            
            # Datos por grupo (NUEVO V19)
            if i in asociaciones:
                evento['grupo_pixeles'] = asociaciones[i]
                print(f"   ✅ Evento {i+1} asociado a grupo Y={asociaciones[i]['centro_y']} ({asociaciones[i]['area']} px²)")
            else:
                evento['grupo_pixeles'] = None
                if len(grupos) > 0:
                    print(f"   ⚠️ Evento {i+1} sin grupo asociado")
        
        return eventos
    
    except Exception as e:
        print(f"   ❌ ERROR en analizar_puntos_distancia V19: {e}")
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
    V19: Valida GRUPOS de píxeles individuales antes de validar con estrella
    
    SISTEMA 3 FASES (mejorado V19):
    FASE 1: Píxeles rojos en ROI temporal → NUEVO: Validación por GRUPO individual
    FASE 2: Estrella verde (V16 - PRESERVADO)
    FASE 3: Píxeles negros (V17 - PRESERVADO)
    """
    vrp_mw = evento.get('VRP_MW', 0)
    
    # Validar VRP
    if vrp_mw == 0 or np.isnan(vrp_mw) or vrp_mw is None:
        return {
            'guardar': False,
            'guardar_imagenes': False,
            'tipo_registro': 'VRP_INVALIDO',
            'confianza': 'invalido',
            'Color_Punto': 'sin_punto',
            'Nota': f'VRP inválido: {vrp_mw}'
        }
    
    # ========================================
    # FASE 1 V19 (MEJORADA): Validar con grupo individual
    # ========================================
    grupo_info = evento.get('grupo_pixeles')
    
    if grupo_info:
        y_absoluto = grupo_info['y_absoluto']
        area_grupo = grupo_info['area']
        
        limites = LIMITES_Y_COORDENADAS.get(volcan_nombre, {})
        y_limite_px = limites.get('Y_LIMITE_PX', 257)
        y_eje_x = limites.get('Y_EJE_X_PX', 335)
        limite_km = limites.get('LIMITE_KM', 5.0)
        
        if y_absoluto >= y_limite_px:
            # DENTRO del límite - VRP REAL
            distancia_aprox = ((y_absoluto - y_limite_px) / (y_eje_x - y_limite_px)) * limite_km
            
            print(f"   ═════════════════════════════════════════════════════════")
            print(f"   🎯 FASE 1 V19 (grupo individual): Y={y_absoluto} >= {y_limite_px} ✅")
            print(f"      ✅ ALERTA_TERMICA_OCR: Grupo píxeles en Y={y_absoluto}")
            print(f"         Área={area_grupo} px², dist≈{distancia_aprox:.2f} km")
            
            return {
                'guardar': True,
                'guardar_imagenes': True,
                'tipo_registro': 'ALERTA_TERMICA_OCR',
                'confianza': 'alta',
                'Color_Punto': 'sin_punto',
                'Metodo_Deteccion': 'grupo_pixeles_v19',
                'Nota': f'Grupo píxeles rojos Y={y_absoluto} (área={area_grupo} px², dist≈{distancia_aprox:.2f} km)'
            }
        else:
            # FUERA del límite - FALSO POSITIVO
            print(f"   ═════════════════════════════════════════════════════════")
            print(f"   🎯 FASE 1 V19 (grupo individual): Y={y_absoluto} < {y_limite_px} ❌")
            print(f"      ❌ FALSO_POSITIVO: Grupo fuera límite")
            
            return {
                'guardar': False,
                'guardar_imagenes': False,
                'tipo_registro': 'FALSO_POSITIVO_OCR',
                'confianza': 'baja',
                'Color_Punto': 'sin_punto',
                'Nota': f'Grupo fuera límite: Y={y_absoluto} < {y_limite_px}'
            }
    
    # ========================================
    # FASE 2 (PRESERVADA V16): Estrella verde
    # ========================================
    print(f"   ═════════════════════════════════════════════════════════")
    print(f"   🎯 FASE 1: Sin grupo individual → Continuando FASE 2 (estrella)")
    
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
    
    # ========================================
    # FASE 3 (PRESERVADA V17): Píxeles negros
    # ========================================
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
    
    # Sin señal clara - FALSO POSITIVO
    return {
        'guardar': False,
        'guardar_imagenes': False,
        'tipo_registro': 'FALSO_POSITIVO_OCR',
        'confianza': 'baja',
        'Color_Punto': evento.get('Color_Punto', 'mixto'),
        'Nota': 'Sin grupo ni estrella clara'
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

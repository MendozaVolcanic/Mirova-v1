"""
OCR UTILS V10 - FUSIÓN DEFINITIVA
Combina lo mejor de:
- V22-Ene: ROI temporal + análisis densidad píxeles
- V6: Validación NaN robusta
- V9: Pareo fechas/VRP separado + Fix Last Update
- V5: Clasificación estrella verde

FILOSOFÍA: Precisión > Cobertura
- Solo analiza ÚLTIMAS 24H (ROI temporal 84.24%-86.35%)
- Eventos fuera de ROI = sin_punto = FALSO_POSITIVO
"""

import cv2
import numpy as np
import pytesseract
from datetime import datetime
import pytz
import re
from PIL import Image

# ========================================
# COORDENADAS DE LÍMITES (desde Photoshop)
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
    'PuyehueCordonCaulle': {'Y_LIMITE_PX': 148, 'Y_EJE_X_PX': 335, 'LIMITE_KM': 20.0}
}

# ========================================
# ROI TEMPORAL - CRÍTICO (de V22-Ene)
# ========================================
ROI_CONFIG = {
    'x_start_pct': 0.8424,  # 84.24% - SOLO ÚLTIMAS 24H
    'x_end_pct': 0.8635,    # 86.35%
    'y_start_pct': 0.1817,  # 18.17%
    'y_end_pct': 0.4933     # 49.33%
}

# JUSTIFICACIÓN:
# - Máxima precisión temporal (sin mezcla de días)
# - Desde 22-Ene-2026: alta confiabilidad
# - Eventos antiguos quedarán "sin_punto" (esperado)
# - Ideal para monitoreo en tiempo real


# ========================================
# EXTRACCIÓN OCR (Fusión V9 + V6)
# ========================================

def extraer_eventos_latest10nti(img_path):
    """
    V10: Fusión de V9 (pareo fechas/VRP) + V6 (validación NaN)
    
    Extrae eventos de Latest10NTI.png usando OCR
    
    Mejoras:
    - Pareo de fechas y VRP por separado (V9)
    - Filtro "Last Update" mejorado (V9)
    - Validación NaN robusta (V6)
    - Logs detallados para debug
    
    Args:
        img_path: Path a Latest10NTI.png
    
    Returns:
        list: Lista de eventos [{timestamp, datetime, vrp_mw}, ...]
    """
    print(f"\n🔍 OCR V10 - Procesando: {img_path}")
    
    try:
        img = Image.open(img_path)
        img_array = np.array(img)
        print(f"   ✅ Imagen cargada: {img_array.shape}")
        
        # OCR con múltiples configuraciones
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
        
        # ===== PASO 1: Extraer TODAS las fechas (excepto Last Update) =====
        patron_fechas = r'(\d{2}-[A-Za-z]{3}-\d{4}\s+\d{2}:\d{2}:\d{2})'
        
        fechas = []
        for match in re.finditer(patron_fechas, texto):
            fecha_str = match.group(1)
            
            # Saltar si está justo después de "Last Update"
            start_pos = match.start()
            texto_antes = texto[max(0, start_pos-20):start_pos]
            
            if 'Last Update' in texto_antes or 'update' in texto_antes.lower():
                print(f"   ⏭️ Saltando fecha después de 'Last Update': {fecha_str}")
                continue
            
            fechas.append(fecha_str)
        
        print(f"\n📅 FECHAS EXTRAÍDAS: {len(fechas)}")
        
        # ===== PASO 2: Extraer TODOS los VRP =====
        patron_vrp = r'VRP\s*=?\s*([\d.]+|NaN)\s*MW'
        
        vrps = []
        for match in re.finditer(patron_vrp, texto, re.IGNORECASE):
            vrp_str = match.group(1)
            vrps.append(vrp_str)
        
        print(f"🔥 VRP EXTRAÍDOS: {len(vrps)}")
        
        # ===== PASO 3: Emparejar fechas con VRP =====
        if len(fechas) != len(vrps):
            print(f"   ⚠️ Cantidad diferente: {len(fechas)} fechas vs {len(vrps)} VRP")
            n_eventos = min(len(fechas), len(vrps))
        else:
            n_eventos = len(fechas)
            print(f"   ✅ Cantidades coinciden: {n_eventos} eventos")
        
        eventos = []
        
        for i in range(n_eventos):
            fecha_str = fechas[i]
            vrp_str = vrps[i]
            
            # ===== Validación VRP (de V6) =====
            
            # 1. Descartar NaN
            if 'nan' in vrp_str.lower() or any(c.isalpha() for c in vrp_str):
                continue
            
            # 2. Convertir a float
            try:
                vrp_mw = float(vrp_str)
            except ValueError:
                continue
            
            # 3. Validar rango
            if vrp_mw < 0.01 or vrp_mw > 1000:
                continue
            
            # 4. Parsear fecha
            try:
                dt_utc = datetime.strptime(fecha_str, "%d-%b-%Y %H:%M:%S")
                dt_utc = dt_utc.replace(tzinfo=pytz.utc)
            except Exception:
                continue
            
            eventos.append({
                'timestamp': int(dt_utc.timestamp()),
                'datetime': dt_utc,
                'vrp_mw': vrp_mw
            })
        
        print(f"\n📊 RESULTADO: {len(eventos)} eventos válidos\n")
        
        return eventos
    
    except Exception as e:
        print(f"❌ ERROR en OCR: {e}")
        return []


# ========================================
# ANÁLISIS ROI (de V22-Ene)
# ========================================

def analizar_puntos_distancia(img_dist_path, eventos):
    """
    V10: Análisis completo con ROI temporal de V22-Ene
    
    Analiza Dist.png con ROI de ÚLTIMAS 24H
    
    Funcionalidades:
    - ROI temporal específico (84.24%-86.35%)
    - Detección estrella verde (última detección)
    - Densidad píxeles rojos (evento dentro)
    - Densidad píxeles negros (evento fuera)
    - Clasificación 3 fases
    
    Args:
        img_dist_path: Path a Dist.png
        eventos: Lista de eventos extraídos por OCR
    
    Returns:
        list: Eventos con campos agregados:
            - color_punto: 'rojo'/'negro'/'mezcla'/'sin_punto'
            - metodo: método de clasificación usado
            - pixeles_rojos, pixeles_negros: conteo
    """
    try:
        img_dist = cv2.imread(img_dist_path)
        if img_dist is None:
            print(f"   ❌ No se pudo cargar Dist.png")
            for evento in eventos:
                evento['color_punto'] = 'sin_punto'
                evento['metodo'] = 'sin_imagen'
            return eventos
        
        img_rgb = cv2.cvtColor(img_dist, cv2.COLOR_BGR2RGB)
        height, width = img_rgb.shape[:2]
        
        # ===== Extraer ROI TEMPORAL (CRÍTICO) =====
        roi_x_start = int(width * ROI_CONFIG['x_start_pct'])
        roi_x_end = int(width * ROI_CONFIG['x_end_pct'])
        roi_y_start = int(height * ROI_CONFIG['y_start_pct'])
        roi_y_end = int(height * ROI_CONFIG['y_end_pct'])
        
        roi = img_rgb[roi_y_start:roi_y_end, roi_x_start:roi_x_end]
        
        print(f"   🔍 ROI temporal: {roi.shape} (últimas 24h)")
        
        # ===== PASO 1: Detectar estrella verde =====
        mask_verde = (roi[:, :, 1] > 150) & \
                     ((roi[:, :, 1] - roi[:, :, 0]) > 50) & \
                     ((roi[:, :, 1] - roi[:, :, 2]) > 50)
        num_verdes = np.sum(mask_verde)
        tiene_estrella = num_verdes >= 50
        
        # ===== PASO 2: Detectar rojos (EXCLUIR verdes) =====
        mask_rojo = (roi[:, :, 0] > 150) & \
                    ((roi[:, :, 0] - roi[:, :, 1]) > 50) & \
                    ((roi[:, :, 0] - roi[:, :, 2]) > 50) & \
                    ~mask_verde
        num_rojos = np.sum(mask_rojo)
        
        # ===== PASO 3: Detectar negros (EXCLUIR verdes) =====
        mask_negro = (roi[:, :, 0] < 100) & \
                     (roi[:, :, 1] < 100) & \
                     (roi[:, :, 2] < 100) & \
                     ~mask_verde
        num_negros = np.sum(mask_negro)
        
        print(f"   🟢 Estrella: {num_verdes} px ({'SÍ' if tiene_estrella else 'NO'})")
        print(f"   🔴 Rojos: {num_rojos} px")
        print(f"   ⚫ Negros: {num_negros} px")
        
        # ===== PASO 4: Clasificar según densidad =====
        UMBRAL_PIXELES = 10
        
        tiene_rojos = num_rojos >= UMBRAL_PIXELES
        tiene_negros = num_negros >= UMBRAL_PIXELES
        
        # Con estrella: usar RATIO
        if tiene_estrella and (num_rojos > 0 or num_negros > 0):
            ratio = num_rojos / max(num_negros, 1)
            print(f"   📊 Ratio R/N: {ratio:.2f}")
            
            if ratio > 2.0:
                color_final = 'rojo'
                metodo_final = 'rojo_dominante_con_estrella'
                print(f"   ✅ Rojo dominante → REAL")
            elif ratio < 0.5:
                color_final = 'negro'
                metodo_final = 'negro_dominante_con_estrella'
                print(f"   ❌ Negro dominante → FALSO")
            else:
                color_final = 'mezcla'
                metodo_final = 'mezcla_con_estrella'
                print(f"   ⚠️ Mezcla → REVISAR")
        else:
            # Sin estrella: lógica de densidad pura
            if not tiene_rojos and not tiene_negros:
                color_final = 'sin_punto'
                metodo_final = 'sin_pixeles_roi'
            elif tiene_rojos and not tiene_negros:
                color_final = 'rojo'
                metodo_final = 'solo_rojos_densidad'
            elif tiene_negros and not tiene_rojos:
                color_final = 'negro'
                metodo_final = 'solo_negros_densidad'
            else:
                color_final = 'mezcla'
                metodo_final = 'mezcla_densidad'
        
        print(f"   🎯 Clasificación: {color_final}\n")
        
        # Aplicar a todos los eventos
        for evento in eventos:
            evento['color_punto'] = color_final
            evento['metodo'] = metodo_final
            evento['pixeles_rojos'] = int(num_rojos)
            evento['pixeles_negros'] = int(num_negros)
        
        return eventos
    
    except Exception as e:
        print(f"   ❌ Error analizando Dist.png: {e}")
        for evento in eventos:
            evento['color_punto'] = 'sin_punto'
            evento['metodo'] = 'error_analisis'
        return eventos


# ========================================
# CLASIFICACIÓN (de V22-Ene)
# ========================================

def clasificar_confianza(evento):
    """
    V10: Clasificación completa de V22-Ene
    
    Clasifica confianza según análisis de píxeles
    
    Filosofía "Precisión > Cobertura":
    - sin_punto = FALSO_POSITIVO (evento fuera de ventana temporal)
    - solo rojos = ALERTA_TERMICA (guardar imágenes)
    - solo negros = FALSO_POSITIVO (evento fuera de límite)
    - mezcla = ALERTA_TERMICA + requiere_verificacion
    
    Args:
        evento: Dict con color_punto, metodo, vrp_mw
    
    Returns:
        dict: {tipo_registro, confianza, guardar, guardar_imagenes, ...}
    """
    color = evento.get('color_punto', 'sin_punto')
    metodo = evento.get('metodo', '')
    vrp_mw = evento.get('vrp_mw', 0)
    pixeles_rojos = evento.get('pixeles_rojos', 0)
    pixeles_negros = evento.get('pixeles_negros', 0)
    
    # REGLA 1: VRP inválido
    if np.isnan(vrp_mw) or vrp_mw <= 0:
        return {
            'tipo_registro': None,
            'confianza': 'invalido',
            'requiere_verificacion': False,
            'nota': 'VRP inválido o cero',
            'guardar': False,
            'guardar_imagenes': False
        }
    
    # REGLA 2: sin_punto = fuera de ventana temporal
    if color == 'sin_punto':
        return {
            'tipo_registro': 'FALSO_POSITIVO_OCR',
            'confianza': 'alta',
            'requiere_verificacion': False,
            'nota': 'Sin píxeles en ROI - Evento fuera de ventana temporal',
            'guardar': True,
            'guardar_imagenes': False
        }
    
    # REGLA 3: Rojo dominante = REAL
    if color == 'rojo':
        if pixeles_rojos > 100:
            return {
                'tipo_registro': 'ALERTA_TERMICA_OCR',
                'confianza': 'alta',
                'requiere_verificacion': False,
                'nota': 'Píxeles rojos dominantes en ROI - Evento real',
                'guardar': True,
                'guardar_imagenes': True
            }
        else:
            return {
                'tipo_registro': 'ALERTA_TERMICA_OCR',
                'confianza': 'media',
                'requiere_verificacion': True,
                'nota': f'Píxeles rojos bajos ({pixeles_rojos}) - Verificar',
                'guardar': True,
                'guardar_imagenes': True
            }
    
    # REGLA 4: Negro dominante = FUERA de límite
    if color == 'negro':
        return {
            'tipo_registro': 'FALSO_POSITIVO_OCR',
            'confianza': 'alta',
            'requiere_verificacion': False,
            'nota': 'Píxeles negros dominantes - Fuera de límite distancia',
            'guardar': True,
            'guardar_imagenes': False
        }
    
    # REGLA 5: Mezcla = ZONA LÍMITE (requiere revisión)
    if color == 'mezcla':
        return {
            'tipo_registro': 'ALERTA_TERMICA_OCR',
            'confianza': 'media',
            'requiere_verificacion': True,
            'nota': f'Mezcla rojos/negros - Evento en zona límite (VRP={vrp_mw} MW)',
            'guardar': True,
            'guardar_imagenes': True
        }
    
    # Fallback
    return {
        'tipo_registro': 'FALSO_POSITIVO_OCR',
        'confianza': 'baja',
        'requiere_verificacion': False,
        'nota': 'Caso no clasificado',
        'guardar': True,
        'guardar_imagenes': False
    }


def verificar_evento_no_existe(evento, volcan_nombre, sensor, df_consolidado, df_ocr):
    """
    Verifica que el evento NO exista ya en los CSVs
    
    Args:
        evento: Dict con timestamp
        volcan_nombre: Nombre del volcán
        sensor: MODIS, VIIRS375, VIIRS, VIIRS750
        df_consolidado: DataFrame de latest.php
        df_ocr: DataFrame de OCR
    
    Returns:
        bool: True si NO existe (es nuevo), False si ya existe
    """
    ts = evento['timestamp']
    
    if not df_consolidado.empty:
        existe = (
            (df_consolidado['timestamp'] == ts) &
            (df_consolidado['Volcan'] == volcan_nombre) &
            (df_consolidado['Sensor'] == sensor)
        ).any()
        
        if existe:
            return False
    
    if not df_ocr.empty:
        existe = (
            (df_ocr['timestamp'] == ts) &
            (df_ocr['Volcan'] == volcan_nombre) &
            (df_ocr['Sensor'] == sensor)
        ).any()
        
        if existe:
            return False
    
    return True


# ========================================
# FUNCIONES ESTRELLA VERDE (de V31-Ene / V5)
# ========================================
# Mantenidas por compatibilidad con otros scripts

def analizar_pixeles_rojos(roi):
    if roi is None or roi.size == 0:
        return None, None
    
    mask_rojos = cv2.inRange(roi, (200, 0, 0), (255, 50, 50))
    pixeles_rojos = np.sum(mask_rojos > 0)
    total_pixeles = roi.shape[0] * roi.shape[1]
    
    if total_pixeles == 0:
        return None, None
    
    porcentaje_rojos = (pixeles_rojos / total_pixeles) * 100
    
    if porcentaje_rojos > 30:
        return 'alta', 'rojo_dominante'
    elif porcentaje_rojos > 10:
        return 'media', 'rojo_presente'
    else:
        return None, None


def detectar_centro_estrella_verde(img_dist):
    if img_dist is None or img_dist.size == 0:
        return None
    
    try:
        img_hsv = cv2.cvtColor(img_dist, cv2.COLOR_RGB2HSV)
        mask_verde = cv2.inRange(img_hsv, (40, 80, 80), (80, 255, 255))
        contornos, _ = cv2.findContours(mask_verde, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contornos) == 0:
            return None
        
        contornos_validos = [c for c in contornos if cv2.contourArea(c) > 10]
        
        if len(contornos_validos) == 0:
            return None
        
        contorno_max = max(contornos_validos, key=cv2.contourArea)
        
        M = cv2.moments(contorno_max)
        if M['m00'] == 0:
            return None
        
        cy = int(M['m01'] / M['m00'])
        
        return cy
    
    except Exception as e:
        print(f"Error detectando estrella verde: {e}")
        return None


def validar_con_estrella_verde(img_dist, volcan_nombre):
    if volcan_nombre not in LIMITES_Y_COORDENADAS:
        return None, None, f"Volcán '{volcan_nombre}' sin coordenadas calibradas"
    
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
        
        nota = f"Estrella verde en Y={y_estrella} (dentro límite Y={y_limite}, dist≈{dist_km:.2f} km)"
        return 'alta', 'ALERTA_TERMICA_OCR', nota
    else:
        nota = f"Estrella verde en Y={y_estrella} (fuera límite Y={y_limite}, límite={coords['LIMITE_KM']} km)"
        return 'baja', 'FALSO_POSITIVO_OCR', nota


def clasificar_confianza_v5(img_dist_path, roi, volcan_nombre):
    confianza_rojos, metodo_rojos = analizar_pixeles_rojos(roi)
    
    if confianza_rojos == 'alta':
        return (
            'alta',
            'ALERTA_TERMICA_OCR',
            'pixeles_rojos_dominantes',
            'Píxeles rojos >30% del ROI - Evento dentro del límite'
        )
    
    if confianza_rojos == 'media':
        return (
            'media',
            'ALERTA_TERMICA_OCR',
            'pixeles_rojos_presentes',
            'Píxeles rojos 10-30% del ROI - Evento probable dentro del límite'
        )
    
    try:
        img_dist = cv2.imread(img_dist_path)
        if img_dist is not None:
            img_dist_rgb = cv2.cvtColor(img_dist, cv2.COLOR_BGR2RGB)
            
            confianza_estrella, tipo_estrella, nota_estrella = validar_con_estrella_verde(
                img_dist_rgb, volcan_nombre
            )
            
            if confianza_estrella is not None:
                return (confianza_estrella, tipo_estrella, 'estrella_verde', nota_estrella)
    except Exception as e:
        print(f"Error en fase 2 (estrella verde): {e}")
    
    if roi is not None and roi.size > 0:
        mask_negros = cv2.inRange(roi, (0, 0, 0), (50, 50, 50))
        pixeles_negros = np.sum(mask_negros > 0)
        total_pixeles = roi.shape[0] * roi.shape[1]
        
        if total_pixeles > 0:
            porcentaje_negros = (pixeles_negros / total_pixeles) * 100
            
            if porcentaje_negros > 70:
                return (
                    'baja',
                    'FALSO_POSITIVO_OCR',
                    'pixeles_negros_dominantes',
                    f'Píxeles negros {porcentaje_negros:.1f}% - Sin señal clara de evento térmico'
                )
    
    return (
        'baja',
        'FALSO_POSITIVO_OCR',
        'sin_senal_clara',
        'No se detectaron píxeles rojos ni estrella verde'
    )

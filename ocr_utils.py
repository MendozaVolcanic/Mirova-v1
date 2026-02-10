"""
OCR UTILS V6 - FIX NaN DETECTION
Incluye:
- FIX CRÍTICO: Detecta y descarta NaN correctamente
- Funciones V5 (clasificación con estrella verde)
- Funciones antiguas (para scraper_ocr.py)
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
    'Lastarria': {
        'Y_LIMITE_PX': 272,
        'Y_EJE_X_PX': 335,
        'LIMITE_KM': 3.0
    },
    'PlanchonPeteroa': {
        'Y_LIMITE_PX': 272,
        'Y_EJE_X_PX': 335,
        'LIMITE_KM': 3.0
    },
    'Peteroa': {  # Alias
        'Y_LIMITE_PX': 272,
        'Y_EJE_X_PX': 335,
        'LIMITE_KM': 3.0
    },
    'Copahue': {
        'Y_LIMITE_PX': 266,
        'Y_EJE_X_PX': 335,
        'LIMITE_KM': 4.0
    },
    'Lascar': {
        'Y_LIMITE_PX': 257,
        'Y_EJE_X_PX': 335,
        'LIMITE_KM': 5.0
    },
    'Isluga': {
        'Y_LIMITE_PX': 257,
        'Y_EJE_X_PX': 335,
        'LIMITE_KM': 5.0
    },
    'Nevados de Chillan': {
        'Y_LIMITE_PX': 257,
        'Y_EJE_X_PX': 335,
        'LIMITE_KM': 5.0
    },
    'ChillanNevadosde': {  # Alias MIROVA
        'Y_LIMITE_PX': 257,
        'Y_EJE_X_PX': 335,
        'LIMITE_KM': 5.0
    },
    'Llaima': {
        'Y_LIMITE_PX': 257,
        'Y_EJE_X_PX': 335,
        'LIMITE_KM': 5.0
    },
    'Villarrica': {
        'Y_LIMITE_PX': 257,
        'Y_EJE_X_PX': 335,
        'LIMITE_KM': 5.0
    },
    'Chaiten': {
        'Y_LIMITE_PX': 257,
        'Y_EJE_X_PX': 335,
        'LIMITE_KM': 5.0
    },
    'Puyehue-Cordon Caulle': {
        'Y_LIMITE_PX': 148,
        'Y_EJE_X_PX': 335,
        'LIMITE_KM': 20.0
    },
    'PuyehueCordonCaulle': {  # Alias MIROVA
        'Y_LIMITE_PX': 148,
        'Y_EJE_X_PX': 335,
        'LIMITE_KM': 20.0
    }
}


# ========================================
# FUNCIONES ANTIGUAS (para scraper_ocr.py)
# ========================================

def extraer_eventos_latest10nti(img_path):
    """
    Extrae eventos de Latest10NTI.png usando OCR
    
    FIX V6: Detecta y descarta NaN correctamente
    
    Args:
        img_path: Path a Latest10NTI.png
    
    Returns:
        list: Lista de eventos [{timestamp, datetime, vrp_mw}, ...]
    """
    try:
        img = Image.open(img_path)
        img_array = np.array(img)
        
        # OCR con múltiples configuraciones
        configs = [
            r'--oem 3 --psm 6',
            r'--oem 3 --psm 4',
            r'--oem 3 --psm 11'
        ]
        
        texto = None
        for config in configs:
            texto_temp = pytesseract.image_to_string(img_array, config=config)
            if texto_temp and len(texto_temp.strip()) > 50:
                texto = texto_temp
                break
        
        if not texto:
            return []
        
        # Filtrar línea "Last Update"
        for match in re.finditer(r'Last Update.*', texto, re.IGNORECASE):
            start_pos = match.start()
            # Solo tomar texto ANTES de "Last Update"
            texto = texto[:start_pos]
            break
        
        # ===== FIX V6: Patrón mejorado para capturar VRP =====
        # Busca explícitamente "VRP = X MW" o "VRP =X MW"
        # Evita capturar líneas sin "VRP" o sin "MW"
        patron = r'(\d{2}-[A-Za-z]{3}-\d{4}\s+\d{2}:\d{2}:\d{2})\s+.*?VRP\s*=?\s*([\d.]+)\s*MW'
        
        eventos = []
        for match in re.finditer(patron, texto, re.IGNORECASE):
            try:
                fecha_str = match.group(1)
                vrp_str = match.group(2)
                
                # ===== FIX V6: Validaciones de VRP =====
                
                # 1. Descartar si contiene letras (NaN, nan, N/A, etc.)
                if any(c.isalpha() for c in vrp_str):
                    print(f"   ⚠️ SKIP: VRP inválido '{vrp_str}' (contiene letras)")
                    continue
                
                # 2. Validar que sea numérico válido
                try:
                    vrp_mw = float(vrp_str)
                except ValueError:
                    print(f"   ⚠️ SKIP: VRP no numérico '{vrp_str}'")
                    continue
                
                # 3. Validar rango razonable (0.01 - 1000 MW)
                if vrp_mw < 0.01:
                    print(f"   ⚠️ SKIP: VRP demasiado bajo {vrp_mw} MW")
                    continue
                
                if vrp_mw > 1000:
                    print(f"   ⚠️ SKIP: VRP sospechosamente alto {vrp_mw} MW")
                    continue
                
                # Parsear fecha
                dt_utc = datetime.strptime(fecha_str, "%d-%b-%Y %H:%M:%S")
                dt_utc = dt_utc.replace(tzinfo=pytz.utc)
                
                eventos.append({
                    'timestamp': int(dt_utc.timestamp()),
                    'datetime': dt_utc,
                    'vrp_mw': vrp_mw
                })
                
            except Exception as e:
                print(f"   ❌ Error parseando evento: {e}")
                continue
        
        return eventos
    
    except Exception as e:
        print(f"❌ Error en OCR: {e}")
        return []


def analizar_puntos_distancia(img_dist_path, eventos):
    """
    Analiza píxeles en Dist.png para validar eventos
    
    Args:
        img_dist_path: Path a Dist.png
        eventos: Lista de eventos extraídos por OCR
    
    Returns:
        list: Eventos con campo 'color_punto' agregado
    """
    try:
        img_dist = cv2.imread(img_dist_path)
        if img_dist is None:
            return eventos
        
        img_dist_rgb = cv2.cvtColor(img_dist, cv2.COLOR_BGR2RGB)
        
        # ROI para análisis (últimas 24 horas del gráfico)
        h, w = img_dist_rgb.shape[:2]
        
        # ROI genérico
        roi_x = int(w * 0.7)
        roi_y = int(h * 0.3)
        roi_w = int(w * 0.25)
        roi_h = int(h * 0.5)
        
        roi = img_dist_rgb[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
        
        # Contar píxeles por color
        # Filtrar verde (estrella, puede confundir)
        mask_verde = cv2.inRange(roi, (0, 100, 0), (100, 255, 100))
        pixeles_verde = np.sum(mask_verde > 0)
        
        # Rojos (evento dentro)
        mask_rojos = cv2.inRange(roi, (200, 0, 0), (255, 50, 50))
        pixeles_rojos = np.sum(mask_rojos > 0)
        
        # Negros (evento fuera)
        mask_negros = cv2.inRange(roi, (0, 0, 0), (50, 50, 50))
        pixeles_negros = np.sum(mask_negros > 0)
        
        # Determinar color dominante
        if pixeles_rojos > pixeles_negros and pixeles_rojos > 10:
            color = 'rojo'
        elif pixeles_negros > pixeles_rojos and pixeles_negros > 10:
            color = 'negro'
        elif pixeles_verde > 10:
            color = 'verde'
        else:
            color = 'sin_punto'
        
        # Agregar a todos los eventos
        for evento in eventos:
            evento['color_punto'] = color
            evento['pixeles_rojos'] = int(pixeles_rojos)
            evento['pixeles_negros'] = int(pixeles_negros)
            evento['metodo'] = 'rgb_analysis'
        
        return eventos
    
    except Exception as e:
        print(f"❌ Error analizando Dist.png: {e}")
        return eventos


def clasificar_confianza(evento):
    """
    Clasifica confianza de un evento OCR
    
    Args:
        evento: Dict con campos color_punto, pixeles_rojos, pixeles_negros, vrp_mw
    
    Returns:
        dict: {confianza, tipo_registro, guardar, guardar_imagenes, requiere_verificacion, nota}
    """
    color = evento.get('color_punto', 'sin_punto')
    pixeles_rojos = evento.get('pixeles_rojos', 0)
    pixeles_negros = evento.get('pixeles_negros', 0)
    vrp_mw = evento.get('vrp_mw', 0)
    
    # Sin VRP = no es evento
    if vrp_mw <= 0:
        return {
            'confianza': 'invalido',
            'tipo_registro': 'FALSO_POSITIVO_OCR',
            'guardar': False,
            'guardar_imagenes': False,
            'requiere_verificacion': False,
            'nota': 'VRP = 0, no es evento térmico'
        }
    
    # Color rojo = alta confianza
    if color == 'rojo' or pixeles_rojos > 30:
        return {
            'confianza': 'alta',
            'tipo_registro': 'ALERTA_TERMICA_OCR',
            'guardar': True,
            'guardar_imagenes': True,
            'requiere_verificacion': False,
            'nota': 'Píxeles rojos dominantes - Evento dentro del límite'
        }
    
    # Mezcla equilibrada = media confianza
    if pixeles_rojos > 0 and pixeles_negros > 0:
        ratio = pixeles_rojos / max(pixeles_negros, 1)
        if ratio > 0.5:
            return {
                'confianza': 'media',
                'tipo_registro': 'ALERTA_TERMICA_OCR',
                'guardar': True,
                'guardar_imagenes': True,
                'requiere_verificacion': True,
                'nota': f'Mezcla rojos/negros (ratio {ratio:.2f}) - Requiere verificación'
            }
    
    # Negro dominante = falso positivo
    if color == 'negro' or pixeles_negros > 70:
        return {
            'confianza': 'baja',
            'tipo_registro': 'FALSO_POSITIVO_OCR',
            'guardar': True,
            'guardar_imagenes': False,
            'requiere_verificacion': False,
            'nota': 'Píxeles negros dominantes - Evento fuera del límite'
        }
    
    # Sin señal clara
    return {
        'confianza': 'baja',
        'tipo_registro': 'FALSO_POSITIVO_OCR',
        'guardar': True,
        'guardar_imagenes': False,
        'requiere_verificacion': False,
        'nota': 'Sin señal clara en Dist.png'
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
    
    # Verificar en consolidado
    if not df_consolidado.empty:
        existe = (
            (df_consolidado['timestamp'] == ts) &
            (df_consolidado['Volcan'] == volcan_nombre) &
            (df_consolidado['Sensor'] == sensor)
        ).any()
        
        if existe:
            return False
    
    # Verificar en OCR
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
# FUNCIONES V5 (Estrella Verde)
# ========================================

def analizar_pixeles_rojos(roi):
    """
    Analiza píxeles rojos en ROI de Dist.png
    
    Returns:
        (confianza, metodo): ('alta'/'media'/None, str)
    """
    if roi is None or roi.size == 0:
        return None, None
    
    # Detectar píxeles rojos
    mask_rojos = cv2.inRange(roi, (200, 0, 0), (255, 50, 50))
    pixeles_rojos = np.sum(mask_rojos > 0)
    total_pixeles = roi.shape[0] * roi.shape[1]
    
    if total_pixeles == 0:
        return None, None
    
    porcentaje_rojos = (pixeles_rojos / total_pixeles) * 100
    
    # Si hay muchos píxeles rojos → DENTRO del límite
    if porcentaje_rojos > 30:
        return 'alta', 'rojo_dominante'
    elif porcentaje_rojos > 10:
        return 'media', 'rojo_presente'
    else:
        return None, None


def detectar_centro_estrella_verde(img_dist):
    """
    Detecta el centro de la estrella verde en Dist.png
    
    Args:
        img_dist: Imagen Dist.png completa (RGB)
    
    Returns:
        y_centro (int): Coordenada Y del centro de estrella
        None: Si no se detecta estrella
    """
    if img_dist is None or img_dist.size == 0:
        return None
    
    try:
        # Convertir a HSV para mejor detección de verde
        img_hsv = cv2.cvtColor(img_dist, cv2.COLOR_RGB2HSV)
        
        # Rango de verde para estrella MIROVA
        # Hue: 40-80 (verde), Saturation: 80-255, Value: 80-255
        mask_verde = cv2.inRange(img_hsv, (40, 80, 80), (80, 255, 255))
        
        # Encontrar contornos de estrella
        contornos, _ = cv2.findContours(mask_verde, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contornos) == 0:
            return None
        
        # Tomar el contorno más grande (estrella principal)
        # Filtrar contornos muy pequeños (ruido)
        contornos_validos = [c for c in contornos if cv2.contourArea(c) > 10]
        
        if len(contornos_validos) == 0:
            return None
        
        contorno_max = max(contornos_validos, key=cv2.contourArea)
        
        # Calcular centro usando momentos
        M = cv2.moments(contorno_max)
        if M['m00'] == 0:
            return None
        
        cy = int(M['m01'] / M['m00'])
        
        return cy  # Solo necesitamos Y
    
    except Exception as e:
        print(f"Error detectando estrella verde: {e}")
        return None


def validar_con_estrella_verde(img_dist, volcan_nombre):
    """
    Valida si estrella verde está dentro del límite
    
    Args:
        img_dist: Imagen Dist.png completa (RGB)
        volcan_nombre: Nombre del volcán
    
    Returns:
        (confianza, tipo_registro, nota)
    """
    # Obtener coordenadas del volcán
    if volcan_nombre not in LIMITES_Y_COORDENADAS:
        return None, None, f"Volcán '{volcan_nombre}' sin coordenadas calibradas"
    
    coords = LIMITES_Y_COORDENADAS[volcan_nombre]
    
    # Detectar centro de estrella
    y_estrella = detectar_centro_estrella_verde(img_dist)
    
    if y_estrella is None:
        return None, None, "No se detectó estrella verde"
    
    # Validar posición
    y_limite = coords['Y_LIMITE_PX']
    y_eje_x = coords['Y_EJE_X_PX']
    
    # REGLA: Si Y estrella >= Y límite → DENTRO
    # (en imágenes, mayor Y = más abajo = más cerca del cráter)
    if y_estrella >= y_limite:
        # Calcular distancia estimada
        if y_estrella >= y_eje_x:
            dist_km = 0.0  # En el eje X o debajo
        else:
            # Proporción entre límite y eje X
            proporcion = (y_eje_x - y_estrella) / (y_eje_x - y_limite)
            dist_km = proporcion * coords['LIMITE_KM']
        
        nota = f"Estrella verde en Y={y_estrella} (dentro límite Y={y_limite}, dist≈{dist_km:.2f} km)"
        return 'alta', 'ALERTA_TERMICA_OCR', nota
    else:
        # Estrella fuera del límite
        nota = f"Estrella verde en Y={y_estrella} (fuera límite Y={y_limite}, límite={coords['LIMITE_KM']} km)"
        return 'baja', 'FALSO_POSITIVO_OCR', nota


def clasificar_confianza_v5(img_dist_path, roi, volcan_nombre):
    """
    Clasificación completa en 3 fases:
    1. Píxeles rojos
    2. Estrella verde
    3. Píxeles negros (fallback)
    
    Args:
        img_dist_path: Path a imagen Dist.png
        roi: ROI extraído de Dist.png (para análisis de píxeles)
        volcan_nombre: Nombre del volcán
    
    Returns:
        (confianza, tipo_registro, metodo, nota)
    """
    
    # ===== FASE 1: Píxeles rojos =====
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
    
    # ===== FASE 2: Estrella verde =====
    # Cargar imagen completa para detectar estrella
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
    
    # ===== FASE 3: Píxeles negros (fallback) =====
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
    
    # Sin señal clara
    return (
        'baja',
        'FALSO_POSITIVO_OCR',
        'sin_senal_clara',
        'No se detectaron píxeles rojos ni estrella verde'
    )

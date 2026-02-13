"""
OCR UTILS V15 DEFINITIVO - FIX REGRESIÓN ESTRELLA VERDE
CAMBIO CRÍTICO: Agregar FASE 2 de clasificación (estrella verde en imagen completa)
que se perdió en V11-V14
"""

import cv2
import numpy as np
import pytesseract
from datetime import datetime
import pytz
import re
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
    'PuyehueCordonCaulle': {'Y_LIMITE_PX': 148, 'Y_EJE_X_PX': 335, 'LIMITE_KM': 20.0}
}

# ========================================
# ROI TEMPORAL
# ========================================
ROI_CONFIG = {
    'x_start_pct': 0.8424,
    'x_end_pct': 0.8635,
    'y_start_pct': 0.1817,
    'y_end_pct': 0.4933
}


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
        
        # ===== Emparejamiento =====
        if len(fechas) != len(vrps):
            print(f"\n   ⚠️ ADVERTENCIA: {len(fechas)} fechas vs {len(vrps)} VRP")
            n_eventos = min(len(fechas), len(vrps))
        else:
            n_eventos = len(fechas)
            print(f"\n   ✅ Cantidades coinciden: {n_eventos} eventos")
        
        eventos = []
        
        print(f"\n🔗 PROCESANDO EVENTOS:")
        
        for i in range(n_eventos):
            fecha_str = fechas[i]
            vrp_str = vrps[i]
            
            print(f"\n   📌 Evento {i+1}/{n_eventos}:")
            print(f"      Fecha: {fecha_str}")
            print(f"      VRP: {vrp_str} MW")
            
            if 'nan' in vrp_str.lower() or any(c.isalpha() for c in vrp_str):
                print(f"      ❌ SKIP: NaN o contiene letras")
                continue
            
            try:
                vrp_mw = float(vrp_str)
            except ValueError:
                print(f"      ❌ SKIP: No numérico")
                continue
            
            if vrp_mw < 0.01 or vrp_mw > 1000:
                print(f"      ❌ SKIP: Fuera de rango ({vrp_mw})")
                continue
            
            try:
                dt_utc = datetime.strptime(fecha_str, "%d-%b-%Y %H:%M:%S")
                dt_utc = dt_utc.replace(tzinfo=pytz.utc)
            except Exception as e:
                print(f"      ❌ SKIP: Error fecha: {e}")
                continue
            
            eventos.append({
                'timestamp': int(dt_utc.timestamp()),
                'datetime': dt_utc,
                'vrp_mw': vrp_mw
            })
            
            print(f"      ✅ VÁLIDO - Agregado")
        
        print(f"\n📊 RESULTADO FINAL: {len(eventos)} eventos válidos de {n_eventos} procesados\n")
        
        return eventos
    
    except Exception as e:
        print(f"❌ ERROR en OCR: {e}")
        return []


def analizar_puntos_distancia(img_dist_path, eventos):
    """V15: Análisis ROI temporal (sin cambios)"""
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
        
        # Extraer ROI temporal
        roi_x_start = int(width * ROI_CONFIG['x_start_pct'])
        roi_x_end = int(width * ROI_CONFIG['x_end_pct'])
        roi_y_start = int(height * ROI_CONFIG['y_start_pct'])
        roi_y_end = int(height * ROI_CONFIG['y_end_pct'])
        
        roi = img_rgb[roi_y_start:roi_y_end, roi_x_start:roi_x_end]
        
        print(f"   🔍 ROI temporal: {roi.shape} (últimas 24h)")
        
        # Análisis de píxeles en ROI
        mask_verde = (roi[:, :, 1] > 150) & \
                     ((roi[:, :, 1] - roi[:, :, 0]) > 50) & \
                     ((roi[:, :, 1] - roi[:, :, 2]) > 50)
        num_verdes = np.sum(mask_verde)
        tiene_estrella = num_verdes >= 50
        
        mask_rojo = (roi[:, :, 0] > 150) & \
                    ((roi[:, :, 0] - roi[:, :, 1]) > 50) & \
                    ((roi[:, :, 0] - roi[:, :, 2]) > 50) & \
                    ~mask_verde
        num_rojos = np.sum(mask_rojo)
        
        mask_negro = (roi[:, :, 0] < 100) & \
                     (roi[:, :, 1] < 100) & \
                     (roi[:, :, 2] < 100) & \
                     ~mask_verde
        num_negros = np.sum(mask_negro)
        
        print(f"   🟢 Estrella: {num_verdes} px ({'SÍ' if tiene_estrella else 'NO'})")
        print(f"   🔴 Rojos: {num_rojos} px")
        print(f"   ⚫ Negros: {num_negros} px")
        
        # Clasificación PRELIMINAR basada en ROI temporal
        UMBRAL_PIXELES = 10
        
        tiene_rojos = num_rojos >= UMBRAL_PIXELES
        tiene_negros = num_negros >= UMBRAL_PIXELES
        
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
                print(f"   ❌ Negro dominante → PENDIENTE verificación estrella")
            else:
                color_final = 'mezcla'
                metodo_final = 'mezcla_con_estrella'
                print(f"   ⚠️ Mezcla → REVISAR")
        else:
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
        
        print(f"   🎯 Clasificación ROI: {color_final}")
        
        # Agregar datos a eventos
        print(f"\n📋 CLASIFICACIÓN POR EVENTO (ROI temporal):")
        for i, evento in enumerate(eventos):
            evento['color_punto'] = color_final
            evento['metodo'] = metodo_final
            evento['pixeles_rojos'] = int(num_rojos)
            evento['pixeles_negros'] = int(num_negros)
            
            fecha_str = evento['datetime'].strftime('%d-%b %H:%M:%S')
            vrp = evento['vrp_mw']
            
            print(f"   {i+1}. {fecha_str} | {vrp} MW → {color_final}")
        
        print()
        
        return eventos
    
    except Exception as e:
        print(f"   ❌ Error analizando Dist.png: {e}")
        for evento in eventos:
            evento['color_punto'] = 'sin_punto'
            evento['metodo'] = 'error_analisis'
        return eventos


# ========================================
# FASE 2: ESTRELLA VERDE (IMAGEN COMPLETA)
# ========================================

def detectar_centro_estrella_verde(img_dist):
    """
    Detecta el centro de la estrella verde en imagen COMPLETA
    
    Returns:
        y_centro (int): Coordenada Y del centro
        None: Si no se detecta
    """
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
        print(f"   ⚠️ Error detectando estrella: {e}")
        return None


def validar_con_estrella_verde(img_dist, volcan_nombre):
    """
    V15: Valida posición Y de estrella verde en imagen COMPLETA
    
    Returns:
        (confianza, tipo_registro, nota)
    """
    if volcan_nombre not in LIMITES_Y_COORDENADAS:
        return None, None, f"Volcán '{volcan_nombre}' sin coordenadas"
    
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
    V15: CLASIFICACIÓN EN 3 FASES (RESTAURADA)
    
    FASE 1: Píxeles rojos en ROI
    FASE 2: Estrella verde en imagen completa ← NUEVO (restaurado)
    FASE 3: Píxeles negros fallback
    """
    color = evento.get('color_punto', 'sin_punto')
    vrp_mw = evento.get('vrp_mw', 0)
    pixeles_rojos = evento.get('pixeles_rojos', 0)
    pixeles_negros = evento.get('pixeles_negros', 0)
    
    if np.isnan(vrp_mw) or vrp_mw <= 0:
        return {
            'tipo_registro': None,
            'confianza': 'invalido',
            'requiere_verificacion': False,
            'nota': 'VRP inválido o cero',
            'guardar': False,
            'guardar_imagenes': False
        }
    
    if color == 'sin_punto':
        return {
            'tipo_registro': 'FALSO_POSITIVO_OCR',
            'confianza': 'alta',
            'requiere_verificacion': False,
            'nota': 'Sin píxeles en ROI - Evento fuera de ventana temporal',
            'guardar': True,
            'guardar_imagenes': False
        }
    
    # ===== FASE 1: PÍXELES ROJOS =====
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
    
    # ===== FASE 2: ESTRELLA VERDE (NUEVO) =====
    if color == 'negro':
        # Antes de marcar como FALSO, verificar estrella verde
        try:
            img_dist = cv2.imread(img_dist_path)
            if img_dist is not None:
                img_dist_rgb = cv2.cvtColor(img_dist, cv2.COLOR_BGR2RGB)
                
                confianza_estrella, tipo_estrella, nota_estrella = validar_con_estrella_verde(
                    img_dist_rgb, volcan_nombre
                )
                
                if confianza_estrella is not None:
                    print(f"      🌟 FASE 2 (estrella verde): {tipo_estrella}")
                    print(f"         {nota_estrella}")
                    
                    return {
                        'tipo_registro': tipo_estrella,
                        'confianza': confianza_estrella,
                        'requiere_verificacion': tipo_estrella == 'ALERTA_TERMICA_OCR',
                        'nota': nota_estrella,
                        'guardar': True,
                        'guardar_imagenes': tipo_estrella == 'ALERTA_TERMICA_OCR'
                    }
        except Exception as e:
            print(f"      ⚠️ Error en FASE 2: {e}")
        
        # Si FASE 2 falla, usar clasificación original
        return {
            'tipo_registro': 'FALSO_POSITIVO_OCR',
            'confianza': 'alta',
            'requiere_verificacion': False,
            'nota': 'Píxeles negros dominantes - Fuera de límite distancia',
            'guardar': True,
            'guardar_imagenes': False
        }
    
    # ===== MEZCLA =====
    if color == 'mezcla':
        return {
            'tipo_registro': 'ALERTA_TERMICA_OCR',
            'confianza': 'media',
            'requiere_verificacion': True,
            'nota': f'Mezcla rojos/negros - Evento en zona límite (VRP={vrp_mw} MW)',
            'guardar': True,
            'guardar_imagenes': True
        }
    
    return {
        'tipo_registro': 'FALSO_POSITIVO_OCR',
        'confianza': 'baja',
        'requiere_verificacion': False,
        'nota': 'Caso no clasificado',
        'guardar': True,
        'guardar_imagenes': False
    }


def verificar_evento_no_existe(evento, volcan_nombre, sensor, df_consolidado, df_ocr):
    """V14: Sin cambios (con debug)"""
    ts = evento['timestamp']
    dt = evento['datetime']
    vrp = evento['vrp_mw']
    
    print(f"\n      🐛 DEBUG V14 - VERIFICACIÓN DUPLICADOS:")
    print(f"         Buscando: ts={ts} | {dt.strftime('%d-%b %H:%M:%S')} | {vrp} MW")
    print(f"         Volcán: {volcan_nombre} | Sensor: {sensor}")
    
    # 1. Verificar en consolidado
    if not df_consolidado.empty:
        mask = (
            (df_consolidado['Volcan'] == volcan_nombre) &
            (df_consolidado['Sensor'] == sensor)
        )
        df_filtrado = df_consolidado[mask]
        
        print(f"\n         📊 CONSOLIDADO:")
        print(f"            Total eventos {volcan_nombre}: {len(df_consolidado[df_consolidado['Volcan'] == volcan_nombre])}")
        print(f"            Eventos {volcan_nombre} + {sensor}: {len(df_filtrado)}")
        
        if not df_filtrado.empty:
            timestamps_consolidado = df_filtrado['timestamp'].values.tolist()
            print(f"            Últimos 3 timestamps: {timestamps_consolidado[-3:]}")
            
            if ts in timestamps_consolidado:
                print(f"         ❌ DUPLICADO EXACTO ENCONTRADO en consolidado")
                return False
            else:
                print(f"            ✅ NO encontrado en consolidado")
        else:
            print(f"            ✅ Sin eventos de este volcán+sensor en consolidado")
    else:
        print(f"\n         📊 CONSOLIDADO: vacío")
    
    # 2. Verificar en OCR
    if not df_ocr.empty:
        mask = (
            (df_ocr['Volcan'] == volcan_nombre) &
            (df_ocr['Sensor'] == sensor)
        )
        df_filtrado = df_ocr[mask]
        
        print(f"\n         📊 OCR:")
        print(f"            Total eventos {volcan_nombre}: {len(df_ocr[df_ocr['Volcan'] == volcan_nombre])}")
        print(f"            Eventos {volcan_nombre} + {sensor}: {len(df_filtrado)}")
        
        if not df_filtrado.empty:
            timestamps_ocr = df_filtrado['timestamp'].values.tolist()
            print(f"            Últimos 3 timestamps: {timestamps_ocr[-3:]}")
            
            print(f"            Últimos 3 eventos:")
            for _, row in df_filtrado.tail(3).iterrows():
                ts_csv = row['timestamp']
                fecha_csv = row.get('Fecha_Satelite_UTC', 'N/A')
                vrp_csv = row.get('VRP_MW', 0)
                delta = ts - ts_csv
                print(f"               - {fecha_csv} | {vrp_csv} MW | ts={ts_csv} (Δ={delta}s)")
            
            if ts in timestamps_ocr:
                print(f"         ❌ DUPLICADO EXACTO ENCONTRADO en OCR")
                return False
            else:
                print(f"            ✅ NO encontrado en OCR")
        else:
            print(f"            ✅ Sin eventos de este volcán+sensor en OCR")
    else:
        print(f"\n         📊 OCR: vacío")
    
    print(f"\n         ✅ RESULTADO: ES NUEVO (no es duplicado)")
    return True


# ========================================
# FUNCIONES V5 (compatibilidad - sin cambios)
# ========================================

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


def clasificar_confianza_v5(img_dist_path, roi, volcan_nombre):
    """V5: Función de compatibilidad (no se usa en V15)"""
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

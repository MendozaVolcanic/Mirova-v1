"""
OCR UTILS V9 - FIX CRÍTICO: Emparejar fechas y VRP por separado
Problema: Las fechas y VRP están en líneas diferentes
Solución: Extraer todas las fechas, todos los VRP, emparejar por índice
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


def extraer_eventos_latest10nti(img_path):
    """
    V9: FIX CRÍTICO - Emparejar fechas y VRP por separado
    
    Problema detectado:
    - Fechas están en una línea: "12-Feb-2026 06:24:00 12-Feb-2026 05:00:01 ..."
    - VRP están en otra línea: "VRP =0.34MW VRP =1.17MW ..."
    
    Solución:
    1. Extraer TODAS las fechas
    2. Extraer TODOS los VRP
    3. Emparejar por índice (fecha[0] con VRP[0], etc.)
    4. Filtrar "Last Update" y NaN
    """
    print(f"\n🔍 DEBUG OCR V9 - Procesando: {img_path}")
    
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
            print(f"   🔧 Intentando config OCR {i+1}/3: {config}")
            texto_temp = pytesseract.image_to_string(img_array, config=config)
            
            if texto_temp and len(texto_temp.strip()) > 50:
                texto = texto_temp
                print(f"   ✅ OCR exitoso con config {i+1} (longitud: {len(texto)} caracteres)")
                break
        
        if not texto:
            print(f"   ❌ NINGUNA configuración OCR funcionó")
            return []
        
        # ===== DEBUG: Mostrar texto completo =====
        print(f"\n📄 TEXTO COMPLETO OCR:")
        print("="*80)
        print(texto)
        print("="*80)
        
        # ===== ESTRATEGIA V9: Extraer fechas y VRP por separado =====
        
        # 1. Extraer TODAS las fechas (excepto la de "Last Update")
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
        for i, f in enumerate(fechas):
            print(f"   {i}: {f}")
        
        # 2. Extraer TODOS los VRP (incluyendo NaN para emparejar correctamente)
        patron_vrp = r'VRP\s*=?\s*([\d.]+|NaN)\s*MW'
        
        vrps = []
        for match in re.finditer(patron_vrp, texto, re.IGNORECASE):
            vrp_str = match.group(1)
            vrps.append(vrp_str)
        
        print(f"\n🔥 VRP EXTRAÍDOS: {len(vrps)}")
        for i, v in enumerate(vrps):
            print(f"   {i}: {v}")
        
        # 3. Verificar que haya igual cantidad
        if len(fechas) != len(vrps):
            print(f"\n   ⚠️ ADVERTENCIA: Cantidad diferente de fechas ({len(fechas)}) vs VRP ({len(vrps)})")
            print(f"   💡 Usando el mínimo para emparejar")
            
            # Usar el mínimo para evitar errores
            n_eventos = min(len(fechas), len(vrps))
        else:
            n_eventos = len(fechas)
            print(f"\n   ✅ Cantidades coinciden: {n_eventos} eventos")
        
        # 4. Emparejar fechas con VRP
        eventos = []
        
        print(f"\n🔗 EMPAREJANDO FECHAS CON VRP:")
        
        for i in range(n_eventos):
            fecha_str = fechas[i]
            vrp_str = vrps[i]
            
            print(f"\n   🎯 Par {i+1}/{n_eventos}:")
            print(f"      📅 Fecha: {fecha_str}")
            print(f"      🔥 VRP: {vrp_str}")
            
            # Validar VRP
            # Descartar NaN
            if 'nan' in vrp_str.lower() or any(c.isalpha() for c in vrp_str):
                print(f"      ❌ SKIP: VRP es NaN o contiene letras")
                continue
            
            try:
                vrp_mw = float(vrp_str)
                print(f"      ✅ VRP numérico: {vrp_mw} MW")
            except ValueError:
                print(f"      ❌ SKIP: VRP no numérico")
                continue
            
            # Validar rango
            if vrp_mw < 0.01:
                print(f"      ❌ SKIP: VRP muy bajo ({vrp_mw} < 0.01)")
                continue
            
            if vrp_mw > 1000:
                print(f"      ❌ SKIP: VRP muy alto ({vrp_mw} > 1000)")
                continue
            
            # Parsear fecha
            try:
                dt_utc = datetime.strptime(fecha_str, "%d-%b-%Y %H:%M:%S")
                dt_utc = dt_utc.replace(tzinfo=pytz.utc)
                print(f"      ✅ Fecha parseada: {dt_utc}")
            except Exception as e:
                print(f"      ❌ SKIP: Error parseando fecha: {e}")
                continue
            
            eventos.append({
                'timestamp': int(dt_utc.timestamp()),
                'datetime': dt_utc,
                'vrp_mw': vrp_mw
            })
            
            print(f"      ✅✅ EVENTO VÁLIDO AGREGADO")
        
        print(f"\n📊 RESULTADO FINAL: {len(eventos)} eventos válidos de {n_eventos} pares")
        
        if len(eventos) > 0:
            print(f"\n✅ Eventos extraídos:")
            for ev in eventos:
                print(f"   - {ev['datetime']} | {ev['vrp_mw']} MW | timestamp={ev['timestamp']}")
        
        return eventos
    
    except Exception as e:
        print(f"❌ ERROR GENERAL en OCR: {e}")
        import traceback
        print(traceback.format_exc())
        return []


def analizar_puntos_distancia(img_dist_path, eventos):
    """Analiza píxeles en Dist.png para validar eventos"""
    try:
        img_dist = cv2.imread(img_dist_path)
        if img_dist is None:
            return eventos
        
        img_dist_rgb = cv2.cvtColor(img_dist, cv2.COLOR_BGR2RGB)
        
        h, w = img_dist_rgb.shape[:2]
        roi_x = int(w * 0.7)
        roi_y = int(h * 0.3)
        roi_w = int(w * 0.25)
        roi_h = int(h * 0.5)
        
        roi = img_dist_rgb[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
        
        mask_verde = cv2.inRange(roi, (0, 100, 0), (100, 255, 100))
        pixeles_verde = np.sum(mask_verde > 0)
        
        mask_rojos = cv2.inRange(roi, (200, 0, 0), (255, 50, 50))
        pixeles_rojos = np.sum(mask_rojos > 0)
        
        mask_negros = cv2.inRange(roi, (0, 0, 0), (50, 50, 50))
        pixeles_negros = np.sum(mask_negros > 0)
        
        if pixeles_rojos > pixeles_negros and pixeles_rojos > 10:
            color = 'rojo'
        elif pixeles_negros > pixeles_rojos and pixeles_negros > 10:
            color = 'negro'
        elif pixeles_verde > 10:
            color = 'verde'
        else:
            color = 'sin_punto'
        
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
    """Clasifica confianza de un evento OCR"""
    color = evento.get('color_punto', 'sin_punto')
    pixeles_rojos = evento.get('pixeles_rojos', 0)
    pixeles_negros = evento.get('pixeles_negros', 0)
    vrp_mw = evento.get('vrp_mw', 0)
    
    if color == 'rojo' and pixeles_rojos > pixeles_negros:
        if pixeles_rojos > 100:
            return {
                'confianza': 'alta',
                'tipo_registro': 'ALERTA_TERMICA_OCR',
                'guardar': True,
                'guardar_imagenes': True,
                'requiere_verificacion': False,
                'nota': f'Píxeles rojos dominantes ({pixeles_rojos}) - Evento real'
            }
        else:
            return {
                'confianza': 'media',
                'tipo_registro': 'ALERTA_TERMICA_OCR',
                'guardar': True,
                'guardar_imagenes': True,
                'requiere_verificacion': True,
                'nota': f'Mezcla rojos/negros - Evento en zona límite (VRP={vrp_mw} MW)'
            }
    
    if color == 'sin_punto' and pixeles_rojos > 20 and pixeles_negros > 20:
        return {
            'confianza': 'media',
            'tipo_registro': 'ALERTA_TERMICA_OCR',
            'guardar': True,
            'guardar_imagenes': True,
            'requiere_verificacion': True,
            'nota': f'Mezcla rojos/negros - Evento en zona límite (VRP={vrp_mw} MW)'
        }
    
    if color == 'negro' or (pixeles_negros > pixeles_rojos and pixeles_negros > 50):
        return {
            'confianza': 'alta',
            'tipo_registro': 'FALSO_POSITIVO_OCR',
            'guardar': True,
            'guardar_imagenes': False,
            'requiere_verificacion': False,
            'nota': 'Píxeles negros dominantes - Evento fuera del límite'
        }
    
    return {
        'confianza': 'baja',
        'tipo_registro': 'FALSO_POSITIVO_OCR',
        'guardar': True,
        'guardar_imagenes': False,
        'requiere_verificacion': False,
        'nota': 'Sin señal clara en Dist.png'
    }


def verificar_evento_no_existe(evento, volcan_nombre, sensor, df_consolidado, df_ocr):
    """Verifica que el evento NO exista ya en los CSVs"""
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
# FUNCIONES V5 (Estrella Verde) - SIN CAMBIOS
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

"""
OCR_UTILS.PY V29 - Estrella v2 (verde+gris) + geometría medida px<->km
BASE: V28 (extracción espacial) + estrella gris + km medidos por imagen

CAMBIO V29 (2026-06-12, ver tasks/AUDITORIA_OCR_EMPIRICA_2026-06.md §G):
- medir_geometria_panel(): detecta las espinas 25km/0km del panel Last Month
  en cada imagen (576/576 validadas) -> y_a_km() convierte píxel a km medidos.
  La clasificación dentro/fuera compara km contra limite_km (+0.15 tolerancia);
  Y_LIMITE_PX queda solo como fallback.
- detectar_estrella_gris() + detectar_estrella_v2(): la estrella gris es una
  detección débil real (VRP 0.02-0.05 MW, sub-umbral del banner MIROVA).
  Verde -> confianza alta (sin cambio) | Gris -> confianza media.
- leer_header_anomalia(): valida en cruzado el color de la estrella con la
  caja "Thermal anomaly" (consistencia histórica 100%).

V28 - Extracción espacial por celdas (grilla 2x5)
BASE: V27 (contexto latest.php) + NUEVO extractor espacial

CAMBIO V28 (2026-06-11, ver tasks/AUDITORIA_OCR_EMPIRICA_2026-06.md):
- NUEVA: extraer_eventos_espacial() — empareja fecha<->VRP por celda física
  de la grilla 2x5 (image_to_data + posiciones). Inmune a corrimientos.
- extraer_eventos_latest10nti() ahora usa espacial como primario y la página
  completa (V11, emparejado por orden) solo como fallback si espacial <10.
- Benchmark: espacial 330/330 pares vs 329/330 del legacy (33 imágenes vivas).
- Calibración corregida: Tupungatito y_limite 257->243, eje 0km = y295.

V27: Contexto latest.php para asociación precisa
BASE: V26 (orden temporal) + NUEVO contexto latest.php

CAMBIO V27 (INTEGRACIÓN COMPLETA):
- NUEVA función: obtener_contexto_latest() para leer eventos en latest.php
- MODIFICADA: analizar_puntos_distancia() ahora recibe contexto_latest
- MODIFICADA: clasificar_confianza() detecta duplicados con latest.php
- ESTRATEGIA: Usar estrella verde como calibración
  * Estrella verde → Evento lejano en latest.php (FALSO_POSITIVO)
  * Píxeles rojos → Evento cercano NO en latest.php (ALERTA_TERMICA_OCR)
- VENTANA TEMPORAL: ±10 min (scraper latest.php corre cada 5 min)

CASO USO: Tupungatito
- 1.32 MW (18.1 km) en latest.php → Estrella verde → NO guardar OCR
- 0.29 MW (< 7 km) NO en latest.php → Píxeles rojos → Guardar OCR

PRESERVA V26:
- Orden temporal grupos
- Filtro VRP válidos
- Umbral 3 px²
- Tupungatito 7 km

PRESERVA V22:
- Campo requiere_verificacion en todos los returns
- Campo nota minúscula

PRESERVA V21:
- Campo vrp_mw minúscula (fix crítico)

PRESERVA V20:
- Orden parámetros correcto
- Carga img_dist antes de validar estrella

PRESERVA V19:
- Detección grupos píxeles

PRESERVA V17:
- ROI TEMPORAL: (x: 0.8424-0.8635, y: 0.1817-0.4933)
- Sistema 3 fases: rojos → estrella → negros
- 14 volcanes en LIMITES_Y_COORDENADAS
- Filtro estrella verde: mask_grafico[100:, 250:]
"""

import cv2
import numpy as np
import pytesseract
from datetime import datetime
import pytz
import re
import os
from PIL import Image
from volcanes import LIMITES_Y_COORDENADAS  # fuente única de verdad

# ========================================
# NUEVA V27: CONTEXTO LATEST.PHP
# ========================================

def obtener_contexto_latest(volcan_nombre, sensor, eventos_ocr, df_consolidado):
    """
    V27: Obtiene contexto de latest.php para eventos cercanos temporalmente
    
    PROPÓSITO:
    - Identificar eventos en latest.php que corresponden a estrella verde
    - Ventana temporal: ±10 min (scraper latest corre cada 5 min)
    - Permite diferenciar eventos simultáneos por su distancia conocida
    
    CASO USO: Tupungatito
    - OCR detecta: 1.32 MW + 0.29 MW
    - latest.php tiene: 1.32 MW a 18.1 km (FALSO_POSITIVO)
    - Contexto indica: 1.32 MW → Estrella verde (NO guardar OCR)
    - Por eliminación: 0.29 MW → Píxeles rojos (SÍ guardar OCR)
    
    Args:
        volcan_nombre: Nombre del volcán
        sensor: Sensor (VIIRS375, VIIRS, MODIS)
        eventos_ocr: Lista de eventos detectados en OCR
        df_consolidado: DataFrame con registro_vrp_consolidado.csv
    
    Returns:
        dict: {
            'tiene_eventos_latest': bool,
            'eventos_lejanos': list de dicts con {timestamp, distancia_km, vrp_mw},
            'eventos_cercanos': list de dicts con {timestamp, distancia_km, vrp_mw}
        }
    """
    if df_consolidado is None or df_consolidado.empty:
        return {
            'tiene_eventos_latest': False,
            'eventos_lejanos': [],
            'eventos_cercanos': []
        }
    
    limite_km = LIMITES_Y_COORDENADAS.get(volcan_nombre, {}).get('LIMITE_KM', 5.0)
    
    # Ventana temporal: ±10 minutos de cada evento OCR
    ventana_segundos = 600  # 10 minutos
    
    eventos_lejanos = []
    eventos_cercanos = []
    
    for evento_ocr in eventos_ocr:
        ts_ocr = evento_ocr['timestamp']
        ts_min = ts_ocr - ventana_segundos
        ts_max = ts_ocr + ventana_segundos
        
        # Buscar eventos en latest.php cercanos temporalmente
        mask = (
            (df_consolidado['Volcan'] == volcan_nombre) &
            (df_consolidado['Sensor'] == sensor) &
            (df_consolidado['timestamp'] >= ts_min) &
            (df_consolidado['timestamp'] <= ts_max) &
            (df_consolidado['VRP_MW'] > 0)
        )
        
        eventos_latest = df_consolidado[mask]
        
        for idx, row in eventos_latest.iterrows():
            evento_info = {
                'timestamp': int(row['timestamp']),
                'distancia_km': float(row['Distancia_km']),
                'vrp_mw': float(row['VRP_MW']),
                'tipo_registro': row['Tipo_Registro']
            }
            
            # Clasificar según distancia
            if row['Distancia_km'] > limite_km:
                # Evento lejano (FALSO_POSITIVO en latest.php)
                # Corresponde a ESTRELLA VERDE en Dist.png
                if evento_info not in eventos_lejanos:
                    eventos_lejanos.append(evento_info)
            else:
                # Evento cercano (ALERTA_TERMICA en latest.php)
                # Ya está siendo procesado por scraper.py
                if evento_info not in eventos_cercanos:
                    eventos_cercanos.append(evento_info)
    
    return {
        'tiene_eventos_latest': len(eventos_lejanos) > 0 or len(eventos_cercanos) > 0,
        'eventos_lejanos': eventos_lejanos,
        'eventos_cercanos': eventos_cercanos
    }

# ========================================
# COORDENADAS DE LÍMITES → centralizado en volcanes.py
# (LIMITES_Y_COORDENADAS se importa arriba; incluye Tupungatito 7 km y los alias)
# ========================================

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

def detectar_grupos_pixeles_rojos(roi, umbral_area_minima=3):
    # =====NUEVO V24: Umbral reducido 10 → 3 px²=====
    # PROBLEMA: Lascar grupo real 8 px² → descartado umbral 10
    # EVIDENCIA: Grupo compacto dispersión Y=3.7, X=1.1
    # SOLUCIÓN: Umbral 3 px² captura grupos pequeños reales
    # =================================================
    """
    V24: Detecta grupos separados de píxeles rojos en ROI
    CAMBIO V24: umbral_area_minima = 3 px² (antes 10 en V23, 20 en V19)
    
    Útil para eventos superpuestos (ej: Lastarria 05:42 + 06:06, Tupungatito 04:48 + 05:12 + 06:30)
    
    Args:
        roi: ROI de imagen (numpy array RGB)
        umbral_area_minima: Área mínima en píxeles para considerar grupo válido (V23: 10 px²)
    
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
    # =====FIX V26: Asociar por ORDEN TEMPORAL=====
    # PROBLEMA V25: Asociaba por índice, causaba asignaciones incorrectas
    # EVIDENCIA: Tupungatito 0.29 MW (grupo Y=273 parte baja) asignado a 1.32 MW
    # SOLUCIÓN: Asociar grupos ordenados por Y (descendente) a eventos ordenados temporalmente
    # 
    # LÓGICA:
    # - Eventos ya vienen ordenados cronológicamente (más reciente primero)
    # - Grupos ordenados por Y descendente (más alto = más reciente visualmente)
    # - Asociación: evento_reciente[0] ← grupo_alto[0]
    # ==================================================
    """
    V26: Asocia grupos a eventos por ORDEN TEMPORAL
    
    CAMBIO V26: Asociación por orden cronológico, no por índice ciego
    
    Estrategia:
    - Filtrar eventos con VRP > 0
    - Ordenar grupos por Y DESCENDENTE (top = más reciente)
    - Asociar por orden: grupo[0] (top) → evento_reciente[0]
    
    Args:
        eventos: Lista de eventos (YA ordenados cronológicamente, más reciente primero)
        grupos: Lista de grupos detectados en ROI (ordenados por Y ascendente)
        roi_y_start: Coordenada Y inicial del ROI en imagen completa
    
    Returns:
        dict: {evento_index_original: grupo_info con y_absoluto}
    """
    if not grupos:
        return {}
    
    # Filtrar solo eventos VRP válidos (preservado V25)
    # =====NUEVO V27: PASO 2 - Excluir eventos en latest.php=====
    # No asociar grupos a eventos que ya están en latest.php
    # porque no los vamos a guardar en OCR (son duplicados)
    # ===========================================================
    eventos_validos = []
    indices_originales = []
    
    for i, evento in enumerate(eventos):
        vrp = evento.get('vrp_mw', 0)
        en_latest = evento.get('en_latest_php', False)  # =====NUEVO V27=====
        
        # Validar: VRP > 0 Y NO esté en latest.php
        if vrp > 0 and not np.isnan(vrp) and not en_latest:
            eventos_validos.append(evento)
            indices_originales.append(i)
        elif en_latest:
            # Log informativo de exclusión
            print(f"      ⏭️ Evento {i+1} ({vrp:.2f} MW) excluido de asociación (ya en latest.php)")
    
    if not eventos_validos:
        return {}
    
    # =====NUEVO V26: Ordenar grupos por Y DESCENDENTE (top primero)=====
    # Grupos vienen ordenados por Y ascendente, invertir para tener top primero
    grupos_ordenados = sorted(grupos, key=lambda g: g['centro_y'], reverse=True)
    # ===================================================================
    
    if len(grupos_ordenados) == 1 and len(eventos_validos) == 1:
        # Caso simple: 1 grupo + 1 evento
        grupo = grupos_ordenados[0].copy()
        grupo['y_absoluto'] = roi_y_start + grupo['centro_y']
        return {indices_originales[0]: grupo}
    
    # Múltiples grupos o eventos → Asociar por orden temporal
    # grupo[0] (top/reciente) → evento[0] (más reciente)
    # grupo[1] (siguiente) → evento[1] (siguiente)
    asociaciones = {}
    
    for idx_valido, evento in enumerate(eventos_validos):
        if idx_valido < len(grupos_ordenados):
            grupo = grupos_ordenados[idx_valido].copy()
            grupo['y_absoluto'] = roi_y_start + grupo['centro_y']
            # Asociar al índice ORIGINAL del evento
            asociaciones[indices_originales[idx_valido]] = grupo
    
    return asociaciones


# JUSTIFICACIÓN:
# - Máxima precisión temporal (sin mezcla de días)
# - Reduce área de análisis en 99.4% (3,162 px² vs 510,000 px²)
# - Ideal para monitoreo en tiempo real
# - Evita falsos positivos de días antiguos


# ========================================
# NUEVO V28: EXTRACCIÓN ESPACIAL POR CELDAS (grilla 2x5 de Latest10NTI)
# ========================================
# PROBLEMA del método por página completa: junta todas las fechas y todos los
# VRP de la imagen y los empareja POR ORDEN. Si Tesseract pierde UNA fecha,
# todos los pares siguientes quedan corridos (timestamp de un evento con el
# VRP de otro) sin error visible.
# SOLUCIÓN: leer las tiras de fecha y de VRP con image_to_data (posiciones) y
# asignar cada palabra a su columna de la grilla 2x5. Fecha y VRP se emparejan
# por CELDA física -> el corrimiento es estructuralmente imposible.
# Benchmark 2026-06-11 (33 imágenes vivas): espacial 330/330 vs legacy 329/330.
# Escala con alto/600 -> absorbe la variante 850x596 de MIROVA.
# ========================================

# (fecha_y1, fecha_y2, vrp_y1, vrp_y2) de cada fila de la grilla, en 850x600
FILAS_GRILLA_NTI = [(140, 168, 313, 342), (376, 404, 548, 578)]
ANCHO_COL_NTI = 170
PATRON_FECHA_NTI = re.compile(r'(\d{1,2})-([A-Za-z]{3})-(\d{4})\s+(\d{2}:\d{2}:\d{2})')


def _normalizar_texto_ocr(t):
    """Limpia ruido típico de Tesseract en las tiras de Latest10NTI."""
    t = re.sub(r'([A-Z])/([a-z])', r'\1\2', t)    # "J/un" -> "Jun"
    t = re.sub(r'-/([a-z]{2})-', r'-J\1-', t)      # "-/un-" -> "-Jun-"
    t = re.sub(r'(\d{4})(\d{2}:)', r'\1 \2', t)    # "202607:" -> "2026 07:"
    return t


def _palabras_con_posicion(img_bgr, y1, y2, escala=3):
    """OCR de una tira horizontal completa. Devuelve [(x_centro_original, texto)]."""
    g = cv2.cvtColor(img_bgr[y1:y2, :], cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, None, fx=escala, fy=escala, interpolation=cv2.INTER_CUBIC)
    d = pytesseract.image_to_data(g, config='--oem 3 --psm 6',
                                  output_type=pytesseract.Output.DICT)
    return [((d['left'][i] + d['width'][i] / 2) / escala, d['text'][i].strip())
            for i in range(len(d['text'])) if d['text'][i].strip()]


def extraer_eventos_espacial(img_path):
    """
    V28: Extrae los (hasta) 10 eventos de Latest10NTI emparejando fecha<->VRP
    por celda de la grilla 2x5. Devuelve eventos en el mismo formato que el
    extractor por página completa: [{'datetime','timestamp','vrp_mw'}].
    """
    eventos = []
    try:
        img = cv2.imread(img_path)
        if img is None:
            print(f"   ❌ Espacial: no se pudo cargar {img_path}")
            return []
        h = img.shape[0]
        sy = h / 600.0  # adaptación a la variante 850x596

        for (fy1, fy2, vy1, vy2) in FILAS_GRILLA_NTI:
            celdas_f = {c: [] for c in range(5)}
            celdas_v = {c: [] for c in range(5)}
            for x, t in _palabras_con_posicion(img, int(fy1 * sy), int(fy2 * sy)):
                celdas_f[min(4, max(0, int((x - 5) / ANCHO_COL_NTI)))].append(t)
            for x, t in _palabras_con_posicion(img, int(vy1 * sy), int(vy2 * sy)):
                celdas_v[min(4, max(0, int((x - 5) / ANCHO_COL_NTI)))].append(t)

            for c in range(5):
                tf = _normalizar_texto_ocr(' '.join(celdas_f[c]))
                tv = _normalizar_texto_ocr(' '.join(celdas_v[c]))
                m = PATRON_FECHA_NTI.search(tf)
                mv = re.search(r'VRP\s*[=~]?\s*([\d.]+|NaN)\s*MW', tv, re.IGNORECASE)
                if not (m and mv):
                    continue
                fecha_str = f"{m.group(1).zfill(2)}-{m.group(2)}-{m.group(3)} {m.group(4)}"
                try:
                    dt_obj = datetime.strptime(fecha_str, "%d-%b-%Y %H:%M:%S")
                except ValueError:
                    continue
                dt_utc = dt_obj.replace(tzinfo=pytz.utc)
                vrp_str = mv.group(1)
                vrp_mw = 0.0 if vrp_str.lower() == 'nan' else float(vrp_str)
                eventos.append({
                    'datetime': dt_utc,
                    'timestamp': int(dt_utc.timestamp()),
                    'vrp_mw': vrp_mw
                })
    except Exception as e:
        print(f"   ❌ ERROR en extraer_eventos_espacial: {e}")
        import traceback
        traceback.print_exc()
    return eventos


def extraer_eventos_latest10nti(img_path):
    """
    V28: extractor ESPACIAL como primario + página completa como fallback.
    Mantiene el nombre público que usan scraper_ocr.py y los workflows.
    """
    print(f"\n🔍 OCR V28 - Procesando: {img_path}")
    eventos_esp = extraer_eventos_espacial(img_path)
    print(f"   📐 Espacial: {len(eventos_esp)} eventos")

    if len(eventos_esp) >= 10:
        return sorted(eventos_esp, key=lambda e: e['timestamp'], reverse=True)

    # Fallback: método por página completa (si el espacial logró <10 pares)
    eventos_leg = _extraer_eventos_pagina_completa(img_path)
    if len(eventos_leg) > len(eventos_esp):
        print(f"   ⚠️ Fallback página completa: {len(eventos_leg)} > {len(eventos_esp)} "
              f"(emparejado por orden — riesgo de corrimiento)")
        return sorted(eventos_leg, key=lambda e: e['timestamp'], reverse=True)
    return sorted(eventos_esp, key=lambda e: e['timestamp'], reverse=True)


def _extraer_eventos_pagina_completa(img_path):
    """V11 (legacy): OCR de página completa, emparejado por orden. Solo fallback."""
    print(f"\n🔍 OCR V11 (fallback) - Procesando: {img_path}")
    
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


def analizar_puntos_distancia(img_dist_path, eventos, volcan_nombre, contexto_latest=None):
    # =====NUEVO V27: Parámetro contexto_latest=====
    # Recibe info de latest.php para asociar correctamente
    # contexto_latest = {
    #     'tiene_eventos_latest': bool,
    #     'eventos_lejanos': [{timestamp, distancia_km, vrp_mw}],
    #     'eventos_cercanos': [...]
    # }
    # ===============================================
    """
    V27: Usa contexto de latest.php para asociación precisa
    BASE V19: Detecta grupos píxeles rojos y asocia a eventos individuales
    PRESERVA V17: ROI temporal (x: 0.8424-0.8635, y: 0.1817-0.4933)
    
    NUEVO V27:
    - Recibe contexto_latest con eventos en latest.php
    - Marca eventos que ya están en latest.php (duplicados)
    - Asocia grupos solo a eventos NO en latest.php
    
    COMPATIBILIDAD:
    - Si contexto_latest=None, funciona como V26 (sin cambios)
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

        # =====V29: medir geometría del panel (px<->km) para esta imagen=====
        geometria_panel = medir_geometria_panel(cv2.cvtColor(img_dist, cv2.COLOR_BGR2GRAY))
        if geometria_panel:
            print(f"   📏 V29 geometría medida: techo(25km)=y{geometria_panel[0]}, eje(0km)=y{geometria_panel[1]}")
        else:
            print(f"   ⚠️ V29: geometría no medible -> se usará calibración fija")
        # ====================================================================

        # ========================================
        # ROI TEMPORAL (PRESERVADO V17)
        # ========================================
        roi_x_start = int(width * ROI_CONFIG['x_start_pct'])
        roi_x_end = int(width * ROI_CONFIG['x_end_pct'])
        roi_y_start = int(height * ROI_CONFIG['y_start_pct'])
        roi_y_end = int(height * ROI_CONFIG['y_end_pct'])
        
        roi = img_rgb[roi_y_start:roi_y_end, roi_x_start:roi_x_end]
        
        print(f"\n🎯 V27 - Analizando píxeles con ROI TEMPORAL + GRUPOS + CONTEXTO LATEST")
        print(f"   📍 ROI temporal: X={roi_x_start}-{roi_x_end}, Y={roi_y_start}-{roi_y_end}")
        print(f"   📏 Tamaño ROI: {roi.shape[1]}x{roi.shape[0]} = {roi.shape[0]*roi.shape[1]} px²")
        
        # ========================================
        # NUEVO V19: Detectar grupos separados
        # V23: umbral_area_minima = 10 (reducido de 20)
        # ========================================
        grupos = detectar_grupos_pixeles_rojos(roi)
        
        print(f"   🔴 Grupos detectados: {len(grupos)}")
        for i, grupo in enumerate(grupos, 1):
            y_abs = roi_y_start + grupo['centro_y']
            print(f"      Grupo {i}: Y_relativo={grupo['centro_y']}, Y_absoluto={y_abs}, área={grupo['area']} px²")
        
        # Asociar grupos a eventos
        asociaciones = asociar_grupos_a_eventos(eventos, grupos, roi_y_start)
        
        # =====NUEVO V27: PASO 1 - Marcar eventos en latest.php=====
        # Compara timestamps OCR con eventos en contexto_latest
        # Marca duplicados para excluirlos de guardado
        # ==========================================================
        if contexto_latest and contexto_latest['tiene_eventos_latest']:
            print(f"\n   🔍 V27 - Verificando duplicados con latest.php:")
            
            eventos_marcados = 0
            for evento in eventos:
                ts_evento = evento['timestamp']
                
                # Buscar en eventos lejanos (FALSO_POSITIVO en latest.php)
                for ev_latest in contexto_latest['eventos_lejanos']:
                    # Ventana ±60 segundos (diferencias de redondeo timestamp)
                    if abs(ts_evento - ev_latest['timestamp']) <= 60:
                        evento['en_latest_php'] = True
                        evento['distancia_latest'] = ev_latest['distancia_km']
                        evento['tipo_latest'] = 'FALSO_POSITIVO'
                        eventos_marcados += 1
                        print(f"      ⚠️ Evento {evento['vrp_mw']:.2f} MW → DUPLICADO latest.php (dist={ev_latest['distancia_km']:.1f} km)")
                        break
                
                # También buscar en eventos cercanos
                if not evento.get('en_latest_php', False):
                    for ev_latest in contexto_latest['eventos_cercanos']:
                        if abs(ts_evento - ev_latest['timestamp']) <= 60:
                            evento['en_latest_php'] = True
                            evento['distancia_latest'] = ev_latest['distancia_km']
                            evento['tipo_latest'] = 'ALERTA_TERMICA'
                            eventos_marcados += 1
                            print(f"      ⚠️ Evento {evento['vrp_mw']:.2f} MW → DUPLICADO latest.php (dist={ev_latest['distancia_km']:.1f} km)")
                            break
            
            if eventos_marcados == 0:
                print(f"      ✅ No hay duplicados con latest.php")
            else:
                print(f"      ⚠️ {eventos_marcados} eventos duplicados con latest.php")
        # ===========================================================
        
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
            evento['geometria_panel'] = geometria_panel  # V29: px<->km medido
            evento['color_punto'] = color_dominante
            evento['pixeles_rojos'] = int(pixeles_rojos)
            evento['pixeles_negros'] = int(pixeles_negros)
            evento['pixeles_verdes'] = int(pixeles_verdes)
            evento['ratio_rojos'] = float(ratio_rojos)
            evento['ratio_negros'] = float(ratio_negros)
            evento['metodo'] = 'roi_temporal_v26'
            
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
        print(f"   ❌ ERROR en analizar_puntos_distancia V23: {e}")
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


# ========================================
# NUEVO V29: GEOMETRÍA MEDIDA DEL PANEL (px <-> km)
# ========================================
# PROBLEMA: la clasificación dentro/fuera usaba Y_LIMITE_PX calibrado a mano por
# volcán, asumiendo imagen 850x600. MIROVA entrega variantes (850x596, espina
# superior clara) y un error de calibración ya costó eventos (Tupungatito).
# SOLUCIÓN: medir en CADA imagen las dos espinas del panel "Last Month"
# (techo = 25 km, eje = 0 km) y convertir píxel->km con esa regla medida.
# Validado 2026-06-12: 576/576 imágenes históricas+vivas detectadas
# (600px: techo 110/eje 295; 596px: 109/293 -> ~7.4 px/km en todas).
# La calibración fija de volcanes.py queda como fallback si la medición falla.
# Tolerancia +0.15 km (~1 px) preserva los casos borde del método anterior.
# ========================================

TOLERANCIA_KM = 0.15  # ~1 px de ruido de render/centroide


def medir_geometria_panel(img_gray):
    """
    V29: Detecta (y_techo_25km, y_eje_0km) del panel Last Month.
    El eje siempre se renderiza oscuro (<170); el techo a veces claro (~227),
    por eso usa umbral relativo (<235). Devuelve (techo, eje) o None.
    """
    try:
        h = img_gray.shape[0]
        sy = h / 600.0

        def filas_espina(y_lo, y_hi, umbral):
            v = img_gray[y_lo:y_hi, 300:790] < umbral
            need = int(0.93 * v.shape[1])
            return [y_lo + i for i, c in enumerate(v.sum(axis=1)) if c >= need]

        def grupos_de(filas):
            if not filas:
                return []
            gs = [[filas[0]]]
            for y in filas[1:]:
                if y - gs[-1][-1] <= 2:
                    gs[-1].append(y)
                else:
                    gs.append([y])
            return [int(np.mean(gr)) for gr in gs]

        f_eje = filas_espina(int(240 * sy), int(340 * sy), 170)
        if not f_eje:
            return None
        eje = grupos_de(f_eje)[-1]
        candidatos = grupos_de(filas_espina(int(70 * sy), eje - int(150 * sy), 235))
        # el techo correcto es el grupo con separación ~185*sy del eje
        validos = [t for t in candidatos if 160 * sy < eje - t < 210 * sy]
        if not validos:
            return None
        techo = min(validos, key=lambda t: abs((eje - t) - 185 * sy))
        return techo, eje
    except Exception:
        return None


def y_a_km(y, geometria):
    """Convierte fila de píxel a km usando la geometría medida (panel 0-25 km)."""
    techo, eje = geometria
    return (eje - y) * 25.0 / (eje - techo)


def detectar_estrella_gris(img_dist, sy=1.0):
    """
    V29: Detecta la estrella GRIS (detección débil sub-umbral del banner MIROVA,
    VRP 0.02-0.05 MW según cruce con latest.php — ver auditoría §G).
    Relleno plateado g 150-225, S<60; el contorno oscuro fragmenta el relleno a
    ~49 px², por eso umbral área >=30 y SIN morfología. Zona: junto a la línea
    punteada del "ahora" (x 660-800). Devuelve y_centro o None.
    """
    try:
        rgb = cv2.cvtColor(img_dist, cv2.COLOR_BGR2RGB)
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        gg = cv2.cvtColor(img_dist, cv2.COLOR_BGR2GRAY)
        y1, y2, x1, x2 = int(108 * sy), int(302 * sy), 660, 800
        zg, zs = gg[y1:y2, x1:x2], hsv[y1:y2, x1:x2, 1]
        mask = ((zg > 150) & (zg < 225) & (zs < 60)).astype(np.uint8) * 255
        cont, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        mejores = []
        for c in cont:
            a = cv2.contourArea(c)
            if a < 30 or a > 500:
                continue
            x, y, w, h = cv2.boundingRect(c)
            if not (9 <= w <= 30 and 9 <= h <= 30 and 0.5 < w / h < 2.0):
                continue
            M = cv2.moments(c)
            if M['m00'] == 0:
                continue
            mejores.append((a, y1 + int(M['m01'] / M['m00'])))
        return max(mejores)[1] if mejores else None
    except Exception:
        return None


def detectar_estrella_v2(img_dist, sy=1.0):
    """
    V29: estrella verde (detector V16 preservado) o gris (nueva).
    Devuelve (color, y_centro) | (None, None).
    """
    cy = detectar_centro_estrella_verde(img_dist)
    if cy is not None:
        return 'verde', cy
    cy = detectar_estrella_gris(img_dist, sy)
    if cy is not None:
        return 'gris', cy
    return None, None


def leer_header_anomalia(img_dist, sy=1.0):
    """
    V29: Lee el color de la caja "Thermal anomaly" del header.
    Devuelve 'activa' (caja verde) o 'none'. Validación cruzada del color de
    estrella: consistencia 100% en 464 imágenes (451 verde<->activa, 13 gris<->none).
    """
    try:
        caja = img_dist[int(48 * sy):int(76 * sy), 460:760]
        hsv = cv2.cvtColor(cv2.cvtColor(caja, cv2.COLOR_BGR2RGB), cv2.COLOR_RGB2HSV)
        verdes = cv2.inRange(hsv, (40, 80, 80), (80, 255, 255)).sum() / 255
        return 'activa' if verdes > 500 else 'none'
    except Exception:
        return 'desconocido'


def validar_con_estrella_verde(img_dist, volcan_nombre):
    """
    V29: Valida con estrella VERDE o GRIS usando km medidos en la imagen.
    - Verde = anomalía activa (banner) -> confianza alta (sin cambio vs V16)
    - Gris  = detección débil sub-umbral (VRP 0.02-0.05 MW) -> confianza media
    - Posición de ambas = distancia de la última detección (error mediano
      0.06 km verde / 0.15 km gris, n=459; auditoría §G)
    Fallback: si no se puede medir la geometría, usa Y_LIMITE_PX (calibración fija).
    """
    if volcan_nombre not in LIMITES_Y_COORDENADAS:
        return None, None, f"Volcán '{volcan_nombre}' sin coordenadas calibradas"

    coords = LIMITES_Y_COORDENADAS[volcan_nombre]
    limite_km = coords['LIMITE_KM']
    sy = img_dist.shape[0] / 600.0

    color, y_estrella = detectar_estrella_v2(img_dist, sy)
    header = leer_header_anomalia(img_dist, sy)

    if y_estrella is None:
        if header == 'activa':
            # banner dice anomalía pero no encontramos la estrella -> revisar
            return None, None, "Sin estrella detectada PERO header=ACTIVA (revisar detector)"
        return None, None, "Sin estrella (última medición sin detección, header=NONE)"

    # validación cruzada estrella<->header (consistencia esperada 100%)
    esperado = 'activa' if color == 'verde' else 'none'
    aviso_header = ""
    if header != 'desconocido' and header != esperado:
        aviso_header = f" ⚠️header={header}≠{esperado}"
        print(f"      ⚠️ V29: color estrella ({color}) no coincide con header ({header})")

    # px -> km con geometría MEDIDA; fallback a calibración fija
    geometria = medir_geometria_panel(cv2.cvtColor(img_dist, cv2.COLOR_BGR2GRAY))
    if geometria:
        dist_km = max(0.0, y_a_km(y_estrella, geometria))
        dentro = dist_km <= limite_km + TOLERANCIA_KM
        base_nota = (f"Estrella {color} en Y={y_estrella} -> {dist_km:.2f} km "
                     f"(límite {limite_km} km, geometría medida){aviso_header}")
    else:
        y_limite = coords['Y_LIMITE_PX'] if img_dist.shape[0] == 600 else int(coords['Y_LIMITE_PX'] * sy)
        dentro = y_estrella >= y_limite
        base_nota = (f"Estrella {color} en Y={y_estrella} vs límite Y={y_limite} "
                     f"(fallback calibración fija){aviso_header}")

    if dentro:
        if color == 'verde':
            return 'alta', 'ALERTA_TERMICA_OCR', base_nota
        return 'media', 'ALERTA_TERMICA_OCR', base_nota + " | detección débil sub-umbral MIROVA"
    else:
        return 'baja', 'FALSO_POSITIVO_OCR', base_nota + " | FUERA de límite"


def clasificar_confianza(evento, img_dist_path, volcan_nombre):
    """
    V27: Detecta duplicados con latest.php ANTES de clasificar
    BASE V23: Sistema 3 fases con umbral grupos reducido a 10 px²
    
    NUEVO V27:
    - Verifica si evento está en latest.php
    - Si está → DUPLICADO_LATEST (no guardar)
    - Si no → Continúa sistema 3 fases normal
    
    SISTEMA 3 FASES:
    FASE 1: Píxeles rojos en ROI temporal → Validación por GRUPO individual (umbral 10 px²)
    FASE 2: Estrella verde (V16 - PRESERVADO)
    FASE 3: Píxeles negros (V17 - PRESERVADO)
    """
    
    # =====NUEVO V27: PASO 3 - Detectar duplicados con latest.php=====
    # Revisar ANTES de cualquier validación si evento ya está en latest.php
    # Esto evita procesamiento innecesario y duplicados en CSV
    # ================================================================
    if evento.get('en_latest_php', False):
        distancia = evento.get('distancia_latest', 0)
        tipo_latest = evento.get('tipo_latest', 'desconocido')
        
        print(f"   ═════════════════════════════════════════════════════════")
        print(f"   ⚠️ V27 - DUPLICADO CON LATEST.PHP:")
        print(f"      Evento ya procesado por scraper.py")
        print(f"      Distancia: {distancia:.1f} km")
        print(f"      Tipo en latest: {tipo_latest}")
        print(f"      ❌ NO guardar en OCR (duplicado)")
        
        return {
            'guardar': False,
            'guardar_imagenes': False,
            'tipo_registro': 'DUPLICADO_LATEST',
            'confianza': 'alta',
            'requiere_verificacion': False,
            'Color_Punto': 'sin_punto',
            'nota': f'Duplicado con latest.php (dist={distancia:.1f} km, tipo={tipo_latest})'
        }
    # ================================================================
    
    vrp_mw = evento.get('vrp_mw', 0)
    
    # Validar VRP
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
    
    # ========================================
    # FASE 1 V23: Validar con grupo individual (umbral 10 px²)
    # ========================================
    grupo_info = evento.get('grupo_pixeles')
    
    if grupo_info:
        y_absoluto = grupo_info['y_absoluto']
        area_grupo = grupo_info['area']

        limites = LIMITES_Y_COORDENADAS.get(volcan_nombre, {})
        y_limite_px = limites.get('Y_LIMITE_PX', 257)
        y_eje_x = limites.get('Y_EJE_X_PX', 295)  # eje 0 km real (auditoría 2026-06)
        limite_km = limites.get('LIMITE_KM', 5.0)

        # =====V29: dentro/fuera por km MEDIDOS en la imagen (si hay geometría)=====
        geometria = evento.get('geometria_panel')
        if geometria:
            km_grupo = max(0.0, y_a_km(y_absoluto, geometria))
            dentro_limite = km_grupo <= limite_km + TOLERANCIA_KM
        else:
            km_grupo = None
            dentro_limite = y_absoluto >= y_limite_px  # fallback calibración fija
        # ==========================================================================

        if dentro_limite:
            # DENTRO del límite - VRP REAL
            if km_grupo is not None:
                distancia_aprox = km_grupo
            else:
                # Distancia desde el cráter: 0 km en el eje (y_eje_x), limite_km en la
                # línea de límite (y_limite_px). Corregida 2026-06 (estaba invertida).
                distancia_aprox = ((y_eje_x - y_absoluto) / (y_eje_x - y_limite_px)) * limite_km
            
            metodo_dist = "geometría medida" if km_grupo is not None else "calibración fija"
            print(f"   ═════════════════════════════════════════════════════════")
            print(f"   🎯 FASE 1 V29 (grupo {area_grupo} px²): Y={y_absoluto} -> {distancia_aprox:.2f} km <= {limite_km} km ✅ ({metodo_dist})")
            print(f"      ✅ ALERTA_TERMICA_OCR: Grupo píxeles en Y={y_absoluto}")

            return {
                'guardar': True,
                'guardar_imagenes': True,
                'tipo_registro': 'ALERTA_TERMICA_OCR',
                'confianza': 'alta',
                'requiere_verificacion': False,
                'Color_Punto': 'sin_punto',
                'Metodo_Deteccion': 'grupo_pixeles_v29',
                'nota': f'Grupo píxeles rojos Y={y_absoluto} (área={area_grupo} px², dist≈{distancia_aprox:.2f} km, {metodo_dist})'
            }
        else:
            # FUERA del límite - FALSO POSITIVO
            detalle = (f"{km_grupo:.2f} km > {limite_km} km" if km_grupo is not None
                       else f"Y={y_absoluto} < {y_limite_px}")
            print(f"   ═════════════════════════════════════════════════════════")
            print(f"   🎯 FASE 1 V29 (grupo {area_grupo} px²): {detalle} ❌")
            print(f"      ❌ FALSO_POSITIVO: Grupo fuera límite")

            return {
                'guardar': False,
                'guardar_imagenes': False,
                'tipo_registro': 'FALSO_POSITIVO_OCR',
                'confianza': 'baja',
                'requiere_verificacion': False,
                'Color_Punto': 'sin_punto',
                'nota': f'Grupo fuera límite: {detalle}'
            }
    
    # ========================================
    # FASE 2 (PRESERVADA V16): Estrella verde
    # ========================================
    print(f"   ═════════════════════════════════════════════════════════")
    print(f"   🎯 FASE 1: Sin grupo individual → Continuando FASE 2 (estrella)")
    
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
        nota_estrella = 'Imagen Dist.png no disponible'
    
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
            'requiere_verificacion': False,
            'Color_Punto': evento.get('Color_Punto', 'sin_punto'),
            'nota': f'ROI mayormente negro (ratio={ratio_negros:.2f})'
        }
    
    # Sin señal clara - FALSO POSITIVO
    return {
        'guardar': False,
        'guardar_imagenes': False,
        'tipo_registro': 'FALSO_POSITIVO_OCR',
        'confianza': 'baja',
        'requiere_verificacion': False,
        'Color_Punto': evento.get('Color_Punto', 'mixto'),
        'nota': 'Sin grupo ni estrella clara'
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
    print("TEST: OCR UTILS V26")
    print("  - Asociación grupos: Orden temporal (Y descendente)")
    print("  - Filtro VRP válidos preservado")
    print("  - Umbral grupos: 3 px²")
    print("  - Tupungatito: 7 km")
    print("  - ROI temporal preservado")
    print("  - Sistema 3 fases preservado")
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
    
    print(f"\n✅ CAMBIOS V26:")
    print(f"   - Asociación grupos: Orden temporal (top→reciente)")
    print(f"   - Grupos ordenados Y DESC: más alto = más reciente")
    print(f"   - Filtro VRP > 0 preservado")
    print(f"   - Umbral: 3 px²")
    print(f"   - Tupungatito: 7 km")
    
    print("\n" + "="*70)
    print("✅ OCR UTILS V26 LISTO")
    print("="*70)

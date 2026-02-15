"""
SCRAPER_OCR.PY V18 - FILTRO FECHA: SOLO ÚLTIMAS 24 HORAS
FIX: No procesar eventos antiguos de Latest10NTI cuando se agrega volcán nuevo
"""

import requests
import os
import pandas as pd
from datetime import datetime, timedelta
import pytz
import time
from ocr_utils import (
    extraer_eventos_latest10nti,
    analizar_puntos_distancia,
    clasificar_confianza,
    verificar_evento_no_existe
)

# =========================
# CONFIGURACIÓN
# =========================

VOLCANES_CONFIG = {
    "355100": {"nombre": "Lascar", "id_mirova": "Lascar"},
    "355120": {"nombre": "Lastarria", "id_mirova": "Lastarria"},
    "355030": {"nombre": "Isluga", "id_mirova": "Isluga"},
    "357120": {"nombre": "Villarrica", "id_mirova": "Villarrica"},
    "357110": {"nombre": "Llaima", "id_mirova": "Llaima"},
    "357070": {"nombre": "Nevados de Chillan", "id_mirova": "ChillanNevadosde"},
    "357090": {"nombre": "Copahue", "id_mirova": "Copahue"},
    "357150": {"nombre": "Puyehue-Cordon Caulle", "id_mirova": "PuyehueCordonCaulle"},
    "358041": {"nombre": "Chaiten", "id_mirova": "Chaiten"},
    "357040": {"nombre": "PlanchonPeteroa", "id_mirova": "PlanchonPeteroa"},
    "357010": {"nombre": "Tupungatito", "id_mirova": "Tupungatito"}
}

SENSORES = ["VIIRS375", "VIIRS", "MODIS"]

# ===== NUEVO V18: FILTRO DE FECHA =====
# Solo procesar eventos de últimas 24 horas
VENTANA_HORAS = 24

CARPETA_PRINCIPAL = "monitoreo_satelital"
CARPETA_TEMP = os.path.join(CARPETA_PRINCIPAL, "ocr_temp")
CARPETA_IMAGENES = os.path.join(CARPETA_PRINCIPAL, "imagenes_satelitales")
CARPETA_LOGS = os.path.join(CARPETA_PRINCIPAL, "ocr_logs")

DB_OCR = os.path.join(CARPETA_PRINCIPAL, "registro_vrp_ocr.csv")
DB_CONSOLIDADO = os.path.join(CARPETA_PRINCIPAL, "registro_vrp_consolidado.csv")

COLUMNAS_OCR = [
    "timestamp", "Fecha_Satelite_UTC", "Fecha_Captura_Chile",
    "Volcan", "Sensor", "VRP_MW", "Distancia_km", "Tipo_Registro",
    "Nivel_Actividad", "Ruta Foto", "Fecha_Registro", "Ultima_Actualizacion",
    "Es_Nuevo", "Color_Punto", "Confianza", "En_Grafico", "Metodo_Deteccion",
    "Nota", "Version_OCR"
]

Version_OCR = '18.0'  # V18: Filtro fecha 24h

# ... [resto del código igual hasta la función procesar_volcan_sensor] ...

def procesar_volcan_sensor(id_volcan, sensor, df_consolidado, df_ocr):
    """
    Procesa un volcán-sensor específico
    V18: Filtra eventos antiguos (>24h)
    """
    
    config = VOLCANES_CONFIG.get(id_volcan)
    if not config:
        print(f"⚠️ Volcán {id_volcan} no configurado")
        return []
    
    nombre_v = config["nombre"]
    id_mirova = config["id_mirova"]
    
    print(f"\n🔍 Procesando: {nombre_v} - {sensor}")
    
    # Descargar imagen
    img_latest10_url = f"https://www.mirovaweb.it/mirova/tmp/{id_mirova}_{sensor}_Latest10NTI.png?v={int(time.time())}"
    img_dist_url = f"https://www.mirovaweb.it/mirova/tmp/{id_mirova}_{sensor}_Dist.png?v={int(time.time())}"
    
    img_latest10_path = os.path.join(CARPETA_TEMP, f"{nombre_v}_{sensor}_Latest10NTI.png")
    img_dist_path = os.path.join(CARPETA_TEMP, f"{nombre_v}_{sensor}_Dist.png")
    
    try:
        response_latest = requests.get(img_latest10_url, timeout=10)
        response_dist = requests.get(img_dist_url, timeout=10)
        
        if response_latest.status_code == 200 and response_dist.status_code == 200:
            with open(img_latest10_path, 'wb') as f:
                f.write(response_latest.content)
            with open(img_dist_path, 'wb') as f:
                f.write(response_dist.content)
        else:
            print(f"❌ Error descargando imágenes: {response_latest.status_code}, {response_dist.status_code}")
            return []
    except Exception as e:
        print(f"❌ Error: {e}")
        return []
    
    # Extraer eventos con OCR
    eventos = extraer_eventos_latest10nti(img_latest10_path)
    
    if not eventos:
        print(f"⚠️ No se extrajeron eventos de {nombre_v} - {sensor}")
        return []
    
    print(f"✅ EVENTOS CREADOS: {len(eventos)}")
    
    # ===== NUEVO V18: FILTRO DE FECHA =====
    # Calcular límite de tiempo (hace 24 horas)
    ahora_utc = datetime.now(pytz.utc)
    limite_tiempo = ahora_utc - timedelta(hours=VENTANA_HORAS)
    
    # Filtrar eventos antiguos
    eventos_validos = []
    eventos_descartados = 0
    
    for evento in eventos:
        fecha_evento = datetime.fromisoformat(evento['Fecha_Satelite_UTC'])
        
        if fecha_evento >= limite_tiempo:
            eventos_validos.append(evento)
        else:
            eventos_descartados += 1
    
    if eventos_descartados > 0:
        print(f"⏭️ Descartados {eventos_descartados} eventos antiguos (>{VENTANA_HORAS}h)")
    
    if not eventos_validos:
        print(f"⚠️ No hay eventos recientes (últimas {VENTANA_HORAS}h)")
        return []
    
    print(f"✅ Eventos válidos (últimas {VENTANA_HORAS}h): {len(eventos_validos)}")
    
    # Analizar píxeles en Dist.png (con ROI temporal V17)
    if os.path.exists(img_dist_path):
        analizar_puntos_distancia(eventos_validos, img_dist_path, nombre_v)
    
    # Clasificar y filtrar eventos
    nuevos_eventos = []
    
    print(f"\n📋 PROCESANDO {len(eventos_validos)} EVENTOS INDIVIDUALES:")
    
    for i, evento in enumerate(eventos_validos, 1):
        print(f"\n   {'='*60}")
        print(f"   📌 EVENTO {i}/{len(eventos_validos)}: {evento['Fecha_Satelite_UTC'][5:16]} | {evento.get('VRP_MW', 'N/A')} MW")
        print(f"   {'='*60}")
        
        # Clasificar con sistema 3 fases (V17)
        clasificacion = clasificar_confianza(evento, img_dist_path, nombre_v)
        
        evento.update(clasificacion)
        
        print(f"   📊 CLASIFICACIÓN:")
        print(f"      Tipo: {evento.get('Tipo_Registro', 'N/A')}")
        print(f"      Confianza: {evento.get('Confianza', 'N/A')}")
        print(f"      Guardar: {clasificacion.get('guardar', False)}")
        print(f"      Guardar imágenes: {clasificacion.get('guardar_imagenes', False)}")
        print(f"      Color punto: {evento.get('Color_Punto', 'sin_punto')}")
        print(f"      Nota: {evento.get('Nota', 'N/A')}")
        
        if not clasificacion.get('guardar', False):
            print(f"   ❌ SKIP: guardar=False ({evento.get('Nota', 'Sin razón')})")
            continue
        
        # Verificar duplicados
        es_nuevo = verificar_evento_no_existe(evento, nombre_v, sensor, df_consolidado, df_ocr)
        
        evento['Es_Nuevo'] = 'SI' if es_nuevo else 'NO'
        
        if not es_nuevo:
            print(f"   ⭕ SKIP: Ya existe en CSV (duplicado)")
            continue
        
        # Descargar imágenes si corresponde
        if clasificacion.get('guardar_imagenes', False):
            descargar_imagenes_evento(evento, id_mirova, sensor, nombre_v)
        
        evento['Volcan'] = nombre_v
        evento['Sensor'] = sensor
        evento['Tipo_Registro'] = clasificacion.get('tipo_registro', 'ALERTA_TERMICA_OCR')
        evento['Nivel_Actividad'] = clasificar_nivel_mirova(evento.get('VRP_MW', 0))
        evento['Fecha_Registro'] = ahora_utc.strftime('%Y-%m-%d %H:%M:%S')
        evento['Ultima_Actualizacion'] = ahora_utc.strftime('%Y-%m-%d %H:%M:%S')
        evento['Version_OCR'] = Version_OCR
        
        nuevos_eventos.append(evento)
        print(f"   ✅ NUEVO EVENTO guardado")
    
    print(f"\n{'='*80}")
    print(f"📊 RESUMEN {nombre_v} - {sensor}:")
    print(f"   Total procesados: {len(eventos_validos)}")
    print(f"   Eventos a guardar: {len(nuevos_eventos)}")
    print(f"{'='*80}")
    
    return nuevos_eventos

# [Resto del código igual: descargar_imagenes_evento, clasificar_nivel_mirova, guardar_eventos, main]

def descargar_imagenes_evento(evento, id_mirova, sensor, nombre_volcan):
    """Descarga imágenes Latest y Dist para un evento"""
    # [Código sin cambios]
    pass

def clasificar_nivel_mirova(vrp_mw):
    """Clasifica nivel de actividad según escala MIROVA"""
    # [Código sin cambios]
    pass

def guardar_eventos(nuevos_eventos):
    """Guarda eventos nuevos en CSV"""
    # [Código sin cambios]
    pass

def main():
    """Proceso principal OCR"""
    # [Código sin cambios]
    pass

if __name__ == "__main__":
    main()

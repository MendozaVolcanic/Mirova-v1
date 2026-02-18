"""
SCRAPER_OCR.PY V18 - FILTRO FECHA 24H + ROI TEMPORAL + TUPUNGATITO
BASE: V17 (14 Feb funcionando) + Filtro 24h para evitar eventos antiguos
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
    # ===== NUEVO: TUPUNGATITO =====
    "357010": {"nombre": "Tupungatito", "id_mirova": "Tupungatito"}
}

SENSORES = ["VIIRS375", "VIIRS", "MODIS"]

CARPETA_PRINCIPAL = "monitoreo_satelital"
CARPETA_TEMP = os.path.join(CARPETA_PRINCIPAL, "ocr_temp")
CARPETA_IMAGENES = os.path.join(CARPETA_PRINCIPAL, "imagenes_satelitales")
CARPETA_LOGS = os.path.join(CARPETA_PRINCIPAL, "ocr_logs")

DB_OCR = os.path.join(CARPETA_PRINCIPAL, "registro_vrp_ocr.csv")
DB_CONSOLIDADO = os.path.join(CARPETA_PRINCIPAL, "registro_vrp_consolidado.csv")

COLUMNAS_OCR = [
    "timestamp", "Fecha_Satelite_UTC", "Fecha_Captura_Chile",
    "Volcan", "Sensor", "VRP_MW", "Distancia_km", "Tipo_Registro",
    "Clasificacion Mirova", "Ruta Foto", "Fecha_Proceso_GitHub",
    "Ultima_Actualizacion", "Editado",
    "Color_Punto_Dist", "Confianza_Validacion", "Requiere_Verificacion",
    "Metodo_Validacion", "Nota_Validacion", "Version_OCR"
]

# =========================
# FUNCIONES
# =========================

def descargar_imagen_temp(session, url, ruta_destino):
    """Descarga imagen temporal"""
    try:
        r = session.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=25)
        if r.status_code == 200 and len(r.content) > 5000:
            with open(ruta_destino, 'wb') as f:
                f.write(r.content)
            return True
    except:
        pass
    return False


def descargar_imagenes_permanentes(session, volcan_id, sensor, evento, es_verificar):
    """
    Descarga y guarda imágenes permanentes
    Normalización CONSISTENTE: solo espacios → guión bajo (NO guiones)
    """
    conf = VOLCANES_CONFIG[volcan_id]
    nombre_v = conf["nombre"]
    
    # Solo reemplazar espacios, NO guiones
    nombre_v_normalizado = nombre_v.replace(' ', '_')
    id_mirova = conf["id_mirova"]
    
    dt_utc = evento['datetime']
    f_c = dt_utc.strftime("%Y-%m-%d")
    h_a = dt_utc.strftime("%H-%M-%S")
    
    ruta_dia = os.path.join(CARPETA_IMAGENES, nombre_v_normalizado, f_c)
    os.makedirs(ruta_dia, exist_ok=True)
    
    s_url = "VIIRS750" if sensor == "VIIRS" else sensor
    sufijo = "_VERIFICAR" if es_verificar else ""
    
    tipos = ["VRP", "logVRP", "Latest10NTI", "Dist"]
    ruta_relativa = "No descargada"
    
    for t in tipos:
        if t == "Latest10NTI":
            t_url = "Latest10NTI"
            filename = f"{h_a}_{nombre_v_normalizado}_{s_url}_Latest{sufijo}.png"
        else:
            t_url = t
            filename = f"{h_a}_{nombre_v_normalizado}_{s_url}_{t}{sufijo}.png"
        
        url = f"https://www.mirovaweb.it/OUTPUTweb/MIROVA/{s_url}/VOLCANOES/{id_mirova}/{id_mirova}_{s_url}_{t_url}.png"
        path_f = os.path.join(ruta_dia, filename)
        
        if os.path.exists(path_f):
            if t == "VRP":
                ruta_relativa = f"imagenes_satelitales/{nombre_v_normalizado}/{f_c}/{filename}"
            continue
        
        try:
            r = session.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=25)
            if r.status_code == 200 and len(r.content) > 5000:
                with open(path_f, 'wb') as f:
                    f.write(r.content)
                if t == "VRP":
                    ruta_relativa = f"imagenes_satelitales/{nombre_v_normalizado}/{f_c}/{filename}"
            time.sleep(0.3)
        except:
            continue
    
    return ruta_relativa


def procesar_volcan_sensor(session, volcan_id, sensor, df_ocr, df_consolidado):
    """Procesa un volcán-sensor específico"""
    conf = VOLCANES_CONFIG[volcan_id]
    nombre_v = conf["nombre"]
    id_mirova = conf["id_mirova"]
    
    print(f"\n🔍 Procesando: {nombre_v} - {sensor}")
    
    # URLs de imágenes
    s_url = "VIIRS750" if sensor == "VIIRS" else sensor
    url_latest = f"https://www.mirovaweb.it/OUTPUTweb/MIROVA/{s_url}/VOLCANOES/{id_mirova}/{id_mirova}_{s_url}_Latest10NTI.png"
    url_dist = f"https://www.mirovaweb.it/OUTPUTweb/MIROVA/{s_url}/VOLCANOES/{id_mirova}/{id_mirova}_{s_url}_Dist.png"
    
    # Descargar temporales
    temp_latest = os.path.join(CARPETA_TEMP, f"{nombre_v}_{sensor}_Latest10NTI.png")
    temp_dist = os.path.join(CARPETA_TEMP, f"{nombre_v}_{sensor}_Dist.png")
    
    if not descargar_imagen_temp(session, url_latest, temp_latest):
        print(f"  ⚠️ No se pudo descargar Latest10NTI")
        return []
    
    if not descargar_imagen_temp(session, url_dist, temp_dist):
        print(f"  ⚠️ No se pudo descargar Dist.png")
    
    # OCR de Latest10NTI
    eventos = extraer_eventos_latest10nti(temp_latest)
    
    if not eventos:
        print(f"  ℹ️ No se detectaron eventos")
        return []
    
    # ===== NUEVO V18: FILTRO DE FECHA 24H =====
    ahora_utc = datetime.now(pytz.utc)
    limite_tiempo = ahora_utc - timedelta(hours=24)
    
    eventos_validos = []
    eventos_descartados = 0
    
    for evento in eventos:
        dt_utc = evento['datetime']
        if dt_utc >= limite_tiempo:
            eventos_validos.append(evento)
        else:
            eventos_descartados += 1
    
    if eventos_descartados > 0:
        print(f"  ⏭️ Descartados {eventos_descartados} eventos antiguos (>24h)")
    
    if not eventos_validos:
        print(f"  ℹ️ No hay eventos recientes (últimas 24h)")
        return []
    
    print(f"  ✅ Eventos válidos (últimas 24h): {len(eventos_validos)}")
    eventos = eventos_validos
    # ==============================================
    
    # Análisis RGB de Dist.png (ROI TEMPORAL)
    if os.path.exists(temp_dist):
        eventos = analizar_puntos_distancia(temp_dist, eventos, nombre_v)
    
    # Preparar img_dist_path para FASE 2 (estrella verde)
    img_dist_path = temp_dist if os.path.exists(temp_dist) else None
    
    print(f"\n📋 PROCESANDO {len(eventos)} EVENTOS INDIVIDUALES:")
    
    # Procesar cada evento
    eventos_nuevos = []
    ahora_cl = datetime.now(pytz.timezone('America/Santiago')).strftime("%Y-%m-%d %H:%M:%S")
    
    for i, evento in enumerate(eventos, 1):
        ts = evento['timestamp']
        vrp_mw = evento['vrp_mw']
        dt_utc = evento['datetime']
        fecha_str = dt_utc.strftime('%d-%b %H:%M')
        
        print(f"\n   {'='*60}")
        print(f"   📌 EVENTO {i}/{len(eventos)}: {fecha_str} | {vrp_mw} MW")
        print(f"   {'='*60}")
        
        # Clasificar confianza (3 parámetros)
        clasificacion = clasificar_confianza(evento, img_dist_path, nombre_v)
        
        print(f"   📊 CLASIFICACIÓN:")
        print(f"      Tipo: {clasificacion['tipo_registro']}")
        print(f"      Confianza: {clasificacion['confianza']}")
        print(f"      Guardar: {clasificacion['guardar']}")
        print(f"      Guardar imágenes: {clasificacion.get('guardar_imagenes', False)}")
        print(f"      Color punto: {evento.get('color_punto', 'sin_punto')}")
        print(f"      Nota: {clasificacion['nota']}")
        
        if not clasificacion['guardar']:
            print(f"   ❌ SKIP: guardar=False (VRP inválido)")
            continue
        
        # Verificar duplicados
        print(f"\n   🔍 VERIFICANDO DUPLICADOS:")
        print(f"      Buscando: ts={ts}, volcan={nombre_v}, sensor={sensor}")
        
        es_nuevo = verificar_evento_no_existe(evento, nombre_v, sensor, df_consolidado, df_ocr)
        
        print(f"      ¿Es nuevo? {es_nuevo}")
        
        if not es_nuevo:
            print(f"   ⭕ SKIP: Ya existe en CSV (duplicado)")
            continue
        
        print(f"   ✅ ES NUEVO - Procediendo a guardar")
        
        # Descargar imágenes si es necesario
        guardar_imgs = clasificacion.get('guardar_imagenes', False)
        
        if guardar_imgs:
            print(f"   📥 Descargando imágenes permanentes...")
            es_verificar = clasificacion['requiere_verificacion']
            ruta_foto = descargar_imagenes_permanentes(
                session, volcan_id, sensor, evento, es_verificar
            )
            print(f"      Ruta: {ruta_foto}")
        else:
            ruta_foto = "No descargada - Evento descartado"
            print(f"   💾 Imágenes NO descargadas (FALSO_POSITIVO)")
        
        # Clasificación MIROVA basada en VRP
        if vrp_mw < 0.2:
            clasificacion_mirova = "Muy Bajo"
        elif vrp_mw < 1.0:
            clasificacion_mirova = "Bajo"
        elif vrp_mw < 5.0:
            clasificacion_mirova = "Medio"
        else:
            clasificacion_mirova = "Alto"
        
        # Crear registro
        nuevo_evento = {
            'timestamp': ts,
            'Fecha_Satelite_UTC': dt_utc.strftime("%Y-%m-%d %H:%M:%S"),
            'Fecha_Captura_Chile': dt_utc.replace(tzinfo=pytz.utc).astimezone(
                pytz.timezone('America/Santiago')
            ).strftime("%Y-%m-%d %H:%M:%S"),
            'Volcan': nombre_v,
            'Sensor': sensor,
            'VRP_MW': vrp_mw,
            'Distancia_km': 0.0,
            'Tipo_Registro': clasificacion['tipo_registro'],
            'Clasificacion Mirova': clasificacion_mirova,
            'Ruta Foto': ruta_foto,
            'Fecha_Proceso_GitHub': ahora_cl,
            'Ultima_Actualizacion': ahora_cl,
            'Editado': 'NO',
            'Color_Punto_Dist': evento.get('color_punto', 'sin_punto'),
            'Confianza_Validacion': clasificacion['confianza'],
            'Requiere_Verificacion': clasificacion['requiere_verificacion'],
            'Metodo_Validacion': evento.get('metodo', 'desconocido'),
            'Nota_Validacion': clasificacion['nota'],
            'Version_OCR': '18.0'  # V18: Filtro 24h
        }
        
        eventos_nuevos.append(nuevo_evento)
        print(f"   ✅ AGREGADO A LISTA DE GUARDADO")
    
    print(f"\n{'='*80}")
    print(f"📊 RESUMEN {nombre_v} - {sensor}:")
    print(f"   Total procesados: {len(eventos)}")
    print(f"   Eventos a guardar: {len(eventos_nuevos)}")
    print(f"{'='*80}")
    
    return eventos_nuevos


def procesar():
    """Proceso principal"""
    os.makedirs(CARPETA_PRINCIPAL, exist_ok=True)
    os.makedirs(CARPETA_TEMP, exist_ok=True)
    os.makedirs(CARPETA_LOGS, exist_ok=True)
    
    print("="*80)
    print("🔬 SCRAPER OCR V18 - INICIO (Filtro 24h + ROI Temporal + Tupungatito)")
    print("="*80)
    
    session = requests.Session()
    
    # Cargar CSVs existentes
    df_ocr = pd.read_csv(DB_OCR) if os.path.exists(DB_OCR) else pd.DataFrame(columns=COLUMNAS_OCR)
    df_consolidado = pd.read_csv(DB_CONSOLIDADO) if os.path.exists(DB_CONSOLIDADO) else pd.DataFrame()
    
    print(f"\n📊 CSVs CARGADOS:")
    print(f"   registro_vrp_ocr.csv: {len(df_ocr)} registros")
    print(f"   registro_vrp_consolidado.csv: {len(df_consolidado)} registros")
    
    todos_eventos_nuevos = []
    
    # Procesar cada volcán × sensor
    for volcan_id in VOLCANES_CONFIG.keys():
        for sensor in SENSORES:
            try:
                eventos_nuevos = procesar_volcan_sensor(
                    session, volcan_id, sensor, df_ocr, df_consolidado
                )
                todos_eventos_nuevos.extend(eventos_nuevos)
            except Exception as e:
                print(f"❌ Error en {VOLCANES_CONFIG[volcan_id]['nombre']} {sensor}: {e}")
                import traceback
                traceback.print_exc()
                continue
    
    # Guardar eventos nuevos
    print(f"\n{'='*80}")
    print(f"💾 GUARDANDO EN CSV:")
    print(f"{'='*80}")
    
    if todos_eventos_nuevos:
        print(f"   Eventos a agregar: {len(todos_eventos_nuevos)}")
        
        df_nuevos = pd.DataFrame(todos_eventos_nuevos)
        print(f"   DataFrame creado: {len(df_nuevos)} filas")
        
        df_ocr_final = pd.concat([df_ocr, df_nuevos], ignore_index=True)
        print(f"   CSV final: {len(df_ocr_final)} filas totales")
        
        df_ocr_final = df_ocr_final[COLUMNAS_OCR].sort_values('timestamp', ascending=False)
        
        df_ocr_final.to_csv(DB_OCR, index=False)
        print(f"   ✅ Guardado en: {DB_OCR}")
        
        print(f"\n✅ Se agregaron {len(todos_eventos_nuevos)} eventos nuevos")
        
        # Mostrar eventos guardados
        print(f"\n📝 EVENTOS GUARDADOS:")
        for ev in todos_eventos_nuevos:
            print(f"   - {ev['Fecha_Satelite_UTC']} | {ev['Volcan']} | {ev['Sensor']} | {ev['VRP_MW']} MW | {ev['Tipo_Registro']}")
    else:
        print(f"   ℹ️ No hay eventos nuevos para agregar")
    
    # Limpiar temporales
    import shutil
    if os.path.exists(CARPETA_TEMP):
        shutil.rmtree(CARPETA_TEMP)
        os.makedirs(CARPETA_TEMP)
    
    print(f"\n✅ Proceso completado")
    print("="*80)


if __name__ == "__main__":
    procesar()

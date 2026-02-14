"""
MERGER_MAESTRO.PY V17
Combina registro_vrp_consolidado.csv + registro_vrp_ocr.csv
Genera registro_vrp_maestro_publicable.csv

V17: Compatible con Tupungatito
"""

import pandas as pd
import os

# =========================
# CONFIGURACIÓN
# =========================

CARPETA_PRINCIPAL = "monitoreo_satelital"
DB_CONSOLIDADO = os.path.join(CARPETA_PRINCIPAL, "registro_vrp_consolidado.csv")
DB_OCR = os.path.join(CARPETA_PRINCIPAL, "registro_vrp_ocr.csv")
DB_MAESTRO = os.path.join(CARPETA_PRINCIPAL, "registro_vrp_maestro.csv")

# Columnas del maestro
COLUMNAS_MAESTRO = [
    "timestamp", "Fecha_Satelite_UTC", "Fecha_Captura_Chile",
    "Volcan", "Sensor", "VRP_MW", "Distancia_km", "Tipo_Registro",
    "Clasificacion Mirova", "Ruta Foto",
    "Fecha_Proceso_GitHub", "Ultima_Actualizacion", "Editado",
    "Origen_Dato", "Confianza_Validacion", "Requiere_Verificacion",
    "Nota_Validacion"
]

def actualizar_registros_por_volcan(df_publicable):
    """
    Genera/actualiza CSV individual por volcán desde maestro publicable
    """
    print(f"\n📂 Actualizando registros individuales por volcán...")
    
    volcanes_procesados = 0
    
    for volcan in df_publicable['Volcan'].unique():
        df_volcan = df_publicable[df_publicable['Volcan'] == volcan].copy()
        df_volcan = df_volcan.sort_values('timestamp', ascending=False)
        
        nombre_archivo = volcan.replace(' ', '_').replace('-', '_')
        ruta_csv = os.path.join(CARPETA_PRINCIPAL, f"registro_{nombre_archivo}.csv")
        
        df_volcan.to_csv(ruta_csv, index=False)
        
        volcanes_procesados += 1
        print(f"   ✅ {nombre_archivo}: {len(df_volcan)} eventos")
    
    print(f"   📊 Total volcanes actualizados: {volcanes_procesados}")


def merge():
    """Genera CSV maestro"""
    
    print("="*80)
    print("📄 MERGER V17 - Generando CSV Maestro (+ Tupungatito)")
    print("="*80)
    
    df_consolidado = pd.read_csv(DB_CONSOLIDADO) if os.path.exists(DB_CONSOLIDADO) else pd.DataFrame()
    df_ocr = pd.read_csv(DB_OCR) if os.path.exists(DB_OCR) else pd.DataFrame()
    
    if df_consolidado.empty and df_ocr.empty:
        print("❌ No hay datos para procesar")
        return
    
    # Preparar consolidado
    if not df_consolidado.empty:
        df_consolidado.loc[:, 'Origen_Dato'] = 'latest.php'
        df_consolidado.loc[:, 'Confianza_Validacion'] = 'alta'
        df_consolidado.loc[:, 'Requiere_Verificacion'] = False
        df_consolidado.loc[:, 'Nota_Validacion'] = 'Validado por MIROVA latest.php'
        
        print(f"   📊 Consolidado preparado: {len(df_consolidado)} eventos")
    
    # Preparar OCR
    if not df_ocr.empty:
        df_ocr.loc[:, 'Origen_Dato'] = 'OCR'
        if 'Distancia_km' not in df_ocr.columns:
            df_ocr.loc[:, 'Distancia_km'] = 0.0
        if 'Clasificacion Mirova' not in df_ocr.columns:
            df_ocr.loc[:, 'Clasificacion Mirova'] = 'N/A'
        if 'Ultima_Actualizacion' not in df_ocr.columns:
            df_ocr.loc[:, 'Ultima_Actualizacion'] = df_ocr['Fecha_Proceso_GitHub']
        if 'Editado' not in df_ocr.columns:
            df_ocr.loc[:, 'Editado'] = 'NO'
        
        print(f"   📊 OCR preparado: {len(df_ocr)} eventos")
    
    # Combinar
    df_maestro = pd.concat([df_consolidado, df_ocr], ignore_index=True)
    
    # Detectar duplicados
    df_maestro['duplicado'] = df_maestro.duplicated(
        subset=['timestamp', 'Volcan', 'Sensor'], 
        keep='first'
    )
    
    # Marcar eventos en ambos
    for idx, row in df_maestro[df_maestro['duplicado']].iterrows():
        mask = (
            (df_maestro['timestamp'] == row['timestamp']) &
            (df_maestro['Volcan'] == row['Volcan']) &
            (df_maestro['Sensor'] == row['Sensor']) &
            (~df_maestro['duplicado'])
        )
        df_maestro.loc[mask, 'Origen_Dato'] = 'ambos'
    
    # Eliminar duplicados
    df_maestro = df_maestro[~df_maestro['duplicado']].copy()
    df_maestro.drop(columns=['duplicado'], inplace=True)
    
    # Ordenar
    df_maestro = df_maestro.sort_values('timestamp', ascending=False)
    
    # Seleccionar columnas
    columnas_disponibles = [c for c in COLUMNAS_MAESTRO if c in df_maestro.columns]
    df_maestro = df_maestro[columnas_disponibles]
    
    # Generar maestro publicable
    print(f"\n📝 Generando CSV Maestro PUBLICABLE...")
    
    df_publicable = df_maestro.copy()
    antes = len(df_publicable)
    
    # Filtro 1: Solo tipos ALERTA
    tipos_publicables = ['ALERTA_TERMICA', 'ALERTA_TERMICA_OCR']
    df_publicable = df_publicable[df_publicable['Tipo_Registro'].isin(tipos_publicables)].copy()
    print(f"   Filtro tipo: {antes} → {len(df_publicable)} eventos")
    
    # Filtro 2: Solo VRP > 0
    antes = len(df_publicable)
    df_publicable = df_publicable[df_publicable['VRP_MW'] > 0].copy()
    print(f"   Filtro VRP>0: {antes} → {len(df_publicable)} eventos")
    
    # Filtro 3: Confianza válida
    antes = len(df_publicable)
    if 'Confianza_Validacion' in df_publicable.columns:
        df_publicable = df_publicable[df_publicable['Confianza_Validacion'] != 'invalido'].copy()
        print(f"   Filtro confianza: {antes} → {len(df_publicable)} eventos")
    
    # Guardar SOLO publicable
    DB_PUBLICABLE = DB_MAESTRO.replace('.csv', '_publicable.csv')
    df_publicable.to_csv(DB_PUBLICABLE, index=False)
    
    print(f"\n✅ CSV Maestro PUBLICABLE generado:")
    print(f"   Total eventos: {len(df_publicable)}")
    print(f"   Archivo: {DB_PUBLICABLE}")
    
    # Actualizar registros individuales
    actualizar_registros_por_volcan(df_publicable)
    
    # Estadísticas
    if not df_publicable.empty:
        print(f"\n📊 Composición:")
        for tipo in df_publicable['Tipo_Registro'].unique():
            count = len(df_publicable[df_publicable['Tipo_Registro'] == tipo])
            print(f"   {tipo}: {count} eventos")
        
        if 'Confianza_Validacion' in df_publicable.columns:
            print(f"\n📊 Por confianza:")
            for conf in df_publicable['Confianza_Validacion'].unique():
                count = len(df_publicable[df_publicable['Confianza_Validacion'] == conf])
                print(f"   {conf}: {count} eventos")
    
    # Eventos excluidos
    df_excluidos = df_maestro[~df_maestro['Tipo_Registro'].isin(tipos_publicables)]
    if not df_excluidos.empty:
        print(f"\n📋 Eventos EXCLUIDOS:")
        for tipo in df_excluidos['Tipo_Registro'].unique():
            count = len(df_excluidos[df_excluidos['Tipo_Registro'] == tipo])
            print(f"   {tipo}: {count} eventos")
    
    print(f"\n📝 Nota: FALSO_POSITIVO_OCR solo en registro_vrp_ocr.csv")
    print("="*80)


if __name__ == "__main__":
    merge()

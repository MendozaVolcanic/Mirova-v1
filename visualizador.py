import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os
import pytz
from datetime import datetime, timedelta

# --- CONFIGURACIÓN ---
ARCHIVO_MAESTRO = "monitoreo_satelital/registro_vrp_maestro_publicable.csv"
ARCHIVO_MAESTRO_COMPLETO = "monitoreo_satelital/registro_vrp_maestro.csv"
ARCHIVO_POSITIVOS = "monitoreo_satelital/registro_vrp_positivos.csv"
CARPETA_LINEAL = "monitoreo_satelital/v_html"
CARPETA_LOG = "monitoreo_satelital/v_html_log"

# ========================================
# FIX: Nombres consistentes con scraper.py y CSVs
# - "PlanchonPeteroa" (NO "Peteroa")
# - "Puyehue-Cordon Caulle" (con guión)
# ========================================
VOLCANES = [
    "Isluga", "Lascar", "Lastarria",
    "PlanchonPeteroa",  # ✅ FIX: era "Peteroa"
    "Nevados de Chillan", "Copahue", "Llaima", "Villarrica",
    "Puyehue-Cordon Caulle",
    "Chaiten"
]

MAPA_SIMBOLOS = {"MODIS": "triangle-up", "VIIRS375": "square", "VIIRS750": "circle", "VIIRS": "circle"}

# ========================================
# FIX: Sistema unificado de confianzas
# - 'alta' (antes 'valido' y 'N/A')
# - 'media', 'baja'
# ========================================
COLORES_CONFIANZA = {
    "N/A": "#2ea043",      # Legacy (por si hay datos antiguos)
    "valido": "#2ea043",   # Legacy (por si hay datos antiguos)
    "alta": "#2ea043",     # ✅ Verde - Confiable
    "media": "#d29922",    # ✅ Amarillo - Requiere verificación
    "baja": "#fb8500"      # ✅ Naranja - Dudoso
}

MESES_ES = {1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun", 7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"}

# ========================================
# CORRECCIÓN: Bandas correctas
# - Escala lineal: desde 0 MW
# - Escala log: desde 10^5 W (0.1 MW)
# ========================================
MIROVA_BANDS = [
    (0,     1e6,  "Muy Bajo", "rgba(128, 128, 128, 0.2)"),   # Gris: 0-1 MW (lineal) | 10^5-10^6 W (log)
    (1e6,   1e7,  "Bajo",     "rgba(34, 139, 34, 0.15)"),    # Verde: 1-10 MW
    (1e7,   1e8,  "Moderado", "rgba(255, 215, 0, 0.15)"),    # Amarillo: 10-100 MW
    (1e8,   1e9,  "Alto",     "rgba(255, 140, 0, 0.15)"),    # Naranja: 100-1000 MW
    (1e9,   1e10, "Muy Alto", "rgba(220, 20, 60, 0.15)")     # Rojo: 1000+ MW
]

def crear_grafico(df_v, v, modo_log=False):
    tz_chile = pytz.timezone('America/Santiago')
    ahora = datetime.now(tz_chile)
    hace_30_dias = (ahora - timedelta(days=30)).replace(hour=0, minute=0, second=0)
    
    df_v_30 = pd.DataFrame()
    if not df_v.empty:
        df_v['Fecha_UTC'] = pd.to_datetime(df_v['Fecha_Satelite_UTC']).dt.tz_localize('UTC')
        df_v['Fecha_Chile_temp'] = df_v['Fecha_UTC'].dt.tz_convert('America/Santiago')
        df_v_30 = df_v[df_v['Fecha_Chile_temp'] >= hace_30_dias].copy()
        df_v_30 = df_v_30[df_v_30['VRP_MW'] > 0].copy()

    if df_v_30.empty: return None

    unidad = "Watt" if modo_log else "MW"
    fig = go.Figure()
    v_max_val = df_v_30['VRP_MW'].max()
    
    # ========================================
    # CORRECCIÓN: Transform diferenciado
    # ========================================
    def transform(val_mw):
        if modo_log:
            watts = val_mw * 1e6
            return np.log10(max(watts, 1e4))
        else:
            return val_mw
    
    v_max_val_watts = v_max_val * 1e6
    
    # Bandas de color
    for y0, y1, label, color in MIROVA_BANDS:
        if modo_log:
            if y0 == 0:
                l_y0 = np.log10(1e5)
            else:
                l_y0 = np.log10(max(y0, 1e5))
            
            l_y1 = np.log10(y1)
        else:
            l_y0 = y0 / 1e6
            l_y1 = y1 / 1e6
        
        fig.add_hrect(y0=l_y0, y1=l_y1, fillcolor=color, line_width=0, layer="below")
        
        # Mostrar en leyenda si hay datos en ese rango
        if modo_log:
            rango_inicio = 1e5 if y0 == 0 else y0
            if v_max_val_watts >= rango_inicio:
                fig.add_trace(go.Scatter(
                    x=[None], y=[None],
                    mode='markers',
                    marker=dict(size=0),
                    showlegend=True,
                    name=f"{label}",
                    legendgroup='bandas',
                    hoverinfo='skip'
                ))
        else:
            rango_inicio_mw = y0 / 1e6
            if v_max_val >= rango_inicio_mw:
                fig.add_trace(go.Scatter(
                    x=[None], y=[None],
                    mode='markers',
                    marker=dict(size=0),
                    showlegend=True,
                    name=f"{label}",
                    legendgroup='bandas',
                    hoverinfo='skip'
                ))
    
    # ========================================
    # FIX CRÍTICO: Confianza_Validacion OPCIONAL
    # ========================================
    tiene_confianza = 'Confianza_Validacion' in df_v_30.columns
    
    if tiene_confianza:
        # Agrupar por sensor Y confianza
        grupos = df_v_30.groupby(['Sensor', 'Confianza_Validacion'])
    else:
        # Solo agrupar por sensor (modo legacy)
        grupos = df_v_30.groupby(['Sensor'])
    
    for grupo_key, grupo in grupos:
        # Manejar tanto tuplas (Sensor, Confianza) como strings (solo Sensor)
        if isinstance(grupo_key, tuple):
            sensor, confianza = grupo_key
        else:
            sensor = grupo_key
            confianza = None
        
        simbolo = MAPA_SIMBOLOS.get(sensor, "circle")
        
        # Color según confianza (si existe)
        if confianza:
            color = COLORES_CONFIANZA.get(confianza, "#808080")
        else:
            color = "#2ea043"  # Verde por defecto
        
        x_fechas = grupo['Fecha_Chile_temp']
        y_valores = grupo['VRP_MW'].apply(transform)
        
        # Hover text
        hover_texts = []
        for idx, row in grupo.iterrows():
            fecha_chile = row['Fecha_Chile_temp'].strftime('%d-%b %H:%M')
            vrp_mw = row['VRP_MW']
            vrp_w = int(vrp_mw * 1e6)
            
            # Formatear VRP según escala
            if modo_log:
                vrp_display = f"{vrp_w:,} W"
            else:
                vrp_display = f"{vrp_mw:.2f} MW"
            
            dist_km = row.get('Distancia_km', 0)
            
            # Confianza solo si existe
            if tiene_confianza and confianza:
                conf_texto = confianza
            else:
                conf_texto = "N/A"
            
            hover_texts.append(
                f"<b>{fecha_chile}</b><br>" +
                f"VRP: {vrp_display}<br>" +
                f"Distancia: {dist_km:.2f} km<br>" +
                f"Sensor: {sensor}<br>" +
                f"Confianza: {conf_texto}"
            )
        
        # Nombre de leyenda
        nombre_leyenda = f"{sensor}"
        if tiene_confianza and confianza and confianza not in ["N/A", "valido"]:
            nombre_leyenda += f" ({confianza})"
        
        fig.add_trace(go.Scatter(
            x=x_fechas,
            y=y_valores,
            mode='markers',
            marker=dict(
                symbol=simbolo,
                size=10,
                color=color,
                line=dict(width=1, color='white')
            ),
            name=nombre_leyenda,
            text=hover_texts,
            hovertemplate='%{text}<extra></extra>',
            legendgroup='sensores',
            showlegend=True
        ))
    
    # Configuración de ejes
    if modo_log:
        y_min_log = np.log10(1e5)
        y_max_log = np.log10(v_max_val_watts)
        y_max_log = max(y_max_log + 0.3, y_min_log + 1)
        
        fig.update_yaxes(
            title=f"VRP ({unidad})",
            range=[y_min_log, y_max_log],
            tickvals=[5, 6, 7, 8, 9, 10],
            ticktext=["10⁵", "10⁶", "10⁷", "10⁸", "10⁹", "10¹⁰"],
            gridcolor='rgba(128, 128, 128, 0.2)',
            showgrid=True
        )
    else:
        y_max_lineal = v_max_val
        y_max_lineal = max(y_max_lineal * 1.1, 0.1)
        
        fig.update_yaxes(
            title=f"VRP ({unidad})",
            range=[0, y_max_lineal],
            gridcolor='rgba(128, 128, 128, 0.2)',
            showgrid=True
        )
    
    fig.update_xaxes(
        title="Fecha (Hora Chile)",
        gridcolor='rgba(128, 128, 128, 0.2)',
        showgrid=True,
        tickformat='%d-%b'
    )
    
    # Título con última actualización
    titulo = f"{v} - Últimos 30 días"
    if not df_v_30.empty:
        ultima_fecha = df_v_30['Fecha_Chile_temp'].max().strftime('%d-%b-%Y %H:%M')
        titulo += f"<br><sub>Última detección: {ultima_fecha}</sub>"
    
    # ========================================
    # FIX: Fondo NEGRO para exportar a PPT
    # ========================================
    fig.update_layout(
        title=dict(
            text=titulo,
            x=0.5,
            xanchor='center',
            font=dict(size=18, color='white')
        ),
        paper_bgcolor='black',     # ✅ Fondo negro exterior
        plot_bgcolor='#1a1a1a',    # ✅ Fondo negro gráfico
        font=dict(color='white'),  # ✅ Texto blanco
        hovermode='closest',
        legend=dict(
            bgcolor='rgba(0, 0, 0, 0.7)',
            bordercolor='rgba(255, 255, 255, 0.3)',
            borderwidth=1,
            font=dict(color='white')
        ),
        margin=dict(l=60, r=40, t=80, b=60),
        height=500
    )
    
    return fig

def main():
    print("="*80)
    print("📊 GENERADOR DE GRÁFICOS")
    print("="*80)
    
    os.makedirs(CARPETA_LINEAL, exist_ok=True)
    os.makedirs(CARPETA_LOG, exist_ok=True)
    
    # Cargar datos
    if not os.path.exists(ARCHIVO_POSITIVOS):
        print(f"❌ No se encontró: {ARCHIVO_POSITIVOS}")
        return
    
    df = pd.read_csv(ARCHIVO_POSITIVOS)
    print(f"\n📂 Cargados {len(df)} eventos de: {ARCHIVO_POSITIVOS}")
    
    # Mostrar nombres únicos de volcanes en CSV
    volcanes_en_csv = df['Volcan'].unique()
    print(f"\n🌋 Volcanes en CSV:")
    for v_csv in sorted(volcanes_en_csv):
        print(f"   - {v_csv}")
    
    # Verificar si existe columna Confianza_Validacion
    tiene_confianza_csv = 'Confianza_Validacion' in df.columns
    if tiene_confianza_csv:
        print(f"\n✅ Columna 'Confianza_Validacion' detectada")
    else:
        print(f"\n⚠️ Columna 'Confianza_Validacion' NO existe (modo legacy)")
    
    # Generar gráficos
    total_lineal = 0
    total_log = 0
    
    for v in VOLCANES:
        print(f"\n🌋 Procesando: {v}")
        
        # ========================================
        # FIX: Buscar nombre exacto en CSV
        # ========================================
        df_v = df[df['Volcan'] == v].copy()
        
        if df_v.empty:
            print(f"   ⚠️ No hay datos en CSV para '{v}'")
            print(f"   💡 Verifica que el nombre coincida con scraper.py")
            continue
        
        print(f"   ✅ {len(df_v)} eventos encontrados")
        
        # Gráfico lineal
        fig_lineal = crear_grafico(df_v, v, modo_log=False)
        if fig_lineal:
            # Normalizar nombre para archivo (sin espacios ni guiones)
            nombre_archivo = v.replace(' ', '_').replace('-', '_')
            path_lineal = os.path.join(CARPETA_LINEAL, f"{nombre_archivo}.html")
            
            # ========================================
            # FIX: config para fondo negro al exportar
            # ========================================
            fig_lineal.write_html(
                path_lineal,
                config={
                    'toImageButtonOptions': {
                        'format': 'png',
                        'filename': f'{nombre_archivo}_lineal',
                        'height': 500,
                        'width': 1200,
                        'scale': 2
                    },
                    'displaylogo': False,
                    'modeBarButtonsToRemove': ['pan2d', 'lasso2d', 'select2d']
                }
            )
            
            total_lineal += 1
            print(f"   ✅ Gráfico lineal: {nombre_archivo}.html")
        else:
            print(f"   ⚠️ Sin datos en últimos 30 días (gráfico lineal)")
        
        # Gráfico logarítmico
        fig_log = crear_grafico(df_v, v, modo_log=True)
        if fig_log:
            nombre_archivo = v.replace(' ', '_').replace('-', '_')
            path_log = os.path.join(CARPETA_LOG, f"{nombre_archivo}.html")
            
            fig_log.write_html(
                path_log,
                config={
                    'toImageButtonOptions': {
                        'format': 'png',
                        'filename': f'{nombre_archivo}_log',
                        'height': 500,
                        'width': 1200,
                        'scale': 2
                    },
                    'displaylogo': False,
                    'modeBarButtonsToRemove': ['pan2d', 'lasso2d', 'select2d']
                }
            )
            
            total_log += 1
            print(f"   ✅ Gráfico log: {nombre_archivo}.html")
        else:
            print(f"   ⚠️ Sin datos en últimos 30 días (gráfico log)")
    
    print(f"\n{'='*80}")
    print(f"✅ PROCESO COMPLETADO")
    print(f"{'='*80}")
    print(f"   Gráficos lineales: {total_lineal}")
    print(f"   Gráficos logarítmicos: {total_log}")
    print(f"\n📁 Ubicación:")
    print(f"   Lineal: {CARPETA_LINEAL}/")
    print(f"   Log: {CARPETA_LOG}/")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()

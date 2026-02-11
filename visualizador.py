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
VOLCANES = ["Isluga", "Lascar", "Lastarria", "PlanchonPeteroa", "Nevados de Chillan", "Copahue", "Llaima", "Villarrica", "Puyehue-Cordon Caulle", "Chaiten"]

MAPA_SIMBOLOS = {"MODIS": "triangle-up", "VIIRS375": "square", "VIIRS750": "circle", "VIIRS": "circle"}
COLORES_CONFIANZA = {
    "N/A": "#2ea043",
    "valido": "#2ea043",
    "alta": "#2ea043",
    "media": "#d29922",
    "baja": "#fb8500"
}
MESES_ES = {1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun", 7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"}

MIROVA_BANDS = [
    (0,     1e6,  "Muy Bajo", "rgba(128, 128, 128, 0.2)"),
    (1e6,   1e7,  "Bajo",     "rgba(34, 139, 34, 0.15)"),
    (1e7,   1e8,  "Moderado", "rgba(255, 215, 0, 0.15)"),
    (1e8,   1e9,  "Alto",     "rgba(255, 140, 0, 0.15)"),
    (1e9,   1e10, "Muy Alto", "rgba(220, 20, 60, 0.15)")
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
        
        if modo_log:
            rango_inicio = 1e5 if y0 == 0 else y0
            if v_max_val_watts >= rango_inicio:
                fig.add_trace(go.Scatter(
                    x=[None], y=[None],
                    mode='markers',
                    name=label,
                    marker=dict(
                        size=8,
                        symbol='square',
                        color=color.replace('0.2', '0.8').replace('0.15', '0.8')
                    ),
                    showlegend=True
                ))
        else:
            if v_max_val_watts >= y0:
                fig.add_trace(go.Scatter(
                    x=[None], y=[None],
                    mode='markers',
                    name=label,
                    marker=dict(
                        size=8,
                        symbol='square',
                        color=color.replace('0.2', '0.8').replace('0.15', '0.8')
                    ),
                    showlegend=True
                ))

    # Función para generar URLs a imágenes
    def generar_url_imagenes(row):
        ruta_foto = row.get('Ruta Foto', 'No descargada')
        
        if pd.isna(ruta_foto) or ruta_foto == 'No descargada' or 'descartado' in str(ruta_foto).lower():
            return None
        
        partes = ruta_foto.split('/')
        if len(partes) >= 4:
            volcan_carpeta = partes[1]
            fecha_carpeta = partes[2]
            volcan_normalizado = volcan_carpeta.replace('-', '_').replace(' ', '_')
            url_github = f"https://github.com/MendozaVolcanic/Mirova-v1/tree/main/monitoreo_satelital/imagenes_satelitales/{volcan_normalizado}/{fecha_carpeta}"
            return url_github
        
        return None

    # ========================================
    # FIX 1: Almacenar URLs para hacer clickeable
    # ========================================
    # Traces por sensor y confianza
    for sensor in df_v_30['Sensor'].unique():
        df_sensor = df_v_30[df_v_30['Sensor'] == sensor]
        
        for confianza in ['N/A', 'valido', 'alta', 'media', 'baja']:
            if 'Confianza_Validacion' in df_sensor.columns:
                df_grupo = df_sensor[df_sensor['Confianza_Validacion'] == confianza]
            else:
                df_grupo = df_sensor.copy()
                confianza = 'N/A'
            
            if df_grupo.empty:
                continue
            
            hover_texts = []
            customdata_urls = []  # ✅ Lista de URLs para customdata
            
            for _, row in df_grupo.iterrows():
                url_github = generar_url_imagenes(row)
                
                # Hover text (mostrar link)
                if url_github:
                    hover_texts.append(
                        f"<b>{row['Fecha_Satelite_UTC']}</b><br>"
                        f"{row['VRP_MW']:.2f} MW<br>"
                        f"{row['Sensor']}<br>"
                        f"Dist: {row['Distancia_km']:.1f} km<br>"
                        f"Conf: {row.get('Confianza_Validacion', 'N/A')}<br>"
                        f"<i>Click para ver carpeta</i>"
                    )
                    customdata_urls.append(url_github)
                else:
                    hover_texts.append(
                        f"<b>{row['Fecha_Satelite_UTC']}</b><br>"
                        f"{row['VRP_MW']:.2f} MW<br>"
                        f"{row['Sensor']}<br>"
                        f"Dist: {row['Distancia_km']:.1f} km<br>"
                        f"Conf: {row.get('Confianza_Validacion', 'N/A')}"
                    )
                    customdata_urls.append(None)
            
            df_grupo['VRP_Transformed'] = df_grupo['VRP_MW'].apply(transform)
            
            fig.add_trace(go.Scatter(
                x=df_grupo['Fecha_UTC'],
                y=df_grupo['VRP_Transformed'],
                mode='markers',
                name=sensor,
                marker=dict(
                    size=6,
                    symbol=MAPA_SIMBOLOS.get(sensor, 'circle'),
                    color=COLORES_CONFIANZA.get(confianza, '#2ea043'),
                    line=dict(width=0.5, color='white')
                ),
                hovertemplate='%{text}<extra></extra>',
                text=hover_texts,
                customdata=customdata_urls,  # ✅ Almacenar URLs
                showlegend=True
            ))

    # ========================================
    # FIX 2: Fecha actual en eje X (CORREGIDO)
    # ========================================
    MESES_ES_DICT = {
        'Jan': 'Ene', 'Feb': 'Feb', 'Mar': 'Mar', 'Apr': 'Abr',
        'May': 'May', 'Jun': 'Jun', 'Jul': 'Jul', 'Aug': 'Ago',
        'Sep': 'Sep', 'Oct': 'Oct', 'Nov': 'Nov', 'Dec': 'Dic'
    }
    
    tick_dates = []
    tick_labels = []
    
    # Calcular días transcurridos desde hace_30_dias hasta ahora
    dias_totales = (ahora - hace_30_dias).days
    
    # Generar ticks cada ~5 días
    # Si han pasado 30 días: 0, 5, 10, 15, 20, 25, 30
    num_ticks_intermedios = 6  # 6 ticks + fecha actual = 7 total
    
    for i in range(num_ticks_intermedios):
        dias_offset = int((dias_totales / num_ticks_intermedios) * i)
        fecha = hace_30_dias + timedelta(days=dias_offset)
        tick_dates.append(fecha)
        
        label_en = fecha.strftime("%d %b")
        for en, es in MESES_ES_DICT.items():
            label_en = label_en.replace(en, es)
        tick_labels.append(label_en)
    
    # ✅ TICK FINAL: FECHA ACTUAL (hoy)
    tick_dates.append(ahora)
    label_actual = ahora.strftime("%d %b")
    for en, es in MESES_ES_DICT.items():
        label_actual = label_actual.replace(en, es)
    tick_labels.append(label_actual)
    
    fig.update_xaxes(
        type="date",
        range=[hace_30_dias, ahora],
        tickmode='array',
        tickvals=tick_dates,
        ticktext=tick_labels,
        showgrid=True,
        gridcolor='rgba(255,255,255,0.12)',
        minor=dict(dtick=86400000.0, showgrid=True, gridcolor='rgba(255,255,255,0.03)'),
        tickangle=-45,
        fixedrange=True,
        tickfont=dict(size=9)
    )
    
    # Eje Y
    if modo_log:
        fig.update_yaxes(
            type="linear",
            range=[4.7, 9],
            tickvals=[5, 6, 7, 8],
            ticktext=["10⁵", "10⁶", "10⁷", "10⁸"],
            gridcolor='rgba(255,255,255,0.05)',
            tickfont=dict(size=9),
            autorange=False,
            fixedrange=True
        )
    else:
        fig.update_yaxes(
            type="linear",
            range=[0, max(1.1, v_max_val * 1.5)],
            gridcolor='rgba(255,255,255,0.05)',
            tickfont=dict(size=9),
            fixedrange=True
        )
    
    # Etiqueta de unidad
    fig.add_annotation(
        xref="paper",
        yref="paper",
        x=-0.01,
        y=1.15,
        text=f"<b>{unidad}</b>",
        showarrow=False,
        font=dict(size=10, color="white"),
        xanchor="right"
    )
    
    # Anotación MAX
    if not df_v_30.empty:
        max_r = df_v_30.loc[df_v_30['VRP_MW'].idxmax()]
        y_pos = transform(max_r['VRP_MW'])
        
        fecha_max = max_r['Fecha_UTC']
        dias_desde_inicio = (fecha_max - hace_30_dias).total_seconds() / 86400
        proporcion_x = dias_desde_inicio / 30
        
        if proporcion_x > 0.85:
            ax = -60
        elif proporcion_x < 0.15:
            ax = 60
        else:
            ax = 0
        
        fig.add_annotation(
            x=fecha_max,
            y=y_pos,
            xref="x",
            yref="y",
            text=f"MÁX: {max_r['VRP_MW']:.2f} MW",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=1.5,
            arrowcolor="white",
            bgcolor="rgba(0,0,0,0.8)",
            bordercolor="#58a6ff",
            borderwidth=1,
            font=dict(color="white", size=9),
            ay=-40,
            ax=ax
        )
    
    # Layout
    fig.update_layout(
        template="plotly_dark",
        height=300,
        margin=dict(l=40, r=2, t=35, b=40),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=True,
        legend=dict(
            orientation="h", 
            yanchor="bottom", 
            y=1.03, 
            xanchor="center", 
            x=0.5, 
            font=dict(size=11)
        ),
        autosize=True,
        width=None
    )
    
    return fig

def procesar():
    os.makedirs(CARPETA_LINEAL, exist_ok=True)
    os.makedirs(CARPETA_LOG, exist_ok=True)
    
    if os.path.exists(ARCHIVO_MAESTRO):
        df = pd.read_csv(ARCHIVO_MAESTRO)
        print(f"📊 Leyendo {ARCHIVO_MAESTRO}: {len(df)} eventos")
    elif os.path.exists(ARCHIVO_MAESTRO_COMPLETO):
        df = pd.read_csv(ARCHIVO_MAESTRO_COMPLETO)
        print(f"⚠️ Maestro publicable no existe, usando completo: {len(df)} eventos")
        
        if not df.empty:
            antes = len(df)
            
            if 'Tipo_Registro' in df.columns:
                tipos_ok = ['ALERTA_TERMICA', 'ALERTA_TERMICA_OCR', 'EVIDENCIA_DIARIA']
                df = df[df['Tipo_Registro'].isin(tipos_ok)].copy()
            
            df = df[df['VRP_MW'] > 0].copy()
            
            if 'Confianza_Validacion' in df.columns:
                df = df[df['Confianza_Validacion'] != 'baja'].copy()
            
            print(f"   Filtrado: {antes} → {len(df)} eventos")
    else:
        df = pd.read_csv(ARCHIVO_POSITIVOS) if os.path.exists(ARCHIVO_POSITIVOS) else pd.DataFrame()
        if not df.empty:
            df['Confianza_Validacion'] = 'valido'
    
    config_lineal = {
        'displayModeBar': True,
        'displaylogo': False,
        'responsive': True,
        'modeBarButtonsToRemove': ['select2d', 'lasso2d'],
        'toImageButtonOptions': {
            'format': 'jpeg',
            'filename': 'grafico_volcan',
            'height': 500,
            'width': 1400,
            'scale': 2
        }
    }
    
    config_log = {
        'displayModeBar': True,
        'displaylogo': False,
        'responsive': False,
        'modeBarButtonsToRemove': ['select2d', 'lasso2d'],
        'toImageButtonOptions': {
            'format': 'jpeg',
            'filename': 'grafico_volcan_log',
            'height': 500,
            'width': 1400,
            'scale': 2
        }
    }

    for v in VOLCANES:
        df_v = df[df['Volcan'] == v].copy()
        nombre_f = f"{v.replace(' ', '_').replace('-', '_')}.html"
        
        for carpeta, es_log in [(CARPETA_LINEAL, False), (CARPETA_LOG, True)]:
            fig = crear_grafico(df_v, v, modo_log=es_log)
            path = os.path.join(carpeta, nombre_f)
            
            if fig is None:
                html_sin_datos = f"""
                <!DOCTYPE html>
                <html><head><meta charset="UTF-8"><title>{v}</title></head>
                <body style="background-color:#0d1117;color:#c9d1d9;font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
                <div style="text-align:center;">
                <h2 style="color:#8b949e;font-weight:400;">SIN ANOMALÍA TÉRMICA</h2>
                <p style="color:#6e7681;font-size:0.9em;">Últimos 30 días</p>
                </div>
                </body></html>
                """
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(html_sin_datos)
                continue
            
            cfg = config_log if es_log else config_lineal
            
            # ========================================
            # FIX 1: Agregar JavaScript para clicks
            # ========================================
            html_base = fig.to_html(config=cfg, include_plotlyjs='cdn')
            
            # Inyectar JavaScript para manejar clicks
            script_click = """
<script>
document.addEventListener('DOMContentLoaded', function() {
    var plotDiv = document.getElementsByClassName('plotly-graph-div')[0];
    if (plotDiv) {
        plotDiv.on('plotly_click', function(data) {
            var point = data.points[0];
            if (point.customdata) {
                var url = point.customdata;
                if (url) {
                    window.open(url, '_blank');
                }
            }
        });
    }
});
</script>
</body>
"""
            html_final = html_base.replace('</body>', script_click)
            
            with open(path, 'w', encoding='utf-8') as f:
                f.write(html_final)

    # Estado del sistema
    ahora_utc = datetime.now(pytz.UTC)
    estado = {
        "estado": "✅ Operativo",
        "color": "#2ea043",
        "ultima_actualizacion": ahora_utc.strftime("%Y-%m-%d %H:%M UTC")
    }
    
    with open("monitoreo_satelital/estado_sistema.json", "w") as f:
        import json
        json.dump(estado, f, indent=2)
    
    print(f"\n✅ Gráficos generados para {len(VOLCANES)} volcanes")

if __name__ == "__main__":
    procesar()

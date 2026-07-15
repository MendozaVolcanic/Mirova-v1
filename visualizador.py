import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os
import pytz
from datetime import datetime, timedelta

ARCHIVO_MAESTRO = "monitoreo_satelital/registro_vrp_maestro_publicable.csv"
ARCHIVO_POSITIVOS = "monitoreo_satelital/registro_vrp_positivos.csv"
CARPETA_LINEAL = "monitoreo_satelital/v_html"
CARPETA_LOG = "monitoreo_satelital/v_html_log"
# Overlay de curaduria humana: detecciones marcadas a mano como falso positivo /
# artefacto (cirrus, etc.). NO se borran del dato crudo; solo cambian como se
# grafican (se excluyen de la escala y van a una traza aparte). Ver marcar_artefacto.yml.
ARCHIVO_ANOTACIONES = "monitoreo_satelital/anotaciones.csv"

# Lista de volcanes y datos del dashboard desde la fuente única (volcanes.py)
from volcanes import LISTA_VOLCANES as VOLCANES, DASHBOARD

MAPA_SIMBOLOS = {"MODIS": "triangle-up", "VIIRS375": "square", "VIIRS750": "circle", "VIIRS": "circle"}

COLORES_SENSOR = {
    "MODIS": "#2ea043",
    "VIIRS375": "#2ea043",
    "VIIRS": "#2ea043",
    "VIIRS750": "#2ea043"
}

COLORES_CONFIANZA_ESPECIAL = {
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

def cargar_anotaciones():
    """Lee anotaciones.csv y devuelve {(timestamp, Volcan): motivo}. El dato crudo
    NO se toca; esto solo afecta la visualizacion. Si el archivo no existe devuelve
    {} (comportamiento identico al actual)."""
    d = {}
    if not os.path.exists(ARCHIVO_ANOTACIONES):
        return d
    try:
        a = pd.read_csv(ARCHIVO_ANOTACIONES, dtype=str).fillna('')
    except Exception as e:
        print(f"⚠️ No se pudo leer {ARCHIVO_ANOTACIONES}: {e}")
        return d
    for _, r in a.iterrows():
        ts = str(r.get('timestamp', '')).strip()
        vol = str(r.get('Volcan', '')).strip()
        if not ts or not vol:
            continue
        try:
            ts = str(int(float(ts)))
        except ValueError:
            pass
        d[(ts, vol)] = str(r.get('motivo', '')).strip()
    return d


def crear_grafico(df_v, v, modo_log=False, anotaciones_v=None):
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

    # --- Capa de curaduria: separar detecciones marcadas como artefacto ----------
    # Los marcados se EXCLUYEN del autoescalado del eje Y (para no aplastar la senal
    # real) y se dibujan aparte (gris, apagados por defecto). No se borra nada.
    anotaciones_v = anotaciones_v or {}
    def _ts_key(x):
        try:
            return str(int(float(x)))
        except (ValueError, TypeError):
            return str(x).strip()
    df_v_30['_es_artefacto'] = df_v_30['timestamp'].apply(_ts_key).isin(set(anotaciones_v.keys()))
    df_normal = df_v_30[~df_v_30['_es_artefacto']].copy()
    df_arte = df_v_30[df_v_30['_es_artefacto']].copy()

    unidad = "Watt" if modo_log else "MW"
    fig = go.Figure()
    v_max_val = df_normal['VRP_MW'].max() if not df_normal.empty else 1.0
    
    def transform(val_mw):
        if modo_log:
            watts = val_mw * 1e6
            return np.log10(max(watts, 1e4))
        else:
            return val_mw
    
    v_max_val_watts = v_max_val * 1e6
    
    # ========================================
    # FIX 1: Bandas SIN agregar a leyenda
    # ========================================
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
        
        # Dibujar rectángulo de fondo PERO sin agregarlo a la leyenda
        fig.add_hrect(y0=l_y0, y1=l_y1, fillcolor=color, line_width=0, layer="below")
        
        # ❌ NO agregar trace a leyenda (comentado)
        # if v_max_val_watts >= y0:
        #     fig.add_trace(go.Scatter(..., showlegend=True))

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

    sensores_agregados = set()
    
    for sensor in df_normal['Sensor'].unique():
        df_sensor = df_normal[df_normal['Sensor'] == sensor].copy()
        
        hover_texts = []
        customdata_urls = []
        colores_puntos = []
        
        for _, row in df_sensor.iterrows():
            url_github = generar_url_imagenes(row)
            
            tipo_registro = row.get('Tipo_Registro', 'N/A')
            if 'OCR' in tipo_registro:
                fuente = "OCR"
            elif 'ALERTA_TERMICA' in tipo_registro:
                fuente = "Latest.php"
            else:
                fuente = "N/A"
            
            confianza = row.get('Confianza_Validacion', 'N/A')
            
            if url_github:
                hover_texts.append(
                    f"<b>{row['Fecha_Satelite_UTC']}</b><br>"
                    f"{row['VRP_MW']:.2f} MW<br>"
                    f"{row['Sensor']}<br>"
                    f"Dist: {row['Distancia_km']:.1f} km<br>"
                    f"Conf: {confianza}<br>"
                    f"Fuente: {fuente}<br>"
                    f"<i>Click para ver carpeta</i>"
                )
                customdata_urls.append(url_github)
            else:
                hover_texts.append(
                    f"<b>{row['Fecha_Satelite_UTC']}</b><br>"
                    f"{row['VRP_MW']:.2f} MW<br>"
                    f"{row['Sensor']}<br>"
                    f"Dist: {row['Distancia_km']:.1f} km<br>"
                    f"Conf: {confianza}<br>"
                    f"Fuente: {fuente}"
                )
                customdata_urls.append(None)
            
            if confianza in ['alta', 'valido', 'N/A']:
                colores_puntos.append(COLORES_SENSOR[sensor])
            else:
                colores_puntos.append(COLORES_CONFIANZA_ESPECIAL.get(confianza, COLORES_SENSOR[sensor]))
        
        df_sensor['VRP_Transformed'] = df_sensor['VRP_MW'].apply(transform)
        
        if sensor not in sensores_agregados:
            fig.add_trace(go.Scatter(
                x=df_sensor['Fecha_UTC'],
                y=df_sensor['VRP_Transformed'],
                mode='markers',
                name=sensor,
                marker=dict(
                    size=6,
                    symbol=MAPA_SIMBOLOS.get(sensor, 'circle'),
                    color=colores_puntos,
                    line=dict(width=0.5, color='white')
                ),
                hovertemplate='%{text}<extra></extra>',
                text=hover_texts,
                customdata=customdata_urls,
                showlegend=True
            ))
            sensores_agregados.add(sensor)

    # Traza de posibles artefactos: gris, simbolo X, apagada por defecto.
    if not df_arte.empty:
        df_arte['VRP_Transformed'] = df_arte['VRP_MW'].apply(transform)
        hover_arte = []
        for _, row in df_arte.iterrows():
            motivo = anotaciones_v.get(_ts_key(row['timestamp']), '')
            hover_arte.append(
                f"<b>{row['Fecha_Satelite_UTC']}</b><br>"
                f"{row['VRP_MW']:.2f} MW · {row['Sensor']}<br>"
                f"Dist: {row['Distancia_km']:.1f} km<br>"
                f"<b>⚠ Marcado como posible artefacto</b><br>"
                f"<i>{motivo}</i>"
            )
        fig.add_trace(go.Scatter(
            x=df_arte['Fecha_UTC'],
            y=df_arte['VRP_Transformed'],
            mode='markers',
            name='Posibles artefactos',
            marker=dict(size=8, symbol='x', color='rgba(150,150,150,0.75)',
                        line=dict(width=1, color='#8b949e')),
            hovertemplate='%{text}<extra></extra>',
            text=hover_arte,
            visible='legendonly',
            showlegend=True
        ))

    MESES_ES_DICT = {
        'Jan': 'Ene', 'Feb': 'Feb', 'Mar': 'Mar', 'Apr': 'Abr',
        'May': 'May', 'Jun': 'Jun', 'Jul': 'Jul', 'Aug': 'Ago',
        'Sep': 'Sep', 'Oct': 'Oct', 'Nov': 'Nov', 'Dec': 'Dic'
    }
    
    dias_totales = (ahora - hace_30_dias).days
    
    tick_dates = []
    tick_labels = []
    
    for i in range(6):
        dias_offset = int((dias_totales / 6) * i)
        fecha = hace_30_dias + timedelta(days=dias_offset)
        tick_dates.append(fecha)
        
        label_en = fecha.strftime("%d %b")
        for en, es in MESES_ES_DICT.items():
            label_en = label_en.replace(en, es)
        tick_labels.append(label_en)
    
    ultimo_tick = tick_dates[-1]
    diferencia_horas = (ahora - ultimo_tick).total_seconds() / 3600
    
    if diferencia_horas > 24:
        tick_dates.append(ahora)
        label_actual = ahora.strftime("%d %b")
        for en, es in MESES_ES_DICT.items():
            label_actual = label_actual.replace(en, es)
        tick_labels.append(label_actual)
    
    fig.update_xaxes(
        type="date",
        range=[hace_30_dias, ahora + timedelta(hours=6)],
        tickmode='array',
        tickvals=tick_dates,
        ticktext=tick_labels,
        showgrid=True,
        gridcolor='rgba(255,255,255,0.2)',
        gridwidth=1,
        minor=dict(
            dtick=86400000,
            showgrid=True,
            gridcolor='rgba(255,255,255,0.08)',
            gridwidth=0.5
        ),
        tickangle=-45,
        fixedrange=False,
        tickfont=dict(size=9),
        showticklabels=True
    )
    
    if modo_log:
        fig.update_yaxes(
            type="linear",
            range=[4.7, 9],
            tickvals=[5, 6, 7, 8],
            ticktext=["10⁵", "10⁶", "10⁷", "10⁸"],
            showgrid=True,
            gridcolor='rgba(255,255,255,0.15)',
            tickfont=dict(size=9),
            autorange=False,
            fixedrange=False
        )
    else:
        fig.update_yaxes(
            type="linear",
            range=[0, max(1.1, v_max_val * 1.5)],
            showgrid=True,
            gridcolor='rgba(255,255,255,0.15)',
            tickfont=dict(size=9),
            fixedrange=False
        )
    
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
    
    if not df_normal.empty:
        # Rango Y según el modo (para ubicar las etiquetas sin que se salgan)
        y_lo, y_hi = (4.7, 9.0) if modo_log else (0.0, max(1.1, v_max_val * 1.5))

        def _dist_txt(row):
            """Distancia al cráter (km) para agregar después de la potencia."""
            d = row.get('Distancia_km')
            try:
                if pd.notna(d):
                    return f" · {float(d):.1f} km"
            except Exception:
                pass
            return ""

        def _anclas(fecha, y_pos):
            """Ancla + offset que empujan la etiqueta HACIA ADENTRO desde el borde
            más cercano (X e Y) → nunca se sale del gráfico."""
            propx = (fecha - hace_30_dias).total_seconds() / 86400 / 30
            if propx > 0.78:      # cerca del borde derecho → texto hacia la izquierda
                xa, ax = 'right', -28
            elif propx < 0.22:    # cerca del borde izquierdo → texto hacia la derecha
                xa, ax = 'left', 28
            else:
                xa, ax = 'center', 0
            propy = (y_pos - y_lo) / (y_hi - y_lo) if y_hi > y_lo else 0.5
            if propy < 0.5:       # punto en la mitad baja → etiqueta hacia ARRIBA
                ya, ay = 'bottom', -30
            else:                 # punto en la mitad alta → etiqueta hacia ABAJO
                ya, ay = 'top', 30
            return xa, ax, ya, ay

        max_r = df_normal.loc[df_normal['VRP_MW'].idxmax()]
        fecha_max = max_r['Fecha_UTC']

        # Última lectura = evento VRP>0 más reciente del periodo
        ult_r = df_normal.loc[df_normal['Fecha_UTC'].idxmax()]
        fecha_ult = ult_r['Fecha_UTC']
        # ¿La última lectura es también el máximo? (mismo punto → una sola etiqueta)
        ult_es_max = (fecha_ult == fecha_max) and (ult_r['VRP_MW'] == max_r['VRP_MW'])

        # --- Etiqueta MÁX (azul) — potencia + km ---
        y_max = transform(max_r['VRP_MW'])
        xa, ax, ya, ay = _anclas(fecha_max, y_max)
        fig.add_annotation(
            x=fecha_max, y=y_max, xref="x", yref="y",
            text=(f"MÁX/ÚLTIMA: {max_r['VRP_MW']:.2f} MW{_dist_txt(max_r)}" if ult_es_max
                  else f"MÁX: {max_r['VRP_MW']:.2f} MW{_dist_txt(max_r)}"),
            showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.5, arrowcolor="white",
            bgcolor="rgba(0,0,0,0.8)", bordercolor="#58a6ff", borderwidth=1.2,
            font=dict(color="white", size=12),
            xanchor=xa, yanchor=ya, ax=ax, ay=ay
        )

        # --- Etiqueta ÚLTIMA (naranja) — solo si es un punto distinto al MÁX ---
        if not ult_es_max:
            y_ult = transform(ult_r['VRP_MW'])
            xa, ax, ya, ay = _anclas(fecha_ult, y_ult)
            fig.add_annotation(
                x=fecha_ult, y=y_ult, xref="x", yref="y",
                text=f"ÚLTIMA: {ult_r['VRP_MW']:.2f} MW{_dist_txt(ult_r)}",
                showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.5, arrowcolor="white",
                bgcolor="rgba(0,0,0,0.8)", bordercolor="#f0883e", borderwidth=1.2,
                font=dict(color="white", size=12),
                xanchor=xa, yanchor=ya, ax=ax, ay=ay
            )
    
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
    else:
        # Fallback: positivos de latest.php (el "maestro completo" nunca existió;
        # se eliminó ese fallback muerto en la limpieza 2026-06)
        df = pd.read_csv(ARCHIVO_POSITIVOS) if os.path.exists(ARCHIVO_POSITIVOS) else pd.DataFrame()
        if not df.empty:
            df['Confianza_Validacion'] = 'valido'
    
    config_lineal = {
        'displayModeBar': True,
        'displaylogo': False,
        'responsive': True,
        'modeBarButtonsToRemove': [
            'select2d',
            'lasso2d',
            'pan2d',
            'zoomIn2d',
            'zoomOut2d',
            'autoScale2d',
            'toggleSpikelines'
        ],
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
        'modeBarButtonsToRemove': [
            'select2d',
            'lasso2d',
            'pan2d',
            'zoomIn2d',
            'zoomOut2d',
            'autoScale2d',
            'toggleSpikelines'
        ],
        'toImageButtonOptions': {
            'format': 'jpeg',
            'filename': 'grafico_volcan_log',
            'height': 500,
            'width': 1400,
            'scale': 2
        }
    }

    anotaciones = cargar_anotaciones()
    if anotaciones:
        print(f"📌 {len(anotaciones)} deteccion(es) marcadas como artefacto (overlay curaduria)")

    for v in VOLCANES:
        df_v = df[df['Volcan'] == v].copy()
        anot_v = {ts: mot for (ts, vol), mot in anotaciones.items() if vol == v}
        nombre_f = f"{v.replace(' ', '_').replace('-', '_')}.html"
        
        for carpeta, es_log in [(CARPETA_LINEAL, False), (CARPETA_LOG, True)]:
            fig = crear_grafico(df_v, v, modo_log=es_log, anotaciones_v=anot_v)
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
            html_base = fig.to_html(config=cfg, include_plotlyjs='cdn')
            
            script_modebar = """
<style>
.modebar {
    opacity: 0;
    transition: opacity 0.3s ease;
}

.plotly-graph-div:hover .modebar {
    opacity: 1;
}
</style>
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
            html_final = html_base.replace('</body>', script_modebar)
            
            with open(path, 'w', encoding='utf-8') as f:
                f.write(html_final)

    ahora_utc = datetime.now(pytz.UTC)
    estado = {
        "estado": "✅ Operativo",
        "color": "#2ea043",
        "ultima_actualizacion": ahora_utc.strftime("%Y-%m-%d %H:%M UTC")
    }
    
    with open("monitoreo_satelital/estado_sistema.json", "w") as f:
        import json
        json.dump(estado, f, indent=2)

    # Generar volcanes.js para el dashboard desde la fuente única (volcanes.py)
    import json
    with open("volcanes.js", "w", encoding="utf-8") as f:
        f.write("window.VOLCANES_DASHBOARD = " + json.dumps(DASHBOARD, ensure_ascii=False) + ";\n")

    print(f"\n✅ Gráficos generados para {len(VOLCANES)} volcanes")

if __name__ == "__main__":
    procesar()

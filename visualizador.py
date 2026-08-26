import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os
import pytz
from datetime import datetime, timedelta

# Parametros que dependen del entorno (GitHub vs instalacion local en OVDAS).
# Por defecto reproduce el comportamiento de GitHub: ver config.py.
import config

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
    
    # --- Serie completa vs ventana visible -------------------------------------
    # Se GRAFICA toda la serie historica (para poder navegar hacia atras), pero
    # la ESCALA y las etiquetas MAX/ULTIMA se calculan sobre los ultimos 30 dias,
    # que es la ventana que se abre por defecto. Si se calcularan sobre todo el
    # historico, un pico viejo (Lascar llego a 760 MW) aplastaria la vista actual
    # y "MAX" pasaria a significar "maximo historico" en vez de "maximo del
    # periodo mostrado".
    df_v_30 = pd.DataFrame()
    if not df_v.empty:
        df_v['Fecha_UTC'] = pd.to_datetime(df_v['Fecha_Satelite_UTC']).dt.tz_localize('UTC')
        df_v['Fecha_Chile_temp'] = df_v['Fecha_UTC'].dt.tz_convert('America/Santiago')
        df_v_30 = df_v[df_v['VRP_MW'] > 0].copy()

    if df_v_30.empty: return None

    # Ventana por defecto = ultimos 30 dias. Si el volcan no tuvo actividad en
    # ese periodo, se abre mostrando toda la serie: antes devolviamos None y el
    # usuario veia "SIN ANOMALIA TERMICA" sin poder consultar el historico.
    df_escala = df_v_30[df_v_30['Fecha_Chile_temp'] >= hace_30_dias].copy()
    hay_datos_recientes = not df_escala.empty
    if not hay_datos_recientes:
        df_escala = df_v_30
        x_inicio = df_v_30['Fecha_Chile_temp'].min()
    else:
        x_inicio = hace_30_dias
    x_fin = ahora + timedelta(hours=6)
    # Limite duro hacia atras: el primer dato de la serie (no hay nada anterior).
    x_min_datos = df_v_30['Fecha_Chile_temp'].min()

    # --- Capa de curaduria: separar detecciones marcadas como artefacto ----------
    # Los marcados se EXCLUYEN del autoescalado del eje Y (para no aplastar la senal
    # real) y se dibujan aparte (gris, apagados por defecto). No se borra nada.
    anotaciones_v = anotaciones_v or {}
    def _ts_key(x):
        try:
            return str(int(float(x)))
        except (ValueError, TypeError):
            return str(x).strip()
    _claves_arte = set(anotaciones_v.keys())
    df_v_30['_es_artefacto'] = df_v_30['timestamp'].apply(_ts_key).isin(_claves_arte)
    df_normal = df_v_30[~df_v_30['_es_artefacto']].copy()
    df_arte = df_v_30[df_v_30['_es_artefacto']].copy()

    # Solo lo que cae dentro de la ventana visible inicial manda en la escala Y
    # y en las etiquetas MAX/ULTIMA.
    df_escala['_es_artefacto'] = df_escala['timestamp'].apply(_ts_key).isin(_claves_arte)
    df_escala_normal = df_escala[~df_escala['_es_artefacto']].copy()

    unidad = "Watt" if modo_log else "MW"
    fig = go.Figure()
    v_max_val = df_escala_normal['VRP_MW'].max() if not df_escala_normal.empty else 1.0
    
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
            # Base configurable: el repo en GitHub, o la carpeta local servida
            # por el servidor web cuando corre en OVDAS (ver config.py).
            url_github = f"{config.URL_BASE_IMAGENES}/{volcan_normalizado}/{fecha_carpeta}"
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
                # .tolist(): con una Series, plotly 6.x serializa el eje Y como
                # binario base64 y el JS de autoescalado no puede leer los valores.
                y=df_sensor['VRP_Transformed'].tolist(),
                mode='markers',
                name=sensor,
                meta='serie_vrp',   # lo lee el JS de autoescalado del eje Y
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
    
    dias_totales = max(1, (x_fin - x_inicio).days)
    
    tick_dates = []
    tick_labels = []
    
    for i in range(6):
        dias_offset = int((dias_totales / 6) * i)
        fecha = x_inicio + timedelta(days=dias_offset)
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
    
    # Botones de navegacion temporal. El HTML lleva la serie completa, asi que
    # moverse hacia atras no requiere regenerar nada; el limite real es el primer
    # dato de la serie (ene-2026). El eje Y y las fechas se recalculan por JS al
    # cambiar de ventana (ver script_navegacion mas abajo).
    _botones = []
    _dias_serie = max(1, (x_fin - x_min_datos).days)
    for _n, _et in ((30, "1M"), (90, "3M"), (180, "6M")):
        if _dias_serie > _n:
            _botones.append(dict(count=_n, label=_et, step="day", stepmode="backward"))
    _botones.append(dict(step="all", label="Todo"))

    fig.update_xaxes(
        type="date",
        range=[x_inicio, x_fin],
        rangeselector=dict(
            buttons=_botones,
            bgcolor="rgba(22,27,34,0.9)",
            activecolor="#1f6feb",
            bordercolor="rgba(139,148,158,0.4)",
            borderwidth=1,
            font=dict(color="#c9d1d9", size=10),
            x=0, xanchor="left", y=1.12, yanchor="top"
        ),
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
    
    # Las etiquetas se dibujan sobre la ventana visible; si esta vacia no hay nada que rotular.
    if not df_escala_normal.empty:
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

        max_r = df_escala_normal.loc[df_escala_normal['VRP_MW'].idxmax()]
        fecha_max = max_r['Fecha_UTC']

        # Última lectura = evento VRP>0 más reciente del periodo MOSTRADO
        ult_r = df_escala_normal.loc[df_escala_normal['Fecha_UTC'].idxmax()]
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
        # Sin alto fijo: el gráfico ocupa el 100% del iframe que lo contiene, así
        # el dashboard puede agrandarlo (modo foco / pantalla completa) sin que
        # quede una banda muerta debajo. El alto real lo decide el CSS del
        # dashboard; acá solo se pide que Plotly se adapte al contenedor.
        height=None,
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

    # Modo 'directory' (instalacion local sin internet): plotly espera encontrar
    # un plotly.min.js JUNTO a los HTML, pero NO lo escribe solo. Se copia el que
    # trae el paquete instalado, una vez por carpeta (~4,5 MB compartidos, en vez
    # de 4,5 MB dentro de cada uno de los 22 graficos).
    if config.PLOTLY_JS == "directory":
        from plotly.offline import get_plotlyjs
        js = get_plotlyjs()
        for carpeta_js in (CARPETA_LINEAL, CARPETA_LOG):
            with open(os.path.join(carpeta_js, "plotly.min.js"), "w", encoding="utf-8") as f:
                f.write(js)
        print(f"[config] {config.resumen()}")
    
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
        # igual que el lineal: si no, el gráfico log no se redimensiona al
        # cambiar el tamaño de la tarjeta (quedaba cortado en modo foco).
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
            html_base = fig.to_html(config=cfg, include_plotlyjs=config.PLOTLY_JS)
            
            script_modebar = """
<style>
/* El div de Plotly se genera con height:100%; sin esto el <body> no tiene
   altura propia y el gráfico colapsa. Con esto, el gráfico mide exactamente
   lo que mida el iframe. */
html, body { height: 100%; margin: 0; overflow: hidden; }
.plotly-graph-div { height: 100% !important; width: 100% !important; }

.modebar {
    opacity: 0;
    transition: opacity 0.3s ease;
}

.plotly-graph-div:hover .modebar {
    opacity: 1;
}
</style>
<script>
// ---------------------------------------------------------------------------
// Navegacion temporal: el HTML trae la serie completa y la ventana por defecto
// son los ultimos 30 dias. Al cambiar de ventana (botones 1M/3M/6M/Todo, zoom o
// arrastre) hay que recalcular dos cosas que Plotly no ajusta solo:
//   1. El eje Y, para que cada periodo se vea en su propia escala. Sin esto un
//      pico viejo (Lascar: 760 MW historicos vs 1,6 MW del ultimo mes) deja los
//      meses tranquilos pegados al piso.
//   2. Las fechas del eje X, que se generan en espanol desde aca en vez de
//      cargar un locale de Plotly por CDN (en OVDAS puede no haber internet).
// El eje Y logaritmico NO se toca: su rango fijo ya cubre toda la serie.
// ---------------------------------------------------------------------------
var MESES_ES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
var _ajustando = false;   // evita el bucle: relayout dispara plotly_relayout

function _fmtFecha(d, dias) {
    var s = d.getDate() + ' ' + MESES_ES[d.getMonth()];
    if (dias > 200) { s = MESES_ES[d.getMonth()] + ' ' + String(d.getFullYear()).slice(2); }
    return s;
}

// plotly 6.x puede entregar el eje Y como {dtype,bdata} (binario base64) en vez
// de un array. Se cubren ambos casos para no depender de la version.
function _valoresY(tr) {
    var y = tr.y;
    if (!y) return null;
    if (Array.isArray(y) || ArrayBuffer.isView(y)) return y;
    if (y._inputArray) return y._inputArray;
    return null;
}

function _ajustarVista(gd) {
    if (_ajustando) return;
    var xa = gd.layout.xaxis;
    if (!xa || !xa.range) return;
    var x0 = new Date(xa.range[0]).getTime(), x1 = new Date(xa.range[1]).getTime();
    if (!isFinite(x0) || !isFinite(x1) || x1 <= x0) return;
    var dias = (x1 - x0) / 86400000;

    var upd = {};

    // --- 1. eje Y sobre los puntos visibles (solo escala lineal) -------------
    var esLog = gd.layout.yaxis && gd.layout.yaxis.tickvals &&
                gd.layout.yaxis.tickvals.length === 4;
    if (!esLog) {
        var vmax = null;
        (gd.data || []).forEach(function(tr) {
            if (tr.meta !== 'serie_vrp') return;      // ignora bandas y artefactos
            if (tr.visible === false || tr.visible === 'legendonly') return;
            var xs = tr.x || [], ys = _valoresY(tr);
            if (!ys) return;
            for (var i = 0; i < xs.length; i++) {
                var t = new Date(xs[i]).getTime();
                if (t >= x0 && t <= x1 && ys[i] != null) {
                    if (vmax === null || ys[i] > vmax) vmax = ys[i];
                }
            }
        });
        // Sin puntos visibles se deja la escala como esta: un eje que salta a 0
        // al pasar por un hueco sin datos se lee como si el volcan hubiera
        // dejado de medirse.
        if (vmax !== null) upd['yaxis.range'] = [0, Math.max(1.1, vmax * 1.5)];
    }

    // --- 2. fechas del eje X en espanol, densidad segun el zoom --------------
    var n = 6, vals = [], txts = [];
    for (var k = 0; k <= n; k++) {
        var d = new Date(x0 + (x1 - x0) * k / n);
        vals.push(d.toISOString());
        txts.push(_fmtFecha(d, dias));
    }
    upd['xaxis.tickvals'] = vals;
    upd['xaxis.ticktext'] = txts;

    _ajustando = true;
    Plotly.relayout(gd, upd).then(function() { _ajustando = false; })
                            .catch(function() { _ajustando = false; });
}

document.addEventListener('DOMContentLoaded', function() {
    var plotDiv = document.getElementsByClassName('plotly-graph-div')[0];
    if (plotDiv) {
        plotDiv.on('plotly_relayout', function(ev) {
            // solo cuando cambio el eje X (botones, zoom, arrastre o autoscale)
            var tocaX = Object.keys(ev || {}).some(function(k) {
                return k.indexOf('xaxis') === 0;
            });
            if (tocaX) _ajustarVista(plotDiv);
        });
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

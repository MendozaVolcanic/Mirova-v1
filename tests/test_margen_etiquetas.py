"""La etiqueta del ultimo tick del eje X tiene que caber en el grafico.

El ultimo tick cae en el borde derecho (el dia actual en la ventana 1M, el
mes actual en Todo) y su etiqueta va inclinada a -45 grados, asi que la caja
del texto sobresale unos pixeles a la derecha. Plotly oculta cualquier
etiqueta que pase el borde del div (ticklabeloverflow "hide past div").

Con margin.r=2 se ocultaba la fecha del dia en las 11 tarjetas del dashboard
(medido en el sitio publicado, 13-sep-2026). Desde r=8 se veia en todas, en
1M y en Todo. Este test no reemplaza esa medicion en navegador, pero impide
que alguien vuelva a apretar el margen sin saber por que estaba asi.
"""
import json

import pandas as pd

import visualizador

MARGEN_MINIMO_MEDIDO = 8


def _detecciones():
    fechas = ["2026-08-20 05:00:00", "2026-09-10 06:00:00"]
    return pd.DataFrame({
        "timestamp": ["1789000000", "1789000001"],
        "Fecha_Satelite_UTC": fechas,
        "VRP_MW": [1.5, 2.0],
        "Sensor": ["VIIRS375", "VIIRS375"],
        "Distancia_km": [1.0, 1.0],
        "Tipo_Registro": ["ALERTA_TERMICA", "ALERTA_TERMICA"],
        "Confianza_Validacion": ["alta", "alta"],
        "Ruta Foto": ["No descargada", "No descargada"],
    })


def test_margen_derecho_deja_ver_la_ultima_etiqueta():
    for modo_log in (False, True):
        fig = visualizador.crear_grafico(_detecciones(), "Isluga", modo_log=modo_log)
        layout = json.loads(fig.to_json())["layout"]
        assert layout["xaxis"]["tickangle"] == -45
        assert layout["margin"]["r"] >= MARGEN_MINIMO_MEDIDO, (
            "con la etiqueta inclinada, un margen derecho menor oculta la "
            "fecha del ultimo tick"
        )

"""El eje X de los graficos tiene que estar entero en UTC.

El dashboard dice "todas las horas en UTC" y los puntos se dibujan en UTC,
pero crear_grafico armaba el rango, la ventana de 30 dias y las etiquetas en
hora de Chile. Plotly descarta la zona horaria de los strings, asi que el eje
quedaba en hora de pared chilena y los puntos en hora de pared UTC: dos relojes
en el mismo eje.

Se notaba en dos lugares:
  - entre las 21:00 y la medianoche de Chile (ya dia siguiente en UTC) la
    etiqueta del dia no calzaba con la fecha UTC de los datos;
  - que los puntos recientes quedaran dentro del eje dependia de que el margen
    de 6 h fuera mayor que la diferencia horaria (3 h, 4 h en invierno).
"""
import json
import re
from datetime import datetime

import pandas as pd
import pytest
import pytz

import visualizador

# 13-sep-2026 01:30 UTC = 12-sep 22:30 en Chile: el caso donde los relojes
# discrepan en la fecha.
AHORA_UTC = datetime(2026, 9, 13, 1, 30, tzinfo=pytz.UTC)


class _RelojFijo(datetime):
    @classmethod
    def now(cls, tz=None):
        return AHORA_UTC if tz is None else AHORA_UTC.astimezone(tz)


def _pared(s):
    """Hora de pared, como la lee Plotly.js: se descarta la zona."""
    s = re.sub(r"(Z|[+-]\d\d:?\d\d)$", "", str(s))
    return pd.Timestamp(s)


def _detecciones(fechas_utc):
    return pd.DataFrame({
        "timestamp": [str(1789000000 + i) for i in range(len(fechas_utc))],
        "Fecha_Satelite_UTC": fechas_utc,
        "VRP_MW": [1.5] * len(fechas_utc),
        "Sensor": ["VIIRS375"] * len(fechas_utc),
        "Distancia_km": [1.0] * len(fechas_utc),
        "Tipo_Registro": ["ALERTA_TERMICA"] * len(fechas_utc),
        "Confianza_Validacion": ["alta"] * len(fechas_utc),
        "Ruta Foto": ["No descargada"] * len(fechas_utc),
    })


@pytest.fixture
def eje(monkeypatch):
    monkeypatch.setattr(visualizador, "datetime", _RelojFijo)
    df = _detecciones(["2026-08-20 05:00:00", "2026-09-13 01:00:00"])
    fig = visualizador.crear_grafico(df, "Isluga")
    return json.loads(fig.to_json())["layout"]["xaxis"]


def test_rango_y_ticks_sin_hora_de_chile(eje):
    fechas = list(eje["range"]) + list(eje["tickvals"])
    con_chile = [f for f in fechas if re.search(r"-0[34]:?00$", str(f))]
    assert not con_chile, f"fechas del eje en hora de Chile: {con_chile}"


def test_ventana_parte_a_medianoche_utc_hace_30_dias(eje):
    assert _pared(eje["range"][0]) == pd.Timestamp("2026-08-14 00:00:00")


def test_ultima_etiqueta_es_el_dia_utc(eje):
    assert eje["ticktext"][-1] == "13 Sep"


def test_ultimo_dato_dentro_del_eje(eje):
    assert _pared(eje["range"][1]) >= pd.Timestamp("2026-09-13 01:00:00")

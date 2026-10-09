"""
V31: la fila OCR solo se crea si la imagen Dist.png es de la pasada de la fila.

Fenómeno: MIROVA mantiene UNA imagen viva por volcán y sensor y la reemplaza en
cada pasada. La cabecera "Last Update" dice de qué pasada es. El OCR corre una vez
por hora; si MIROVA ya procesó otra pasada, la estrella de Dist.png (distancia y
clase) es de esa otra pasada, no de las celdas viejas de Latest10NTI.

Caso testigo (VRP Chile, docs/S150_IMAGENES_SNPP.md): Láscar VIIRS375 2026-08-22.
Las imágenes guardadas como 05-06-00_* son byte a byte las mismas que 05-24-01_*
(cabecera 22-Aug-2026 05:24:01). La fila de las 05:06 (Suomi NPP, 1,65 MW) quedó
como ALERTA_TERMICA_OCR con la estrella de las 05:24 (1,22 km).

Fixtures (todas bajadas del archivo de este repo):
- cabecera_lascar_viirs375_{vrp,dist,latest10nti}_0524.png: Láscar/2026-08-22/
  05-06-00_* (= 05-24-01_*), cabecera 05:24:01.
- cabecera_villarrica_viirs375_dist_0542.png: Villarrica/2026-09-17/05-42-01_*_Dist,
  cabecera 05:42:01 (bien rotulada).
- cabecera_isluga_viirs375_latest_vieja.png: Isluga/2026-10-07/06-00-01_*_Latest,
  cabecera 06-Oct-2026 06:24:01 (imagen VIEJA guardada con hora nueva).
"""
import csv
import os
import shutil
from datetime import datetime

import pandas as pd
import pytest
import pytz

from conftest import requiere_tesseract

UTC = pytz.utc


def _utc(s):
    return UTC.localize(datetime.strptime(s, "%Y-%m-%d %H:%M:%S"))


# ---------------------------------------------------------------------------
# Lectura de la cabecera sobre imágenes reales
# ---------------------------------------------------------------------------

@requiere_tesseract
@pytest.mark.parametrize("fixture, esperado", [
    ("cabecera_lascar_viirs375_vrp_0524.png", "2026-08-22 05:24:01"),
    ("cabecera_lascar_viirs375_dist_0524.png", "2026-08-22 05:24:01"),
    ("cabecera_lascar_viirs375_latest10nti_0524.png", "2026-08-22 05:24:01"),
    ("cabecera_villarrica_viirs375_dist_0542.png", "2026-09-17 05:42:01"),
    ("cabecera_isluga_viirs375_latest_vieja.png", "2026-10-06 06:24:01"),
    # variante 850x596 de MIROVA
    ("dist_estrella_gris_596.png", "2026-03-11 06:36:01"),
    # Tesseract lee "19-]an-2026": la J de Jan sale como ']'
    ("dist_techo_claro_600.png", "2026-01-19 06:00:01"),
])
def test_lee_last_update(fixture_path, fixture, esperado):
    from ocr_utils import leer_last_update
    assert leer_last_update(fixture_path(fixture)) == _utc(esperado)


@requiere_tesseract
def test_lee_last_update_desde_ndarray(fixture_path):
    """Las imágenes permanentes se verifican desde bytes en memoria (ndarray)."""
    import cv2
    import numpy as np
    from ocr_utils import leer_last_update
    with open(fixture_path("cabecera_lascar_viirs375_vrp_0524.png"), "rb") as f:
        img = cv2.imdecode(np.frombuffer(f.read(), np.uint8), cv2.IMREAD_COLOR)
    assert leer_last_update(img) == _utc("2026-08-22 05:24:01")


def test_ilegible_es_none():
    import numpy as np
    from ocr_utils import leer_last_update
    assert leer_last_update(np.full((600, 850, 3), 255, np.uint8)) is None
    assert leer_last_update("/no/existe.png") is None


# ---------------------------------------------------------------------------
# Decisión del scraper: los tres casos pedidos + dirección contraria
# ---------------------------------------------------------------------------

@requiere_tesseract
def test_rechaza_fila_lascar_0506(fixture_path):
    """Suomi NPP 05:06:00 con la imagen de NOAA-20 05:24:01: NO se crea la fila."""
    from ocr_utils import leer_last_update
    from scraper_ocr import motivo_rechazo_cabecera
    cab = leer_last_update(fixture_path("cabecera_lascar_viirs375_dist_0524.png"))
    motivo = motivo_rechazo_cabecera(_utc("2026-08-22 05:06:00"), cab)
    assert motivo is not None
    assert "POSTERIOR" in motivo and "+18.0 min" in motivo
    assert "," not in motivo  # va a CSV y a un frontend que parte por coma


@requiere_tesseract
def test_acepta_fila_lascar_0524(fixture_path):
    from ocr_utils import leer_last_update
    from scraper_ocr import motivo_rechazo_cabecera
    cab = leer_last_update(fixture_path("cabecera_lascar_viirs375_dist_0524.png"))
    assert motivo_rechazo_cabecera(_utc("2026-08-22 05:24:01"), cab) is None


@requiere_tesseract
def test_acepta_fila_villarrica_0542(fixture_path):
    from ocr_utils import leer_last_update
    from scraper_ocr import motivo_rechazo_cabecera
    cab = leer_last_update(fixture_path("cabecera_villarrica_viirs375_dist_0542.png"))
    assert motivo_rechazo_cabecera(_utc("2026-09-17 05:42:01"), cab) is None


@requiere_tesseract
def test_rechaza_imagen_vieja_isluga(fixture_path):
    """Dirección contraria: imagen de la pasada ANTERIOR guardada con hora nueva."""
    from ocr_utils import leer_last_update
    from scraper_ocr import motivo_rechazo_cabecera
    cab = leer_last_update(fixture_path("cabecera_isluga_viirs375_latest_vieja.png"))
    motivo = motivo_rechazo_cabecera(_utc("2026-10-07 06:00:01"), cab)
    assert motivo is not None and "ANTERIOR" in motivo


# ---------------------------------------------------------------------------
# Tolerancia y casos borde (sin OCR)
# ---------------------------------------------------------------------------

def test_tolerancia_dos_minutos():
    from ocr_utils import cabecera_coincide, TOLERANCIA_CABECERA_S
    assert TOLERANCIA_CABECERA_S == 120
    cab = _utc("2026-08-22 05:24:01")
    assert cabecera_coincide(cab, _utc("2026-08-22 05:24:01"))
    assert cabecera_coincide(cab, _utc("2026-08-22 05:25:30"))   # 89 s
    assert cabecera_coincide(cab, _utc("2026-08-22 05:22:31"))   # -90 s
    assert not cabecera_coincide(cab, _utc("2026-08-22 05:26:02"))  # 121 s
    # la separación mínima medida entre pasadas distintas es 5 min
    assert not cabecera_coincide(cab, _utc("2026-08-22 05:29:01"))
    # datetime sin zona se interpreta como UTC
    assert cabecera_coincide(cab, datetime(2026, 8, 22, 5, 24, 1))


def test_sin_cabecera_o_sin_dist_se_rechaza():
    from scraper_ocr import motivo_rechazo_cabecera
    assert "ilegible" in motivo_rechazo_cabecera(_utc("2026-08-22 05:24:01"), None)
    assert "sin Dist" in motivo_rechazo_cabecera(_utc("2026-08-22 05:24:01"),
                                                 _utc("2026-08-22 05:24:01"), hay_dist=False)


def test_log_de_rechazos_una_fila_por_pasada(tmp_path):
    from scraper_ocr import registrar_rechazo_cabecera, COLUMNAS_RECHAZOS
    log = str(tmp_path / "rechazos.csv")
    ev = {'datetime': _utc("2026-08-22 05:06:00"), 'vrp_mw': 1.65, 'zen': 59, 'azi': 104}
    cab = _utc("2026-08-22 05:24:01")
    assert registrar_rechazo_cabecera("Lascar", "VIIRS375", ev, cab, cab, "m1", ruta_log=log)
    # la corrida siguiente vuelve a ver la misma celda: no se repite
    assert not registrar_rechazo_cabecera("Lascar", "VIIRS375", ev, cab, cab, "m1", ruta_log=log)
    with open(log, newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    assert len(filas) == 1
    assert list(filas[0].keys()) == COLUMNAS_RECHAZOS
    assert filas[0]["fecha_pasada_utc"] == "2026-08-22 05:06:00"
    assert filas[0]["vrp_mw_celda"] == "1.65"
    assert filas[0]["cabecera_dist_utc"] == "2026-08-22 05:24:01"


# ---------------------------------------------------------------------------
# De punta a punta: la corrida real del 2026-08-22 08:31 UTC, sin red
# ---------------------------------------------------------------------------

class _Resp:
    def __init__(self, content):
        self.status_code = 200
        self.content = content


class _SesionFalsa:
    """Sirve las imágenes de MIROVA desde las fixtures (todas de las 05:24:01)."""
    def __init__(self, fixture_path):
        self.fp = fixture_path
        self.urls = []

    def get(self, url, **kw):
        self.urls.append(url)
        if url.endswith("_Latest10NTI.png"):
            nombre = "cabecera_lascar_viirs375_latest10nti_0524.png"
        elif url.endswith("_Dist.png"):
            nombre = "cabecera_lascar_viirs375_dist_0524.png"
        else:  # VRP y logVRP: misma cabecera
            nombre = "cabecera_lascar_viirs375_vrp_0524.png"
        with open(self.fp(nombre), "rb") as f:
            return _Resp(f.read())


@requiere_tesseract
def test_corrida_lascar_20260822_no_crea_la_fila_0506(fixture_path, tmp_path, monkeypatch):
    """Reproduce la corrida del OCR de las 08:31 UTC del 2026-08-22, cuando MIROVA
    servía las imágenes de las 05:24:01. Antes creaba DOS filas ALERTA_TERMICA_OCR
    (05:06 con 1,65 MW y 05:24 con 0,23 MW, ambas a 1,22 km). Ahora solo la de las
    05:24, y la de las 05:06 queda en el log de rechazos con el VRP de su celda."""
    import scraper_ocr

    ahora = _utc("2026-08-22 08:31:37")

    class _DT(datetime):
        @classmethod
        def now(cls, tz=None):
            return ahora.astimezone(tz) if tz else ahora.replace(tzinfo=None)

    monkeypatch.setattr(scraper_ocr, "datetime", _DT)
    monkeypatch.setattr(scraper_ocr, "time", type("T", (), {"sleep": staticmethod(lambda s: None)}))
    monkeypatch.setattr(scraper_ocr, "CARPETA_PRINCIPAL", str(tmp_path))
    monkeypatch.setattr(scraper_ocr, "CARPETA_TEMP", str(tmp_path / "ocr_temp"))
    monkeypatch.setattr(scraper_ocr, "CARPETA_IMAGENES", str(tmp_path / "imagenes_satelitales"))
    log = str(tmp_path / "ocr_rechazos_cabecera.csv")
    monkeypatch.setattr(scraper_ocr, "LOG_RECHAZOS_CABECERA", log)
    monkeypatch.setattr(scraper_ocr, "RECHAZOS_CABECERA_CORRIDA", [])
    os.makedirs(scraper_ocr.CARPETA_TEMP)

    from volcanes import VOLCANES_CONFIG
    id_lascar = next(k for k, v in VOLCANES_CONFIG.items() if v["nombre"] == "Lascar")
    sesion = _SesionFalsa(fixture_path)
    df_ocr = pd.DataFrame(columns=scraper_ocr.COLUMNAS_OCR)
    filas = scraper_ocr.procesar_volcan_sensor(sesion, id_lascar, "VIIRS375", df_ocr, pd.DataFrame())

    fechas = [f["Fecha_Satelite_UTC"] for f in filas]
    assert "2026-08-22 05:06:00" not in fechas
    assert fechas == ["2026-08-22 05:24:01"]
    assert filas[0]["VRP_MW"] == 0.23
    assert filas[0]["Version_OCR"] == "31.0"

    with open(log, newline="", encoding="utf-8") as f:
        rech = list(csv.DictReader(f))
    assert [(r["fecha_pasada_utc"], r["vrp_mw_celda"]) for r in rech] == [("2026-08-22 05:06:00", "1.65")]
    assert rech[0]["cabecera_dist_utc"] == "2026-08-22 05:24:01"

    # la evidencia de las 05:24 se guarda con su hora; nada con hora 05:06
    guardadas = sorted(os.listdir(tmp_path / "imagenes_satelitales" / "Lascar" / "2026-08-22"))
    assert guardadas and all(n.startswith("05-24-01_") for n in guardadas)

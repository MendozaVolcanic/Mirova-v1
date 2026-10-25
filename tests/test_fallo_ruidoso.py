"""scraper.py falla en rojo cuando latest.php no trae lo que se espera (auditoria 2026-10-22).

POR QUE (H-P1 y H-P4): el ciclo entero estaba dentro de un try que solo escribia la bitacora y
salia con 0. En todo modo de falla de MIROVA (caida, 500, pagina sin tabla, columnas cambiadas)
el workflow quedaba verde y commiteaba la bitacora, asi que el repo parecia vivo: 141 ciclos
reales leyeron 0 filas y cerraron "Proceso completado". Y un sensor renombrado abria una serie
paralela en silencio. Ahora cada uno de esos casos devuelve 1 y no toca el consolidado.
"""
import hashlib
import os

import pytest
import requests

import scraper

FILA = ("<tr><td>{fecha}</td><td>{id}</td><td>{nombre}</td><td>{vrp}</td>"
        "<td>{dist}</td><td>{sensor}</td></tr>")


def _html(filas):
    return ("<html><body><table><thead><tr><th>Time (UTC)</th></tr></thead><tbody>"
            + "".join(FILA.format(**f) for f in filas) + "</tbody></table></body></html>")


SANA = [
    dict(fecha="10-Jan-2026 05:00:00", id="355100", nombre="Lascar", vrp="1.50", dist="1.0", sensor="MODIS"),
    dict(fecha="10-Jan-2026 05:00:00", id="211060", nombre="Etna", vrp="9.00", dist="0.5", sensor="MODIS"),
]


class _Resp:
    def __init__(self, status, text):
        self.status_code, self.text, self.content = status, text, text.encode()


class _Sesion:
    def __init__(self, status, text, error=None):
        self._r, self._error = _Resp(status, text), error

    def get(self, url, **kw):
        if self._error:
            raise self._error
        return self._r


def _correr(monkeypatch, tmp_path, status=200, text="", error=None):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scraper.requests, "Session", lambda: _Sesion(status, text, error))
    os.makedirs("monitoreo_satelital", exist_ok=True)
    ruta = os.path.join("monitoreo_satelital", "registro_vrp_consolidado.csv")
    previo = "timestamp,Fecha_Satelite_UTC,Volcan,Sensor\n1767000000,2025-12-29 09:20:00,Lascar,MODIS\n"
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        f.write(previo)
    antes = hashlib.sha1(open(ruta, "rb").read()).hexdigest()
    codigo = scraper.procesar()
    despues = hashlib.sha1(open(ruta, "rb").read()).hexdigest()
    return codigo, antes != despues


def test_tabla_sana_sale_0_y_escribe(monkeypatch, tmp_path):
    assert _correr(monkeypatch, tmp_path, text=_html(SANA)) == (0, True)


@pytest.mark.parametrize("caso", [
    dict(status=500, text="<html><body><h1>Internal Server Error</h1></body></html>"),
    dict(text=""),
    dict(text=_html(SANA).replace("<tbody>", "").replace("</tbody>", "")),
    dict(text=_html([])),
    dict(text=_html([SANA[1]])),                                         # ninguna fila chilena
    dict(text=_html([dict(SANA[0], fecha="2026-01-10T05:00:00Z")])),     # formato de fecha cambiado
    dict(text=_html([dict(SANA[0], sensor="VIIRS-I")])),                 # sensor renombrado
    dict(error=requests.ConnectionError("caida")),
], ids=["http_500", "cuerpo_vacio", "sin_tbody", "tabla_vacia", "sin_filas_chilenas",
        "fecha_iso", "sensor_desconocido", "conexion_caida"])
def test_falla_de_latest_sale_1_sin_tocar_el_consolidado(monkeypatch, tmp_path, caso):
    assert _correr(monkeypatch, tmp_path, **caso) == (1, False)

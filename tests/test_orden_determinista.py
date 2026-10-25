"""Orden determinista de los CSV de datos (auditoria 2026-10-22, hallazgo H-T1).

POR QUE: el scraper reescribia el consolidado ordenado solo por timestamp. El 98 % de las
filas comparte timestamp con otras (varios volcanes en la misma pasada), asi que cada ciclo
dejaba esos empates en otro orden y el archivo entero cambiaba de forma. Cuando una corrida
tenia que rebasar su commit sobre otro ciclo (main.yml, `git pull --rebase -X ours`), git
mezclaba como texto tres ordenes distintos del mismo archivo y dejaba filas dos veces o
ninguna: 2.165 filas perdidas en la historia, 18 alertas de 1 MW o mas.

Con orden total (timestamp, Volcan, Sensor), el mismo contenido da siempre los mismos bytes y
la mezcla de tres vias solo choca en las lineas que de verdad cambiaron.
"""
import io
import os
import random
import shutil
import subprocess

import pandas as pd
import pytest

from orden_registros import ordenar_registros

TIENE_GIT = shutil.which("git") is not None


def _filas(n_ts=40, refresco=None):
    """Tabla sintetica con muchos empates: 10 pares volcan-sensor por timestamp."""
    volcanes = ["Lascar", "Isluga", "Villarrica", "Llaima", "Copahue"]
    sensores = ["MODIS", "VIIRS375"]
    filas = []
    for i in range(n_ts):
        ts = 1_780_000_000 + 300 * i
        for v in volcanes:
            for s in sensores:
                filas.append({"timestamp": ts, "Volcan": v, "Sensor": s,
                              "VRP_MW": 0.0, "Ultima_Actualizacion": "2026-10-01 00:00:00"})
    df = pd.DataFrame(filas)
    if refresco:
        df.loc[df.index[-10:], "Ultima_Actualizacion"] = refresco
    return df


def _csv(df, semilla):
    """Como lo escribe el scraper: la entrada llega en cualquier orden y se ordena al final."""
    entrada = df.sample(frac=1, random_state=semilla)
    return ordenar_registros(entrada).to_csv(index=False, lineterminator="\n")


def _llaves(texto):
    df = pd.read_csv(io.StringIO(texto))
    return list(zip(df["timestamp"], df["Volcan"], df["Sensor"]))


def test_mismo_contenido_da_los_mismos_bytes():
    df = _filas()
    assert _csv(df, semilla=1) == _csv(df, semilla=2)


def test_orden_es_timestamp_descendente_y_luego_volcan_y_sensor():
    df = ordenar_registros(_filas(n_ts=2).sample(frac=1, random_state=3))
    esperado = sorted(zip(df["timestamp"], df["Volcan"], df["Sensor"]),
                      key=lambda k: (-k[0], k[1], k[2]))
    assert list(zip(df["timestamp"], df["Volcan"], df["Sensor"])) == esperado


ESCRITORES = ["scraper.py", "scraper_ocr.py", "merger_maestro.py"]
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.parametrize("archivo", ESCRITORES)
def test_escritores_de_csv_usan_el_orden_total(archivo):
    """Todo modulo que reescribe un CSV de datos ordena con ordenar_registros, no con sort_values propio."""
    fuente = open(os.path.join(RAIZ, archivo), encoding="utf-8").read()
    assert "ordenar_registros(" in fuente
    assert "sort_values('timestamp'" not in fuente and 'sort_values("timestamp"' not in fuente


@pytest.mark.skipif(not TIENE_GIT, reason="git no disponible")
def test_rebase_de_dos_ciclos_no_pierde_ni_duplica_filas(tmp_path):
    """Lo que hace main.yml cuando otro ciclo empujo primero: rebase -X ours de tres versiones."""
    base = _csv(_filas(), semilla=1)
    arriba = _csv(_filas(refresco="2026-10-01 00:05:00"), semilla=2)
    local = _csv(_filas(refresco="2026-10-01 00:10:00"), semilla=3)

    def g(*a):
        return subprocess.run(["git", *a], cwd=tmp_path, capture_output=True, text=True)

    archivo = tmp_path / "registro.csv"
    g("init", "-q", "-b", "main")
    g("config", "user.email", "t@t"); g("config", "user.name", "t"); g("config", "core.autocrlf", "false")
    archivo.write_text(base, encoding="utf-8", newline="\n"); g("add", "."); g("commit", "-qm", "base")
    g("branch", "arriba"); g("checkout", "-q", "arriba")
    archivo.write_text(arriba, encoding="utf-8", newline="\n"); g("commit", "-qam", "arriba")
    g("checkout", "-q", "main")
    archivo.write_text(local, encoding="utf-8", newline="\n"); g("commit", "-qam", "local")
    r = g("rebase", "-X", "ours", "arriba")
    assert r.returncode == 0, r.stderr

    resultado = _llaves(archivo.read_text(encoding="utf-8"))
    esperadas = set(_llaves(base))
    assert len(resultado) == len(set(resultado)), "la mezcla duplico filas"
    assert esperadas - set(resultado) == set(), "la mezcla perdio filas"

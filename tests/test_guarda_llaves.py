"""Guarda antes del push: un CSV de datos no puede perder llaves ni traerlas repetidas.

POR QUE (auditoria 2026-10-22, H-T1): nueve episodios de mezcla en el push dejaron 2.165 filas
perdidas y hasta 3.146 duplicadas en un solo commit, y el workflow termino en verde. La guarda
compara el CSV que se va a empujar con el de la rama remota y deja la corrida en rojo.
"""
import subprocess
import sys

from guarda_llaves import revisar

CAB = "timestamp,Fecha_Satelite_UTC,Volcan,Sensor,VRP_MW\n"
A = "1780000000,2026-05-28 20:26:40,Lascar,MODIS,1.5\n"
B = "1780000000,2026-05-28 20:26:40,Isluga,MODIS,0.0\n"
C = "1780000300,2026-05-28 20:31:40,Lascar,VIIRS375,0.0\n"


def test_mismo_contenido_pasa():
    assert revisar(CAB + A + B, CAB + A + B) == []


def test_otro_orden_y_filas_nuevas_pasan():
    assert revisar(CAB + A + B, CAB + C + B + A) == []


def test_perder_una_llave_falla():
    problemas = revisar(CAB + A + B, CAB + A)
    assert len(problemas) == 1 and "perdidas 1" in problemas[0]


def test_llave_repetida_falla():
    problemas = revisar(CAB + A + B, CAB + A + B + A)
    assert len(problemas) == 1 and "repetidas 1" in problemas[0]


def test_archivo_nuevo_vacio_falla():
    assert revisar(CAB + A, "") != []


def test_sin_version_anterior_solo_revisa_repetidas():
    assert revisar(None, CAB + A + B) == []
    assert revisar(None, CAB + A + A) != []


def test_linea_de_comandos_sale_en_rojo(tmp_path):
    viejo, nuevo = tmp_path / "viejo.csv", tmp_path / "nuevo.csv"
    viejo.write_text(CAB + A + B, encoding="utf-8")
    nuevo.write_text(CAB + A, encoding="utf-8")
    r = subprocess.run([sys.executable, "guarda_llaves.py", str(nuevo), "--anterior", str(viejo)],
                       capture_output=True, text=True)
    assert r.returncode == 1
    nuevo.write_text(CAB + B + A + C, encoding="utf-8")
    r = subprocess.run([sys.executable, "guarda_llaves.py", str(nuevo), "--anterior", str(viejo)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr

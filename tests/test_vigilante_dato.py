"""Vigilante de dato: avisa si el consolidado dejo de actualizarse (auditoria 2026-10-22, R6).

POR QUE (H-P1, 414): los vigilantes que habia median que el workflow termino, no que llego dato
(estado "Operativo" fijo, heartbeat con la hora del runner). La columna Ultima_Actualizacion_UTC
la reescribe cada ciclo sano en las filas que latest.php esta mostrando, asi que su maximo se
congela a los 5 min de una falla. Umbral medido: en 60 dias de bitacora, 3 de 17.397 silencios
entre ciclos completos pasan de 60 min y ninguno de 90.
Un vigilante que no puede leer su dato tiene que dar rojo, no verde.
"""
from datetime import datetime, timezone

from vigilante_dato import evaluar

AHORA = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
CAB = "timestamp,Volcan,Sensor,Ultima_Actualizacion_UTC\n"


def test_dato_fresco_pasa():
    codigo, _ = evaluar(CAB + "1,Lascar,MODIS,2026-10-22T11:50:00Z\n1,Isluga,MODIS,2026-10-20T00:00:00Z\n", AHORA)
    assert codigo == 0


def test_dato_viejo_falla():
    codigo, msj = evaluar(CAB + "1,Lascar,MODIS,2026-10-22T10:30:00Z\n", AHORA)
    assert codigo == 1 and "90" in msj


def test_columna_ausente_falla():
    assert evaluar("timestamp,Volcan,Sensor\n1,Lascar,MODIS\n", AHORA)[0] == 1


def test_archivo_vacio_o_sin_horas_falla():
    assert evaluar("", AHORA)[0] == 1
    assert evaluar(CAB + "1,Lascar,MODIS,\n", AHORA)[0] == 1


def test_umbral_configurable():
    texto = CAB + "1,Lascar,MODIS,2026-10-22T11:20:00Z\n"
    assert evaluar(texto, AHORA, umbral_min=60)[0] == 0
    assert evaluar(texto, AHORA, umbral_min=30)[0] == 1

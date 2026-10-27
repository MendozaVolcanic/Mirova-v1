"""Reposicion de las filas que el consolidado perdio en las mezclas del push (auditoria 2026-10-22, R4).

POR QUE: 2.648 filas de pasadas ya ocurridas (23 alertas de 1 MW o mas) desaparecieron en los
episodios de mezcla de abril y de agosto a octubre de 2026, y latest.php ya no las muestra, asi que
el scraper no las puede volver a leer. Sus copias intactas estan en los padres de esos commits.
reponer_filas.py las devuelve: solo agrega llaves que faltan, nunca pisa una fila que existe, y
correrlo dos veces no cambia nada.
"""
import pandas as pd

from reponer_filas import reponer

COLS = ["timestamp", "Fecha_Satelite_UTC", "Volcan", "Sensor", "VRP_MW", "Tipo_Registro"]


def _df(filas):
    return pd.DataFrame(filas, columns=COLS)


ACTUAL = _df([[1780000300, "2026-05-28 20:31:40", "Lascar", "MODIS", 0.0, "RUTINA"]])
PERDIDAS = _df([
    [1780000000, "2026-05-28 20:26:40", "Lascar", "MODIS", 1.64, "ALERTA_TERMICA"],
    [1780000300, "2026-05-28 20:31:40", "Lascar", "MODIS", 9.99, "ALERTA_TERMICA"],  # ya existe: no se pisa
    [1780000000, "2026-05-28 20:26:40", "Peteroa", "MODIS", 0.0, "RUTINA"],           # nombre viejo
    [1780000000, "2026-05-28 20:26:40", "Isluga", "MODIS", 0.0, "EVIDENCIA_DIARIA"],  # tipo de desarrollo
])


def test_agrega_solo_las_llaves_que_faltan():
    final, n = reponer(ACTUAL, PERDIDAS)
    assert n == 1
    assert len(final) == 2
    assert set(zip(final["Volcan"], final["timestamp"])) == {("Lascar", 1780000000), ("Lascar", 1780000300)}


def test_no_pisa_una_fila_que_existe():
    final, _ = reponer(ACTUAL, PERDIDAS)
    fila = final[final["timestamp"] == 1780000300].iloc[0]
    assert fila["VRP_MW"] == 0.0 and fila["Tipo_Registro"] == "RUTINA"


def test_correrlo_dos_veces_no_cambia_nada():
    una, _ = reponer(ACTUAL, PERDIDAS)
    dos, n = reponer(una, PERDIDAS)
    assert n == 0
    assert una.to_csv(index=False) == dos.to_csv(index=False)


def test_descarta_nombres_no_canonicos_y_tipos_desconocidos():
    final, _ = reponer(ACTUAL, PERDIDAS)
    assert "Peteroa" not in set(final["Volcan"])
    assert "EVIDENCIA_DIARIA" not in set(final["Tipo_Registro"])


def test_archivo_de_perdidas_real_tiene_las_23_protegidas():
    p = pd.read_csv("monitoreo_satelital/filas_perdidas_por_mezcla_2026.csv")
    prot = p[(p["Tipo_Registro"] == "ALERTA_TERMICA") & (p["VRP_MW"] >= 1)]
    # 2.110 de la auditoria del 2026-10-22, 241 del episodio del 2026-10-24 (commit 53b1e6d3c0) y 297 de los
    # episodios del 2026-10-26 15:37 UTC (0b73eb4b21) y del 2026-10-27 09:12 UTC (126ef0064c), 3 de ellas protegidas.
    assert len(p) == 2648 and len(prot) == 23
    assert not p.duplicated(["timestamp", "Volcan", "Sensor"]).any()

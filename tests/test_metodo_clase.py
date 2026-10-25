"""El OCR deja escrito con que metodo decidio la clase, y el metodo de grupo baja su confianza.

POR QUE (auditoria 2026-10-22, H-O1 y H-O4): el metodo de "grupo de pixeles rojos" asigna los
grupos de Dist.png a las pasadas por orden, no por hora. Contra latest.php, donde la tabla tiene
la misma pasada, su ALERTA acierta 62 de 78 de noche (0,795) y 5 de 48 de dia (0,104); el de la
estrella, 0,990 de noche. Pero Metodo_Validacion escribia 'roi_temporal_v26' para todas, asi que
VRP Chile no podia separar uno de otro sin leer la nota. Ahora la columna Metodo_Clase (al final,
para no mover ninguna columna existente) dice el metodo, y el de grupo sale con confianza baja y
pidiendo verificacion. Marcar no es descartar: la fila se guarda igual.
"""
import pandas as pd

import scraper_ocr
from ocr_utils import clasificar_confianza


def _grupo(y):
    return {"vrp_mw": 2.0, "grupo_pixeles": {"y_absoluto": y, "area": 20}}


def test_grupo_dentro_del_radio_sale_con_confianza_baja():
    c = clasificar_confianza(_grupo(290), None, "Lascar")
    assert c["tipo_registro"] == "ALERTA_TERMICA_OCR"
    assert c["Metodo_Deteccion"] == "grupo_pixeles_v29"
    assert c["confianza"] == "baja"
    assert c["requiere_verificacion"] is True
    assert "0.104" in c["nota"] and "," not in c["nota"].split("|")[-1]


def test_grupo_fuera_del_radio_sigue_siendo_falso_positivo():
    c = clasificar_confianza(_grupo(100), None, "Lascar")
    assert c["tipo_registro"] == "FALSO_POSITIVO_OCR"
    assert c["Metodo_Deteccion"] == "grupo_pixeles_v29"


def test_guardar_ocr_pone_metodo_clase_al_final_sin_mover_columnas(tmp_path):
    ruta = tmp_path / "registro_vrp_ocr.csv"
    viejo = pd.DataFrame([{"timestamp": 1, "Volcan": "Lascar", "Sensor": "MODIS", "VRP_MW": 1.0}])
    nuevo = {"timestamp": 2, "Volcan": "Lascar", "Sensor": "VIIRS375", "VRP_MW": 2.0,
             "Metodo_Clase": "estrella_verde_v16"}
    scraper_ocr.guardar_ocr(viejo, [nuevo], str(ruta))
    df = pd.read_csv(ruta, keep_default_na=False)
    esperadas = scraper_ocr.COLUMNAS_OCR + scraper_ocr.COLUMNAS_DIST_APROX + ["Metodo_Clase"]
    assert list(df.columns) == esperadas
    assert dict(zip(df["timestamp"], df["Metodo_Clase"])) == {2: "estrella_verde_v16", 1: ""}

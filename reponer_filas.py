"""
reponer_filas.py: devuelve al consolidado las filas que perdio en las mezclas del push.

POR QUE (auditoria 2026-10-22, H-T1 y R4): en los episodios de abril y de agosto a octubre de
2026 el bucle de push de main.yml mezclo como texto el consolidado y borro 2.110 filas de pasadas
ya ocurridas, 18 de ellas alertas de 1 MW o mas; el episodio del 2026-10-24 17:44 UTC (commit 53b1e6d3c0,
despues de la auditoria) borro 241 mas, 2 de ellas alertas de 1 MW o mas; los del 2026-10-26 15:37 (0b73eb4b21) y del 2026-10-27 09:12
UTC (126ef0064c), mientras el PR esperaba el merge, borraron 297 mas, 3 de ellas alertas de 1 MW o mas: 2.648 en total. latest.php solo muestra la ultima pasada de cada
volcan y sensor, asi que el scraper no las puede volver a leer. Sus copias intactas estan en el
padre de cada commit de mezcla; monitoreo_satelital/filas_perdidas_por_mezcla_2026.csv las junta
(comandos y conteos en el PR que lo agrego).

Que hace: agrega las filas de ese archivo cuya llave (timestamp, Volcan, Sensor) no esta en el
consolidado. Nunca pisa una fila que existe. Solo nombres canonicos de volcanes.py y tipos
vigentes (las 65 filas "Peteroa" del renombre manual del 2026-06-12 no son perdidas). Idempotente:
main.yml lo corre en cada ciclo antes del scraper y, una vez repuestas, no cambia nada. Se puede
quitar del workflow cuando el consolidado las tenga todas.
"""
import os
import sys

import pandas as pd

from orden_registros import ordenar_registros
from volcanes import VOLCANES_CONFIG

CARPETA = "monitoreo_satelital"
DB_MASTER = os.path.join(CARPETA, "registro_vrp_consolidado.csv")
PERDIDAS = os.path.join(CARPETA, "filas_perdidas_por_mezcla_2026.csv")
LLAVE = ["timestamp", "Volcan", "Sensor"]
TIPOS = {"ALERTA_TERMICA", "FALSO_POSITIVO", "RUTINA"}
NOMBRES = {v["nombre"] for v in VOLCANES_CONFIG.values()}


def reponer(df_actual, df_perdidas):
    """Devuelve (consolidado con las filas que faltaban, cuantas se agregaron)."""
    validas = df_perdidas[df_perdidas["Volcan"].isin(NOMBRES) & df_perdidas["Tipo_Registro"].isin(TIPOS)]
    existentes = set(zip(*(df_actual[c] for c in LLAVE)))
    faltan = validas[[k not in existentes for k in zip(*(validas[c] for c in LLAVE))]]
    if faltan.empty:
        return df_actual, 0
    final = pd.concat([df_actual, faltan], ignore_index=True).reindex(columns=df_actual.columns)
    return ordenar_registros(final), len(faltan)


def main():
    if not (os.path.exists(DB_MASTER) and os.path.exists(PERDIDAS)):
        print("reponer_filas: falta el consolidado o el archivo de perdidas; nada que hacer")
        return 0
    actual = pd.read_csv(DB_MASTER)
    final, n = reponer(actual, pd.read_csv(PERDIDAS))
    if n:
        final.to_csv(DB_MASTER, index=False)
    print(f"reponer_filas: {n} filas repuestas")
    return 0


if __name__ == "__main__":
    sys.exit(main())

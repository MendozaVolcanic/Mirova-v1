"""orden_registros.py: orden con que se escriben los CSV de datos.

POR QUE (auditoria 2026-10-22, H-T1): ordenar solo por timestamp dejaba los empates (varios
volcanes en la misma pasada, el 98 % de las filas) en el orden en que llegaran, y ese orden
cambiaba en cada ciclo. Cuando el push rebasaba sobre otro ciclo, git mezclaba como texto dos
ordenes distintos del mismo archivo y duplicaba o perdia filas. Con un orden total y estable el
mismo contenido da siempre los mismos bytes, y la mezcla solo toca las lineas que cambiaron.
"""

COLUMNAS_ORDEN = ['timestamp', 'Volcan', 'Sensor']


def ordenar_registros(df):
    """Timestamp descendente (lo mas nuevo arriba, como siempre) y empates por Volcan y Sensor."""
    return df.sort_values(COLUMNAS_ORDEN, ascending=[False, True, True], kind='mergesort')

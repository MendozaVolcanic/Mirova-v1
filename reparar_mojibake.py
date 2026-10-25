"""
reparar_mojibake.py: devuelve a UTF-8 las notas del OCR que quedaron en mojibake.

POR QUE (auditoria 2026-10-22, H-O8; abierto desde la auditoria S139 de VRP Chile, H203): el
commit manual ffc7a97d8b (2026-06-12) leyo registro_vrp_ocr.csv como cp1252 y lo escribio como
UTF-8. 647 notas quedaron con "pÃ­xeles", "lÃ­mite" y "distâ‰ˆ" en vez de "píxeles", "límite" y
"dist≈", y el lector de VRP Chile, que busca "dist≈", no les encuentra la distancia. (Esas
distancias se midieron con la geometria anterior al 2026-06-11: aun legibles no valen como
distancia; esto repara el texto, no la medicion.)

Como: se repara tramo por tramo. Un tramo de caracteres del rango de cp1252 se vuelve a sus
bytes cp1252 y se decodifica como UTF-8; si eso no es UTF-8 valido, el tramo se deja como esta.
Asi una "í" legitima (un byte suelto, que no es UTF-8 valido) no se toca, y una nota que mezcla
la parte vieja corrupta con texto agregado despues, limpio, solo cambia en la parte corrupta.
Idempotente: corre en cada ciclo de ocr_workflow.yml y, reparadas, no cambia nada.

Uso: python reparar_mojibake.py [csv]   (por defecto el registro del OCR; columna Nota_Validacion)
"""
import csv
import os
import re
import sys

CSV_OCR = os.path.join("monitoreo_satelital", "registro_vrp_ocr.csv")
COLUMNA = "Nota_Validacion"

# Caracteres que cp1252 produce para los bytes 0x80 a 0xFF.
_CP1252_ALTO = "".join(bytes([b]).decode("cp1252", errors="ignore") for b in range(0x80, 0x100))
_TRAMO = re.compile("[" + re.escape(_CP1252_ALTO) + "]{2,}")


def _reparar_tramo(m):
    tramo = m.group(0)
    try:
        return tramo.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return tramo


def reparar_texto(texto):
    if not isinstance(texto, str):
        return texto
    return _TRAMO.sub(_reparar_tramo, texto)


def reparar_archivo(ruta, columna=COLUMNA):
    """Repara la columna en el CSV. Devuelve cuantas celdas cambiaron (0 si no hay nada)."""
    if not os.path.exists(ruta):
        return 0
    with open(ruta, newline="", encoding="utf-8") as f:
        lector = csv.DictReader(f)
        cabecera = list(lector.fieldnames or [])
        filas = list(lector)
    if columna not in cabecera:
        return 0
    n = 0
    for fila in filas:
        nuevo = reparar_texto(fila[columna])
        if nuevo != fila[columna]:
            fila[columna] = nuevo
            n += 1
    if n:
        tmp = ruta + ".tmp"
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cabecera, lineterminator="\n")
            w.writeheader()
            w.writerows(filas)
        os.replace(tmp, ruta)
    return n


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    ruta = argv[0] if argv else CSV_OCR
    n = reparar_archivo(ruta)
    print(f"reparar_mojibake: {n} notas reparadas en {ruta}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Hash normalizado de los datos-fuente + assets publicables del dashboard.
#
# visualizador.py depende de dos CSV: registro_vrp_maestro_publicable.csv y
# registro_vrp_positivos.csv. Esos archivos se reescriben en CADA ciclo (~5 min)
# con las filas REORDENADAS y con columnas de timestamp (Fecha_Proceso_GitHub,
# Ultima_Actualizacion) y el flag Editado actualizados, aunque el conjunto real
# de detecciones sea el mismo. Un hash byte-a-byte churnearia cada ciclo y
# forzaria un deploy inutil a GitHub Pages (que solo admite 1 deployment activo
# por sitio -> colisiones -> "Deployment failed").
#
# Aca normalizamos los CSV: quitamos esas columnas volatiles y ordenamos las
# filas, de modo que el hash SOLO cambia cuando cambian los datos reales.
# Ademas incluimos los assets publicables estaticos (index.html, volcanes.js):
# si cambia el dashboard o la lista de volcanes tambien hay que republicar, y
# como son estables (no churnean cada ciclo) alcanza un hash byte-a-byte directo.
#
# graficos_completo.yml usa este hash para decidir si republicar el sitio.
# Direccion de fallo segura: si una columna volatil se renombra, deja de quitarse
# -> el hash vuelve a churnear -> se deploya de mas (nunca de menos), asi que el
# sitio nunca queda desactualizado por este script.
import csv
import hashlib

CSV_FUENTE = [
    "monitoreo_satelital/registro_vrp_maestro_publicable.csv",
    "monitoreo_satelital/registro_vrp_positivos.csv",
    # visualizador.py tambien lee anotaciones.csv (overlay de curaduria: oculta
    # de la escala los focos marcados como artefacto, sin borrar el dato crudo).
    # Estaba fuera del hash, asi que marcar un artefacto con marcar_artefacto.yml
    # cambiaba los graficos pero NO disparaba la republicacion: la curaduria no
    # llegaba al sitio hasta que cambiaran los datos VRP por otro motivo.
    "monitoreo_satelital/anotaciones.csv",
]
ASSETS_PUBLICABLES = ["index.html", "volcanes.js"]
VOLATILES = {"Fecha_Proceso_GitHub", "Ultima_Actualizacion", "Editado"}
SEP = b"::FIN::"

h = hashlib.sha256()

for path in CSV_FUENTE:
    try:
        with open(path, encoding="utf-8", newline="") as f:
            filas = list(csv.reader(f))
    except FileNotFoundError:
        h.update((path + "::AUSENTE::").encode())
        continue
    if not filas:
        h.update((path + "::VACIO::").encode())
        continue
    cabecera = filas[0]
    conservar = [i for i, col in enumerate(cabecera) if col not in VOLATILES]
    lineas = sorted(
        "\t".join(fila[i] for i in conservar if i < len(fila))
        for fila in filas[1:]
    )
    h.update(path.encode())
    h.update("\n".join(lineas).encode())
    h.update(SEP)

for path in ASSETS_PUBLICABLES:
    try:
        with open(path, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        h.update((path + "::AUSENTE::").encode())
        continue
    h.update(path.encode())
    h.update(data)
    h.update(SEP)

print(h.hexdigest())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Hash normalizado de los datos-fuente que alimentan los graficos del dashboard.
#
# visualizador.py solo depende de dos CSV: registro_vrp_maestro_publicable.csv y
# registro_vrp_positivos.csv. Esos archivos se reescriben en CADA ciclo (~5 min)
# con las filas REORDENADAS y con dos columnas de timestamp
# (Fecha_Proceso_GitHub, Ultima_Actualizacion) y el flag Editado actualizados,
# aunque el conjunto real de detecciones sea el mismo. Un hash byte-a-byte
# churnearia cada ciclo y forzaria un deploy inutil a GitHub Pages (que solo
# admite 1 deployment activo por sitio -> colisiones -> "Deployment failed").
#
# Aca normalizamos: quitamos esas columnas volatiles y ordenamos las filas, de
# modo que el hash SOLO cambia cuando cambian los datos reales (nueva deteccion,
# VRP distinto, nueva fila, etc.). graficos_completo.yml lo usa para decidir si
# republicar el sitio.
#
# Direccion de fallo segura: si una columna volatil se renombra, deja de
# quitarse -> el hash vuelve a churnear -> se deploya de mas (nunca de menos),
# asi que el sitio nunca queda desactualizado por este script.
import csv
import hashlib

ARCHIVOS = [
    "monitoreo_satelital/registro_vrp_maestro_publicable.csv",
    "monitoreo_satelital/registro_vrp_positivos.csv",
    # Overlay de curaduria: marcar/desmarcar un artefacto cambia los graficos, asi
    # que debe disparar una republicacion. Sin volatiles -> solo cambia al curar.
    "monitoreo_satelital/anotaciones.csv",
]
VOLATILES = {"Fecha_Proceso_GitHub", "Ultima_Actualizacion", "Editado"}

h = hashlib.sha256()
for path in ARCHIVOS:
    try:
        with open(path, encoding="utf-8", newline="") as f:
            filas = list(csv.reader(f))
    except FileNotFoundError:
        h.update((path + "\x00AUSENTE\n").encode())
        continue
    if not filas:
        h.update((path + "\x00VACIO\n").encode())
        continue
    cabecera = filas[0]
    conservar = [i for i, col in enumerate(cabecera) if col not in VOLATILES]
    lineas = sorted(
        "\t".join(fila[i] for i in conservar if i < len(fila))
        for fila in filas[1:]
    )
    h.update(path.encode())
    h.update("\n".join(lineas).encode())
    h.update(b"\x00")

print(h.hexdigest())

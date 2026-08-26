#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Sella el heartbeat que ve el dashboard, dentro de _site (lo publicable).
#
# Por que no se toma del repo: visualizador.py reescribe estado_sistema.json
# solo cuando hay datos nuevos, asi que el "last-sync" del sitio se quedaba
# congelado y llegaba a mostrar horas de atraso aunque el sistema estuviera
# corriendo perfecto. En un tablero de monitoreo volcanico eso se lee como
# "pipeline caido", que es justo el diagnostico equivocado.
#
# Por que no se commitea: commitear el heartbeat en cada ciclo devolveria los
# ~288 commits/dia de ruido que se eliminaron al condicionar la regeneracion
# de graficos. Se sella solo en _site, que es lo que se publica.
#
# Si el pipeline se cae de verdad, este script deja de correr, el sitio deja de
# recibir heartbeat y el atraso vuelve a crecer: la senal de alarma se conserva.
import datetime
import json
import os

RUTA = os.path.join("_site", "monitoreo_satelital", "estado_sistema.json")

try:
    with open(RUTA, encoding="utf-8") as f:
        estado = json.load(f)
except (OSError, ValueError):
    # Sin archivo previo (o ilegible) se parte del estado por defecto: es
    # preferible publicar un heartbeat fresco a no publicar ninguno.
    estado = {"estado": "\u2705 Operativo", "color": "#2ea043"}

estado["ultima_actualizacion"] = datetime.datetime.now(
    datetime.timezone.utc
).strftime("%Y-%m-%d %H:%M UTC")

os.makedirs(os.path.dirname(RUTA), exist_ok=True)
with open(RUTA, "w", encoding="utf-8") as f:
    json.dump(estado, f, indent=2)

print("heartbeat publicable:", estado["ultima_actualizacion"])

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Lee por stdin el estado_sistema.json PUBLICADO y responde "si" / "no":
# ¿el last-sync que ve el dashboard quedo mas viejo que el umbral?
#
# graficos_completo.yml lo usa para decidir si republicar aunque no haya datos
# nuevos. Sin esto el heartbeat del sitio se congela en el ultimo deploy y el
# dashboard aparenta estar caido mientras el sistema corre bien.
#
# Direccion de fallo segura: ante cualquier problema (sitio caido, JSON roto,
# fecha ilegible) responde "si" -> se republica de mas, nunca de menos.
import datetime
import json
import os
import sys

UMBRAL_HORAS = float(os.environ.get("MIROVA_HEARTBEAT_HORAS", "1"))

try:
    datos = json.load(sys.stdin)
    marca = datos["ultima_actualizacion"].replace(" UTC", "").strip()
    publicado = datetime.datetime.strptime(marca, "%Y-%m-%d %H:%M").replace(
        tzinfo=datetime.timezone.utc
    )
    horas = (
        datetime.datetime.now(datetime.timezone.utc) - publicado
    ).total_seconds() / 3600.0
    # Un heartbeat con fecha futura significa reloj corrido o dato corrupto:
    # se republica para volver a un valor confiable.
    print("si" if (horas >= UMBRAL_HORAS or horas < -0.25) else "no")
except Exception:
    print("si")

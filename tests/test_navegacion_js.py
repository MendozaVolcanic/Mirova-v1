"""Navegacion temporal de los graficos: el JS que va embebido en cada HTML.

Plotly.js lee las fechas como hora de pared: si el string trae 'Z' o '-03:00'
lo descarta y usa la hora escrita tal cual. El JS del grafico usaba el reloj de
JavaScript (new Date / toISOString), que SI respeta la zona. Resultado: los
ticks recalculados quedaban corridos +3 h, el ultimo caia fuera del rango y
Plotly lo ocultaba (desaparecia la fecha del dia en el dashboard, sep-2026).

Estos tests corren el script real en node con un Plotly simulado que parsea
fechas igual que el de verdad. Se fuerza TZ=America/Santiago para que un
new Date() dependiente de la zona del computador tambien falle aca.
"""
import json
import os
import re
import shutil
import subprocess

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

requiere_node = pytest.mark.skipif(shutil.which("node") is None,
                                   reason="node no disponible")


def _script_navegacion():
    with open(os.path.join(RAIZ, "visualizador.py"), encoding="utf-8") as f:
        src = f.read()
    m = re.search(r"<script>\n(// -{10,}\n// Navegacion temporal.*?)</script>", src, re.S)
    assert m, "no se encontro el bloque JS de navegacion en visualizador.py"
    return m.group(1)


ARNES = r"""
const vm = require('vm');
const fs = require('fs');
const escenario = JSON.parse(process.argv[3]);

// Hora de pared en ms, como Plotly.js: se descarta cualquier zona horaria.
function paredPlotly(v) {
  const s = String(v).trim().replace(' ', 'T')
    .replace(/(Z|[+-]\d\d:?\d\d)$/i, '').replace(/(\.\d{3})\d+/, '$1');
  return Date.parse(s.length <= 10 ? s + 'T00:00:00Z' : s + 'Z');
}

const gd = {
  layout: {xaxis: {range: escenario.range.slice()}, yaxis: {}},
  data: escenario.trazas,
  on: () => {},
};
const llamadas = [];
const Plotly = {
  relayout(div, upd) {
    llamadas.push(upd);
    for (const k of Object.keys(upd)) {
      const [ax, prop] = k.split('.');
      if (prop) div.layout[ax][prop] = upd[k];
    }
    return Promise.resolve();
  },
};
const ctx = {
  Plotly,
  document: {getElementsByClassName: () => [gd], addEventListener: () => {}},
  location: {search: ''},
  console,
};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), ctx);

const r = {};
const ticks = () => ({
  vals: gd.layout.xaxis.tickvals.map(paredPlotly),
  txts: gd.layout.xaxis.ticktext,
});
const rango = () => gd.layout.xaxis.range.map(paredPlotly);

r.rango_inicial = rango();
ctx._ajustarVista(gd);                 // lo que dispara el ?nav=ext al cargar
r.carga = Object.assign(ticks(), {rango: rango(), ymax: (gd.layout.yaxis.range || [])[1]});
ctx._ajustando = false;
ctx.mirovaVentana(30);
ctx._ajustando = false;
ctx._ajustarVista(gd);
r.v30 = Object.assign(ticks(), {rango: rango()});
console.log(JSON.stringify(r));
"""


def _correr(tmp_path, escenario):
    js = tmp_path / "nav.js"
    js.write_text(_script_navegacion(), encoding="utf-8")
    arnes = tmp_path / "arnes.js"
    arnes.write_text(ARNES, encoding="utf-8")
    env = dict(os.environ, TZ="America/Santiago")
    out = subprocess.run(["node", str(arnes), str(js), json.dumps(escenario)],
                         capture_output=True, text=True, env=env, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


# Caso real de Isluga publicado el 13-sep-2026: rango en hora Chile con offset
# (lo escribe plotly.py desde un datetime con zona) y datos en UTC sin zona.
ISLUGA = {
    "range": ["2026-08-14T00:00:00.036954-03:00", "2026-09-13T13:37:03.036954-03:00"],
    "trazas": [{
        "meta": "serie_vrp",
        "x": ["2026-08-20T05:00:00.000000", "2026-09-13T05:54:02.000000"],
        "y": [22.0, 0.12],
    }],
}
DIA = 86400000


@requiere_node
def test_al_cargar_los_ticks_quedan_dentro_del_eje(tmp_path):
    r = _correr(tmp_path, ISLUGA)
    x0, x1 = r["carga"]["rango"]
    vals = r["carga"]["vals"]
    assert len(vals) == 7
    fuera = [v for v in vals if not (x0 <= v <= x1)]
    assert not fuera, "ticks fuera del rango: Plotly los oculta"
    assert vals[-1] == x1


@requiere_node
def test_la_etiqueta_del_ultimo_tick_es_el_dia_del_borde(tmp_path):
    r = _correr(tmp_path, ISLUGA)
    assert r["carga"]["txts"][0] == "14 Ago"
    assert r["carga"]["txts"][-1] == "13 Sep"


@requiere_node
def test_ventana_1m_no_corre_el_borde_derecho(tmp_path):
    r = _correr(tmp_path, ISLUGA)
    x0, x1 = r["v30"]["rango"]
    assert x1 == r["rango_inicial"][1]
    assert x1 - x0 == 30 * DIA
    assert all(x0 <= v <= x1 for v in r["v30"]["vals"])
    assert r["v30"]["txts"][-1] == "13 Sep"


@requiere_node
def test_escala_y_ve_el_punto_pegado_al_borde(tmp_path):
    # Un punto a 1 h del borde derecho (hora de pared) tiene que entrar en la
    # escala. Con el reloj de JS en hora Chile quedaba afuera o adentro segun
    # la zona del computador que abre el grafico.
    esc = {
        "range": ["2026-08-14T00:00:00-03:00", "2026-09-13T13:00:00-03:00"],
        "trazas": [{"meta": "serie_vrp",
                    "x": ["2026-09-01T00:00:00", "2026-09-13T12:00:00"],
                    "y": [1.0, 10.0]}],
    }
    r = _correr(tmp_path, esc)
    assert r["carga"]["ymax"] == pytest.approx(15.0)

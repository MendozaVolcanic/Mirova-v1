"""
Tests del lector del panel "Last Month" de Dist.png como serie de tiempo
(dist_serie.py, distancia aproximada de cada pasada).

Por qué existe: Dist.png no es una foto de la pasada sino un gráfico de unos 30
días, donde cada pasada con anomalía queda dibujada como un marcador a la altura
de su distancia. El OCR de hoy lee sólo la estrella (la pasada de la cabecera);
leer el panel entero permite recuperar la distancia de pasadas cuya imagen propia
ya fue reemplazada. Estudio y verificador: repo VRP-chile,
experiments/_s151_distancia_ocr/ (INFORME.md y verificador/VERIFICADOR.md).

Fixture: imagen REAL de Nevados de Chillán VIIRS 375 escrita el 2026-10-15
14:06 UTC (mirova-tif-archive). Los valores esperados salen de correr el lector
del estudio (con scipy) sobre esta misma imagen.
"""
import os

import pytest

from conftest import FIXTURES

DIST_CHILLAN = os.path.join(FIXTURES, "dist", "chillan_viirs375_dist_20261015_140626.png")


def test_lee_geometria_del_panel():
    import dist_serie as D
    x = D.leer(DIST_CHILLAN)
    assert x is not None
    g = x["geo"]
    assert g["techo"] == pytest.approx(110.0, abs=1)
    assert g["eje"] == pytest.approx(295.0, abs=1)
    assert len(g["ticks"]) == 6
    # unos 15,2 px por día (marcas semanales separadas por ~106,5 px)
    assert 15.0 < g["ppd"] < 15.4


def test_lee_marcadores_estrella_y_punteada():
    import dist_serie as D
    x = D.leer(DIST_CHILLAN)
    ms = x["marcadores"]
    # 39 con el desempate al centro de la meseta; el lector del estudio lee 40 (decide el ruido numérico en un
    # empate y deja un pico a 3 px de su vecino). El re-control completo valida esta variante, no el conteo de una imagen.
    assert len(ms) == 39
    assert all(0.0 <= m["km"] <= 25.5 for m in ms)
    # la pasada de 22 MW del 2026-10-15 05:00 está cerca del cráter (informe §5: 0,41 a 1,49 km)
    assert any(m["tipo"] == "circulo" and 0.41 <= m["km"] <= 1.49 for m in ms)
    assert x["estrella"]["km"] == pytest.approx(0.94, abs=0.05)
    assert x["punteada"] == pytest.approx(731.0, abs=1)


TABLA_CHILLAN = os.path.join(FIXTURES, "dist", "tabla_chillan_viirs375_20260913_20261016.csv")
LM_CHILLAN = "2026-10-15 14:06:26"     # last_modified de la imagen (index_png.csv de mirova-tif-archive)


def _tabla():
    import pandas as pd
    t = pd.read_csv(TABLA_CHILLAN)
    t["t"] = pd.to_datetime(t.Fecha_Satelite_UTC)
    return t


def test_calado_reproduce_el_del_estudio():
    """El estudio cala esta imagen con 32 pareos, primera marca semanal el
    2026-09-15 y desfase +0,76 d (calculado con su código sobre esta misma
    tabla). Es uno de los 7 de 429 calados en el borde de la búsqueda (+0,80)."""
    import pandas as pd
    import dist_serie as D
    cal = D.calibrar(D.leer(DIST_CHILLAN), pd.Timestamp(LM_CHILLAN), _tabla())
    assert cal["L"] == pd.Timestamp("2026-09-15")
    assert 0.70 <= cal["desfase"] <= 0.78
    assert cal["pareos"] >= 30


def test_calado_ignora_filas_ocr():
    """Cambio 1 del verificador: las distancias del OCR no calan ni eliminan
    (del 06-13 al 10-08 discrepan en ~24 %). Una fila OCR que calzaría un
    marcador no debe sumar pareos."""
    import pandas as pd
    import dist_serie as D
    x = D.leer(DIST_CHILLAN)
    base = D.calibrar(x, pd.Timestamp(LM_CHILLAN), _tabla())
    ms = D.marcadores_t(x, base["L"], base["desfase"])
    libre = next(m for m in ms if D.pareos([m], _tabla()) == 0)
    ocr = pd.DataFrame([{"t": libre["t"], "Distancia_km": libre["km"], "Tipo_Registro": "ALERTA_TERMICA_OCR"}])
    con_ocr = pd.concat([_tabla(), ocr], ignore_index=True)
    assert D.calibrar(x, pd.Timestamp(LM_CHILLAN), con_ocr)["pareos"] == base["pareos"]


# ---------------------------------------------------------------- eliminación (tarea 3)
def _m(t, km):
    import pandas as pd
    return {"tipo": "circulo", "x": 0, "y": 0, "km": km, "t": pd.Timestamp(t)}


def _conocidas(filas):
    import pandas as pd
    d = pd.DataFrame(filas, columns=["t", "Distancia_km", "Tipo_Registro"])
    d["t"] = pd.to_datetime(d.t, format="mixed")
    return d


P ="2026-10-15 05:00:00"          # la pasada buscada


def test_eliminacion_unico():
    import dist_serie as D
    ms = [_m("2026-10-15 05:30", 0.9), _m("2026-10-15 06:10", 12.0)]
    otras = D.otras_de(P, _conocidas([("2026-10-15 06:10", 12.1, "FALSO_POSITIVO")]))
    r = D.eliminar(P, ms, otras)
    assert (r["clase"], r["km"], r["kmin"], r["kmax"], r["n_col"]) == ("unico", 0.9, 0.9, 0.9, 2)


def test_eliminacion_ambiguo_da_el_intervalo():
    import dist_serie as D
    ms = [_m("2026-10-15 05:00", 1.2), _m("2026-10-15 05:40", 23.5)]
    r = D.eliminar(P, ms, D.otras_de(P, _conocidas([])))
    assert (r["clase"], r["km"], r["kmin"], r["kmax"]) == ("ambiguo", None, 1.2, 23.5)


def test_eliminacion_solapado_y_sin_marcador():
    import dist_serie as D
    ms = [_m("2026-10-15 05:20", 3.0)]
    otras = D.otras_de(P, _conocidas([("2026-10-15 05:20", 3.2, "ALERTA_TERMICA")]))
    r = D.eliminar(P, ms, otras)
    assert (r["clase"], r["kmin"], r["kmax"]) == ("solapado", 3.0, 3.0)
    # un marcador de otra noche no cuenta: la columna queda vacía
    r = D.eliminar(P, [_m("2026-10-16 05:00", 3.0)], D.otras_de(P, _conocidas([])))
    assert r["clase"] == "sin_marcador" and r["n_col"] == 0


def test_eliminacion_no_descuenta_con_distancias_ocr():
    """Cambio 1: una fila OCR que calzaría el marcador no lo descuenta."""
    import dist_serie as D
    ms = [_m("2026-10-15 05:20", 3.0), _m("2026-10-15 05:50", 9.0)]
    otras = D.otras_de(P, _conocidas([("2026-10-15 05:50", 9.0, "ALERTA_TERMICA_OCR")]))
    assert len(otras) == 0
    assert D.eliminar(P, ms, otras)["clase"] == "ambiguo"


def test_otras_de_excluye_la_propia_pasada_y_otras_noches():
    import dist_serie as D
    c = _conocidas([(P, 1.0, "ALERTA_TERMICA"),                   # la misma pasada (menos de 3 min)
                    ("2026-10-15 05:02:30", 1.0, "RUTINA"),       # también la misma
                    ("2026-10-15 06:30", 5.0, "ALERTA_TERMICA"),  # misma noche
                    ("2026-10-16 05:00", 5.0, "ALERTA_TERMICA")]) # otra noche
    assert list(D.otras_de(P, c).Distancia_km) == [5.0]


# ---------------------------------------------------------------- elección de la imagen (tarea 4)
def _indice(filas):
    import pandas as pd
    return pd.DataFrame(filas, columns=["last_modified_utc", "md5", "png_path"])


def test_imagen_mas_reciente_dentro_de_1_a_25_dias():
    import dist_serie as D
    idx = _indice([("2026-10-15T12:00:00+00:00", "a", "hoy.png"),       # 0,3 d: muy pronto
                   ("2026-10-18T05:00:00+00:00", "b", "tres.png"),      # 3 d
                   ("2026-11-01T05:00:00+00:00", "c", "diecisiete.png"),  # 17 d: la más reciente válida
                   ("2026-11-12T05:00:00+00:00", "d", "veintiocho.png")])  # 28 d: fuera
    assert D.imagen_para(P, idx)["png_path"] == "diecisiete.png"


def test_sin_imagen_valida_queda_pendiente():
    import dist_serie as D
    assert D.imagen_para(P, _indice([("2026-10-15T12:00:00+00:00", "a", "hoy.png")])) is None
    assert D.imagen_para(P, _indice([("2026-11-12T05:00:00+00:00", "a", "tarde.png")])) is None


def test_md5_repetido_vale_por_su_primera_aparicion():
    """A106 de VRP-chile: MIROVA a veces vuelve a servir una imagen vieja bajo
    una hora nueva. La copia tardía tiene el contenido de la primera, así que su
    antigüedad es la de la primera: aquí 0,3 d, no 3 d."""
    import dist_serie as D
    idx = _indice([("2026-10-15T12:00:00+00:00", "a", "hoy.png"),
                   ("2026-10-18T05:00:00+00:00", "a", "hoy_reservida.png")])
    assert D.imagen_para(P, idx) is None


def test_pico_va_al_centro_de_la_meseta_de_empate():
    """Una meseta de tres filas empatadas: el pico es la fila del medio, no la de
    arriba ni la que elija el ruido numérico."""
    import numpy as np
    import dist_serie as D
    s = np.zeros((20, 20))
    s[8:11, 9] = 0.95
    s[9, 9] += 1e-16          # ruido como el de la correlación: no debe decidir
    picos = D._picos(s, 0.65)
    assert [(y, x) for y, x, _ in picos] == [(9, 9)]


def test_igual_al_lector_del_estudio_con_scipy():
    """El port usa OpenCV en vez de scipy (scipy no está en requirements). Si
    scipy está instalado, la correlación debe dar exactamente los mismos picos."""
    scipy_signal = pytest.importorskip("scipy.signal")
    import numpy as np
    import dist_serie as D
    rng = np.random.default_rng(0)
    mask = rng.random((60, 80)) > 0.7
    for tpl in [D.RING] + D.SQUARES:
        ref = scipy_signal.correlate2d(mask.astype(float), tpl.astype(float), mode="same") / tpl.sum()
        assert np.allclose(D._score(mask, tpl), ref)


# ---------------------------------------------------------------- decisión cerca o lejos (tarea 6)
def test_decision_cerca_lejos_e_indecidible_con_el_limite_del_volcan():
    """Margen de 0,6 km a cada lado del límite (la tolerancia de lectura del
    control). Villarrica tiene límite 5 km en volcanes.py."""
    import dist_serie as D
    assert D.decidir("unico", 4.3, 4.3, 4.3, "Villarrica") == "cerca"
    assert D.decidir("unico", 5.7, 5.7, 5.7, "Villarrica") == "lejos"
    assert D.decidir("unico", 5.2, 5.2, 5.2, "Villarrica") == "indecidible"
    # un intervalo decide sólo si cae entero de un lado
    assert D.decidir("ambiguo", None, 0.4, 1.5, "Villarrica") == "cerca"
    assert D.decidir("ambiguo", None, 1.2, 23.5, "Villarrica") == "indecidible"
    assert D.decidir("solapado", None, 8.0, 12.0, "Villarrica") == "lejos"


def test_decision_lee_el_limite_de_volcanes_py():
    """Los límites no se copian: Lastarria 3, Copahue 4, Tupungatito 7 y PCC 20
    (con el nombre del CSV y con el de MIROVA)."""
    import dist_serie as D
    import volcanes
    assert D.limite_km("Lastarria") == volcanes.LIMITES_Y_COORDENADAS["Lastarria"]["LIMITE_KM"] == 3.0
    assert D.decidir("unico", 3.8, 3.8, 3.8, "Lastarria") == "lejos"
    assert D.decidir("unico", 3.8, 3.8, 3.8, "Copahue") == "indecidible"
    assert D.decidir("unico", 6.2, 6.2, 6.2, "Tupungatito") == "cerca"
    assert D.decidir("unico", 8.0, 8.0, 8.0, "Puyehue-Cordon Caulle") == "cerca"
    assert D.decidir("unico", 8.0, 8.0, 8.0, "PuyehueCordonCaulle") == "cerca"


def test_sin_marcador_es_posible_lejos_nunca_cerca():
    """Sin marcador en la columna: la pasada puede estar a más de 25 km, que el
    panel no dibuja (en el control, 129 de 138 eran lejanas)."""
    import dist_serie as D
    assert D.decidir("sin_marcador", None, None, None, "Villarrica") == "posible >25 km"


def test_sin_lectura_no_decide():
    import dist_serie as D
    for metodo in ("pendiente", "calado_debil", "sin_control"):
        assert D.decidir(metodo, None, None, None, "Villarrica") is None


def test_tabla_solo_pasadas_dibujables_de_la_tabla():
    """Las conocidas son pasadas de latest.php con VRP > 0 y distancia: MIROVA
    sólo dibuja pasadas con anomalía, y las RUTINA traen Distancia_km = 0, que
    calzaría con cualquier marcador del cráter. Las filas OCR quedan fuera
    (cambio 1). El volcán se lleva al nombre de MIROVA, el del índice de PNG."""
    import pandas as pd
    import dist_serie as D
    c = pd.DataFrame([
        ("2026-10-15 05:00:00", "Puyehue-Cordon Caulle", "VIIRS375", 0.4, 7.7, "ALERTA_TERMICA"),
        ("2026-10-15 05:30:00", "Puyehue-Cordon Caulle", "VIIRS375", 0.0, 0.0, "RUTINA"),
        ("2026-10-15 06:00:00", "Puyehue-Cordon Caulle", "VIIRS375", 0.3, 7.9, "ALERTA_TERMICA_OCR"),
        ("2026-10-15 06:30:00", "Puyehue-Cordon Caulle", "VIIRS375", 0.3, None, "ALERTA_TERMICA"),
        ("2026-10-15 07:00:00", "Nevados de Chillan", "VIIRS", 9.0, 1.0, "ALERTA_TERMICA"),
        ("2026-10-15 07:10:00", "Nevados de Chillan", "VIIRS375", 22.1, 0.9, "ALERTA_TERMICA"),
    ], columns=["Fecha_Satelite_UTC", "Volcan", "Sensor", "VRP_MW", "Distancia_km", "Tipo_Registro"])
    t = D.tabla(c, "VIIRS375")
    # ordenadas por volcán y hora
    assert list(t.vol) == ["ChillanNevadosde", "PuyehueCordonCaulle"]
    assert list(t.t) == [pd.Timestamp("2026-10-15 07:10:00"), pd.Timestamp("2026-10-15 05:00:00")]


# ---------------------------------------------------------------- la cifra del OCR en la columna
def test_marcador_a_la_cifra_ocr_mas_uno_lejano_queda_ambiguo():
    """Si la columna trae un marcador a la cifra que midió el OCR y la
    eliminación se queda con otro lejano, la serie no sabe cuál es de esta
    pasada: en las pasadas OCR que también están en la tabla, con ese patrón la
    serie dijo «lejos» en 5 de 9 cuya verdad era cráter (VRP-chile, medición del
    2026-10-16). Se marca ambiguo con el intervalo de los dos, no «lejos»."""
    import dist_serie as D
    ms = [_m("2026-10-15 05:10", 0.95), _m("2026-10-15 05:40", 16.5)]
    r = D.con_cifra_ocr(P, ms, {"clase": "unico", "km": 16.5, "kmin": 16.5, "kmax": 16.5, "n_col": 2}, 0.95)
    assert (r["clase"], r["km"], r["kmin"], r["kmax"]) == ("ambiguo", None, 0.95, 16.5)
    assert D.decidir(r["clase"], r["km"], r["kmin"], r["kmax"], "Isluga") == "indecidible"


def test_cifra_ocr_sin_marcador_o_ya_elegida_no_cambia_nada():
    import dist_serie as D
    unico_lejos = {"clase": "unico", "km": 16.5, "kmin": 16.5, "kmax": 16.5, "n_col": 1}
    # sin marcador a la cifra del OCR (el caso diurno firme): la serie manda
    assert D.con_cifra_ocr(P, [_m("2026-10-15 05:40", 16.5)], unico_lejos, 0.95) == unico_lejos
    # la eliminación ya eligió el marcador de la cifra OCR
    ms = [_m("2026-10-15 05:10", 0.95), _m("2026-10-15 05:40", 16.5)]
    cerca = {"clase": "unico", "km": 0.95, "kmin": 0.95, "kmax": 0.95, "n_col": 2}
    assert D.con_cifra_ocr(P, ms, cerca, 0.95) == cerca
    # sin cifra del OCR (vacía o 0, que en el OCR es «no medida»)
    for ocr in (None, 0.0, float("nan")):
        assert D.con_cifra_ocr(P, ms, unico_lejos, ocr) == unico_lejos
    # el marcador de la cifra OCR es de otra noche
    assert D.con_cifra_ocr(P, [_m("2026-10-16 05:10", 0.95), _m("2026-10-15 05:40", 16.5)], unico_lejos, 0.95) == unico_lejos


# ---------------------------------------------------------------- umbral de calado débil (tarea 5)
def test_umbral_de_pareos_sale_del_control_portado():
    """PAREOS_MINIMOS no se elige: es el que da scripts/umbral_pareos.py sobre los
    dos controles corridos con este mismo lector (tests/fixtures/dist/control_juntas.csv).
    Si el lector, el calado o la regla cambian, hay que volver a correr el control."""
    import importlib.util
    import dist_serie as D
    ruta = os.path.join(os.path.dirname(FIXTURES), "..", "scripts", "umbral_pareos.py")
    spec = importlib.util.spec_from_file_location("umbral_pareos", ruta)
    U = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(U)
    X = U.juntar([os.path.join(FIXTURES, "dist", "control_juntas.csv")])
    assert len(X) == 2919
    assert U.umbral(X) == D.PAREOS_MINIMOS


def test_umbral_no_acepta_el_piso_por_construccion():
    """La regla mira la banda marginal, no el acumulado: con calados débiles que
    yerran más que el global, el umbral sube aunque el acumulado quede bajo el global."""
    import importlib.util
    import pandas as pd
    ruta = os.path.join(os.path.dirname(FIXTURES), "..", "scripts", "umbral_pareos.py")
    spec = importlib.util.spec_from_file_location("umbral_pareos", ruta)
    U = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(U)
    filas = [dict(pareos=p, dec="cerca", real="lejos" if (p < 6 and i == 0) else "cerca")
             for p in range(1, 31) for i in range(10)]
    X = pd.DataFrame(filas)
    assert U.umbral(X) == 6

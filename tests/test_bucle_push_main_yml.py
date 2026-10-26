"""El paso de push de main.yml no puede perder ni duplicar filas cuando otro ciclo empuja en medio.

POR QUE (auditoria 2026-10-22, H-T1; episodio nuevo del 2026-10-24 17:44 UTC, commit 53b1e6d3c0,
241 filas perdidas): una corrida hizo checkout del sha del despacho, espero runner 3,7 min, y al
empujar rebaso con `-X ours` sobre otro ciclo del scraper. La mezcla de texto de dos ordenes del
mismo CSV dejo filas dos veces o ninguna. Las pruebas de orden_registros cubren R1 (orden total);
esta cubre R2 y R3 en el workflow mismo: ejecuta el `run:` real del paso, tomado de main.yml, en
un repo de juguete. El scraper de mentira escribe en el orden VIEJO (empates al azar), el peor caso,
y la primera vez que corre hace que otro ciclo empuje antes que el. Asi la prueba no depende de R1.

Linea base roja: con el main.yml anterior al arreglo (pull --rebase -X ours) esta prueba falla.
"""
import os
import shutil
import subprocess
import sys
import textwrap

import pandas as pd
import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIENE_BASH = shutil.which("bash") is not None and shutil.which("git") is not None
NOMBRE_PASO = "Scraper, guarda y push (sin mezclar datos)"
CSV = "monitoreo_satelital/registro_vrp_consolidado.csv"

SCRAPER_FALSO = textwrap.dedent('''
    """Ciclo de mentira: refresca filas, agrega una pasada nueva y escribe con el orden VIEJO."""
    import os, subprocess, sys, pandas as pd
    ruta = "monitoreo_satelital/registro_vrp_consolidado.csv"
    marca = os.environ["MARCA_CICLO"]
    contador = marca + ".n"
    n = int(open(contador).read()) + 1 if os.path.exists(contador) else 1
    open(contador, "w").write(str(n))
    df = pd.read_csv(ruta)
    if n == 1 and os.environ.get("OTRO_CICLO"):
        # Mientras este ciclo trabaja, otro ciclo del scraper empuja primero.
        subprocess.run(["bash", os.environ["OTRO_CICLO"]], check=True)
    semilla = abs(hash((marca, n))) % 10_000
    df.loc[df.index[:40], "Ultima_Actualizacion"] = f"refresco {marca} {n}"
    nueva = {"timestamp": int(os.environ["TS_NUEVO"]), "Volcan": "Lascar", "Sensor": marca,
             "VRP_MW": 1.5, "Ultima_Actualizacion": "nueva"}
    df = pd.concat([df, pd.DataFrame([nueva])]).drop_duplicates(["timestamp", "Volcan", "Sensor"], keep="last")
    df = df.sample(frac=1, random_state=semilla).sort_values("timestamp", ascending=False)
    df.to_csv(ruta, index=False, lineterminator="\\n")
''')


def _base():
    filas = []
    for i in range(300):
        ts = 1_780_000_000 + 300 * i
        for v in ["Lascar", "Isluga", "Villarrica", "Llaima", "Copahue"]:
            for s in ["MODIS", "VIIRS375"]:
                filas.append({"timestamp": ts, "Volcan": v, "Sensor": s, "VRP_MW": 0.0,
                              "Ultima_Actualizacion": "2026-10-01 00:00:00"})
    return pd.DataFrame(filas)


def _sin_comentarios(run):
    return "\n".join(l for l in run.splitlines() if not l.lstrip().startswith("#"))


def _pasos(yml_texto):
    """(nombre, run) de cada paso, sin depender de PyYAML (no esta en requirements.txt): los `run: |`
    son bloques literales, asi que basta la sangria."""
    pasos, nombre, run, sangria = [], None, None, None
    for linea in yml_texto.splitlines():
        s = linea.lstrip(); ind = len(linea) - len(s)
        if run is not None:
            if s and ind <= sangria:
                pasos.append((nombre, "\n".join(run))); run = None
            else:
                run.append(linea[sangria + 2:] if len(linea) > sangria + 2 else "")
                continue
        if s.startswith("- name:"):
            nombre = s[len("- name:"):].strip()
        elif s.startswith("run: |") or s.startswith("run: >"):
            run, sangria = [], ind
        elif s.startswith("run:"):
            pasos.append((nombre, s[len("run:"):].strip()))
    if run is not None:
        pasos.append((nombre, "\n".join(run)))
    return pasos


def _script_del_paso(yml_texto):
    """El `run:` del paso que empuja."""
    for nombre, run in _pasos(yml_texto):
        if nombre == NOMBRE_PASO or "git push" in run:
            return run
    raise AssertionError("main.yml no tiene un paso que empuje")


def _script_desde_el_scraper(yml_texto):
    """Los `run:` desde el paso que corre scraper.py hasta el que empuja, en orden (el main.yml
    anterior al arreglo los tenia en pasos separados; con `bash -e` cada paso corta igual)."""
    trozos, dentro = [], False
    for _nombre, run in _pasos(yml_texto):
        dentro = dentro or "scraper.py" in run
        if dentro:
            trozos.append(run)
        if dentro and "git push" in run:
            return "\n".join(trozos)
    raise AssertionError("main.yml no corre scraper.py antes de empujar")


def _correr(yml_texto, tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "MSYS_NO_PATHCONV"}
    env["GIT_CONFIG_GLOBAL"] = str(tmp_path / "gitconfig_global")  # el paso hace git config --global
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    (tmp_path / "gitconfig_global").write_text("[core]\n\tautocrlf = false\n")

    def g(cwd, *a):
        r = subprocess.run(["git", *a], cwd=cwd, env=env, capture_output=True, text=True)
        assert r.returncode == 0, (a, r.stderr)
        return r.stdout

    remoto = tmp_path / "remoto.git"
    g(tmp_path, "init", "-q", "--bare", "-b", "main", str(remoto))
    url = remoto.as_uri()
    sem = tmp_path / "sem"
    g(tmp_path, "clone", "-q", url, str(sem))
    for c in ("user.email", "user.name"):
        g(sem, "config", c, "t")
    (sem / "monitoreo_satelital").mkdir()
    _base().to_csv(sem / CSV, index=False, lineterminator="\n")
    for nombre, contenido in {
        "scraper.py": SCRAPER_FALSO,
        "reponer_filas.py": "pass\n",
        "backfill_horas_utc.py": "pass\n",
    }.items():
        (sem / nombre).write_text(contenido)
    shutil.copy(os.path.join(RAIZ, "guarda_llaves.py"), sem / "guarda_llaves.py")
    g(sem, "add", ".")
    g(sem, "commit", "-qm", "base")
    g(sem, "push", "-q", "origin", "HEAD:main")

    script = _script_desde_el_scraper(yml_texto)
    paso = tmp_path / "paso.sh"
    paso.write_text(script)
    clones = {}
    for marca in ("A", "B"):
        d = tmp_path / marca
        g(tmp_path, "clone", "-q", "-b", "main", url, str(d))  # los dos parten de la misma base
        clones[marca] = d
    # Ciclo A: lo que hace otro runner mientras B trabaja.
    otro = tmp_path / "otro.sh"
    otro.write_text(f'cd "{clones["A"]}" && MARCA_CICLO=A TS_NUEVO=1790000001 '
                    f'bash -e "{paso}" > "{tmp_path / "A.log"}" 2>&1\n')
    envb = dict(env, MARCA_CICLO="B", TS_NUEVO="1790000002", OTRO_CICLO=str(otro),
                PATH=os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", ""))
    r = subprocess.run(["bash", "-e", str(paso)], cwd=clones["B"], env=envb, capture_output=True, text=True)
    final = subprocess.run(["git", "--git-dir", str(remoto), "show", f"main:{CSV}"],
                           env=env, capture_output=True, text=True).stdout
    return r, final


def _llaves(texto):
    import io
    df = pd.read_csv(io.StringIO(texto))
    return list(zip(df["timestamp"], df["Volcan"], df["Sensor"]))


@pytest.mark.skipif(not TIENE_BASH, reason="hace falta bash y git")
def test_push_concurrente_no_pierde_ni_duplica(tmp_path):
    yml = open(os.path.join(RAIZ, ".github", "workflows", "main.yml"), encoding="utf-8").read()
    r, final = _correr(yml, tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    llaves = _llaves(final)
    esperadas = set(_llaves(_base().to_csv(index=False))) | {(1790000001, "Lascar", "A"), (1790000002, "Lascar", "B")}
    assert len(llaves) == len(set(llaves)), "el push dejo llaves repetidas"
    assert esperadas - set(llaves) == set(), f"el push perdio {len(esperadas - set(llaves))} llaves"


def test_paso_de_push_no_mezcla_datos_como_texto():
    """Regla estructural: ni -X ours ni rebase en el paso que empuja el consolidado, y la guarda antes del push."""
    script = _sin_comentarios(_script_del_paso(open(os.path.join(RAIZ, ".github", "workflows", "main.yml"), encoding="utf-8").read()))
    assert "-X ours" not in script and "--strategy-option" not in script
    assert "rebase" not in script.replace("rebasar", "")
    i_reset, i_scraper = script.index("git reset --hard origin/main"), script.index("python scraper.py")
    i_guarda, i_push = script.index("python guarda_llaves.py"), script.index("git push origin main")
    assert i_reset < i_scraper < i_guarda < i_push


def test_push_del_ocr_no_resuelve_choques_a_ciegas():
    """ocr_workflow.yml: el rebase del push va sin -X ours (si choca, rojo) y la guarda del OCR antes del push."""
    pasos = _pasos(open(os.path.join(RAIZ, ".github", "workflows", "ocr_workflow.yml"), encoding="utf-8").read())
    push = [run for nombre, run in pasos if (nombre or "").startswith("Guardar cambios")
            or ("git push" in run and "registro_vrp_ocr.csv" in run)]
    assert push, "no encontre el paso de push del OCR"
    for run in map(_sin_comentarios, push):
        assert "-X ours" not in run and "--strategy-option" not in run
    guardar = _sin_comentarios(next(run for nombre, run in pasos if (nombre or "").startswith("Guardar cambios")))
    assert guardar.index("guarda_llaves.py") < guardar.index("git push origin main")

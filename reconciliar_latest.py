"""
reconciliar_latest.py — Auto-corrección OCR contra latest.php (MIROVA).

latest.php es la tabla AUTORITATIVA de MIROVA (trae la distancia exacta). El OCR,
en cambio, estima la distancia visualmente y puede ubicar mal un foco lejano como
si fuera dentro de radio (error histórico del método de estrella, pre-V29).

Este sweep busca eventos OCR guardados como ALERTA_TERMICA_OCR que tengan el
MISMO (timestamp, volcán, sensor) marcado FALSO_POSITIVO en latest.php y los
reclasifica a FALSO_POSITIVO_OCR con la distancia real. Como latest.php es la
verdad eventual, esto cierra el hueco sin importar la causa (carrera de tiempos,
estrella, o un bug futuro). Se ejecuta cada ciclo en ocr_workflow, ANTES del merger.

Los eventos NO se borran: quedan en registro_vrp_ocr.csv como referencia MIROVA;
solo salen del publicable por pasar a FALSO_POSITIVO.
"""
import os
import pandas as pd

CARPETA = "monitoreo_satelital"
DB_OCR = os.path.join(CARPETA, "registro_vrp_ocr.csv")
DB_CONS = os.path.join(CARPETA, "registro_vrp_consolidado.csv")


def reconciliar(df_ocr, df_cons, marca=""):
    """
    Reclasifica ALERTA_TERMICA_OCR -> FALSO_POSITIVO_OCR cuando latest.php tiene el
    MISMO (ts, volcán, sensor) como FALSO_POSITIVO. Devuelve (df_ocr, n_corregidos).
    Idempotente: una vez reclasificado ya no es ALERTA, no se vuelve a tocar.
    """
    if df_ocr.empty or df_cons.empty:
        return df_ocr, 0
    fp = {(int(r.timestamp), r.Volcan, r.Sensor): float(r.Distancia_km)
          for _, r in df_cons.iterrows() if r.Tipo_Registro == 'FALSO_POSITIVO'}
    n = 0
    for i, r in df_ocr.iterrows():
        if r.Tipo_Registro != 'ALERTA_TERMICA_OCR':
            continue
        key = (int(r.timestamp), r.Volcan, r.Sensor)
        if key in fp:
            dist = round(fp[key], 2)
            df_ocr.at[i, 'Tipo_Registro'] = 'FALSO_POSITIVO_OCR'
            df_ocr.at[i, 'Confianza_Validacion'] = 'baja'
            df_ocr.at[i, 'Distancia_km'] = dist
            df_ocr.at[i, 'Requiere_Verificacion'] = False
            df_ocr.at[i, 'Editado'] = 'AUTO'
            base = str(r.Nota_Validacion).split(' | RECONCILIADO')[0]
            df_ocr.at[i, 'Nota_Validacion'] = (
                base + f" | RECONCILIADO{(' ' + marca) if marca else ''}: latest.php (MIROVA) "
                f"= FALSO_POSITIVO @ {dist} km (el OCR lo tenía como ALERTA por mala ubicación).")
            n += 1
    return df_ocr, n


def main():
    if not (os.path.exists(DB_OCR) and os.path.exists(DB_CONS)):
        print("ℹ️ Falta algún CSV — nada que reconciliar"); return
    from datetime import datetime
    import pytz
    marca = datetime.now(pytz.utc).strftime("%Y-%m-%d")
    df_ocr = pd.read_csv(DB_OCR)
    df_cons = pd.read_csv(DB_CONS)
    df_ocr, n = reconciliar(df_ocr, df_cons, marca=marca)
    print(f"🔁 Reconciliación OCR↔latest.php: {n} eventos reclasificados a FALSO_POSITIVO")
    if n > 0:
        df_ocr.to_csv(DB_OCR, index=False)
        print(f"   ✅ {DB_OCR} actualizado")


if __name__ == "__main__":
    main()

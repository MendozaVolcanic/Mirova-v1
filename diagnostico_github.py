#!/usr/bin/env python3
"""
DIAGNOSTICO_GITHUB.py
Ejecutar ANTES de scraper_ocr.py para verificar el entorno
"""

import sys
import os

print("="*80)
print("🔍 DIAGNÓSTICO ENTORNO GITHUB ACTIONS")
print("="*80)

# Test 1: Python version
print(f"\n1️⃣ PYTHON VERSION:")
print(f"   {sys.version}")
print(f"   Executable: {sys.executable}")

# Test 2: Módulos requeridos
print(f"\n2️⃣ MÓDULOS REQUERIDOS:")

modulos_requeridos = [
    'requests',
    'pandas',
    'pytz',
    'PIL',
    'cv2',
    'numpy',
    'pytesseract'
]

for mod in modulos_requeridos:
    try:
        __import__(mod)
        print(f"   ✅ {mod}")
    except ImportError as e:
        print(f"   ❌ {mod}: {e}")

# Test 3: Archivo ocr_utils.py existe
print(f"\n3️⃣ ARCHIVOS:")

archivos_criticos = [
    'ocr_utils.py',
    'scraper_ocr.py',
    'monitoreo_satelital/registro_vrp_ocr.csv',
    'monitoreo_satelital/registro_vrp_consolidado.csv'
]

for archivo in archivos_criticos:
    existe = os.path.exists(archivo)
    status = "✅" if existe else "❌"
    print(f"   {status} {archivo}")
    
    if existe and archivo.endswith('.py'):
        size = os.path.getsize(archivo) / 1024
        print(f"      Tamaño: {size:.1f} KB")

# Test 4: Test import ocr_utils
print(f"\n4️⃣ TEST IMPORT ocr_utils:")

try:
    import ocr_utils
    print(f"   ✅ Import exitoso")
    
    # Verificar funciones
    funciones = ['extraer_eventos_latest10nti', 'analizar_puntos_distancia',
                 'clasificar_confianza', 'verificar_evento_no_existe']
    
    for func in funciones:
        if hasattr(ocr_utils, func):
            print(f"   ✅ {func}")
        else:
            print(f"   ❌ FALTA: {func}")

except ImportError as e:
    print(f"   ❌ Error import: {e}")
    import traceback
    traceback.print_exc()

except Exception as e:
    print(f"   ❌ Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("✅ DIAGNÓSTICO COMPLETADO")
print("="*80)

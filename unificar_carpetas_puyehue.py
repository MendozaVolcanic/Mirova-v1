"""
UNIFICAR_CARPETAS_PUYEHUE.PY
Unifica imagenes_satelitales/Puyehue-Cordon Caulle/ + Puyehue_Cordon_Caulle/
Elimina la carpeta con guión bajo (incorrecta)

PROBLEMA:
- Carpeta 1: Puyehue-Cordon Caulle (guión) ← CORRECTA
- Carpeta 2: Puyehue_Cordon_Caulle (guión bajo) ← INCORRECTA

SOLUCIÓN:
1. Mover todas las imágenes de carpeta 2 a carpeta 1 (por fecha)
2. Eliminar carpeta 2
3. Actualizar paths en CSVs si es necesario

USO EN GITHUB:
1. Subir a raíz del repo
2. Crear workflow manual para ejecutarlo
3. Ejecutar desde Actions
"""

import os
import shutil
from datetime import datetime

# =========================
# CONFIGURACIÓN
# =========================

CARPETA_BASE = "monitoreo_satelital/imagenes_satelitales"
CARPETA_CORRECTA = os.path.join(CARPETA_BASE, "Puyehue-Cordon Caulle")
CARPETA_INCORRECTA = os.path.join(CARPETA_BASE, "Puyehue_Cordon_Caulle")

# =========================
# FUNCIONES
# =========================

def listar_imagenes(carpeta):
    """Lista todas las imágenes PNG en una carpeta"""
    imagenes = []
    
    if not os.path.exists(carpeta):
        return imagenes
    
    for root, dirs, files in os.walk(carpeta):
        for file in files:
            if file.endswith('.png'):
                path_completo = os.path.join(root, file)
                imagenes.append(path_completo)
    
    return imagenes


def mover_imagen_con_estructura(path_origen, carpeta_destino_base):
    """
    Mueve imagen manteniendo estructura de subcarpetas (por fecha)
    
    Ejemplo:
    origen: Puyehue_Cordon_Caulle/2026-02-10/05-42-01_..._Latest.png
    destino: Puyehue-Cordon Caulle/2026-02-10/05-42-01_..._Latest.png
    """
    
    # Extraer estructura relativa (fecha + archivo)
    # path_origen = "imagenes_satelitales/Puyehue_Cordon_Caulle/2026-02-10/archivo.png"
    # Queremos: "2026-02-10/archivo.png"
    
    partes = path_origen.split(os.sep)
    
    # Buscar índice de "Puyehue_Cordon_Caulle"
    try:
        idx_volcan = partes.index("Puyehue_Cordon_Caulle")
    except ValueError:
        print(f"   ⚠️ No se pudo parsear path: {path_origen}")
        return False
    
    # Estructura relativa: ["2026-02-10", "archivo.png"]
    estructura_relativa = partes[idx_volcan + 1:]
    
    # Path destino
    path_destino = os.path.join(carpeta_destino_base, *estructura_relativa)
    
    # Crear carpeta destino si no existe
    carpeta_destino = os.path.dirname(path_destino)
    os.makedirs(carpeta_destino, exist_ok=True)
    
    # Verificar si ya existe
    if os.path.exists(path_destino):
        # Comparar tamaños
        tamano_origen = os.path.getsize(path_origen)
        tamano_destino = os.path.getsize(path_destino)
        
        if tamano_origen == tamano_destino:
            # Duplicado exacto → eliminar origen
            os.remove(path_origen)
            return 'duplicado'
        else:
            # Tamaños diferentes → mover con sufijo _dup
            nombre_archivo = os.path.basename(path_destino)
            nombre_sin_ext, ext = os.path.splitext(nombre_archivo)
            path_destino_dup = os.path.join(carpeta_destino, f"{nombre_sin_ext}_dup{ext}")
            
            shutil.move(path_origen, path_destino_dup)
            return 'movido_dup'
    else:
        # No existe → mover normalmente
        shutil.move(path_origen, path_destino)
        return 'movido'


def eliminar_carpeta_vacia(carpeta):
    """Elimina carpeta si está vacía (recursivamente)"""
    
    if not os.path.exists(carpeta):
        return False
    
    try:
        # Verificar si está vacía
        contenido = []
        for root, dirs, files in os.walk(carpeta):
            contenido.extend(files)
            contenido.extend(dirs)
        
        if len(contenido) == 0:
            shutil.rmtree(carpeta)
            return True
        else:
            print(f"   ⚠️ Carpeta no está vacía: {len(contenido)} items restantes")
            return False
    except Exception as e:
        print(f"   ❌ Error eliminando carpeta: {e}")
        return False


def main():
    """Proceso principal"""
    
    print("="*80)
    print("🔧 UNIFICADOR DE CARPETAS PUYEHUE")
    print("="*80)
    
    # Verificar que existan las carpetas
    print(f"\n📂 Verificando carpetas...")
    
    if not os.path.exists(CARPETA_CORRECTA):
        print(f"   ❌ No existe carpeta correcta: {CARPETA_CORRECTA}")
        print(f"   💡 Creando carpeta...")
        os.makedirs(CARPETA_CORRECTA, exist_ok=True)
    else:
        print(f"   ✅ Carpeta correcta existe: {CARPETA_CORRECTA}")
    
    if not os.path.exists(CARPETA_INCORRECTA):
        print(f"   ℹ️ No existe carpeta incorrecta: {CARPETA_INCORRECTA}")
        print(f"   ✅ No hay nada que unificar")
        print("="*80)
        return
    else:
        print(f"   ⚠️ Carpeta incorrecta existe: {CARPETA_INCORRECTA}")
    
    # Listar imágenes en carpeta incorrecta
    print(f"\n📸 Listando imágenes en carpeta incorrecta...")
    imagenes_incorrecta = listar_imagenes(CARPETA_INCORRECTA)
    
    if not imagenes_incorrecta:
        print(f"   ℹ️ No hay imágenes en carpeta incorrecta")
        print(f"   🗑️ Eliminando carpeta vacía...")
        eliminar_carpeta_vacia(CARPETA_INCORRECTA)
        print("="*80)
        return
    
    print(f"   📊 Total imágenes a mover: {len(imagenes_incorrecta)}")
    
    # Mover imágenes
    print(f"\n🚚 Moviendo imágenes...")
    
    stats = {
        'movido': 0,
        'duplicado': 0,
        'movido_dup': 0,
        'error': 0
    }
    
    for img_path in imagenes_incorrecta:
        resultado = mover_imagen_con_estructura(img_path, CARPETA_CORRECTA)
        
        if resultado:
            stats[resultado] += 1
            
            if stats['movido'] + stats['duplicado'] + stats['movido_dup'] <= 10:
                nombre_archivo = os.path.basename(img_path)
                if resultado == 'movido':
                    print(f"   ✅ Movido: {nombre_archivo}")
                elif resultado == 'duplicado':
                    print(f"   🔁 Duplicado eliminado: {nombre_archivo}")
                elif resultado == 'movido_dup':
                    print(f"   ⚠️ Conflicto (movido como _dup): {nombre_archivo}")
        else:
            stats['error'] += 1
    
    if len(imagenes_incorrecta) > 10:
        print(f"   ... y {len(imagenes_incorrecta) - 10} más")
    
    # Eliminar carpeta incorrecta
    print(f"\n🗑️ Eliminando carpeta incorrecta...")
    
    if eliminar_carpeta_vacia(CARPETA_INCORRECTA):
        print(f"   ✅ Carpeta eliminada: {CARPETA_INCORRECTA}")
    else:
        print(f"   ⚠️ Carpeta NO pudo eliminarse (puede tener archivos restantes)")
    
    # Resumen
    print(f"\n{'='*80}")
    print(f"✅ UNIFICACIÓN COMPLETADA")
    print(f"{'='*80}")
    print(f"   Imágenes movidas: {stats['movido']}")
    print(f"   Duplicados eliminados: {stats['duplicado']}")
    print(f"   Conflictos (movidos como _dup): {stats['movido_dup']}")
    print(f"   Errores: {stats['error']}")
    print(f"\n📁 Carpeta unificada: {CARPETA_CORRECTA}")
    print("="*80)


if __name__ == "__main__":
    main()

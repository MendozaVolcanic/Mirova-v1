# 📦 Plan de almacenamiento de evidencia visual (item #8 — DIFERIDO)
**Decisión de Nicolás (2026-06-12):** migrar lo más viejo a **GitHub Releases**
cuando estemos cerca de un límite.

## ⚠️ Estado actual: MÁS CERCA DE LO ESPERADO
- Tamaño del repo (API GitHub, 12-jun-2026): **4.41 GB**.
- Límites de GitHub: recomendado <1 GB, *strongly recommended* <5 GB (a partir de
  ahí pueden llegar avisos); límite duro por push 2 GB.
- Crecimiento: ~2.300 imágenes de evidencia y subiendo con cada alerta.
- **Estamos a ~0.6 GB del umbral de 5 GB** → planificar la primera migración
  en semanas, no meses.

## Plan acordado (cuando se ejecute)
1. Crear un Release por trimestre (ej. `evidencia-2026Q1`) con un ZIP de
   `imagenes_satelitales/` de ese período (Releases no cuentan contra el tamaño
   del repo; límite 2 GB por archivo).
2. Borrar esas carpetas del working tree (commit normal).
3. **Importante:** el tamaño del repo lo domina el HISTORIAL git, no el working
   tree — borrar archivos no reduce los 4.41 GB. Para recuperar espacio real
   haría falta reescribir historial (`git filter-repo` de imagenes_satelitales/
   antiguas) + push forzado. Eso invalida clones existentes → coordinar.
   Alternativa sin reescritura: aceptar el historial actual (~4.4 GB congelado)
   y solo evitar crecimiento futuro (migración periódica + borrado).
4. Los enlaces del dashboard a evidencia (github.com/.../tree/...) dejarán de
   funcionar para lo migrado → si importa, generar un índice de redirección
   (CSV período→URL del Release) o aceptar que la evidencia vieja se consulta
   desde Releases.

## Disparador
Revisar `gh api repos/MendozaVolcanic/Mirova-v1 --jq .size` (KB) al inicio de
sesión de mantenimiento; ejecutar el plan al superar ~4.8 GB o ante aviso de GitHub.

---
## ✅ EJECUTADO 2026-06-13 (primera migración)
- Repo en **4.48 GB** (.git) | working tree era **988 MB** (cerca del límite 1 GB de Pages).
- Creado workflow reutilizable **`.github/workflows/archivar_evidencia.yml`**
  (workflow_dispatch, input `antes_de=YYYY-MM-DD`): zipea las carpetas viejas,
  las sube a un Release y las borra del working tree (commit con pull-rebase).
- **Primera corrida (corte 2026-04-01):** Release **`evidencia-pre-2026-04-01`**
  con `evidencia_pre_2026-04-01.zip` (**361 MB**, ene–mar). Working tree:
  **988 → 622 MB** (-37%); imágenes 5905 → 3636.
- Honesto: el **.git sigue en 4.48 GB** (el historial conserva todo; solo un
  rewrite lo baja — decisión diferida hasta que GitHub avise).

## Cómo repetir (cada trimestre o al acercarse working tree a ~900 MB)
- Actions → "Archivar evidencia vieja" → Run → `antes_de` = inicio del próximo
  trimestre (ej. `2026-07-01`). Genera un Release nuevo por tag.
- ⚠️ NO re-correr el MISMO corte: el `--clobber` sobreescribiría el ZIP bueno
  con uno chico. Cada migración usa una fecha de corte distinta (tag distinto).
- Efecto: baja el sitio de Pages y el checkout; NO baja el .git.

## Pendiente (decisión de Nicolás, no ejecutado)
- **Reducir crecimiento futuro**: hoy se commitean 4 PNG por alerta (VRP, logVRP,
  Latest10NTI, Dist). Bajar a 2 (VRP + Dist) ~halvaría el crecimiento de .git y
  working tree. Es cambio de comportamiento → requiere tu OK.
- **Rewrite de historial** (`git filter-repo` de imagenes viejas): única forma de
  recuperar los ~4 GB de .git. Destructivo (reescribe SHAs, rompe clones, hay que
  pausar los bots). Solo cuando GitHub lo exija y coordinado.

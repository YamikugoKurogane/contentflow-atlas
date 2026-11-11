# ContentFlow – MongoDB Atlas (Evaluación Parcial 2, BDY0101, Forma A)

Base del proyecto: importación, conversión de fechas, validación y corrección de datos.
Lenguaje: Python 3 + pymongo. **Las credenciales van solo en `.env` (nunca en el repo).**

## Estructura
```
data/        JSON del anexo (campanas.json ya sin ñ)
scripts/     01 conexión · 02 importar · 03 fechas · 04 validar · 05 corregir · 06 índices
docs/evidencias/  JSON de evidencia que genera cada script (úsalos en el informe)
logs/        registros de ejecución (no se suben)
```

## Paso a paso

### A. MongoDB Atlas (en el navegador)
1. Crea cuenta en https://cloud.mongodb.com y un **proyecto** (ej. `ContentFlow`).
2. **Create cluster → M0 (Free)**. Anota: nombre (ej. `contentflow-m0`), proveedor (AWS) y región.
   Para Chile conviene **AWS São Paulo (sa-east-1)** por cercanía.
3. **Database Access → Add New Database User**: método *Password*, rol *Specific Privileges* →
   `readWrite` sobre la base `contentflow`. Guarda la contraseña.
4. **Network Access → Add IP Address**: usa *Add Current IP*. (`0.0.0.0/0` solo si cambias de red;
   justifícalo en el informe como medida temporal de desarrollo.)
5. **Connect → Drivers → Python**: copia el string `mongodb+srv://...`.

### B. Tu computador
```bash
git clone <URL-de-tu-repo> && cd contentflow
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env
```
Edita `.env` con tu usuario, contraseña y cluster. Si la contraseña tiene `@ : / ? # %`, codifícala.

### C. Ejecutar en este orden
```bash
python scripts/01_verificar_conexion.py     # ping + concerns + almacenamiento
python scripts/02_importar_datos.py         # carga los 5 JSON y compara conteos
python scripts/03_convertir_fechas.py       # string ISO -> Date (documenta antes/después)
python scripts/04_validar_datos.py          # detecta inconsistencias (solo lectura)
python scripts/05_corregir_datos.py         # simulación
python scripts/05_corregir_datos.py --aplicar
python scripts/04_validar_datos.py          # repetir: evidencia "después"
```
Resultados esperados:

| Paso | Esperado |
|---|---|
| 02 | 500 documentos en cada una de las 5 colecciones |
| 03 | 6 campos convertidos; tipos finales = `date` |
| 04 (antes) | reacciones duplicadas 1 · reacciones antes de publicación 245 · comentarios antes de publicación 251 · publicaciones antes de registro 48 · reacciones antes de registro 53 · nombres de campaña repetidos 91 · autoreacciones 1 · autocomentarios 1 · pubs sin campaña 22 · usuarios sin actividad 31 · referencias inválidas 0 |
| 05 --aplicar | 1 reacción eliminada (respaldada en `auditoria_correcciones`); marcas `inconsistencia_temporal` según los 4 chequeos temporales (245, 251, 48 y 53 casos; una reacción puede caer en dos chequeos, así que los documentos únicos marcados pueden ser menos de 597) |
| 04 (después) | reacciones duplicadas 0; los temporales siguen apareciendo (están marcados, no borrados) |

### D. Segunda herramienta de conectividad (exigida por la rúbrica)
Abre **MongoDB Compass** con el mismo string, entra a `contentflow` y toma captura de las 5 colecciones
con sus conteos. También sirve el Data Explorer de Atlas.

### E. Qué capturar para el informe (evidencias)
- Cluster M0 (nombre, proveedor, región), Database Access y Network Access (sin mostrar contraseña).
- Salida de los scripts 01–05 (la salida queda en `logs/` y `docs/evidencias/*.json`).
- Compass/Data Explorer mostrando las colecciones.
- Un documento antes y después de la conversión de fechas (`$type`).

### F. Subir al repositorio
Verifica antes de `git push` que `.env` NO aparece en `git status`. Da acceso a tu docente
(repo público o añadiéndolo como colaborador) y pega el enlace en AVA al inicio del proyecto.

## Siguientes etapas (pendientes)
7. `07_consultas.py`: filtros, proyecciones, `$match/$group/$lookup/$unwind/$sort`, y `explain("executionStats")`
   **antes** de ejecutar `06_crear_indices.py`; luego repetir el explain.
8. Script CRUD de casos de negocio, API REST (Flask/FastAPI) con ≥2 colecciones, colección Postman, informe PDF.

## Notas de configuración para el informe
- Write concern `majority` y read concern `majority` (definidos en `scripts/common.py`).
- M0: 512 MB, máx. 500 conexiones, sin sharding; los ~2.500 documentos ocupan una fracción mínima.
- Se agrega la colección técnica `auditoria_correcciones` (respaldo de lo eliminado); no es parte de las 5 requeridas.

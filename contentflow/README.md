# ContentFlow – MongoDB Atlas (Evaluación Parcial 2, BDY0101, Forma A)

Importación, validación, consultas, explain, CRUD y API REST.
Lenguaje: Python 3 + pymongo. **Las credenciales van solo en `.env` (nunca en el repo).**

## Estructura
```
data/        JSON del anexo (campanas.json ya sin ñ)
scripts/     01 conexión · 02 importar · 03 fechas · 04 validar · 05 corregir · 06 índices
             07 consultas · 08 explain · 09 CRUD
api/         API REST (Flask)
postman/     colección de Postman
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

## Etapa 2: consultas, eficiencia, CRUD y API

### Consultas de negocio (apartado 4)
```bash
python scripts/07_consultas.py              # 5 consultas find + 8 agregaciones
python scripts/07_consultas.py --solo A1,A7 # solo algunas
```
Cada consulta indica el requerimiento de negocio que responde (usuarios más activos, contenidos
populares, horarios, perfil de audiencia, éxito de campañas). Evidencia: `docs/evidencias/07_consultas.json`.

### Eficiencia con explain (apartado 4, IE6)
```bash
python scripts/08_explain_indices.py
```
Mide 3 consultas **sin índice** (COLLSCAN) y **con índice** (IXSCAN), 5 repeticiones cada una, y
muestra tiempo (mediana), documentos examinados vs retornados y tipo de acceso.
Con solo 500 documentos los tiempos son de pocos milisegundos; el indicador más claro es
la cantidad de documentos examinados. Al terminar, los 3 índices quedan creados.
Después puedes ejecutar `06_crear_indices.py` para crear el resto de los índices.

### CRUD (apartado 5, IE7 e IE8)
```bash
python scripts/09_crud.py
```
Caso "lanzamiento de una publicación en una campaña": crea usuario, publicación, reacciones y
comentario; actualiza con `$set`, `$inc` y `$push`; prueba 3 validaciones que deben rechazarse
(referencia inexistente, duplicado, usuario inexistente); elimina todo y comprueba que los
conteos finales sean iguales a los iniciales. Los datos de prueba tienen `_id` con prefijo `demo_`.

### API REST (apartados 6 y 7, IE9 a IE11)
```bash
python api/app.py          # http://127.0.0.1:5000
```
Endpoints principales:

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Prueba de conectividad con Atlas |
| GET/POST | `/publicaciones` | Listar (filtros `categoria`, `tipo`, `usuario_id`, `limit`) / crear |
| GET/PATCH/DELETE | `/publicaciones/<id>` | Leer / editar / eliminar (con sus reacciones y comentarios) |
| GET/POST | `/reacciones` | Listar / crear (409 si ya existe, 422 si la referencia no existe) |
| DELETE | `/reacciones/<id>` | Eliminar |
| GET/POST | `/comentarios` | Listar / crear |
| POST | `/comentarios/<id>/like` | Suma un like con `$inc` |
| DELETE | `/comentarios/<id>` | Eliminar |
| GET | `/campanas` | Listar campañas |
| GET | `/estadisticas/publicaciones-populares` | Agregación de popularidad |

Códigos de error: 400 (datos inválidos o faltantes), 404 (no existe), 409 (duplicado),
422 (referencia inválida), 503 (sin conexión con la base), 500 (error interno).
Cada solicitud queda registrada en `logs/api.log` (método, ruta, estado y duración).

**Postman:** importa `postman/ContentFlow_API.postman_collection.json` y ejecútala con el
*Collection Runner* (16 solicitudes con pruebas automáticas; la API debe estar corriendo).
Mientras ejecutas, abre Compass o Atlas para mostrar el reflejo de los datos en la base.

## Qué capturar en esta etapa
- Salida de `07_consultas.py` (una o dos consultas find y las agregaciones A1, A3 y A7).
- Salida del `08_explain_indices.py` (la tabla comparativa) y la pestaña *Indexes* de Compass.
- Salida del `09_crud.py` (pasos C, R, U, V y D con sus ANTES y DESPUÉS).
- API corriendo en la terminal, `GET /health` en Postman, resultado del Collection Runner
  y, para la escritura en tiempo real, la publicación creada vista en Compass (y su eliminación).
- Un error provocado en Postman: 404, 409, 422 y 400, con el JSON de respuesta.

## Notas de configuración para el informe
- Write concern `majority` y read concern `majority` (definidos en `scripts/common.py` y en `api/app.py`).
- M0: 512 MB, máx. 500 conexiones, sin sharding; los ~2.500 documentos ocupan una fracción mínima.
- Se agrega la colección técnica `auditoria_correcciones` (respaldo de lo eliminado); no es parte de las 5 requeridas.

"""API REST de ContentFlow conectada a MongoDB Atlas (apartados 6 y 7, IE9, IE10 e IE11).

Librerías: Flask (servidor HTTP), pymongo (driver oficial) y python-dotenv (variables de entorno).
El string de conexión se lee SOLO de la variable de entorno MONGODB_URI (archivo .env, no versionado).

Ejecutar desde la raíz del repositorio:
    python api/app.py
"""
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, g, jsonify, request
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import ConnectionFailure, DuplicateKeyError, PyMongoError, ServerSelectionTimeoutError
from werkzeug.exceptions import HTTPException

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# ---------------------------------------------------------------- logging (trazabilidad)
(ROOT / "logs").mkdir(exist_ok=True)
log = logging.getLogger("contentflow.api")
if not log.handlers:
    log.setLevel(logging.INFO)
    _fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    for h in (logging.FileHandler(ROOT / "logs" / "api.log", encoding="utf-8"), logging.StreamHandler()):
        h.setFormatter(_fmt)
        log.addHandler(h)

app = Flask(__name__)
app.json.ensure_ascii = False

CATEGORIAS = {"Tecnología", "Cultura", "Educación", "Deportes", "Entretenimiento"}
TIPOS = {"Imagen", "Video", "Texto"}
REACCIONES = {"Me gusta", "Me encanta", "Me entristece", "Me enoja"}

# ---------------------------------------------------------------- conexión
_client = None
_db = None


def get_db():
    """Crea el cliente una sola vez (pool de conexiones). Usa majority para lecturas y escrituras."""
    global _client, _db
    if _db is None:
        uri = os.getenv("MONGODB_URI")
        if not uri:
            raise ApiError(503, "Falta la variable de entorno MONGODB_URI")
        _client = MongoClient(uri, serverSelectionTimeoutMS=5000, maxPoolSize=10,
                              w="majority", readConcernLevel="majority", retryWrites=True)
        _db = _client[os.getenv("DB_NAME", "contentflow")]
    return _db


# ---------------------------------------------------------------- errores
class ApiError(Exception):
    def __init__(self, status, mensaje, detalle=None):
        self.status, self.mensaje, self.detalle = status, mensaje, detalle


def respuesta_error(status, mensaje, detalle=None):
    cuerpo = {"error": {"codigo": status, "mensaje": mensaje}}
    if detalle:
        cuerpo["error"]["detalle"] = detalle
    return jsonify(cuerpo), status


@app.errorhandler(ApiError)
def _api_error(e):
    log.warning("ApiError %s: %s %s", e.status, e.mensaje, e.detalle or "")
    return respuesta_error(e.status, e.mensaje, e.detalle)


@app.errorhandler(DuplicateKeyError)
def _duplicado(e):
    log.warning("Clave duplicada")
    return respuesta_error(409, "Ya existe un documento con esa clave")


@app.errorhandler(ServerSelectionTimeoutError)
@app.errorhandler(ConnectionFailure)
def _sin_conexion(e):
    log.error("Sin conexión con MongoDB Atlas: %s", type(e).__name__)
    return respuesta_error(503, "No se pudo conectar con la base de datos")


@app.errorhandler(PyMongoError)
def _mongo(e):
    log.error("Error de MongoDB: %s", type(e).__name__)
    return respuesta_error(500, "Error al operar con la base de datos")


MENSAJES_HTTP = {404: "La ruta solicitada no existe", 405: "Método no permitido para esta ruta",
                 413: "El cuerpo de la solicitud es demasiado grande", 415: "Tipo de contenido no soportado"}


@app.errorhandler(HTTPException)
def _http(e):
    return respuesta_error(e.code, MENSAJES_HTTP.get(e.code, e.description))


@app.errorhandler(Exception)
def _inesperado(e):
    log.exception("Error inesperado")
    return respuesta_error(500, "Error interno del servidor")


@app.before_request
def _inicio():
    g.t0 = time.perf_counter()


@app.after_request
def _fin(resp):
    ms = (time.perf_counter() - g.get("t0", time.perf_counter())) * 1000
    log.info("%s %s -> %s (%.0f ms)", request.method, request.full_path.rstrip("?"), resp.status_code, ms)
    return resp


# ---------------------------------------------------------------- utilidades
def limpiar(x):
    """Convierte fechas a texto ISO para poder devolver JSON."""
    if isinstance(x, datetime):
        return x.isoformat()
    if isinstance(x, dict):
        return {k: limpiar(v) for k, v in x.items()}
    if isinstance(x, list):
        return [limpiar(v) for v in x]
    return x


def cuerpo_json():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        raise ApiError(400, "El cuerpo debe ser un objeto JSON")
    return datos


def texto(datos, campo, maximo=500, obligatorio=True):
    v = datos.get(campo)
    if v is None:
        if obligatorio:
            raise ApiError(400, f"Falta el campo obligatorio '{campo}'")
        return None
    if not isinstance(v, str) or not v.strip():
        raise ApiError(400, f"El campo '{campo}' debe ser un texto no vacío")
    if len(v) > maximo:
        raise ApiError(400, f"El campo '{campo}' supera {maximo} caracteres")
    return v.strip()


def opcion(valor, permitidos, campo):
    if valor not in permitidos:
        raise ApiError(400, f"Valor inválido para '{campo}'", {"permitidos": sorted(permitidos)})
    return valor


def hashtags_validos(datos):
    h = datos.get("hashtags", [])
    if not isinstance(h, list) or not all(isinstance(x, str) and x.startswith("#") and len(x) > 1 for x in h):
        raise ApiError(400, "'hashtags' debe ser una lista de textos que comienzan con #")
    return h


def existe(col, _id, nombre):
    if not get_db()[col].find_one({"_id": _id}, {"_id": 1}):
        raise ApiError(422, f"Referencia inválida: {nombre} '{_id}' no existe")


def limite():
    try:
        n = int(request.args.get("limit", 20))
    except ValueError:
        raise ApiError(400, "'limit' debe ser un entero")
    if not 1 <= n <= 100:
        raise ApiError(400, "'limit' debe estar entre 1 y 100")
    return n


def nuevo_id(prefijo):
    return f"{prefijo}_api_{uuid.uuid4().hex[:8]}"


def ahora():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- raíz y salud
@app.get("/")
def raiz():
    return jsonify({"servicio": "ContentFlow API", "endpoints": sorted(
        f"{','.join(sorted(r.methods - {'HEAD', 'OPTIONS'}))} {r.rule}" for r in app.url_map.iter_rules()
        if r.endpoint != "static")})


@app.get("/health")
def health():
    """Prueba de conectividad con Atlas."""
    t = time.perf_counter()
    db = get_db()
    db.command("ping")
    return jsonify({"estado": "ok", "base_de_datos": db.name,
                    "latencia_ms": round((time.perf_counter() - t) * 1000, 1)})


# ---------------------------------------------------------------- publicaciones
@app.get("/publicaciones")
def listar_publicaciones():
    filtro = {}
    for campo in ("categoria", "tipo", "usuario_id"):
        if request.args.get(campo):
            filtro[campo] = request.args[campo]
    docs = get_db().publicaciones.find(filtro).sort("fecha_publicacion", -1).limit(limite())
    lista = [limpiar(d) for d in docs]
    return jsonify({"total": len(lista), "publicaciones": lista})


@app.get("/publicaciones/<pub_id>")
def obtener_publicacion(pub_id):
    db = get_db()
    d = db.publicaciones.find_one({"_id": pub_id})
    if not d:
        raise ApiError(404, f"La publicación '{pub_id}' no existe")
    d["reacciones"] = db.reacciones.count_documents({"publicacion_id": pub_id})
    d["comentarios"] = db.comentarios.count_documents({"publicacion_id": pub_id})
    return jsonify(limpiar(d))


@app.post("/publicaciones")
def crear_publicacion():
    b = cuerpo_json()
    usuario_id = texto(b, "usuario_id", 64)
    doc = {
        "_id": nuevo_id("pub"),
        "usuario_id": usuario_id,
        "contenido": texto(b, "contenido", 500),
        "fecha_publicacion": ahora(),
        "categoria": opcion(texto(b, "categoria", 40), CATEGORIAS, "categoria"),
        "hashtags": hashtags_validos(b),
        "tipo": opcion(texto(b, "tipo", 20), TIPOS, "tipo"),
    }
    existe("usuarios", usuario_id, "el usuario")
    get_db().publicaciones.insert_one(doc)
    log.info("Publicación creada: %s por %s", doc["_id"], usuario_id)
    resp = jsonify(limpiar(doc))
    resp.status_code = 201
    resp.headers["Location"] = f"/publicaciones/{doc['_id']}"
    return resp


@app.patch("/publicaciones/<pub_id>")
def actualizar_publicacion(pub_id):
    b = cuerpo_json()
    cambios = {}
    if "contenido" in b:
        cambios["contenido"] = texto(b, "contenido", 500)
    if "categoria" in b:
        cambios["categoria"] = opcion(texto(b, "categoria", 40), CATEGORIAS, "categoria")
    if "tipo" in b:
        cambios["tipo"] = opcion(texto(b, "tipo", 20), TIPOS, "tipo")
    if "hashtags" in b:
        cambios["hashtags"] = hashtags_validos(b)
    if not cambios:
        raise ApiError(400, "No se indicó ningún campo modificable",
                       {"modificables": ["contenido", "categoria", "tipo", "hashtags"]})
    r = get_db().publicaciones.find_one_and_update({"_id": pub_id}, {"$set": cambios}, return_document=ReturnDocument.AFTER)
    if not r:
        raise ApiError(404, f"La publicación '{pub_id}' no existe")
    return jsonify(limpiar(r))


@app.delete("/publicaciones/<pub_id>")
def eliminar_publicacion(pub_id):
    """Elimina también sus reacciones y comentarios y la quita de las campañas (sin referencias huérfanas)."""
    db = get_db()
    if db.publicaciones.delete_one({"_id": pub_id}).deleted_count == 0:
        raise ApiError(404, f"La publicación '{pub_id}' no existe")
    r = db.reacciones.delete_many({"publicacion_id": pub_id}).deleted_count
    c = db.comentarios.delete_many({"publicacion_id": pub_id}).deleted_count
    db.campanas.update_many({"publicaciones_asociadas": pub_id}, {"$pull": {"publicaciones_asociadas": pub_id}})
    log.info("Publicación eliminada: %s (reacciones=%d, comentarios=%d)", pub_id, r, c)
    return jsonify({"eliminada": pub_id, "reacciones_eliminadas": r, "comentarios_eliminados": c})


# ---------------------------------------------------------------- reacciones
@app.get("/reacciones")
def listar_reacciones():
    filtro = {k: request.args[k] for k in ("publicacion_id", "usuario_id") if request.args.get(k)}
    docs = get_db().reacciones.find(filtro).sort("fecha", -1).limit(limite())
    lista = [limpiar(d) for d in docs]
    return jsonify({"total": len(lista), "reacciones": lista})


@app.post("/reacciones")
def crear_reaccion():
    b = cuerpo_json()
    usuario_id, pub_id = texto(b, "usuario_id", 64), texto(b, "publicacion_id", 64)
    tipo = opcion(texto(b, "tipo_reaccion", 30), REACCIONES, "tipo_reaccion")
    existe("usuarios", usuario_id, "el usuario")
    existe("publicaciones", pub_id, "la publicación")
    if get_db().reacciones.find_one({"usuario_id": usuario_id, "publicacion_id": pub_id}, {"_id": 1}):
        raise ApiError(409, "El usuario ya reaccionó a esta publicación")
    doc = {"_id": nuevo_id("react"), "usuario_id": usuario_id, "publicacion_id": pub_id,
           "tipo_reaccion": tipo, "fecha": ahora()}
    get_db().reacciones.insert_one(doc)
    log.info("Reacción creada: %s", doc["_id"])
    resp = jsonify(limpiar(doc))
    resp.status_code = 201
    return resp


@app.delete("/reacciones/<react_id>")
def eliminar_reaccion(react_id):
    if get_db().reacciones.delete_one({"_id": react_id}).deleted_count == 0:
        raise ApiError(404, f"La reacción '{react_id}' no existe")
    return jsonify({"eliminada": react_id})


# ---------------------------------------------------------------- comentarios
@app.get("/comentarios")
def listar_comentarios():
    filtro = {k: request.args[k] for k in ("publicacion_id", "usuario_id") if request.args.get(k)}
    docs = get_db().comentarios.find(filtro).sort("fecha", -1).limit(limite())
    lista = [limpiar(d) for d in docs]
    return jsonify({"total": len(lista), "comentarios": lista})


@app.post("/comentarios")
def crear_comentario():
    b = cuerpo_json()
    usuario_id, pub_id = texto(b, "usuario_id", 64), texto(b, "publicacion_id", 64)
    doc = {"_id": nuevo_id("comm"), "usuario_id": usuario_id, "publicacion_id": pub_id,
           "comentario": texto(b, "comentario", 500), "fecha": ahora(), "likes": 0}
    existe("usuarios", usuario_id, "el usuario")
    existe("publicaciones", pub_id, "la publicación")
    get_db().comentarios.insert_one(doc)
    log.info("Comentario creado: %s", doc["_id"])
    resp = jsonify(limpiar(doc))
    resp.status_code = 201
    return resp


@app.post("/comentarios/<comm_id>/like")
def like_comentario(comm_id):
    r = get_db().comentarios.find_one_and_update({"_id": comm_id}, {"$inc": {"likes": 1}}, return_document=ReturnDocument.AFTER)
    if not r:
        raise ApiError(404, f"El comentario '{comm_id}' no existe")
    return jsonify(limpiar(r))


@app.delete("/comentarios/<comm_id>")
def eliminar_comentario(comm_id):
    if get_db().comentarios.delete_one({"_id": comm_id}).deleted_count == 0:
        raise ApiError(404, f"El comentario '{comm_id}' no existe")
    return jsonify({"eliminado": comm_id})


# ---------------------------------------------------------------- campañas y estadísticas
@app.get("/campanas")
def listar_campanas():
    docs = get_db().campanas.find({}, {"nombre": 1, "objetivo": 1, "fecha_inicio": 1, "fecha_fin": 1,
                                         "metricas_objetivo": 1}).sort("fecha_inicio", -1).limit(limite())
    lista = [limpiar(d) for d in docs]
    return jsonify({"total": len(lista), "campanas": lista})


@app.get("/estadisticas/publicaciones-populares")
def publicaciones_populares():
    """Mismo criterio que la consulta A2: popularidad = reacciones + comentarios."""
    pipeline = [
        {"$lookup": {"from": "reacciones", "localField": "_id", "foreignField": "publicacion_id", "as": "r"}},
        {"$lookup": {"from": "comentarios", "localField": "_id", "foreignField": "publicacion_id", "as": "c"}},
        {"$project": {"categoria": 1, "tipo": 1, "usuario_id": 1,
                      "reacciones": {"$size": "$r"}, "comentarios": {"$size": "$c"}}},
        {"$addFields": {"popularidad": {"$add": ["$reacciones", "$comentarios"]}}},
        {"$sort": {"popularidad": -1, "_id": 1}},
        {"$limit": limite()},
    ]
    return jsonify({"publicaciones": limpiar(list(get_db().publicaciones.aggregate(pipeline)))})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)

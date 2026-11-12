"""Script CRUD de un caso de negocio de ContentFlow (apartado 5, IE7 e IE8).

Caso: "Lanzamiento de una publicación dentro de una campaña".
Un usuario nuevo se registra, publica, la publicación se asocia a la campaña camp_1, otros usuarios
reaccionan y comentan, se actualizan métricas y, al final, se eliminan los datos de prueba.
Todos los documentos creados tienen _id con prefijo "demo_", así que el script es repetible y
deja la base como estaba (se verifica comparando los conteos inicial y final).

Cada paso guarda el estado ANTES y DESPUÉS como evidencia.
"""
from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from common import get_db, get_logger, guardar_evidencia

log = get_logger("09_crud")
EVIDENCIA = []

U_ID, P_ID, C_ID, CAMP = "demo_user_1", "demo_pub_1", "demo_comm_1", "camp_1"
R_IDS = ["demo_react_1", "demo_react_2"]
COLECCIONES = ["usuarios", "publicaciones", "reacciones", "comentarios", "campanas"]


def ahora():
    return datetime.now(timezone.utc)


def registrar(paso, operacion, antes, despues, nota=""):
    EVIDENCIA.append({"paso": paso, "operacion": operacion, "antes": antes, "despues": despues, "nota": nota})
    log.info("[%s] %s", paso, operacion)
    log.info("    ANTES   : %s", antes)
    log.info("    DESPUÉS : %s", despues)
    if nota:
        log.info("    NOTA    : %s", nota)


# ---------------- validaciones (criterio de calidad de datos, IE8) ----------------
class ErrorValidacion(Exception):
    pass


def validar_reaccion(db, usuario_id, publicacion_id):
    """Rechaza referencias inválidas y reacciones duplicadas (mismo usuario + misma publicación)."""
    if not db.usuarios.find_one({"_id": usuario_id}, {"_id": 1}):
        raise ErrorValidacion(f"referencia inválida: el usuario {usuario_id} no existe")
    if not db.publicaciones.find_one({"_id": publicacion_id}, {"_id": 1}):
        raise ErrorValidacion(f"referencia inválida: la publicación {publicacion_id} no existe")
    if db.reacciones.find_one({"usuario_id": usuario_id, "publicacion_id": publicacion_id}, {"_id": 1}):
        raise ErrorValidacion(f"duplicado: {usuario_id} ya reaccionó a {publicacion_id}")


def intentar(db, paso, descripcion, fn):
    """Ejecuta una operación que DEBE ser rechazada y deja la evidencia."""
    try:
        fn()
        registrar(paso, descripcion, "-", "ERROR: la operación no fue rechazada", "revisar validación")
    except (ErrorValidacion, DuplicateKeyError) as e:
        registrar(paso, descripcion, "sin cambios", f"RECHAZADA -> {e}", "criterio: no se inserta dato inválido")


def conteos(db):
    return {c: db[c].count_documents({}) for c in COLECCIONES}


def limpiar(db):
    for c in ["usuarios", "publicaciones", "reacciones", "comentarios"]:
        db[c].delete_many({"_id": {"$regex": "^demo_"}})
    db.campanas.update_many({}, {"$pull": {"publicaciones_asociadas": P_ID}})


def main():
    _, db = get_db()
    limpiar(db)  # residuos de ejecuciones anteriores
    inicial = conteos(db)
    log.info("Conteos iniciales: %s", inicial)

    # ================= CREATE =================
    antes = db.usuarios.count_documents({"_id": U_ID})
    db.usuarios.insert_one({
        "_id": U_ID, "nombre": "Usuario Demo", "correo": "demo@contentflow.test", "pais": "Chile",
        "genero": "Otro", "fecha_registro": ahora(), "dispositivo": "Móvil"})
    registrar("C1", "insert_one en usuarios: registro de un usuario nuevo",
              {"existe": antes}, db.usuarios.find_one({"_id": U_ID}, {"nombre": 1, "pais": 1, "dispositivo": 1}))

    antes = db.publicaciones.count_documents({"usuario_id": U_ID})
    db.publicaciones.insert_one({
        "_id": P_ID, "usuario_id": U_ID, "contenido": "Lanzamiento de la campaña de otoño",
        "fecha_publicacion": ahora(), "categoria": "Tecnología", "hashtags": ["#innovacion"], "tipo": "Texto"})
    registrar("C2", "insert_one en publicaciones: el usuario publica",
              {"publicaciones_del_usuario": antes},
              db.publicaciones.find_one({"_id": P_ID}, {"contenido": 1, "hashtags": 1, "tipo": 1}))

    antes = db.campanas.find_one({"_id": CAMP}, {"publicaciones_asociadas": 1})["publicaciones_asociadas"]
    db.campanas.update_one({"_id": CAMP}, {"$push": {"publicaciones_asociadas": P_ID}})
    despues = db.campanas.find_one({"_id": CAMP}, {"publicaciones_asociadas": 1})["publicaciones_asociadas"]
    registrar("U1", "update_one con $push en campanas: la publicación se asocia a camp_1",
              {"asociadas": len(antes)}, {"asociadas": len(despues), "ultima": despues[-1]})

    reacciones = [
        {"_id": R_IDS[0], "usuario_id": "user_1", "publicacion_id": P_ID, "tipo_reaccion": "Me gusta", "fecha": ahora()},
        {"_id": R_IDS[1], "usuario_id": "user_2", "publicacion_id": P_ID, "tipo_reaccion": "Me encanta", "fecha": ahora()},
    ]
    for r in reacciones:
        validar_reaccion(db, r["usuario_id"], r["publicacion_id"])
    antes = db.reacciones.count_documents({"publicacion_id": P_ID})
    db.reacciones.insert_many(reacciones)
    registrar("C3", "insert_many en reacciones (validadas contra usuarios y publicaciones)",
              {"reacciones_de_la_pub": antes}, {"reacciones_de_la_pub": db.reacciones.count_documents({"publicacion_id": P_ID})})

    db.comentarios.insert_one({
        "_id": C_ID, "usuario_id": "user_3", "publicacion_id": P_ID,
        "comentario": "Muy buena iniciativa", "fecha": ahora(), "likes": 0})
    registrar("C4", "insert_one en comentarios", {"comentarios_de_la_pub": 0},
              db.comentarios.find_one({"_id": C_ID}, {"comentario": 1, "likes": 1}))

    # ================= READ =================
    resumen = list(db.reacciones.aggregate([
        {"$match": {"publicacion_id": P_ID}},
        {"$group": {"_id": "$tipo_reaccion", "total": {"$sum": 1}}}, {"$sort": {"_id": 1}}]))
    registrar("R1", "aggregate: reacciones de la publicación agrupadas por tipo", "-", resumen)

    detalle = db.publicaciones.aggregate([
        {"$match": {"_id": P_ID}},
        {"$lookup": {"from": "usuarios", "localField": "usuario_id", "foreignField": "_id", "as": "autor"}},
        {"$unwind": "$autor"},
        {"$project": {"contenido": 1, "autor": "$autor.nombre", "pais_autor": "$autor.pais"}}])
    registrar("R2", "aggregate con $lookup y $unwind: publicación con los datos de su autor", "-", list(detalle))

    # ================= UPDATE =================
    antes = db.comentarios.find_one({"_id": C_ID}, {"likes": 1, "comentario": 1, "_id": 0})
    db.comentarios.update_one({"_id": C_ID}, {"$inc": {"likes": 5}, "$set": {"comentario": "Muy buena iniciativa (editado)"}})
    registrar("U2", "update_one con $inc y $set en comentarios",
              antes, db.comentarios.find_one({"_id": C_ID}, {"likes": 1, "comentario": 1, "_id": 0}))

    antes = db.publicaciones.find_one({"_id": P_ID}, {"hashtags": 1, "tipo": 1, "_id": 0})
    db.publicaciones.update_one({"_id": P_ID}, {"$push": {"hashtags": "#otono"}, "$set": {"tipo": "Video"}})
    registrar("U3", "update_one con $push y $set en publicaciones",
              antes, db.publicaciones.find_one({"_id": P_ID}, {"hashtags": 1, "tipo": 1, "_id": 0}))

    r = db.reacciones.update_many({"publicacion_id": P_ID}, {"$set": {"revisada": True}})
    registrar("U4", "update_many en reacciones: marcar como revisadas",
              {"sin_marca": r.matched_count}, {"modificadas": r.modified_count})

    # ================= VALIDACIONES (errores comunes de datos) =================
    intentar(db, "V1", "Reacción a una publicación inexistente (referencia inválida)",
             lambda: validar_reaccion(db, "user_1", "pub_999999"))
    intentar(db, "V2", "Reacción duplicada: mismo usuario y misma publicación",
             lambda: validar_reaccion(db, "user_1", P_ID))
    intentar(db, "V3", "Reacción de un usuario inexistente (referencia inválida)",
             lambda: validar_reaccion(db, "user_999999", P_ID))

    # ================= DELETE =================
    antes = db.comentarios.count_documents({"publicacion_id": P_ID})
    db.comentarios.delete_one({"_id": C_ID})
    registrar("D1", "delete_one en comentarios", {"comentarios_de_la_pub": antes},
              {"comentarios_de_la_pub": db.comentarios.count_documents({"publicacion_id": P_ID})})

    antes = db.reacciones.count_documents({"publicacion_id": P_ID})
    d = db.reacciones.delete_many({"publicacion_id": P_ID})
    registrar("D2", "delete_many en reacciones de la publicación (evita referencias huérfanas)",
              {"reacciones_de_la_pub": antes}, {"eliminadas": d.deleted_count})

    db.campanas.update_one({"_id": CAMP}, {"$pull": {"publicaciones_asociadas": P_ID}})
    db.publicaciones.delete_one({"_id": P_ID})
    db.usuarios.delete_one({"_id": U_ID})
    registrar("D3", "$pull en campanas y delete_one de la publicación y del usuario de prueba",
              {"existen": ["publicación", "usuario"]},
              {"publicacion": db.publicaciones.count_documents({"_id": P_ID}),
               "usuario": db.usuarios.count_documents({"_id": U_ID}),
               "en_campana": db.campanas.count_documents({"_id": CAMP, "publicaciones_asociadas": P_ID})})

    final = conteos(db)
    igual = final == inicial
    log.info("Conteos finales:   %s", final)
    log.info("¿La base quedó igual que al inicio? %s", "SÍ" if igual else "NO (revisar)")
    EVIDENCIA.append({"paso": "FIN", "conteos_iniciales": inicial, "conteos_finales": final, "base_intacta": igual})
    log.info("Evidencia: %s", guardar_evidencia("09_crud", EVIDENCIA))


if __name__ == "__main__":
    main()

"""Definición de las validaciones de calidad de datos (pipelines de agregación).

Cada chequeo = (colección origen, descripción, pipeline). Requiere fechas ya como Date.
"""


def _lookup(desde, local, nombre):
    return {"$lookup": {"from": desde, "localField": local, "foreignField": "_id", "as": nombre}}


CHECKS = {
    # ---------- duplicados ----------
    "reacciones_duplicadas": (
        "reacciones",
        "Misma reacción repetida: mismo usuario + misma publicación",
        [
            {"$group": {"_id": {"usuario_id": "$usuario_id", "publicacion_id": "$publicacion_id"},
                        "n": {"$sum": 1}, "ids": {"$push": "$_id"}}},
            {"$match": {"n": {"$gt": 1}}},
        ],
    ),
    "campanas_nombre_repetido": (
        "campanas",
        "Nombres de campaña repetidos (distinto _id)",
        [
            {"$group": {"_id": "$nombre", "n": {"$sum": 1}, "ids": {"$push": "$_id"}}},
            {"$match": {"n": {"$gt": 1}}},
        ],
    ),
    # ---------- referencias inválidas ----------
    "publicaciones_autor_inexistente": (
        "publicaciones", "publicaciones.usuario_id no existe en usuarios",
        [_lookup("usuarios", "usuario_id", "r"), {"$match": {"r": {"$size": 0}}},
         {"$project": {"usuario_id": 1}}],
    ),
    "reacciones_usuario_inexistente": (
        "reacciones", "reacciones.usuario_id no existe en usuarios",
        [_lookup("usuarios", "usuario_id", "r"), {"$match": {"r": {"$size": 0}}},
         {"$project": {"usuario_id": 1}}],
    ),
    "reacciones_publicacion_inexistente": (
        "reacciones", "reacciones.publicacion_id no existe en publicaciones",
        [_lookup("publicaciones", "publicacion_id", "r"), {"$match": {"r": {"$size": 0}}},
         {"$project": {"publicacion_id": 1}}],
    ),
    "comentarios_usuario_inexistente": (
        "comentarios", "comentarios.usuario_id no existe en usuarios",
        [_lookup("usuarios", "usuario_id", "r"), {"$match": {"r": {"$size": 0}}},
         {"$project": {"usuario_id": 1}}],
    ),
    "comentarios_publicacion_inexistente": (
        "comentarios", "comentarios.publicacion_id no existe en publicaciones",
        [_lookup("publicaciones", "publicacion_id", "r"), {"$match": {"r": {"$size": 0}}},
         {"$project": {"publicacion_id": 1}}],
    ),
    "campanas_publicacion_inexistente": (
        "campanas", "campanas.publicaciones_asociadas contiene ids que no existen",
        [{"$unwind": "$publicaciones_asociadas"}, _lookup("publicaciones", "publicaciones_asociadas", "r"),
         {"$match": {"r": {"$size": 0}}}, {"$project": {"publicaciones_asociadas": 1}}],
    ),
    # ---------- coherencia temporal ----------
    "reacciones_antes_de_publicacion": (
        "reacciones", "Reacción con fecha anterior a la publicación reaccionada",
        [_lookup("publicaciones", "publicacion_id", "p"), {"$unwind": "$p"},
         {"$match": {"$expr": {"$lt": ["$fecha", "$p.fecha_publicacion"]}}},
         {"$project": {"fecha": 1, "publicacion_id": 1, "fecha_publicacion": "$p.fecha_publicacion"}}],
    ),
    "comentarios_antes_de_publicacion": (
        "comentarios", "Comentario con fecha anterior a la publicación comentada",
        [_lookup("publicaciones", "publicacion_id", "p"), {"$unwind": "$p"},
         {"$match": {"$expr": {"$lt": ["$fecha", "$p.fecha_publicacion"]}}},
         {"$project": {"fecha": 1, "publicacion_id": 1, "fecha_publicacion": "$p.fecha_publicacion"}}],
    ),
    "publicaciones_antes_de_registro": (
        "publicaciones", "Publicación con fecha anterior al registro de su autor",
        [_lookup("usuarios", "usuario_id", "u"), {"$unwind": "$u"},
         {"$match": {"$expr": {"$lt": ["$fecha_publicacion", "$u.fecha_registro"]}}},
         {"$project": {"fecha_publicacion": 1, "usuario_id": 1, "fecha_registro": "$u.fecha_registro"}}],
    ),
    "reacciones_antes_de_registro": (
        "reacciones", "Reacción con fecha anterior al registro del usuario",
        [_lookup("usuarios", "usuario_id", "u"), {"$unwind": "$u"},
         {"$match": {"$expr": {"$lt": ["$fecha", "$u.fecha_registro"]}}},
         {"$project": {"fecha": 1, "usuario_id": 1, "fecha_registro": "$u.fecha_registro"}}],
    ),
    "campanas_fin_antes_de_inicio": (
        "campanas", "Campaña con fecha_fin anterior a fecha_inicio",
        [{"$match": {"$expr": {"$lt": ["$fecha_fin", "$fecha_inicio"]}}},
         {"$project": {"fecha_inicio": 1, "fecha_fin": 1}}],
    ),
    # ---------- calidad / contexto (se justifican, no se corrigen) ----------
    "autoreacciones": (
        "reacciones", "El autor reacciona a su propia publicación",
        [_lookup("publicaciones", "publicacion_id", "p"), {"$unwind": "$p"},
         {"$match": {"$expr": {"$eq": ["$usuario_id", "$p.usuario_id"]}}},
         {"$project": {"usuario_id": 1, "publicacion_id": 1}}],
    ),
    "autocomentarios": (
        "comentarios", "El autor comenta su propia publicación",
        [_lookup("publicaciones", "publicacion_id", "p"), {"$unwind": "$p"},
         {"$match": {"$expr": {"$eq": ["$usuario_id", "$p.usuario_id"]}}},
         {"$project": {"usuario_id": 1, "publicacion_id": 1}}],
    ),
    "publicaciones_sin_campana": (
        "publicaciones", "Publicaciones que no pertenecen a ninguna campaña",
        [{"$lookup": {"from": "campanas", "localField": "_id",
                      "foreignField": "publicaciones_asociadas", "as": "c"}},
         {"$match": {"c": {"$size": 0}}}, {"$project": {"usuario_id": 1}}],
    ),
    "usuarios_sin_actividad": (
        "usuarios", "Usuarios sin publicaciones, reacciones ni comentarios",
        [{"$lookup": {"from": "publicaciones", "localField": "_id", "foreignField": "usuario_id", "as": "a"}},
         {"$lookup": {"from": "reacciones", "localField": "_id", "foreignField": "usuario_id", "as": "b"}},
         {"$lookup": {"from": "comentarios", "localField": "_id", "foreignField": "usuario_id", "as": "c"}},
         {"$match": {"a": {"$size": 0}, "b": {"$size": 0}, "c": {"$size": 0}}},
         {"$project": {"nombre": 1}}],
    ),
}

# Chequeos que producen una marca "inconsistencia_temporal" en 06_corregir_datos.py
TEMPORALES = [
    "reacciones_antes_de_publicacion",
    "comentarios_antes_de_publicacion",
    "publicaciones_antes_de_registro",
    "reacciones_antes_de_registro",
]

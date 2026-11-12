"""Consultas de negocio sobre ContentFlow (apartado 4 del encargo, IE4 e IE5).

Cada consulta indica el requerimiento de negocio al que responde. Solo lectura.
Requiere haber ejecutado 03_convertir_fechas.py (fechas tipo Date).

Uso:
    python scripts/07_consultas.py                 # todas
    python scripts/07_consultas.py --solo F1,A3   # solo algunas
"""
import argparse
import json
from datetime import datetime

from common import get_db, get_logger, guardar_evidencia

log = get_logger("07_consultas")


def _lk(desde, local, foreign, como):
    return {"$lookup": {"from": desde, "localField": local, "foreignField": foreign, "as": como}}


# (id, tipo, colección, requerimiento de negocio, argumentos)
CONSULTAS = [
    # ---------------- LECTURA: filtros, proyecciones, ordenamientos ----------------
    ("F1", "find", "publicaciones",
     "Diseño de contenido: ¿cuáles son los videos de Deportes más recientes?",
     {"filtro": {"categoria": "Deportes", "tipo": "Video"},
      "proyeccion": {"contenido": 1, "hashtags": 1, "fecha_publicacion": 1},
      "orden": [("fecha_publicacion", -1)], "limite": 5}),
    ("F2", "find", "usuarios",
     "Perfil de audiencia: usuarios de móvil o tablet registrados desde 2025 (operadores $and, $in y $gte).",
     {"filtro": {"$and": [{"dispositivo": {"$in": ["Móvil", "Tablet"]}},
                          {"fecha_registro": {"$gte": datetime(2025, 1, 1)}}]},
      "proyeccion": {"nombre": 1, "pais": 1, "dispositivo": 1, "fecha_registro": 1, "_id": 0},
      "orden": [("fecha_registro", 1)], "limite": 5}),
    ("F3", "find", "comentarios",
     "Contenido popular: comentarios con 80 o más likes, ordenados de mayor a menor.",
     {"filtro": {"likes": {"$gte": 80}},
      "proyeccion": {"comentario": 1, "likes": 1, "publicacion_id": 1},
      "orden": [("likes", -1), ("_id", 1)], "limite": 5}),
    ("F4", "find", "publicaciones",
     "Búsqueda compuesta: publicaciones con #futbol o #series que no sean de tipo Texto "
     "y no estén marcadas como inconsistentes ($or, $ne).",
     {"filtro": {"$or": [{"hashtags": "#futbol"}, {"hashtags": "#series"}],
                 "tipo": {"$ne": "Texto"},
                 "inconsistencia_temporal": {"$ne": True}},
      "proyeccion": {"categoria": 1, "tipo": 1, "hashtags": 1},
      "orden": [("_id", 1)], "limite": 5}),
    ("F5", "find", "campanas",
     "Éxito de campañas: campañas vigentes el 1 de mayo de 2025 (comparación de fechas Date).",
     {"filtro": {"fecha_inicio": {"$lte": datetime(2025, 5, 1)}, "fecha_fin": {"$gte": datetime(2025, 5, 1)}},
      "proyeccion": {"nombre": 1, "objetivo": 1, "fecha_inicio": 1, "fecha_fin": 1},
      "orden": [("fecha_inicio", 1)], "limite": 5}),

    # ---------------- AGREGACIÓN ----------------
    ("A1", "aggregate", "usuarios",
     "Usuarios más activos: publicaciones + reacciones + comentarios por usuario ($lookup, $size, $sort).",
     {"pipeline": [
         _lk("publicaciones", "_id", "usuario_id", "pubs"),
         _lk("reacciones", "_id", "usuario_id", "reacs"),
         _lk("comentarios", "_id", "usuario_id", "coms"),
         {"$project": {"nombre": 1, "pais": 1, "publicaciones": {"$size": "$pubs"},
                       "reacciones": {"$size": "$reacs"}, "comentarios": {"$size": "$coms"}}},
         {"$addFields": {"actividad_total": {"$add": ["$publicaciones", "$reacciones", "$comentarios"]}}},
         {"$sort": {"actividad_total": -1, "_id": 1}},
         {"$limit": 10}]}),
    ("A2", "aggregate", "publicaciones",
     "Contenidos más populares: popularidad = reacciones + comentarios por publicación.",
     {"pipeline": [
         _lk("reacciones", "_id", "publicacion_id", "r"),
         _lk("comentarios", "_id", "publicacion_id", "c"),
         {"$project": {"categoria": 1, "tipo": 1, "usuario_id": 1,
                       "reacciones": {"$size": "$r"}, "comentarios": {"$size": "$c"}}},
         {"$addFields": {"popularidad": {"$add": ["$reacciones", "$comentarios"]}}},
         {"$sort": {"popularidad": -1, "_id": 1}},
         {"$limit": 10}]}),
    ("A3", "aggregate", "publicaciones",
     "Horarios de publicación: promedio de reacciones recibidas según la hora (UTC) de publicación ($hour, $group).",
     {"pipeline": [
         _lk("reacciones", "_id", "publicacion_id", "r"),
         {"$project": {"hora": {"$hour": "$fecha_publicacion"}, "n": {"$size": "$r"}}},
         {"$group": {"_id": "$hora", "publicaciones": {"$sum": 1},
                     "reacciones_promedio": {"$avg": "$n"}}},
         {"$project": {"publicaciones": 1, "reacciones_promedio": {"$round": ["$reacciones_promedio", 2]}}},
         {"$sort": {"reacciones_promedio": -1, "_id": 1}},
         {"$limit": 5}]}),
    ("A4", "aggregate", "publicaciones",
     "Horarios de publicación: promedio de reacciones por día de la semana (1 = domingo) ($dayOfWeek).",
     {"pipeline": [
         _lk("reacciones", "_id", "publicacion_id", "r"),
         {"$project": {"dia": {"$dayOfWeek": "$fecha_publicacion"}, "n": {"$size": "$r"}}},
         {"$group": {"_id": "$dia", "publicaciones": {"$sum": 1}, "reacciones_promedio": {"$avg": "$n"}}},
         {"$project": {"publicaciones": 1, "reacciones_promedio": {"$round": ["$reacciones_promedio", 2]}}},
         {"$sort": {"reacciones_promedio": -1}}]}),
    ("A5", "aggregate", "reacciones",
     "Perfil de audiencia: tipo de reacción predominante según dispositivo del usuario ($lookup, $unwind, $group).",
     {"pipeline": [
         _lk("usuarios", "usuario_id", "_id", "u"),
         {"$unwind": "$u"},
         {"$group": {"_id": {"dispositivo": "$u.dispositivo", "reaccion": "$tipo_reaccion"}, "total": {"$sum": 1}}},
         {"$sort": {"_id.dispositivo": 1, "total": -1}}]}),
    ("A6", "aggregate", "publicaciones",
     "Diseño de contenido: hashtags más usados ($unwind sobre arreglo, $group, $sort).",
     {"pipeline": [
         {"$unwind": "$hashtags"},
         {"$group": {"_id": "$hashtags", "usos": {"$sum": 1}}},
         {"$sort": {"usos": -1, "_id": 1}},
         {"$limit": 10}]}),
    ("A7", "aggregate", "campanas",
     "Éxito de campañas: reacciones y comentarios reales frente a la meta (metricas_objetivo) de cada campaña.",
     {"pipeline": [
         _lk("reacciones", "publicaciones_asociadas", "publicacion_id", "r"),
         _lk("comentarios", "publicaciones_asociadas", "publicacion_id", "c"),
         {"$project": {"nombre": 1, "objetivo": 1,
                       "meta_likes": "$metricas_objetivo.likes", "meta_comentarios": "$metricas_objetivo.comentarios",
                       "reacciones": {"$size": "$r"}, "comentarios": {"$size": "$c"}}},
         {"$addFields": {"cumplimiento_reacciones_pct": {"$round": [
             {"$multiply": [{"$divide": ["$reacciones", "$meta_likes"]}, 100]}, 1]}}},
         {"$sort": {"cumplimiento_reacciones_pct": -1, "_id": 1}},
         {"$limit": 5}]}),
    ("A8", "aggregate", "campanas",
     "Éxito de campañas por objetivo: cumplimiento promedio de la meta de reacciones.",
     {"pipeline": [
         _lk("reacciones", "publicaciones_asociadas", "publicacion_id", "r"),
         {"$project": {"objetivo": 1, "meta_likes": "$metricas_objetivo.likes", "reacciones": {"$size": "$r"}}},
         {"$group": {"_id": "$objetivo", "campanas": {"$sum": 1},
                     "reacciones_promedio": {"$avg": "$reacciones"}, "meta_promedio": {"$avg": "$meta_likes"}}},
         {"$project": {"campanas": 1, "reacciones_promedio": {"$round": ["$reacciones_promedio", 1]},
                       "meta_promedio": {"$round": ["$meta_promedio", 1]}}},
         {"$sort": {"reacciones_promedio": -1}}]}),
]


def ejecutar(db, tipo, col, args):
    if tipo == "find":
        cur = db[col].find(args["filtro"], args.get("proyeccion")).sort(args["orden"]).limit(args["limite"])
        return list(cur)
    return list(db[col].aggregate(args["pipeline"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo", help="ids separados por coma, ej. F1,A3")
    a = ap.parse_args()
    solo = set(a.solo.split(",")) if a.solo else None

    _, db = get_db()
    evidencia = {}
    for cid, tipo, col, requisito, args in CONSULTAS:
        if solo and cid not in solo:
            continue
        filas = ejecutar(db, tipo, col, args)
        log.info("=== %s [%s sobre %s] %s", cid, tipo, col, requisito)
        for f in filas[:5]:
            log.info("    %s", json.dumps(f, ensure_ascii=False, default=str))
        log.info("    -> %d resultado(s) mostrados/devueltos", len(filas))
        evidencia[cid] = {"tipo": tipo, "coleccion": col, "requisito": requisito,
                          "consulta": {k: str(v) for k, v in args.items()}, "resultados": filas[:10]}
    log.info("Evidencia: %s", guardar_evidencia("07_consultas", evidencia))


if __name__ == "__main__":
    main()

"""Crea los índices recomendados.

IMPORTANTE (indicador IE6): primero ejecuta tus consultas con
explain("executionStats") SIN índices, guarda la evidencia, y recién después
corre este script para repetir el explain.
"""
from pymongo import ASCENDING, DESCENDING

from common import get_db, get_logger, guardar_evidencia

log = get_logger("06_crear_indices")

INDICES = [
    ("usuarios", [("correo", ASCENDING)], {"unique": True, "name": "ux_correo"}, "Login/búsqueda por correo, evita duplicados"),
    ("usuarios", [("pais", ASCENDING)], {"name": "ix_pais"}, "Perfil de audiencia por país"),
    ("publicaciones", [("usuario_id", ASCENDING)], {"name": "ix_pub_usuario"}, "Publicaciones de un usuario / $lookup"),
    ("publicaciones", [("categoria", ASCENDING), ("fecha_publicacion", DESCENDING)], {"name": "ix_pub_categoria_fecha"}, "Contenido por categoría y recencia"),
    ("reacciones", [("publicacion_id", ASCENDING)], {"name": "ix_react_pub"}, "Popularidad por publicación / $lookup"),
    ("reacciones", [("usuario_id", ASCENDING), ("publicacion_id", ASCENDING)], {"unique": True, "name": "ux_react_usuario_pub"}, "Evita reacciones duplicadas (requiere haber corregido el duplicado)"),
    ("comentarios", [("publicacion_id", ASCENDING)], {"name": "ix_com_pub"}, "Comentarios de una publicación"),
    ("comentarios", [("usuario_id", ASCENDING)], {"name": "ix_com_usuario"}, "Usuarios más activos"),
    ("campanas", [("publicaciones_asociadas", ASCENDING)], {"name": "ix_camp_pubs"}, "Multikey: campañas de una publicación"),
]


def main():
    _, db = get_db()
    ev = []
    for col, claves, opts, motivo in INDICES:
        nombre = db[col].create_index(claves, **opts)
        ev.append({"coleccion": col, "indice": nombre, "claves": claves, "justificacion": motivo})
        log.info("%-14s %-24s %s", col, nombre, motivo)
    log.info("Evidencia: %s", guardar_evidencia("06_indices", ev))


if __name__ == "__main__":
    main()

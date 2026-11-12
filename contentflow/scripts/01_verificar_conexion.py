"""Prueba de conectividad con Atlas (herramienta 1: driver pymongo)."""
from common import get_db, get_logger, guardar_evidencia

log = get_logger("01_verificar_conexion")


def main():
    client, db = get_db()
    try:
        client.admin.command("ping")
    except Exception as e:
        log.error("No se pudo conectar: %s", type(e).__name__)
        log.error("Revisa: Network Access (tu IP), usuario/contraseña y MONGODB_URI")
        raise SystemExit(1)
    info = client.server_info()
    stats = db.command("dbstats")
    resultado = {
        "ping": "ok",
        "version_servidor": info.get("version"),
        "base_de_datos": db.name,
        "write_concern": client.write_concern.document,
        "read_concern": client.read_concern.document,
        "colecciones": db.list_collection_names(),
        "almacenamiento_MB": round(stats.get("storageSize", 0) / 1024 / 1024, 2),
        "limite_M0_MB": 512,
    }
    for k, v in resultado.items():
        log.info("%s: %s", k, v)
    log.info("Evidencia: %s", guardar_evidencia("01_conexion", resultado))


if __name__ == "__main__":
    main()

"""Importa los 5 JSON a Atlas (equivalente a mongoimport --jsonArray).

Los _id se mantienen como texto ("user_1"), tal como pide el enunciado.
Uso:
    python scripts/02_importar_datos.py            # falla si la colección ya tiene datos
    python scripts/02_importar_datos.py --reset    # borra y vuelve a cargar
"""
import argparse
import json

from common import COLECCIONES, ROOT, get_db, get_logger, guardar_evidencia

log = get_logger("02_importar_datos")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="vacía cada colección antes de importar")
    args = ap.parse_args()

    _, db = get_db()
    resumen = {}
    for nombre in COLECCIONES:
        ruta = ROOT / "data" / f"{nombre}.json"
        with open(ruta, encoding="utf-8") as f:
            docs = json.load(f)
        col = db[nombre]
        if args.reset:
            col.drop()
        elif col.count_documents({}) > 0:
            log.warning("%s ya tiene datos; omitida (usa --reset para recargar)", nombre)
            resumen[nombre] = {"archivo": len(docs), "coleccion": col.count_documents({}), "omitida": True}
            continue
        col.insert_many(docs)
        en_atlas = col.count_documents({})
        ok = en_atlas == len(docs)
        resumen[nombre] = {"archivo": len(docs), "coleccion": en_atlas, "coincide": ok}
        log.info("%-14s archivo=%d  atlas=%d  %s", nombre, len(docs), en_atlas, "OK" if ok else "DIFERENCIA")
    log.info("Evidencia: %s", guardar_evidencia("02_importacion", resumen))


if __name__ == "__main__":
    main()

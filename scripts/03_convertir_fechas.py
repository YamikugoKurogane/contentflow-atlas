"""Convierte los campos de fecha (string ISO) a tipo Date con $toDate.

Es idempotente: solo toca documentos cuyo campo aún es string.
Usa un update con pipeline de agregación (requiere MongoDB 4.2+).
"""
from common import CAMPOS_FECHA, get_db, get_logger, guardar_evidencia

log = get_logger("03_convertir_fechas")


def tipos(col, campo):
    r = col.aggregate([{"$group": {"_id": {"$type": f"${campo}"}, "n": {"$sum": 1}}}])
    return {x["_id"]: x["n"] for x in r}


def main():
    _, db = get_db()
    evidencia = {}
    for nombre, campos in CAMPOS_FECHA.items():
        col = db[nombre]
        for campo in campos:
            antes = tipos(col, campo)
            r = col.update_many(
                {campo: {"$type": "string"}},
                [{"$set": {campo: {"$toDate": f"${campo}"}}}],
            )
            despues = tipos(col, campo)
            evidencia[f"{nombre}.{campo}"] = {
                "tipos_antes": antes, "modificados": r.modified_count, "tipos_despues": despues,
            }
            log.info("%s.%s  antes=%s  modificados=%d  despues=%s",
                     nombre, campo, antes, r.modified_count, despues)
    log.info("Evidencia: %s", guardar_evidencia("03_conversion_fechas", evidencia))


if __name__ == "__main__":
    main()

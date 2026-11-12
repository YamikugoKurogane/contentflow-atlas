"""Detecta inconsistencias mediante consultas (solo lectura). Indicador IE8."""
from common import CAMPOS_FECHA, get_db, get_logger, guardar_evidencia
from validaciones import CHECKS

log = get_logger("04_validar_datos")


def main():
    _, db = get_db()

    # 0) las fechas deben ser Date antes de comparar
    for col, campos in CAMPOS_FECHA.items():
        for c in campos:
            n = db[col].count_documents({c: {"$type": "string"}})
            if n:
                log.error("%s.%s tiene %d fechas como texto. Ejecuta antes 03_convertir_fechas.py", col, c, n)
                raise SystemExit(1)

    reporte = {}
    log.info("%-38s %8s  %s", "CHEQUEO", "CASOS", "DESCRIPCIÓN")
    for nombre, (col, desc, pipeline) in CHECKS.items():
        res = list(db[col].aggregate(pipeline))
        reporte[nombre] = {"coleccion": col, "descripcion": desc, "casos": len(res), "ejemplos": res[:3]}
        log.info("%-38s %8d  %s", nombre, len(res), desc)
    log.info("Evidencia: %s", guardar_evidencia("04_validacion", reporte))


if __name__ == "__main__":
    main()

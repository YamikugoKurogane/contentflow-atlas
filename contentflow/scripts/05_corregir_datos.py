"""Corrige o justifica las inconsistencias. Por defecto SOLO MUESTRA (dry-run).

Criterios aplicados (documentarlos en el informe):
 1. Reacciones duplicadas -> se conserva la de menor _id; las demás se respaldan
    en la colección 'auditoria_correcciones' y luego se eliminan.
 2. Incoherencias temporales -> NO se eliminan (son cientos y el dato sigue siendo
    útil); se marcan con inconsistencia_temporal=true y un motivo.
 3. Nombres de campaña repetidos, autointeracciones, publicaciones sin campaña y
    usuarios sin actividad -> no se modifican; se justifican en el informe.

Uso:
    python scripts/05_corregir_datos.py             # simulación
    python scripts/05_corregir_datos.py --aplicar   # ejecuta cambios
"""
import argparse
from datetime import datetime, timezone

from common import get_db, get_logger, guardar_evidencia
from validaciones import CHECKS, TEMPORALES

log = get_logger("05_corregir_datos")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()
    modo = "APLICANDO" if args.aplicar else "SIMULACIÓN (dry-run)"
    log.info("Modo: %s", modo)

    _, db = get_db()
    ev = {"modo": modo}

    # ---- 1) duplicados de reacciones ----
    col, _, pipe = CHECKS["reacciones_duplicadas"]
    grupos = list(db[col].aggregate(pipe))
    a_borrar = []
    for g in grupos:
        a_borrar += sorted(g["ids"])[1:]  # conserva el primero
    ev["reacciones_duplicadas"] = {"grupos": len(grupos), "ids_a_eliminar": a_borrar}
    log.info("Reacciones duplicadas: %d grupo(s) -> eliminar %s", len(grupos), a_borrar)
    if args.aplicar and a_borrar:
        docs = list(db.reacciones.find({"_id": {"$in": a_borrar}}))
        db.auditoria_correcciones.insert_many([
            {"coleccion": "reacciones", "motivo": "duplicado usuario+publicacion",
             "documento": d, "fecha_correccion": datetime.now(timezone.utc)} for d in docs])
        r = db.reacciones.delete_many({"_id": {"$in": a_borrar}})
        log.info("Eliminadas: %d (respaldo en auditoria_correcciones)", r.deleted_count)
        ev["reacciones_duplicadas"]["eliminadas"] = r.deleted_count

    # ---- 2) marcar incoherencias temporales ----
    ev["temporales"] = {}
    for nombre in TEMPORALES:
        col, desc, pipe = CHECKS[nombre]
        ids = [d["_id"] for d in db[col].aggregate(pipe)]
        ev["temporales"][nombre] = len(ids)
        log.info("%s: %d documento(s) a marcar", nombre, len(ids))
        if args.aplicar and ids:
            r = db[col].update_many(
                {"_id": {"$in": ids}},
                {"$set": {"inconsistencia_temporal": True},
                 "$addToSet": {"motivos_inconsistencia": nombre}},
            )
            log.info("  marcados: %d", r.modified_count)

    if not args.aplicar:
        log.info("Nada se modificó. Repite con --aplicar para ejecutar.")
    log.info("Evidencia: %s", guardar_evidencia("05_correccion" if args.aplicar else "05_correccion_simulacion", ev))


if __name__ == "__main__":
    main()

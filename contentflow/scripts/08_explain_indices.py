"""Evaluación de eficiencia con explain("executionStats") ANTES y DESPUÉS de crear índices (IE6).

Para cada prueba el script:
  1. elimina el índice (si existe) y mide la consulta 5 veces (sin índice),
  2. crea el índice y vuelve a medir 5 veces (con índice),
  3. muestra una tabla comparativa y guarda la evidencia.
Se informa la mediana del tiempo, porque con pocos documentos el tiempo es muy pequeño y ruidoso.
Los índices quedan creados al final (mismos nombres que 06_crear_indices.py).
"""
import statistics

from pymongo import ASCENDING, DESCENDING
from pymongo.errors import OperationFailure

from common import get_db, get_logger, guardar_evidencia

log = get_logger("08_explain_indices")
REPETICIONES = 5

PRUEBAS = [
    {"id": "T1", "col": "reacciones",
     "negocio": "Popularidad: reacciones de una publicación",
     "filtro": {"publicacion_id": "pub_430"}, "orden": None,
     "indice": ("ix_react_pub", [("publicacion_id", ASCENDING)])},
    {"id": "T2", "col": "publicaciones",
     "negocio": "Diseño de contenido: publicaciones de Tecnología, más recientes primero",
     "filtro": {"categoria": "Tecnología"}, "orden": {"fecha_publicacion": -1},
     "indice": ("ix_pub_categoria_fecha", [("categoria", ASCENDING), ("fecha_publicacion", DESCENDING)])},
    {"id": "T3", "col": "comentarios",
     "negocio": "Usuarios activos: comentarios de un usuario",
     "filtro": {"usuario_id": "user_92"}, "orden": None,
     "indice": ("ix_com_usuario", [("usuario_id", ASCENDING)])},
]


def etapas(nodo, acc=None):
    """Recorre el plan ganador y junta los nombres de etapa (COLLSCAN, IXSCAN, SORT...)."""
    acc = set() if acc is None else acc
    if isinstance(nodo, dict):
        if isinstance(nodo.get("stage"), str):
            acc.add(nodo["stage"])
        for v in nodo.values():
            etapas(v, acc)
    elif isinstance(nodo, list):
        for v in nodo:
            etapas(v, acc)
    return acc


def explicar(db, prueba):
    cmd = {"find": prueba["col"], "filter": prueba["filtro"]}
    if prueba["orden"]:
        cmd["sort"] = prueba["orden"]
    ex = db.command({"explain": cmd, "verbosity": "executionStats"})
    es = ex["executionStats"]
    et = etapas(ex["queryPlanner"]["winningPlan"])
    return {
        "tiempo_ms": es["executionTimeMillis"],
        "docs_examinados": es["totalDocsExamined"],
        "claves_examinadas": es["totalKeysExamined"],
        "retornados": es["nReturned"],
        "acceso": "IXSCAN" if "IXSCAN" in et else ("COLLSCAN" if "COLLSCAN" in et else "/".join(sorted(et))),
        "sort_en_memoria": "SORT" in et,
    }


def medir(db, prueba):
    corridas = [explicar(db, prueba) for _ in range(REPETICIONES)]
    r = dict(corridas[-1])
    r["tiempos_ms"] = [c["tiempo_ms"] for c in corridas]
    r["tiempo_ms"] = statistics.median(r["tiempos_ms"])
    return r


def main():
    _, db = get_db()
    resultados = {}
    for pr in PRUEBAS:
        nombre, claves = pr["indice"]
        try:
            db[pr["col"]].drop_index(nombre)
            log.info("%s: índice %s eliminado para medir 'antes'", pr["id"], nombre)
        except OperationFailure:
            log.info("%s: el índice %s no existía (medición 'antes' limpia)", pr["id"], nombre)
        antes = medir(db, pr)
        db[pr["col"]].create_index(claves, name=nombre)
        despues = medir(db, pr)
        resultados[pr["id"]] = {"coleccion": pr["col"], "negocio": pr["negocio"], "filtro": str(pr["filtro"]),
                                "orden": str(pr["orden"]), "indice": f"{nombre} {claves}",
                                "antes": antes, "despues": despues}

    log.info("")
    log.info("%-4s %-14s %-9s %8s %8s %8s %8s %-9s", "id", "colección", "fase", "ms", "examin.", "claves", "retorn.", "acceso")
    for k, r in resultados.items():
        for fase in ("antes", "despues"):
            x = r[fase]
            log.info("%-4s %-14s %-9s %8s %8d %8d %8d %-9s%s", k, r["coleccion"], fase, x["tiempo_ms"],
                     x["docs_examinados"], x["claves_examinadas"], x["retornados"], x["acceso"],
                     "  (+SORT en memoria)" if x["sort_en_memoria"] else "")
    log.info("Evidencia: %s", guardar_evidencia("08_explain_indices", resultados))


if __name__ == "__main__":
    main()

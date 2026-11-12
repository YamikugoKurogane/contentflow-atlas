"""Utilidades compartidas: conexión, logging y guardado de evidencias."""
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

COLECCIONES = ["usuarios", "publicaciones", "reacciones", "comentarios", "campanas"]

# Campos de fecha que vienen como texto ISO y deben pasar a tipo Date
CAMPOS_FECHA = {
    "usuarios": ["fecha_registro"],
    "publicaciones": ["fecha_publicacion"],
    "reacciones": ["fecha"],
    "comentarios": ["fecha"],
    "campanas": ["fecha_inicio", "fecha_fin"],
}


def get_logger(nombre: str) -> logging.Logger:
    (ROOT / "logs").mkdir(exist_ok=True)
    log = logging.getLogger(nombre)
    if not log.handlers:
        log.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        fh = logging.FileHandler(ROOT / "logs" / f"{nombre}.log", encoding="utf-8")
        sh = logging.StreamHandler(sys.stdout)
        for h in (fh, sh):
            h.setFormatter(fmt)
            log.addHandler(h)
    return log


def get_db():
    """Devuelve (client, db). Usa write concern y read concern 'majority'."""
    uri = os.getenv("MONGODB_URI")
    if not uri or "<password>" in uri:
        sys.exit("ERROR: define MONGODB_URI en el archivo .env (ver .env.example)")
    client = MongoClient(
        uri,
        serverSelectionTimeoutMS=8000,
        w="majority",
        readConcernLevel="majority",
        retryWrites=True,
    )
    return client, client[os.getenv("DB_NAME", "contentflow")]


def guardar_evidencia(nombre: str, datos) -> Path:
    carpeta = ROOT / "docs" / "evidencias"
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{nombre}.json"
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(
            {"generado": datetime.now().isoformat(timespec="seconds"), "datos": datos},
            f, ensure_ascii=False, indent=2, default=str,
        )
    return ruta

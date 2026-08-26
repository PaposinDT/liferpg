import os

import psycopg
from fastapi import FastAPI, HTTPException

from app.dashboard_api import router as dashboard_router
from app.settings import APP_VERSION, CHARACTER_NAME

app = FastAPI(
    title="Life RPG API",
    version=APP_VERSION,
)

app.include_router(dashboard_router)


@app.get("/")
def root():
    return {
        "name": "Life RPG",
        "character": CHARACTER_NAME,
        "version": APP_VERSION,
    }


@app.get("/health/live")
def health_live():
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready():
    try:
        with psycopg.connect(
            os.environ["DATABASE_URL"],
            connect_timeout=3,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()

        return {
            "status": "ready",
            "database": "ok",
        }

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="database unavailable",
        ) from exc

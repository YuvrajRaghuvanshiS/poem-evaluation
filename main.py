import json
import os
import random
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()
app = FastAPI(title="Hindi Poem Evaluator")

POEMS_FILE = Path("poems.json")
STATIC_DIR = Path("static")
DATABASE_URL = os.environ.get("DATABASE_URL", "")


# ── Pydantic models ──────────────────────────────────────────────────────────


class Annotation(BaseModel):
    selected_text: str
    comment: str


class PoemEvaluation(BaseModel):
    poem_id: str
    ratings: dict[str, int]
    annotations: list[Annotation] = []


class Evaluator(BaseModel):
    name: str
    email: str


class SubmissionPayload(BaseModel):
    evaluator: Evaluator
    artist_id: str
    evaluations: list[PoemEvaluation]


# ── Connection pool ──────────────────────────────────────────────────────────
#
# One module-level pool, created at startup and closed at shutdown.
# min_size=1  keeps one connection permanently open so the first real request
#             never has to wait for a handshake.
# max_size=3  is plenty for a low-traffic evaluation study; free-tier Postgres
#             plans cap total connections (Neon: 100, Supabase: 15 on free).
# reconnect_timeout / max_waiting give the pool room to recover if the hosted
#             DB drops a connection after its idle timeout.

_pool = None  # psycopg_pool.ConnectionPool, set in startup()


def _init_pool() -> None:
    global _pool
    from psycopg_pool import ConnectionPool

    _pool = ConnectionPool(
        conninfo=DATABASE_URL,
        min_size=1,
        max_size=3,
        max_waiting=30,  # queue up to 30 requests before raising
        reconnect_timeout=10,  # seconds to wait before giving up on reconnect
        open=True,  # open synchronously so startup() can catch errors
    )


def _init_db() -> None:
    """Create the submissions table if it doesn't exist (runs once at startup)."""
    with _pool.connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                submission_id   TEXT        PRIMARY KEY,
                timestamp       TIMESTAMPTZ NOT NULL,
                evaluator_name  TEXT        NOT NULL,
                evaluator_email TEXT        NOT NULL,
                artist_id       TEXT        NOT NULL,
                evaluations     JSONB       NOT NULL
            );
        """)
        conn.commit()


@app.on_event("startup")
def startup() -> None:
    try:
        _init_pool()
        _init_db()
        print("✓ PostgreSQL pool ready.")
    except Exception as e:
        print(f"⚠ DB init failed ({e});")
        raise


@app.on_event("shutdown")
def shutdown() -> None:
    if _pool:
        _pool.close()
        print("✓ PostgreSQL pool closed.")


# ── Save entry point ─────────────────────────────────────────────────


def save_submission(submission: dict) -> None:
    """
    Borrow a connection from the pool, insert, return the connection.
    The 'with _pool.connection()' block handles commit on success and
    rollback on exception automatically.
    """
    with _pool.connection() as conn:
        conn.execute(
            """
            INSERT INTO submissions
                (submission_id, timestamp, evaluator_name, evaluator_email,
                 artist_id, evaluations)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                submission["submission_id"],
                submission["timestamp"],
                submission["evaluator"]["name"],
                submission["evaluator"]["email"],
                submission["artist_id"],
                json.dumps(submission["evaluations"]),
            ),
        )


# ── Poems helper ─────────────────────────────────────────────────────────────


def load_poems() -> dict:
    with open(POEMS_FILE, encoding="utf-8") as f:
        return json.load(f)


# ── API routes ───────────────────────────────────────────────────────────────


@app.get("/api/poems")
def get_poems():
    """Return a randomly selected artist's 5 poems, shuffled to anonymize position."""
    data = load_poems()
    artist = random.choice(data["artists"])
    poems = artist["poems"].copy()
    random.shuffle(poems)
    return {
        "artist_id": artist["artist_id"],
        "artist_name": artist["artist_name"],
        "poems": poems,
    }


@app.post("/api/submit")
def submit_evaluation(payload: SubmissionPayload):
    """Validate and persist a full evaluation submission."""
    # Basic validation: must have exactly 5 poem evaluations
    if len(payload.evaluations) != 5:
        raise HTTPException(
            status_code=400, detail="Exactly 5 poem evaluations required."
        )

    required_criteria = {"fluency", "coherence", "relevance", "creativity", "style"}
    for ev in payload.evaluations:
        if set(ev.ratings.keys()) != required_criteria:
            raise HTTPException(
                status_code=400,
                detail=f"Each poem must be rated on all 5 criteria. Missing for poem {ev.poem_id}.",
            )
        for k, v in ev.ratings.items():
            if not (1 <= v <= 5):
                raise HTTPException(
                    status_code=400, detail=f"Rating for '{k}' must be between 1 and 5."
                )

    submission = {
        "submission_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "evaluator": payload.evaluator.model_dump(),
        "artist_id": payload.artist_id,
        "evaluations": [ev.model_dump() for ev in payload.evaluations],
    }

    save_submission(submission)
    return {"status": "ok", "submission_id": submission["submission_id"]}


# ── Static frontend ──────────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def serve_index():
    return FileResponse(str(STATIC_DIR / "index.html"))

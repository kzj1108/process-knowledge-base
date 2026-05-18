import os
from pathlib import Path

import aiosqlite

ROOT = Path(os.environ.get("PKB_ROOT", str(Path(__file__).resolve().parents[2])))
DB_PATH = os.environ.get("PKB_DB_PATH", str(ROOT / "database" / "process_kb.db"))
SCHEMA_PATH = ROOT / "database" / "schema.sql"
SEED_PATH = ROOT / "database" / "seed.sql"
SCHEMA_VERSION = 2


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    return db


async def _current_schema_version(db: aiosqlite.Connection) -> int:
    try:
        cur = await db.execute("SELECT MAX(version) AS v FROM schema_version")
        row = await cur.fetchone()
        return int(row["v"]) if row and row["v"] is not None else 0
    except Exception:
        return 0


async def _knowledge_count(db: aiosqlite.Connection) -> int:
    try:
        cur = await db.execute("SELECT COUNT(*) AS c FROM process_knowledge")
        return int((await cur.fetchone())["c"])
    except Exception:
        return 0


async def init_db() -> None:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    db = await get_db()
    try:
        ver = await _current_schema_version(db)
        if ver < SCHEMA_VERSION:
            schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
            await db.executescript(schema_sql)
            await db.execute(
                "INSERT OR REPLACE INTO schema_version(version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
        if SEED_PATH.exists() and await _knowledge_count(db) < 8:
            seed_sql = SEED_PATH.read_text(encoding="utf-8")
            await db.executescript(seed_sql)
        await db.commit()
    finally:
        await db.close()

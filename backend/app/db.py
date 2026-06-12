import os
from pathlib import Path

import aiosqlite

ROOT = Path(os.environ.get("PKB_ROOT", str(Path(__file__).resolve().parents[2])))
DB_PATH = os.environ.get("PKB_DB_PATH", str(ROOT / "database" / "process_kb.db"))
SCHEMA_PATH = ROOT / "database" / "schema.sql"
SCHEMA_V3_PATH = ROOT / "database" / "schema_v3.sql"
SEED_PATH = ROOT / "database" / "seed.sql"
SCHEMA_VERSION = 3
TARGET_TOTAL = int(os.environ.get("PKB_TARGET_TOTAL", "50000"))


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
        if ver < 2:
            schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
            await db.executescript(schema_sql)
            await db.execute(
                "INSERT OR REPLACE INTO schema_version(version) VALUES (?)",
                (2,),
            )
        if ver < SCHEMA_VERSION and SCHEMA_V3_PATH.exists():
            v3_sql = SCHEMA_V3_PATH.read_text(encoding="utf-8")
            for stmt in v3_sql.split(";"):
                stmt = stmt.strip()
                if stmt:
                    try:
                        await db.execute(stmt)
                    except Exception:
                        pass
            await db.execute(
                "INSERT OR REPLACE INTO schema_version(version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
        if SEED_PATH.exists() and await _knowledge_count(db) < 8:
            seed_sql = SEED_PATH.read_text(encoding="utf-8")
            await db.executescript(seed_sql)
        await _seed_v3_rules(db)
        await db.commit()
    finally:
        await db.close()


async def _seed_v3_rules(db: aiosqlite.Connection) -> None:
    cur = await db.execute("SELECT COUNT(*) AS c FROM recommendation_rule")
    if (await cur.fetchone())["c"] > 0:
        return
    rules = [
        (
            "RR-001",
            "小模数渗碳淬火齿轮",
            10,
            '{"part_type":"齿轮","heat_treatment":"渗碳淬火","module_max":3}',
            '{"equipment_code":"YK3150E-01","spindle_speed":800,"feed_rate":0.3,"cutting_depth":2.5}',
        ),
        (
            "RR-002",
            "中等模数调质齿轮",
            20,
            '{"part_type":"齿轮","heat_treatment":"调质","module_min":3,"module_max":6}',
            '{"equipment_code":"YK3150E-01","spindle_speed":650,"feed_rate":0.25,"cutting_depth":3.0}',
        ),
        (
            "RR-003",
            "高精度齿轮",
            5,
            '{"accuracy_grade":"6级","part_type":"齿轮"}',
            '{"spindle_speed":500,"feed_rate":0.2,"cutting_depth":2.0}',
        ),
    ]
    await db.executemany(
        """
        INSERT INTO recommendation_rule (rule_code, rule_name, priority, match_json, action_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        rules,
    )

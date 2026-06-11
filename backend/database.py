"""SQLite schema and connection for process knowledge base."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(os.environ.get("PKB_DB_PATH", "data/pkb.db"))
TARGET_TOTAL = int(os.environ.get("PKB_TARGET_TOTAL", "50000"))


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS part (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                part_no TEXT UNIQUE NOT NULL,
                part_name TEXT,
                material TEXT,
                drawing_no TEXT,
                module REAL,
                teeth_count INTEGER,
                pressure_angle REAL,
                helix_angle REAL,
                part_type TEXT,
                heat_treatment TEXT,
                accuracy_grade TEXT,
                face_width REAL,
                secret_level TEXT DEFAULT 'INTERNAL',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS process (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                part_no TEXT NOT NULL,
                step_no INTEGER,
                operation_no INTEGER,
                operation_name TEXT,
                version TEXT DEFAULT 'A',
                status TEXT DEFAULT 'active',
                equipment_code TEXT,
                machine_type TEXT,
                spindle_speed REAL,
                feed_rate REAL,
                depth REAL,
                tool_code TEXT,
                nc_program_no TEXT,
                coolant TEXT,
                notes TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT,
                tags TEXT,
                part_no TEXT,
                status TEXT DEFAULT 'published',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS optimization_record (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                opt_id TEXT UNIQUE,
                part_no TEXT NOT NULL,
                operation_no INTEGER,
                equipment_code TEXT,
                baseline_params TEXT,
                recommended_params TEXT,
                candidate_set TEXT,
                before_params TEXT,
                after_params TEXT,
                improvement TEXT,
                model_version TEXT,
                status TEXT DEFAULT 'completed',
                adopted INTEGER DEFAULT 0,
                source TEXT DEFAULT 'digital_twin',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS equipment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE,
                name TEXT,
                model TEXT,
                status TEXT DEFAULT 'idle',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS realtime_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_code TEXT,
                metric_name TEXT,
                metric_value REAL,
                unit TEXT,
                recorded_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS import_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT,
                record_type TEXT,
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS recommendation_rule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_code TEXT UNIQUE NOT NULL,
                rule_name TEXT NOT NULL,
                priority INTEGER DEFAULT 100,
                match_json TEXT NOT NULL,
                action_json TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS recommendation_result (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_json TEXT NOT NULL,
                matched_rules TEXT,
                recommended_process TEXT,
                similar_cases TEXT,
                cited_knowledge TEXT,
                risk_hints TEXT,
                confidence REAL,
                human_confirmed INTEGER DEFAULT 0,
                confirm_note TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                entity_type TEXT,
                entity_id TEXT,
                operator TEXT DEFAULT 'api',
                detail TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS quality_record (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id TEXT,
                part_no TEXT NOT NULL,
                operation_no INTEGER,
                equipment_code TEXT,
                batch_no TEXT,
                process_step TEXT,
                inspection_item TEXT,
                measured_value REAL,
                standard_value REAL,
                tolerance TEXT,
                result TEXT,
                profile_error REAL,
                pitch_error REAL,
                helix_error REAL,
                burr_status TEXT,
                surface_wave TEXT,
                quality_grade TEXT,
                issue TEXT,
                action_taken TEXT,
                recheck_result TEXT,
                inspector TEXT,
                trace_source TEXT,
                status TEXT DEFAULT 'OPEN',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS resource (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resource_type TEXT NOT NULL,
                code TEXT UNIQUE NOT NULL,
                name TEXT,
                spec_json TEXT,
                valid_range TEXT,
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT (datetime('now'))
            );
            """
        )
        _migrate_columns(conn)
        _seed_defaults(conn)
        _seed_demo_data(conn)


def _migrate_columns(conn: sqlite3.Connection) -> None:
    """Add columns for existing SQLite DBs (Render redeploy)."""
    alters = [
        "ALTER TABLE process ADD COLUMN operation_no INTEGER",
        "ALTER TABLE process ADD COLUMN version TEXT DEFAULT 'A'",
        "ALTER TABLE process ADD COLUMN status TEXT DEFAULT 'active'",
        "ALTER TABLE process ADD COLUMN equipment_code TEXT",
        "ALTER TABLE process ADD COLUMN nc_program_no TEXT",
        "ALTER TABLE process ADD COLUMN coolant TEXT",
        "ALTER TABLE optimization_record ADD COLUMN opt_id TEXT",
        "ALTER TABLE optimization_record ADD COLUMN operation_no INTEGER",
        "ALTER TABLE optimization_record ADD COLUMN equipment_code TEXT",
        "ALTER TABLE optimization_record ADD COLUMN baseline_params TEXT",
        "ALTER TABLE optimization_record ADD COLUMN recommended_params TEXT",
        "ALTER TABLE optimization_record ADD COLUMN candidate_set TEXT",
        "ALTER TABLE optimization_record ADD COLUMN model_version TEXT",
        "ALTER TABLE optimization_record ADD COLUMN status TEXT DEFAULT 'completed'",
        "ALTER TABLE optimization_record ADD COLUMN adopted INTEGER DEFAULT 0",
        "ALTER TABLE recommendation_result ADD COLUMN similar_cases TEXT",
        "ALTER TABLE recommendation_result ADD COLUMN cited_knowledge TEXT",
        "ALTER TABLE recommendation_result ADD COLUMN risk_hints TEXT",
        "ALTER TABLE recommendation_result ADD COLUMN human_confirmed INTEGER DEFAULT 0",
        "ALTER TABLE recommendation_result ADD COLUMN confirm_note TEXT",
        "ALTER TABLE part ADD COLUMN drawing_no TEXT",
        "ALTER TABLE part ADD COLUMN secret_level TEXT DEFAULT 'INTERNAL'",
        "ALTER TABLE quality_record ADD COLUMN record_id TEXT",
        "ALTER TABLE quality_record ADD COLUMN operation_no INTEGER",
        "ALTER TABLE quality_record ADD COLUMN equipment_code TEXT",
        "ALTER TABLE quality_record ADD COLUMN profile_error REAL",
        "ALTER TABLE quality_record ADD COLUMN pitch_error REAL",
        "ALTER TABLE quality_record ADD COLUMN helix_error REAL",
        "ALTER TABLE quality_record ADD COLUMN burr_status TEXT",
        "ALTER TABLE quality_record ADD COLUMN surface_wave TEXT",
        "ALTER TABLE quality_record ADD COLUMN quality_grade TEXT",
        "ALTER TABLE quality_record ADD COLUMN issue TEXT",
        "ALTER TABLE quality_record ADD COLUMN action_taken TEXT",
        "ALTER TABLE quality_record ADD COLUMN recheck_result TEXT",
        "ALTER TABLE quality_record ADD COLUMN inspector TEXT",
        "ALTER TABLE quality_record ADD COLUMN status TEXT DEFAULT 'OPEN'",
    ]
    for sql in alters:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass


def _seed_defaults(conn: sqlite3.Connection) -> None:
    cur = conn.execute("SELECT COUNT(*) FROM recommendation_rule")
    if cur.fetchone()[0] > 0:
        return
    rules = [
        (
            "RR-001",
            "小模数渗碳淬火齿轮",
            10,
            '{"part_type":"齿轮","heat_treatment":"渗碳淬火","module_max":3}',
            '{"machine_type":"数控滚齿机","spindle_speed":800,"feed_rate":0.3,"depth":2.5}',
        ),
        (
            "RR-002",
            "中等模数调质齿轮",
            20,
            '{"part_type":"齿轮","heat_treatment":"调质","module_min":3,"module_max":6}',
            '{"machine_type":"数控滚齿机","spindle_speed":650,"feed_rate":0.25,"depth":3.0}',
        ),
        (
            "RR-003",
            "高精度齿轮",
            5,
            '{"accuracy_grade":"6级","part_type":"齿轮"}',
            '{"machine_type":"数控滚齿机","spindle_speed":500,"feed_rate":0.2,"depth":2.0,"notes":"降速精加工"}',
        ),
    ]
    conn.executemany(
        """
        INSERT INTO recommendation_rule (rule_code, rule_name, priority, match_json, action_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        rules,
    )


def _seed_demo_data(conn: sqlite3.Connection) -> None:
    """实施方案5 演示数据（空库时写入，便于 Render 汇报演示）。"""
    if conn.execute("SELECT COUNT(*) FROM part").fetchone()[0] > 0:
        return
    conn.executemany(
        """
        INSERT INTO part (part_no, part_name, material, drawing_no, module, teeth_count,
                          part_type, heat_treatment, accuracy_grade, face_width, secret_level)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("GH-2024-088", "中间轴齿轮", "20CrMnTi", "DW-GH-088", 2.5, 32, "齿轮", "渗碳淬火", "6级", 28.0, "INTERNAL"),
            ("PART-DEMO-001", "演示齿轮轴", "40Cr", "DW-DEMO-01", 3.0, 24, "齿轮", "调质", "7级", 22.0, "DEMO"),
        ],
    )
    conn.executemany(
        """
        INSERT INTO process (part_no, step_no, operation_no, operation_name, version, status,
                             equipment_code, machine_type, spindle_speed, feed_rate, depth, tool_code, nc_program_no, coolant)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("GH-2024-088", 50, 50, "滚齿", "A", "active", "YK3150E-01", "数控滚齿机", 650, 0.25, 2.8, "HOB-M2.5-A", "O2088", "油冷"),
            ("PART-DEMO-001", 10, 10, "滚齿", "A", "active", "YK3150E-01", "数控滚齿机", 800, 0.3, 2.5, "HOB-M3-B", "O1001", "油冷"),
        ],
    )
    conn.executemany(
        """
        INSERT INTO knowledge (category, title, content, tags, part_no, status)
        VALUES (?, ?, ?, ?, ?, 'published')
        """,
        [
            ("RULE", "20CrMnTi滚齿毛刺控制", "精滚阶段降进给0.05mm/r，加强去毛刺与齿顶倒角检查。", "毛刺;20CrMnTi", "GH-2024-088"),
            ("CASE", "齿面波纹处置经验", "检查主轴负载与刀具磨损，必要时更换滚刀并降速至550rpm。", "波纹;质量", "GH-2024-088"),
        ],
    )
    conn.executemany(
        "INSERT OR IGNORE INTO equipment (code, name, model, status) VALUES (?, ?, ?, ?)",
        [("YK3150E-01", "数控滚齿机", "YK3150E", "RUN"), ("LOADER-01", "上下料设备", "桁架", "idle")],
    )
    conn.executemany(
        """
        INSERT OR IGNORE INTO resource (resource_type, code, name, spec_json, valid_range)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            ("machine", "YK3150E-01", "数控滚齿机", '{"max_module":8,"max_rpm":800}', "模数1~8"),
            ("tool", "HOB-M2.5-A", "滚刀 M2.5", '{"module":2.5,"material":"M35"}', "20CrMnTi渗碳件"),
        ],
    )
    conn.execute(
        """
        INSERT INTO quality_record
        (record_id, part_no, operation_no, equipment_code, profile_error, pitch_error,
         burr_status, quality_grade, issue, action_taken, inspector, trace_source, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "QC-2024-088-01", "GH-2024-088", 50, "YK3150E-01", 0.012, 0.008,
            "轻微", "合格", "齿顶毛刺", "调整去毛刺工序并复检", "质检员A", "mes", "CLOSED",
        ),
    )


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


def write_audit(action: str, entity_type: str = "", entity_id: str = "", detail: str = "", operator: str = "api") -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO audit_log (action, entity_type, entity_id, operator, detail) VALUES (?, ?, ?, ?, ?)",
            (action, entity_type, entity_id, operator, detail),
        )


def get_overview_stats() -> dict:
    with get_conn() as conn:
        def count(table: str) -> int:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

        return {
            "target_total": TARGET_TOTAL,
            "parts": count("part"),
            "process_steps": count("process"),
            "knowledge_items": count("knowledge"),
            "equipment": count("equipment"),
            "optimization_records": count("optimization_record"),
            "quality_records": count("quality_record"),
            "resources": count("resource"),
            "realtime_records": count("realtime_data"),
            "recommendation_rules": count("recommendation_rule"),
            "recommendation_results": count("recommendation_result"),
            "import_batches": count("import_log"),
            "effective_total": (
                count("part")
                + count("process")
                + count("knowledge")
                + count("equipment")
                + count("resource")
                + count("optimization_record")
                + count("quality_record")
                + count("recommendation_rule")
                + count("recommendation_result")
            ),
        }

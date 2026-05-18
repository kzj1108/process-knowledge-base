-- 工艺知识库 v2 Schema（SQLite 开发 / 达梦·金仓生产迁移）

CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 零件主数据
CREATE TABLE IF NOT EXISTS part_catalog (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    part_no         VARCHAR(64) NOT NULL UNIQUE,
    part_name       VARCHAR(128) NOT NULL,
    material        VARCHAR(64),
    drawing_no      VARCHAR(64),
    category        VARCHAR(64),
    remark          TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 设备主数据
CREATE TABLE IF NOT EXISTS equipment (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            VARCHAR(64) NOT NULL UNIQUE,
    name            VARCHAR(128) NOT NULL,
    type            VARCHAR(32) NOT NULL,
    model           VARCHAR(64),
    workshop        VARCHAR(64),
    status          VARCHAR(16) DEFAULT 'ACTIVE',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 静态结构化工艺（工序级）
CREATE TABLE IF NOT EXISTS part_process (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    part_no         VARCHAR(64) NOT NULL,
    part_name       VARCHAR(128),
    material        VARCHAR(64),
    operation_no    INTEGER NOT NULL,
    operation_name  VARCHAR(128),
    equipment_code  VARCHAR(64),
    tool_code       VARCHAR(64),
    spindle_speed   REAL,
    cutting_depth   REAL,
    feed_rate       REAL,
    speed_min       REAL,
    speed_max       REAL,
    depth_min       REAL,
    depth_max       REAL,
    feed_min        REAL,
    feed_max        REAL,
    version         VARCHAR(16) DEFAULT '1.0',
    is_active       INTEGER DEFAULT 1,
    approved_by     VARCHAR(64),
    remark          TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(part_no, operation_no, version)
);

CREATE INDEX IF NOT EXISTS idx_process_part ON part_process(part_no);
CREATE INDEX IF NOT EXISTS idx_process_equip ON part_process(equipment_code);

-- 工艺知识条目
CREATE TABLE IF NOT EXISTS process_knowledge (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    category        VARCHAR(32) NOT NULL,
    title           VARCHAR(256) NOT NULL,
    content         TEXT NOT NULL,
    tags            VARCHAR(256),
    related_part_no VARCHAR(64),
    related_op_no   INTEGER,
    source          VARCHAR(64),
    author          VARCHAR(64),
    status          VARCHAR(16) DEFAULT 'PUBLISHED',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_knowledge_part ON process_knowledge(related_part_no);
CREATE INDEX IF NOT EXISTS idx_knowledge_cat ON process_knowledge(category);

-- 知识条目与工序关联（多对多）
CREATE TABLE IF NOT EXISTS knowledge_process_link (
    knowledge_id    INTEGER NOT NULL,
    process_id      INTEGER NOT NULL,
    PRIMARY KEY (knowledge_id, process_id)
);

-- 实时加工工况（动态）
CREATE TABLE IF NOT EXISTS machining_realtime (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_code  VARCHAR(64) NOT NULL,
    part_no         VARCHAR(64),
    ts              TIMESTAMP NOT NULL,
    spindle_speed   REAL,
    cutting_depth   REAL,
    feed_rate       REAL,
    axis_x          REAL,
    axis_y          REAL,
    axis_z          REAL,
    joint_angles    TEXT,
    program_no      VARCHAR(32),
    status          VARCHAR(32),
    raw_payload     TEXT
);

CREATE INDEX IF NOT EXISTS idx_realtime_equip_ts ON machining_realtime(equipment_code, ts DESC);

-- 优化模型运行记录（动态）
CREATE TABLE IF NOT EXISTS optimization_run (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_code  VARCHAR(64) NOT NULL,
    part_no         VARCHAR(64),
    operation_no    INTEGER,
    input_snapshot  TEXT,
    pred_spindle    REAL,
    pred_depth      REAL,
    pred_feed       REAL,
    model_version   VARCHAR(32),
    score           REAL,
    adopted         INTEGER DEFAULT 0,
    remark          TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_opt_equip ON optimization_run(equipment_code, created_at DESC);

-- 操作审计日志
CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    action          VARCHAR(32) NOT NULL,
    entity          VARCHAR(32) NOT NULL,
    entity_id       INTEGER,
    detail          TEXT,
    operator        VARCHAR(64),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

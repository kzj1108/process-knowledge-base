-- v3: 实施方案5 — 滚齿单元扩展、质量追溯、方案推荐

ALTER TABLE part_catalog ADD COLUMN module_m REAL;
ALTER TABLE part_catalog ADD COLUMN teeth_z INTEGER;
ALTER TABLE part_catalog ADD COLUMN face_width REAL;
ALTER TABLE part_catalog ADD COLUMN precision_grade VARCHAR(32);
ALTER TABLE part_catalog ADD COLUMN heat_treatment VARCHAR(64);
ALTER TABLE part_catalog ADD COLUMN secret_level VARCHAR(16) DEFAULT 'INTERNAL';

CREATE TABLE IF NOT EXISTS quality_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id VARCHAR(64),
    part_no VARCHAR(64) NOT NULL,
    operation_no INTEGER,
    equipment_code VARCHAR(64),
    profile_error REAL,
    pitch_error REAL,
    helix_error REAL,
    burr_status VARCHAR(32),
    surface_wave VARCHAR(32),
    quality_grade VARCHAR(16),
    issue TEXT,
    action_taken TEXT,
    recheck_result VARCHAR(128),
    inspector VARCHAR(64),
    trace_source VARCHAR(32) DEFAULT 'mes',
    status VARCHAR(16) DEFAULT 'OPEN',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_quality_part ON quality_record(part_no);

CREATE TABLE IF NOT EXISTS recommendation_rule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_code VARCHAR(32) UNIQUE NOT NULL,
    rule_name VARCHAR(128) NOT NULL,
    priority INTEGER DEFAULT 100,
    match_json TEXT NOT NULL,
    action_json TEXT NOT NULL,
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resource (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_type VARCHAR(32) NOT NULL,
    code VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(128),
    spec_json TEXT,
    valid_range VARCHAR(128),
    status VARCHAR(16) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

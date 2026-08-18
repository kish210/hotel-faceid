-- Hotel Face-ID / Access-Log schema
-- PostgreSQL 16 (portable schema: vectors live in JSONB, matched via numpy)

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------------- persons
CREATE TYPE person_role AS ENUM ('guest', 'staff', 'visitor', 'unknown');

CREATE TABLE persons (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    display_name    TEXT,
    role            person_role  NOT NULL DEFAULT 'unknown',
    room_number     TEXT,
    phone           TEXT,
    reference_image TEXT,                       -- relative path of the face crop
    first_seen_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_seen_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    merged_into     UUID REFERENCES persons(id) ON DELETE SET NULL,
    deleted_at      TIMESTAMPTZ,                -- soft delete / right-to-be-forgotten
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX idx_persons_role       ON persons(role) WHERE deleted_at IS NULL;
CREATE INDEX idx_persons_last_seen  ON persons(last_seen_at DESC);

-- ------------------------------------------------------- face_embeddings
-- Multiple embeddings per person improve re-identification across
-- lighting/pose variation. 512 dims == ArcFace (InsightFace buffalo_l).
-- The vector is stored as a JSON array and matched in-process with numpy
-- (portable across Postgres and SQLite, no pgvector needed).
CREATE TABLE face_embeddings (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    person_id   UUID NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    embedding   JSONB NOT NULL,
    image_path  TEXT,
    quality     REAL,                            -- 0..1 face quality score
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_face_embeddings_person ON face_embeddings(person_id);

-- ---------------------------------------------------------------- cameras
CREATE TYPE camera_brand   AS ENUM ('dahua', 'hikvision', 'onvif', 'generic');
CREATE TYPE camera_purpose AS ENUM ('entry', 'exit', 'bidirectional', 'monitor');

CREATE TABLE cameras (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name           TEXT NOT NULL,
    brand          camera_brand   NOT NULL DEFAULT 'onvif',
    purpose        camera_purpose NOT NULL DEFAULT 'bidirectional',
    location       TEXT,
    host           TEXT NOT NULL,
    port           INTEGER NOT NULL DEFAULT 80,
    rtsp_url       TEXT,
    username       TEXT,
    password_enc   TEXT,                          -- encrypted at rest
    use_device_face_engine BOOLEAN NOT NULL DEFAULT FALSE,
    enabled        BOOLEAN NOT NULL DEFAULT TRUE,
    online         BOOLEAN NOT NULL DEFAULT FALSE,
    last_seen_at   TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ----------------------------------------------------------------- events
CREATE TYPE event_direction AS ENUM ('in', 'out');

CREATE TABLE events (
    id           BIGSERIAL PRIMARY KEY,
    person_id    UUID NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    camera_id    UUID REFERENCES cameras(id) ON DELETE SET NULL,
    direction    event_direction NOT NULL,
    occurred_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    confidence   REAL,
    image_path   TEXT,
    manual       BOOLEAN NOT NULL DEFAULT FALSE,  -- corrected by an operator
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_events_person_time ON events(person_id, occurred_at DESC);
CREATE INDEX idx_events_time        ON events(occurred_at DESC);
CREATE INDEX idx_events_direction   ON events(direction, occurred_at DESC);

-- ------------------------------------------------------------------ stays
-- One row per continuous visit. nights is recomputed on each check-out.
CREATE TABLE stays (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    person_id     UUID NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    checkin_at    TIMESTAMPTZ NOT NULL,
    checkout_at   TIMESTAMPTZ,
    nights        INTEGER NOT NULL DEFAULT 0,
    room_number   TEXT,
    active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_stays_person ON stays(person_id, checkin_at DESC);
CREATE UNIQUE INDEX idx_stays_one_active ON stays(person_id) WHERE active;

-- ------------------------------------------------------------------ users
CREATE TYPE user_role AS ENUM ('admin', 'manager', 'reception', 'security');

CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username      TEXT UNIQUE NOT NULL,
    full_name     TEXT,
    password_hash TEXT NOT NULL,
    role          user_role NOT NULL DEFAULT 'reception',
    active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------- audit_logs
CREATE TABLE audit_logs (
    id          BIGSERIAL PRIMARY KEY,
    user_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    action      TEXT NOT NULL,
    entity      TEXT,
    entity_id   TEXT,
    detail      JSONB,
    ip_address  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_time ON audit_logs(created_at DESC);

-- --------------------------------------------------------- seed admin user
-- password: admin  (bcrypt) — MUST be changed on first login
INSERT INTO users (username, full_name, password_hash, role)
VALUES ('admin', 'System Administrator',
        '$2b$12$.f6kUmZvUhaZibN/D./QjuJa0W58ASU1bQmxeTJYLrV5CaTpXi99q', 'admin')
ON CONFLICT (username) DO NOTHING;

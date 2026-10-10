-- AlloyDB / PostgreSQL schema for the knowledge fabric. Idempotent.
-- Embedding dimension is substituted at runtime ({dim}).
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id          TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    title       TEXT NOT NULL,
    url         TEXT,
    author      TEXT,
    updated_at  TIMESTAMPTZ,
    acl_roles   TEXT[] NOT NULL,
    metadata    JSONB NOT NULL DEFAULT '{{}}'
);

CREATE TABLE IF NOT EXISTS chunks (
    id          TEXT PRIMARY KEY,
    doc_id      TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ordinal     INT NOT NULL,
    text        TEXT NOT NULL,
    source      TEXT NOT NULL,
    title       TEXT NOT NULL,
    url         TEXT,
    acl_roles   TEXT[] NOT NULL,          -- denormalized for filter-before-rank
    updated_at  TIMESTAMPTZ,
    embedding   vector({dim}) NOT NULL,
    tsv         tsvector GENERATED ALWAYS AS (
                    setweight(to_tsvector('english', title), 'A') || setweight(to_tsvector('english', text), 'B')
                ) STORED
);

CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_tsv_gin ON chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS chunks_acl_gin ON chunks USING gin (acl_roles);

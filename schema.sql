-- =============================================================================
-- tg-news-channel-bot — Database Schema
-- PostgreSQL 14+
-- =============================================================================

-- Main articles table
CREATE TABLE IF NOT EXISTS t_feed (
    c_id            TEXT PRIMARY KEY,               -- Article URL used as unique ID
    c_title         TEXT NOT NULL,                  -- Article headline
    c_type          TEXT,                           -- Feed entry type (e.g. 'article')
    c_link          TEXT NOT NULL,                  -- Source URL
    c_date          TIMESTAMPTZ NOT NULL,           -- Publication date from RSS feed
    c_tags          TEXT,                           -- Comma-separated tags from feed
    c_summary       TEXT,                           -- Short excerpt from feed
    c_media_content TEXT,                           -- Image/media URL from feed
    c_content       TEXT,                           -- Full article body (scraped)
    c_status        TEXT NOT NULL DEFAULT 'new',    -- ArticleStatus enum value
    c_rating        INTEGER DEFAULT 0,              -- GPT interest score (0–100)
    c_lurkable      INTEGER DEFAULT 0,              -- GPT lurkmore-style score (0–100)
    c_reasoning     TEXT,                           -- GPT reasoning / notes
    c_category      TEXT,                           -- Content category (movie_industry, rumor, etc.)
    c_lurk          TEXT,                           -- AI-generated translated post text
    c_used          BOOLEAN NOT NULL DEFAULT FALSE, -- Whether the article has been posted
    c_created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    c_updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_status CHECK (c_status IN ('new', 'processing', 'rated', 'translated', 'posted', 'failed')),
    CONSTRAINT chk_rating  CHECK (c_rating  BETWEEN 0 AND 100),
    CONSTRAINT chk_lurkable CHECK (c_lurkable BETWEEN 0 AND 100)
);

-- Dynamic configuration key-value store
CREATE TABLE IF NOT EXISTS t_config (
    c_key        TEXT PRIMARY KEY,
    c_value      TEXT NOT NULL,
    c_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Indexes ──────────────────────────────────────────────────────────────────

-- Fast lookup for articles that need AI rating
CREATE INDEX IF NOT EXISTS idx_feed_status ON t_feed (c_status);

-- Fast lookup for best unposted article (used by posting scheduler)
CREATE INDEX IF NOT EXISTS idx_feed_unposted ON t_feed (c_rating DESC, c_lurkable DESC)
    WHERE c_used = FALSE AND c_status = 'rated';

-- Filter by publication date (used in fetch window queries)
CREATE INDEX IF NOT EXISTS idx_feed_date ON t_feed (c_date DESC);

-- ─── Auto-update updated_at ───────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.c_updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_feed_updated_at
    BEFORE UPDATE ON t_feed
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_config_updated_at
    BEFORE UPDATE ON t_config
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ─── Default config values ────────────────────────────────────────────────────

INSERT INTO t_config (c_key, c_value) VALUES
    ('max_daily_posts',       '24'),
    ('min_rating_threshold',  '60'),
    ('min_lurkable_threshold','70'),
    ('fetch_interval_hours',  '1')
ON CONFLICT (c_key) DO NOTHING;

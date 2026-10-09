-- Tables read and written by Chainlit's SQLAlchemyDataLayer (chainlit 2.12.0: the columns
-- change between versions, which is why the version is pinned in pyproject.toml), plus
-- our own accounts table. Created at startup (chat/db.py), never dropped.
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    identifier TEXT NOT NULL UNIQUE,
    metadata TEXT NOT NULL,
    createdAt TEXT
);
CREATE TABLE IF NOT EXISTS threads (
    id TEXT PRIMARY KEY,
    createdAt TEXT,
    name TEXT,
    userId TEXT,
    userIdentifier TEXT,
    tags TEXT,
    metadata TEXT
);
CREATE TABLE IF NOT EXISTS steps (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    threadId TEXT NOT NULL,
    parentId TEXT,
    streaming INTEGER NOT NULL DEFAULT 0,
    waitForAnswer INTEGER,
    isError INTEGER,
    metadata TEXT,
    tags TEXT,
    input TEXT,
    output TEXT,
    createdAt TEXT,
    start TEXT,
    end TEXT,
    generation TEXT,
    showInput TEXT,
    language TEXT,
    defaultOpen INTEGER,
    autoCollapse INTEGER
);
CREATE TABLE IF NOT EXISTS elements (
    id TEXT PRIMARY KEY,
    threadId TEXT,
    type TEXT,
    chainlitKey TEXT,
    url TEXT,
    objectKey TEXT,
    name TEXT NOT NULL,
    display TEXT,
    size TEXT,
    language TEXT,
    page INTEGER,
    forId TEXT,
    mime TEXT,
    props TEXT
);
CREATE TABLE IF NOT EXISTS feedbacks (
    id TEXT PRIMARY KEY,
    forId TEXT NOT NULL,
    threadId TEXT NOT NULL,
    value INTEGER NOT NULL,
    comment TEXT
);
CREATE INDEX IF NOT EXISTS idx_steps_thread ON steps (threadId);
CREATE INDEX IF NOT EXISTS idx_threads_user ON threads (userId);

-- Accounts: a pseudo (case-insensitive) and two argon2 hashes, nothing else.
CREATE TABLE IF NOT EXISTS accounts (
    pseudo TEXT PRIMARY KEY COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    recovery_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_login_at TEXT
);

-- Journal of the answers (#18), written by journal/store.py for the chat and for /api/query.
-- No pseudo and no IP: thread_id and message_id only tie an entry to a conversation of the
-- chat (for the feedback buttons of #19) and are cleared when that account is deleted.
-- Purged after ANSWER_LOG_RETENTION_DAYS (python -m journal.purge).
CREATE TABLE IF NOT EXISTS answer_log (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    channel TEXT NOT NULL CHECK (channel IN ('chat', 'api')),
    thread_id TEXT,
    message_id TEXT,
    question TEXT NOT NULL,
    rewritten TEXT,
    answer TEXT NOT NULL,
    route TEXT NOT NULL CHECK (route IN ('generate', 'refuse', 'smalltalk', 'error')),
    top_score REAL,
    sources TEXT NOT NULL DEFAULT '[]',
    retrieved TEXT NOT NULL DEFAULT '[]',
    llm_model TEXT,
    llm_alias TEXT,
    tokens_in INTEGER,
    tokens_out INTEGER,
    latency_ms INTEGER,
    error TEXT,
    collection TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    threshold REAL NOT NULL,
    app_version TEXT,
    review_label TEXT CHECK (review_label IN ('bonne', 'partielle', 'fausse', 'hors_sujet')),
    review_note TEXT,
    reviewed_at TEXT,
    promoted_as TEXT
);
CREATE INDEX IF NOT EXISTS idx_answer_log_created ON answer_log (created_at);
CREATE INDEX IF NOT EXISTS idx_answer_log_review ON answer_log (review_label);
CREATE INDEX IF NOT EXISTS idx_answer_log_route ON answer_log (route);
CREATE INDEX IF NOT EXISTS idx_answer_log_thread ON answer_log (thread_id);

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

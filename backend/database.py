import aiosqlite
import os

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "data.db"))

CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_name TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    total_results INTEGER DEFAULT 0,
    sources_done TEXT DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);

CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_id INTEGER NOT NULL,
    company_name TEXT,
    job_title TEXT,
    job_url TEXT,
    location TEXT,
    contract_type TEXT,
    tool_context TEXT,
    source TEXT,
    scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (search_id) REFERENCES searches(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    job_url TEXT NOT NULL,
    job_title TEXT NOT NULL,
    company_name TEXT DEFAULT '',
    source TEXT DEFAULT '',
    location TEXT DEFAULT '',
    contract_type TEXT DEFAULT '',
    tool_context TEXT DEFAULT '[]',
    status TEXT DEFAULT 'saved',
    notes TEXT DEFAULT '',
    applied_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, job_url)
);

CREATE INDEX IF NOT EXISTS idx_results_search_id   ON results(search_id);
CREATE INDEX IF NOT EXISTS idx_searches_tool        ON searches(tool_name);
CREATE INDEX IF NOT EXISTS idx_applications_user    ON applications(user_id);
CREATE INDEX IF NOT EXISTS idx_applications_status  ON applications(user_id, status);
"""


async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        for statement in CREATE_TABLES.strip().split(";"):
            s = statement.strip()
            if s:
                await db.execute(s)
        await db.commit()

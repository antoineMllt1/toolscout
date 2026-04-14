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

CREATE TABLE IF NOT EXISTS application_preps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    application_id INTEGER NOT NULL,
    profile_id INTEGER,
    status TEXT NOT NULL DEFAULT 'ready',
    target_snapshot_json TEXT DEFAULT '{}',
    fit_summary_json TEXT DEFAULT '{}',
    selected_evidence_json TEXT DEFAULT '{}',
    interview_questions_json TEXT DEFAULT '{}',
    star_stories_json TEXT DEFAULT '[]',
    portfolio_ideas_json TEXT DEFAULT '[]',
    strengthening_actions_json TEXT DEFAULT '[]',
    copy_notes_json TEXT DEFAULT '[]',
    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE,
    FOREIGN KEY (profile_id) REFERENCES cv_profiles(id) ON DELETE SET NULL,
    UNIQUE(user_id, application_id)
);

CREATE INDEX IF NOT EXISTS idx_application_preps_user_app ON application_preps(user_id, application_id);

CREATE TABLE IF NOT EXISTS watchlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    tools_json TEXT DEFAULT '[]',
    roles_json TEXT DEFAULT '[]',
    cadence TEXT NOT NULL DEFAULT 'daily',
    active INTEGER DEFAULT 1,
    slack_enabled INTEGER DEFAULT 0,
    last_run_at DATETIME,
    next_run_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS watchlist_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    watchlist_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    tools_json TEXT DEFAULT '[]',
    roles_json TEXT DEFAULT '[]',
    search_ids_json TEXT DEFAULT '[]',
    matched_results INTEGER DEFAULT 0,
    total_results INTEGER DEFAULT 0,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    error TEXT DEFAULT '',
    FOREIGN KEY (watchlist_id) REFERENCES watchlists(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_watchlists_user ON watchlists(user_id);
CREATE INDEX IF NOT EXISTS idx_watchlists_next_run ON watchlists(active, next_run_at);
CREATE INDEX IF NOT EXISTS idx_watchlist_runs_watchlist ON watchlist_runs(watchlist_id, started_at DESC);

CREATE TABLE IF NOT EXISTS cv_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    title TEXT NOT NULL DEFAULT 'Main profile',
    full_name TEXT DEFAULT '',
    headline TEXT DEFAULT '',
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    location TEXT DEFAULT '',
    website TEXT DEFAULT '',
    linkedin TEXT DEFAULT '',
    github TEXT DEFAULT '',
    target_roles_json TEXT DEFAULT '[]',
    cv_text TEXT DEFAULT '',
    portfolio_url TEXT DEFAULT '',
    portfolio_snapshot_json TEXT DEFAULT '{}',
    portfolio_last_scraped_at DATETIME,
    summary TEXT DEFAULT '',
    skills_json TEXT DEFAULT '[]',
    languages_json TEXT DEFAULT '[]',
    certifications_json TEXT DEFAULT '[]',
    education_json TEXT DEFAULT '[]',
    experience_json TEXT DEFAULT '[]',
    projects_json TEXT DEFAULT '[]',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cv_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    profile_id INTEGER,
    template_slug TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_id INTEGER,
    target_title TEXT DEFAULT '',
    target_company TEXT DEFAULT '',
    target_job_url TEXT DEFAULT '',
    target_snapshot_json TEXT DEFAULT '{}',
    selected_payload_json TEXT DEFAULT '{}',
    latex_source TEXT DEFAULT '',
    prompt_payload_json TEXT DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (profile_id) REFERENCES cv_profiles(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_cv_profiles_user ON cv_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_cv_drafts_user ON cv_drafts(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS story_bank_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    situation TEXT DEFAULT '',
    task TEXT DEFAULT '',
    action TEXT DEFAULT '',
    result TEXT DEFAULT '',
    reflection TEXT DEFAULT '',
    tags_json TEXT DEFAULT '[]',
    source_kind TEXT DEFAULT '',
    source_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pipeline_queue_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    label TEXT NOT NULL,
    url TEXT DEFAULT '',
    company_name TEXT DEFAULT '',
    role_hint TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    notes TEXT DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS company_portals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    company_name TEXT NOT NULL,
    careers_url TEXT NOT NULL,
    active INTEGER DEFAULT 1,
    favorite INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    tags_json TEXT DEFAULT '[]',
    cadence TEXT DEFAULT 'weekly',
    last_scan_at DATETIME,
    next_scan_at DATETIME,
    last_result_json TEXT DEFAULT '{}',
    last_delta_json TEXT DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS company_portal_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portal_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    jobs_found INTEGER DEFAULT 0,
    new_jobs INTEGER DEFAULT 0,
    removed_jobs INTEGER DEFAULT 0,
    summary_json TEXT DEFAULT '{}',
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    error TEXT DEFAULT '',
    FOREIGN KEY (portal_id) REFERENCES company_portals(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS company_research_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    company_name TEXT NOT NULL,
    role_title TEXT DEFAULT '',
    source_url TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    culture_json TEXT DEFAULT '[]',
    product_json TEXT DEFAULT '[]',
    risks_json TEXT DEFAULT '[]',
    headings_json TEXT DEFAULT '[]',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS career_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    title TEXT DEFAULT '',
    input_text TEXT DEFAULT '',
    output_json TEXT DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS favorite_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    search_result_id INTEGER,
    job_url TEXT NOT NULL,
    job_title TEXT DEFAULT '',
    company_name TEXT DEFAULT '',
    source TEXT DEFAULT '',
    location TEXT DEFAULT '',
    contract_type TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    payload_json TEXT DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, job_url)
);

CREATE INDEX IF NOT EXISTS idx_story_bank_user ON story_bank_entries(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_queue_user ON pipeline_queue_items(user_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_company_portals_user ON company_portals(user_id, active, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_company_portal_runs_portal ON company_portal_runs(portal_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_company_research_user ON company_research_reports(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_career_evaluations_user ON career_evaluations(user_id, kind, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_favorite_jobs_user ON favorite_jobs(user_id, created_at DESC);
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
        await _run_migrations(db)
        await db.commit()


async def _run_migrations(db):
    await _ensure_columns(
        db,
        "cv_profiles",
        {
            "target_roles_json": "TEXT DEFAULT '[]'",
            "cv_text": "TEXT DEFAULT ''",
            "portfolio_url": "TEXT DEFAULT ''",
            "portfolio_snapshot_json": "TEXT DEFAULT '{}'",
            "portfolio_last_scraped_at": "DATETIME",
        },
    )
    await _ensure_columns(
        db,
        "company_portals",
        {
            "favorite": "INTEGER DEFAULT 0",
            "notes": "TEXT DEFAULT ''",
            "tags_json": "TEXT DEFAULT '[]'",
            "cadence": "TEXT DEFAULT 'weekly'",
            "next_scan_at": "DATETIME",
            "last_delta_json": "TEXT DEFAULT '{}'",
        },
    )


async def _ensure_columns(db, table_name: str, columns: dict[str, str]):
    cursor = await db.execute(f"PRAGMA table_info({table_name})")
    rows = await cursor.fetchall()
    existing = {row[1] for row in rows}
    for column_name, definition in columns.items():
        if column_name in existing:
            continue
        await db.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

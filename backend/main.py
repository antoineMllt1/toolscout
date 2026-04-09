import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncIterator, Optional

# Fix Playwright sync_api in asyncio thread pool on Windows:
# SelectorEventLoop (used in threads) doesn't support subprocess on Windows.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import aiosqlite
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from database import init_db, get_db, DB_PATH
from models import SearchCreate
from auth import hash_password, verify_password, create_token, decode_token
from cookie_manager import load_cookies_from_db, cookie_refresh_loop
from scrapers.wttj import WTTJScraper
from scrapers.indeed import IndeedScraper
from scrapers.jobteaser import JobteaserScraper
from scrapers.linkedin import LinkedInScraper

# ── Live cookie store — populated from DB at startup, auto-refreshed every 6h ─
COOKIES: dict[str, dict] = {}

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Load persisted cookies from DB
    db_cookies = await load_cookies_from_db()
    COOKIES.update(db_cookies)
    # Start background cookie refresh loop (harvests fresh CF cookies every 6h)
    asyncio.create_task(cookie_refresh_loop(COOKIES))
    yield


app = FastAPI(title="ToolScout API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve React build assets
_assets_dir = os.path.join(FRONTEND_DIR, "assets")
if os.path.exists(_assets_dir):
    app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")


# ── Auth models ─────────────────────────────────────────────────────────────
class RegisterBody(BaseModel):
    email: str
    password: str
    name: str = ""

class LoginBody(BaseModel):
    email: str
    password: str

class ApplicationBody(BaseModel):
    job_url: str
    job_title: str
    company_name: str = ""
    source: str = ""
    location: str = ""
    contract_type: str = ""
    tool_context: list = []
    status: str = "saved"
    notes: str = ""

class ApplicationUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    applied_at: Optional[str] = None


# ── Auth dependency ───────────────────────────────────────────────────────────
async def get_current_user(authorization: str = Header(default="")):
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(401, "Not authenticated")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(401, "Invalid or expired token")
    return {"id": int(payload["sub"]), "email": payload["email"]}


# ── Auth endpoints ────────────────────────────────────────────────────────────
@app.post("/api/auth/register")
async def register(body: RegisterBody):
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    hashed = hash_password(body.password)
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "INSERT INTO users (email, password_hash, name) VALUES (?, ?, ?)",
                (body.email.lower().strip(), hashed, body.name.strip()),
            )
            await db.commit()
            user_id = cur.lastrowid
    except Exception:
        raise HTTPException(409, "Email already registered")
    token = create_token(user_id, body.email.lower().strip())
    return {"token": token, "user": {"id": user_id, "email": body.email, "name": body.name}}


@app.post("/api/auth/login")
async def login(body: LoginBody):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM users WHERE email = ?", (body.email.lower().strip(),)
        )
        user = await cur.fetchone()
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    token = create_token(user["id"], user["email"])
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user["name"]}}


@app.get("/api/auth/me")
async def me(current_user=Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, email, name, created_at FROM users WHERE id = ?",
            (current_user["id"],)
        )
        user = await cur.fetchone()
    if not user:
        raise HTTPException(404, "User not found")
    return dict(user)


# ── Application (postulation) endpoints ──────────────────────────────────────
@app.get("/api/applications")
async def get_applications(current_user=Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM applications WHERE user_id = ? ORDER BY updated_at DESC",
            (current_user["id"],)
        )
        rows = await cur.fetchall()
    return [_parse_app(dict(r)) for r in rows]


@app.post("/api/applications")
async def save_application(body: ApplicationBody, current_user=Depends(get_current_user)):
    uid = current_user["id"]
    ctx = json.dumps(body.tool_context, ensure_ascii=False)
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """INSERT INTO applications
                   (user_id, job_url, job_title, company_name, source, location,
                    contract_type, tool_context, status, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (uid, body.job_url, body.job_title, body.company_name,
                 body.source, body.location, body.contract_type, ctx,
                 body.status, body.notes),
            )
            await db.commit()
            app_id = cur.lastrowid
            cur2 = await db.execute("SELECT * FROM applications WHERE id = ?", (app_id,))
            row = await cur2.fetchone()
    except Exception:
        # Already exists — return existing
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM applications WHERE user_id = ? AND job_url = ?",
                (uid, body.job_url)
            )
            row = await cur.fetchone()
        if not row:
            raise HTTPException(500, "Failed to save application")
    return _parse_app(dict(row))


@app.put("/api/applications/{app_id}")
async def update_application(app_id: int, body: ApplicationUpdate, current_user=Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM applications WHERE id = ? AND user_id = ?",
            (app_id, current_user["id"])
        )
        existing = await cur.fetchone()
        if not existing:
            raise HTTPException(404, "Application not found")

        updates = {"updated_at": datetime.utcnow().isoformat()}
        if body.status is not None:
            updates["status"] = body.status
            if body.status == "applied" and not existing["applied_at"]:
                updates["applied_at"] = datetime.utcnow().isoformat()
        if body.notes is not None:
            updates["notes"] = body.notes
        if body.applied_at is not None:
            updates["applied_at"] = body.applied_at

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [app_id]
        await db.execute(f"UPDATE applications SET {set_clause} WHERE id = ?", values)
        await db.commit()

        cur2 = await db.execute("SELECT * FROM applications WHERE id = ?", (app_id,))
        row = await cur2.fetchone()
    return _parse_app(dict(row))


@app.delete("/api/applications/{app_id}")
async def delete_application(app_id: int, current_user=Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM applications WHERE id = ? AND user_id = ?",
            (app_id, current_user["id"])
        )
        await db.commit()
    return {"deleted": app_id}


@app.get("/api/applications/stats")
async def application_stats(current_user=Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT status, COUNT(*) as count
               FROM applications WHERE user_id = ?
               GROUP BY status""",
            (current_user["id"],)
        )
        rows = await cur.fetchall()
    return {r["status"]: r["count"] for r in rows}


def _parse_app(r: dict) -> dict:
    try:
        r["tool_context"] = json.loads(r.get("tool_context") or "[]")
    except Exception:
        r["tool_context"] = []
    return r


# ── Search ──────────────────────────────────────────────────────────────────
@app.post("/api/search")
async def create_search(body: SearchCreate):
    tool = body.tool_name.strip()
    if not tool:
        raise HTTPException(400, "tool_name required")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "INSERT INTO searches (tool_name, status) VALUES (?, 'pending')",
            (tool,),
        )
        await db.commit()
        search_id = cursor.lastrowid

    # Launch scraping in background
    asyncio.create_task(_run_scrapers(search_id, tool))
    return {"search_id": search_id, "tool_name": tool, "status": "pending"}


@app.get("/api/search/{search_id}/stream")
async def stream_results(search_id: int):
    """SSE stream — send new results as they arrive."""
    return StreamingResponse(
        _sse_generator(search_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/search/{search_id}/results")
async def get_results(search_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM searches WHERE id = ?", (search_id,))
        search = await cur.fetchone()
        if not search:
            raise HTTPException(404, "Search not found")

        cur2 = await db.execute(
            "SELECT * FROM results WHERE search_id = ? ORDER BY scraped_at DESC",
            (search_id,),
        )
        rows = await cur2.fetchall()

    return {
        "search": dict(search),
        "results": [dict(r) for r in rows],
    }


@app.get("/api/search/{search_id}")
async def get_search(search_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM searches WHERE id = ?", (search_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "Search not found")
        return dict(row)


# ── History ──────────────────────────────────────────────────────────────────
@app.get("/api/history")
async def get_history():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM searches ORDER BY created_at DESC LIMIT 100"
        )
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@app.delete("/api/history/{search_id}")
async def delete_search(search_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM results WHERE search_id = ?", (search_id,))
        await db.execute("DELETE FROM searches WHERE id = ?", (search_id,))
        await db.commit()
    return {"deleted": search_id}


# ── Popular tools ─────────────────────────────────────────────────────────
@app.get("/api/tools/popular")
async def popular_tools():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT tool_name, COUNT(*) as searches, SUM(total_results) as results
               FROM searches WHERE status = 'completed'
               GROUP BY LOWER(tool_name)
               ORDER BY searches DESC LIMIT 20"""
        )
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


# ── Cookies config ───────────────────────────────────────────────────────
@app.post("/api/config/cookies")
async def set_cookies(body: dict):
    """
    Save cookies per source so scrapers can bypass login walls.
    Body: { "source": "indeed", "cookies": {"session_id": "...", ...} }
    """
    source = body.get("source", "").lower()
    cookies = body.get("cookies", {})
    if source and cookies:
        COOKIES[source] = cookies
    return {"saved": source, "keys": list(cookies.keys())}


@app.get("/api/config/cookies")
async def get_cookie_sources():
    return {"sources_configured": list(COOKIES.keys())}


@app.get("/api/cookies/status")
async def cookies_status():
    """Cookie freshness info for the admin UI."""
    from cookie_manager import ensure_cookies_table
    await ensure_cookies_table()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT source, harvested_at FROM cf_cookies")
        rows = await cur.fetchall()
    status = {}
    for row in rows:
        harvested = row["harvested_at"]
        try:
            age_h = (datetime.utcnow() - datetime.fromisoformat(harvested)).total_seconds() / 3600
        except Exception:
            age_h = 999
        status[row["source"]] = {
            "harvested_at": harvested,
            "age_hours": round(age_h, 1),
            "fresh": age_h < 12,
            "in_memory": row["source"] in COOKIES,
        }
    return status


@app.post("/api/cookies/refresh")
async def trigger_cookie_refresh(current_user=Depends(get_current_user)):
    """Manually trigger a cookie harvest (admin only for now)."""
    from cookie_manager import harvest_source
    asyncio.create_task(_refresh_all_cookies())
    return {"status": "refresh_started"}


async def _refresh_all_cookies():
    from cookie_manager import harvest_source, HARVEST_TARGETS
    for source in HARVEST_TARGETS:
        await harvest_source(source, COOKIES)


# ── Stats ──────────────────────────────────────────────────────────────────
@app.get("/api/stats")
async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT COUNT(*) as total FROM searches")
        total_searches = (await cur.fetchone())["total"]
        cur2 = await db.execute("SELECT COUNT(*) as total FROM results")
        total_results = (await cur2.fetchone())["total"]
        cur3 = await db.execute(
            "SELECT COUNT(DISTINCT company_name) as total FROM results WHERE company_name != ''"
        )
        total_companies = (await cur3.fetchone())["total"]
    return {
        "total_searches": total_searches,
        "total_results": total_results,
        "total_companies": total_companies,
    }


# ── Background scraping logic ─────────────────────────────────────────────
async def _run_scrapers(search_id: int, tool: str):
    scrapers = [
        ("wttj",      WTTJScraper(COOKIES.get("wttj"))),
        ("linkedin",  LinkedInScraper()),
        ("indeed",    IndeedScraper(COOKIES.get("indeed"))),
        ("jobteaser", JobteaserScraper(COOKIES.get("jobteaser"))),
    ]

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE searches SET status = 'running' WHERE id = ?", (search_id,)
        )
        await db.commit()

    total = 0
    sources_done = []

    for source_name, scraper in scrapers:
        try:
            # Run blocking scraper in thread pool
            results = await asyncio.get_event_loop().run_in_executor(
                None, lambda s=scraper, t=tool: list(s.search(t, max_results=30))
            )

            async with aiosqlite.connect(DB_PATH) as db:
                for r in results:
                    await db.execute(
                        """INSERT INTO results
                           (search_id, company_name, job_title, job_url,
                            location, contract_type, tool_context, source)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            search_id,
                            r.company_name,
                            r.job_title,
                            r.job_url,
                            r.location,
                            r.contract_type,
                            json.dumps(r.tool_context, ensure_ascii=False),
                            r.source,
                        ),
                    )
                total += len(results)
                sources_done.append(source_name)
                await db.execute(
                    "UPDATE searches SET total_results = ?, sources_done = ? WHERE id = ?",
                    (total, ",".join(sources_done), search_id),
                )
                await db.commit()
        except Exception as e:
            print(f"[{source_name}] scraper failed: {e}")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE searches
               SET status = 'completed', total_results = ?, completed_at = ?
               WHERE id = ?""",
            (total, datetime.utcnow().isoformat(), search_id),
        )
        await db.commit()


async def _sse_generator(search_id: int) -> AsyncIterator[str]:
    """
    Poll DB for new results and push via SSE.
    Sends: { type: 'result', data: {...} } or { type: 'done', ... }
    """
    last_id = 0
    sent_ids: set[int] = set()
    max_wait = 180  # seconds timeout
    elapsed = 0
    interval = 1.5

    while elapsed < max_wait:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row

            # New results
            cur = await db.execute(
                "SELECT * FROM results WHERE search_id = ? AND id > ? ORDER BY id",
                (search_id, last_id),
            )
            rows = await cur.fetchall()

            for row in rows:
                r = dict(row)
                last_id = r["id"]
                # Parse JSON tool_context
                try:
                    r["tool_context"] = json.loads(r["tool_context"] or "[]")
                except Exception:
                    r["tool_context"] = []
                yield f"data: {json.dumps({'type': 'result', 'data': r})}\n\n"

            # Check search status
            cur2 = await db.execute(
                "SELECT status, total_results, sources_done FROM searches WHERE id = ?",
                (search_id,),
            )
            search = await cur2.fetchone()
            if search:
                yield f"data: {json.dumps({'type': 'status', 'status': search['status'], 'total': search['total_results'], 'sources_done': search['sources_done']})}\n\n"

                if search["status"] == "completed":
                    yield f"data: {json.dumps({'type': 'done', 'total': search['total_results']})}\n\n"
                    return

        await asyncio.sleep(interval)
        elapsed += interval


# ── Frontend SPA catch-all (MUST be last — catches all unmatched GET routes) ─
@app.get("/")
@app.get("/{full_path:path}")
def serve_index(full_path: str = ""):
    index = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"status": "ToolScout API running — build the React frontend first."}

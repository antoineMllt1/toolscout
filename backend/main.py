import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from time import perf_counter
from typing import AsyncIterator, Optional

# Fix Playwright sync_api in asyncio thread pool on Windows:
# SelectorEventLoop (used in threads) doesn't support subprocess on Windows.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import aiosqlite
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv

import logging

load_dotenv()

from database import init_db, get_db, DB_PATH
from models import SearchCreate
from anthropic_client import AnthropicConfigError, AnthropicResponseError, generate_cv_copy
from auth import hash_password, verify_password, create_token, decode_token
from cookie_manager import load_cookies_from_db, cookie_refresh_loop
from cv_engine import (
    CV_TEMPLATE_LIBRARY,
    build_target_snapshot,
    build_targeted_cv_draft,
    default_cv_profile,
    dumps_json,
    sanitize_cv_profile,
)
from normalization import build_normalized_result, match_role_targets
from scrapers.wttj import WTTJScraper
from scrapers.indeed import IndeedScraper
from scrapers.jobteaser import JobteaserScraper
from scrapers.linkedin import LinkedInScraper

logger = logging.getLogger("toolscout.app")
ACTIVE_WATCHLIST_RUNS: set[int] = set()
WATCHLIST_CADENCES = {
    "daily": timedelta(days=1),
    "every_3_days": timedelta(days=3),
    "weekly": timedelta(days=7),
}
WATCHLIST_POLL_SECONDS = 60

# ── Live cookie store — populated from DB at startup, auto-refreshed every 6h ─
COOKIES: dict[str, dict] = {}

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup: initializing database at %s", DB_PATH)
    await init_db()
    db_cookies = await load_cookies_from_db()
    COOKIES.update(db_cookies)
    logger.info("startup: loaded %s cookie stores", len(db_cookies))
    asyncio.create_task(cookie_refresh_loop(COOKIES))
    logger.info("startup: cookie refresh loop started")
    asyncio.create_task(watchlist_scheduler_loop())
    logger.info("startup: watchlist scheduler loop started")
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


@app.get("/health")
async def healthcheck():
    return {"status": "ok"}


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


class WatchlistBody(BaseModel):
    name: str
    tools: list[str] = []
    roles: list[str] = []
    cadence: str = "daily"
    active: bool = True


class WatchlistUpdate(BaseModel):
    name: Optional[str] = None
    tools: Optional[list[str]] = None
    roles: Optional[list[str]] = None
    cadence: Optional[str] = None
    active: Optional[bool] = None


class CvProfileBody(BaseModel):
    title: str = "Main profile"
    full_name: str = ""
    headline: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    website: str = ""
    linkedin: str = ""
    github: str = ""
    summary: str = ""
    skills: list[str] = []
    languages: list[str] = []
    certifications: list[str] = []
    education: list[dict] = []
    experience: list[dict] = []
    projects: list[dict] = []


class CvDraftBody(BaseModel):
    template_slug: str = "moderncv-classic"
    application_id: Optional[int] = None
    result_id: Optional[int] = None


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
    r["normalized"] = build_normalized_result(r)
    return r


def _parse_result_row(r: dict) -> dict:
    try:
        r["tool_context"] = json.loads(r.get("tool_context") or "[]")
    except Exception:
        r["tool_context"] = []
    r["normalized"] = build_normalized_result(r)
    return r


def _sanitize_string_list(values: list[str] | None) -> list[str]:
    cleaned = []
    for value in values or []:
        text = (value or "").strip()
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def _serialize_watchlist_payload(name: str, tools: list[str], roles: list[str], cadence: str, active: bool):
    safe_cadence = cadence if cadence in WATCHLIST_CADENCES else "daily"
    now = datetime.utcnow()
    next_run = now if active else None
    return {
        "name": name.strip(),
        "tools_json": json.dumps(_sanitize_string_list(tools), ensure_ascii=False),
        "roles_json": json.dumps(_sanitize_string_list(roles), ensure_ascii=False),
        "cadence": safe_cadence,
        "active": 1 if active else 0,
        "next_run_at": now.isoformat() if next_run else None,
        "updated_at": now.isoformat(),
    }


def _parse_watchlist_row(row: dict, latest_run: dict | None = None) -> dict:
    try:
        tools = json.loads(row.get("tools_json") or "[]")
    except Exception:
        tools = []
    try:
        roles = json.loads(row.get("roles_json") or "[]")
    except Exception:
        roles = []
    payload = {
        "id": row["id"],
        "name": row["name"],
        "tools": tools,
        "roles": roles,
        "cadence": row["cadence"],
        "active": bool(row["active"]),
        "slack_enabled": bool(row.get("slack_enabled", 0)),
        "last_run_at": row.get("last_run_at"),
        "next_run_at": row.get("next_run_at"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }
    if latest_run:
        payload["latest_run"] = _parse_watchlist_run_row(latest_run)
    return payload


def _parse_watchlist_run_row(row: dict) -> dict:
    try:
        tools = json.loads(row.get("tools_json") or "[]")
    except Exception:
        tools = []
    try:
        roles = json.loads(row.get("roles_json") or "[]")
    except Exception:
        roles = []
    try:
        search_ids = json.loads(row.get("search_ids_json") or "[]")
    except Exception:
        search_ids = []
    return {
        "id": row["id"],
        "watchlist_id": row["watchlist_id"],
        "status": row["status"],
        "tools": tools,
        "roles": roles,
        "search_ids": search_ids,
        "matched_results": row.get("matched_results", 0),
        "total_results": row.get("total_results", 0),
        "started_at": row.get("started_at"),
        "completed_at": row.get("completed_at"),
        "error": row.get("error", ""),
    }


# ── Search ──────────────────────────────────────────────────────────────────
def _json_value(raw, fallback):
    try:
        return json.loads(raw) if raw else fallback
    except Exception:
        return fallback


def _parse_cv_profile_row(row: dict, user: dict | None = None) -> dict:
    if not row:
        return default_cv_profile(user)
    return {
        "id": row["id"],
        "title": row.get("title") or "Main profile",
        "full_name": row.get("full_name") or "",
        "headline": row.get("headline") or "",
        "email": row.get("email") or "",
        "phone": row.get("phone") or "",
        "location": row.get("location") or "",
        "website": row.get("website") or "",
        "linkedin": row.get("linkedin") or "",
        "github": row.get("github") or "",
        "summary": row.get("summary") or "",
        "skills": _json_value(row.get("skills_json"), []),
        "languages": _json_value(row.get("languages_json"), []),
        "certifications": _json_value(row.get("certifications_json"), []),
        "education": _json_value(row.get("education_json"), []),
        "experience": _json_value(row.get("experience_json"), []),
        "projects": _json_value(row.get("projects_json"), []),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _parse_cv_draft_row(row: dict) -> dict:
    return {
        "id": row["id"],
        "profile_id": row.get("profile_id"),
        "template_slug": row["template_slug"],
        "source_kind": row["source_kind"],
        "source_id": row.get("source_id"),
        "target_title": row.get("target_title") or "",
        "target_company": row.get("target_company") or "",
        "target_job_url": row.get("target_job_url") or "",
        "target_snapshot": _json_value(row.get("target_snapshot_json"), {}),
        "selected_payload": _json_value(row.get("selected_payload_json"), {}),
        "latex_source": row.get("latex_source") or "",
        "prompt_payload": _json_value(row.get("prompt_payload_json"), {}),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


async def _fetch_user_record(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT id, email, name FROM users WHERE id = ?", (user_id,))
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "User not found")
    return dict(row)


async def _fetch_cv_profile(user_id: int) -> tuple[dict | None, dict]:
    user = await _fetch_user_record(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM cv_profiles WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
    return (dict(row) if row else None, user)


async def _load_cv_target(body: CvDraftBody, user_id: int) -> tuple[str, dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if body.application_id is not None:
            cur = await db.execute(
                "SELECT * FROM applications WHERE id = ? AND user_id = ?",
                (body.application_id, user_id),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(404, "Application not found")
            return "application", _parse_app(dict(row))

        if body.result_id is not None:
            cur = await db.execute("SELECT * FROM results WHERE id = ?", (body.result_id,))
            row = await cur.fetchone()
            if not row:
                raise HTTPException(404, "Search result not found")
            return "result", _parse_result_row(dict(row))

    raise HTTPException(400, "application_id or result_id is required")


@app.post("/api/search")
async def create_search(body: SearchCreate):
    tool = body.tool_name.strip()
    if not tool:
        raise HTTPException(400, "tool_name required")

    search_id = await _create_search_record(tool)
    logger.info("search %s created for tool=%s", search_id, tool)
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
        "results": [_parse_result_row(dict(r)) for r in rows],
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


@app.get("/api/cv/templates")
async def cv_templates():
    return CV_TEMPLATE_LIBRARY


@app.get("/api/cv/profile")
async def get_cv_profile(current_user=Depends(get_current_user)):
    row, user = await _fetch_cv_profile(current_user["id"])
    return _parse_cv_profile_row(row, user)


@app.put("/api/cv/profile")
async def save_cv_profile(body: CvProfileBody, current_user=Depends(get_current_user)):
    payload = body.model_dump() if hasattr(body, "model_dump") else body.dict()
    _, user = await _fetch_cv_profile(current_user["id"])
    profile = sanitize_cv_profile(payload, user)
    now = datetime.utcnow().isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            """INSERT INTO cv_profiles
               (user_id, title, full_name, headline, email, phone, location, website, linkedin, github, summary,
                skills_json, languages_json, certifications_json, education_json, experience_json, projects_json,
                updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                 title = excluded.title,
                 full_name = excluded.full_name,
                 headline = excluded.headline,
                 email = excluded.email,
                 phone = excluded.phone,
                 location = excluded.location,
                 website = excluded.website,
                 linkedin = excluded.linkedin,
                 github = excluded.github,
                 summary = excluded.summary,
                 skills_json = excluded.skills_json,
                 languages_json = excluded.languages_json,
                 certifications_json = excluded.certifications_json,
                 education_json = excluded.education_json,
                 experience_json = excluded.experience_json,
                 projects_json = excluded.projects_json,
                 updated_at = excluded.updated_at""",
            (
                current_user["id"],
                profile["title"],
                profile["full_name"],
                profile["headline"],
                profile["email"],
                profile["phone"],
                profile["location"],
                profile["website"],
                profile["linkedin"],
                profile["github"],
                profile["summary"],
                dumps_json(profile["skills"]),
                dumps_json(profile["languages"]),
                dumps_json(profile["certifications"]),
                dumps_json(profile["education"]),
                dumps_json(profile["experience"]),
                dumps_json(profile["projects"]),
                now,
            ),
        )
        await db.commit()
        cur = await db.execute("SELECT * FROM cv_profiles WHERE user_id = ?", (current_user["id"],))
        row = await cur.fetchone()
    return _parse_cv_profile_row(dict(row), user)


@app.get("/api/cv/drafts")
async def list_cv_drafts(current_user=Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM cv_drafts WHERE user_id = ? ORDER BY created_at DESC LIMIT 30",
            (current_user["id"],),
        )
        rows = await cur.fetchall()
    return [_parse_cv_draft_row(dict(row)) for row in rows]


@app.get("/api/cv/drafts/{draft_id}")
async def get_cv_draft(draft_id: int, current_user=Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM cv_drafts WHERE id = ? AND user_id = ?",
            (draft_id, current_user["id"]),
        )
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "CV draft not found")
    return _parse_cv_draft_row(dict(row))


@app.post("/api/cv/drafts/{draft_id}/copywrite")
async def copywrite_cv_draft(draft_id: int, current_user=Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM cv_drafts WHERE id = ? AND user_id = ?",
            (draft_id, current_user["id"]),
        )
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "CV draft not found")

    draft = _parse_cv_draft_row(dict(row))
    try:
        suggestions = generate_cv_copy(draft["prompt_payload"])
    except AnthropicConfigError as error:
        raise HTTPException(400, str(error))
    except AnthropicResponseError as error:
        raise HTTPException(502, str(error))

    selected = draft["selected_payload"]
    allowed_experience_ids = {item.get("id") for item in selected.get("experience", [])}
    allowed_project_ids = {item.get("id") for item in selected.get("projects", [])}
    allowed_education_ids = {item.get("id") for item in selected.get("education", [])}
    allowed_skills = set(selected.get("skills", []))

    cleaned = {
        "headline": str(suggestions.get("headline", "")).strip()[:160],
        "summary": str(suggestions.get("summary", "")).strip()[:1200],
        "skills_priority": [
            skill for skill in suggestions.get("skills_priority", [])
            if isinstance(skill, str) and skill in allowed_skills
        ][:10],
        "experience_rewrites": [],
        "project_rewrites": [],
        "education_rewrites": [],
        "compliance_notes": [
            note.strip()[:220]
            for note in suggestions.get("compliance_notes", [])
            if isinstance(note, str) and note.strip()
        ][:8],
    }

    for item in suggestions.get("experience_rewrites", []):
        if not isinstance(item, dict) or item.get("id") not in allowed_experience_ids:
            continue
        bullets = [str(bullet).strip()[:220] for bullet in item.get("bullets", []) if str(bullet).strip()]
        cleaned["experience_rewrites"].append({"id": item["id"], "bullets": bullets[:4]})

    for item in suggestions.get("project_rewrites", []):
        if not isinstance(item, dict) or item.get("id") not in allowed_project_ids:
            continue
        bullets = [str(bullet).strip()[:220] for bullet in item.get("bullets", []) if str(bullet).strip()]
        cleaned["project_rewrites"].append({"id": item["id"], "bullets": bullets[:4]})

    for item in suggestions.get("education_rewrites", []):
        if not isinstance(item, dict) or item.get("id") not in allowed_education_ids:
            continue
        bullet = str(item.get("bullet", "")).strip()[:220]
        if bullet:
            cleaned["education_rewrites"].append({"id": item["id"], "bullet": bullet})

    return {
        "draft_id": draft_id,
        "model": os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-latest"),
        "suggestions": cleaned,
    }


@app.get("/api/cv/drafts/{draft_id}/tex")
async def download_cv_draft_tex(draft_id: int, current_user=Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM cv_drafts WHERE id = ? AND user_id = ?",
            (draft_id, current_user["id"]),
        )
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "CV draft not found")
    draft = _parse_cv_draft_row(dict(row))
    filename = f"toolscout-cv-{draft_id}.tex"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return PlainTextResponse(draft["latex_source"], headers=headers)


@app.post("/api/cv/drafts/generate")
async def generate_cv_draft(body: CvDraftBody, current_user=Depends(get_current_user)):
    profile_row, user = await _fetch_cv_profile(current_user["id"])
    profile = _parse_cv_profile_row(profile_row, user)
    has_profile_data = any(
        [
            profile["summary"],
            profile["skills"],
            profile["experience"],
            profile["projects"],
            profile["education"],
        ]
    )
    if not has_profile_data:
        raise HTTPException(400, "Complete your CV profile before generating a draft")

    source_kind, source_record = await _load_cv_target(body, current_user["id"])
    target = build_target_snapshot(source_kind, source_record)
    draft_payload = build_targeted_cv_draft(profile, target, body.template_slug)
    now = datetime.utcnow().isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id FROM cv_profiles WHERE user_id = ?",
            (current_user["id"],),
        )
        profile_ref = await cur.fetchone()
        cursor = await db.execute(
            """INSERT INTO cv_drafts
               (user_id, profile_id, template_slug, source_kind, source_id,
                target_title, target_company, target_job_url,
                target_snapshot_json, selected_payload_json, latex_source, prompt_payload_json, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                current_user["id"],
                profile_ref["id"] if profile_ref else None,
                draft_payload["template"]["slug"],
                source_kind,
                source_record.get("id"),
                target["job_title"],
                target["company_name"],
                target["job_url"],
                dumps_json(target),
                dumps_json(draft_payload["selected_payload"]),
                draft_payload["latex_source"],
                dumps_json(draft_payload["prompt_payload"]),
                now,
            ),
        )
        await db.commit()
        draft_id = cursor.lastrowid
        row_cur = await db.execute("SELECT * FROM cv_drafts WHERE id = ?", (draft_id,))
        row = await row_cur.fetchone()
    return _parse_cv_draft_row(dict(row))


@app.get("/api/watchlists")
async def get_watchlists(current_user=Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM watchlists WHERE user_id = ? ORDER BY created_at DESC",
            (current_user["id"],),
        )
        rows = await cur.fetchall()

        items = []
        for row in rows:
            latest_cur = await db.execute(
                "SELECT * FROM watchlist_runs WHERE watchlist_id = ? ORDER BY started_at DESC LIMIT 1",
                (row["id"],),
            )
            latest_run = await latest_cur.fetchone()
            items.append(_parse_watchlist_row(dict(row), dict(latest_run) if latest_run else None))
    return items


@app.get("/api/watchlists/{watchlist_id}/runs")
async def get_watchlist_runs(watchlist_id: int, current_user=Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM watchlists WHERE id = ? AND user_id = ?",
            (watchlist_id, current_user["id"]),
        )
        watchlist = await cur.fetchone()
        if not watchlist:
            raise HTTPException(404, "Watchlist not found")

        runs_cur = await db.execute(
            "SELECT * FROM watchlist_runs WHERE watchlist_id = ? ORDER BY started_at DESC LIMIT 20",
            (watchlist_id,),
        )
        runs = await runs_cur.fetchall()
    return [_parse_watchlist_run_row(dict(run)) for run in runs]


@app.post("/api/watchlists")
async def create_watchlist(body: WatchlistBody, current_user=Depends(get_current_user)):
    payload = _serialize_watchlist_payload(body.name, body.tools, body.roles, body.cadence, body.active)
    if not payload["name"]:
        raise HTTPException(400, "watchlist name required")
    if not json.loads(payload["tools_json"]):
        raise HTTPException(400, "at least one tool is required")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """INSERT INTO watchlists
               (user_id, name, tools_json, roles_json, cadence, active, next_run_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                current_user["id"],
                payload["name"],
                payload["tools_json"],
                payload["roles_json"],
                payload["cadence"],
                payload["active"],
                payload["next_run_at"],
                payload["updated_at"],
            ),
        )
        await db.commit()
        watchlist_id = cur.lastrowid
        row_cur = await db.execute("SELECT * FROM watchlists WHERE id = ?", (watchlist_id,))
        row = await row_cur.fetchone()
    return _parse_watchlist_row(dict(row))


@app.put("/api/watchlists/{watchlist_id}")
async def update_watchlist(watchlist_id: int, body: WatchlistUpdate, current_user=Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM watchlists WHERE id = ? AND user_id = ?",
            (watchlist_id, current_user["id"]),
        )
        existing = await cur.fetchone()
        if not existing:
            raise HTTPException(404, "Watchlist not found")

        existing = dict(existing)
        payload = _serialize_watchlist_payload(
            body.name if body.name is not None else existing["name"],
            body.tools if body.tools is not None else json.loads(existing["tools_json"] or "[]"),
            body.roles if body.roles is not None else json.loads(existing["roles_json"] or "[]"),
            body.cadence if body.cadence is not None else existing["cadence"],
            body.active if body.active is not None else bool(existing["active"]),
        )
        if body.active is None:
            payload["next_run_at"] = existing["next_run_at"]
        await db.execute(
            """UPDATE watchlists
               SET name = ?, tools_json = ?, roles_json = ?, cadence = ?, active = ?, next_run_at = ?, updated_at = ?
               WHERE id = ?""",
            (
                payload["name"],
                payload["tools_json"],
                payload["roles_json"],
                payload["cadence"],
                payload["active"],
                payload["next_run_at"],
                payload["updated_at"],
                watchlist_id,
            ),
        )
        await db.commit()
        row_cur = await db.execute("SELECT * FROM watchlists WHERE id = ?", (watchlist_id,))
        row = await row_cur.fetchone()
    return _parse_watchlist_row(dict(row))


@app.post("/api/watchlists/{watchlist_id}/run")
async def run_watchlist_now(watchlist_id: int, current_user=Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM watchlists WHERE id = ? AND user_id = ?",
            (watchlist_id, current_user["id"]),
        )
        watchlist = await cur.fetchone()
        if not watchlist:
            raise HTTPException(404, "Watchlist not found")

        await db.execute(
            "UPDATE watchlists SET next_run_at = ?, updated_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), watchlist_id),
        )
        await db.commit()

    if watchlist_id not in ACTIVE_WATCHLIST_RUNS:
        ACTIVE_WATCHLIST_RUNS.add(watchlist_id)
        asyncio.create_task(_run_watchlist_by_id(watchlist_id))
    return {"status": "scheduled", "watchlist_id": watchlist_id}


@app.delete("/api/watchlists/{watchlist_id}")
async def delete_watchlist(watchlist_id: int, current_user=Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM watchlists WHERE id = ? AND user_id = ?",
            (watchlist_id, current_user["id"]),
        )
        await db.commit()
    ACTIVE_WATCHLIST_RUNS.discard(watchlist_id)
    return {"deleted": watchlist_id}


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


def _next_watchlist_run(now: datetime, cadence: str) -> str:
    delta = WATCHLIST_CADENCES.get(cadence, WATCHLIST_CADENCES["daily"])
    return (now + delta).isoformat()


async def watchlist_scheduler_loop():
    while True:
        try:
            now = datetime.utcnow().isoformat()
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                cur = await db.execute(
                    """SELECT * FROM watchlists
                       WHERE active = 1 AND (next_run_at IS NULL OR next_run_at <= ?)
                       ORDER BY next_run_at ASC, created_at ASC""",
                    (now,),
                )
                rows = await cur.fetchall()

            for row in rows:
                watchlist_id = row["id"]
                if watchlist_id in ACTIVE_WATCHLIST_RUNS:
                    continue
                ACTIVE_WATCHLIST_RUNS.add(watchlist_id)
                asyncio.create_task(_run_watchlist_by_id(watchlist_id))
        except Exception as e:
            logger.exception("watchlist scheduler crashed: %s", e)

        await asyncio.sleep(WATCHLIST_POLL_SECONDS)


async def _run_watchlist_by_id(watchlist_id: int):
    run_id = None
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM watchlists WHERE id = ?", (watchlist_id,))
            watchlist = await cur.fetchone()
            if not watchlist:
                return
            watchlist = dict(watchlist)
            if not watchlist["active"]:
                return

            now = datetime.utcnow()
            await db.execute(
                "UPDATE watchlists SET last_run_at = ?, next_run_at = ?, updated_at = ? WHERE id = ?",
                (
                    now.isoformat(),
                    _next_watchlist_run(now, watchlist["cadence"]),
                    now.isoformat(),
                    watchlist_id,
                ),
            )
            cur = await db.execute(
                """INSERT INTO watchlist_runs
                   (watchlist_id, status, tools_json, roles_json)
                   VALUES (?, 'running', ?, ?)""",
                (watchlist_id, watchlist["tools_json"], watchlist["roles_json"]),
            )
            await db.commit()
            run_id = cur.lastrowid

        tools = _sanitize_string_list(json.loads(watchlist["tools_json"] or "[]"))
        roles = _sanitize_string_list(json.loads(watchlist["roles_json"] or "[]"))
        search_ids: list[int] = []
        total_results = 0
        matched_results = 0

        for tool in tools:
            search_id = await _create_search_record(tool)
            search_ids.append(search_id)
            logger.info("watchlist %s started tool=%s search=%s", watchlist_id, tool, search_id)
            await _run_scrapers(search_id, tool)
            total_results += await _count_search_results(search_id)
            matched_results += await _count_search_role_matches(search_id, roles)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """UPDATE watchlist_runs
                   SET status = 'completed', search_ids_json = ?, matched_results = ?, total_results = ?, completed_at = ?
                   WHERE id = ?""",
                (
                    json.dumps(search_ids, ensure_ascii=False),
                    matched_results,
                    total_results,
                    datetime.utcnow().isoformat(),
                    run_id,
                ),
            )
            await db.commit()
        logger.info(
            "watchlist %s completed tools=%s total=%s matched=%s",
            watchlist_id,
            ",".join(tools),
            total_results,
            matched_results,
        )
    except Exception as e:
        logger.exception("watchlist %s failed: %s", watchlist_id, e)
        if run_id is not None:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    """UPDATE watchlist_runs
                       SET status = 'failed', error = ?, completed_at = ?
                       WHERE id = ?""",
                    (str(e), datetime.utcnow().isoformat(), run_id),
                )
                await db.commit()
    finally:
        ACTIVE_WATCHLIST_RUNS.discard(watchlist_id)


async def _create_search_record(tool: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO searches (tool_name, status) VALUES (?, 'pending')",
            (tool,),
        )
        await db.commit()
        return cursor.lastrowid


async def _count_search_results(search_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT COUNT(*) AS total FROM results WHERE search_id = ?", (search_id,))
        row = await cur.fetchone()
    return row["total"] if row else 0


async def _count_search_role_matches(search_id: int, roles: list[str]) -> int:
    if not roles:
        return await _count_search_results(search_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT job_title FROM results WHERE search_id = ?", (search_id,))
        rows = await cur.fetchall()
    return sum(1 for row in rows if match_role_targets(row["job_title"] or "", roles))


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
        ("wttj",      WTTJScraper(COOKIES.get("wttj")), 30),
        ("linkedin",  LinkedInScraper(), 15),
        ("indeed",    IndeedScraper(COOKIES.get("indeed")), 5),
        ("jobteaser", JobteaserScraper(COOKIES.get("jobteaser")), 4),
    ]

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE searches SET status = 'running' WHERE id = ?", (search_id,)
        )
        await db.commit()

    total = 0
    sources_done = []
    source_names = [source_name for source_name, _, _ in scrapers]
    total_sources = len(scrapers)
    logger.info(
        "search %s started tool=%s mode=parallel total_sources=%s sources=%s",
        search_id,
        tool,
        total_sources,
        ",".join(source_names),
    )

    tasks = [
        asyncio.create_task(_execute_scraper(search_id, source_name, scraper, tool, limit))
        for source_name, scraper, limit in scrapers
    ]

    for task in asyncio.as_completed(tasks):
        outcome = await task
        source_name = outcome["source_name"]
        results = outcome["results"]
        duration = outcome["duration"]
        error = outcome["error"]

        total += len(results)
        sources_done.append(source_name)
        await _persist_scraper_results(search_id, results, total, sources_done)

        status = "failed" if error else ("completed-zero" if not results else "completed")
        logger.info(
            "search %s source=%s %s results=%s total=%s finished=%s/%s duration=%.1fs",
            search_id,
            source_name,
            status,
            len(results),
            total,
            len(sources_done),
            total_sources,
            duration,
        )
        running_sources = ",".join(name for name in source_names if name not in sources_done) or "-"
        logger.info(
            "search %s progress done=%s/%s running=%s total=%s",
            search_id,
            len(sources_done),
            total_sources,
            running_sources,
            total,
        )

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE searches
               SET status = 'completed', total_results = ?, completed_at = ?
               WHERE id = ?""",
            (total, datetime.utcnow().isoformat(), search_id),
        )
        await db.commit()
    logger.info("search %s completed tool=%s total=%s", search_id, tool, total)


async def _execute_scraper(search_id: int, source_name: str, scraper, tool: str, limit: int) -> dict:
    budget = getattr(scraper, "MAX_DURATION", None)
    if budget is None:
        logger.info("search %s source=%s started limit=%s", search_id, source_name, limit)
    else:
        logger.info("search %s source=%s started limit=%s budget=%ss", search_id, source_name, limit, budget)
    started_at = perf_counter()
    loop = asyncio.get_running_loop()

    try:
        results = await loop.run_in_executor(
            None, lambda s=scraper, t=tool, m=limit: list(s.search(t, max_results=m))
        )
        return {
            "source_name": source_name,
            "results": results,
            "duration": perf_counter() - started_at,
            "error": None,
        }
    except Exception as e:
        logger.exception("search %s source=%s crashed: %s", search_id, source_name, e)
        return {
            "source_name": source_name,
            "results": [],
            "duration": perf_counter() - started_at,
            "error": str(e),
        }


async def _persist_scraper_results(search_id: int, results: list, total: int, sources_done: list[str]):
    async with aiosqlite.connect(DB_PATH) as db:
        if results:
            await db.executemany(
                """INSERT INTO results
                   (search_id, company_name, job_title, job_url,
                    location, contract_type, tool_context, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        search_id,
                        r.company_name,
                        r.job_title,
                        r.job_url,
                        r.location,
                        r.contract_type,
                        json.dumps(r.tool_context, ensure_ascii=False),
                        r.source,
                    )
                    for r in results
                ],
            )

        await db.execute(
            "UPDATE searches SET total_results = ?, sources_done = ? WHERE id = ?",
            (total, ",".join(sources_done), search_id),
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
                r = _parse_result_row(dict(row))
                last_id = r["id"]
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

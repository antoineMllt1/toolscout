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
import requests
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
from career_ops_fit import (
    build_company_research,
    diff_company_portal_results,
    evaluate_project_fit,
    evaluate_training_fit,
    scan_company_portal,
    story_bank_suggestions,
    tracker_status_label,
    tracker_status_meta,
)
from portfolio_ingest import (
    build_application_plan,
    PortfolioImportError,
    build_candidate_brief,
    build_interview_prep,
    build_student_guidance,
    merge_portfolio_into_profile,
    scrape_portfolio,
)
from scrapers.wttj import WTTJScraper
from scrapers.indeed import IndeedScraper
from scrapers.jobteaser import JobteaserScraper
from scrapers.linkedin import LinkedInScraper

logger = logging.getLogger("toolscout.app")
ACTIVE_WATCHLIST_RUNS: set[int] = set()
ACTIVE_COMPANY_PORTAL_SCANS: set[int] = set()
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
    asyncio.create_task(company_portal_scheduler_loop())
    logger.info("startup: company portal scheduler loop started")
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
    target_roles: list[str] = []
    cv_text: str = ""
    portfolio_url: str = ""
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


class PortfolioImportBody(BaseModel):
    portfolio_url: str


class StoryBankBody(BaseModel):
    title: str
    situation: str = ""
    task: str = ""
    action: str = ""
    result: str = ""
    reflection: str = ""
    tags: list[str] = []
    source_kind: str = ""
    source_id: Optional[int] = None


class QueueItemBody(BaseModel):
    label: str
    url: str = ""
    company_name: str = ""
    role_hint: str = ""
    status: str = "pending"
    notes: str = ""


class QueueItemUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


class CompanyPortalBody(BaseModel):
    company_name: str
    careers_url: str
    active: bool = True
    favorite: bool = False
    notes: str = ""
    tags: list[str] = []
    cadence: str = "weekly"


class CompanyPortalUpdate(BaseModel):
    company_name: Optional[str] = None
    careers_url: Optional[str] = None
    active: Optional[bool] = None
    favorite: Optional[bool] = None
    notes: Optional[str] = None
    tags: Optional[list[str]] = None
    cadence: Optional[str] = None


class CompanyResearchBody(BaseModel):
    company_name: str
    source_url: str
    role_title: str = ""


class CareerEvaluationBody(BaseModel):
    title: str
    input_text: str


class FavoriteJobBody(BaseModel):
    search_result_id: Optional[int] = None
    job_url: str
    job_title: str = ""
    company_name: str = ""
    source: str = ""
    location: str = ""
    contract_type: str = ""
    notes: str = ""
    payload: dict = {}


class FavoriteJobUpdate(BaseModel):
    notes: Optional[str] = None


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
    r["status_label"] = tracker_status_label(r.get("status") or "")
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


def _serialize_company_portal_payload(payload: dict, existing: dict | None = None) -> dict:
    now = datetime.utcnow()
    safe_cadence = sanitize_line(payload.get("cadence") or (existing or {}).get("cadence") or "weekly", 32)
    if safe_cadence not in WATCHLIST_CADENCES:
        safe_cadence = "weekly"

    active = bool(payload.get("active") if payload.get("active") is not None else bool((existing or {}).get("active", 1)))
    next_scan_at = (existing or {}).get("next_scan_at")
    cadence_changed = existing is not None and safe_cadence != existing.get("cadence")
    became_active = existing is not None and active and not bool(existing.get("active", 1))

    if active:
        if existing is None or cadence_changed or became_active or not next_scan_at:
            next_scan_at = now.isoformat()
    else:
        next_scan_at = None

    return {
        "company_name": sanitize_line(payload.get("company_name") if payload.get("company_name") is not None else (existing or {}).get("company_name"), 120),
        "careers_url": sanitize_line(payload.get("careers_url") if payload.get("careers_url") is not None else (existing or {}).get("careers_url"), 240),
        "active": 1 if active else 0,
        "favorite": 1 if bool(payload.get("favorite") if payload.get("favorite") is not None else bool((existing or {}).get("favorite", 0))) else 0,
        "notes": sanitize_block(payload.get("notes") if payload.get("notes") is not None else (existing or {}).get("notes"), 800),
        "tags_json": json.dumps(_sanitize_string_list(payload.get("tags") if payload.get("tags") is not None else _json_value((existing or {}).get("tags_json"), [])), ensure_ascii=False),
        "cadence": safe_cadence,
        "next_scan_at": next_scan_at,
        "updated_at": now.isoformat(),
    }


def _score_portal_seed_url(url: str) -> int:
    normalized = (url or "").lower()
    score = 0
    if any(token in normalized for token in ["/careers", "/career", "/jobs", "/join-us"]):
        score += 3
    if any(token in normalized for token in ["/job/", "/jobs/", "/positions/", "/opening/"]):
        score -= 1
    score -= normalized.count("/")
    return score


# ── Search ──────────────────────────────────────────────────────────────────
def _json_value(raw, fallback):
    try:
        return json.loads(raw) if raw else fallback
    except Exception:
        return fallback


def _parse_cv_profile_row(row: dict, user: dict | None = None) -> dict:
    if not row:
        profile = default_cv_profile(user)
        profile["candidate_brief"] = build_candidate_brief(profile)
        profile["student_guidance"] = build_student_guidance(profile)
        profile["interview_prep"] = build_interview_prep(profile)
        profile["application_plan"] = build_application_plan(profile)
        return profile
    profile = {
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
        "target_roles": _json_value(row.get("target_roles_json"), []),
        "cv_text": row.get("cv_text") or "",
        "portfolio_url": row.get("portfolio_url") or "",
        "portfolio_snapshot": _json_value(row.get("portfolio_snapshot_json"), {}),
        "portfolio_last_scraped_at": row.get("portfolio_last_scraped_at"),
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
    profile["candidate_brief"] = build_candidate_brief(profile)
    profile["student_guidance"] = build_student_guidance(profile)
    profile["interview_prep"] = build_interview_prep(profile)
    profile["application_plan"] = build_application_plan(profile)
    return profile


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


def _parse_story_bank_row(row: dict) -> dict:
    return {
        "id": row["id"],
        "title": row.get("title") or "",
        "situation": row.get("situation") or "",
        "task": row.get("task") or "",
        "action": row.get("action") or "",
        "result": row.get("result") or "",
        "reflection": row.get("reflection") or "",
        "tags": _json_value(row.get("tags_json"), []),
        "source_kind": row.get("source_kind") or "",
        "source_id": row.get("source_id"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _parse_queue_item_row(row: dict) -> dict:
    status = row.get("status") or "pending"
    return {
        "id": row["id"],
        "label": row.get("label") or "",
        "url": row.get("url") or "",
        "company_name": row.get("company_name") or "",
        "role_hint": row.get("role_hint") or "",
        "status": status,
        "status_label": tracker_status_label(status) if status in {"saved", "applied", "interview", "offer", "rejected"} else status.title(),
        "notes": row.get("notes") or "",
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _parse_company_portal_row(row: dict) -> dict:
    return {
        "id": row["id"],
        "company_name": row.get("company_name") or "",
        "careers_url": row.get("careers_url") or "",
        "active": bool(row.get("active", 1)),
        "favorite": bool(row.get("favorite", 0)),
        "notes": row.get("notes") or "",
        "tags": _json_value(row.get("tags_json"), []),
        "cadence": row.get("cadence") or "weekly",
        "last_scan_at": row.get("last_scan_at"),
        "next_scan_at": row.get("next_scan_at"),
        "last_result": _json_value(row.get("last_result_json"), {}),
        "last_delta": _json_value(row.get("last_delta_json"), {}),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _parse_company_portal_run_row(row: dict) -> dict:
    return {
        "id": row["id"],
        "portal_id": row.get("portal_id"),
        "company_name": row.get("company_name") or "",
        "status": row.get("status") or "running",
        "jobs_found": row.get("jobs_found", 0),
        "new_jobs": row.get("new_jobs", 0),
        "removed_jobs": row.get("removed_jobs", 0),
        "summary": _json_value(row.get("summary_json"), {}),
        "started_at": row.get("started_at"),
        "completed_at": row.get("completed_at"),
        "error": row.get("error") or "",
    }


def _parse_company_research_row(row: dict) -> dict:
    return {
        "id": row["id"],
        "company_name": row.get("company_name") or "",
        "role_title": row.get("role_title") or "",
        "source_url": row.get("source_url") or "",
        "summary": row.get("summary") or "",
        "culture_signals": _json_value(row.get("culture_json"), []),
        "product_signals": _json_value(row.get("product_json"), []),
        "risks": _json_value(row.get("risks_json"), []),
        "headings": _json_value(row.get("headings_json"), []),
        "created_at": row.get("created_at"),
    }


def _parse_career_evaluation_row(row: dict) -> dict:
    return {
        "id": row["id"],
        "kind": row.get("kind") or "",
        "title": row.get("title") or "",
        "input_text": row.get("input_text") or "",
        "output": _json_value(row.get("output_json"), {}),
        "created_at": row.get("created_at"),
    }


def _parse_favorite_job_row(row: dict) -> dict:
    return {
        "id": row["id"],
        "search_result_id": row.get("search_result_id"),
        "job_url": row.get("job_url") or "",
        "job_title": row.get("job_title") or "",
        "company_name": row.get("company_name") or "",
        "source": row.get("source") or "",
        "location": row.get("location") or "",
        "contract_type": row.get("contract_type") or "",
        "notes": row.get("notes") or "",
        "payload": _json_value(row.get("payload_json"), {}),
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


async def _upsert_cv_profile(
    user_id: int,
    user: dict,
    payload: dict,
    existing_row: dict | None = None,
    portfolio_snapshot: dict | None = None,
    portfolio_last_scraped_at: str | None = None,
):
    profile = sanitize_cv_profile(payload, user)
    existing_snapshot = _json_value((existing_row or {}).get("portfolio_snapshot_json"), {})
    snapshot = portfolio_snapshot if portfolio_snapshot is not None else existing_snapshot
    existing_scraped_at = (existing_row or {}).get("portfolio_last_scraped_at")
    scraped_at = portfolio_last_scraped_at if portfolio_last_scraped_at is not None else existing_scraped_at
    now = datetime.utcnow().isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            """INSERT INTO cv_profiles
               (user_id, title, full_name, headline, email, phone, location, website, linkedin, github,
                target_roles_json, cv_text, portfolio_url, portfolio_snapshot_json, portfolio_last_scraped_at,
                summary, skills_json, languages_json, certifications_json, education_json, experience_json,
                projects_json, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                 target_roles_json = excluded.target_roles_json,
                 cv_text = excluded.cv_text,
                 portfolio_url = excluded.portfolio_url,
                 portfolio_snapshot_json = excluded.portfolio_snapshot_json,
                 portfolio_last_scraped_at = excluded.portfolio_last_scraped_at,
                 summary = excluded.summary,
                 skills_json = excluded.skills_json,
                 languages_json = excluded.languages_json,
                 certifications_json = excluded.certifications_json,
                 education_json = excluded.education_json,
                 experience_json = excluded.experience_json,
                 projects_json = excluded.projects_json,
                 updated_at = excluded.updated_at""",
            (
                user_id,
                profile["title"],
                profile["full_name"],
                profile["headline"],
                profile["email"],
                profile["phone"],
                profile["location"],
                profile["website"],
                profile["linkedin"],
                profile["github"],
                dumps_json(profile["target_roles"]),
                profile["cv_text"],
                profile["portfolio_url"],
                dumps_json(snapshot),
                scraped_at,
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
        cur = await db.execute("SELECT * FROM cv_profiles WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
    return dict(row) if row else None


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


async def _run_company_portal_scan_by_id(portal_id: int) -> dict | None:
    run_id = None
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM company_portals WHERE id = ?", (portal_id,))
            row = await cur.fetchone()
            if not row:
                return None
            portal = dict(row)

            run_cur = await db.execute(
                """INSERT INTO company_portal_runs (portal_id, status)
                   VALUES (?, 'running')""",
                (portal_id,),
            )
            await db.commit()
            run_id = run_cur.lastrowid

        previous_result = _json_value(portal.get("last_result_json"), {})
        result = scan_company_portal(portal["company_name"], portal["careers_url"])
        delta = diff_company_portal_results(previous_result, result)
        now = datetime.utcnow()
        next_scan_at = _next_watchlist_run(now, portal.get("cadence") or "weekly") if portal.get("active") else None

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            await db.execute(
                """UPDATE company_portals
                   SET last_scan_at = ?, next_scan_at = ?, last_result_json = ?, last_delta_json = ?, updated_at = ?
                   WHERE id = ?""",
                (
                    result["scanned_at"],
                    next_scan_at,
                    dumps_json(result),
                    dumps_json(delta),
                    now.isoformat(),
                    portal_id,
                ),
            )
            if run_id is not None:
                await db.execute(
                    """UPDATE company_portal_runs
                       SET status = 'completed', jobs_found = ?, new_jobs = ?, removed_jobs = ?,
                           summary_json = ?, completed_at = ?
                       WHERE id = ?""",
                    (
                        delta["jobs_found_count"],
                        delta["new_jobs_count"],
                        delta["removed_jobs_count"],
                        dumps_json({"result": result, "delta": delta}),
                        now.isoformat(),
                        run_id,
                    ),
                )
            await db.commit()
            cur = await db.execute("SELECT * FROM company_portals WHERE id = ?", (portal_id,))
            updated = await cur.fetchone()
        return _parse_company_portal_row(dict(updated)) if updated else None
    except Exception as error:
        if run_id is not None:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    """UPDATE company_portal_runs
                       SET status = 'failed', error = ?, completed_at = ?
                       WHERE id = ?""",
                    (str(error), datetime.utcnow().isoformat(), run_id),
                )
                await db.commit()
        raise
    finally:
        ACTIVE_COMPANY_PORTAL_SCANS.discard(portal_id)


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
    existing_row, user = await _fetch_cv_profile(current_user["id"])
    row = await _upsert_cv_profile(
        current_user["id"],
        user,
        payload,
        existing_row=existing_row,
    )
    return _parse_cv_profile_row(dict(row), user)


@app.post("/api/cv/portfolio/import")
async def import_cv_portfolio(body: PortfolioImportBody, current_user=Depends(get_current_user)):
    existing_row, user = await _fetch_cv_profile(current_user["id"])
    current_profile = _parse_cv_profile_row(existing_row, user)
    try:
        snapshot = scrape_portfolio(body.portfolio_url)
    except PortfolioImportError as error:
        raise HTTPException(400, str(error))
    except requests.RequestException as error:
        raise HTTPException(502, f"Portfolio fetch failed: {error}")

    merged_profile = merge_portfolio_into_profile(current_profile, snapshot)
    row = await _upsert_cv_profile(
        current_user["id"],
        user,
        merged_profile,
        existing_row=existing_row,
        portfolio_snapshot=snapshot,
        portfolio_last_scraped_at=snapshot.get("captured_at"),
    )
    profile = _parse_cv_profile_row(row, user)
    return {
        "profile": profile,
        "snapshot": snapshot,
        "imported": {
            "portfolio_url": snapshot.get("final_url") or body.portfolio_url,
            "projects_found": len(snapshot.get("projects") or []),
            "skills_found": len(snapshot.get("skills") or []),
        },
    }


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


@app.get("/api/tracker/statuses")
async def get_tracker_statuses():
    return tracker_status_meta()


@app.get("/api/story-bank")
async def list_story_bank(current_user=Depends(get_current_user)):
    profile_row, user = await _fetch_cv_profile(current_user["id"])
    profile = _parse_cv_profile_row(profile_row, user)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM story_bank_entries WHERE user_id = ? ORDER BY updated_at DESC, created_at DESC",
            (current_user["id"],),
        )
        rows = await cur.fetchall()
    return {
        "items": [_parse_story_bank_row(dict(row)) for row in rows],
        "suggestions": story_bank_suggestions(profile),
    }


@app.post("/api/story-bank")
async def create_story_bank_item(body: StoryBankBody, current_user=Depends(get_current_user)):
    payload = body.model_dump() if hasattr(body, "model_dump") else body.dict()
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """INSERT INTO story_bank_entries
               (user_id, title, situation, task, action, result, reflection, tags_json, source_kind, source_id, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                current_user["id"],
                sanitize_line(payload.get("title"), 140),
                sanitize_block(payload.get("situation"), 1200),
                sanitize_block(payload.get("task"), 700),
                sanitize_block(payload.get("action"), 1200),
                sanitize_block(payload.get("result"), 900),
                sanitize_block(payload.get("reflection"), 900),
                dumps_json(sanitize_string_list(payload.get("tags"), max_items=8, max_length=50)),
                sanitize_line(payload.get("source_kind"), 40),
                payload.get("source_id"),
                now,
            ),
        )
        await db.commit()
        cur = await db.execute("SELECT * FROM story_bank_entries WHERE id = ?", (cursor.lastrowid,))
        row = await cur.fetchone()
    return _parse_story_bank_row(dict(row))


@app.put("/api/story-bank/{item_id}")
async def update_story_bank_item(item_id: int, body: StoryBankBody, current_user=Depends(get_current_user)):
    payload = body.model_dump() if hasattr(body, "model_dump") else body.dict()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            """UPDATE story_bank_entries
               SET title = ?, situation = ?, task = ?, action = ?, result = ?, reflection = ?, tags_json = ?,
                   source_kind = ?, source_id = ?, updated_at = ?
               WHERE id = ? AND user_id = ?""",
            (
                sanitize_line(payload.get("title"), 140),
                sanitize_block(payload.get("situation"), 1200),
                sanitize_block(payload.get("task"), 700),
                sanitize_block(payload.get("action"), 1200),
                sanitize_block(payload.get("result"), 900),
                sanitize_block(payload.get("reflection"), 900),
                dumps_json(sanitize_string_list(payload.get("tags"), max_items=8, max_length=50)),
                sanitize_line(payload.get("source_kind"), 40),
                payload.get("source_id"),
                datetime.utcnow().isoformat(),
                item_id,
                current_user["id"],
            ),
        )
        await db.commit()
        cur = await db.execute("SELECT * FROM story_bank_entries WHERE id = ? AND user_id = ?", (item_id, current_user["id"]))
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Story bank item not found")
    return _parse_story_bank_row(dict(row))


@app.delete("/api/story-bank/{item_id}")
async def delete_story_bank_item(item_id: int, current_user=Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM story_bank_entries WHERE id = ? AND user_id = ?", (item_id, current_user["id"]))
        await db.commit()
    return {"deleted": item_id}


@app.get("/api/pipeline-queue")
async def list_pipeline_queue(current_user=Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM pipeline_queue_items WHERE user_id = ? ORDER BY created_at DESC",
            (current_user["id"],),
        )
        rows = await cur.fetchall()
    return [_parse_queue_item_row(dict(row)) for row in rows]


@app.post("/api/pipeline-queue")
async def create_pipeline_queue_item(body: QueueItemBody, current_user=Depends(get_current_user)):
    payload = body.model_dump() if hasattr(body, "model_dump") else body.dict()
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """INSERT INTO pipeline_queue_items
               (user_id, label, url, company_name, role_hint, status, notes, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                current_user["id"],
                sanitize_line(payload.get("label"), 160),
                sanitize_line(payload.get("url"), 240),
                sanitize_line(payload.get("company_name"), 120),
                sanitize_line(payload.get("role_hint"), 120),
                sanitize_line(payload.get("status") or "pending", 40),
                sanitize_block(payload.get("notes"), 800),
                now,
            ),
        )
        await db.commit()
        cur = await db.execute("SELECT * FROM pipeline_queue_items WHERE id = ?", (cursor.lastrowid,))
        row = await cur.fetchone()
    return _parse_queue_item_row(dict(row))


@app.put("/api/pipeline-queue/{item_id}")
async def update_pipeline_queue_item(item_id: int, body: QueueItemUpdate, current_user=Depends(get_current_user)):
    payload = body.model_dump() if hasattr(body, "model_dump") else body.dict()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM pipeline_queue_items WHERE id = ? AND user_id = ?", (item_id, current_user["id"]))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "Queue item not found")
        existing = dict(row)
        next_status = sanitize_line(payload.get("status") if payload.get("status") is not None else existing.get("status"), 40)
        next_notes = sanitize_block(payload.get("notes") if payload.get("notes") is not None else existing.get("notes"), 800)
        await db.execute(
            "UPDATE pipeline_queue_items SET status = ?, notes = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (next_status, next_notes, datetime.utcnow().isoformat(), item_id, current_user["id"]),
        )
        await db.commit()
        cur = await db.execute("SELECT * FROM pipeline_queue_items WHERE id = ? AND user_id = ?", (item_id, current_user["id"]))
        row = await cur.fetchone()
    return _parse_queue_item_row(dict(row))


@app.delete("/api/pipeline-queue/{item_id}")
async def delete_pipeline_queue_item(item_id: int, current_user=Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM pipeline_queue_items WHERE id = ? AND user_id = ?", (item_id, current_user["id"]))
        await db.commit()
    return {"deleted": item_id}


@app.get("/api/company-portals")
async def list_company_portals(current_user=Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM company_portals WHERE user_id = ? ORDER BY favorite DESC, updated_at DESC",
            (current_user["id"],),
        )
        rows = await cur.fetchall()
    return [_parse_company_portal_row(dict(row)) for row in rows]


@app.post("/api/company-portals")
async def create_company_portal(body: CompanyPortalBody, current_user=Depends(get_current_user)):
    payload = body.model_dump(exclude_unset=True) if hasattr(body, "model_dump") else body.dict(exclude_unset=True)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        existing_cur = await db.execute(
            """SELECT * FROM company_portals
               WHERE user_id = ? AND (
                   lower(company_name) = lower(?)
                   OR lower(careers_url) = lower(?)
               )
               ORDER BY favorite DESC, updated_at DESC
               LIMIT 1""",
            (
                current_user["id"],
                sanitize_line(payload.get("company_name"), 120),
                sanitize_line(payload.get("careers_url"), 240),
            ),
        )
        existing = await existing_cur.fetchone()
        serialized = _serialize_company_portal_payload(payload, dict(existing) if existing else None)

        if not serialized["company_name"] or not serialized["careers_url"]:
            raise HTTPException(400, "company_name and careers_url are required")

        if existing:
            existing_url = existing["careers_url"] or ""
            incoming_url = serialized["careers_url"] or ""
            if existing_url and incoming_url and existing_url.lower() != incoming_url.lower():
                if _score_portal_seed_url(existing_url) >= _score_portal_seed_url(incoming_url):
                    serialized["careers_url"] = existing_url
            await db.execute(
                """UPDATE company_portals
                   SET company_name = ?, careers_url = ?, active = ?, favorite = ?, notes = ?, tags_json = ?,
                       cadence = ?, next_scan_at = ?, updated_at = ?
                   WHERE id = ? AND user_id = ?""",
                (
                    serialized["company_name"],
                    serialized["careers_url"],
                    serialized["active"],
                    serialized["favorite"],
                    serialized["notes"],
                    serialized["tags_json"],
                    serialized["cadence"],
                    serialized["next_scan_at"],
                    serialized["updated_at"],
                    existing["id"],
                    current_user["id"],
                ),
            )
            await db.commit()
            cur = await db.execute("SELECT * FROM company_portals WHERE id = ?", (existing["id"],))
        else:
            cursor = await db.execute(
                """INSERT INTO company_portals
                   (user_id, company_name, careers_url, active, favorite, notes, tags_json, cadence, next_scan_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    current_user["id"],
                    serialized["company_name"],
                    serialized["careers_url"],
                    serialized["active"],
                    serialized["favorite"],
                    serialized["notes"],
                    serialized["tags_json"],
                    serialized["cadence"],
                    serialized["next_scan_at"],
                    serialized["updated_at"],
                ),
            )
            await db.commit()
            cur = await db.execute("SELECT * FROM company_portals WHERE id = ?", (cursor.lastrowid,))
        row = await cur.fetchone()
    return _parse_company_portal_row(dict(row))


@app.put("/api/company-portals/{portal_id}")
async def update_company_portal(portal_id: int, body: CompanyPortalUpdate, current_user=Depends(get_current_user)):
    payload = body.model_dump(exclude_none=True) if hasattr(body, "model_dump") else body.dict(exclude_none=True)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM company_portals WHERE id = ? AND user_id = ?", (portal_id, current_user["id"]))
        existing = await cur.fetchone()
        if not existing:
            raise HTTPException(404, "Company portal not found")

        serialized = _serialize_company_portal_payload(payload, dict(existing))
        await db.execute(
            """UPDATE company_portals
               SET company_name = ?, careers_url = ?, active = ?, favorite = ?, notes = ?, tags_json = ?,
                   cadence = ?, next_scan_at = ?, updated_at = ?
               WHERE id = ? AND user_id = ?""",
            (
                serialized["company_name"],
                serialized["careers_url"],
                serialized["active"],
                serialized["favorite"],
                serialized["notes"],
                serialized["tags_json"],
                serialized["cadence"],
                serialized["next_scan_at"],
                serialized["updated_at"],
                portal_id,
                current_user["id"],
            ),
        )
        await db.commit()
        cur = await db.execute("SELECT * FROM company_portals WHERE id = ? AND user_id = ?", (portal_id, current_user["id"]))
        row = await cur.fetchone()
    return _parse_company_portal_row(dict(row))


@app.post("/api/company-portals/{portal_id}/scan")
async def run_company_portal_scan(portal_id: int, current_user=Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM company_portals WHERE id = ? AND user_id = ?", (portal_id, current_user["id"]))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "Company portal not found")
    if portal_id in ACTIVE_COMPANY_PORTAL_SCANS:
        raise HTTPException(409, "Company portal scan already running")

    ACTIVE_COMPANY_PORTAL_SCANS.add(portal_id)
    try:
        updated = await _run_company_portal_scan_by_id(portal_id)
    except requests.RequestException as error:
        raise HTTPException(502, f"Portal scan failed: {error}")
    if not updated:
        raise HTTPException(404, "Company portal not found")
    return updated


@app.get("/api/company-portals/{portal_id}/runs")
async def list_company_portal_runs(portal_id: int, current_user=Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM company_portals WHERE id = ? AND user_id = ?", (portal_id, current_user["id"]))
        portal = await cur.fetchone()
        if not portal:
            raise HTTPException(404, "Company portal not found")
        runs_cur = await db.execute(
            """SELECT runs.*, portals.company_name
               FROM company_portal_runs runs
               JOIN company_portals portals ON portals.id = runs.portal_id
               WHERE runs.portal_id = ?
               ORDER BY runs.started_at DESC
               LIMIT 20""",
            (portal_id,),
        )
        runs = await runs_cur.fetchall()
    return [_parse_company_portal_run_row(dict(run)) for run in runs]


@app.delete("/api/company-portals/{portal_id}")
async def delete_company_portal(portal_id: int, current_user=Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM company_portals WHERE id = ? AND user_id = ?", (portal_id, current_user["id"]))
        await db.commit()
    ACTIVE_COMPANY_PORTAL_SCANS.discard(portal_id)
    return {"deleted": portal_id}


@app.get("/api/company-research")
async def list_company_research(current_user=Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM company_research_reports WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
            (current_user["id"],),
        )
        rows = await cur.fetchall()
    return [_parse_company_research_row(dict(row)) for row in rows]


@app.post("/api/company-research/generate")
async def generate_company_research(body: CompanyResearchBody, current_user=Depends(get_current_user)):
    payload = body.model_dump() if hasattr(body, "model_dump") else body.dict()
    try:
        result = build_company_research(payload.get("company_name"), payload.get("source_url"), payload.get("role_title"))
    except requests.RequestException as error:
        raise HTTPException(502, f"Research fetch failed: {error}")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """INSERT INTO company_research_reports
               (user_id, company_name, role_title, source_url, summary, culture_json, product_json, risks_json, headings_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                current_user["id"],
                result["company_name"],
                result["role_title"],
                result["source_url"],
                result["summary"],
                dumps_json(result["culture_signals"]),
                dumps_json(result["product_signals"]),
                dumps_json(result["risks"]),
                dumps_json(result["headings"]),
            ),
        )
        await db.commit()
        cur = await db.execute("SELECT * FROM company_research_reports WHERE id = ?", (cursor.lastrowid,))
        row = await cur.fetchone()
    return _parse_company_research_row(dict(row))


@app.post("/api/evaluations/training")
async def create_training_evaluation(body: CareerEvaluationBody, current_user=Depends(get_current_user)):
    profile_row, user = await _fetch_cv_profile(current_user["id"])
    profile = _parse_cv_profile_row(profile_row, user)
    result = evaluate_training_fit(profile, body.input_text)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """INSERT INTO career_evaluations (user_id, kind, title, input_text, output_json)
               VALUES (?, 'training', ?, ?, ?)""",
            (current_user["id"], sanitize_line(body.title, 140), sanitize_block(body.input_text, 900), dumps_json(result)),
        )
        await db.commit()
        cur = await db.execute("SELECT * FROM career_evaluations WHERE id = ?", (cursor.lastrowid,))
        row = await cur.fetchone()
    return _parse_career_evaluation_row(dict(row))


@app.post("/api/evaluations/project")
async def create_project_evaluation(body: CareerEvaluationBody, current_user=Depends(get_current_user)):
    profile_row, user = await _fetch_cv_profile(current_user["id"])
    profile = _parse_cv_profile_row(profile_row, user)
    result = evaluate_project_fit(profile, body.input_text)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """INSERT INTO career_evaluations (user_id, kind, title, input_text, output_json)
               VALUES (?, 'project', ?, ?, ?)""",
            (current_user["id"], sanitize_line(body.title, 140), sanitize_block(body.input_text, 900), dumps_json(result)),
        )
        await db.commit()
        cur = await db.execute("SELECT * FROM career_evaluations WHERE id = ?", (cursor.lastrowid,))
        row = await cur.fetchone()
    return _parse_career_evaluation_row(dict(row))


@app.get("/api/evaluations/{kind}")
async def list_evaluations(kind: str, current_user=Depends(get_current_user)):
    safe_kind = sanitize_line(kind, 40)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM career_evaluations WHERE user_id = ? AND kind = ? ORDER BY created_at DESC LIMIT 20",
            (current_user["id"], safe_kind),
        )
        rows = await cur.fetchall()
    return [_parse_career_evaluation_row(dict(row)) for row in rows]


@app.get("/api/favorites/jobs")
async def list_favorite_jobs(current_user=Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM favorite_jobs WHERE user_id = ? ORDER BY updated_at DESC, created_at DESC",
            (current_user["id"],),
        )
        rows = await cur.fetchall()
    return [_parse_favorite_job_row(dict(row)) for row in rows]


@app.post("/api/favorites/jobs")
async def create_favorite_job(body: FavoriteJobBody, current_user=Depends(get_current_user)):
    payload = body.model_dump() if hasattr(body, "model_dump") else body.dict()
    job_url = sanitize_line(payload.get("job_url"), 320)
    if not job_url:
        raise HTTPException(400, "job_url required")
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            """INSERT INTO favorite_jobs
               (user_id, search_result_id, job_url, job_title, company_name, source, location, contract_type, notes, payload_json, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id, job_url) DO UPDATE SET
                   search_result_id = excluded.search_result_id,
                   job_title = excluded.job_title,
                   company_name = excluded.company_name,
                   source = excluded.source,
                   location = excluded.location,
                   contract_type = excluded.contract_type,
                   notes = CASE
                       WHEN excluded.notes != '' THEN excluded.notes
                       ELSE favorite_jobs.notes
                   END,
                   payload_json = excluded.payload_json,
                   updated_at = excluded.updated_at""",
            (
                current_user["id"],
                payload.get("search_result_id"),
                job_url,
                sanitize_line(payload.get("job_title"), 180),
                sanitize_line(payload.get("company_name"), 140),
                sanitize_line(payload.get("source"), 80),
                sanitize_line(payload.get("location"), 140),
                sanitize_line(payload.get("contract_type"), 80),
                sanitize_block(payload.get("notes"), 500),
                dumps_json(payload.get("payload") or {}),
                now,
            ),
        )
        await db.commit()
        cur = await db.execute(
            "SELECT * FROM favorite_jobs WHERE user_id = ? AND job_url = ?",
            (current_user["id"], job_url),
        )
        row = await cur.fetchone()
    return _parse_favorite_job_row(dict(row))


@app.put("/api/favorites/jobs/{favorite_id}")
async def update_favorite_job(favorite_id: int, body: FavoriteJobUpdate, current_user=Depends(get_current_user)):
    payload = body.model_dump(exclude_none=True) if hasattr(body, "model_dump") else body.dict(exclude_none=True)
    if "notes" not in payload:
        raise HTTPException(400, "No update payload")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "UPDATE favorite_jobs SET notes = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (
                sanitize_block(payload.get("notes"), 500),
                datetime.utcnow().isoformat(),
                favorite_id,
                current_user["id"],
            ),
        )
        await db.commit()
        cur = await db.execute("SELECT * FROM favorite_jobs WHERE id = ? AND user_id = ?", (favorite_id, current_user["id"]))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "Favorite job not found")
    return _parse_favorite_job_row(dict(row))


@app.delete("/api/favorites/jobs/{favorite_id}")
async def delete_favorite_job(favorite_id: int, current_user=Depends(get_current_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM favorite_jobs WHERE id = ? AND user_id = ?", (favorite_id, current_user["id"]))
        await db.commit()
    return {"deleted": favorite_id}


@app.get("/api/ops/overview")
async def get_ops_overview(current_user=Depends(get_current_user)):
    profile_row, user = await _fetch_cv_profile(current_user["id"])
    profile = _parse_cv_profile_row(profile_row, user)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        queue_cur = await db.execute(
            "SELECT * FROM pipeline_queue_items WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
            (current_user["id"],),
        )
        story_cur = await db.execute(
            "SELECT * FROM story_bank_entries WHERE user_id = ? ORDER BY updated_at DESC LIMIT 20",
            (current_user["id"],),
        )
        portal_cur = await db.execute(
            "SELECT * FROM company_portals WHERE user_id = ? ORDER BY favorite DESC, updated_at DESC LIMIT 20",
            (current_user["id"],),
        )
        portal_run_cur = await db.execute(
            """SELECT runs.*, portals.company_name
               FROM company_portal_runs runs
               JOIN company_portals portals ON portals.id = runs.portal_id
               WHERE portals.user_id = ?
               ORDER BY runs.started_at DESC
               LIMIT 20""",
            (current_user["id"],),
        )
        research_cur = await db.execute(
            "SELECT * FROM company_research_reports WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
            (current_user["id"],),
        )
        training_cur = await db.execute(
            "SELECT * FROM career_evaluations WHERE user_id = ? AND kind = 'training' ORDER BY created_at DESC LIMIT 10",
            (current_user["id"],),
        )
        project_cur = await db.execute(
            "SELECT * FROM career_evaluations WHERE user_id = ? AND kind = 'project' ORDER BY created_at DESC LIMIT 10",
            (current_user["id"],),
        )
        favorite_job_cur = await db.execute(
            "SELECT * FROM favorite_jobs WHERE user_id = ? ORDER BY updated_at DESC LIMIT 20",
            (current_user["id"],),
        )
        queue_rows = await queue_cur.fetchall()
        story_rows = await story_cur.fetchall()
        portal_rows = await portal_cur.fetchall()
        portal_run_rows = await portal_run_cur.fetchall()
        research_rows = await research_cur.fetchall()
        training_rows = await training_cur.fetchall()
        project_rows = await project_cur.fetchall()
        favorite_job_rows = await favorite_job_cur.fetchall()
    return {
        "tracker_statuses": tracker_status_meta(),
        "story_bank": {
            "items": [_parse_story_bank_row(dict(row)) for row in story_rows],
            "suggestions": story_bank_suggestions(profile),
        },
        "pipeline_queue": [_parse_queue_item_row(dict(row)) for row in queue_rows],
        "company_portals": [_parse_company_portal_row(dict(row)) for row in portal_rows],
        "company_portal_runs": [_parse_company_portal_run_row(dict(row)) for row in portal_run_rows],
        "company_research": [_parse_company_research_row(dict(row)) for row in research_rows],
        "training_evaluations": [_parse_career_evaluation_row(dict(row)) for row in training_rows],
        "project_evaluations": [_parse_career_evaluation_row(dict(row)) for row in project_rows],
        "favorite_jobs": [_parse_favorite_job_row(dict(row)) for row in favorite_job_rows],
    }


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


async def company_portal_scheduler_loop():
    while True:
        try:
            now = datetime.utcnow().isoformat()
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                cur = await db.execute(
                    """SELECT * FROM company_portals
                       WHERE active = 1 AND careers_url != '' AND (next_scan_at IS NULL OR next_scan_at <= ?)
                       ORDER BY favorite DESC, next_scan_at ASC, created_at ASC""",
                    (now,),
                )
                rows = await cur.fetchall()

            for row in rows:
                portal_id = row["id"]
                if portal_id in ACTIVE_COMPANY_PORTAL_SCANS:
                    continue
                ACTIVE_COMPANY_PORTAL_SCANS.add(portal_id)
                asyncio.create_task(_run_company_portal_scan_by_id(portal_id))
        except Exception as e:
            logger.exception("company portal scheduler crashed: %s", e)

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

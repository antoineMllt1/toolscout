import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from cv_engine import TEMPLATE_BY_SLUG, sanitize_block, sanitize_line, sanitize_string_list
except ModuleNotFoundError:
    from backend.cv_engine import TEMPLATE_BY_SLUG, sanitize_block, sanitize_line, sanitize_string_list


TEMPLATE_COLORS = {
    "green": {"primary": "#2f855a", "accent": "#276749", "light": "#e6f4ec"},
    "red": {"primary": "#b83232", "accent": "#822727", "light": "#fbeaea"},
    "orange": {"primary": "#c05621", "accent": "#9c4221", "light": "#fff0e8"},
    "blue": {"primary": "#2b6cb0", "accent": "#1a4f84", "light": "#e8f1fb"},
}


def _get_template(template_slug: str) -> dict:
    return TEMPLATE_BY_SLUG.get(template_slug) or TEMPLATE_BY_SLUG["moderncv-classic"]


def _get_colors(template: dict) -> dict:
    return TEMPLATE_COLORS.get(template.get("color", "green"), TEMPLATE_COLORS["green"])


def _escape_html(value: str, max_length: int = 4000) -> str:
    text = sanitize_block(value, max_length=max_length)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _date_label(start_date: str, end_date: str) -> str:
    start = sanitize_line(start_date, 40)
    end = sanitize_line(end_date, 40)
    if start and end:
        return f"{start} - {end}"
    return start or end or ""


def _contact_items(profile: dict) -> list[str]:
    contacts = []
    for key in ["email", "phone", "location"]:
        value = sanitize_line(profile.get(key), 180)
        if value:
            contacts.append(_escape_html(value, 180))
    for key in ["website", "linkedin", "github"]:
        value = sanitize_line(profile.get(key), 220)
        if not value:
            continue
        display = value.replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")
        contacts.append(_escape_html(display, 220))
    return contacts[:6]


def _clean_bullets(values: list[str], max_items: int = 6) -> list[str]:
    return sanitize_string_list(values, max_items=max_items, max_length=400)


def _lookup_rewrites(copy_suggestions: dict | None, key: str, value_key: str) -> dict[str, list[str] | str]:
    lookup = {}
    if not copy_suggestions:
        return lookup
    for item in copy_suggestions.get(key) or []:
        item_id = sanitize_line(item.get("id"), 80)
        if not item_id:
            continue
        lookup[item_id] = item.get(value_key) or ([] if value_key == "bullets" else "")
    return lookup


def _is_valid_composed_cv(copy_suggestions: dict | None) -> bool:
    if not copy_suggestions:
        return False
    composed = copy_suggestions.get("composed_cv")
    if not isinstance(composed, dict):
        return False
    title = sanitize_line(composed.get("title"), 140)
    profile = sanitize_block(composed.get("profile"), 1000)
    experiences = composed.get("experience") or []
    projects = composed.get("projects") or []
    banned_titles = {
        "l'impact",
        "impact",
        "cadre du projet",
        "contexte",
        "enjeu",
        "mission",
        "resultat",
        "résultat",
    }
    if not title or not profile:
        return False
    if not experiences and not projects:
        return False
    for group in [experiences, projects]:
        for item in group:
            if not isinstance(item, dict):
                return False
            item_title = sanitize_line(item.get("title"), 180).lower()
            if not item_title or item_title in banned_titles:
                return False
    if profile.strip().startswith(("Et si ", "Pourquoi ", "Imaginez ")):
        return False
    return True


def _render_claude_direct_cv_html(profile: dict, template_slug: str, copy_suggestions: dict) -> str:
    template = _get_template(template_slug)
    colors = _get_colors(template)
    composed = copy_suggestions.get("composed_cv") or {}
    title = sanitize_line(composed.get("title") or profile.get("headline"), 140)
    subtitle = sanitize_line(composed.get("subtitle"), 220)
    profile_block = sanitize_block(composed.get("profile") or copy_suggestions.get("summary") or profile.get("summary"), 1800)
    hard_skills = sanitize_string_list(composed.get("hard_skills"), max_items=8, max_length=60)
    soft_skills = sanitize_string_list(composed.get("soft_skills"), max_items=6, max_length=60)
    contacts = " <span class=\"sep\">|</span> ".join(
        f"<span class=\"contact-item\">{item}</span>" for item in _contact_items(profile)
    )

    def render_list(items: list[dict], note_key: str = "bullets") -> str:
        blocks = []
        for item in items or []:
            title_html = _escape_html(item.get("title") or "", 180)
            meta_html = _escape_html(item.get("meta") or "", 220)
            if note_key == "bullets":
                bullets = "".join(f"<li>{_escape_html(bullet, 220)}</li>" for bullet in sanitize_string_list(item.get("bullets"), max_items=4, max_length=220))
                note_html = f"<ul class=\"entry-bullets\">{bullets}</ul>" if bullets else ""
            else:
                note = _escape_html(item.get(note_key) or "", 260)
                note_html = f"<p class=\"entry-note\">{note}</p>" if note else ""
            blocks.append(
                f"""
                <div class="entry">
                  <div class="entry-header">
                    <span class="entry-title">{title_html}</span>
                    <span class="entry-meta">{meta_html}</span>
                  </div>
                  {note_html}
                </div>
                """
            )
        return "".join(blocks)

    extra_html = "".join(
        f"<div class=\"mini-proof\"><strong>{_escape_html(item.get('title') or '', 120)}</strong><span>{_escape_html(item.get('bullet') or '', 220)}</span></div>"
        for item in (composed.get("extra") or [])
        if item.get("title") or item.get("bullet")
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    @page {{
      size: A4;
      margin: 0;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      color: #17212b;
      background: #f7f4ee;
    }}
    .page {{
      width: 210mm;
      min-height: 297mm;
      padding: 16mm 15mm 15mm;
      background:
        radial-gradient(circle at top right, {colors['light']} 0, rgba(255,255,255,0) 32%),
        linear-gradient(180deg, #fffdf9 0%, #ffffff 100%);
    }}
    .cv-header {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 190px;
      gap: 18px;
      align-items: start;
      border-bottom: 2px solid {colors['primary']};
      padding-bottom: 10px;
      margin-bottom: 14px;
    }}
    .cv-header h1 {{
      margin: 0;
      color: {colors['primary']};
      font-size: 30px;
      line-height: 0.95;
      letter-spacing: -0.03em;
    }}
    .role-title {{
      margin: 8px 0 0;
      font-size: 14px;
      font-family: "Helvetica Neue", Arial, sans-serif;
      color: #1f2c37;
      font-weight: 700;
    }}
    .subtitle {{
      margin: 8px 0 0;
      font-size: 11px;
      color: #586674;
      line-height: 1.45;
      font-family: "Helvetica Neue", Arial, sans-serif;
    }}
    .contact-card {{
      padding: 10px 12px;
      border: 1px solid #d8d0c2;
      background: rgba(255,255,255,0.8);
      border-radius: 14px;
      font-size: 9.5px;
      line-height: 1.6;
      color: #40505e;
      font-family: "Helvetica Neue", Arial, sans-serif;
    }}
    .sep {{ color: #bfae90; margin: 0 4px; }}
    .cv-grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.55fr) minmax(0, 0.95fr);
      gap: 16px;
    }}
    .main-column, .side-column {{
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}
    .cv-section {{
      break-inside: avoid;
    }}
    .section-title {{
      margin: 0 0 6px;
      font-size: 10px;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      font-family: "Helvetica Neue", Arial, sans-serif;
      color: {colors['accent']};
      font-weight: 800;
    }}
    .profile-card, .side-card {{
      padding: 10px 12px;
      border-radius: 14px;
      border: 1px solid #e2dbcf;
      background: rgba(255,255,255,0.84);
    }}
    .profile-card p, .side-card p {{
      margin: 0;
      font-size: 10.6px;
      line-height: 1.58;
      color: #22303d;
      font-family: "Helvetica Neue", Arial, sans-serif;
    }}
    .skill-group + .skill-group {{ margin-top: 8px; }}
    .skill-label {{
      display: block;
      margin-bottom: 4px;
      font-size: 9px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: #7b6f5c;
      font-weight: 700;
      font-family: "Helvetica Neue", Arial, sans-serif;
    }}
    .skill-values {{
      font-size: 10px;
      line-height: 1.5;
      color: #1f2c37;
      font-family: "Helvetica Neue", Arial, sans-serif;
    }}
    .entry {{
      padding: 0 0 8px;
      margin-bottom: 8px;
      border-bottom: 1px solid #efe8dc;
      break-inside: avoid;
    }}
    .entry:last-child {{
      margin-bottom: 0;
      border-bottom: 0;
      padding-bottom: 0;
    }}
    .entry-header {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: baseline;
    }}
    .entry-title {{
      font-size: 12px;
      font-weight: 700;
      color: #17212b;
      font-family: "Helvetica Neue", Arial, sans-serif;
    }}
    .entry-meta {{
      text-align: right;
      font-size: 9px;
      color: #637280;
      font-family: "Helvetica Neue", Arial, sans-serif;
    }}
    .entry-bullets {{
      margin: 6px 0 0;
      padding-left: 16px;
      font-size: 10px;
      line-height: 1.44;
      color: #263341;
      font-family: "Helvetica Neue", Arial, sans-serif;
    }}
    .entry-note {{
      margin: 6px 0 0;
      font-size: 10px;
      line-height: 1.5;
      color: #2e3d4c;
      font-family: "Helvetica Neue", Arial, sans-serif;
    }}
    .mini-proof + .mini-proof {{ margin-top: 8px; }}
    .mini-proof {{
      display: flex;
      flex-direction: column;
      gap: 3px;
      font-family: "Helvetica Neue", Arial, sans-serif;
    }}
    .mini-proof strong {{
      font-size: 10px;
      color: #1f2c37;
    }}
    .mini-proof span {{
      font-size: 9.6px;
      line-height: 1.45;
      color: #5a6877;
    }}
  </style>
</head>
<body>
  <div class="page">
    <header class="cv-header">
      <div>
        <h1>{_escape_html(profile.get("full_name") or "Candidate", 160)}</h1>
        {f'<p class="role-title">{_escape_html(title, 140)}</p>' if title else ''}
        {f'<p class="subtitle">{_escape_html(subtitle, 220)}</p>' if subtitle else ''}
      </div>
      <div class="contact-card">{contacts}</div>
    </header>
    <div class="cv-grid">
      <div class="main-column">
        <section class="cv-section">
          <h2 class="section-title">Profile</h2>
          <div class="profile-card"><p>{_escape_html(profile_block, 1800)}</p></div>
        </section>
        <section class="cv-section">
          <h2 class="section-title">Experience</h2>
          {render_list(composed.get("experience") or [], "bullets")}
        </section>
        <section class="cv-section">
          <h2 class="section-title">Projects</h2>
          {render_list(composed.get("projects") or [], "bullets")}
        </section>
      </div>
      <div class="side-column">
        <section class="cv-section">
          <h2 class="section-title">Hybrid Skills</h2>
          <div class="side-card">
            <div class="skill-group">
              <span class="skill-label">Hard Skills</span>
              <div class="skill-values">{_escape_html(', '.join(hard_skills), 420)}</div>
            </div>
            <div class="skill-group">
              <span class="skill-label">Soft Skills</span>
              <div class="skill-values">{_escape_html(', '.join(soft_skills), 320)}</div>
            </div>
          </div>
        </section>
        <section class="cv-section">
          <h2 class="section-title">Education</h2>
          {render_list(composed.get("education") or [], "bullet")}
        </section>
        {f'<section class="cv-section"><h2 class="section-title">Extra-Professional</h2><div class="side-card">{extra_html}</div></section>' if extra_html else ''}
      </div>
    </div>
  </div>
</body>
</html>"""


def _compact_selected_payload(selected_payload: dict, copy_suggestions: dict | None = None) -> dict:
    compact = dict(selected_payload or {})
    compact["experience"] = list((selected_payload.get("experience") or [])[:4])
    compact["projects"] = list((selected_payload.get("projects") or [])[:4])
    compact["education"] = list((selected_payload.get("education") or [])[:2])
    compact["skills"] = list((copy_suggestions or {}).get("skills_priority") or selected_payload.get("skills") or [])[:14]
    compact["languages"] = list((selected_payload.get("languages") or [])[:4])
    compact["certifications"] = list((selected_payload.get("certifications") or [])[:4])
    return compact


def render_cv_html(
    profile: dict,
    template_slug: str,
    selected_payload: dict,
    copy_suggestions: dict | None = None,
) -> str:
    selected_payload = _compact_selected_payload(selected_payload, copy_suggestions)
    template = _get_template(template_slug)
    colors = _get_colors(template)
    target = selected_payload.get("target") or {}
    style = template.get("style", "classic")

    headline = sanitize_line(
        (copy_suggestions or {}).get("headline")
        or profile.get("headline")
        or target.get("job_title")
        or "",
        180,
    )
    summary = sanitize_block(
        (copy_suggestions or {}).get("summary")
        or profile.get("summary")
        or "",
        1200,
    )

    exp_rewrites = _lookup_rewrites(copy_suggestions, "experience_rewrites", "bullets")
    project_rewrites = _lookup_rewrites(copy_suggestions, "project_rewrites", "bullets")
    education_rewrites = _lookup_rewrites(copy_suggestions, "education_rewrites", "bullet")

    contacts = " <span class=\"sep\">|</span> ".join(
        f"<span class=\"contact-item\">{item}</span>" for item in _contact_items(profile)
    )

    variant_class = f"template-{style}"
    sections = []

    if summary:
        sections.append(
            f"""
            <section class="cv-section">
              <h2 class="section-title">Profile</h2>
              <p class="section-paragraph">{_escape_html(summary, 1400)}</p>
            </section>
            """
        )

    experience_html = []
    for item in selected_payload.get("experience") or []:
        bullets = exp_rewrites.get(item.get("id")) or []
        if not bullets:
            bullets = [item.get("summary", ""), *(item.get("highlights") or [])]
        bullets = _clean_bullets(bullets, max_items=4)
        meta = " - ".join(
            value
            for value in [
                sanitize_line(item.get("company"), 140),
                sanitize_line(item.get("location"), 120),
                _date_label(item.get("start_date"), item.get("end_date")),
            ]
            if value
        )
        bullets_html = "".join(f"<li>{_escape_html(bullet, 400)}</li>" for bullet in bullets)
        experience_html.append(
            f"""
            <div class="entry">
              <div class="entry-header">
                <span class="entry-title">{_escape_html(item.get('title') or item.get('company') or 'Experience', 180)}</span>
                <span class="entry-meta">{_escape_html(meta, 220)}</span>
              </div>
              {f'<ul class="entry-bullets">{bullets_html}</ul>' if bullets_html else ''}
            </div>
            """
        )
    if experience_html:
        sections.append(
            f"""
            <section class="cv-section">
              <h2 class="section-title">Experience</h2>
              {''.join(experience_html)}
            </section>
            """
        )

    projects_html = []
    for item in selected_payload.get("projects") or []:
        bullets = project_rewrites.get(item.get("id")) or []
        if not bullets:
            bullets = [item.get("summary", ""), *(item.get("highlights") or [])]
        technologies = sanitize_string_list(item.get("technologies"), max_items=4, max_length=80)
        if technologies:
            bullets = [*bullets, f"Stack: {', '.join(technologies)}"]
        bullets = _clean_bullets(bullets, max_items=3)
        bullets_html = "".join(f"<li>{_escape_html(bullet, 400)}</li>" for bullet in bullets)
        meta = sanitize_line(item.get("role"), 140)
        projects_html.append(
            f"""
            <div class="entry">
              <div class="entry-header">
                <span class="entry-title">{_escape_html(item.get('name') or item.get('role') or 'Project', 180)}</span>
                <span class="entry-meta">{_escape_html(meta, 180)}</span>
              </div>
              {f'<ul class="entry-bullets">{bullets_html}</ul>' if bullets_html else ''}
            </div>
            """
        )
    if projects_html:
        sections.append(
            f"""
            <section class="cv-section">
              <h2 class="section-title">Projects</h2>
              {''.join(projects_html)}
            </section>
            """
        )

    education_html = []
    for item in selected_payload.get("education") or []:
        degree_bits = [sanitize_line(item.get("degree"), 140), sanitize_line(item.get("field"), 140)]
        title = " - ".join(part for part in degree_bits if part) or sanitize_line(item.get("school"), 160) or "Education"
        meta = " - ".join(
            value
            for value in [
                sanitize_line(item.get("school"), 140),
                sanitize_line(item.get("location"), 120),
                _date_label(item.get("start_date"), item.get("end_date")),
            ]
            if value
        )
        note = sanitize_block(education_rewrites.get(item.get("id")) or item.get("summary") or "", 500)
        education_html.append(
            f"""
            <div class="entry">
              <div class="entry-header">
                <span class="entry-title">{_escape_html(title, 220)}</span>
                <span class="entry-meta">{_escape_html(meta, 220)}</span>
              </div>
              {f'<p class="entry-note">{_escape_html(note, 600)}</p>' if note else ''}
            </div>
            """
        )
    if education_html:
        sections.append(
            f"""
            <section class="cv-section">
              <h2 class="section-title">Education</h2>
              {''.join(education_html)}
            </section>
            """
        )

    skills = selected_payload.get("skills") or []
    if skills:
        sections.append(
            f"""
            <section class="cv-section">
              <h2 class="section-title">Core Skills</h2>
              <p class="section-paragraph">{_escape_html(', '.join(skills), 900)}</p>
            </section>
            """
        )

    extras = []
    if selected_payload.get("languages"):
        extras.append(f"<p><strong>Languages</strong> {_escape_html(', '.join(selected_payload['languages']), 400)}</p>")
    if selected_payload.get("certifications"):
        extras.append(f"<p><strong>Certifications</strong> {_escape_html(', '.join(selected_payload['certifications']), 500)}</p>")
    if extras:
        sections.append(
            f"""
            <section class="cv-section">
              <h2 class="section-title">Additional</h2>
              <div class="section-paragraph extras-block">{''.join(extras)}</div>
            </section>
            """
        )

    header_note = f"<p class=\"headline\">{_escape_html(headline, 220)}</p>" if headline else ""
    body_sections = "".join(sections)
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    @page {{
      size: A4;
      margin: 0;
    }}
    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      font-family: "Helvetica Neue", Arial, sans-serif;
      color: #17212b;
      background: #ffffff;
    }}
    .page {{
      width: 210mm;
      min-height: 297mm;
      padding: 13mm 13mm 12mm;
    }}
    .template-classic .page {{
      padding-top: 12mm;
    }}
    .template-banking .page {{
      padding-top: 11mm;
    }}
    .template-casual .page {{
      padding-top: 13mm;
      background:
        linear-gradient(90deg, {colors['light']} 0 16mm, #ffffff 16mm 100%);
      padding-left: 20mm;
    }}
    .cv-header {{
      border-bottom: 2px solid {colors['primary']};
      padding-bottom: 7px;
      margin-bottom: 8px;
    }}
    .template-banking .cv-header {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 12px;
      align-items: end;
    }}
    .cv-header h1 {{
      margin: 0;
      color: {colors['primary']};
      font-size: 22px;
      line-height: 1.05;
      letter-spacing: -0.02em;
      font-weight: 700;
    }}
    .headline {{
      margin: 5px 0 0;
      font-size: 11px;
      color: #51606f;
      font-weight: 500;
    }}
    .contact-line {{
      margin-top: 7px;
      font-size: 9.5px;
      color: #5c6978;
      line-height: 1.4;
    }}
    .contact-item {{
      white-space: nowrap;
    }}
    .sep {{
      color: #b8c0c8;
      margin: 0 4px;
    }}
    .cv-section {{
      margin-bottom: 11px;
      break-inside: avoid;
    }}
    .section-title {{
      margin: 0 0 5px;
      font-size: 9.5px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: {colors['accent']};
      font-weight: 700;
      border-bottom: 1px solid {colors['light']};
      padding-bottom: 4px;
    }}
    .section-paragraph,
    .extras-block p {{
      margin: 0;
      font-size: 10.5px;
      line-height: 1.5;
      color: #22303d;
    }}
    .extras-block p + p {{
      margin-top: 5px;
    }}
    .entry {{
      margin-bottom: 9px;
      break-inside: avoid;
    }}
    .entry.compact {{
      margin-bottom: 0;
    }}
    .entry-header {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: baseline;
    }}
    .entry-title {{
      font-size: 11px;
      font-weight: 700;
      color: #17212b;
    }}
    .entry-meta {{
      flex-shrink: 0;
      text-align: right;
      font-size: 9px;
      color: #61707f;
    }}
    .entry-bullets {{
      margin: 4px 0 0;
      padding-left: 15px;
      font-size: 10px;
      color: #243241;
      line-height: 1.45;
    }}
    .entry-bullets li {{
      margin-bottom: 3px;
    }}
    .entry-note {{
      margin: 4px 0 0;
      font-size: 10px;
      color: #314253;
      line-height: 1.45;
    }}
  </style>
</head>
<body class="{variant_class}">
  <div class="page">
    <header class="cv-header">
      <div>
        <h1>{_escape_html(profile.get("full_name") or "Candidate", 160)}</h1>
        {header_note}
      </div>
      <div class="contact-line">{contacts}</div>
    </header>
    {body_sections}
  </div>
</body>
</html>
"""
    return html


def render_cover_letter_html(profile: dict, target: dict, letter_text: str, template_slug: str) -> str:
    template = _get_template(template_slug)
    colors = _get_colors(template)
    full_name = _escape_html(profile.get("full_name") or "Candidate", 160)
    job_title = _escape_html(target.get("job_title"), 160)
    company_name = _escape_html(target.get("company_name"), 160)
    paragraphs = [
        f"<p>{_escape_html(paragraph, 1600)}</p>"
        for paragraph in sanitize_block(letter_text, 5000).split("\n")
        if paragraph.strip()
    ]
    contacts = " | ".join(_contact_items(profile))
    subject = f"Objet : Candidature - {sanitize_line(target.get('job_title'), 180)}" if target.get("job_title") else "Objet : Candidature"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <style>
    @page {{
      size: A4;
      margin: 0;
    }}
    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      font-family: "Helvetica Neue", Arial, sans-serif;
      color: #17212b;
      background: #ffffff;
    }}
    .page {{
      width: 210mm;
      min-height: 297mm;
      padding: 20mm 18mm;
    }}
    .sender {{
      margin-bottom: 16px;
    }}
    .sender h1 {{
      margin: 0 0 4px;
      font-size: 22px;
      color: {colors['primary']};
    }}
    .sender p,
    .recipient p,
    .subject,
    .body p,
    .closing p {{
      margin: 0;
      font-size: 11px;
      line-height: 1.6;
    }}
    .recipient {{
      text-align: right;
      margin-bottom: 20px;
      color: #51606f;
    }}
    .subject {{
      margin-bottom: 16px;
      padding-bottom: 8px;
      border-bottom: 1px solid {colors['light']};
      font-weight: 700;
      color: {colors['accent']};
    }}
    .body p {{
      margin-bottom: 12px;
      text-align: justify;
    }}
    .closing {{
      margin-top: 24px;
    }}
  </style>
</head>
<body>
  <div class="page">
    <div class="sender">
      <h1>{full_name}</h1>
      <p>{contacts}</p>
    </div>
    <div class="recipient">
      <p>{company_name}</p>
      <p>{job_title}</p>
    </div>
    <div class="subject">{_escape_html(subject, 220)}</div>
    <div class="body">
      {''.join(paragraphs)}
    </div>
    <div class="closing">
      <p>{full_name}</p>
    </div>
  </div>
</body>
</html>
"""


def generate_pdf_from_html(html_content: str) -> bytes:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".html", delete=False) as handle:
        handle.write(html_content)
        html_path = Path(handle.name)

    pdf_path = html_path.with_suffix(".pdf")
    html_uri = html_path.as_uri()
    script = """
from pathlib import Path
from playwright.sync_api import sync_playwright

html_uri = {html_uri}
pdf_path = Path({pdf_path})

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(html_uri, wait_until="networkidle")
    page.pdf(
        path=str(pdf_path),
        format="A4",
        print_background=True,
        margin={{"top": "0mm", "right": "0mm", "bottom": "0mm", "left": "0mm"}},
    )
    browser.close()
""".format(
        html_uri=json.dumps(html_uri),
        pdf_path=json.dumps(str(pdf_path)),
    )

    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=45,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if result.returncode != 0:
            error_text = (result.stderr or result.stdout or "").strip()
            if "Executable doesn't exist" in error_text or "browserType.launch" in error_text:
                raise RuntimeError("Playwright Chromium is not installed. Run `playwright install chromium`.")
            raise RuntimeError(f"PDF generation failed: {error_text[:300]}")
        return pdf_path.read_bytes()
    finally:
        for path in [html_path, pdf_path]:
            try:
                os.unlink(path)
            except OSError:
                pass

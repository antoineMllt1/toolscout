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
    return sanitize_string_list(values, max_items=max_items, max_length=220)


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


def render_cv_html(
    profile: dict,
    template_slug: str,
    selected_payload: dict,
    copy_suggestions: dict | None = None,
) -> str:
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

    if target.get("job_title") or target.get("company_name"):
        job_title = _escape_html(target.get("job_title"), 180)
        company_name = _escape_html(target.get("company_name"), 180)
        focus_terms = ", ".join((target.get("keywords") or [])[:8])
        sections.append(
            f"""
            <section class="cv-section">
              <h2 class="section-title">Target</h2>
              <div class="entry compact">
                <div class="entry-header">
                  <span class="entry-title">{job_title or 'Target role'}</span>
                  <span class="entry-meta">{company_name}</span>
                </div>
                {f'<p class="entry-note">{_escape_html(focus_terms, 240)}</p>' if focus_terms else ''}
              </div>
            </section>
            """
        )

    if summary:
        sections.append(
            f"""
            <section class="cv-section">
              <h2 class="section-title">Profile</h2>
              <p class="section-paragraph">{_escape_html(summary, 1400)}</p>
            </section>
            """
        )

    skills = copy_suggestions.get("skills_priority") if copy_suggestions and copy_suggestions.get("skills_priority") else selected_payload.get("skills") or []
    if skills:
        sections.append(
            f"""
            <section class="cv-section">
              <h2 class="section-title">Core Skills</h2>
              <p class="section-paragraph">{_escape_html(', '.join(skills), 800)}</p>
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

    experience_html = []
    for item in selected_payload.get("experience") or []:
        bullets = exp_rewrites.get(item.get("id")) or []
        if not bullets:
            bullets = [item.get("summary", ""), *(item.get("highlights") or [])]
        bullets = _clean_bullets(bullets, max_items=6)
        meta = " - ".join(
            value
            for value in [
                sanitize_line(item.get("company"), 140),
                sanitize_line(item.get("location"), 120),
                _date_label(item.get("start_date"), item.get("end_date")),
            ]
            if value
        )
        bullets_html = "".join(f"<li>{_escape_html(bullet, 240)}</li>" for bullet in bullets)
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
        technologies = sanitize_string_list(item.get("technologies"), max_items=10, max_length=80)
        if technologies:
            bullets = [*bullets, f"Technologies: {', '.join(technologies)}"]
        bullets = _clean_bullets(bullets, max_items=6)
        bullets_html = "".join(f"<li>{_escape_html(bullet, 240)}</li>" for bullet in bullets)
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
        note = education_rewrites.get(item.get("id")) or item.get("summary") or ""
        education_html.append(
            f"""
            <div class="entry">
              <div class="entry-header">
                <span class="entry-title">{_escape_html(title, 220)}</span>
                <span class="entry-meta">{_escape_html(meta, 220)}</span>
              </div>
              {f'<p class="entry-note">{_escape_html(note, 260)}</p>' if note else ''}
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
      padding: 18mm 16mm 16mm;
    }}
    .template-classic .page {{
      padding-top: 16mm;
    }}
    .template-banking .page {{
      padding-top: 14mm;
    }}
    .template-casual .page {{
      padding-top: 18mm;
      background:
        linear-gradient(90deg, {colors['light']} 0 16mm, #ffffff 16mm 100%);
      padding-left: 24mm;
    }}
    .cv-header {{
      border-bottom: 2px solid {colors['primary']};
      padding-bottom: 10px;
      margin-bottom: 12px;
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
      font-size: 26px;
      line-height: 1.05;
      letter-spacing: -0.02em;
      font-weight: 700;
    }}
    .headline {{
      margin: 6px 0 0;
      font-size: 12px;
      color: #51606f;
      font-weight: 500;
    }}
    .contact-line {{
      margin-top: 8px;
      font-size: 10px;
      color: #5c6978;
      line-height: 1.5;
    }}
    .contact-item {{
      white-space: nowrap;
    }}
    .sep {{
      color: #b8c0c8;
      margin: 0 4px;
    }}
    .cv-section {{
      margin-bottom: 12px;
      break-inside: avoid;
    }}
    .section-title {{
      margin: 0 0 6px;
      font-size: 10px;
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
      font-size: 11px;
      line-height: 1.48;
      color: #22303d;
    }}
    .extras-block p + p {{
      margin-top: 4px;
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
      font-size: 11.5px;
      font-weight: 700;
      color: #17212b;
    }}
    .entry-meta {{
      flex-shrink: 0;
      text-align: right;
      font-size: 9.5px;
      color: #61707f;
    }}
    .entry-bullets {{
      margin: 4px 0 0;
      padding-left: 16px;
      font-size: 10.5px;
      color: #243241;
      line-height: 1.42;
    }}
    .entry-bullets li {{
      margin-bottom: 2px;
    }}
    .entry-note {{
      margin: 4px 0 0;
      font-size: 10.5px;
      color: #314253;
      line-height: 1.42;
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

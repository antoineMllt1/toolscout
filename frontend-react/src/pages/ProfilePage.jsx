import { useEffect, useMemo, useState } from 'react'
import { useAuth } from '../context/AuthContext'

const EMPTY_PROFILE = {
  title: 'Main profile', full_name: '', headline: '', email: '',
  phone: '', location: '', website: '', linkedin: '', github: '',
  portfolio_url: '', summary: '', cv_text: '',
  target_roles: [], skills: [], languages: [], certifications: [],
  experience: [], projects: [], education: [],
}

function asArray(v) {
  if (Array.isArray(v)) return v
  if (typeof v === 'string') return v.split(/\n|,/).map((s) => s.trim()).filter(Boolean)
  return []
}

function asString(v) {
  if (typeof v === 'string') return v
  if (typeof v === 'number' || typeof v === 'boolean') return String(v)
  if (v && typeof v === 'object') {
    const first = [v.title, v.name, v.label, v.summary, v.brief, v.prompt].find((s) => typeof s === 'string' && s.trim())
    if (first) return first
    try { return JSON.stringify(v) } catch { return '' }
  }
  return ''
}

function asStringArray(v) { return asArray(v).map((i) => asString(i).trim()).filter(Boolean) }
function parseList(v) { return asArray(v) }
function formatList(v) { return asStringArray(v).join(', ') }

function makeId() {
  return typeof globalThis?.crypto?.randomUUID === 'function'
    ? globalThis.crypto.randomUUID()
    : `local-${Math.random().toString(36).slice(2, 11)}`
}

function normList(entries) { return Array.isArray(entries) ? entries.filter((i) => i && typeof i === 'object') : [] }

function normalizeProfile(raw) {
  const p = { ...EMPTY_PROFILE, ...(raw || {}) }
  p.target_roles  = asArray(p.target_roles)
  p.skills        = asStringArray(p.skills)
  p.languages     = asStringArray(p.languages)
  p.certifications= asStringArray(p.certifications)
  p.experience    = normList(p.experience).map((i) => ({ ...blankExp(),  ...i, highlights: asStringArray(i.highlights), skills: asStringArray(i.skills) }))
  p.projects      = normList(p.projects).map((i)   => ({ ...blankProj(), ...i, highlights: asStringArray(i.highlights), technologies: asStringArray(i.technologies) }))
  p.education     = normList(p.education).map((i)  => ({ ...blankEdu(),  ...i, highlights: asStringArray(i.highlights), skills: asStringArray(i.skills) }))
  p.student_guidance   = { ...(p.student_guidance || {}),   role_tracks: asStringArray(p.student_guidance?.role_tracks), story_starters: normList(p.student_guidance?.story_starters).map((i) => ({ ...i, title: asString(i.title), when_to_use: asString(i.when_to_use), prompt: asString(i.prompt) })) }
  p.application_plan   = { ...(p.application_plan || {}),   priority_actions: asStringArray(p.application_plan?.priority_actions) }
  p.interview_prep     = { ...(p.interview_prep || {}),     role_question_sets: normList(p.interview_prep?.role_question_sets) }
  p.candidate_brief    = { ...(p.candidate_brief || {}),    strengths: asStringArray(p.candidate_brief?.strengths), project_highlights: asStringArray(p.candidate_brief?.project_highlights) }
  return p
}

function blankExp()  { return { id: makeId(), company: '', title: '', location: '', start_date: '', end_date: '', summary: '', highlights: [], skills: [], featured: false } }
function blankProj() { return { id: makeId(), name: '', role: '', url: '', summary: '', highlights: [], technologies: [], featured: false } }
function blankEdu()  { return { id: makeId(), school: '', degree: '', field: '', location: '', start_date: '', end_date: '', summary: '', highlights: [], skills: [], featured: false } }

export default function ProfilePage() {
  const { authFetch, user } = useAuth()
  const [profile, setProfile] = useState(EMPTY_PROFILE)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')
  const [importingPortfolio, setImportingPortfolio] = useState(false)

  useEffect(() => { void loadProfile() }, [])

  async function loadProfile() {
    setLoading(true)
    try {
      const r = await authFetch('/api/cv/profile')
      if (r.ok) setProfile(normalizeProfile(await r.json()))
    } finally { setLoading(false) }
  }

  async function saveProfile(e) {
    e?.preventDefault()
    setSaving(true); setError(''); setSaved(false)
    try {
      const r = await authFetch('/api/cv/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profile),
      })
      if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.detail || 'Unable to save profile') }
      setProfile(normalizeProfile(await r.json()))
      setSaved(true)
      window.setTimeout(() => setSaved(false), 2600)
    } catch (err) { setError(err.message) }
    finally { setSaving(false) }
  }

  async function importPortfolio() {
    if (!profile.portfolio_url) return
    setImportingPortfolio(true); setError('')
    try {
      const r = await authFetch('/api/cv/portfolio/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ portfolio_url: profile.portfolio_url }),
      })
      if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.detail || 'Import failed') }
      const payload = await r.json()
      setProfile(normalizeProfile(payload.profile))
      setSaved(true); window.setTimeout(() => setSaved(false), 2600)
    } catch (err) { setError(err.message) }
    finally { setImportingPortfolio(false) }
  }

  function upd(field, value)                { setProfile((p) => ({ ...p, [field]: value })) }
  function updEntry(sec, idx, field, value) {
    setProfile((p) => ({ ...p, [sec]: p[sec].map((item, i) => i === idx ? { ...item, [field]: value } : item) }))
  }
  function addEntry(sec) {
    setProfile((p) => ({ ...p, [sec]: [...p[sec], sec === 'experience' ? blankExp() : sec === 'projects' ? blankProj() : blankEdu()] }))
  }
  function removeEntry(sec, idx) {
    setProfile((p) => ({ ...p, [sec]: p[sec].filter((_, i) => i !== idx) }))
  }

  const readiness = profile.application_plan?.readiness_score || 0

  const stats = useMemo(() => [
    { label: 'Experience entries',  value: profile.experience?.length  || 0 },
    { label: 'Projects',            value: profile.projects?.length    || 0 },
    { label: 'Education entries',   value: profile.education?.length   || 0 },
    { label: 'Skills listed',       value: profile.skills?.length      || 0 },
  ], [profile])

  if (loading) {
    return (
      <div className="page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
        <div className="spinner spinner--lg" />
      </div>
    )
  }

  return (
    <div className="page fade-up">
      <div className="page-header">
        <div className="page-header__eyebrow">Profile</div>
        <h1 className="page-header__title">Your candidate base profile</h1>
        <p className="page-header__sub">
          This is the source the AI reads when tailoring CVs and prep dossiers. The more concrete content here, the stronger every output becomes.
        </p>
      </div>

      {/* Readiness + stats */}
      <div className="card" style={{ marginBottom: 'var(--s5)' }}>
        <div className="row-between">
          <div className="row" style={{ gap: 'var(--s5)' }}>
            <div>
              <div style={{ fontFamily: 'var(--font-d)', fontSize: '1.5rem', fontWeight: 800, letterSpacing: '-0.02em' }}>
                {readiness}%
              </div>
              <div className="muted">readiness score</div>
            </div>
            {stats.map((s) => (
              <div key={s.label}>
                <div style={{ fontFamily: 'var(--font-d)', fontSize: '1.25rem', fontWeight: 800, letterSpacing: '-0.02em' }}>
                  {s.value}
                </div>
                <div className="muted">{s.label.toLowerCase()}</div>
              </div>
            ))}
          </div>
          <div className="button-row">
            <button type="button" className="btn" onClick={saveProfile} disabled={saving}>
              {saving ? 'Saving…' : 'Save profile'}
            </button>
            {saved && <span className="pill success">Saved</span>}
          </div>
        </div>
      </div>

      <div>
        {/* ── Full-width form ─────────────────────── */}
        <form className="stack" onSubmit={saveProfile}>

          {/* Identity */}
          <div className="card stack-s">
            <div className="row-between">
              <div>
                <h2 className="section-title">Identity &amp; positioning</h2>
                <p className="section-copy" style={{ marginTop: 'var(--s1)' }}>
                  Basics used on every generated CV.
                </p>
              </div>
              <span className="pill brand">{user?.email}</span>
            </div>

            <div className="grid-2">
              <F label="Full name"      value={profile.full_name} onChange={(v) => upd('full_name', v)} />
              <F label="Headline"       value={profile.headline}  onChange={(v) => upd('headline', v)}  placeholder="Backend student building APIs and automation tools" />
              <F label="Email"          value={profile.email}     onChange={(v) => upd('email', v)} />
              <F label="Phone"          value={profile.phone}     onChange={(v) => upd('phone', v)} />
              <F label="Location"       value={profile.location}  onChange={(v) => upd('location', v)} />
              <F label="Profile title"  value={profile.title}     onChange={(v) => upd('title', v)} />
            </div>

            <div className="grid-3">
              <F label="Website"  value={profile.website}  onChange={(v) => upd('website', v)} />
              <F label="LinkedIn" value={profile.linkedin} onChange={(v) => upd('linkedin', v)} />
              <F label="GitHub"   value={profile.github}   onChange={(v) => upd('github', v)} />
            </div>

            <TA
              label="Professional summary"
              hint="High-level positioning used across CVs and prep"
              value={profile.summary}
              onChange={(v) => upd('summary', v)}
              rows={5}
              placeholder="Explain what you know, what roles you want, and the impact you can create quickly."
            />
          </div>

          {/* Targeting */}
          <div className="card stack-s">
            <h2 className="section-title">Targeting &amp; signal</h2>
            <p className="section-copy" style={{ marginTop: 'var(--s1)' }}>
              These fields drive keyword matching and prep recommendations.
            </p>

            <div className="grid-2">
              <TA label="Target roles"    hint="Comma or line separated" value={formatList(profile.target_roles)}   onChange={(v) => upd('target_roles', parseList(v))}  rows={2} placeholder="Backend intern, AI product intern" />
              <TA label="Skills"          hint="Comma or line separated" value={formatList(profile.skills)}         onChange={(v) => upd('skills', parseList(v))}         rows={3} placeholder="Python, FastAPI, SQL, React" />
              <TA label="Languages"                                       value={formatList(profile.languages)}      onChange={(v) => upd('languages', parseList(v))}      rows={2} placeholder="French, English" />
              <TA label="Certifications"                                  value={formatList(profile.certifications)} onChange={(v) => upd('certifications', parseList(v))} rows={2} placeholder="AWS Cloud Practitioner" />
            </div>

            <TA
              label="Master CV text"
              hint="Paste a full CV for extra context (optional)"
              value={profile.cv_text}
              onChange={(v) => upd('cv_text', v)}
              rows={6}
              placeholder="Paste the full raw CV text here for the backend to have more context when matching and selecting."
            />
          </div>

          {/* Portfolio import */}
          <div className="card stack-s">
            <div className="row-between">
              <div>
                <h2 className="section-title">Portfolio import</h2>
                <p className="section-copy" style={{ marginTop: 'var(--s1)' }}>Pull project signals from a public portfolio URL.</p>
              </div>
              <button
                type="button"
                className="btn-soft"
                onClick={importPortfolio}
                disabled={importingPortfolio || !profile.portfolio_url}
              >
                {importingPortfolio ? 'Importing…' : 'Import'}
              </button>
            </div>
            <F label="Portfolio URL" value={profile.portfolio_url} onChange={(v) => upd('portfolio_url', v)} placeholder="https://your-portfolio.com" />
            {profile.portfolio_last_scraped_at && (
              <p className="muted">Last imported {new Date(profile.portfolio_last_scraped_at).toLocaleString()}</p>
            )}
          </div>

          {/* Experience */}
          <Section
            title="Experience"
            hint="Internships, jobs, freelance work, student associations."
            items={profile.experience}
            onAdd={() => addEntry('experience')}
            addLabel="Add experience"
          >
            {profile.experience.map((item, idx) => (
              <div key={item.id} className="entry-editor">
                <div className="entry-editor__header">
                  <div>
                    <div className="item-title">{item.title || item.company || 'New experience'}</div>
                    <div className="item-subtitle">{item.company || 'Add title, company, scope, and actions you owned'}</div>
                  </div>
                  <div className="entry-editor__actions">
                    <button type="button" className={item.featured ? 'btn-soft btn-sm' : 'btn-ghost btn-sm'} onClick={() => updEntry('experience', idx, 'featured', !item.featured)}>
                      {item.featured ? 'Featured' : 'Mark featured'}
                    </button>
                    <button type="button" className="btn-danger btn-sm" onClick={() => removeEntry('experience', idx)}>Remove</button>
                  </div>
                </div>
                <div className="entry-editor__grid">
                  <F label="Title"      value={item.title}      onChange={(v) => updEntry('experience', idx, 'title', v)} />
                  <F label="Company"    value={item.company}    onChange={(v) => updEntry('experience', idx, 'company', v)} />
                  <F label="Location"   value={item.location}   onChange={(v) => updEntry('experience', idx, 'location', v)} />
                  <F label="Start date" value={item.start_date} onChange={(v) => updEntry('experience', idx, 'start_date', v)} placeholder="Sep 2025" />
                  <F label="End date"   value={item.end_date}   onChange={(v) => updEntry('experience', idx, 'end_date', v)}   placeholder="Present" />
                  <F label="Skills used" hint="Comma separated" value={formatList(item.skills)} onChange={(v) => updEntry('experience', idx, 'skills', parseList(v))} />
                </div>
                <TA label="Summary" value={item.summary} onChange={(v) => updEntry('experience', idx, 'summary', v)} rows={3} placeholder="What was the mission and in what context?" />
                <TA label="Highlights" hint="One action or result per line" value={(item.highlights || []).join('\n')} onChange={(v) => updEntry('experience', idx, 'highlights', parseList(v))} />
              </div>
            ))}
          </Section>

          {/* Projects */}
          <Section
            title="Projects"
            hint="Independent, freelance, school, hackathon, or startup projects."
            items={profile.projects}
            onAdd={() => addEntry('projects')}
            addLabel="Add project"
          >
            {profile.projects.map((item, idx) => (
              <div key={item.id} className="entry-editor">
                <div className="entry-editor__header">
                  <div>
                    <div className="item-title">{item.name || item.role || 'New project'}</div>
                    <div className="item-subtitle">{item.role || 'Scope, decisions, technologies, and a URL when you have one'}</div>
                  </div>
                  <div className="entry-editor__actions">
                    <button type="button" className={item.featured ? 'btn-soft btn-sm' : 'btn-ghost btn-sm'} onClick={() => updEntry('projects', idx, 'featured', !item.featured)}>
                      {item.featured ? 'Featured' : 'Mark featured'}
                    </button>
                    <button type="button" className="btn-danger btn-sm" onClick={() => removeEntry('projects', idx)}>Remove</button>
                  </div>
                </div>
                <div className="entry-editor__grid">
                  <F label="Project name"  value={item.name} onChange={(v) => updEntry('projects', idx, 'name', v)} />
                  <F label="Role"          value={item.role} onChange={(v) => updEntry('projects', idx, 'role', v)} />
                  <F label="URL"           value={item.url}  onChange={(v) => updEntry('projects', idx, 'url', v)} placeholder="https://github.com/..." />
                  <F label="Technologies"  hint="Comma separated" value={formatList(item.technologies)} onChange={(v) => updEntry('projects', idx, 'technologies', parseList(v))} />
                </div>
                <TA label="Summary" value={item.summary} onChange={(v) => updEntry('projects', idx, 'summary', v)} rows={3} placeholder="What problem did it solve and why did it matter?" />
                <TA label="Highlights" hint="Decisions, implementation, results — one per line" value={(item.highlights || []).join('\n')} onChange={(v) => updEntry('projects', idx, 'highlights', parseList(v))} />
              </div>
            ))}
          </Section>

          {/* Education */}
          <Section
            title="Education"
            hint="Degrees, schools, relevant coursework, and formations."
            items={profile.education}
            onAdd={() => addEntry('education')}
            addLabel="Add education"
          >
            {profile.education.map((item, idx) => (
              <div key={item.id} className="entry-editor">
                <div className="entry-editor__header">
                  <div>
                    <div className="item-title">{item.degree || item.school || 'New education'}</div>
                    <div className="item-subtitle">{item.school || 'Degree, school, track, and relevant coursework'}</div>
                  </div>
                  <div className="entry-editor__actions">
                    <button type="button" className={item.featured ? 'btn-soft btn-sm' : 'btn-ghost btn-sm'} onClick={() => updEntry('education', idx, 'featured', !item.featured)}>
                      {item.featured ? 'Featured' : 'Mark featured'}
                    </button>
                    <button type="button" className="btn-danger btn-sm" onClick={() => removeEntry('education', idx)}>Remove</button>
                  </div>
                </div>
                <div className="entry-editor__grid">
                  <F label="School"     value={item.school}     onChange={(v) => updEntry('education', idx, 'school', v)} />
                  <F label="Degree"     value={item.degree}     onChange={(v) => updEntry('education', idx, 'degree', v)} />
                  <F label="Field"      value={item.field}      onChange={(v) => updEntry('education', idx, 'field', v)} />
                  <F label="Location"   value={item.location}   onChange={(v) => updEntry('education', idx, 'location', v)} />
                  <F label="Start date" value={item.start_date} onChange={(v) => updEntry('education', idx, 'start_date', v)} />
                  <F label="End date"   value={item.end_date}   onChange={(v) => updEntry('education', idx, 'end_date', v)} />
                </div>
                <TA label="Summary" value={item.summary} onChange={(v) => updEntry('education', idx, 'summary', v)} rows={3} placeholder="Specialisation, context, or positioning for recruiters" />
                <div className="entry-editor__grid">
                  <TA label="Highlights" value={(item.highlights || []).join('\n')} onChange={(v) => updEntry('education', idx, 'highlights', parseList(v))} />
                  <TA label="Skills / coursework" value={(item.skills || []).join('\n')} onChange={(v) => updEntry('education', idx, 'skills', parseList(v))} />
                </div>
              </div>
            ))}
          </Section>

          {error && <div className="callout callout--error">{error}</div>}

          <div className="button-row" style={{ paddingBottom: 'var(--s7)' }}>
            <button type="submit" className="btn" disabled={saving}>
              {saving ? 'Saving profile…' : 'Save profile'}
            </button>
            {saved && <span className="pill success">Saved</span>}
          </div>
        </form>
      </div>

      {/* AI signals sidebar (shown as a separate card below) */}
      {(profile.candidate_brief?.strengths?.length > 0 || profile.application_plan?.priority_actions?.length > 0) && (
        <div className="grid-2" style={{ marginTop: 'var(--s5)', gap: 'var(--s4)', paddingBottom: 'var(--s7)' }}>
          {profile.candidate_brief?.strengths?.length > 0 && (
            <div className="card stack-s">
              <h3 className="section-title">AI candidate brief</h3>
              <div className="badge-row">
                {profile.candidate_brief.strengths.map((s) => <span key={s} className="pill brand">{s}</span>)}
              </div>
              {profile.candidate_brief?.project_highlights?.length > 0 && (
                <div className="timeline-list">
                  {profile.candidate_brief.project_highlights.map((h) => (
                    <div key={h} className="callout">{h}</div>
                  ))}
                </div>
              )}
            </div>
          )}

          {profile.application_plan?.priority_actions?.length > 0 && (
            <div className="card stack-s">
              <h3 className="section-title">Priority actions</h3>
              <ol className="note-list">
                {profile.application_plan.priority_actions.map((a) => <li key={a}>{a}</li>)}
              </ol>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/* ── Helpers ─────────────────────────────────────────────── */

function Section({ title, hint, items, onAdd, addLabel, children }) {
  return (
    <div className="card stack-s">
      <div className="row-between">
        <div>
          <h2 className="section-title">{title}</h2>
          {hint && <p className="section-copy" style={{ marginTop: 'var(--s1)' }}>{hint}</p>}
        </div>
        <button type="button" className="btn-soft btn-sm" onClick={onAdd}>{addLabel}</button>
      </div>
      {items.length === 0 ? (
        <div className="callout">Nothing here yet. Add at least one concrete, strong entry.</div>
      ) : (
        <div className="stack-s">{children}</div>
      )}
    </div>
  )
}

function F({ label, hint, value, onChange, placeholder = '' }) {
  return (
    <div className="field-stack">
      <div className="field-label">
        {label}
        {hint && <span className="field-hint">{hint}</span>}
      </div>
      <input value={value || ''} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
    </div>
  )
}

function TA({ label, hint, value, onChange, rows = 4, placeholder = '' }) {
  return (
    <div className="field-stack">
      <div className="field-label">
        {label}
        {hint && <span className="field-hint">{hint}</span>}
      </div>
      <textarea rows={rows} value={value || ''} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
    </div>
  )
}

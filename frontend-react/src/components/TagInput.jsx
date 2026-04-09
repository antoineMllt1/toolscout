import { useState } from 'react'

export default function TagInput({ label, placeholder, value, onChange }) {
  const [draft, setDraft] = useState('')

  const commitDraft = () => {
    const next = draft.trim()
    if (!next) return
    if (value.includes(next)) { setDraft(''); return }
    onChange([...value, next])
    setDraft('')
  }

  return (
    <div className="tag-input-wrapper">
      {label && <span className="tag-input-label">{label}</span>}
      <div className="tag-input-field">
        {value.map((item) => (
          <span key={item} className="tag-pill">
            {item}
            <button
              type="button"
              onClick={() => onChange(value.filter((entry) => entry !== item))}
              aria-label={`Retirer ${item}`}
            >
              ×
            </button>
          </span>
        ))}
        <input
          className="tag-input-inner"
          value={draft}
          placeholder={value.length ? '' : placeholder}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ',') {
              event.preventDefault()
              commitDraft()
            }
            if (event.key === 'Backspace' && !draft && value.length) {
              onChange(value.slice(0, -1))
            }
          }}
          onBlur={commitDraft}
        />
      </div>
    </div>
  )
}

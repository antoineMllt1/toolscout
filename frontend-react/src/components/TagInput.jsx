import { useState } from 'react'

export default function TagInput({ label, placeholder, value, onChange }) {
  const [draft, setDraft] = useState('')

  const commitDraft = () => {
    const next = draft.trim()
    if (!next) return
    if (value.includes(next)) {
      setDraft('')
      return
    }
    onChange([...value, next])
    setDraft('')
  }

  return (
    <label className="field-stack">
      <span>{label}</span>
      <div className="tag-input-shell">
        {value.map((item) => (
          <button
            key={item}
            type="button"
            className="tag-chip"
            onClick={() => onChange(value.filter((entry) => entry !== item))}
          >
            {item}
          </button>
        ))}
        <input
          value={draft}
          placeholder={placeholder}
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
    </label>
  )
}

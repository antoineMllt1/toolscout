function FilterGroup({ title, options, values, onToggle }) {
  if (!options.length) return null

  return (
    <section className="filter-group">
      <header className="filter-group-head">
        <p className="filter-group-title">{title}</p>
      </header>

      <div className="filter-chip-list">
        {options.map((option) => {
          const active = values.includes(option.value)
          return (
            <button
              key={option.value}
              className={`filter-chip ${active ? 'is-active' : ''}`}
              onClick={() => onToggle(option.value)}
              title={option.label}
            >
              <span>{option.label}</span>
              <small>{option.count}</small>
            </button>
          )
        })}
      </div>
    </section>
  )
}

export default function FilterBar({ filters, setFilters, options, resultCount }) {
  const updateSet = (field, value) => {
    setFilters((prev) => {
      const current = prev[field]
      return {
        ...prev,
        [field]: current.includes(value)
          ? current.filter((item) => item !== value)
          : [...current, value],
      }
    })
  }

  const clearFilters = () => {
    setFilters((prev) => ({
      ...prev,
      source: [],
      contract: [],
      remote: [],
      seniority: [],
      location: [],
      query: '',
    }))
  }

  return (
    <aside className="filter-sidebar">
      <div className="filter-sidebar-head">
        <div>
          <p className="eyebrow">Filtrage</p>
          <div className="filter-sidebar-stat">
            <strong>{resultCount}</strong>
            <span>cartes visibles</span>
          </div>
        </div>
        <button className="secondary-button filter-reset-button" onClick={clearFilters}>
          Reinitialiser
        </button>
      </div>

      <label className="field-stack">
        <span>Recherche locale</span>
        <input
          value={filters.query}
          onChange={(event) => setFilters((prev) => ({ ...prev, query: event.target.value }))}
          placeholder="Titre, entreprise, extrait"
        />
      </label>

      <label className="field-stack">
        <span>Trier</span>
        <select
          value={filters.sort}
          onChange={(event) => setFilters((prev) => ({ ...prev, sort: event.target.value }))}
        >
          <option value="recent">Plus recent</option>
          <option value="company">Entreprise A-Z</option>
          <option value="title">Titre A-Z</option>
        </select>
      </label>

      <FilterGroup
        title="Sources"
        options={options.source}
        values={filters.source}
        onToggle={(value) => updateSet('source', value)}
      />
      <FilterGroup
        title="Contrats"
        options={options.contract}
        values={filters.contract}
        onToggle={(value) => updateSet('contract', value)}
      />
      <FilterGroup
        title="Mode"
        options={options.remote}
        values={filters.remote}
        onToggle={(value) => updateSet('remote', value)}
      />
      <FilterGroup
        title="Niveau"
        options={options.seniority}
        values={filters.seniority}
        onToggle={(value) => updateSet('seniority', value)}
      />
      <FilterGroup
        title="Villes"
        options={options.location}
        values={filters.location}
        onToggle={(value) => updateSet('location', value)}
      />
    </aside>
  )
}

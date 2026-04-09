function MultiSelect({ label, options, value, onChange }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: '#9AABB8' }}>
        {label}
      </p>
      <div className="flex flex-wrap gap-1.5">
        {options.map(opt => {
          const active = value.includes(opt.value)
          return (
            <button
              key={opt.value}
              onClick={() =>
                onChange(active ? value.filter(v => v !== opt.value) : [...value, opt.value])
              }
              className="px-3 py-1 rounded-full text-xs font-medium border transition-all"
              style={
                active
                  ? { background: '#6B9BC8', color: '#fff', borderColor: '#6B9BC8' }
                  : { background: '#fff', color: '#6B7B90', borderColor: '#D6DFF0' }
              }
            >
              {opt.label} {opt.count !== undefined && `(${opt.count})`}
            </button>
          )
        })}
      </div>
    </div>
  )
}

export default function FilterBar({ results, filters, setFilters }) {
  // Build option lists from current results
  const sources = [...new Set(results.map(r => r.source).filter(Boolean))]
  const contracts = [...new Set(results.map(r => r.contract_type).filter(Boolean))].sort()
  const locations = [...new Set(results.map(r => r.location).filter(Boolean))].sort()

  const sourceLabels = { wttj: 'WTTJ', indeed: 'Indeed', jobteaser: 'Jobteaser' }

  function count(field, val) {
    return results.filter(r => r[field] === val).length
  }

  const sortOpts = [
    { value: 'recent', label: 'Plus récent' },
    { value: 'company', label: 'Entreprise A→Z' },
    { value: 'title', label: 'Titre A→Z' },
  ]

  return (
    <div
      className="rounded-2xl border p-5 space-y-5"
      style={{ background: '#fff', borderColor: '#D6DFF0' }}
    >
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-sm" style={{ color: '#2C3E50' }}>Filtres</h2>
        {(filters.sources.length > 0 || filters.contracts.length > 0 || filters.locations.length > 0) && (
          <button
            onClick={() => setFilters({ sources: [], contracts: [], locations: [], sort: filters.sort })}
            className="text-xs underline"
            style={{ color: '#9AABB8' }}
          >
            Effacer
          </button>
        )}
      </div>

      {/* Sort */}
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: '#9AABB8' }}>Trier</p>
        <select
          value={filters.sort}
          onChange={e => setFilters({ ...filters, sort: e.target.value })}
          className="w-full rounded-lg border px-3 py-1.5 text-sm focus:outline-none"
          style={{ borderColor: '#D6DFF0', color: '#2C3E50' }}
        >
          {sortOpts.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>

      {/* Source */}
      <MultiSelect
        label="Source"
        options={sources.map(s => ({ value: s, label: sourceLabels[s] || s, count: count('source', s) }))}
        value={filters.sources}
        onChange={v => setFilters({ ...filters, sources: v })}
      />

      {/* Contract */}
      {contracts.length > 0 && (
        <MultiSelect
          label="Contrat"
          options={contracts.map(c => ({ value: c, label: c, count: count('contract_type', c) }))}
          value={filters.contracts}
          onChange={v => setFilters({ ...filters, contracts: v })}
        />
      )}

      {/* Location */}
      {locations.length > 0 && (
        <MultiSelect
          label="Lieu"
          options={locations.slice(0, 10).map(l => ({ value: l, label: l, count: count('location', l) }))}
          value={filters.locations}
          onChange={v => setFilters({ ...filters, locations: v })}
        />
      )}
    </div>
  )
}

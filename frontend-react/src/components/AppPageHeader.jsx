export function HeaderStat({ label, value, tone = '' }) {
  return (
    <article className={`app-header-stat ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  )
}

export default function AppPageHeader({ eyebrow, title, description, actions, stats }) {
  return (
    <section className="app-page-header fade-stagger" style={{ '--index': 0 }}>
      <div className="app-page-header-main">
        <div className="app-page-header-copy">
          {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
          <h1>{title}</h1>
          {description ? <p>{description}</p> : null}
        </div>
        {actions ? <div className="app-page-actions">{actions}</div> : null}
      </div>
      {stats?.length ? (
        <div className="app-page-stats">
          {stats.map((item) => (
            <HeaderStat key={item.label} {...item} />
          ))}
        </div>
      ) : null}
    </section>
  )
}

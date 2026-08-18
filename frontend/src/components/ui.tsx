import type { ReactNode } from 'react'

export function Spinner() {
  return <span className="spinner" aria-hidden="true" />
}

export function Panel({
  title,
  action,
  children,
}: {
  title: ReactNode
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="panel">
      <div className="panel__header">
        <h2 className="panel__title">{title}</h2>
        {action}
      </div>
      <div className="panel__body">{children}</div>
    </section>
  )
}

export function Chip({
  tone,
  children,
}: {
  tone: 'blue' | 'green' | 'red' | 'amber' | 'gray' | 'violet' | 'amber-dark'
  children: ReactNode
}) {
  return <span className={`chip chip--${tone}`}>{children}</span>
}

export function Alert({
  tone,
  title,
  children,
}: {
  tone: 'error' | 'success' | 'info'
  title: string
  children?: ReactNode
}) {
  const icon = tone === 'error' ? '⛔' : tone === 'success' ? '✅' : 'ℹ️'
  return (
    <div className={`alert alert--${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      <span className="alert__icon" aria-hidden="true">
        {icon}
      </span>
      <div className="alert__body">
        <div className="alert__title">{title}</div>
        {children ? <div className="alert__detail">{children}</div> : null}
      </div>
    </div>
  )
}

export function EmptyState({ icon, children }: { icon: string; children: ReactNode }) {
  return (
    <div className="empty-state">
      <div className="empty-state__icon" aria-hidden="true">
        {icon}
      </div>
      {children}
    </div>
  )
}

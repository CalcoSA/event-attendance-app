import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent, ReactNode } from 'react'
import { ApiError, api, apiDownload, isAbort, messageOf } from './api'
import type { AttendanceMember, AttendanceSummary, EventContext, Participant, User } from './types'
import { useConnection } from './useConnection'

type IconName = 'check' | 'search' | 'arrow' | 'people' | 'calendar' | 'bus' | 'download' | 'logout' | 'eye' | 'eye-off' | 'wifi' | 'alert' | 'plus' | 'close'
function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, ReactNode> = {
    check: <path d="m5 12 4 4L19 6" />,
    search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></>,
    arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
    people: <><circle cx="9" cy="8" r="3" /><path d="M3 21v-3a6 6 0 0 1 12 0v3M16 5a3 3 0 0 1 0 6m2 4a5 5 0 0 1 3 5" /></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="3" /><path d="M7 3v4m10-4v4M3 11h18m-14 5h3m4 0h3" /></>,
    bus: <><rect x="5" y="3" width="14" height="17" rx="3" /><path d="M5 12h14M8 20v2m8-2v2M8 16h1m6 0h1M5 7h14" /></>,
    download: <path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5" />,
    logout: <path d="M9 4H4v16h5m6-13 5 5-5 5M9 12h11" />,
    eye: <><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" /></>,
    'eye-off': <><path d="m3 3 18 18M10 5h2c7 0 10 7 10 7a19 19 0 0 1-3 4M6 6a19 19 0 0 0-4 6s3 7 10 7c2 0 3-.5 4-1" /><path d="M9 9a4 4 0 0 0 6 6" /></>,
    wifi: <><path d="M2 8a16 16 0 0 1 20 0M5 12a11 11 0 0 1 14 0m-11 4a6 6 0 0 1 8 0" /><circle cx="12" cy="20" r=".5" /></>,
    alert: <><path d="m10 4-8 14a2 2 0 0 0 2 3h16a2 2 0 0 0 2-3L14 4a2.3 2.3 0 0 0-4 0ZM12 9v5m0 3v.1" /></>,
    plus: <path d="M12 5v14M5 12h14" />,
    close: <path d="m6 6 12 12M6 18 18 6" />,
  }
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>
}

function Spinner() { return <span className="spinner" aria-hidden="true" /> }
function ErrorNotice({ children }: { children: ReactNode }) { return <div className="notice error" role="alert"><Icon name="alert" /><span>{children}</span></div> }
function Brand({ light = false }: { light?: boolean }) {
  return <div className={`brand ${light ? 'brand-light' : ''}`}><span className="brand-symbol"><Icon name="calendar" size={25} /></span><span><strong>Fiesta Niños <span>2026</span></strong><small>CONTROL DE ASISTENCIA</small></span></div>
}

function Login({ onLogin, connected, sessionMessage }: { onLogin: (user: User) => void; connected: boolean; sessionMessage: string }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const lock = useRef(false)
  async function login(event: FormEvent) {
    event.preventDefault()
    if (lock.current) return
    lock.current = true
    setBusy(true)
    setError('')
    try {
      const user = await api<User>('/api/auth/login', { method: 'POST', body: JSON.stringify({ username: username.trim(), password }) })
      setPassword('')
      onLogin(user)
    } catch (err) { setError(messageOf(err)) } finally { setBusy(false); lock.current = false }
  }
  return <main className="login-layout">
    <section className="login-intro">
      <Brand light />
      <div className="intro-copy"><span className="eyebrow">6 Y 7 DE OCTUBRE</span><h1>Un gran día<br /> empieza con una<br /><em>bienvenida.</em></h1><p>Todo listo para recibir a nuestras familias.<br /> Registra cada llegada de forma sencilla.</p></div>
      <div className="intro-bottom"><span className="tiny-star">✳</span><span>Fiesta Niños 2026<span className="subtle-line">Equipo de logística</span></span><span className="intro-year">2026</span></div>
    </section>
    <section className="login-panel">
      <div className="login-card">        
        <div className="section-kicker"><span className="mini-rule" /> BIENVENIDO AL EQUIPO</div>
        <br></br>
        <p className="muted login-description">Ingresa con tu usuario de logística para comenzar a registrar asistencias.</p>
        {sessionMessage && <div className="notice warning" role="status">{sessionMessage}</div>}
        <form onSubmit={login}>
          <label htmlFor="username">Cédula / usuario</label>
          <input id="username" name="username" autoComplete="username" inputMode="numeric" placeholder="Escribe tu número de cédula" value={username} onChange={e => setUsername(e.target.value)} required disabled={busy} maxLength={50} />
          <label htmlFor="password">Contraseña</label>
          <div className="input-with-action"><input id="password" name="password" autoComplete="current-password" type={showPassword ? 'text' : 'password'} placeholder="Escribe tu contraseña" value={password} onChange={e => setPassword(e.target.value)} required disabled={busy} /><button className="input-icon" type="button" onClick={() => setShowPassword(!showPassword)} aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'} aria-pressed={showPassword}><Icon name={showPassword ? 'eye-off' : 'eye'} /></button></div>
          {error && <ErrorNotice>{error}</ErrorNotice>}
          <button className="button primary login-submit" disabled={busy || !connected}>{busy ? <Spinner /> : null}{busy ? 'Ingresando…' : 'Ingresar'}{!busy && <Icon name="arrow" />}</button>
        </form>
      </div>
      <footer>6 · 7 OCTUBRE <span>Un encuentro para compartir.</span></footer>
    </section>
  </main>
}

function PreviousAttendance({ attendance }: { attendance: AttendanceSummary }) {
  const time = new Intl.DateTimeFormat('es-CO', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'America/Bogota' }).format(new Date(attendance.checked_in_at))
  return <div className="previous-attendance">
    <div className="notice success"><Icon name="check" /><div><strong>ASISTENCIA YA REGISTRADA</strong><p>Esta persona ya fue registrada previamente.</p></div></div>
    <dl className="details-grid">
      <div><dt>Día real</dt><dd>{attendance.actual_day}</dd></div>
      <div><dt>Bus</dt><dd>{attendance.display_name}</dd></div>
      <div><dt>Fecha y hora</dt><dd>{time}</dd></div>
      <div><dt>Usuario que registró</dt><dd>{attendance.registered_by_name}<small>CC {attendance.registered_by_document}</small></dd></div>
      <div><dt>Titular presente</dt><dd>{attendance.titular_present ? 'Sí' : 'No'}</dd></div>
      <div><dt>Acompañantes reales</dt><dd>{attendance.actual_companions}</dd></div>
    </dl>
    <div className="total-row"><span>Total de personas registradas</span><strong>{attendance.total_present}</strong></div>
    <p className="muted small">Solo se permite una asistencia por persona durante todo el evento.</p>
  </div>
}

function CheckIn({ participant, context, connected, onSuccess, onDuplicate, onBusy }: {
  participant: Participant; context: EventContext; connected: boolean
  onSuccess: (summary: AttendanceSummary, participant: Participant) => void
  onDuplicate: (summary: AttendanceSummary) => void
  onBusy: (busy: boolean) => void
}) {
  const [dayId, setDayId] = useState(() => {
    const parts = new Intl.DateTimeFormat('en', { timeZone: 'America/Bogota', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date())
    const date = ['year', 'month', 'day'].map(type => parts.find(part => part.type === type)?.value).join('-')
    return context.days.find(value => value.event_date === date)?.event_day_id ?? participant.planned_day_id
  })
  const [busId, setBusId] = useState('')
  const [members, setMembers] = useState<AttendanceMember[]>(() => Array.from({ length: participant.planned_companion_count + 1 }, (_, index) => ({ member_number: index, member_type: index === 0 ? 'TITULAR' : 'COMPANION', is_present: true })))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const lock = useRef(false)
  const companions = members.filter(member => member.member_type === 'COMPANION' && member.is_present).length
  const titular = members[0].is_present
  const total = companions + Number(titular)
  const day = context.days.find(value => value.event_day_id === dayId)
  const bus = context.buses.find(value => String(value.bus_id) === busId)
  const differentDay = dayId !== participant.planned_day_id

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (lock.current || !connected || !bus || !day || total === 0) return
    lock.current = true
    setBusy(true)
    onBusy(true)
    setError('')
    try {
      const summary = await api<AttendanceSummary>('/api/attendance', {
        method: 'POST',
        body: JSON.stringify({ participant_id: participant.participant_id, actual_day_id: dayId, bus_id: bus.bus_id, members }),
      })
      onSuccess(summary, participant)
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        if (err.attendance) onDuplicate(err.attendance)
        else {
          try {
            const current = await api<Participant>(`/api/participants/${encodeURIComponent(participant.document)}`)
            if (current.attendance) onDuplicate(current.attendance)
            else setError('Esta persona ya fue registrada previamente. Busca nuevamente su cédula para ver el registro.')
          } catch (reloadError) { setError(messageOf(reloadError)) }
        }
      } else if (err instanceof ApiError && err.status === 0) {
        setError('No pudimos confirmar la respuesta del registro. Busca nuevamente esta misma cédula para comprobar si la asistencia quedó guardada antes de reintentar.')
      } else setError(messageOf(err))
    } finally { lock.current = false; setBusy(false); onBusy(false) }
  }

  return <form className="check-in-form" onSubmit={submit}>
    <fieldset disabled={busy}>
      <div className="form-section-heading"><span className="step-number">02</span><h3>Confirma la llegada</h3></div>
      <div className="field-grid"><div><label htmlFor="actual-day"><Icon name="calendar" size={17} /> Día real</label><select id="actual-day" value={dayId} onChange={e => setDayId(Number(e.target.value))} required>{context.days.map(value => <option key={value.event_day_id} value={value.event_day_id}>{value.day_label}</option>)}</select></div><div><label htmlFor="bus"><Icon name="bus" size={17} /> Bus real</label><select id="bus" value={busId} onChange={e => setBusId(e.target.value)} required><option value="">Selecciona un bus</option>{context.buses.map(value => <option key={value.bus_id} value={value.bus_id}>{value.display_name}</option>)}</select></div></div>
      {differentDay && <div className="notice warning" role="status"><Icon name="alert" /><span>Esta persona estaba programada para {participant.planned_day}, pero está siendo registrada para {day?.day_label}.</span></div>}
      {context.buses.length === 0 && <ErrorNotice>No hay buses activos disponibles. Contacta al responsable de logística.</ErrorNotice>}
      <div className="companions-heading"><h3>¿Quiénes llegaron?</h3><span>{participant.planned_companion_count} acompañantes registrados</span></div>
      <div className="member-list">{members.map(member => <label className={`member-row ${member.is_present ? 'member-present' : ''}`} key={member.member_number}><input type="checkbox" checked={member.is_present} onChange={e => setMembers(current => current.map(value => value.member_number === member.member_number ? { ...value, is_present: e.target.checked } : value))} /><span>{member.member_type === 'TITULAR' ? <><strong>Titular</strong><small>{participant.full_name}</small></> : <strong>Acompañante {member.member_number}</strong>}</span>{member.member_number > participant.planned_companion_count && <span className="extra-badge">Extra</span>}<span className="member-state">{member.is_present ? 'Presente' : 'Ausente'}</span></label>)}</div>
      <button className="button add-member" type="button" disabled={members.length >= 51} onClick={() => setMembers(current => [...current, { member_number: current.length, member_type: 'COMPANION', is_present: true }])}><Icon name="plus" size={18} />Agregar acompañante</button>
      {members.length >= 51 && <p className="muted small">Máximo 50 acompañantes.</p>}
      <div className="presence-totals"><div><span>Registrados</span><strong>{participant.planned_companion_count} <small>acompañantes</small></strong></div><div><span>Presentes</span><strong>{companions} <small>acompañantes</small></strong></div><div><span>Total presentes</span><strong>{total} <small>{total === 1 ? 'persona' : 'personas'}</small></strong></div></div>
      <div className="confirmation"><div className="confirmation-title"><Icon name="check" size={18} /><h3>Resumen de asistencia</h3></div><strong className="summary-name">{participant.full_name}</strong><p>{day?.day_label ?? 'Selecciona el día'} <span>·</span> {bus ? bus.display_name : 'Bus pendiente'}</p><p>Titular: {titular ? 'Sí' : 'No'} <span>·</span> Acompañantes: {companions} <span>·</span> Total: <strong>{total}</strong></p></div>
      {total === 0 && <div className="notice warning" role="status">Selecciona al menos una persona presente para confirmar.</div>}
      {error && <ErrorNotice>{error}</ErrorNotice>}
      <button className="button primary confirm-button" disabled={!connected || busy || !bus || !day || total === 0}>{busy ? <Spinner /> : <Icon name="check" />}{busy ? 'Registrando asistencia…' : 'Confirmar asistencia'}</button>
      <p className="form-footnote">Revisa los datos antes de confirmar. El registro es único para todo el evento.</p>
    </fieldset>
  </form>
}

function Workspace({ user, connected, onLogout }: { user: User; connected: boolean; onLogout: () => Promise<void> }) {
  const [context, setContext] = useState<EventContext | null>(null)
  const [contextError, setContextError] = useState('')
  const [contextAttempt, setContextAttempt] = useState(0)
  const [documentQuery, setDocumentQuery] = useState('')
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Participant[]>([])
  const [showResults, setShowResults] = useState(false)
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchError, setSearchError] = useState('')
  const [selected, setSelected] = useState<Participant | null>(null)
  const [selectionLoading, setSelectionLoading] = useState(false)
  const [selectionError, setSelectionError] = useState('')
  const [activeOption, setActiveOption] = useState(-1)
  const [saving, setSaving] = useState(false)
  const [loggingOut, setLoggingOut] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [actionError, setActionError] = useState('')
  const [success, setSuccess] = useState('')
  const [listRevision, setListRevision] = useState(0)
  const exactInput = useRef<HTMLInputElement>(null)
  const selectionController = useRef<AbortController | null>(null)
  const searchSequence = useRef(0)
  const exportLock = useRef(false)
  const logoutLock = useRef(false)
  const detailRef = useRef<HTMLElement>(null)

  useEffect(() => {
    const controller = new AbortController()
    setContextError('')
    api<EventContext>('/api/event/context', { signal: controller.signal }).then(setContext).catch(err => { if (!isAbort(err)) setContextError(messageOf(err)) })
    return () => controller.abort()
  }, [contextAttempt])

  useEffect(() => {
    if (!context || !connected) return
    const controller = new AbortController()
    const sequence = ++searchSequence.current
    setSearchLoading(true)
    setSearchError('')
    setActiveOption(-1)
    const timeout = window.setTimeout(() => {
      api<Participant[]>(`/api/participants?search=${encodeURIComponent(query.trim())}&limit=30`, { signal: controller.signal })
        .then(data => { if (sequence === searchSequence.current) setResults(data) })
        .catch(err => { if (!isAbort(err) && sequence === searchSequence.current) { setSearchError(messageOf(err)); setResults([]) } })
        .finally(() => { if (sequence === searchSequence.current && !controller.signal.aborted) setSearchLoading(false) })
    }, 250)
    return () => { clearTimeout(timeout); controller.abort(); searchSequence.current++ }
  }, [query, context, connected, listRevision])

  useEffect(() => () => selectionController.current?.abort(), [])

  useEffect(() => {
    // Focus after React has enabled the search input following a completed save.
    if (success && !saving && !selected) exactInput.current?.focus()
  }, [success, saving, selected])

  async function selectParticipant(document: string) {
    if (saving) return
    selectionController.current?.abort()
    const controller = new AbortController()
    selectionController.current = controller
    setSelectionLoading(true)
    setSelectionError('')
    setShowResults(false)
    setSelected(null)
    setSuccess('')
    try {
      const participant = await api<Participant>(`/api/participants/${encodeURIComponent(document.trim())}`, { signal: controller.signal })
      if (selectionController.current !== controller) return
      setSelected(participant)
      setDocumentQuery('')
      setQuery('')
      window.setTimeout(() => { detailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }); detailRef.current?.focus({ preventScroll: true }) }, 0)
    } catch (err) { if (!isAbort(err) && selectionController.current === controller) setSelectionError(messageOf(err)) }
    finally { if (selectionController.current === controller) setSelectionLoading(false) }
  }

  function clearParticipant() {
    if (saving) return
    selectionController.current?.abort()
    selectionController.current = null
    setSelectionLoading(false)
    setSelected(null)
    setSelectionError('')
    setDocumentQuery('')
    setQuery('')
    setShowResults(false)
    exactInput.current?.focus()
  }

  function onSuccess(summary: AttendanceSummary, participant: Participant) {
    setSelected(null)
    setQuery('')
    setDocumentQuery('')
    setShowResults(false)
    setSuccess(`${participant.full_name}: asistencia registrada. ${summary.display_name} · ${summary.total_present} ${summary.total_present === 1 ? 'persona' : 'personas'}.`)
    setListRevision(value => value + 1)
  }

  function onSearchKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape') { setShowResults(false); return }
    if (event.key === 'ArrowDown') { event.preventDefault(); setShowResults(true); setActiveOption(value => Math.min(value + 1, results.length - 1)) }
    if (event.key === 'ArrowUp') { event.preventDefault(); setActiveOption(value => Math.max(value - 1, 0)) }
    if (event.key === 'Enter' && showResults && activeOption >= 0 && results[activeOption]) { event.preventDefault(); void selectParticipant(results[activeOption].document) }
  }

  async function exportFile() {
    if (exportLock.current || !connected) return
    exportLock.current = true
    setExporting(true)
    setActionError('')
    try {
      const { blob, disposition } = await apiDownload('/api/export/attendance.xlsx')
      const matched = /filename="?([^";]+)"?/i.exec(disposition)
      const filename = matched?.[1] ?? 'asistencia_fiesta_ninos_2026.xlsx'
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = filename
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (err) { setActionError(messageOf(err)) }
    finally { setExporting(false); exportLock.current = false }
  }

  async function logout() {
    if (logoutLock.current || saving) return
    logoutLock.current = true
    setLoggingOut(true)
    setActionError('')
    try { await onLogout() } catch (err) { setActionError(messageOf(err)) }
    finally { setLoggingOut(false); logoutLock.current = false }
  }

  return <>
    <header className="app-header"><div className="header-inner"><Brand /><div className="header-actions"><span className={`connection-label ${connected ? '' : 'disconnected'}`}><span />{connected ? 'Conectado' : 'Sin conexión'}</span><button className="button logout-button" disabled={loggingOut || saving} onClick={() => void logout()}>{loggingOut ? <Spinner /> : <Icon name="logout" size={18} />}<span>{loggingOut ? 'Cerrando…' : 'Cerrar sesión'}</span></button></div></div></header>
    <main className="workspace">
      <section className="workspace-heading"><div><div className="section-kicker">EQUIPO DE LOGÍSTICA <span className="date-separator">/</span> 6 · 7 OCTUBRE</div><h1>Bienvenidos.</h1><p>Registrando: <strong>{user.full_name}</strong></p></div><button className="button secondary export-button" onClick={() => void exportFile()} disabled={!connected || exporting}>{exporting ? <Spinner /> : <Icon name="download" size={18} />}{exporting ? 'Preparando Excel…' : 'Exportar Excel'}</button></section>
      {actionError && <ErrorNotice>{actionError}</ErrorNotice>}
      {success && <div className="notice success success-banner" role="status"><Icon name="check" /><div><strong>¡Asistencia registrada!</strong><p>{success}</p><span>Todo listo para recibir a la siguiente persona.</span></div><button type="button" className="input-icon" aria-label="Cerrar mensaje de éxito" onClick={() => setSuccess('')}><Icon name="close" size={17} /></button></div>}
      {contextError ? <div className="context-error"><ErrorNotice>{contextError}</ErrorNotice><button className="button secondary" onClick={() => setContextAttempt(value => value + 1)} disabled={!connected}>Reintentar</button></div> : !context ? <div className="loading-block" role="status"><Spinner />Cargando información del evento…</div> : <div className="work-grid">
        <section className="card search-card"><div className="form-section-heading"><span className="step-number">01</span><h2>Busca a la persona</h2></div><p className="muted">Una cédula o un nombre.<br /> El primer paso para dar la bienvenida.</p>
          <form onSubmit={e => { e.preventDefault(); if (documentQuery.trim()) void selectParticipant(documentQuery) }}><label htmlFor="document-search">Buscar por cédula</label><div className="exact-search"><input ref={exactInput} id="document-search" inputMode="numeric" autoComplete="off" placeholder="Número de cédula" maxLength={20} value={documentQuery} disabled={saving || !connected} onChange={e => setDocumentQuery(e.target.value)} /><button className="button primary icon-button" type="submit" aria-label="Buscar por cédula" disabled={saving || !connected || !documentQuery.trim() || selectionLoading}>{selectionLoading ? <Spinner /> : <Icon name="search" />}</button></div></form>
          <div className="search-divider"><span />o busca por nombre<span /></div>
          <div className="autocomplete" onBlur={e => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setShowResults(false) }}><label htmlFor="participant-search">Buscar participante...</label><div className="search-input-wrap"><Icon name="search" size={18} /><input id="participant-search" role="combobox" aria-autocomplete="list" aria-controls="participant-results" aria-expanded={showResults} aria-activedescendant={showResults && activeOption >= 0 ? `participant-option-${activeOption}` : undefined} placeholder="Nombre o cédula" autoComplete="off" value={query} disabled={saving || !connected} maxLength={150} onChange={e => { setQuery(e.target.value); setResults([]); setShowResults(true) }} onFocus={() => setShowResults(true)} onKeyDown={onSearchKey} /></div>
            {showResults && <div className="results-popover"><div className="results-label">{query.trim() ? 'RESULTADOS DEL EVENTO' : 'PARTICIPANTES · PENDIENTES PRIMERO'}</div>{searchLoading ? <div className="results-message" role="status"><Spinner />Buscando…</div> : searchError ? <div className="results-message" role="alert">{searchError}</div> : !results.length ? <div className="results-message" role="status">No se encontraron participantes.</div> : <ul id="participant-results" role="listbox" aria-label="Participantes">{results.map((result, index) => <li id={`participant-option-${index}`} role="option" aria-selected={activeOption === index} key={result.participant_id}><button type="button" className={`result-option ${activeOption === index ? 'active-option' : ''}`} onMouseDown={e => e.preventDefault()} onClick={() => void selectParticipant(result.document)}><span><strong>{result.full_name}</strong><small>CC {result.document}</small></span>{result.already_attended ? <span className="status-badge registered">Registrado</span> : <Icon name="arrow" size={16} />}</button></li>)}</ul>}</div>}
          </div>
          {selectionError && <ErrorNotice>{selectionError}</ErrorNotice>}
          <div className="search-tip"><span className="tip-icon"><Icon name="people" size={20} /></span><p>Puedes buscar a cualquier persona del evento, sin importar su día programado.</p></div>
        </section>
        <section ref={detailRef} tabIndex={-1} aria-label="Información del participante" className={`card participant-card ${!selected ? 'participant-empty' : ''}`}>
          {selectionLoading ? <div className="loading-block" role="status"><Spinner />Consultando participante…</div> : !selected ? <div className="empty-content"><div className="empty-illustration"><span className="illustration-ring" /><span className="illustration-tile"><Icon name="people" size={44} /></span><span className="illustration-check"><Icon name="check" size={22} /></span></div><span className="section-kicker">CADA LLEGADA, UNA SONRISA</span><h2>Listos para recibir.</h2><p>Busca a la persona para consultar su<br className="desktop-break" /> información y confirmar quiénes llegaron.</p><div className="empty-steps"><span>Busca</span><i /><span>Confirma</span><i /><span>Da la bienvenida</span></div></div> : <>
            <div className="participant-topline"><span className={`status-badge ${selected.already_attended ? 'registered' : 'pending'}`}>{selected.already_attended ? 'Asistencia registrada' : 'Pendiente de asistencia'}</span><button className="button change-person" type="button" disabled={saving} onClick={clearParticipant}>Cambiar <Icon name="close" size={15} /></button></div>
            <h2 className="participant-name">{selected.full_name}</h2><p className="participant-document">CC {selected.document}</p><div className="planned-info"><div><Icon name="calendar" size={19} /><span><small>Día programado</small><strong>{selected.planned_day}</strong></span></div><div><Icon name="people" size={19} /><span><small>Acompañantes registrados</small><strong>{selected.planned_companion_count}</strong></span></div></div>
            {selected.already_attended ? selected.attendance ? <PreviousAttendance attendance={selected.attendance} /> : <div className="notice warning" role="status">ASISTENCIA YA REGISTRADA. Esta persona no puede registrarse nuevamente.</div> : <CheckIn key={selected.participant_id} participant={selected} context={context} connected={connected} onBusy={setSaving} onSuccess={onSuccess} onDuplicate={attendance => setSelected(current => current ? { ...current, already_attended: true, attendance } : null)} />}
          </>}
        </section>
      </div>}
      <footer className="app-footer"><span>FIESTA NIÑOS 2026</span><span>Un encuentro para compartir.</span></footer>
    </main>
  </>
}

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [booting, setBooting] = useState(true)
  const [sessionMessage, setSessionMessage] = useState('')
  const { connected, checking, check } = useConnection()
  const resetSession = useCallback(() => { setUser(null); setSessionMessage('La sesión terminó. Ingresa nuevamente.'); setBooting(false) }, [])

  useEffect(() => {
    window.addEventListener('session-expired', resetSession)
    const controller = new AbortController()
    api<User>('/api/auth/me', { signal: controller.signal }).then(value => { setUser(value); setSessionMessage('') }).catch(err => {
      if (!isAbort(err) && !(err instanceof ApiError && err.status === 401)) setSessionMessage(messageOf(err))
      else if (!isAbort(err)) setSessionMessage('')
    }).finally(() => { if (!controller.signal.aborted) setBooting(false) })
    return () => { controller.abort(); window.removeEventListener('session-expired', resetSession) }
  }, [resetSession])

  async function logout() {
    await api<{ message: string }>('/api/auth/logout', { method: 'POST' })
    setUser(null)
    setSessionMessage('')
  }

  return <>
    {!connected && <div className="offline-banner" role="alert"><Icon name="wifi" size={18} /><span>Sin conexión. No es posible registrar asistencias hasta recuperar Internet.</span><button type="button" onClick={() => void check()} disabled={checking}>{checking ? 'Verificando…' : 'Reintentar'}</button></div>}
    {booting ? <main className="boot-screen"><Brand /><div className="loading-block" role="status"><Spinner />Preparando tu bienvenida…</div></main> : user ? <Workspace user={user} connected={connected} onLogout={logout} /> : <Login connected={connected} sessionMessage={sessionMessage} onLogin={value => { setUser(value); setSessionMessage('') }} />}
  </>
}

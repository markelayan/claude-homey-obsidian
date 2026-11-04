// Homey mod. Read-only: runs bin/homey, which reads the vault named in .claude/homey.json.
// No paths here; the config decides band items, tabs and files.
const PANE = 'homey'
const REFRESH_MS = 15_000     // while the pane is open
const IDLE_EVERY = 4          // otherwise every 4th pass
const LATER = 'later'         // keep the question open, under For later; Homey is not woken
const QUIET = '-'             // an answer that needs no action: saved in the note, Homey is not woken
const ANSWER_CHECK_MS = 5_000 // how often held answers are looked at
const ANSWER_QUIET_PASSES = 2 // passes with no new answer before they go out
const LIFT = /^(\.ok|approved|i approve)\b/i // starts a message that lifts a guard

let data = null     // last JSON from `homey data`
let problem = ''    // last failure text, shown instead of data
let tab = ''        // id of the open pane tab
let busy = false    // a refresh is running; skip overlapping ones
let passes = 0      // timer passes, for the slower rate with the pane closed
let expanded = ''   // name of the task row open in the pane
let newOwner = ''   // owner picked for a new task
let showNew = false // New task is rarely used. It stays closed until asked for
let askOther = ''   // question showing its free-text answer
let heldAnswers = []  // answers pressed, waiting to go out as one prompt
let quietPasses = 0   // passes since the last answer pressed

async function run($, args) {
  try {
    const r = await $.process.run(['python3', $.plugin.root + '/bin/homey', ...args], { timeoutMs: 10000 })
    return r.exitCode === 0 ? { ok: true, text: r.stdout.trim() } : { ok: false, text: (r.stderr || r.stdout).trim() }
  } catch (err) {
    return { ok: false, text: String(err && err.message ? err.message : err) }
  }
}

// The watcher leaves prompts for a session open in the app. Only this session's own process can start its turn.
async function takeMessages($) {
  const r = await run($, ['take', await $.session.id()])
  if (!r.ok) return
  let messages = []
  try { messages = JSON.parse(r.text) } catch (err) { return }
  for (const m of messages) void submitMessage($, m)
}

async function submitMessage($, m) {
  if (m.notice) { await $.prompt.submit({ text: m.prompt }); return } // named as from this mod, not the user's words
  const sent = await $.prompt.submit({ text: m.prompt, asUser: true })
  if (!sent || !sent.drop) return
  await run($, ['comment', m.path, 'watcher', 'Open session dropped the message: ' + sent.drop])
  await run($, ['status', m.path, 'blocked'])
}

async function refresh($) {
  if (busy) return
  busy = true
  try {
    const r = await run($, ['data'])
    if (!r.ok) {
      problem = clip(r.text.split('\n')[0] || 'homey failed', 100)
    } else {
      try {
        const d = JSON.parse(r.text)
        if (d.error) { problem = clip('homey: ' + d.error, 100) }
        else { data = d; problem = '' }
      } catch (err) { problem = 'homey: bad data' }
    }
  } finally {
    busy = false
  }
  $.ui.invalidate('ui.render')
}

function clip(s, n) {
  return s.length > n ? s.slice(0, Math.max(0, n - 1)) + '…' : s
}

function bandText(d) {
  const parts = {
    next: 'Next: ' + (d.next || '-'),
    inbox: 'Inbox ' + d.inbox,
    stale: 'Stale ' + d.stale,
    tasks: 'Tasks ' + d.tasks,
  }
  return d.config.band.map((k) => parts[k]).filter(Boolean).join('  ·  ')
}

function paneBody(d, id, T) {
  const pane = d.config.panes.find((p) => p.id === id)
  if (!pane) return [T({ children: ['No pane ' + id + ' in homey.json'] })]
  const rows = []
  if (pane.type === 'board') {
    for (const st of d.config.statuses) {
      const items = d.projects.filter((p) => p.status === st)
      if (!items.length) continue
      rows.push(T({ weight: 'semibold', children: [st + ' (' + items.length + ')'] }))
      for (const p of items) {
        rows.push(T({ children: ['  ' + p.name + (p.stale ? ' [stale]' : '') + ' - ' + p.summary] }))
      }
    }
  } else if (pane.type === 'decisions') {
    for (const x of d.decisions) rows.push(T({ children: [x.date + '  ' + x.name.replace(/^\d{4}-\d{2}-\d{2} /, '') + ' - ' + x.summary] }))
  } else if (pane.type === 'tasks') {
    for (const a of d.tasksBoard ? d.tasksBoard.agents : []) rows.push(T({ children: [a.name + ': ' + a.state + ' - ' + a.detail] }))
    for (const x of d.tasksBoard ? d.tasksBoard.items : []) rows.push(T({ children: ['[' + x.status + '] ' + (x.owner || 'no owner') + ' - ' + (x.summary || x.name) + ' - ' + x.stateText] }))
  } else if (pane.type === 'table') {
    const t = d.tables[pane.id] || { headers: [], rows: [] }
    if (t.error) rows.push(T({ children: [t.error] }))
    for (const r of t.rows) rows.push(T({ children: ['- ' + r.join('  |  ')] }))
  }
  return rows.length ? rows : [T({ children: ['(empty)'] })]
}

// Desktop pane. One job: show what needs the user, then who is doing what.
// Rows with no borders or filled chips; a coloured dot plus a word carries each state.
const STATUS_COLOR = { idea: 'blue', active: 'green', paused: 'yellow', done: 'gray' }
const STATE_COLOR = { working: 'green', needs: 'red', held: 'yellow', queued: 'gray', done: 'gray' }
const BUG_COLOR = { reported: 'yellow', verified: 'red', 'not reproduced': 'gray', fixed: 'green' }
const DECISION_COLOR = { decided: 'cyan', 'in progress': 'yellow', done: 'green', superseded: 'gray' }
const SESSION_FILL = { working: '#16a34a', open: '#0891b2', idle: '#94a3b8' }
const SESSION_DOT = { working: 'green', open: 'cyan', idle: 'gray' }

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

// The team at a glance: one circle per session. Mid-tones read on light and dark themes.
// The app stretches the drawing to the pane, so the width is never less than a full team of 7.
function teamSvg(agents) {
  const w = 48, h = 54
  const total = Math.max(agents.length, 7) * w
  const font = 'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif"'
  const parts = agents.map((a, i) => {
    const x = i * w + w / 2
    const fill = SESSION_FILL[a.state] || SESSION_FILL.idle
    return '<circle cx="' + x + '" cy="19" r="16" fill="' + fill + '"/>' +
      '<text x="' + x + '" y="24" text-anchor="middle" fill="#fff" font-size="14" font-weight="600" ' + font + '>' + esc(a.name.slice(0, 1).toUpperCase()) + '</text>' +
      '<text x="' + x + '" y="49" text-anchor="middle" fill="#64748b" font-size="8.5" ' + font + '>' + esc(a.name.slice(0, 11)) + '</text>'
  })
  return '<svg xmlns="http://www.w3.org/2000/svg" width="' + total + '" height="' + h + '" viewBox="0 0 ' + total + ' ' + h + '">' + parts.join('') + '</svg>'
}

function paneCount(d, pane) {
  if (pane.type === 'board') return d.projects.length
  if (pane.type === 'decisions') return d.decisions.length
  if (pane.type === 'table') return ((d.tables[pane.id] || {}).rows || []).length
  if (pane.type === 'tasks') return d.tasksBoard ? (d.tasksBoard.asks || []).filter((a) => !a.later).length + d.tasksBoard.items.filter((x) => x.state === 'needs').length : 0
  return 0
}

function head(ui, key, title, count) {
  const parts = [ui.Text({ weight: 'semibold', size: 'footnote', children: [title] })]
  if (count !== undefined) parts.push(ui.Text({ dimColor: true, size: 'footnote', tabular: true, children: [String(count)] }))
  return ui.Box({ key, flexDirection: 'row', columnGap: 1, marginTop: 'sm', children: parts })
}

function row(ui, { key, color, title, meta, right, below }) {
  const lines = [ui.Text({ weight: 'medium', children: [title] })]
  if (meta) lines.push(ui.Text({ dimColor: true, size: 'caption', children: [meta] }))
  const top = []
  if (color) top.push(ui.Text({ color, children: ['●'] }))
  top.push(ui.Box({ flexDirection: 'column', flexGrow: 1, flexShrink: 1, children: lines }))
  if (right) top.push(right)
  const content = [ui.Box({ flexDirection: 'row', alignItems: 'flex-start', columnGap: 1, children: top })]
  if (below) content.push(ui.Box({ flexDirection: 'column', gap: 'xs', marginLeft: 2, children: below }))
  return ui.Box({ key, flexDirection: 'column', gap: 'xs', children: content })
}

async function act($, args) {
  const r = await run($, args)
  if (!r.ok) await $.ui.toast('Homey: ' + clip(r.text.split('\n')[0] || 'failed', 120))
  await refresh($)
}

function linkButton($, ui, key, label, link) {
  return ui.Button({ key, label, variant: 'secondary', onPress: async () => { await $.process.run(['open', link], { timeoutMs: 5000 }) } })
}

function taskRow($, ui, x) {
  const isOpen = expanded === x.name
  const toggle = ui.Button({
    key: 'more-' + x.name,
    label: isOpen ? 'Close' : 'Details',
    variant: 'secondary',
    onPress: () => { expanded = isOpen ? '' : x.name; $.ui.invalidate('ui.render') },
  })
  const below = []
  if (isOpen) {
    if (x.result) below.push(ui.Text({ size: 'footnote', children: [x.result] }))
    for (const c of x.recent) below.push(ui.Text({ dimColor: true, size: 'caption', children: [c] }))
    below.push(ui.Input({
      key: 'comment-' + x.name,
      label: 'Comment',
      placeholder: 'Tell ' + (x.owner || 'the session') + ' something',
      value: '',
      submitLabel: 'send',
      onSubmit: async (text) => { if (text.trim()) await act($, ['comment', x.name, (data && data.tasksBoard && data.tasksBoard.userId) || 'user', text]) },
    }))
    const buttons = []
    if (x.status === 'blocked') buttons.push(ui.Button({ key: 'todo-' + x.name, label: 'Run again', variant: 'secondary', onPress: async () => { await act($, ['status', x.name, 'todo']) } }))
    if (x.noteLink) buttons.push(linkButton($, ui, 'note-' + x.name, 'Open note', x.noteLink))
    if (x.link) buttons.push(linkButton($, ui, 'open-' + x.name, 'Open session', x.link))
    below.push(ui.Box({ flexDirection: 'row', flexWrap: 'wrap', columnGap: 1, rowGap: 1, children: buttons }))
  }
  return row(ui, {
    key: 'task-' + x.name,
    color: STATE_COLOR[x.state] || 'gray',
    title: x.summary || x.name,
    meta: (x.owner || 'no session') + ' · ' + x.stateText,
    right: toggle,
    below: below.length ? below : undefined,
  })
}

// Answers go to Homey as the user's own words, so the note and the chat both have them.
async function answer($, ask, text, reply) {
  const r = await run($, ['answer', ask.name, text])
  if (!r.ok) {
    await $.ui.toast('Homey: ' + clip(r.text.split('\n')[0] || 'answer not saved', 120))
    return
  }
  askOther = ''
  await refresh($)
  if (reply === QUIET) return
  const session = await $.session.id()
  // The session whose pane was pressed gets the answer, and is main from now on.
  await run($, ['claim-main', '--session', session])
  // A guard lift must start its own message, so it never waits in a batch.
  if (LIFT.test(reply)) return void $.prompt.submit({ text: oneAnswer({ ask, reply }), asUser: true })
  heldAnswers.push({ ask, reply })
  quietPasses = 0
}

function oneAnswer({ ask, reply }) {
  return reply + '\n\nThis answers the question in ' + ask.note + '. Read its Context first, act once, then record what you did in that note.'
}

function manyAnswers(list) {
  const items = list.map(({ ask, reply }, i) => (i + 1) + '. Question: ' + ask.question + '\nAnswer: ' + reply + '\nNote: ' + ask.note)
  return list.length + ' answers from the pane. For each one, read its note\'s Context first, act once, then record what you did in that note.\n\n---\n\n' + items.join('\n\n---\n\n')
}

// Answers pressed close together go out as one prompt, once the user has paused.
function flushAnswers($) {
  if (!heldAnswers.length || (quietPasses += 1) < ANSWER_QUIET_PASSES) return
  const list = heldAnswers
  heldAnswers = []
  void $.prompt.submit({ text: list.length === 1 ? oneAnswer(list[0]) : manyAnswers(list), asUser: true })
}

function askRow($, ui, ask) {
  const typed = (text) => 'Answer to "' + ask.question + '": ' + text
  const controls = ask.options.filter((o) => !(ask.later && o.reply === LATER)).map((o, i) => ui.Button({
    key: 'answer-' + ask.name + '-' + i,
    label: o.label,
    variant: i === 0 ? 'primary' : 'secondary',
    onPress: async () => { if (o.reply === LATER) await act($, ['later', ask.name]); else await answer($, ask, o.label, o.reply) },
  }))
  const typing = !ask.options.length || askOther === ask.name
  if (ask.options.length) {
    controls.push(ui.Button({
      key: 'other-' + ask.name,
      label: typing ? 'Close' : 'Other',
      variant: 'secondary',
      onPress: () => { askOther = typing ? '' : ask.name; $.ui.invalidate('ui.render') },
    }))
  }
  if (ask.noteLink) controls.push(linkButton($, ui, 'note-' + ask.name, 'Open note', ask.noteLink))
  const below = []
  if (ask.advice) for (const line of ask.advice.split('\n')) if (line.trim()) below.push(ui.Text({ size: 'footnote', children: [line.trim()] }))
  if (ask.advising) below.push(ui.Text({ dimColor: true, size: 'footnote', children: ['Advisor is thinking'] }))
  below.push(ui.Box({ flexDirection: 'row', flexWrap: 'wrap', columnGap: 1, rowGap: 1, children: controls }))
  if (typing) {
    below.push(ui.Input({
      key: 'answer-text-' + ask.name,
      label: 'Answer',
      placeholder: 'Type your answer',
      value: '',
      submitLabel: 'send',
      onSubmit: async (text) => { if (text.trim()) await answer($, ask, text.trim(), typed(text.trim())) },
    }))
  }
  return row(ui, { key: 'ask-' + ask.name, color: 'red', title: ask.question, meta: ask.why, below })
}

// A question the user put off: short until opened, then answered the same way.
function laterRow($, ui, ask) {
  const isOpen = expanded === ask.name
  const toggle = ui.Button({
    key: 'more-' + ask.name,
    label: isOpen ? 'Close' : 'Details',
    variant: 'secondary',
    onPress: () => { expanded = isOpen ? '' : ask.name; $.ui.invalidate('ui.render') },
  })
  if (isOpen) return ui.Box({ flexDirection: 'column', gap: 'xs', children: [askRow($, ui, ask), toggle] })
  const right = ask.noteLink ? ui.Box({ flexDirection: 'row', columnGap: 1, children: [linkButton($, ui, 'note-' + ask.name, 'Open note', ask.noteLink), toggle] }) : toggle
  return row(ui, { key: 'ask-' + ask.name, color: 'gray', title: ask.question, right })
}

function handoffButton($, ui, board) {
  return ui.Button({
    key: 'handoff',
    label: 'Hand off to new session',
    variant: 'secondary',
    onPress: async () => {
      const session = await $.session.id()
      await $.ui.toast('Homey: Haiku is writing the handoff note')
      let r
      try {
        r = await $.process.run(['python3', $.plugin.root + '/bin/homey', 'handoff', '--session', session], { timeoutMs: 300000 })
      } catch (err) {
        r = { exitCode: 1, stderr: String(err && err.message ? err.message : err) }
      }
      if (r.exitCode !== 0) return void (await $.ui.toast('Homey: handoff failed: ' + clip((r.stderr || r.stdout || '').trim(), 120)))
      await $.ui.toast('Homey: note written. Press Enter in the new session.')
      await $.process.run(['open', 'claude://code/new?q=' + encodeURIComponent('Read Homey/Session handoff.md and continue from its Next.')], { timeoutMs: 5000 })
    },
  })
}

function newTask($, ui, board) {
  const owners = board.agents.map((a) => a.name)
  if (!owners.length) return []
  const toggle = ui.Button({
    key: 'new-toggle',
    label: showNew ? 'Close new task' : 'New task',
    variant: 'secondary',
    onPress: () => { showNew = !showNew; $.ui.invalidate('ui.render') },
  })
  if (!showNew) return [toggle]
  if (!owners.includes(newOwner)) newOwner = owners[0]
  return [
    toggle,
    ui.Select({
      key: 'new-owner',
      label: 'For',
      value: newOwner,
      options: owners.map((o) => ({ value: o, label: o })),
      onSelect: (value) => { newOwner = value; $.ui.invalidate('ui.render') },
    }),
    ui.Input({
      key: 'new-title',
      label: 'Task',
      placeholder: 'What should ' + newOwner + ' do?',
      value: '',
      submitLabel: 'assign',
      onSubmit: async (text) => {
        if (!text.trim()) return
        const r = await run($, ['task', newOwner, clip(text.trim(), 70), text.trim()])
        if (!r.ok) await $.ui.toast('Homey: ' + clip(r.text.split('\n')[0] || 'failed', 220) + (/--files/.test(r.text) ? ' (this box has no files field: have the lead write the task)' : ''))
        await refresh($)
      },
    }),
  ]
}

function teamLegend(ui, agents) {
  const parts = []
  for (const [state, word] of [['working', 'working'], ['open', 'open in the app'], ['idle', 'free']]) {
    const n = agents.filter((a) => a.state === state).length
    if (!n) continue
    parts.push(ui.Box({ key: 'legend-' + state, flexDirection: 'row', columnGap: 1, children: [
      ui.Text({ color: SESSION_DOT[state], size: 'caption', children: ['●'] }),
      ui.Text({ dimColor: true, size: 'caption', children: [n + ' ' + word] }),
    ] }))
  }
  return ui.Box({ flexDirection: 'row', flexWrap: 'wrap', columnGap: 2, children: parts })
}

function nowBody($, d, ui) {
  const { Svg, Text } = ui
  const board = d.tasksBoard
  if (!board) return [Text({ dimColor: true, children: ['No task board'] })]
  const rows = []
  if (board.obsidian === false) rows.push(Text({ color: 'red', weight: 'semibold', children: ['● Obsidian not found: Homey requires it'] }))
  if (!board.watcher.on) rows.push(Text({ color: 'red', weight: 'semibold', children: ['● Watcher is off: tasks will not start'] }))
  const asks = (board.asks || []).filter((a) => !a.later)
  const later = (board.asks || []).filter((a) => a.later)
  const stuck = board.items.filter((x) => x.state === 'needs')
  if (asks.length) {
    rows.push(head(ui, 'head-asks', 'Waiting on you', asks.length))
    for (const a of asks) rows.push(askRow($, ui, a))
  }
  if (stuck.length) {
    rows.push(head(ui, 'head-needs', 'Stuck', stuck.length))
    for (const x of stuck) rows.push(taskRow($, ui, x))
  }
  if (!asks.length && !stuck.length) rows.push(Text({ color: 'green', weight: 'medium', children: ['✓ Nothing needs you'] }))
  if (!board.agents.length) rows.push(Text({ color: 'yellow', weight: 'medium', children: ['No agents started yet. Ask Homey to start them.'] }))
  if (board.agents.length) {
    rows.push(head(ui, 'head-team', 'Sessions'))
    rows.push(Svg({ alt: board.agents.map((a) => a.name + ' ' + a.state).join(', '), source: teamSvg(board.agents) }))
    rows.push(teamLegend(ui, board.agents))
  }
  const groups = [
    ['Working now', board.items.filter((x) => x.state === 'working')],
    ['Waiting to start', board.items.filter((x) => x.state === 'queued' || x.state === 'held')],
  ]
  for (const [title, items] of groups) {
    if (!items.length) continue
    rows.push(head(ui, 'head-' + title, title, items.length))
    for (const x of items) rows.push(taskRow($, ui, x))
  }
  if (later.length) {
    rows.push(head(ui, 'head-later', 'For later', later.length))
    for (const a of later) rows.push(laterRow($, ui, a))
  }
  const finished = board.items.filter((x) => x.state === 'finished').length
  if (finished) rows.push(Text({ dimColor: true, size: 'caption', children: ['Homey is checking ' + finished + ' finished'] }))
  rows.push(head(ui, 'next-head', "Homey's next step"))
  rows.push(Text({ size: 'footnote', children: [d.next || 'Nothing set'] }))
  rows.push(Text({ dimColor: true, size: 'caption', children: ['Inbox ' + d.inbox + ' · Stale ' + d.stale + ' · To-dos ' + d.tasks] }))
  rows.push(...newTask($, ui, board), handoffButton($, ui, board))
  return rows
}

function projectsBody($, d, ui) {
  const rows = []
  for (const st of d.config.statuses) {
    const items = d.projects.filter((p) => p.status === st)
    if (!items.length) continue
    rows.push(head(ui, 'status-' + st, st[0].toUpperCase() + st.slice(1), items.length))
    for (const p of items) {
      rows.push(row(ui, {
        key: 'project-' + p.name,
        color: p.stale ? 'red' : STATUS_COLOR[st] || 'cyan',
        title: p.name,
        meta: (p.stale ? 'Stale · ' : '') + (p.summary || 'No summary'),
        right: p.link ? linkButton($, ui, 'open-project-' + p.name, 'Open', p.link) : undefined,
      }))
    }
  }
  return rows
}

function decisionsBody($, d, ui) {
  const rows = []
  const dates = [...new Set(d.decisions.map((x) => x.date))]
  for (const date of dates) {
    const items = d.decisions.filter((x) => x.date === date)
    rows.push(head(ui, 'date-' + date, date === d.today ? 'Today' : date, items.length))
    for (const x of items) {
      rows.push(row(ui, {
        key: 'decision-' + x.name,
        color: DECISION_COLOR[x.status || 'decided'] || 'gray',
        title: x.name.replace(/^\d{4}-\d{2}-\d{2} /, ''),
        meta: (x.status || 'decided') + ' - ' + (x.summary || 'No summary'),
        right: x.link ? linkButton($, ui, 'open-decision-' + x.name, 'Open', x.link) : undefined,
      }))
    }
  }
  return rows
}

function issuesBody($, d, ui, pane) {
  const { Box, Text } = ui
  const t = d.tables[pane.id] || { headers: [], rows: [] }
  const rows = []
  if (t.error) rows.push(Text({ color: 'red', children: [t.error] }))
  const links = t.links || []
  if (pane.style === 'rows') {
    t.rows.forEach((r, i) => {
      const left = r.slice(0, -1)
      rows.push(row(ui, {
        key: 'row-' + i,
        color: BUG_COLOR[(r[1] || '').toLowerCase()] || 'gray',
        title: left[0] || r[0],
        meta: left.slice(1).join(' · ') || undefined,
        right: links[i] ? linkButton($, ui, 'open-row-' + pane.id + '-' + i, 'Open', links[i]) : undefined,
      }))
    })
    return rows
  }
  const sources = [...new Set(t.rows.map((r) => r[r.length - 1]))]
  sources.forEach((source, n) => {
    const items = t.rows.map((r, i) => ({ r, i })).filter(({ r }) => r[r.length - 1] === source)
    const link = links[items[0].i]
    const title = head(ui, 'source-' + n, source.replace(/^\d{4}-\d{2}-\d{2} /, ''), items.length)
    const top = [Box({ flexGrow: 1, flexShrink: 1, children: [title] })]
    if (link) top.push(linkButton($, ui, 'open-source-' + n, 'Open', link))
    rows.push(Box({ key: 'source-row-' + n, flexDirection: 'row', alignItems: 'flex-start', columnGap: 1, children: top }))
    for (const { r, i } of items) rows.push(Text({ key: 'row-' + i, children: ['• ' + (r.length > 1 ? r.slice(0, -1).join(' · ') : r[0])] }))
  })
  return rows
}

function richBody($, d, id, ui) {
  const { Text } = ui
  const pane = d.config.panes.find((p) => p.id === id)
  if (!pane) return [Text({ color: 'red', children: ['No pane ' + id + ' in homey.json'] })]
  let rows = []
  if (pane.type === 'tasks') return nowBody($, d, ui)
  if (pane.type === 'board') rows = projectsBody($, d, ui)
  else if (pane.type === 'decisions') rows = decisionsBody($, d, ui)
  else if (pane.type === 'table') rows = issuesBody($, d, ui, pane)
  return rows.length ? rows : [Text({ dimColor: true, children: ['Nothing here'] })]
}

function richPane($, d, ui, tabs) {
  const { Box, Text } = ui
  const body = [Box({ flexDirection: 'row', flexWrap: 'wrap', columnGap: 1, rowGap: 1, children: tabs })]
  if (problem) body.push(Text({ color: 'red', children: [problem] }))
  body.push(...richBody($, d, tab, ui))
  return Box({ flexDirection: 'column', gap: 'sm', children: body })
}

export function register(on) {
  on('session.start', async ($, e, next) => {
    await refresh($)
    $.clock.every(REFRESH_MS, async () => {
      passes += 1
      const open = (await $.ui.panes()).some((p) => p.id === PANE)
      if (open || passes % IDLE_EVERY === 0) await refresh($)
    })
    $.clock.every(REFRESH_MS, () => takeMessages($))
    $.clock.every(ANSWER_CHECK_MS, () => flushAnswers($))
    await $.command.register({
      name: 'homey',
      description: 'Vault status: now, find <term>, or no argument to open the pane',
      argumentHint: 'now | find <term>',
      immediate: true,
    })
    return next(e)
  })

  on('command.run', { command: 'homey' }, async ($, e) => {
    const parts = (e.args || '').trim().split(/\s+/).filter(Boolean)
    if (parts[0] === 'now') {
      const r = await run($, ['now'])
      return { text: r.text }
    }
    if (parts[0] === 'find') {
      const r = await run($, ['find', ...parts.slice(1)])
      return { text: r.text }
    }
    if (parts.length) return { text: 'Usage: /homey now | /homey find <term> | /homey' }
    await refresh($)
    await $.ui.open({ id: PANE, title: 'Homey', focus: true, closeOnEscape: true })
    return {}
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const { Box, Text, Button } = $.ui.resolve(e)
    const width = e.props.bodyColumns || 100
    if (!data && !problem) return next(e)
    return Box({
      flexDirection: 'row',
      columnGap: 2,
      children: [
        Text(problem ? { color: 'red', children: [clip(problem, width - 12)] } : { dimColor: true, children: [clip(bandText(data), width - 12)] }),
        Button({ key: 'open', label: 'Board', plain: true, onPress: async () => { await $.ui.open({ id: PANE, title: 'Homey', focus: true, closeOnEscape: true }) } }),
      ],
    })
  })

  on('ui.render', { component: 'Pane' }, async ($, e, next) => {
    if (e.requestId !== PANE) return next(e)
    const ui = $.ui.resolve(e)
    const { Box, Text, Button } = ui
    if (!data) return Text({ children: [problem || 'Loading…'] })
    const panes = data.config.panes
    if (!panes.length) return Text({ children: ['No panes in homey.json'] })
    if (!tab || !panes.some((p) => p.id === tab)) tab = panes[0].id
    const rich = e.surface !== 'terminal' && Boolean(ui.Svg)
    const buttons = panes.map((p, i) =>
      Button({
        key: 'tab-' + p.id,
        label: rich && paneCount(data, p) ? p.title + ' ' + paneCount(data, p) : p.title,
        hotkey: String(i + 1),
        ...(rich ? { variant: tab === p.id ? 'primary' : 'secondary' } : { plain: true, dimColor: tab !== p.id }),
        onPress: () => { tab = p.id; $.ui.invalidate('ui.render') },
      }),
    )
    if (rich) return richPane($, data, ui, buttons)
    return Box({
      flexDirection: 'column',
      children: [
        Box({ flexDirection: 'row', columnGap: 3, children: buttons }),
        Text({ children: [' '] }),
        ...paneBody(data, tab, Text),
      ],
    })
  })
}

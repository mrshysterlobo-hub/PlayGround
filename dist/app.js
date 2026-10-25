const state = {
  device: 'Android emulator',
  serial: 'emulator-5554',
  interval: 90,
  modules: {
    gather: { enabled: true, resource: 'food', marches: 3 },
    train: { enabled: true, tier: 'T3', batch: 250 },
    hero: { enabled: true, sweeps: 8, reserve: '40' },
    help: { enabled: true, interval: 10, batch: 12 },
    shield: { enabled: false, threshold: 30, action: 'notify' },
    quests: { enabled: true, scope: 'all', reset: 'local' }
  }
}

const resources = { food: 2410000, wood: 1870000, ore: 940000, might: 3120000 }
const labels = {
  gather: 'Auto Gather',
  train: 'Troop Training',
  hero: 'Hero Stages',
  help: 'Guild Help',
  shield: 'Shield Watch',
  quests: 'Daily Quests'
}

const el = {
  statModules: document.querySelector('#statModules'),
  statInterval: document.querySelector('#statInterval'),
  statActions: document.querySelector('#statActions'),
  moduleSummary: document.querySelector('#moduleSummary'),
  planJson: document.querySelector('#planJson'),
  deviceSelect: document.querySelector('#deviceSelect'),
  serialInput: document.querySelector('#serialInput'),
  intervalInput: document.querySelector('#intervalInput'),
  simulateBtn: document.querySelector('#simulateBtn'),
  downloadBtn: document.querySelector('#downloadBtn'),
  copyBtn: document.querySelector('#copyBtn'),
  runState: document.querySelector('#runState'),
  progressBar: document.querySelector('#progressBar'),
  progressLabel: document.querySelector('#progressLabel'),
  progressPercent: document.querySelector('#progressPercent'),
  progress: document.querySelector('.progress'),
  simLog: document.querySelector('#simLog'),
  toast: document.querySelector('#toast'),
  resFood: document.querySelector('#resFood'),
  resWood: document.querySelector('#resWood'),
  resOre: document.querySelector('#resOre'),
  resMight: document.querySelector('#resMight'),
  deltaFood: document.querySelector('#deltaFood'),
  deltaWood: document.querySelector('#deltaWood'),
  deltaOre: document.querySelector('#deltaOre'),
  deltaMight: document.querySelector('#deltaMight')
}

const base = { ...resources }
const sim = { running: false, timer: null, step: 0, steps: [], gains: {} }
let toastTimer = null

function cap(value) {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

function compact(value) {
  if (value >= 1000000) return (value / 1000000).toFixed(2) + 'M'
  if (value >= 1000) return Math.round(value / 1000) + 'K'
  return String(value)
}

function dailyActions() {
  const m = state.modules
  let actions = 0
  if (m.gather.enabled) actions += m.gather.marches * 120
  if (m.train.enabled) actions += m.train.batch * 2
  if (m.hero.enabled) actions += m.hero.sweeps * 30
  if (m.help.enabled) actions += Math.round((1440 / m.help.interval) * m.help.batch)
  if (m.shield.enabled) actions += 48
  if (m.quests.enabled) actions += 40
  return actions
}

function moduleSummary() {
  const m = state.modules
  return {
    gather: `${cap(m.gather.resource)} · ${m.gather.marches} march${m.gather.marches === 1 ? '' : 'es'}`,
    train: `${m.train.tier} · ${m.train.batch} troops`,
    hero: `${m.hero.sweeps} sweeps · ${m.hero.reserve} reserve`,
    help: `Every ${m.help.interval} min · ${m.help.batch} taps`,
    shield: `${m.shield.action === 'notify' ? 'Notify' : 'Renew'} at ${m.shield.threshold} min`,
    quests: `${m.quests.scope === 'all' ? 'All rewards' : 'Chest only'} · ${m.quests.reset === 'local' ? 'local reset' : 'game reset'}`
  }
}

function buildPlan() {
  const enabled = Object.entries(state.modules)
    .filter(([, value]) => value.enabled)
    .map(([key]) => key)
  const summaries = moduleSummary()
  const modules = {}

  for (const [key, value] of Object.entries(state.modules)) {
    modules[key] = { ...value, summary: summaries[key] }
  }

  return {
    schema: 'lords-mobile-companion/plan@1',
    generatedAt: new Date().toISOString(),
    device: {
      type: state.device,
      serial: state.serial,
      resolution: 'fixed landscape'
    },
    loop: {
      intervalSeconds: state.interval,
      jitterSeconds: Math.max(5, Math.round(state.interval * 0.16)),
      maxRuntimeMinutes: 240,
      stopOnUnknownScreen: true
    },
    modules,
    enabled,
    estimatedDailyActions: dailyActions(),
    safety: {
      requireScreenMatch: true,
      confidence: 0.94,
      pauseOnPopup: true,
      screenshotAudit: true,
      credentialsStored: false
    }
  }
}

function render() {
  let enabledCount = 0
  for (const [key, value] of Object.entries(state.modules)) {
    if (value.enabled) enabledCount += 1
    const card = document.querySelector(`[data-module="${key}"]`)
    if (card) {
      card.classList.toggle('is-off', !value.enabled)
      const toggle = card.querySelector('[data-toggle]')
      if (toggle) toggle.checked = value.enabled
    }
  }

  const summaries = moduleSummary()
  for (const [key, text] of Object.entries(summaries)) {
    const target = document.querySelector(`[data-summary="${key}"]`)
    if (target) target.textContent = text
  }

  el.statModules.innerHTML = `${enabledCount}<small>/6</small>`
  el.statInterval.innerHTML = `${state.interval}<small>s</small>`
  const actions = dailyActions()
  el.statActions.textContent = actions >= 1000 ? `~${(actions / 1000).toFixed(1)}k` : `~${actions}`
  el.moduleSummary.textContent = `${enabledCount} enabled`

  el.planJson.textContent = JSON.stringify(buildPlan(), null, 2)
  document.body.dataset.planModules = String(enabledCount)
}

function setToggle(input) {
  const key = input.dataset.toggle
  state.modules[key].enabled = input.checked
  render()
}

function setField(field) {
  const [moduleKey, property] = field.dataset.field.split('.')
  const numeric = field.type === 'range' || field.type === 'number'
  const value = numeric ? Number(field.value) : field.value
  state.modules[moduleKey][property] = value
  render()
}

function showToast(message) {
  el.toast.textContent = message
  el.toast.classList.add('show')
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => el.toast.classList.remove('show'), 2400)
}

async function copyPlan() {
  const text = el.planJson.textContent
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    const area = document.createElement('textarea')
    area.value = text
    area.style.position = 'fixed'
    area.style.opacity = '0'
    document.body.append(area)
    area.select()
    document.execCommand('copy')
    area.remove()
  }
  el.copyBtn.textContent = 'Copied'
  showToast('Plan copied to clipboard')
  setTimeout(() => { el.copyBtn.textContent = 'Copy' }, 1800)
}

function downloadPlan() {
  const blob = new Blob([JSON.stringify(buildPlan(), null, 2) + '\n'], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'lords-plan.json'
  document.body.append(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
  showToast('lords-plan.json downloaded')
}

function setResource(name, total, gain) {
  const target = el['res' + cap(name)]
  const delta = el['delta' + cap(name)]
  if (target) target.textContent = compact(total)
  if (delta) {
    delta.textContent = gain ? `+${compact(gain)} this loop` : 'stock'
    delta.classList.toggle('up', Boolean(gain))
  }
}

function resetResources() {
  for (const name of Object.keys(resources)) {
    resources[name] = base[name]
    setResource(name, resources[name], 0)
  }
}

function clock() {
  return new Date().toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function addLog(text, kind = '') {
  const item = document.createElement('li')
  const time = document.createElement('time')
  time.textContent = clock()
  const message = document.createElement('span')
  message.className = kind
  message.textContent = text
  item.append(time, message)
  el.simLog.append(item)
  el.simLog.scrollTop = el.simLog.scrollHeight
}

function setRunState(name, label) {
  el.runState.dataset.state = name
  el.runState.innerHTML = `<span></span>${label}`
}

function buildSteps() {
  const steps = []
  const m = state.modules

  steps.push({ text: `ADB handshake → ${state.serial} · ${state.device}`, kind: 'ok' })
  steps.push({ text: 'Screen match → city view · confidence 0.98', kind: 'ok' })

  if (m.help.enabled) {
    steps.push({ text: `Guild help → ${m.help.batch} open requests`, kind: 'action', gain: {} })
  }

  if (m.quests.enabled) {
    steps.push({
      text: `Daily quests → ${m.quests.scope === 'all' ? 'collect every reward' : 'open the chest only'}`,
      kind: 'action',
      gain: { food: 8200, wood: 6400, ore: 3100 }
    })
  }

  if (m.hero.enabled) {
    steps.push({
      text: `Hero stages → sweep ${m.hero.sweeps} times · keep ${m.hero.reserve} stamina`,
      kind: 'action',
      gain: { might: m.hero.sweeps * 180 }
    })
  }

  if (m.gather.enabled) {
    steps.push({
      text: `Auto gather → ${m.gather.marches} marches on ${m.gather.resource}`,
      kind: 'action',
      gain: { [m.gather.resource]: m.gather.marches * 26000 }
    })
  }

  if (m.train.enabled) {
    steps.push({
      text: `Troop training → queue ${m.train.batch} ${m.train.tier} troops`,
      kind: 'action',
      gain: { might: m.train.batch * 22 }
    })
  }

  if (m.shield.enabled) {
    steps.push({
      text: `Shield watch → ${m.shield.action === 'renew' ? 'renew shield' : 'alert'} at ${m.shield.threshold} min`,
      kind: 'warn',
      gain: {}
    })
  }

  steps.push({ text: `Loop complete → next run in ${state.interval}s ± ${Math.max(5, Math.round(state.interval * 0.16))}s`, kind: 'ok' })
  return steps
}

function updateProgress() {
  const total = sim.steps.length || 1
  const percent = Math.round((sim.step / total) * 100)
  el.progressBar.style.width = `${percent}%`
  el.progressPercent.textContent = `${percent}%`
  el.progress.setAttribute('aria-valuenow', String(percent))
  if (sim.step === 0) el.progressLabel.textContent = 'Booting runner'
  else if (sim.step < total) el.progressLabel.textContent = `Executing step ${sim.step} of ${total}`
  else el.progressLabel.textContent = 'Loop finished cleanly'
}

function finishSimulation() {
  clearInterval(sim.timer)
  sim.timer = null
  sim.running = false
  el.simulateBtn.disabled = false
  el.simulateBtn.querySelector('span').textContent = 'Run again'
  setRunState('complete', 'Complete')
  updateProgress()
  addLog('Runner idle · screenshots retained for audit', 'ok')
  showToast('Loop simulation complete')
}

function runSimulation() {
  if (sim.running) return
  clearInterval(sim.timer)
  resetResources()
  el.simLog.replaceChildren()
  sim.running = true
  sim.step = 0
  sim.steps = buildSteps()
  sim.gains = {}
  el.simulateBtn.disabled = true
  el.simulateBtn.querySelector('span').textContent = 'Simulating…'
  setRunState('running', 'Running')
  updateProgress()
  addLog(`Runner boot · ${Object.values(state.modules).filter((item) => item.enabled).length} modules armed`, 'ok')

  sim.timer = setInterval(() => {
    const current = sim.steps[sim.step]
    if (!current) {
      finishSimulation()
      return
    }
    addLog(current.text, current.kind)
    if (current.gain) {
      for (const [name, amount] of Object.entries(current.gain)) {
        if (!(name in resources)) continue
        resources[name] += amount
        sim.gains[name] = (sim.gains[name] || 0) + amount
        setResource(name, resources[name], sim.gains[name])
      }
    }
    sim.step += 1
    updateProgress()
    if (sim.step >= sim.steps.length) finishSimulation()
  }, 720)
}

function bindEvents() {
  document.querySelectorAll('[data-toggle]').forEach((input) => {
    input.addEventListener('change', () => setToggle(input))
  })
  document.querySelectorAll('[data-field]').forEach((field) => {
    field.addEventListener('input', () => setField(field))
    field.addEventListener('change', () => setField(field))
  })

  el.deviceSelect.addEventListener('change', () => {
    state.device = el.deviceSelect.value
    render()
  })
  el.serialInput.addEventListener('input', () => {
    state.serial = el.serialInput.value.trim() || 'emulator-5554'
    render()
  })
  el.intervalInput.addEventListener('input', () => {
    const value = Math.min(600, Math.max(15, Number(el.intervalInput.value) || 90))
    state.interval = value
    render()
  })
  el.intervalInput.addEventListener('blur', () => {
    el.intervalInput.value = String(state.interval)
  })

  el.simulateBtn.addEventListener('click', runSimulation)
  el.downloadBtn.addEventListener('click', downloadPlan)
  el.copyBtn.addEventListener('click', copyPlan)
}

function initEmbers() {
  const canvas = document.querySelector('#embers')
  const context = canvas.getContext('2d')
  if (!context) return
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const dpr = Math.min(2, window.devicePixelRatio || 1)
  let particles = []

  function resize() {
    canvas.width = Math.floor(window.innerWidth * dpr)
    canvas.height = Math.floor(window.innerHeight * dpr)
    canvas.style.width = window.innerWidth + 'px'
    canvas.style.height = window.innerHeight + 'px'
    const count = Math.min(54, Math.max(18, Math.round(window.innerWidth / 28)))
    particles = Array.from({ length: count }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      radius: (0.6 + Math.random() * 1.8) * dpr,
      speed: (0.12 + Math.random() * 0.42) * dpr,
      drift: (Math.random() - 0.5) * 0.18 * dpr,
      alpha: 0.12 + Math.random() * 0.5,
      phase: Math.random() * Math.PI * 2,
      gold: Math.random() > 0.55
    }))
  }

  function draw(time) {
    context.clearRect(0, 0, canvas.width, canvas.height)
    for (const particle of particles) {
      if (!reduced) {
        particle.y -= particle.speed
        particle.x += Math.sin(time / 2600 + particle.phase) * 0.16 + particle.drift
        if (particle.y < -10 || particle.x < -12 || particle.x > canvas.width + 12) {
          particle.y = canvas.height + 8
          particle.x = Math.random() * canvas.width
        }
      }
      const color = particle.gold ? '230, 180, 94' : '99, 230, 190'
      context.beginPath()
      context.arc(particle.x, particle.y, particle.radius, 0, Math.PI * 2)
      context.fillStyle = `rgba(${color}, ${particle.alpha})`
      context.fill()
    }
    if (!reduced) requestAnimationFrame(draw)
  }

  resize()
  window.addEventListener('resize', resize)
  draw(0)
}

bindEvents()
render()
initEmbers()
resetResources()

requestAnimationFrame(() => {
  requestAnimationFrame(() => {
    document.body.dataset.appReady = 'true'
    console.log('Lords Mobile Bot Studio ready')
  })
})

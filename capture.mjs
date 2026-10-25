import { createRequire } from 'node:module'
import { existsSync, mkdirSync, readFileSync, statSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

const url = process.env.CAPTURE_URL
const output = process.env.CAPTURE_DIR

function fail(message, exitCode) {
  const error = new Error(message)
  error.exitCode = exitCode
  throw error
}

if (!url) fail('CAPTURE_URL is required', 1)
if (!output) fail('CAPTURE_DIR is required', 1)

const runtime = join(homedir(), '.local/share/omgithub-playwright')
const runtimeConfig = join(runtime, process.platform === 'darwin' ? 'metal.json' : 'linux.json')
if (!existsSync(runtimeConfig)) fail(`Missing Playwright runtime config: ${runtimeConfig}`, 1)

const require = createRequire(join(runtime, 'package.json'))
const { chromium } = require('playwright')
const config = JSON.parse(readFileSync(runtimeConfig, 'utf8'))

if (process.platform === 'linux' && !process.env.DISPLAY) {
  const displayFile = join(runtime, 'display')
  if (existsSync(displayFile) && statSync(displayFile).size > 0) {
    process.env.DISPLAY = ':' + readFileSync(displayFile, 'utf8').trim()
  }
}

mkdirSync(output, { recursive: true })

const viewports = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'mobile', width: 390, height: 844 }
]

const transient = (error) => {
  error.exitCode = 75
  return error
}

const defect = (message) => {
  const error = new Error(message)
  error.exitCode = 1
  return error
}

let browser
try {
  browser = await chromium.launch({ ...config.browser.launchOptions, timeout: 30000 }).catch((error) => {
    throw transient(error)
  })

  for (const viewport of viewports) {
    console.log(`Capturing ${viewport.name} at ${viewport.width}x${viewport.height}`)
    const page = await browser.newPage({
      viewport: { width: viewport.width, height: viewport.height },
      deviceScaleFactor: 1
    }).catch((error) => {
      throw transient(error)
    })

    page.setDefaultTimeout(30000)
    page.on('pageerror', (error) => console.error(`Page error: ${error.message}`))

    let response
    try {
      response = await page.goto(url, { waitUntil: 'load', timeout: 45000 })
    } catch (error) {
      throw transient(error)
    }

    if (!response) throw transient(new Error(`No response from ${url}`))
    const status = response.status()
    if (!response.ok()) {
      if ([408, 429, 500, 502, 503, 504].includes(status)) throw transient(new Error(`HTTP ${status} loading ${url}`))
      throw defect(`HTTP ${status} loading ${url}`)
    }

    try {
      await page.waitForSelector('body[data-app-ready="true"]', { state: 'attached', timeout: 30000 })
      await page.waitForFunction(() => document.fonts.status === 'loaded', null, { timeout: 10000 })
    } catch (error) {
      throw defect(`App did not finish rendering: ${error.message}`)
    }

    const content = await page.evaluate(() => ({
      title: document.title,
      text: document.body.innerText.replace(/\s+/g, ' ').trim(),
      ready: document.body.dataset.appReady
    }))

    if (content.ready !== 'true' || content.text.length < 120 || !content.text.includes('Bot Studio')) {
      throw defect('Rendered page is missing expected content')
    }

    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.waitForTimeout(900)

    const file = join(output, `final-${viewport.name}.png`)
    try {
      await page.screenshot({ path: file, timeout: 30000 })
    } catch (error) {
      if (error.name === 'TimeoutError' || !browser.isConnected()) throw transient(error)
      throw defect(`Screenshot failed: ${error.message}`)
    }

    const bytes = statSync(file).size
    if (bytes < 15000) throw defect(`Screenshot ${file} is unexpectedly small (${bytes} bytes)`)
    console.log(`Saved ${file} (${bytes} bytes)`)
    await page.close().catch(() => {})
  }
} catch (error) {
  console.error(error.message)
  process.exitCode = error.exitCode || 1
} finally {
  await browser?.close().catch((error) => {
    console.error(`Browser close failed: ${error.message}`)
    process.exitCode ||= 75
  })
}

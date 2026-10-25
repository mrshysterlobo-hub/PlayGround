import { createServer } from 'node:http'
import { existsSync, readFileSync, statSync } from 'node:fs'
import { extname, join, normalize, resolve, sep } from 'node:path'

const root = resolve(process.env.SERVE_DIR || join(process.cwd(), 'dist'))
const port = Number(process.env.PORT || 3000)
const host = process.env.HOST || '0.0.0.0'

if (!existsSync(join(root, 'index.html'))) {
  console.error(`No index.html in ${root}. Run node build.mjs first.`)
  process.exit(1)
}

const types = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.woff2': 'font/woff2',
  '.txt': 'text/plain; charset=utf-8'
}

function resolveFile(pathname) {
  let decoded
  try {
    decoded = decodeURIComponent(pathname)
  } catch {
    return null
  }
  const path = resolve(root, '.' + normalize(decoded))
  if (path !== root && !path.startsWith(root + sep)) return null
  if (existsSync(path) && statSync(path).isDirectory()) {
    const index = join(path, 'index.html')
    return existsSync(index) ? index : null
  }
  return existsSync(path) ? path : null
}

const server = createServer((request, response) => {
  const url = new URL(request.url || '/', `http://${request.headers.host || 'localhost'}`)
  if (url.pathname === '/healthz') {
    response.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' })
    response.end(JSON.stringify({ ok: true, service: 'lords-mobile-bot-studio' }))
    return
  }

  let file = resolveFile(url.pathname)
  if (!file && !extname(url.pathname)) file = join(root, 'index.html')
  if (!file) {
    response.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' })
    response.end('Not found')
    return
  }

  try {
    const body = readFileSync(file)
    response.writeHead(200, {
      'Content-Type': types[extname(file)] || 'application/octet-stream',
      'Content-Length': body.length,
      'Cache-Control': 'no-cache',
      'X-Content-Type-Options': 'nosniff'
    })
    response.end(request.method === 'HEAD' ? undefined : body)
  } catch (error) {
    response.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' })
    response.end('Internal server error')
    console.error(error.message)
  }
})

server.listen(port, host, () => {
  console.log(`Lords Mobile Bot Studio listening on http://${host}:${port} (${root})`)
})

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => server.close(() => process.exit(0)))
}

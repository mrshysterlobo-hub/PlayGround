import { cpSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { join, relative } from 'node:path'

const root = process.cwd()
const source = join(root, 'src')
const output = join(root, 'dist')
const stampFile = join(root, '.build-stamp')

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    return statSync(path).isDirectory() ? walk(path) : [path]
  })
}

if (!existsSync(source)) {
  console.error('Missing src directory')
  process.exit(1)
}

const files = walk(source).sort()
const hash = createHash('sha256')
for (const file of files) {
  hash.update(relative(source, file))
  hash.update(readFileSync(file))
}
const stamp = hash.digest('hex')

let previous = ''
try {
  previous = readFileSync(stampFile, 'utf8')
} catch {}

if (previous === stamp && existsSync(join(output, 'index.html'))) {
  console.log(`Build is current (${stamp.slice(0, 12)})`)
  process.exit(0)
}

rmSync(output, { recursive: true, force: true })
mkdirSync(output, { recursive: true })
cpSync(source, output, { recursive: true })
writeFileSync(join(output, 'build-info.json'), JSON.stringify({ stamp, files: files.length }, null, 2) + '\n')
writeFileSync(stampFile, stamp)
console.log(`Built ${files.length} files into ${output} (${stamp.slice(0, 12)})`)

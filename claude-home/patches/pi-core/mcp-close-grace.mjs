#!/usr/bin/env node
// Conserto local da saída do pi (docs/specs/0003-boot-exit.md). Causa: ao fechar, o transporte stdio do pi-mcp fecha o
// stdin do servidor e espera STDIN_CLOSE_GRACE_MS (500 ms) antes do SIGTERM. Um servidor que ainda sobe (npx a frio) não
// lê o stdin, então todo `pi -p` curto pagava os 500 ms inteiros no fim. Servidores já no ar saem em 10-25 ms.
// Conserto: 500 -> 100 ms (o SIGKILL continua 2 s depois). Idempotente; aplicado pelo wrapper bin/pi.
// Saída 0 = aplicado ou já estava; 2 = não casou (refazer). Uso: mcp-close-grace.mjs <dist do pi-coding-agent>.
import { existsSync, readdirSync, readFileSync, realpathSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'

export const GRACE_MS = 100
// bundle minificado e dist/transports/stdio.js do pi-mcp
const FORMS = [/STDIN_CLOSE_GRACE_MS=500\b/, /STDIN_CLOSE_GRACE_MS = 500;/]

const NEW = (form) =>
  form.source.includes(' = ') ? `STDIN_CLOSE_GRACE_MS = ${GRACE_MS};` : `STDIN_CLOSE_GRACE_MS=${GRACE_MS}`
const DONE = new RegExp(`STDIN_CLOSE_GRACE_MS ?= ?${GRACE_MS}\\b`)

/** Arquivos com o transporte: chunks do bundle e, se existir, o pi-mcp irmão (a release o mantém ao lado). */
export function targets(dist) {
  const files = readdirSync(join(dist, 'bundle/chunks'))
    .filter((f) => f.endsWith('.js'))
    .map((f) => join(dist, 'bundle/chunks', f))
  const sibling = join(dist, '../../pi-mcp/dist/transports/stdio.js')
  if (existsSync(sibling)) files.push(sibling)
  return files
}

/** Conserta os arquivos de `dist`; devolve quantos têm o conserto (já aplicado ou agora). */
export function apply(dist) {
  let fixed = 0
  for (const file of targets(dist)) {
    const src = readFileSync(file, 'utf8')
    if (DONE.test(src)) {
      fixed++
      continue
    }
    const form = FORMS.find((f) => f.test(src))
    if (!form) continue
    writeFileSync(file, src.replace(form, NEW(form)))
    fixed++
  }
  return fixed
}

// realpath: com `install.sh --link` o wrapper chama o .mjs por um symlink e import.meta.url já vem resolvido.
if (process.argv[1] && import.meta.url === pathToFileURL(realpathSync(process.argv[1])).href) {
  const dist = process.argv[2]
  if (!dist) {
    console.error('uso: mcp-close-grace.mjs <dist>')
    process.exit(1)
  }
  if (apply(dist) < 1) {
    console.error('pi: patches/pi-core/mcp-close-grace.mjs não casou nesta versão; refazer o conserto')
    process.exit(2)
  }
}

import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, openSync, closeSync, readFileSync, writeFileSync } from 'node:fs';
import { createServer } from 'node:net';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const url = 'http://127.0.0.1:5173';
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
async function healthy() {
  try {
    const [page, health] = await Promise.all([
      fetch(url, { signal: AbortSignal.timeout(1200) }),
      fetch(`${url}/api/health`, { signal: AbortSignal.timeout(1200) }),
    ]);
    return page.ok && health.ok && /<title>Hivly/i.test(await page.text()) && (await health.json()).ok === true;
  } catch { return false; }
}
async function portAvailable() {
  await new Promise((resolve, reject) => {
    const probe = createServer();
    probe.once('error', reject);
    probe.listen(5173, '127.0.0.1', () => probe.close(resolve));
  });
}
async function start() {
  if (await healthy()) { console.log(`Hivly is already running: ${url}/`); return; }
  const vite = resolve(root, 'node_modules/vite/bin/vite.js');
  if (!existsSync(vite)) throw new Error('Dependencies are missing. Run npm ci inside the frontend folder, then try again.');
  try { await portAvailable(); } catch { throw new Error('Port 5173 is in use by another service. Close that service before starting Hivly.'); }
  const logs = resolve(root, '.hivly'); mkdirSync(logs, { recursive: true });
  const stdout = openSync(resolve(logs, 'server-out.log'), 'a');
  const stderr = openSync(resolve(logs, 'server-error.log'), 'a');
  const child = spawn(process.execPath, [vite, '--host', '127.0.0.1', '--port', '5173', '--strictPort'], {
    cwd: root, detached: true, windowsHide: true, stdio: ['ignore', stdout, stderr],
  });
  closeSync(stdout); closeSync(stderr);
  await new Promise((resolve, reject) => { child.once('spawn', resolve); child.once('error', reject); });
  child.unref();
  writeFileSync(resolve(logs, 'server.json'), JSON.stringify({ pid: child.pid, url, started_at: new Date().toISOString() }, null, 2));
  for (let attempt = 0; attempt < 40; attempt++) {
    if (await healthy()) { console.log(`Hivly is running in the background: ${url}/`); return; }
    await delay(250);
  }
  const log = readFileSync(resolve(logs, 'server-error.log'), 'utf8').trim().split('\n').slice(-10).join('\n');
  throw new Error(`Hivly did not become ready. ${log || 'See frontend/.hivly/server-out.log for startup details.'}`);
}
start().catch(error => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});

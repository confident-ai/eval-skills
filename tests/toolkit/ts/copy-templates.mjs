// Copy every TypeScript template into .tmp/src so it resolves packages from
// this folder's node_modules, the way it will inside a user's project.
import { copyFileSync, mkdirSync, readdirSync, rmSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const skills = join(here, '..', '..', '..', 'skills');
const out = join(here, '.tmp', 'src');
rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });

function walk(dir) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) walk(path);
    else if (name.endsWith('.ts') && path.includes(`${'templates'}`)) copyFileSync(path, join(out, name));
  }
}
walk(skills);
console.log(`Copied TypeScript templates to ${out}`);

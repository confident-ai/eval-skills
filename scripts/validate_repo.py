"""Offline structural validation; behavioral validation is separate."""
import argparse
import ast
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from sync_references import EXTRA, sync

ROOT = Path(__file__).resolve().parents[1]


def validate(require_artwork=True):
    errors = []
    def check(ok, message):
        if not ok:
            errors.append(message)
    check(not sync(check=True), 'Generated skill references differ from docs; run sync_references.py')
    for name in EXTRA:
        folder = ROOT / 'skills' / name
        text = (folder / 'SKILL.md').read_text()
        parts = text.split('---', 2)
        check(len(parts) == 3 and not parts[0].strip(), f'{name}: missing YAML frontmatter')
        if len(parts) == 3:
            check(f'name: {name}\n' in parts[1], f'{name}: name mismatch')
            check(bool(re.search(r'^description: .+', parts[1], re.M)), f'{name}: missing description')
            check('license: Apache-2.0' in parts[1], f'{name}: missing license')
        check((folder / 'LICENSE').is_file(), f'{name}: missing distributed license')
        check((folder / 'agents/openai.yaml').is_file(), f'{name}: missing interface metadata')
        for md in folder.rglob('*.md'):
            for link in re.findall(r'\]\(([^)]+)\)', md.read_text()):
                if re.match(r'^[a-z]+:', link) or link.startswith('#'):
                    continue
                target = (md.parent / link.split('#')[0]).resolve()
                check(target.is_relative_to(folder.resolve()), f'{md}: link escapes installed skill: {link}')
                check(target.exists(), f'{md}: broken link: {link}')
    for path in ROOT.rglob('*.py'):
        if '.git' not in path.parts:
            try:
                ast.parse(path.read_text(), filename=str(path))
            except SyntaxError as exc:
                errors.append(str(exc))
    # Catch unmistakable credential material without echoing potential secrets.
    secret_patterns = [r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
                       r"(?:sk-proj-|sk-ant-api|ghp_)[A-Za-z0-9_-]{24,}"]
    for path in ROOT.rglob('*'):
        if path.is_file() and path.suffix in ('.md', '.py', '.json', '.jsonl', '.yml', '.yaml'):
            text = path.read_text()
            check(not any(re.search(pattern, text) for pattern in secret_patterns),
                  f'{path.relative_to(ROOT)}: possible credential material')
    for path in ROOT.rglob('*.jsonl'):
        for n, line in enumerate(path.read_text().splitlines(), 1):
            if line.strip():
                try:
                    json.loads(line)
                except ValueError:
                    errors.append(f'{path}:{n}: invalid fixture JSON')
    for md in [ROOT / 'README.md', * (ROOT / 'docs').glob('*.md')]:
        for link in re.findall(r'\]\(([^)]+)\)', md.read_text()):
            if re.match(r'^[a-z]+:', link) or link.startswith('#'):
                continue
            if not require_artwork and link.startswith('assets/'):
                continue
            check((md.parent / link.split('#')[0]).exists(), f'{md.name}: broken link {link}')
    if require_artwork:
        png = ROOT / 'assets/eval-skills-banner.png'
        svg = ROOT / 'assets/eval-skills-banner-radial-4s.svg'
        check(png.exists() and svg.exists(), 'Missing final artwork')
        if png.exists():
            raw = png.read_bytes()
            check(raw[:8] == b'\x89PNG\r\n\x1a\n', 'Banner is not PNG')
            if len(raw) >= 24:
                width, height = struct.unpack('>II', raw[16:24])
                check(width == height * 3, f'Banner must be 3:1; got {width}x{height}')
        if svg.exists():
            try:
                ET.parse(svg)
            except ET.ParseError as exc:
                errors.append(f'Invalid SVG: {exc}')
            text = svg.read_text()
            check('prefers-reduced-motion' in text, 'Missing reduced-motion treatment')
            check('dur="4s"' in text, 'Missing four-second reveal')
            check('data:image/png;base64,' in text, 'SVG must embed its image')
    if errors:
        raise ValueError('\n'.join(errors))
    return len(EXTRA)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--without-artwork', action='store_true', help='Pre-artwork development check only')
    args = parser.parse_args()
    try:
        print(f'Validated {validate(not args.without_artwork)} installable skills and repository references')
    except ValueError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

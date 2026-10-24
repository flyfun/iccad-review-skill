#!/usr/bin/env python3
"""Validate the iccad-review skill suite: layout, metadata, references, script hygiene.

Python 3.10+ standard library only. Exit 0 when clean, 2 when problems were found.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
SKILLS = HERE / 'skills'

REQUIRED_SKILL_KEYS = ('name', 'description')
MAX_DESCRIPTION = 400
MIN_DESCRIPTION = 30
MAX_SKILL_LINES = 400
JUNK = {'.venv', '__pycache__', '.work', '.git', 'node_modules'}

STDLIB = {
    'argparse', 'collections', 'datetime', 'decimal', 'hashlib', 'io', 'json',
    'math', 'os', 'pathlib', 're', 'shutil', 'statistics', 'sys', 'tempfile',
    'textwrap', 'time', 'typing', 'unicodedata', 'unittest', 'urllib', 'zipfile',
    'csv', 'difflib', 'functools', 'itertools', 'struct', 'subprocess', 'html',
}

LINK_RE = re.compile(r'\]\(([^)\s]+)\)')
SKILL_REF_RE = re.compile(r'\$([a-z][a-z0-9]+(?:-[a-z0-9]+)*)')
IMPORT_RE = re.compile(r'^\s*(?:from\s+([A-Za-z_][\w.]*)\s+import|import\s+([A-Za-z_][\w.]*))', re.M)


def frontmatter(text):
    if not text.startswith('---'):
        return {}, 'no leading ---'
    end = text.find('\n---', 3)
    if end < 0:
        return {}, 'unterminated frontmatter'
    block = text[3:end]
    data = {}
    for line in block.splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if ':' not in line:
            return {}, f'unparsable frontmatter line: {line!r}'
        key, _, value = line.partition(':')
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data, None


def check_skill(path, names, problems):
    skill_md = path / 'SKILL.md'
    text = skill_md.read_text(encoding='utf-8')
    data, err = frontmatter(text)
    if err:
        problems.append(f'{path.name}: {err}')
        return None
    for key in REQUIRED_SKILL_KEYS:
        if not data.get(key):
            problems.append(f'{path.name}: frontmatter missing {key}')
    if data.get('name') != path.name:
        problems.append(f'{path.name}: frontmatter name {data.get("name")!r} != directory name')
    desc = data.get('description', '')
    if not (MIN_DESCRIPTION <= len(desc) <= MAX_DESCRIPTION):
        problems.append(f'{path.name}: description length {len(desc)} outside {MIN_DESCRIPTION}..{MAX_DESCRIPTION}')
    if len(text.splitlines()) > MAX_SKILL_LINES:
        problems.append(f'{path.name}: SKILL.md has {len(text.splitlines())} lines (>{MAX_SKILL_LINES}); move detail into references/')

    for match in LINK_RE.finditer(text):
        target = match.group(1)
        if target.startswith(('http://', 'https://', 'mailto:', '#')):
            continue
        rel = target.split('#')[0]
        if not rel:
            continue
        if not (path / rel).exists():
            problems.append(f'{path.name}: broken relative link {target}')

    for ref in set(SKILL_REF_RE.findall(text)):
        if ref.startswith('iccad-') and ref not in names:
            problems.append(f'{path.name}: references unknown skill ${ref}')

    for junk in path.rglob('*'):
        if junk.name in JUNK:
            problems.append(f'{path.name}: stray directory {junk.relative_to(HERE)}')

    script_dir = path / 'scripts'
    scripts = sorted(script_dir.glob('*.py')) if script_dir.is_dir() else []
    for script in scripts:
        code = script.read_text(encoding='utf-8')
        for from_mod, plain_mod in IMPORT_RE.findall(code):
            mod = (from_mod or plain_mod).split('.')[0]
            if mod and mod not in STDLIB and not (script.parent / f'{mod}.py').exists():
                problems.append(f'{path.name}/scripts/{script.name}: non-stdlib import {mod!r}')
    return data


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()

    problems = []
    if not SKILLS.is_dir():
        print('skills/ directory missing')
        return 2
    dirs = sorted(p for p in SKILLS.iterdir() if p.is_dir())
    names = {p.name for p in dirs}

    catalog_path = HERE / 'catalog.json'
    if not catalog_path.is_file():
        problems.append('catalog.json missing')
        catalog = []
    else:
        catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
        cat_names = [item.get('name') for item in catalog]
        if len(cat_names) != len(set(cat_names)):
            problems.append('catalog.json: duplicate names')
        for name in names - set(cat_names):
            problems.append(f'catalog.json: missing entry for {name}')
        for name in set(cat_names) - names:
            problems.append(f'catalog.json: entry {name} has no skills/ directory')

    meta = {}
    for path in dirs:
        if not (path / 'SKILL.md').is_file():
            problems.append(f'{path.name}: no SKILL.md')
            continue
        data = check_skill(path, names, problems)
        if data:
            meta[path.name] = data

    for item in catalog:
        name = item.get('name')
        if name in meta and item.get('description') != meta[name].get('description'):
            problems.append(f'catalog.json: description differs from SKILL.md for {name}')
        if not item.get('title'):
            problems.append(f'catalog.json: {name} has no title')

    if not args.quiet:
        for name in sorted(meta):
            print(f'  {name:<20} {len(meta[name].get("description", ""))} chars')
    if problems:
        print(f'\n{len(problems)} problem(s):')
        for p in problems:
            print(f'  - {p}')
        return 2
    print(f'\nOK skills={len(meta)} catalog={len(catalog)} problems=0')
    return 0


if __name__ == '__main__':
    sys.exit(main())

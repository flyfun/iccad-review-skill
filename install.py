#!/usr/bin/env python3
"""Install the iccad-review skill suite into an Agent skills directory.

Python 3.10+ standard library only, no network access.
Stops before writing anything if any target directory already exists.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / 'skills'


def say(msg):
    print(msg, flush=True)


def discover():
    if not SRC.is_dir():
        raise SystemExit(f'skills/ not found next to {Path(__file__).name}')
    return sorted(p for p in SRC.iterdir() if p.is_dir() and (p / 'SKILL.md').is_file())


def catalog_names():
    path = HERE / 'catalog.json'
    if not path.is_file():
        return []
    return [item['name'] for item in json.loads(path.read_text(encoding='utf-8'))]


def check(target):
    """Report which skills are installed and look consistent."""
    rows, bad = [], 0
    for src in discover():
        dst = target / src.name
        skill_md = dst / 'SKILL.md'
        if not skill_md.is_file():
            rows.append((src.name, 'MISSING'))
            bad += 1
            continue
        head = skill_md.read_text(encoding='utf-8')[:400]
        name_ok = f'name: {src.name}' in head
        rows.append((src.name, 'OK' if name_ok else 'NAME-MISMATCH'))
        bad += 0 if name_ok else 1
    for name, state in rows:
        say(f'  {state:<14} {name}')
    say(f'\n{len(rows)} skills checked, {bad} problem(s). target={target}')
    return 0 if bad == 0 else 2


def install(target, force):
    sources = discover()
    names = catalog_names()
    missing = sorted(set(p.name for p in sources) ^ set(names))
    if missing:
        say(f'catalog.json and skills/ disagree on: {", ".join(missing)}')
        return 2
    conflicts = [p.name for p in sources if (target / p.name).exists()]
    if conflicts and not force:
        say('Refusing to write: these target directories already exist —')
        for name in conflicts:
            say(f'  {target / name}')
        say('\nNothing was written. Move or rename them, choose another --target,')
        say('or re-run with --force to replace (your existing copy is NOT backed up).')
        return 2
    target.mkdir(parents=True, exist_ok=True)
    for src in sources:
        dst = target / src.name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        say(f'  installed {src.name}')
    say(f'\n{len(sources)} skills installed to {target}')
    say('Start a new session so the skill list refreshes.')
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--target', type=Path, help='Agent skills directory, e.g. ~/.workbuddy/skills')
    ap.add_argument('--check', action='store_true', help='Only verify an existing installation')
    ap.add_argument('--force', action='store_true', help='Replace existing skill directories')
    args = ap.parse_args()
    if args.check:
        if not args.target:
            ap.error('--check requires --target')
        return check(args.target.expanduser())
    if not args.target:
        ap.error('--target is required to install')
    return install(args.target.expanduser(), args.force)


if __name__ == '__main__':
    sys.exit(main())

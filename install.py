#!/usr/bin/env python3
"""Install the iccad-review skill suite into an Agent skills directory.

Python 3.10+ standard library only, no network access.
Stops before writing anything if any target directory already exists.
"""
import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass

HERE = Path(__file__).resolve().parent
SRC = HERE / 'skills'
IGNORE = shutil.ignore_patterns('__pycache__', '*.pyc', '.venv', '.work')


def skill_name(skill_md):
    """Read `name` from the YAML frontmatter of a SKILL.md; None if absent."""
    text = skill_md.read_text(encoding='utf-8')
    if not text.startswith('---'):
        return None
    end = text.find('\n---', 3)
    if end < 0:
        return None
    for line in text[3:end].splitlines():
        key, _, value = line.partition(':')
        if key.strip() == 'name':
            return value.strip().strip('"').strip("'")
    return None


def say(msg):
    print(msg, flush=True)


def discover():
    if not SRC.is_dir():
        raise SystemExit(f'skills/ not found next to {Path(__file__).name}')
    return sorted(p for p in SRC.iterdir() if p.is_dir() and (p / 'SKILL.md').is_file())


def looks_like_engine(path):
    """The deterministic engine build ships engine/ bytecode and a .venv."""
    return (path / 'engine').is_dir()


def rename_engine_skill(target):
    """Move an existing engine skill named iccad-review aside so both can coexist."""
    busy = target / 'iccad-review'
    free = target / 'iccad-engine'
    if not busy.is_dir() or not looks_like_engine(busy):
        return None
    if free.exists():
        return ('skip', f'{free} already exists; leaving {busy} untouched')
    busy.rename(free)
    skill_md = free / 'SKILL.md'
    if skill_md.is_file():
        text = skill_md.read_text(encoding='utf-8')
        head, sep, tail = text.partition('\n---')
        if sep and 'name: iccad-review' in head:
            skill_md.write_text(head.replace('name: iccad-review', 'name: iccad-engine', 1) + sep + tail,
                                encoding='utf-8')
    return ('renamed', f'{busy.name} -> {free.name} (frontmatter name synced)')


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
        name_ok = skill_name(skill_md) == src.name
        rows.append((src.name, 'OK' if name_ok else 'NAME-MISMATCH'))
        bad += 0 if name_ok else 1
    for name, state in rows:
        say(f'  {state:<14} {name}')
    say(f'\n{len(rows)} skills checked, {bad} problem(s). target={target}')
    return 0 if bad == 0 else 2


def install(target, force, engine_rename=False, backup=False):
    sources = discover()
    names = catalog_names()
    missing = sorted(set(p.name for p in sources) ^ set(names))
    if missing:
        say(f'catalog.json and skills/ disagree on: {", ".join(missing)}')
        return 2
    if engine_rename:
        outcome = rename_engine_skill(target)
        if outcome and outcome[0] == 'renamed':
            say(f'已避让同名引擎技能：{outcome[1]}')
            say('  （引擎与套件并存；还原方式：把目录改回 iccad-review，并把 SKILL.md 的 name 改回）')
        elif outcome:
            say(f'注意：{outcome[1]}')
    conflicts = [p.name for p in sources if (target / p.name).exists()]
    if conflicts and not force:
        say('Refusing to write: these target directories already exist —')
        for name in conflicts:
            say(f'  {target / name}')
        say('\nNothing was written. Move or rename them, choose another --target,')
        say('or re-run with --force to replace (add --backup to keep your existing copy).')
        if 'iccad-review' in conflicts:
            say('若同名的是确定性引擎技能，加 --engine-rename 可自动把它改名为 iccad-engine。')
        return 2
    target.mkdir(parents=True, exist_ok=True)
    backup_root = None
    if backup and conflicts:
        backup_root = target / f'.iccad-backup-{datetime.now():%Y%m%d-%H%M%S}'
        backup_root.mkdir(parents=True, exist_ok=True)
    for src in sources:
        dst = target / src.name
        if dst.exists():
            if backup_root:
                shutil.move(str(dst), str(backup_root / src.name))
            else:
                shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=IGNORE)
        say(f'  installed {src.name}')
    say(f'\n{len(sources)} skills installed to {target}')
    if backup_root:
        say(f'旧版本已备份到：{backup_root}')
    say('Start a new session so the skill list refreshes.')
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--target', type=Path, help='Agent skills directory, e.g. ~/.workbuddy/skills')
    ap.add_argument('--check', action='store_true', help='Only verify an existing installation')
    ap.add_argument('--force', action='store_true', help='Replace existing skill directories')
    ap.add_argument('--engine-rename', action='store_true',
                    help='If an iccad-review engine skill exists in the target, rename it to iccad-engine first')
    ap.add_argument('--backup', action='store_true',
                    help='With --force, move existing directories to a hidden .iccad-backup-<time> folder instead of deleting')
    args = ap.parse_args()
    if args.backup and not args.force:
        ap.error('--backup only makes sense together with --force')
    if args.check:
        if not args.target:
            ap.error('--check requires --target')
        return check(args.target.expanduser())
    if not args.target:
        ap.error('--target is required to install')
    return install(args.target.expanduser(), args.force, args.engine_rename, args.backup)


if __name__ == '__main__':
    sys.exit(main())

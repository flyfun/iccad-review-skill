#!/usr/bin/env python3
"""把 SLReview_Py 的 10 个专业审查包同步进本套件的依据库。

Python 3.10+ 标准库，无网络访问。

引擎仓的 `skills/<pack>/` 里放着已经校准过的领域资产：检查清单（含条款号）、
强制性条文、错情模式、限值表、复算脚本。本脚本把它们复制成本套件的
`skills/iccad-review/references/domain-packs/<slug>/`，让 17 个 Skill 在
无引擎环境下也能查到具体条款与限值。

三条同步纪律：

1. **单向复制，不做合并**。套件里的 domain-packs 是生成物，人工修改会在
   下次同步时被覆盖；要改口径请改引擎仓，然后重跑本脚本。
2. **规范全文类文件默认不同步**。引擎包里 `references/*_clauses.json`（条文抽取件，
   合计约 37 MB）与 `references/*_clauses_src.txt`（逐条条文源文本）都属于标准原文，
   既有授权边界问题、又会把仓库撑大。默认跳过；本机自用可加 `--clauses` 只同步到
   工作副本（已在 .gitignore 里排除）。
3. **来源可追溯**。每次同步写 `_manifest.json`（包 → 文件 → sha256 / 行数）
   并记录引擎版本，便于判断依据库是否落后于引擎。

用法::

    # 同步（默认跳过条文 JSON 与条文源文本）
    python scripts/sync_domain_packs.py --engine-root "C:/Users/Flyfun/Desktop/新建文件夹 (3)/SLReview_Py"

    # 只检查依据库是否与引擎一致，不写文件
    python scripts/sync_domain_packs.py --engine-root ... --check

    # 本机自用：连条文类文件一起同步（体积 +37 MB，勿提交）
    python scripts/sync_domain_packs.py --engine-root ... --clauses
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
TARGET = HERE / 'skills' / 'iccad-review' / 'references' / 'domain-packs'

# 引擎包名 -> 本套件 slug。顺序即索引顺序，改动会让 _manifest.json 的键变化。
PACKS = {
    'flood-impact-report-review': 'flood-impact',
    'earth-dam-report-review': 'earth-dam',
    'gravity-dam-report-review': 'gravity-dam',
    'sluice-report-review': 'sluice',
    'pump-station-report-review': 'pump-station',
    'river-channel-report-review': 'river-channel',
    'port-waterway-report-review': 'port-waterway',
    'soil-conservation-report-review': 'soil-conservation',
    'water-resources-report-review': 'water-resources',
    'hydro-report-review-builder': 'report-builder',
}

MANIFEST = '_manifest.json'
# 规范全文类文件：默认不同步（授权边界 + 体积）
#   *_clauses.json      条文抽取件（约 37 MB）
#   *_clauses_src.txt   条文源文本（逐条原文，供 build_clauses.py 生成上面的 json）
HEAVY_SUFFIXES = ('_clauses.json', '_clauses_src.txt')

PROVENANCE = """<!--
本文件由 scripts/sync_domain_packs.py 从 SLReview_Py 引擎仓复制生成，不要手工修改。
源文件：{source}
引擎版本：{version}
同步时间：{when}
口径以引擎仓为准；重跑同步脚本即可覆盖。
-->

"""


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def engine_version(root):
    """从引擎 src/app_info.py 读 APP_VERSION；读不到就记 unknown。"""
    info = root / 'src' / 'app_info.py'
    if not info.is_file():
        return 'unknown'
    text = info.read_text(encoding='utf-8', errors='ignore')
    match = re.search(r'APP_VERSION\s*=\s*[\'"]([^\'"]+)[\'"]', text)
    return match.group(1) if match else 'unknown'


def strip_frontmatter(text):
    """去掉 SKILL.md 的 YAML frontmatter，只留正文。"""
    if not text.startswith('---'):
        return text
    end = text.find('\n---', 3)
    if end < 0:
        return text
    return text[end + 4:].lstrip('\n')


def collect(pack_dir, with_clauses):
    """返回 [(相对目标路径, 源路径, 是否改写)]，按稳定顺序。"""
    entries = []
    skill_md = pack_dir / 'SKILL.md'
    if skill_md.is_file():
        entries.append(('overview.md', skill_md, True))

    for sub in ('references', 'scripts'):
        base = pack_dir / sub
        if not base.is_dir():
            continue
        for item in sorted(base.iterdir()):
            if not item.is_file():
                continue
            if not with_clauses and any(item.name.endswith(s) for s in HEAVY_SUFFIXES):
                continue
            entries.append((f'{sub}/{item.name}', item, False))

    templates = pack_dir / 'templates'
    if templates.is_dir():
        for item in sorted(templates.iterdir()):
            if item.is_file():
                entries.append((f'templates/{item.name}', item, False))
    return entries


def build_manifest(engine_root, with_clauses):
    version = engine_version(engine_root)
    when = datetime.now().strftime('%Y-%m-%d %H:%M')
    packs, missing = {}, []
    src_root = engine_root / 'skills'
    for engine_name, slug in PACKS.items():
        pack_dir = src_root / engine_name
        if not pack_dir.is_dir():
            missing.append(engine_name)
            continue
        files = {}
        for rel, src, rewritten in collect(pack_dir, with_clauses):
            files[rel] = {
                'sha256': sha256_of(src),
                'source': f'skills/{engine_name}/{src.relative_to(pack_dir).as_posix()}',
                'rewritten': rewritten,
            }
        packs[slug] = {
            'source_skill': engine_name,
            'files': files,
        }
    return {'engine_version': version, 'synced_at': when, 'packs': packs}, missing


def read_text(path):
    return path.read_text(encoding='utf-8', errors='ignore')


def existing_manifest():
    path = TARGET / MANIFEST
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except ValueError:
        return {}


def diff(manifest):
    """把目标现状与期望比对，返回问题列表。"""
    old = existing_manifest()
    problems = []
    if not old:
        return ['domain-packs 尚未同步（_manifest.json 不存在）']
    if old.get('engine_version') != manifest['engine_version']:
        problems.append(f"引擎版本变化：{old.get('engine_version')} -> {manifest['engine_version']}")
    old_packs, new_packs = old.get('packs', {}), manifest['packs']
    for slug in sorted(set(old_packs) | set(new_packs)):
        if slug not in old_packs:
            problems.append(f'{slug}: 依据库缺失')
            continue
        if slug not in new_packs:
            problems.append(f'{slug}: 引擎侧已无此包')
            continue
        old_files, new_files = old_packs[slug]['files'], new_packs[slug]['files']
        for rel in sorted(set(new_files) - set(old_files)):
            problems.append(f'{slug}/{rel}: 引擎有、依据库缺')
        for rel in sorted(set(old_files) - set(new_files)):
            problems.append(f'{slug}/{rel}: 依据库有、引擎已删')
        for rel in sorted(set(old_files) & set(new_files)):
            if old_files[rel]['sha256'] != new_files[rel]['sha256']:
                problems.append(f'{slug}/{rel}: 内容不一致')
    return problems


def sync(manifest, engine_root):
    """按 manifest 重建 domain-packs（只动 TARGET 内的包目录）。"""
    version = manifest['engine_version']
    when = manifest['synced_at']
    TARGET.mkdir(parents=True, exist_ok=True)

    written = 0
    for slug, info in manifest['packs'].items():
        dest = TARGET / slug
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)
        for rel, meta in info['files'].items():
            # manifest 存的是源相对路径（skills/<pack>/…），按 source 字段定位
            src = engine_root / meta['source']
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            if meta['rewritten']:
                body = strip_frontmatter(read_text(src))
                header = PROVENANCE.format(source=meta['source'], version=version, when=when)
                out.write_text(header + body, encoding='utf-8')
            else:
                shutil.copyfile(src, out)
            written += 1

    for slug in PACKS.values():
        if slug not in manifest['packs']:
            stale = TARGET / slug
            if stale.exists():
                shutil.rmtree(stale)

    (TARGET / MANIFEST).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
    return written


def summarize(manifest):
    packs = manifest['packs']
    md = sum(1 for p in packs.values() for f in p['files'] if f.endswith('.md'))
    py = sum(1 for p in packs.values() for f in p['files'] if f.endswith('.py'))
    total = sum(len(p['files']) for p in packs.values())
    return len(packs), total, md, py


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--engine-root', type=Path, required=True,
                    help='SLReview_Py 仓库根目录（其下有 skills/ 与 src/）')
    ap.add_argument('--check', action='store_true', help='只比对，不写文件')
    ap.add_argument('--clauses', action='store_true',
                    help='连条文类文件（*_clauses.json / *_clauses_src.txt）一起同步（约 37 MB，勿提交）')
    args = ap.parse_args()

    root = args.engine_root.expanduser().resolve()
    if not (root / 'skills').is_dir():
        print(f'找不到 {root / "skills"}，--engine-root 应指向 SLReview_Py 仓库根目录')
        return 2

    manifest, missing = build_manifest(root, args.clauses)
    if missing:
        print(f'警告：引擎侧缺少这些包，将不写入依据库：{", ".join(missing)}')
    n_packs, n_files, n_md, n_py = summarize(manifest)

    if args.check:
        problems = diff(manifest)
        if problems:
            print(f'依据库与引擎不一致（{len(problems)} 处）：')
            for item in problems[:40]:
                print(f'  - {item}')
            if len(problems) > 40:
                print(f'  … 另有 {len(problems) - 40} 处')
            return 2
        print(f'OK 依据库与引擎一致：{n_packs} 包 / {n_files} 文件 / 引擎 {manifest["engine_version"]}')
        return 0

    written = sync(manifest, root)
    print(f'已同步 {n_packs} 个专业包 / {written} 个文件（md {n_md} · py {n_py}）')
    print(f'目标：{TARGET}')
    print(f'引擎版本：{manifest["engine_version"]}')
    if not args.clauses:
        print('条文类文件（*_clauses.json / *_clauses_src.txt）未同步（如需本机自用加 --clauses，注意不要提交）。')
    return 0


if __name__ == '__main__':
    sys.exit(main())

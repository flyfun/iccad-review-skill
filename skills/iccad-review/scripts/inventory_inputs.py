#!/usr/bin/env python3
"""Inventory authorised review material: file list, byte hashes, parsing capability.

Python 3.10+ standard library only. Output is a candidate list for the intake step;
it does not establish that a document is authorised, signed or the controlled revision.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SKIP_DIRS = {'.git', '.venv', '__pycache__', '.work', 'node_modules', '.idea'}
CAPABILITY = {
    '.docx': 'text_and_tables', '.doc': 'text_and_tables_legacy', '.pdf': 'text_or_scanned',
    '.txt': 'text', '.md': 'text', '.xlsx': 'tables', '.xls': 'tables', '.csv': 'tables',
    '.dwg': 'drawing_list_or_none', '.dxf': 'drawing_list_or_none',
    '.jpg': 'image_only', '.jpeg': 'image_only', '.png': 'image_only', '.tif': 'image_only',
    '.zip': 'archive_needs_unpack',
}
DRAWING_HINT = ('图', 'drawing', 'dwg', '图纸')


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def guess_discipline(name):
    lowered = name.lower()
    table = (
        ('geotech', ('地质', '勘察', 'geolog')),
        ('cost', ('概算', '估算', '投资', '施工组织', '导流', 'cost', 'boq')),
        ('soil_water', ('水保', '水土保持', 'soilstop')),
        ('water_resource', ('水资源', '取水', '论证')),
        ('environment', ('环评', '环境', '生态')),
        ('flood_eval', ('防洪评价', '洪水影响', '涉河')),
        ('hydrology', ('水文', '泥沙', '洪水')),
        ('coordination', ('附图', '附表', '目录', '总图')),
    )
    for discipline, words in table:
        if any(word in lowered for word in words):
            return discipline
    return None


def inventory(root, max_files=2000):
    root = Path(root).resolve()
    files, skipped = [], []
    for path in sorted(root.rglob('*')):
        if path.is_dir():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            stat = path.stat()
        except OSError as exc:
            skipped.append({'path': str(path.relative_to(root)), 'reason': str(exc)})
            continue
        if len(files) >= max_files:
            skipped.append({'path': str(path.relative_to(root)), 'reason': 'file limit reached'})
            continue
        ext = path.suffix.lower()
        try:
            digest = sha256_of(path)
        except OSError as exc:
            skipped.append({'path': str(path.relative_to(root)), 'reason': str(exc)})
            continue
        files.append({
            'path': str(path.relative_to(root)),
            'sha256': digest,
            'size': stat.st_size,
            'ext': ext,
            'capability': CAPABILITY.get(ext, 'unknown'),
            'discipline_guess': guess_discipline(path.name),
            'suggested_source_id': f'S{len(files) + 1:02d}',
        })
    by_ext = {}
    for item in files:
        by_ext[item['ext'] or '(none)'] = by_ext.get(item['ext'] or '(none)', 0) + 1
    return {
        'schema': 'input-inventory/1.0',
        'root': str(root),
        'generated_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        'file_count': len(files),
        'total_bytes': sum(item['size'] for item in files),
        'by_ext': dict(sorted(by_ext.items(), key=lambda kv: -kv[1])),
        'files': files,
        'skipped': skipped,
        'notes': [
            'These are candidates only; confirm the authorised revision and scope before review.',
            'capability describes what the format can support here, not what the model actually read.',
            'drawing_list_or_none means no geometry parser is available; record such checks as unsupported.',
        ],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('root', type=Path, help='authorised material directory')
    ap.add_argument('--output', type=Path, help='write JSON here (default: stdout)')
    ap.add_argument('--max-files', type=int, default=2000)
    args = ap.parse_args()
    if not args.root.is_dir():
        print(f'Not a directory: {args.root}')
        return 2
    result = inventory(args.root, args.max_files)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding='utf-8')
        print(f'{result["file_count"]} files, {result["total_bytes"]} bytes -> {args.output}')
    else:
        print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())

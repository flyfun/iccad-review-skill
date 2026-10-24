#!/usr/bin/env python3
"""Convert the optional iccad-review engine scan into candidate review checks.

Python 3.10+ standard library only. The engine is NOT required by this suite.
Engine hits are candidates: they are imported with confidence<=medium, review.status=pending,
and never as a finished finding. Hits without a locatable quote become insufficient_input
instead of an invented citation.

Usage:
    python import_scan.py scan.json --document 报告.docx --out review.json [--module M4]
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

DOMAIN_TO_MODULE = {
    '土石坝': 'M1', '混凝土坝': 'M2', '堤防': 'M3', '河道': 'M3', '水闸': 'M4', '泵站': 'M4',
    '隧洞': 'M4', '水电站': 'M4', '灌区': 'M5', '水土保持': 'M7', '水运工程': 'M4', '通用': 'M4',
}
CATEGORY_TO_DISCIPLINE = {
    '数值': 'general', '强制性条文': 'general', '强条': 'general', '跨规范': 'general',
    '规范': 'general', '过时法规': 'general', '工程经验专项': 'general', '公式': 'hydraulic',
    '计算': 'hydraulic', '地质': 'geotech', '施工': 'cost', '概算': 'cost', '水保': 'soil_water',
}
SUGGESTED_DISCIPLINE = ('hydrology', 'dam', 'gate_pump', 'geotech', 'hydraulic', 'structure',
                        'flood_eval', 'soil_water', 'water_resource', 'environment', 'resettlement',
                        'cost', 'coordination', 'general')


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def pick_discipline(*texts):
    blob = ' '.join(t for t in texts if t)
    for discipline, words in (
        ('geotech', ('地质', '勘察', '地基', '边坡', '承载力')),
        ('cost', ('概算', '投资', '单价', '工程量', '施工组织', '导流', '进度')),
        ('soil_water', ('水土保持', '水保', '弃渣')),
        ('water_resource', ('水资源', '取水', '用水定额', '供需平衡')),
        ('environment', ('环境', '生态', '环评')),
        ('flood_eval', ('防洪评价', '阻水', '冲刷', '涉河')),
        ('hydrology', ('水文', '洪水', '径流', '频率', '泥沙')),
        ('structure', ('稳定', '应力', '配筋', '抗滑', '抗倾覆')),
        ('hydraulic', ('水力', '过流', '渗流', '消能', '水面线')),
        ('dam', ('坝', '溢洪道', '防渗')),
        ('gate_pump', ('闸', '泵', '渠', '渡槽', '倒虹吸', '管道')),
    ):
        if any(word in blob for word in words):
            return discipline
    return 'general'


def build_review(scan, document, name=None, module=None, stage='preliminary', grade=None,
                 baseline_id='imported', review_date=None):
    """Build a structurally valid review record from an engine scan payload."""
    document = Path(document)
    review_date = review_date or date.today().isoformat()
    scanned = scan.get('scan', {}) if isinstance(scan.get('scan'), dict) else {}
    engine_domain = scanned.get('primary_domain') or '通用'
    module = module or DOMAIN_TO_MODULE.get(engine_domain, 'M4')

    doc_sha = sha256_of(document) if document.is_file() else '0' * 64
    sources = [{
        'id': 'S01',
        'path': document.name,
        'sha256': doc_sha,
        'revision': f"engine import {review_date}",
        'discipline': 'general',
        'capability': 'text',
        'locator_convention': '章节号 / 表号 / 图号 / 页码；引擎原文检索结果',
    }]

    checks, findings = [], []
    seq_c = seq_f = 0
    for raw in scanned.get('errors') or []:
        content = (raw.get('content') or '').strip()
        if not content:
            continue
        seq_c += 1
        cid = f'E{seq_c:03d}'
        quote = (raw.get('quote') or '').strip()
        category = raw.get('category') or '确定性检查'
        discipline = pick_discipline(raw.get('category'), content, raw.get('explanation'))
        explanation = (raw.get('explanation') or '').strip() or category
        locator = (raw.get('location') or '').strip() or '全文'
        if quote:
            evidence = [{
                'source_id': 'S01',
                'source_sha256': doc_sha,
                'locator': locator,
                'excerpt': quote,
            }]
            checks.append({
                'id': cid,
                'rule_id': None,
                'origin': 'engine',
                'engine_ref': category,
                'basis_ids': [],
                'source_ids': ['S01'],
                'status': 'evaluated',
                'result': 'signal',
                'reason': explanation[:300],
                'evidence': evidence,
            })
            seq_f += 1
            suggestions_only = bool(raw.get('is_suggestion'))
            kind = 'missing_information' if raw.get('finding_type') == 'missing' else 'rule_deviation'
            findings.append({
                'id': f'F{seq_f:03d}',
                'check_id': cid,
                'kind': kind,
                'discipline': discipline,
                'title': content[:60],
                'observation': content,
                'priority': 'P3' if suggestions_only else 'P2',
                'confidence': 'medium',
                'basis_ids': [],
                'evidence': evidence,
                'suggested_action': (raw.get('suggestion') or '请人工核实并补充依据。')[:400],
                'review': {'status': 'pending'},
                'closure': {'status': 'open'},
            })
        else:
            checks.append({
                'id': cid,
                'rule_id': None,
                'origin': 'engine',
                'engine_ref': category,
                'basis_ids': [],
                'source_ids': ['S01'],
                'status': 'insufficient_input',
                'result': None,
                'reason': ('引擎命中但未给出可定位引文，须人工定位后再判定；'
                           f'引擎说明：{explanation[:200]}'),
                'evidence': [],
            })

    for raw in scan.get('spec_codes') or []:
        if raw.get('valid') is not False:
            continue
        seq_c += 1
        cid = f'E{seq_c:03d}'
        code = raw.get('code') or ''
        evidence = [{
            'source_id': 'S01',
            'source_sha256': doc_sha,
            'locator': '全文（引擎规范号检索）',
            'excerpt': f'{code}（{raw.get("name") or ""}）'.strip(),
        }]
        checks.append({
            'id': cid,
            'rule_id': None,
            'origin': 'engine',
            'engine_ref': 'spec_registry',
            'basis_ids': [],
            'source_ids': ['S01'],
            'status': 'evaluated',
            'result': 'signal',
            'reason': (raw.get('message') or f'{code} 未通过规范号有效性核对')[:300],
            'evidence': evidence,
        })
        seq_f += 1
        findings.append({
            'id': f'F{seq_f:03d}',
            'check_id': cid,
            'kind': 'rule_deviation',
            'discipline': 'general',
            'title': f'规范号引用存疑：{code}',
            'observation': raw.get('message') or f'{code} 未通过规范号有效性核对',
            'priority': 'P2',
            'confidence': 'medium',
            'basis_ids': [],
            'evidence': evidence,
            'suggested_action': '核对引用规范号的现行版本与替代关系，改用现行版本或说明适用范围。',
            'review': {'status': 'pending'},
            'closure': {'status': 'open'},
        })

    if not checks:
        checks.append({
            'id': 'E000',
            'rule_id': None,
            'origin': 'engine',
            'engine_ref': 'none',
            'basis_ids': [],
            'source_ids': ['S01'],
            'status': 'insufficient_input',
            'result': None,
            'reason': '引擎未返回任何命中；这不等于报告无问题，须按计划清单人工审查。',
            'evidence': [],
        })

    disciplines = sorted({f['discipline'] for f in findings} or {'general'})
    return {
        'schema_version': '1.0',
        'mode': 'project',
        'project': {
            'id': 'IMP-' + (document.stem or 'doc')[:20].replace(' ', '-'),
            'name': name or document.stem or '未命名项目',
            'region': '待补充',
            'project_type': engine_domain,
            'module': module,
            'modules_extra': [],
            'stage': stage,
            'grade': grade,
            'review_date': review_date,
            'baseline_date': review_date,
            'baseline_id': baseline_id,
            'scope_ref': f'引擎预扫导入（{document.name}）；模块来源 engine_domain={engine_domain}，须用 iccad-route 复核',
            'planned_check_ids': [c['id'] for c in checks],
            'requested_disciplines': disciplines,
            'data_class': 'unclassified',
            'processing': {
                'mode': 'local',
                'environment_verified': False,
                'authorization_ref': '待确认',
                'sanitization_ref': '待确认',
            },
        },
        'sources': sources,
        'bases': [],
        'rules': [],
        'checks': checks,
        'findings': findings,
        'conclusion': {'status': 'pending'},
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('scan', type=Path, help='engine scan JSON (wsl_scan.py --json output)')
    ap.add_argument('--document', type=Path, required=True, help='the report file the scan was run on')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--name')
    ap.add_argument('--module', choices=[f'M{i}' for i in range(1, 15)])
    ap.add_argument('--stage', default='preliminary')
    ap.add_argument('--grade', choices=['I', 'II', 'III', 'IV', 'V'])
    ap.add_argument('--baseline-id', default='imported')
    args = ap.parse_args()
    try:
        scan = json.loads(args.scan.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        print(f'Cannot read scan: {exc}')
        return 2
    review = build_review(scan, args.document, args.name, args.module, args.stage, args.grade, args.baseline_id)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Imported {len(review["checks"])} checks / {len(review["findings"])} candidate findings -> {args.out}')
    print('All candidates are unreviewed (confidence<=medium). Run iccad-route for the plan and validate_review.py afterwards.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

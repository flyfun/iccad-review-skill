#!/usr/bin/env python3
"""Self-check the suite against the synthetic assets.

Verifies that the validators, the renderer and the optional engine bridge behave as documented.
Nothing here proves engineering accuracy: every basis id, value and human record is fictional.
Exit 0 when all checks pass, 1 otherwise.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / 'assets'
sys.path.insert(0, str(HERE))

import import_scan  # noqa: E402
import render_report  # noqa: E402
import validate_review  # noqa: E402

results = []


def record(name, ok, detail=''):
    results.append((name, ok, detail))


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    review = load(ASSETS / 'example-review.json')
    complete = load(ASSETS / 'example-complete.json')
    scan = load(ASSETS / 'example-scan.json')

    # 1. incomplete record: structurally valid, signoff blocked
    got = validate_review.validate(review, ASSETS, False)
    record('example-review.json structure valid', not got['errors'], '; '.join(got['errors'][:3]))
    record('example-review.json gate blocked', bool(got['blockers']) and not got['ready_for_human_signoff'],
           f'{len(got["blockers"])} blocker(s)')

    # 2. file hashes match the synthetic sources
    got = validate_review.validate(review, ASSETS, True)
    record('example-review.json source hashes match', not got['errors'], '; '.join(got['errors'][:3]))

    # 3. complete record: gate passes
    got = validate_review.validate(complete, ASSETS, True)
    record('example-complete.json gate passes',
           not got['errors'] and got['ready_for_human_signoff'], '; '.join(got['errors'][:3]))

    # 4. tampering is detected
    tampered = json.loads(json.dumps(review))
    tampered['sources'][0]['sha256'] = 'f' * 64
    got = validate_review.validate(tampered, ASSETS, True)
    record('tampered hash is rejected', bool(got['errors']), got['errors'][0] if got['errors'] else 'no error')

    # 5. a numeric comparison that does not recompute is rejected
    tampered = json.loads(json.dumps(review))
    tampered['checks'][0]['comparison']['normalized_value'] = 94
    got = validate_review.validate(tampered, ASSETS, False)
    record('inconsistent unit conversion is rejected', bool(got['errors']),
           got['errors'][0] if got['errors'] else 'no error')

    # 6. a dropped planned check is a blocker, not a silent pass
    tampered = json.loads(json.dumps(review))
    tampered['project']['planned_check_ids'].append('C99')
    got = validate_review.validate(tampered, ASSETS, False)
    record('dropped planned check blocks signoff',
           any('C99' in b for b in got['blockers']), '; '.join(got['blockers'][:2]))

    # 7. an evaluated check cannot lean on a draft rule
    tampered = json.loads(json.dumps(review))
    tampered['checks'][0]['rule_id'] = 'R03'
    got = validate_review.validate(tampered, ASSETS, False)
    record('draft rule cannot be evaluated', bool(got['errors']),
           got['errors'][0] if got['errors'] else 'no error')

    # 8. renderer produces the documented sections
    text = render_report.render(review, 'example-review.json', '2026-10-24')
    markers = ['审查意见书（内部工作稿）', '一、审查概况', '三、审查意见', '第1条',
               '四、必查项核查声明', '五、未覆盖与缺口', '六、结论', '附、依据清单']
    missing = [m for m in markers if m not in text]
    record('renderer emits all sections', not missing, f'missing {missing}' if missing else '')

    # 9. engine bridge imports candidates without inventing citations
    built = import_scan.build_review(scan, ASSETS / 'synthetic-report.txt', name='合成导入示例',
                                     module='M1', grade='III')
    got = validate_review.validate(built, ASSETS, False)
    record('engine import is structurally valid', not got['errors'], '; '.join(got['errors'][:3]))
    record('engine import stays unreviewed',
           all(f['review']['status'] == 'pending' for f in built['findings']) and
           all(f['confidence'] in {'medium', 'low'} for f in built['findings']), '')
    no_quote = [c for c in built['checks'] if c['status'] == 'insufficient_input']
    record('engine hit without quote becomes insufficient_input',
           len(no_quote) >= 1 and all(not c['evidence'] for c in no_quote), '')

    # 10. format detection covers all three engine payloads
    verdict_payload = load(ASSETS / 'engine-clause-verdict.json')
    audit_payload = load(ASSETS / 'engine-checklist-audit.json')
    detected = [import_scan.detect_format(p)[0] for p in (verdict_payload, audit_payload, scan)]
    record('engine format detection', detected == ['clause-verdict', 'checklist-audit', 'engine-scan'],
           f'got {detected}')

    # 11. clause-verdict import: 5 态 -> 6 态, structurally valid
    verdicts = import_scan.build_review(verdict_payload, ASSETS / 'synthetic-report.txt',
                                        'clause-verdict', name='合成判词导入', module='M6')
    got = validate_review.validate(verdicts, ASSETS, False)
    record('verdict import is structurally valid', not got['errors'], '; '.join(got['errors'][:3]))
    by_ref = {c['engine_ref'].split(':')[1].split('@')[0]: c for c in verdicts['checks']}
    record('verdict 符合 -> no_signal',
           by_ref['块1-1']['status'] == 'evaluated' and by_ref['块1-1']['result'] == 'no_signal', '')
    record('verdict 不适用 -> not_applicable', by_ref['块10-1']['status'] == 'not_applicable', '')
    record('verdict 待核 -> unverified_basis', by_ref['块12-8']['status'] == 'unverified_basis', '')

    # 12. unverified quote must not become a finding
    bad_quote = by_ref['块6-13']
    record('verdict 不符合 without verified quote -> insufficient_input',
           bad_quote['status'] == 'insufficient_input' and not bad_quote['evidence'], '')
    record('no finding hangs off the unverified-quote check',
           not any(f['check_id'] == bad_quote['id'] for f in verdicts['findings']), '')

    # 13. 缺失 与 不符合 各自成疑点，且引擎的「重大」不升 P1
    kinds = {(f['check_id'], f['kind']) for f in verdicts['findings']}
    record('verdict 不符合 -> rule_deviation',
           (by_ref['块9-7']['id'], 'rule_deviation') in kinds, f'kinds={sorted(kinds)}')
    record('verdict 缺失 -> missing_information',
           (by_ref['块5-7']['id'], 'missing_information') in kinds, '')
    record('engine severity never yields P1',
           all(f['priority'] in {'P2', 'P3'} for f in verdicts['findings']), '')

    # 14. basis cards are unverified anchors, not accepted evidence
    record('engine clause anchors become unverified bases',
           len(verdicts['bases']) >= 2 and
           all(b['authority'] == 'unknown' and b['status'] == 'unknown' for b in verdicts['bases']), '')
    record('basis level derived from the standard code',
           {b['level'] for b in verdicts['bases']} == {'sl_t'}, '')

    # 15. missing-item evidence is a search scope, never a fabricated quote
    missing_check = by_ref['块5-7']
    record('missing item evidence records the search scope only',
           missing_check['evidence'][0]['locator'] == '全文（未命中）' and
           missing_check['evidence'][0]['excerpt'].startswith('检索范围'), '')

    # 16. checklist-audit: 缺失 must reach the ledger (regression guard)
    audit = import_scan.build_review(audit_payload, ASSETS / 'synthetic-report.txt',
                                     'checklist-audit', name='合成清单导入', module='M6')
    got = validate_review.validate(audit, ASSETS, False)
    record('audit import is structurally valid', not got['errors'], '; '.join(got['errors'][:3]))
    audit_by_ref = {c['engine_ref'].split(':')[1]: c for c in audit['checks']}
    record('audit 缺失 becomes a candidate finding', bool(audit['findings']), 'no finding produced')
    record('audit 缺失 -> P2 missing_information',
           any(f['kind'] == 'missing_information' and f['priority'] == 'P2' for f in audit['findings']), '')
    record('audit 部分覆盖 -> P3 low confidence',
           any(f['priority'] == 'P3' and f['confidence'] == 'low' for f in audit['findings']), '')
    record('audit 覆盖 -> no_signal',
           audit_by_ref['块1-1']['status'] == 'evaluated' and
           audit_by_ref['块1-1']['result'] == 'no_signal', '')

    failed = [r for r in results if not r[1]]
    for name, ok, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f'  ({detail})' if detail and not ok else ''))
    print(f'\n{len(results) - len(failed)}/{len(results)} checks passed')
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())

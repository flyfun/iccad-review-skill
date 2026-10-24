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

    failed = [r for r in results if not r[1]]
    for name, ok, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f'  ({detail})' if detail and not ok else ''))
    print(f'\n{len(results) - len(failed)}/{len(results)} checks passed')
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())

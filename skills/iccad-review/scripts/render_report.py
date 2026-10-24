#!/usr/bin/env python3
"""Render an internal review report (Markdown) from a review record.

Python 3.10+ standard library only. Output is an internal working draft;
it is not a signed review opinion and never states that a design has passed review.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

MODULE_LABELS = {
    'M1': '土石坝 / 水库', 'M2': '混凝土坝 / 拱坝', 'M3': '堤防 / 河道治理',
    'M4': '水闸 / 泵站 / 输水建筑物', 'M5': '灌区 / 农田水利', 'M6': '防洪评价（洪水影响评价）',
    'M7': '水土保持方案', 'M8': '水资源论证', 'M9': '环境影响评价', 'M10': '安全鉴定',
    'M11': '重大设计变更 / 建设方案复核', 'M12': '规划同意书论证',
    'M13': '河湖健康评价', 'M14': '幸福河湖建设 / 评估',
}
STAGE_LABELS = {
    'proposal': '项目建议书', 'feasibility': '可行性研究', 'preliminary': '初步设计',
    'construction_doc': '施工图 / 技施设计', 'special': '专项报告', 'safety_appraisal': '安全鉴定',
    'design_change': '重大设计变更', 'evaluation': '评价评估',
}
STATUS_LABELS = {
    'evaluated': '已求值', 'not_applicable': '不适用', 'insufficient_input': '材料不足',
    'unsupported': '能力不支持', 'unverified_basis': '依据未核验', 'error': '执行错误',
}
PRIORITY_LABELS = {'P1': '重大', 'P2': '一般', 'P3': '建议'}
KIND_LABELS = {
    'rule_deviation': '偏离规则 / 强条', 'document_conflict': '图文或篇章矛盾',
    'calculation_inconsistency': '计算不一致', 'missing_information': '资料缺失',
}
CONFIDENCE_LABELS = {'high': '高', 'medium': '中', 'low': '低'}
REVIEW_LABELS = {'pending': '待复核', 'adopted': '已采用', 'not_applicable': '不适用', 'undetermined': '未定论'}
CLOSURE_LABELS = {
    'open': '未闭环', 'response_submitted': '已回复待验', 'recheck_required': '需复查',
    'closed': '已闭环', 'not_applicable': '不适用',
}
CONCLUSION_LABELS = {
    'pending': '待人工填写', 'pass': '通过（人工结论）',
    'pass_with_revision': '修改后通过（人工结论）', 'fail': '不通过（人工结论）',
}
OPERATOR_SYMBOLS = {'ge': '≥', 'le': '≤', 'gt': '>', 'lt': '<', 'eq': '='}
RESULT_LABELS = {'signal': '存在疑点', 'no_signal': '未发现疑点'}


def esc(value):
    if value is None:
        return '—'
    text = str(value).replace('|', '\\|')
    return text.replace('\n', ' ').strip() or '—'


def render(data, source_path='review.json', generated=None):
    project = data.get('project', {})
    bases = {b['id']: b for b in data.get('bases', [])}
    sources = {s['id']: s for s in data.get('sources', [])}
    rules = {r['id']: r for r in data.get('rules', [])}
    checks = data.get('checks', [])
    findings = data.get('findings', [])
    conclusion = data.get('conclusion', {}) or {}
    mode = data.get('mode', 'project')
    generated = generated or date.today().isoformat()

    out = []
    out.append('# 审查意见书（内部工作稿）')
    out.append('')
    out.append(f'> 生成日期：{generated}　记录文件：`{source_path}`　模式：'
               f'{"合成演示（不得代表实际工程）" if mode == "synthetic" else "实际项目"}')
    out.append('> 本文件由套件根据工作记录渲染，是**内部工作稿**；结论、处置与闭环只能由人工填写。'
               '不得据此对外表述为「工程已通过审查」。')
    out.append('')

    out.append('## 一、审查概况')
    out.append('')
    out.append('| 项 | 内容 |')
    out.append('|---|---|')
    modules = [project.get('module')] + list(project.get('modules_extra') or [])
    module_text = '、'.join(f'{m} {MODULE_LABELS.get(m, "")}'.strip() for m in modules if m)
    out.append(f"| 项目 | {esc(project.get('name'))}（{esc(project.get('id'))}） |")
    out.append(f"| 地区 / 类型 | {esc(project.get('region'))} / {esc(project.get('project_type'))} |")
    out.append(f"| 工程等别 | {esc(project.get('grade'))} 等 |")
    out.append(f"| 审查模块 | {esc(module_text)} |")
    out.append(f"| 设计阶段 | {esc(STAGE_LABELS.get(project.get('stage'), project.get('stage')))} |")
    out.append(f"| 资料基线 | {esc(project.get('baseline_id'))}（基线日 {esc(project.get('baseline_date'))}） |")
    out.append(f"| 审查日期 | {esc(project.get('review_date'))} |")
    out.append(f"| 审查范围 | {esc(project.get('scope_ref'))} |")
    disciplines = project.get('requested_disciplines') or []
    out.append(f"| 涉及专业 | {esc('、'.join(disciplines))} |")
    proc = project.get('processing') or {}
    out.append(f"| 处理环境 | {esc(proc.get('mode'))}（已核验：{'是' if proc.get('environment_verified') else '否'}） |")
    out.append('')

    counts = {}
    for c in checks:
        counts[c.get('status')] = counts.get(c.get('status'), 0) + 1
    planned = project.get('planned_check_ids') or []
    evaluated = counts.get('evaluated', 0)
    out.append('## 二、覆盖统计')
    out.append('')
    out.append(f'- 计划检查项：**{len(planned)}**；已求值 **{evaluated}**；不适用 **{counts.get("not_applicable", 0)}**')
    gaps = {k: v for k, v in counts.items() if k in {'insufficient_input', 'unsupported', 'unverified_basis', 'error'}}
    if gaps:
        detail = '、'.join(f'{STATUS_LABELS.get(k, k)} {v}' for k, v in sorted(gaps.items()))
        out.append(f'- 未完成（计入缺口，不构成已审查）：{detail}')
    out.append(f'- 疑点合计：**{len(findings)}**'
               f'（重大 {sum(1 for f in findings if f.get("priority") == "P1")}、'
               f'一般 {sum(1 for f in findings if f.get("priority") == "P2")}、'
               f'建议 {sum(1 for f in findings if f.get("priority") == "P3")}）')
    out.append('')
    out.append('> 条数不等于覆盖。未求值、能力不支持与依据未核验的项目已单列于第五节，不能计入「已审查」。')
    out.append('')

    out.append('## 三、审查意见')
    out.append('')
    if not findings:
        out.append('本轮记录中没有疑点。若无有效检查，这不表示报告无问题。')
        out.append('')
    order = {'P1': 0, 'P2': 1, 'P3': 2}
    numbered = sorted(findings, key=lambda f: (order.get(f.get('priority'), 9), str(f.get('id'))))
    for index, f in enumerate(numbered, 1):
        check = next((c for c in checks if c.get('id') == f.get('check_id')), {})
        out.append(f'### 第{index}条　{f.get("title", "")}')
        out.append('')
        out.append(f'- **严重程度**：{PRIORITY_LABELS.get(f.get("priority"), f.get("priority"))}'
                   f'　**类别**：{KIND_LABELS.get(f.get("kind"), f.get("kind"))}'
                   f'　**专业**：{esc(f.get("discipline"))}'
                   f'　**证据置信**：{CONFIDENCE_LABELS.get(f.get("confidence"), f.get("confidence"))}')
        out.append(f'- **问题描述**：{esc(f.get("observation"))}')
        basis_text = []
        for bid in f.get('basis_ids') or []:
            b = bases.get(bid, {})
            label = b.get('identifier') or b.get('title') or bid
            clause = b.get('clause')
            basis_text.append(f'{label}{(" " + clause) if clause else ""}（{bid}）')
        if basis_text:
            out.append(f'- **审查依据**：{"；".join(basis_text)}')
        else:
            out.append('- **审查依据**：工程判断（未挂依据，须人工确认）')
        ev_lines = []
        for ev in f.get('evidence') or []:
            src = sources.get(ev.get('source_id'), {})
            ev_lines.append(f'`{ev.get("source_id")}` {src.get("path", "")} @ {ev.get("locator")}：'
                            f'「{ev.get("excerpt")}」')
        if ev_lines:
            out.append('- **证据定位**：')
            for line in ev_lines:
                out.append(f'  - {line}')
        if check.get('comparison'):
            cmp = check['comparison']
            out.append(f'- **数值比对**：{esc(cmp.get("object_ref"))} 实测 '
                       f'{esc(cmp.get("observed_value"))}{esc(cmp.get("observed_unit"))} → 归一 '
                       f'{esc(cmp.get("normalized_value"))}{esc(cmp.get("normalized_unit"))}；'
                       f'要求 {OPERATOR_SYMBOLS.get(cmp.get("operator"), esc(cmp.get("operator")))} '
                       f'{esc(cmp.get("threshold"))}{esc(cmp.get("threshold_unit"))}'
                       f'（前提已核验：{"是" if cmp.get("conditions_verified") else "否"}）')
        out.append(f'- **建议处理**：{esc(f.get("suggested_action"))}')
        review = f.get('review') or {}
        closure = f.get('closure') or {}
        out.append(f'- **人工处置**：{REVIEW_LABELS.get(review.get("status"), "未记录")}'
                   f'　**闭环状态**：{CLOSURE_LABELS.get(closure.get("status"), "未记录")}')
        out.append('')

    out.append('## 四、必查项核查声明')
    out.append('')
    out.append('| 检查项 | 状态 | 结论 | 说明 |')
    out.append('|---|---|---|---|')
    for cid in planned or [c.get('id') for c in checks]:
        c = next((x for x in checks if x.get('id') == cid), None)
        if c is None:
            out.append(f'| {esc(cid)} | 未执行 | — | 计划项缺少执行记录 |')
            continue
        rule = rules.get(c.get('rule_id'), {})
        ref = rule.get('criterion', {}).get('quantity') or rule.get('id') or c.get('engine_ref') or '—'
        result = c.get('result') or '—'
        out.append(f'| {esc(cid)}（{esc(ref)}） | {STATUS_LABELS.get(c.get("status"), c.get("status"))} '
                   f'| {RESULT_LABELS.get(result, esc(result))} | {esc(c.get("reason"))} |')
    out.append('')

    out.append('## 五、未覆盖与缺口')
    out.append('')
    gaps_list = [c for c in checks if c.get('status') in {'insufficient_input', 'unsupported', 'unverified_basis', 'error'}]
    if not gaps_list:
        out.append('无。')
    else:
        out.append('| 检查项 | 缺口类型 | 原因 |')
        out.append('|---|---|---|')
        for c in gaps_list:
            out.append(f'| {esc(c.get("id"))} | {STATUS_LABELS.get(c.get("status"), c.get("status"))} '
                       f'| {esc(c.get("reason"))} |')
    out.append('')
    unverified = [b for b in bases.values() if b.get('status') == 'unknown' or b.get('applicability') == 'unknown']
    if unverified:
        out.append('依据缺口（未核验或适用性未确认，相关结论不得作为定论）：')
        out.append('')
        for b in unverified:
            out.append(f"- {esc(b.get('title'))}（{esc(b.get('id'))}）：{esc(b.get('summary'))}")
        out.append('')

    out.append('## 六、结论')
    out.append('')
    out.append(f'- 结论状态：**{CONCLUSION_LABELS.get(conclusion.get("status"), "未填写")}**')
    if conclusion.get('status') not in (None, 'pending'):
        out.append(f"- 记录人：{esc(conclusion.get('actor'))}　时间：{esc(conclusion.get('at'))}"
                   f"　记录号：{esc(conclusion.get('record_ref'))}")
        out.append(f"- 说明：{esc(conclusion.get('note'))}")
    else:
        out.append('- 说明：结论须由审查责任人填写并留存记录，AI 不代为填写。')
    out.append('')

    out.append('## 附、依据清单')
    out.append('')
    if not bases:
        out.append('无。')
    else:
        out.append('| 依据 | 名称 | 条款 | 层级 | 强条 | 状态 | 适用性 |')
        out.append('|---|---|---|---|---|---|---|')
        for b in bases.values():
            out.append(f"| {esc(b.get('identifier'))} | {esc(b.get('title'))} | {esc(b.get('clause'))} "
                       f"| {esc(b.get('level'))} | {'是' if b.get('mandatory') else '否'} "
                       f"| {esc(b.get('status'))} | {esc(b.get('applicability'))} |")
    out.append('')
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('review', type=Path)
    ap.add_argument('--output', type=Path, help='write Markdown here (default: stdout)')
    ap.add_argument('--verify-files', action='store_true', help='also check source hashes and note failures in the report')
    ap.add_argument('--root', type=Path, help='material root for --verify-files')
    args = ap.parse_args()
    try:
        data = json.loads(args.review.read_text(encoding='utf-8'))
    except OSError as exc:
        print(f'Cannot read review file: {exc}')
        return 2
    except ValueError as exc:
        print(f'Invalid JSON: {exc}')
        return 2

    header = ''
    if args.verify_files:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        try:
            from validate_review import validate
        except ImportError as exc:
            print(f'--verify-files unavailable: {exc}')
            return 2
        result = validate(data, args.root or args.review.parent, True)
        if result['errors']:
            header = ('> ⚠️ 来源核验未通过，本稿的证据定位不可直接引用：\n> '
                      + '\n> '.join(result['errors'][:10]) + '\n\n')

    text = header + render(data, args.review.as_posix(), date.today().isoformat())
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding='utf-8')
        print(f'Wrote {args.output} ({len(text)} chars)')
    else:
        print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())

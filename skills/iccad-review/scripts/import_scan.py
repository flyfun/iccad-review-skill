#!/usr/bin/env python3
"""把确定性引擎的预扫/核对结果导入为候选检查项。

Python 3.10+ 标准库。引擎**不是**本套件的依赖；此处只做格式转换。

引擎（SLReview_Py）现在有三种可导入产物，本脚本自动识别：

| 格式 | 产生方式 | 判定粒度 |
|---|---|---|
| `engine-scan` | 旧 `wsl_scan.py --json` | 命中清单（数值/强条/规范号/经验专项） |
| `checklist-audit` | `python tools/checklist_audit.py 报告.docx --json out.json` | 逐项**覆盖度**（覆盖 / 部分覆盖 / 缺失） |
| `clause-verdict` | `python tools/clause_verdict.py 报告.docx --json out.json` | 逐项**条文判词**（符合 / 不符合 / 缺失 / 不适用 / 待核） |

三者的共同纪律（详见 `references/engine-bridge.md`）：

1. **引擎结论不等于审查定稿**。全部导入为 `origin=engine`、`confidence<=medium`、`review.status=pending`；
   证据可靠度与处置结论都要人工复核后填写。
2. **不自动产生 P1**。引擎可以标「重大」，但 P1 是人工的注意力分流，导入时最高只到 P2，
   严重度写进 `observation` 供复核者判断。
3. **无引文不补造**。判词声称「不符合」但引文未通过校验时，记 `insufficient_input` 而不是编一条证据；
   清单核对判「缺失」时，证据只能写**检索范围**，不能写成报告原文。
4. **依据卡一律待核验**。引擎给出的条款锚点（规范号 + 条号）落成 `authority=unknown`、`status=unknown`
   的依据卡并挂到疑点上；人工按 references/workflow/02-standards.md 核验后升为 `effective` 才能作为正式审查依据。

用法::

    python import_scan.py scan.json --document 报告.docx --out review/imported.json
    python import_scan.py audit.json --document 报告.docx --out review/imported.json --module M6
    python import_scan.py verdict.json --document 报告.docx --out review/imported.json --name "XX桥洪评"
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass

# engine profile keyword -> module（粗映射，最终以 workflow/04-route.md 的判定为准）
DOMAIN_TO_MODULE = {
    '土石坝': 'M1', '混凝土坝': 'M2', '重力坝': 'M2', '拱坝': 'M2', '堤防': 'M3', '河道': 'M3',
    '水闸': 'M4', '泵站': 'M4', '隧洞': 'M4', '水电站': 'M4', '灌区': 'M5', '防洪评价': 'M6',
    '洪水影响评价': 'M6', '水土保持': 'M7', '水资源': 'M8', '水运工程': 'M4', '通用': 'M4',
}

# 引擎判词的严重度 -> 套件优先级（引擎不得直接产生 P1）
SEVERITY_TO_PRIORITY = {'重大': 'P2', '一般': 'P2', '建议': 'P3'}

VERDICT_SIGNAL = '不符合'
VERDICT_OK = '符合'
VERDICT_MISSING = '缺失'
VERDICT_NA = '不适用'
VERDICT_UNSURE = '待核'

SPEC_CODE_RE = re.compile(r'([A-Z]{2,3}(?:/T)?)\s*([0-9]{2,5})(?:[.\-—]([0-9]{1,4}))?')


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def pick_discipline(*texts, default='general'):
    blob = ' '.join(t for t in texts if t)
    for discipline, words in (
        ('geotech', ('地质', '勘察', '地基', '边坡', '承载力', '渗透变形')),
        ('cost', ('概算', '投资', '单价', '工程量', '施工组织', '导流', '进度')),
        ('soil_water', ('水土保持', '水保', '弃渣', '扰动土地')),
        ('water_resource', ('水资源', '取水', '用水定额', '供需平衡', '来水量')),
        ('environment', ('环境', '生态', '环评')),
        ('flood_eval', ('防洪评价', '洪水影响', '阻水', '壅水', '冲刷', '涉河', '防汛抢险')),
        ('hydrology', ('水文', '洪水', '径流', '频率', '泥沙', '水位流量')),
        ('structure', ('稳定', '应力', '配筋', '抗滑', '抗倾覆', '抗浮')),
        ('hydraulic', ('水力', '过流', '渗流', '消能', '水面线', '过流能力')),
        ('dam', ('坝', '溢洪道', '防渗', '坝坡')),
        ('gate_pump', ('闸', '泵', '渠', '渡槽', '倒虹吸', '管道', '码头', '船闸')),
    ):
        if any(word in blob for word in words):
            return discipline
    return default


def basis_level(code):
    """规范号 -> 契约的 level 枚举；判断不了就返回 None（该字段可选）。"""
    compact = (code or '').upper().replace(' ', '')
    if compact.startswith(('GB/T', 'GB')):
        return 'gb'
    if compact.startswith('SL/T'):
        return 'sl_t'
    if compact.startswith('SL'):
        return 'sl'
    if compact.startswith('DB'):
        return 'db'
    return None


def detect_format(payload):
    """识别引擎输出格式。返回 (format, 说明)。"""
    if not isinstance(payload, dict):
        return 'unknown', '根节点不是对象'
    if isinstance(payload.get('verdicts'), list):
        return 'clause-verdict', '顶层含 verdicts[]'
    if isinstance(payload.get('items'), list) and 'summary' in payload:
        statuses = {str(i.get('status')) for i in payload['items'] if isinstance(i, dict)}
        if statuses & {'覆盖', '部分覆盖', '缺失'}:
            return 'checklist-audit', '顶层含 items[]，状态为覆盖度三态'
        if statuses & {VERDICT_OK, VERDICT_SIGNAL, VERDICT_UNSURE}:
            return 'clause-verdict', '顶层含 items[]，状态为条文判词五态'
    if isinstance(payload.get('scan'), dict) or isinstance(payload.get('errors'), list):
        return 'engine-scan', '顶层含 scan{} 或 errors[]'
    return 'unknown', '无法识别的结构（既无 verdicts[]/items[]，也无 scan{}/errors[]）'


class Collector:
    """累积 checks / findings / bases，统一分配 ID 并保持引用一致。"""

    def __init__(self, source_id, doc_sha):
        self.source_id = source_id
        self.doc_sha = doc_sha
        self.checks = []
        self.findings = []
        self.bases = []
        self._basis_index = {}

    # ---- 基础构件 ----
    def basis_for(self, code, clause, text=''):
        """为条款锚点建一张待核验依据卡；同一 (code, clause) 复用。"""
        code = (code or '').strip()
        clause = (clause or '').strip()
        if not code:
            return None
        key = (code, clause)
        if key in self._basis_index:
            return self._basis_index[key]
        bid = f'B{len(self.bases) + 1:02d}'
        snippet = (text or '').strip().replace('\n', ' ')
        summary = snippet[:200] if snippet else f'{code} {clause}'.strip() + '（引擎条款锚点，未经官方来源核验）'
        card = {
            'id': bid,
            'kind': 'standard',
            'title': f'{code} {clause}'.strip(),
            'identifier': code,
            'clause': clause or None,
            'source_ref': None,
            'authority': 'unknown',
            'level': basis_level(code),
            'mandatory': False,
            'status': 'unknown',
            'applicability': 'unknown',
            'effective_from': None,
            'effective_to': None,
            'verified_at': None,
            'verified_by': None,
            'transition_ref': None,
            'rights_basis': None,
            'summary': summary,
        }
        self.bases.append(card)
        self._basis_index[key] = bid
        return bid

    def quote_evidence(self, locator, excerpt):
        return [{
            'source_id': self.source_id,
            'source_sha256': self.doc_sha,
            'locator': locator or '全文',
            'excerpt': excerpt,
        }]

    def scope_evidence(self, scope_note, locator='全文（未命中）'):
        """检索范围类证据：只能陈述查了什么、命中多少，不得写成报告原文。"""
        return [{
            'source_id': self.source_id,
            'source_sha256': self.doc_sha,
            'locator': locator,
            'excerpt': scope_note,
        }]

    def add_check(self, **kwargs):
        cid = f'E{len(self.checks) + 1:03d}'
        check = {
            'id': cid,
            'rule_id': None,
            'origin': 'engine',
            'engine_ref': kwargs['engine_ref'],
            'basis_ids': kwargs.get('basis_ids') or [],
            'source_ids': [self.source_id],
            'status': kwargs['status'],
            'result': kwargs.get('result'),
            'reason': kwargs['reason'][:600],
            'evidence': kwargs.get('evidence') or [],
        }
        if kwargs.get('comparison') is not None:
            check['comparison'] = kwargs['comparison']
        self.checks.append(check)
        return cid

    def add_finding(self, check_id, kind, discipline, title, observation, priority,
                    confidence, basis_ids, evidence, action):
        fid = f'F{len(self.findings) + 1:03d}'
        self.findings.append({
            'id': fid,
            'check_id': check_id,
            'kind': kind,
            'discipline': discipline,
            'title': title[:120],
            'observation': observation[:1200],
            'priority': priority,
            'confidence': confidence,
            'basis_ids': basis_ids or [],
            'evidence': evidence or [],
            'suggested_action': action[:400],
            'review': {'status': 'pending'},
            'closure': {'status': 'open'},
        })
        return fid


# ------------------------------------------------------------------ 判词导入

def import_clause_verdict(payload, col, module_default):
    """clause_verdict.py 的 5 态判词 -> 契约 6 态。"""
    verdicts = [v for v in payload.get('verdicts') or [] if isinstance(v, dict)]
    for raw in verdicts:
        item_id = str(raw.get('item_id') or '').strip()
        point = str(raw.get('check_point') or '').strip() or item_id or '未命名检查项'
        block = str(raw.get('block') or '').strip()
        status = str(raw.get('status') or '').strip()
        reason = str(raw.get('reason') or '').strip()
        quote = str(raw.get('report_quote') or '').strip()
        code = str(raw.get('spec_code') or '').strip()
        clause = str(raw.get('clause_id') or '').strip()
        severity = str(raw.get('severity') or '').strip()
        fix = str(raw.get('fix') or '').strip()
        method = str(raw.get('method') or '').strip()
        cite_ok = bool(raw.get('citation_verified'))
        quote_ok = bool(raw.get('quote_verified'))
        engine_ref = f"clause-verdict:{item_id or point}" + (f"@{method}" if method else '')
        discipline = pick_discipline(block, point, reason, default=module_default)

        if status == VERDICT_OK:
            col.add_check(engine_ref=engine_ref, status='evaluated', result='no_signal',
                          reason=(reason or '引擎判为符合；本轮无信号。')[:600])
            continue
        if status == VERDICT_NA:
            col.add_check(engine_ref=engine_ref, status='not_applicable',
                          reason=reason or '引擎判为不适用，须人工确认不适用理由。')
            continue
        if status == VERDICT_UNSURE:
            col.add_check(engine_ref=engine_ref, status='unverified_basis',
                          reason=('引擎判为待核：' + (reason or '条文或事实前提不足'))[:600])
            continue
        if status not in (VERDICT_SIGNAL, VERDICT_MISSING):
            col.add_check(engine_ref=engine_ref, status='error',
                          reason=f'引擎返回无法识别的状态 {status!r}；须人工复核该检查项。')
            continue

        basis_id = col.basis_for(code, clause) if cite_ok else None
        basis_ids = [basis_id] if basis_id else []

        # 不符合：必须有可校验的引文，否则按「无引文不补造」降级
        if status == VERDICT_SIGNAL:
            if not quote_ok or not quote:
                col.add_check(engine_ref=engine_ref, status='insufficient_input', basis_ids=basis_ids,
                              reason=('引擎判为不符合，但引文缺失或未通过校验，须人工定位报告原句后再定稿。'
                                      + (f'引擎理由：{reason}' if reason else ''))[:600])
                continue
            evidence = col.quote_evidence(raw.get('locator') or block or '全文', quote)
            priority = SEVERITY_TO_PRIORITY.get(severity, 'P2')
            obs = reason or f'引擎依据 {code} {clause} 判为不符合。'.strip()
            if severity:
                obs += f'（引擎严重度：{severity}）'
            cid = col.add_check(engine_ref=engine_ref, status='evaluated', result='signal',
                                basis_ids=basis_ids, evidence=evidence,
                                reason=(reason or '引擎判为不符合')[:600])
            col.add_finding(
                cid, 'rule_deviation', discipline,
                point,
                obs,
                priority, 'medium', basis_ids, evidence,
                fix or '核对报告相应论证是否满足该条，补充计算或论证后重查。')
            continue

        # 缺失：报告没有交代判定所必需的内容。证据只能是「已检索范围」。
        missed = raw.get('misses') or []
        scope = '检索范围：报告全文；' + (f'未命中要素：{"、".join(map(str, missed[:8]))}' if missed else '引擎未给出定位片段')
        if quote and quote_ok:
            evidence = col.quote_evidence(raw.get('locator') or block or '全文', quote)
        else:
            evidence = col.scope_evidence(scope)
        obs = ('报告未交代该检查点判定所必需的内容。'
               + (f'引擎理由：{reason}' if reason else '') + f'（{scope}）')
        if severity:
            obs += f'（引擎严重度：{severity}）'
        cid = col.add_check(engine_ref=engine_ref, status='evaluated', result='signal',
                            basis_ids=basis_ids, evidence=evidence,
                            reason=(reason or '引擎判为缺失')[:600])
        col.add_finding(
            cid, 'missing_information', discipline, point, obs,
            SEVERITY_TO_PRIORITY.get(severity, 'P2'), 'medium', basis_ids, evidence,
            fix or '补齐该事项的事实前提与论证；或其不适用须写明理由。')


# ------------------------------------------------------------- 清单核对导入

def import_checklist_audit(payload, col, module_default):
    """checklist_audit.py 的 3 态覆盖度 -> 契约 6 态。"""
    for raw in payload.get('items') or []:
        if not isinstance(raw, dict):
            continue
        item_id = str(raw.get('id') or '').strip()
        point = str(raw.get('check_point') or '').strip() or item_id
        block = str(raw.get('block') or '').strip()
        status = str(raw.get('status') or '').strip()
        mandatory = bool(raw.get('mandatory'))
        hits = [str(x) for x in (raw.get('hits') or [])][:8]
        misses = [str(x) for x in (raw.get('misses') or [])][:8]
        criteria = str(raw.get('criteria') or '').strip()
        code = str(raw.get('basis_code') or '').strip()
        clause = str(raw.get('basis_clause') or '').strip()
        basis_text = str(raw.get('basis_text') or '').strip()
        engine_ref = f'checklist-audit:{item_id}'
        discipline = pick_discipline(block, point, criteria, default=module_default)
        basis_id = col.basis_for(code, clause, basis_text) if code else None
        basis_ids = [basis_id] if basis_id else []

        if status == '覆盖':
            col.add_check(engine_ref=engine_ref, status='evaluated', result='no_signal',
                          reason=f'清单核对：报告已覆盖该检查点（命中要素 {len(hits)} 项）。')
            continue

        scope = '；'.join([
            '检索范围：报告全文',
            f'命中要素 {len(hits)} 项' + (f'：{"、".join(hits)}' if hits else ''),
            f'未命中要素 {len(misses)} 项' + (f'：{"、".join(misses)}' if misses else ''),
        ])
        # 部分覆盖说明确实命中过要素，定位词不能写「未命中」
        evidence = col.scope_evidence(scope, '全文（部分命中）' if hits else '全文（未命中）')

        if status == '缺失':
            priority = 'P2'  # 引擎不产生 P1；mandatory 只写进 observation
            obs = ('清单核对：报告全篇未出现该检查点的判定要素，疑为整项缺失。'
                   f'（{scope}）判定标准：' + (criteria or '见清单'))
            if mandatory:
                obs += '（该检查点标注为强制性条文相关，复核时应按强条处置）'
            action = '确认该项是否适用；适用则补齐内容，不适用须写明理由。'
        elif status == '部分覆盖':
            priority = 'P3'
            obs = ('清单核对：报告涉及该检查点但要素不全。'
                   f'（{scope}）判定标准：' + (criteria or '见清单'))
            action = '补足未覆盖的要素与论证，避免只给结论。'
        else:
            col.add_check(engine_ref=engine_ref, status='error',
                          reason=f'清单核对返回无法识别的状态 {status!r}；须人工复核。')
            continue

        cid = col.add_check(engine_ref=engine_ref, status='evaluated', result='signal',
                            basis_ids=basis_ids, evidence=evidence, reason=obs[:600])
        col.add_finding(cid, 'missing_information', discipline, point, obs, priority,
                        'medium' if status == '缺失' else 'low', basis_ids, evidence, action)


# --------------------------------------------------------------- 旧格式导入

def import_engine_scan(payload, col, module_default):
    """旧 wsl_scan.py --json 的命中清单（保持原有映射，向后兼容）。"""
    scanned = payload.get('scan') if isinstance(payload.get('scan'), dict) else {}
    if not scanned and isinstance(payload.get('errors'), list):
        scanned = payload
    for raw in scanned.get('errors') or []:
        if not isinstance(raw, dict):
            continue
        content = str(raw.get('content') or '').strip()
        if not content:
            continue
        quote = str(raw.get('quote') or '').strip()
        category = str(raw.get('category') or '确定性检查')
        discipline = pick_discipline(category, content, raw.get('explanation'), default=module_default)
        explanation = str(raw.get('explanation') or '').strip() or category
        engine_ref = f'engine-scan:{category}'

        if not quote:
            col.add_check(engine_ref=engine_ref, status='insufficient_input',
                          reason=('引擎命中但未给出可定位引文，须人工定位后再判定；'
                                  f'引擎说明：{explanation[:200]}'))
            continue
        evidence = col.quote_evidence(raw.get('location') or '全文', quote)
        kind = 'missing_information' if raw.get('finding_type') == 'missing' else 'rule_deviation'
        cid = col.add_check(engine_ref=engine_ref, status='evaluated', result='signal',
                            evidence=evidence, reason=explanation[:600])
        col.add_finding(cid, kind, discipline, content[:60], content,
                        'P3' if raw.get('is_suggestion') else 'P2', 'medium', [], evidence,
                        str(raw.get('suggestion') or '请人工核实并补充依据。'))

    for raw in payload.get('spec_codes') or []:
        if not isinstance(raw, dict) or raw.get('valid') is not False:
            continue
        code = str(raw.get('code') or '').strip()
        name = str(raw.get('name') or '').strip()
        message = str(raw.get('message') or f'{code} 未通过规范号有效性核对').strip()
        evidence = col.quote_evidence('全文（引擎规范号检索）', f'{code}（{name}）'.strip())
        cid = col.add_check(engine_ref='engine-scan:spec_registry', status='evaluated',
                            result='signal', evidence=evidence, reason=message[:600])
        col.add_finding(cid, 'rule_deviation', 'general', f'规范号引用存疑：{code}', message,
                        'P2', 'medium', [], evidence,
                        '核对引用规范号的现行版本与替代关系，改用现行版本或说明适用范围。')


# ------------------------------------------------------------------ 组装记录

def build_review(payload, document, fmt=None, name=None, module=None, stage='preliminary',
                 grade=None, baseline_id='imported', review_date=None):
    document = Path(document)
    review_date = review_date or date.today().isoformat()
    if not fmt:
        fmt = detect_format(payload)[0]
        if fmt == 'unknown':
            raise ValueError('无法识别的引擎输出结构；请显式指定 --format')
    doc_sha = sha256_of(document) if document.is_file() else '0' * 64

    profile = payload.get('profile') or {}
    scanned = payload.get('scan') if isinstance(payload.get('scan'), dict) else {}
    engine_domain = (scanned.get('primary_domain') or profile.get('project_type')
                     or profile.get('domain') or '通用')
    module = module or DOMAIN_TO_MODULE.get(str(engine_domain), 'M6' if fmt == 'clause-verdict' else 'M4')

    sources = [{
        'id': 'S01',
        'path': document.name,
        'sha256': doc_sha,
        'revision': f'engine {fmt} import {review_date}',
        'discipline': 'general',
        'capability': 'text',
        'locator_convention': '章节号 / 表号 / 图号 / 页码；引擎原文检索结果',
    }]

    col = Collector('S01', doc_sha)
    default_discipline = 'flood_eval' if fmt in ('clause-verdict', 'checklist-audit') else 'general'
    if fmt == 'clause-verdict':
        import_clause_verdict(payload, col, default_discipline)
    elif fmt == 'checklist-audit':
        import_checklist_audit(payload, col, default_discipline)
    else:
        import_engine_scan(payload, col, default_discipline)

    if not col.checks:
        col.add_check(engine_ref=f'{fmt}:none', status='insufficient_input',
                      reason='引擎未返回任何可导入项；这不等于报告无问题，须按计划清单人工审查。')

    summary = payload.get('summary') if isinstance(payload.get('summary'), dict) else {}
    if summary:
        total = summary.get('total')
        scope_note = f'引擎 {fmt} 汇总：共 {total} 项；' if total else f'引擎 {fmt}：'
        for key, label in (('missing', '缺失'), ('partial', '部分覆盖'),
                           ('covered', '覆盖'), ('cite_rate', '依据覆盖率')):
            if summary.get(key) is not None:
                scope_note += f'{label} {summary[key]}；'
        if summary.get('by_status'):
            scope_note += '状态分布 ' + '、'.join(f'{k}{v}' for k, v in summary['by_status'].items()) + '；'
    else:
        scope_note = f'引擎 {fmt} 无汇总信息；'

    disciplines = sorted({f['discipline'] for f in col.findings} or {default_discipline})
    return {
        'schema_version': '1.0',
        'mode': 'project',
        'project': {
            'id': 'IMP-' + (document.stem or 'doc')[:20].replace(' ', '-'),
            'name': name or document.stem or '未命名项目',
            'region': '待补充',
            'project_type': str(engine_domain),
            'module': module,
            'modules_extra': [],
            'stage': stage,
            'grade': grade,
            'review_date': review_date,
            'baseline_date': review_date,
            'baseline_id': baseline_id,
            'scope_ref': (f'引擎 {fmt} 导入（{document.name}）；模块为粗映射，'
                          '须按 workflow/04-route.md 复核。' + scope_note)[:400],
            'planned_check_ids': [c['id'] for c in col.checks],
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
        'bases': col.bases,
        'rules': [],
        'checks': col.checks,
        'findings': col.findings,
        'conclusion': {'status': 'pending'},
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('scan', type=Path, help='引擎输出的 JSON（三种格式自动识别）')
    ap.add_argument('--document', type=Path, required=True, help='被审查的报告文件（用于哈希与定位）')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--name')
    ap.add_argument('--format', default='auto',
                    choices=['auto', 'engine-scan', 'checklist-audit', 'clause-verdict'])
    ap.add_argument('--module', choices=[f'M{i}' for i in range(1, 15)])
    ap.add_argument('--stage', default='preliminary')
    ap.add_argument('--grade', choices=['I', 'II', 'III', 'IV', 'V'])
    ap.add_argument('--baseline-id', default='imported')
    args = ap.parse_args()

    try:
        payload = json.loads(args.scan.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        print(f'Cannot read scan: {exc}')
        return 2

    if args.format == 'auto':
        fmt, why = detect_format(payload)
        if fmt == 'unknown':
            print(f'无法识别引擎输出：{why}')
            print('支持：clause_verdict.py --json（verdicts[]）、checklist_audit.py --json（items[]）、'
                  '旧 wsl_scan.py --json（scan.errors[]）')
            return 2
    else:
        fmt, why = args.format, '由 --format 指定'

    review = build_review(payload, args.document, fmt, args.name, args.module,
                          args.stage, args.grade, args.baseline_id)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding='utf-8')

    by_status = {}
    for c in review['checks']:
        key = f"{c['status']}/{c['result']}" if c['status'] == 'evaluated' else c['status']
        by_status[key] = by_status.get(key, 0) + 1
    print(f'格式：{fmt}（{why}）')
    print(f'导入 {len(review["checks"])} 个检查项 / {len(review["findings"])} 条候选疑点 / '
          f'{len(review["bases"])} 张待核依据卡 -> {args.out}')
    print('状态分布：' + '，'.join(f'{k} {v}' for k, v in sorted(by_status.items())))
    print('全部候选均未定稿（confidence<=medium, review.status=pending）。'
          '下一步：按 references/workflow/04-route.md 定计划，再用 validate_review.py 校验。')
    return 0


if __name__ == '__main__':
    sys.exit(main())

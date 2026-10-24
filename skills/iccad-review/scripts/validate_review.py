#!/usr/bin/env python3
"""Validate iccad review records: structure, evidence links, numeric comparisons, signoff readiness.

Python 3.10+ standard library only. This does not authenticate people or assess engineering safety.

Exit codes: 0 = requested checks passed; 2 = structural/reference/numeric error;
            3 = structurally valid but signoff-preparation blockers remain (--gate only).
"""
import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

SCHEMA_VERSION = '1.0'
MODES = {'project', 'synthetic'}
DISCIPLINES = {
    'general', 'hydrology', 'dam', 'gate_pump', 'geotech', 'hydraulic', 'structure',
    'flood_eval', 'soil_water', 'water_resource', 'environment', 'resettlement',
    'cost', 'coordination',
}
MODULES = {f'M{i}' for i in range(1, 15)}
STAGES = {
    'proposal', 'feasibility', 'preliminary', 'construction_doc',
    'special', 'safety_appraisal', 'design_change', 'evaluation',
}
GRADES = {'I', 'II', 'III', 'IV', 'V'}
BASE_KINDS = {'standard', 'regulation', 'approval', 'drawing', 'project'}
AUTHORITIES = {'official', 'project_approved', 'synthetic', 'unknown'}
BASE_LEVELS = {'gb', 'sl', 'sl_t', 'db', 'tb', 'internal'}
BASE_STATUS = {'effective', 'superseded', 'future', 'unknown', 'synthetic'}
APPLICABILITY = {'confirmed', 'unknown', 'not_applicable'}
RULE_STATUS = {'draft', 'verified', 'disabled'}
CRITERION_KINDS = {'numeric', 'qualitative', 'consistency', 'completeness'}
CHECK_STATES = {'evaluated', 'not_applicable', 'insufficient_input', 'unsupported', 'unverified_basis', 'error'}
CHECK_ORIGINS = {'plan', 'engine', 'manual'}
FINDING_KINDS = {'rule_deviation', 'document_conflict', 'calculation_inconsistency', 'missing_information'}
PRIORITIES = {'P1', 'P2', 'P3'}
CONFIDENCES = {'high', 'medium', 'low'}
REVIEW_STATUS = {'pending', 'adopted', 'not_applicable', 'undetermined'}
CLOSURE_STATUS = {'open', 'response_submitted', 'recheck_required', 'closed', 'not_applicable'}
CONCLUSIONS = {'pending', 'pass', 'pass_with_revision', 'fail'}
OPERATORS = {'ge', 'le', 'gt', 'lt', 'eq'}

# unit -> (dimension, factor to base unit). Only exact decimal factors; no rounding rules.
UNITS = {
    'mm': ('length', '0.001'), 'cm': ('length', '0.01'), 'm': ('length', '1'), 'km': ('length', '1000'),
    'mm2': ('area', '0.000001'), 'cm2': ('area', '0.0001'), 'm2': ('area', '1'),
    'ha': ('area', '10000'), 'km2': ('area', '1000000'),
    'L': ('volume', '0.001'), 'm3': ('volume', '1'), '万m3': ('volume', '10000'),
    'L/s': ('flow', '0.001'), 'm3/s': ('flow', '1'), 'm3/h': ('flow', '0.0002777777777777778'),
    '万m3/d': ('flow', '0.11574074074074074'),
    'Pa': ('pressure', '1'), 'kPa': ('pressure', '1000'), 'MPa': ('pressure', '1000000'),
    'mH2O': ('pressure', '9806.65'),
    'N': ('force', '1'), 'kN': ('force', '1000'),
    'W': ('power', '1'), 'kW': ('power', '1000'), 'MW': ('power', '1000000'), '万kW': ('power', '10000000'),
    '%': ('ratio', '0.01'), 'ratio': ('ratio', '1'),
    's': ('time', '1'), 'min': ('time', '60'), 'h': ('time', '3600'), 'd': ('time', '86400'),
    'kg': ('mass', '1'), 't': ('mass', '1000'),
}
ID_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}')
HEX_RE = re.compile(r'[0-9a-f]{64}')
DATE_RE = re.compile(r'\d{4}-\d{2}-\d{2}')


def _dec(value):
    if isinstance(value, bool) or value is None:
        raise InvalidOperation()
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        return Decimal(value.strip())
    raise InvalidOperation()


class Validator:
    def __init__(self, data, root=None, verify_files=False):
        self.data = data
        self.root = Path(root).resolve() if root is not None else None
        self.verify_files = verify_files
        self.errors, self.blockers, self.notes = [], [], []
        self.sources, self.bases, self.rules = {}, {}, {}
        self.checks, self.findings = {}, {}
        self.review_date = None
        self.baseline_id = None
        self.synthetic = False

    # ---------- primitives ----------
    def error(self, message):
        self.errors.append(message)

    def block(self, message):
        self.blockers.append(message)

    def note(self, message):
        self.notes.append(message)

    def obj(self, value, label):
        if not isinstance(value, dict):
            self.error(f'{label}: expected object')
            return {}
        return value

    def array(self, value, label, nonempty=False):
        if not isinstance(value, list):
            self.error(f'{label}: expected array')
            return []
        if nonempty and not value:
            self.error(f'{label}: must not be empty')
        return value

    def text(self, value, label):
        if not isinstance(value, str) or not value.strip():
            self.error(f'{label}: nonempty string required')
            return ''
        return value

    def fields(self, record, names, label):
        for name in names.split():
            self.text(record.get(name), f'{label}.{name}')

    def enum(self, value, allowed, label, optional=False):
        if value is None and optional:
            return None
        if not isinstance(value, str) or value not in allowed:
            self.error(f'{label}: expected one of {sorted(allowed)}')
            return None
        return value

    def ident(self, value, label):
        if not isinstance(value, str) or not ID_RE.fullmatch(value):
            self.error(f'{label}: id must match [A-Za-z0-9][A-Za-z0-9._-]*')
            return ''
        return value

    def iso_date(self, value, label, optional=False):
        if value is None and optional:
            return None
        if not isinstance(value, str) or not DATE_RE.fullmatch(value):
            self.error(f'{label}: expected ISO date YYYY-MM-DD')
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            self.error(f'{label}: invalid calendar date')
            return None

    def ident_list(self, value, label, nonempty=False):
        items = self.array(value, label, nonempty)
        out = []
        for i, item in enumerate(items):
            out.append(self.ident(item, f'{label}[{i}]'))
        if len(set(out)) != len(out):
            self.error(f'{label}: duplicate ids')
        return [x for x in out if x]

    # ---------- sections ----------
    def run(self):
        data = self.obj(self.data, 'root')
        if data.get('schema_version') != SCHEMA_VERSION:
            self.error(f'schema_version: expected {SCHEMA_VERSION!r}')
        mode = self.enum(data.get('mode'), MODES, 'mode')
        self.synthetic = mode == 'synthetic'
        self.read_project(self.obj(data.get('project'), 'project'))
        self.read_sources(self.array(data.get('sources'), 'sources', nonempty=True))
        self.read_bases(self.array(data.get('bases'), 'bases'))
        self.read_rules(self.array(data.get('rules'), 'rules'))
        self.read_checks(self.array(data.get('checks'), 'checks', nonempty=True))
        self.read_findings(self.array(data.get('findings'), 'findings'))
        self.read_conclusion(self.obj(data.get('conclusion', {}), 'conclusion'))
        self.cross_checks()
        ready = not self.errors and not self.blockers
        return {
            'schema_version': SCHEMA_VERSION,
            'mode': mode,
            'counts': {
                'sources': len(self.sources),
                'bases': len(self.bases),
                'rules': len(self.rules),
                'checks': len(self.checks),
                'findings': len(self.findings),
                'by_status': dict(Counter(c.get('status') for c in self.checks.values())),
                'by_priority': dict(Counter(f.get('priority') for f in self.findings.values())),
            },
            'errors': self.errors,
            'blockers': self.blockers,
            'notes': self.notes,
            'ready_for_human_signoff': ready,
        }

    def read_project(self, p):
        self.fields(p, 'id name region project_type stage baseline_id scope_ref', 'project')
        self.ident(p.get('id'), 'project.id')
        self.enum(p.get('module'), MODULES, 'project.module')
        self.enum(p.get('stage'), STAGES, 'project.stage')
        self.enum(p.get('grade'), GRADES, 'project.grade', optional=True)
        if p.get('modules_extra') is not None:
            for i, m in enumerate(self.array(p.get('modules_extra'), 'project.modules_extra')):
                self.enum(m, MODULES, f'project.modules_extra[{i}]')
        self.review_date = self.iso_date(p.get('review_date'), 'project.review_date')
        self.iso_date(p.get('baseline_date'), 'project.baseline_date')
        self.baseline_id = p.get('baseline_id')
        self.planned = self.ident_list(p.get('planned_check_ids'), 'project.planned_check_ids', nonempty=True)
        if p.get('requested_disciplines') is not None:
            for i, d in enumerate(self.array(p.get('requested_disciplines'), 'project.requested_disciplines', nonempty=True)):
                self.enum(d, DISCIPLINES, f'project.requested_disciplines[{i}]')
        proc = self.obj(p.get('processing'), 'project.processing')
        self.enum(proc.get('mode'), {'local', 'cloud'}, 'project.processing.mode')
        if not isinstance(proc.get('environment_verified'), bool):
            self.error('project.processing.environment_verified: boolean required')
        self.fields(proc, 'authorization_ref', 'project.processing')
        if proc.get('environment_verified') is False:
            self.block('project.processing: environment not verified; restricted material must not enter a model session')

    def read_sources(self, items):
        for i, raw in enumerate(items):
            s = self.obj(raw, f'sources[{i}]')
            sid = self.ident(s.get('id'), f'sources[{i}].id')
            label = f'sources.{sid}'
            if sid in self.sources:
                self.error(f'{label}: duplicate id')
            self.fields(s, 'path revision capability locator_convention', label)
            self.enum(s.get('discipline'), DISCIPLINES, label + '.discipline')
            sha = s.get('sha256')
            if not isinstance(sha, str) or not HEX_RE.fullmatch(sha):
                self.error(label + '.sha256: 64 lowercase hex characters required')
            self.sources[sid] = s
            if self.verify_files:
                self.verify_source(s, label)

    def verify_source(self, s, label):
        if self.root is None:
            self.error(label + ': --verify-files requires a root directory')
            return
        path = Path(s['path'])
        if not path.is_absolute():
            path = self.root / path
        try:
            resolved = path.resolve()
        except OSError as exc:
            self.error(f'{label}: cannot resolve path ({exc})')
            return
        if self.root not in resolved.parents and resolved != self.root:
            self.error(f'{label}: path escapes the allowed root')
            return
        if not resolved.is_file():
            self.error(f'{label}: file not found: {resolved}')
            return
        digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
        if digest != s['sha256']:
            self.error(f'{label}: sha256 mismatch (recorded {s["sha256"][:12]}…, actual {digest[:12]}…)')

    def read_bases(self, items):
        for i, raw in enumerate(items):
            b = self.obj(raw, f'bases[{i}]')
            bid = self.ident(b.get('id'), f'bases[{i}].id')
            label = f'bases.{bid}'
            if bid in self.bases:
                self.error(f'{label}: duplicate id')
            unknown = b.get('status') == 'unknown'
            self.fields(b, 'title summary', label)
            if not unknown:
                self.fields(b, 'identifier source_ref verified_by rights_basis', label)
                if b.get('kind') == 'standard':
                    self.text(b.get('clause'), label + '.clause')
            kind = self.enum(b.get('kind'), BASE_KINDS, label + '.kind')
            authority = self.enum(b.get('authority'), AUTHORITIES, label + '.authority')
            status = self.enum(b.get('status'), BASE_STATUS, label + '.status')
            self.enum(b.get('applicability'), APPLICABILITY, label + '.applicability')
            self.enum(b.get('level'), BASE_LEVELS, label + '.level', optional=True)
            mandatory = b.get('mandatory')
            if mandatory is not None and not isinstance(mandatory, bool):
                self.error(label + '.mandatory: boolean required')
            elif mandatory is True and kind != 'standard':
                self.error(label + '.mandatory: only standards can carry mandatory clauses')
            elif mandatory is True and not b.get('clause'):
                self.error(label + '.mandatory: mandatory clause needs a clause reference')
            verified_at = self.iso_date(b.get('verified_at'), label + '.verified_at', optional=unknown)
            start = self.iso_date(b.get('effective_from'), label + '.effective_from',
                                  optional=unknown or kind != 'standard')
            end = self.iso_date(b.get('effective_to'), label + '.effective_to', optional=True)
            if verified_at and self.review_date and verified_at > self.review_date:
                self.error(label + ': verification date is later than review_date')
            if start and end and end <= start:
                self.error(label + ': invalid effective interval')
            if authority == 'official' and not b.get('source_ref'):
                self.error(label + ': official authority needs a traceable source_ref')
            identifier = b.get('identifier')
            if not self.synthetic and (
                authority == 'synthetic' or status == 'synthetic'
                or (isinstance(identifier, str) and identifier.startswith('EX-'))
            ):
                self.error(label + ': synthetic basis must not be used in a real project')
            if status == 'unknown':
                self.note(label + ': basis is unverified; dependent rules stay draft and checks must be unverified_basis')
            self.bases[bid] = b

    def read_rules(self, items):
        for i, raw in enumerate(items):
            r = self.obj(raw, f'rules[{i}]')
            rid = self.ident(r.get('id'), f'rules[{i}].id')
            label = f'rules.{rid}'
            if rid in self.rules:
                self.error(f'{label}: duplicate id')
            self.fields(r, 'version', label)
            self.enum(r.get('discipline'), DISCIPLINES, label + '.discipline')
            status = self.enum(r.get('status'), RULE_STATUS, label + '.status')
            basis_ids = self.ident_list(r.get('basis_ids'), label + '.basis_ids', nonempty=True)
            for bid in basis_ids:
                if bid not in self.bases:
                    self.error(f'{label}: unknown basis id {bid}')
            if status == 'verified':
                self.fields(r, 'verified_by verified_at verification_ref', label)
                self.iso_date(r.get('verified_at'), label + '.verified_at')
                if not r.get('test_ref'):
                    self.error(label + ': verified rule needs a test_ref (positive/negative sample)')
            app = self.obj(r.get('applicability'), label + '.applicability')
            self.text(app.get('rationale'), label + '.applicability.rationale')
            criterion = self.obj(r.get('criterion'), label + '.criterion')
            kind = self.enum(criterion.get('kind'), CRITERION_KINDS, label + '.criterion.kind')
            self.fields(criterion, 'quantity object_scope explanation', label + '.criterion')
            locator_optional = status == 'draft'
            if not locator_optional:
                self.text(criterion.get('basis_locator'), label + '.criterion.basis_locator')
            if kind == 'numeric':
                self.enum(criterion.get('operator'), OPERATORS, label + '.criterion.operator', optional=locator_optional)
                unit = criterion.get('unit')
                if unit is None and not locator_optional:
                    self.error(label + '.criterion.unit: required for numeric rules')
                elif unit is not None and unit not in UNITS:
                    self.error(f'{label}.criterion.unit: unsupported unit {unit!r} (see UNITS table)')
                threshold = criterion.get('threshold')
                if threshold is None:
                    if not locator_optional:
                        self.error(label + '.criterion.threshold: required for numeric rules')
                else:
                    try:
                        _dec(threshold)
                    except (InvalidOperation, ValueError):
                        self.error(label + '.criterion.threshold: numeric value required')
                if criterion.get('tolerance') is not None:
                    try:
                        _dec(criterion['tolerance'])
                    except (InvalidOperation, ValueError):
                        self.error(label + '.criterion.tolerance: numeric value required')
            self.rules[rid] = r

    def read_checks(self, items):
        for i, raw in enumerate(items):
            c = self.obj(raw, f'checks[{i}]')
            cid = self.ident(c.get('id'), f'checks[{i}].id')
            label = f'checks.{cid}'
            if cid in self.checks:
                self.error(f'{label}: duplicate id')
            status = self.enum(c.get('status'), CHECK_STATES, label + '.status')
            origin = self.enum(c.get('origin', 'plan'), CHECK_ORIGINS, label + '.origin')
            rid = c.get('rule_id')
            if rid is not None:
                self.ident(rid, label + '.rule_id')
                if rid not in self.rules:
                    self.error(f'{label}: unknown rule_id {rid}')
            engine_ref = c.get('engine_ref')
            if origin == 'engine' and not engine_ref:
                self.error(label + '.engine_ref: required for engine-origin checks')
            if status == 'evaluated':
                if rid is None and origin != 'engine':
                    self.error(label + ': evaluated check needs a rule_id or origin=engine')
                if rid is not None and self.rules.get(rid, {}).get('status') != 'verified':
                    self.error(f'{label}: rule {rid} is not verified; draft rules cannot be evaluated')
            result = c.get('result')
            if status == 'evaluated':
                self.enum(result, {'signal', 'no_signal'}, label + '.result')
            elif result is not None:
                self.error(label + '.result: must be null unless status=evaluated')
            self.fields(c, 'reason', label)
            basis_ids = self.ident_list(c.get('basis_ids', []), label + '.basis_ids')
            source_ids = self.ident_list(c.get('source_ids', []), label + '.source_ids')
            for bid in basis_ids:
                if bid not in self.bases:
                    self.error(f'{label}: unknown basis id {bid}')
            for sid in source_ids:
                if sid not in self.sources:
                    self.error(f'{label}: unknown source id {sid}')
            evidence = self.read_evidence(c.get('evidence', []), label)
            if status == 'evaluated' and not evidence:
                if result == 'signal':
                    self.error(label + ': signal check needs at least one evidence item')
                else:
                    self.note(label + ': no_signal check has no evidence; record the search range instead')
            if status == 'evaluated' and origin != 'engine' and not basis_ids and not rid:
                self.error(label + ': evaluated check needs an applicable basis')
            if status == 'evaluated' and origin != 'engine':
                self.check_basis_ready(basis_ids, label)
            if c.get('comparison') is not None:
                if not evidence:
                    self.error(label + '.comparison: a numeric comparison needs at least one evidence item')
                self.read_comparison(self.obj(c.get('comparison'), label + '.comparison'), label, evidence, result, status)
            c['_source_ids'] = source_ids
            c['_evidence'] = evidence
            self.checks[cid] = c

    def read_evidence(self, items, label):
        out = []
        for i, raw in enumerate(self.array(items, label + '.evidence')):
            ev = self.obj(raw, f'{label}.evidence[{i}]')
            sid = self.ident(ev.get('source_id'), f'{label}.evidence[{i}].source_id')
            self.fields(ev, 'locator excerpt', f'{label}.evidence[{i}]')
            source = self.sources.get(sid)
            if source is None:
                self.error(f'{label}.evidence[{i}]: unknown source_id {sid}')
            else:
                sha = ev.get('source_sha256')
                if sha != source.get('sha256'):
                    self.error(f'{label}.evidence[{i}]: source_sha256 must match sources.{sid}.sha256')
            out.append(ev)
        return out

    def check_basis_ready(self, basis_ids, label):
        for bid in basis_ids:
            b = self.bases.get(bid, {})
            status = b.get('status')
            if status == 'unknown':
                self.error(f'{label}: basis {bid} is unverified and cannot support an evaluated check')
            elif status in {'superseded', 'future'}:
                if b.get('applicability') != 'confirmed' or not b.get('transition_ref'):
                    self.error(f'{label}: basis {bid} is {status}; need confirmed applicability and a transition_ref')
            elif b.get('applicability') != 'confirmed':
                self.error(f'{label}: basis {bid} applicability must be confirmed before evaluation')

    def read_comparison(self, cmp, label, evidence, result, status):
        cl = label + '.comparison'
        self.fields(cmp, 'quantity object_ref operator', cl)
        self.enum(cmp.get('operator'), OPERATORS, cl + '.operator')
        if not isinstance(cmp.get('conditions_verified'), bool):
            self.error(cl + '.conditions_verified: boolean required')
        idx = cmp.get('evidence_index')
        if not isinstance(idx, int) or isinstance(idx, bool) or not 0 <= idx < max(len(evidence), 1):
            self.error(cl + '.evidence_index: must point at an existing evidence item')
        try:
            observed = _dec(cmp.get('observed_value'))
            normalized = _dec(cmp.get('normalized_value'))
            threshold = _dec(cmp.get('threshold'))
        except (InvalidOperation, ValueError):
            self.error(cl + ': observed_value, normalized_value and threshold must be numeric (use null + insufficient_input when unknown)')
            return
        ou, nu, tu = cmp.get('observed_unit'), cmp.get('normalized_unit'), cmp.get('threshold_unit')
        for unit, name in ((ou, 'observed_unit'), (nu, 'normalized_unit'), (tu, 'threshold_unit')):
            if unit not in UNITS:
                self.error(f'{cl}.{name}: unsupported unit {unit!r}')
        if ou not in UNITS or nu not in UNITS or tu not in UNITS:
            return
        odim, ofactor = UNITS[ou]
        ndim, nfactor = UNITS[nu]
        tdim, tfactor = UNITS[tu]
        if odim != ndim or ndim != tdim:
            self.error(f'{cl}: dimensions differ ({odim} vs {ndim} vs {tdim}); convert explicitly')
            return
        expected = observed * Decimal(ofactor) / Decimal(nfactor)
        scale = max(abs(expected), abs(normalized), Decimal(1))
        if abs(expected - normalized) / scale > Decimal('1e-9'):
            self.error(f'{cl}: normalized_value {normalized} != {observed}{ou} expressed in {nu} ({expected})')
        if status != 'evaluated':
            return
        ok = {
            'ge': normalized >= threshold, 'le': normalized <= threshold,
            'gt': normalized > threshold, 'lt': normalized < threshold,
            'eq': abs(normalized - threshold) <= Decimal(str(cmp.get('tolerance') or 0)),
        }[cmp['operator']]
        if result == 'signal' and ok:
            self.note(f'{cl}: recorded comparison satisfies the threshold but the check reports signal; confirm the signal reason')
        if result == 'no_signal' and not ok:
            self.note(f'{cl}: recorded comparison violates the threshold but the check reports no_signal; confirm')

    def read_findings(self, items):
        for i, raw in enumerate(items):
            f = self.obj(raw, f'findings[{i}]')
            fid = self.ident(f.get('id'), f'findings[{i}].id')
            label = f'findings.{fid}'
            if fid in self.findings:
                self.error(f'{label}: duplicate id')
            cid = self.ident(f.get('check_id'), label + '.check_id')
            check = self.checks.get(cid)
            if check is None:
                self.error(f'{label}: unknown check_id {cid}')
            kind = self.enum(f.get('kind'), FINDING_KINDS, label + '.kind')
            self.enum(f.get('discipline'), DISCIPLINES, label + '.discipline')
            self.fields(f, 'title observation suggested_action', label)
            priority = self.enum(f.get('priority'), PRIORITIES, label + '.priority')
            self.enum(f.get('confidence'), CONFIDENCES, label + '.confidence')
            basis_ids = self.ident_list(f.get('basis_ids', []), label + '.basis_ids')
            for bid in basis_ids:
                if bid not in self.bases:
                    self.error(f'{label}: unknown basis id {bid}')
            evidence = self.read_evidence(f.get('evidence', []), label)
            if not evidence:
                self.error(label + ': findings need at least one evidence item')
            dims = {ev.get('source_id') for ev in evidence}
            if kind == 'rule_deviation' and not basis_ids and not (check or {}).get('engine_ref'):
                self.error(label + ': rule_deviation needs basis_ids (or an engine reference on the check)')
            if kind == 'document_conflict' and len(dims) < 2:
                self.error(label + ': document_conflict needs evidence from at least two different sources')
            if kind == 'calculation_inconsistency' and len(evidence) < 2:
                self.error(label + ': calculation_inconsistency needs both calculation and report locations')
            if kind == 'missing_information' and not f.get('observation'):
                self.error(label + ': missing_information must state the searched scope')
            if check is not None and check.get('status') == 'evaluated' and check.get('result') != 'signal':
                self.error(f'{label}: linked check {cid} did not report a signal')
            self.read_review(self.obj(f.get('review'), label + '.review'), label, priority)
            self.read_closure(self.obj(f.get('closure', {}), label + '.closure'), label, evidence)
            self.findings[fid] = f

    def read_review(self, rev, label, priority):
        status = self.enum(rev.get('status'), REVIEW_STATUS, label + '.review.status')
        if status in {'pending'}:
            self.block(f'{label}: review pending; a human disposition is required before signoff')
            return
        self.fields(rev, 'actor at record_ref note', label + '.review')
        self.iso_date(rev.get('at'), label + '.review.at')
        if status == 'not_applicable' and rev.get('baseline_id') != self.baseline_id:
            self.error(f'{label}: review.not_applicable must reference the current baseline_id')

    def read_closure(self, clo, label, evidence):
        if not clo:
            self.block(f'{label}: no closure record; open findings cannot be signed off')
            return
        status = self.enum(clo.get('status'), CLOSURE_STATUS, label + '.closure.status')
        if status in {'open', 'response_submitted', 'recheck_required'}:
            if status != 'open':
                self.text(clo.get('response'), label + '.closure.response')
            self.block(f'{label}: closure is {status}; only a closed item with recheck evidence clears signoff')
            return
        if status == 'not_applicable':
            recheck = self.obj(clo.get('recheck'), label + '.closure.recheck')
            self.fields(recheck, 'actor at record_ref note', label + '.closure.recheck')
            self.iso_date(recheck.get('at'), label + '.closure.recheck.at')
            return
        if status == 'closed':
            self.text(clo.get('response'), label + '.closure.response')
            revision = self.ident_list(clo.get('revision_source_ids', []), label + '.closure.revision_source_ids', nonempty=True)
            for sid in revision:
                if sid not in self.sources:
                    self.error(f'{label}: unknown revision source {sid}')
            recheck = self.obj(clo.get('recheck'), label + '.closure.recheck')
            self.fields(recheck, 'actor at record_ref baseline_id', label + '.closure.recheck')
            self.iso_date(recheck.get('at'), label + '.closure.recheck.at')
            if recheck.get('baseline_id') != self.baseline_id:
                self.error(f'{label}: closure recheck must be performed against the current baseline_id')
            if not recheck.get('evidence'):
                self.error(f'{label}: closed item needs recheck evidence')
            if not any(ev.get('source_id') in revision for ev in evidence):
                self.note(f'{label}: closure evidence does not include any revised source')

    def read_conclusion(self, c):
        if not c:
            self.block('conclusion: missing; record the human conclusion before signoff')
            return
        status = self.enum(c.get('status'), CONCLUSIONS, 'conclusion.status')
        if status == 'pending':
            self.block('conclusion: pending; AI must not fill the conclusion')
            return
        self.fields(c, 'actor at record_ref note', 'conclusion')
        if self.synthetic:
            return

    def cross_checks(self):
        planned = getattr(self, 'planned', [])
        # plan coverage
        missing = [cid for cid in planned if cid not in self.checks]
        for cid in missing:
            self.block(f'project.planned_check_ids: {cid} has no executed check (planned items must not be dropped)')
        extra = [cid for cid in self.checks if cid not in planned]
        for cid in extra:
            self.block(f'checks.{cid}: not in planned_check_ids; add it to the plan before executing')
        for cid in planned:
            check = self.checks.get(cid)
            if not check:
                continue
            status = check.get('status')
            if status == 'evaluated' or status == 'not_applicable':
                continue
            if status in {'insufficient_input', 'unsupported', 'unverified_basis', 'error'}:
                self.block(f'checks.{cid}: {status} — resolve or record an approved scope reduction before signoff')
        # findings must hang off signals, and signals must produce findings
        signals = {cid for cid, c in self.checks.items() if c.get('result') == 'signal'}
        with_finding = {f.get('check_id') for f in self.findings.values()}
        for cid in signals - with_finding:
            self.error(f'checks.{cid}: result=signal but no finding references it')
        for cid in with_finding - signals:
            self.error(f'findings: check {cid} has a finding but no signal result')
        # priority P1 must be closed
        for fid, f in self.findings.items():
            if f.get('priority') == 'P1':
                status = (f.get('closure') or {}).get('status')
                if status not in {'closed', 'not_applicable'}:
                    self.block(f'findings.{fid}: P1 finding is not closed ({status or "no closure"})')
        # no signal under a synthetic basis in a real project
        if not self.synthetic:
            for bid, b in self.bases.items():
                if b.get('status') == 'synthetic':
                    self.error(f'bases.{bid}: synthetic basis in a real project')


def validate(data, root=None, verify_files=False):
    return Validator(data, root, verify_files).run()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('review', type=Path)
    ap.add_argument('--root', type=Path, help='allowed material root for --verify-files (default: review.json directory)')
    ap.add_argument('--verify-files', action='store_true', help='check every declared source exists inside root and its sha256 matches')
    ap.add_argument('--gate', action='store_true', help='verify files and require no signoff-preparation blockers; never a legal signoff')
    ap.add_argument('--quiet', action='store_true', help='only print the summary line')
    args = ap.parse_args()
    try:
        data = json.loads(args.review.read_text(encoding='utf-8'))
    except OSError as exc:
        print(f'Cannot read review file: {exc}')
        return 2
    except ValueError as exc:
        print(f'Invalid JSON: {exc}')
        return 2
    result = validate(data, args.root or args.review.parent, args.verify_files or args.gate)
    if args.quiet:
        print(json.dumps({k: result[k] for k in ('counts', 'ready_for_human_signoff')}, ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    if result['errors']:
        return 2
    if args.gate and result['blockers']:
        return 3
    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""一条命令跑引擎预扫并直接生成 review.json。

Python 3.10+ 标准库。封装三件事，省掉手抄路径与两次转换：

1. 找到引擎根目录与它的解释器（引擎有 .venv 时优先用 .venv，避免依赖冲突）；
2. 调引擎的无 LLM 命令行（`tools/checklist_audit.py`，零 Token、不联网）产出 JSON；
3. 交给 `import_scan.py` 转成 `review.json`（可选同时保留引擎原始输出）。

`--mode verdict` 走 `tools/clause_verdict.py`（逐项条文判词，需要 API Key，会产生 Token 消耗）。
默认 `--mode audit` 只做清单覆盖度核对，不花钱。

用法::

    # 清单一键核对（零 Token）
    python engine_run.py 报告.docx --engine-root "D:/SLReview_Py" --out review/imported.json

    # 逐项条文判词（需 key，可先 --dry-run 看检索结果）
    python engine_run.py 报告.docx --engine-root ... --mode verdict --key sk-xxx

    # 只看会执行什么命令，不真跑
    python engine_run.py 报告.docx --engine-root ... --dry-run
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import import_scan  # noqa: E402  同目录模块

ENGINE_ENV = 'ICCAD_ENGINE_ROOT'
# 引擎里两个可用命令行：(入口脚本, 产出格式名, 额外必需参数)
COMMANDS = {
    'audit': ('tools/checklist_audit.py', 'checklist-audit'),
    'verdict': ('tools/clause_verdict.py', 'clause-verdict'),
}


def find_engine(explicit):
    """按 参数 > 环境变量 > 常见位置 的顺序定位引擎根目录。"""
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get(ENGINE_ENV)
    if env:
        return Path(env).expanduser().resolve()
    candidates = [
        HERE.parent.parent.parent / 'SLReview_Py',
        Path.home() / 'SLReview_Py',
        Path.home() / 'Documents' / 'SLReview_Py',
    ]
    for path in candidates:
        if (path / 'tools' / 'checklist_audit.py').is_file():
            return path
    return None


def find_python(engine_root, explicit):
    """引擎自带 venv 优先，其次用当前解释器。"""
    if explicit:
        return Path(explicit).expanduser()
    if engine_root:
        for rel in ('Scripts/python.exe', 'bin/python', 'bin/python3'):
            candidate = engine_root / '.venv' / rel
            if candidate.is_file():
                return candidate
    return Path(sys.executable)


def build_command(py, engine_root, mode, report, json_out, md_out, extra):
    script, _ = COMMANDS[mode]
    cmd = [str(py), str(engine_root / script), str(report), '--json', str(json_out)]
    if md_out:
        cmd += ['--out', str(md_out)]
    cmd += extra
    return cmd


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('report', type=Path, help='待审报告 .docx/.md/.txt')
    ap.add_argument('--out', type=Path, help='review.json 输出路径（默认与报告同目录的 review-imported.json）')
    ap.add_argument('--engine-root', type=Path, help=f'引擎根目录；也可用环境变量 {ENGINE_ENV}')
    ap.add_argument('--python', help='引擎解释器路径（默认用引擎 .venv，找不到则用当前解释器）')
    ap.add_argument('--mode', default='audit', choices=sorted(COMMANDS),
                    help='audit=清单覆盖度核对（零 Token）；verdict=逐项条文判词（需 key）')
    ap.add_argument('--key', help='verdict 模式下的 API Key（也可用 DEEPSEEK_API_KEY）')
    ap.add_argument('--blocks', nargs='*', help='verdict 模式下只判某几块，如 块5 块6')
    ap.add_argument('--name')
    ap.add_argument('--module', choices=[f'M{i}' for i in range(1, 15)])
    ap.add_argument('--stage', default='preliminary')
    ap.add_argument('--grade', choices=['I', 'II', 'III', 'IV', 'V'])
    ap.add_argument('--keep-raw', action='store_true', help='保留引擎原始 JSON 与 markdown')
    ap.add_argument('--dry-run', action='store_true', help='只打印将执行的命令')
    args = ap.parse_args()

    report = args.report.expanduser().resolve()
    if not args.dry_run and not report.is_file():
        print(f'找不到报告：{report}')
        return 2

    engine_root = find_engine(args.engine_root)
    if engine_root is None:
        print('没找到引擎根目录。请用 --engine-root 指定 SLReview_Py 仓库路径，')
        print(f'或设置环境变量 {ENGINE_ENV}。')
        return 2
    entry = engine_root / COMMANDS[args.mode][0]
    if not entry.is_file():
        print(f'引擎缺少入口脚本：{entry}')
        return 2

    py = find_python(engine_root, args.python)
    out = (args.out or report.with_name('review-imported.json')).expanduser().resolve()

    # 中间产物放在输出目录下（不要放系统临时目录：部分环境/策略会拒写 %TEMP%）
    out.parent.mkdir(parents=True, exist_ok=True)
    workdir = out.parent / (f'{out.stem}.engine' if args.keep_raw else f'.{out.stem}.engine-tmp')
    if workdir.exists() and not args.keep_raw:
        shutil.rmtree(workdir, ignore_errors=True)
    workdir.mkdir(parents=True, exist_ok=True)
    json_out = workdir / f'{out.stem}.engine.json'
    md_out = workdir / f'{out.stem}.engine.md'

    extra = []
    if args.mode == 'verdict':
        key = args.key or os.environ.get('DEEPSEEK_API_KEY')
        if key:
            extra += ['--key', key]
        elif not args.dry_run:
            print('verdict 模式需要 API Key：加 --key 或设置 DEEPSEEK_API_KEY；')
            print('只想先看检索结果可以加 --dry-run 参数到引擎（本脚本用 --blocks 控制范围）。')
            return 2
        if args.blocks:
            extra += ['--blocks', *args.blocks]

    cmd = build_command(py, engine_root, args.mode, report, json_out, md_out, extra)
    printable = ' '.join(f'"{c}"' if ' ' in c else c for c in cmd)
    if args.key:
        printable = printable.replace(args.key, '***')

    if args.dry_run:
        print('将执行：')
        print(f'  cwd={engine_root}')
        print(f'  {printable}')
        print(f'  然后导入 -> {out}')
        return 0

    print(f'引擎：{engine_root}')
    print(f'解释器：{py}')
    print(f'模式：{args.mode}')
    try:
        proc = subprocess.run(cmd, cwd=str(engine_root), capture_output=True, text=True,
                              encoding='utf-8', errors='ignore', timeout=1800)
    except subprocess.TimeoutExpired:
        print('引擎执行超时（1800s）。可先用 --blocks 缩小范围。')
        return 2
    except OSError as exc:
        print(f'无法启动引擎解释器：{exc}')
        return 2

    if proc.stderr.strip():
        tail = [ln for ln in proc.stderr.strip().splitlines() if ln.strip()][-6:]
        for line in tail:
            print(f'  [engine] {line}')
    if proc.returncode != 0 or not json_out.is_file():
        print(f'引擎执行失败（退出码 {proc.returncode}）。')
        if not args.keep_raw:
            shutil.rmtree(workdir, ignore_errors=True)
        return 2

    try:
        payload = json.loads(json_out.read_text(encoding='utf-8'))
    except ValueError as exc:
        print(f'引擎输出不是合法 JSON：{exc}')
        return 2

    fmt, why = import_scan.detect_format(payload)
    review = import_scan.build_review(payload, report, fmt, args.name, args.module,
                                     args.stage, args.grade, 'engine-run')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f'格式：{fmt}（{why}）')
    print(f'导入 {len(review["checks"])} 个检查项 / {len(review["findings"])} 条候选疑点 / '
          f'{len(review["bases"])} 张待核依据卡 -> {out}')
    if args.keep_raw:
        print(f'引擎原始输出保留在：{json_out} / {md_out}')
    else:
        shutil.rmtree(workdir, ignore_errors=True)
    print('下一步：按 references/workflow/04-route.md 复核模块与计划项，再用 validate_review.py 校验。')
    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""报告审查技能交付流水线 —— 一次跑完"交付三关 + 打包 + 同步 + 校验"。

【为什么需要它】
    家族交付约定是**固定五步**，手工易漏（尤其两个已踩过的坑：
    ① package_skill 的输出落点是 cwd → cwd 是技能目录时 zip 会自我包含；
    ② 同步后若又改了文件 → 分发源与安装目录 md5 不一致）。
    本脚本把五步串成一条命令，并附**体检项**（正文<5000字符 / 无 __pycache__ / 无嵌套 zip）。

【用法】
    # 只体检（编译 + 字数 + 残留 + quick_validate），不打不改
    python deliver.py --name pump-station-report-review --check

    # 完整交付：三关 + 打包 + 同步 + md5
    python deliver.py --name pump-station-report-review --deliver

【路径约定】
    SRC_ROOT   = 技能源根（含 <name>/ 的目录），默认 C:\\Users\\Administrator\\Desktop\\自建skill
    INSTALL    = 安装目录，默认 C:\\Users\\Administrator\\.workbuddy\\skills
    SKILLCREAT = skill-creator 的 scripts 目录（quick_validate.py / package_skill.py）

【退出码】0 全绿；1 有体检项未通过 / 有校验不一致。
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import zipfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SRC_ROOT = r"C:\Users\Administrator\Desktop\自建skill"
INSTALL = r"C:\Users\Administrator\.workbuddy\skills"
SKILLCREAT = (r"C:\Program Files\WorkBuddy\resources\app.asar.unpacked\resources"
              r"\plugins\workbuddy-builtin\skills\skill-creator\scripts")
BODY_LIMIT = 5000


def sh(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def clean_pycache(root):
    n = 0
    for dp, dn, fn in os.walk(root):
        if os.path.basename(dp) == "__pycache__":
            shutil.rmtree(dp); n += 1
    return n


def body_chars(skill_md):
    s = open(skill_md, encoding="utf-8").read()
    m = re.match(r"^---\n.*?\n---\n", s, re.S)
    return len(s[m.end():] if m else s)


def file_hashes(base):
    o = {}
    for dp, dn, fn in os.walk(base):
        dn[:] = [d for d in dn if d != "__pycache__"]
        for f in fn:
            fp = os.path.join(dp, f)
            o[os.path.relpath(fp, base).replace("\\", "/")] = hashlib.md5(
                open(fp, "rb").read()).hexdigest()
    return o


def check(name, root, py_exe):
    """体检：编译 / 正文字数 / 残留 / quick_validate。返回 (ok, 报告行 list)。"""
    lines, ok = [], True
    # 1) 语法检查：**进程内 compile**（不留 __pycache__，否则下一项自检必然失败）
    bad_files, err = [], ""
    for f in sorted(os.listdir(os.path.join(root, "scripts"))):
        if not f.endswith(".py"):
            continue
        fp = os.path.join(root, "scripts", f)
        try:
            compile(open(fp, encoding="utf-8").read(), fp, "exec")
        except SyntaxError as e:
            bad_files.append("%s:%s %s" % (f, e.lineno, e.msg))
            err = "；".join(bad_files)
    lines.append(("py_compile", not bad_files, err or "OK"))
    ok &= not bad_files
    # 2) SKILL.md 正文字数
    b = body_chars(os.path.join(root, "SKILL.md"))
    lines.append(("SKILL.md body < %d" % BODY_LIMIT, b < BODY_LIMIT, "%d 字符" % b))
    ok &= b < BODY_LIMIT
    # 3) 残留 __pycache__ / TODO 标记
    pyc = [dp for dp, dn, fn in os.walk(root) if os.path.basename(dp) == "__pycache__"]
    todo_pat = re.compile("<<TO" + "DO:|<!" + "-- TO" + "DO|# TO" + "DO")   # 拼接构造，避免自匹配
    todo = 0
    skip = {"skeleton.py", "deliver.py"}          # 这两个是"发/数标记"的工具本身，不计
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in ("__pycache__", "templates")]
        for f in fn:
            if f in skip:
                continue
            try:
                s = open(os.path.join(dp, f), encoding="utf-8").read()
            except Exception:
                continue
            todo += len(todo_pat.findall(s))
    lines.append(("无 __pycache__", not pyc, str(pyc) if pyc else "clean"))
    lines.append(("骨架 TODO 已清零", todo == 0, "%d 处未填" % todo))
    ok &= not pyc
    # 4) quick_validate
    qv = os.path.join(SKILLCREAT, "quick_validate.py")
    if os.path.isfile(qv):
        rc, out = sh([py_exe, qv, "."], cwd=root)
        good = "valid" in out.lower()
        lines.append(("quick_validate", good, out.strip().splitlines()[-1] if out.strip() else ""))
        ok &= good
    return ok, lines, todo


def deliver(name, root, py_exe):
    """三关 + 打包 + 同步 + md5。返回 (ok, 消息)。"""
    msgs, ok = [], True
    clean_pycache(root)
    # 打包：cwd 固定为分发根，避免 zip 自我包含
    ps = os.path.join(SKILLCREAT, "package_skill.py")
    rc, out = sh([py_exe, ps, name], cwd=SRC_ROOT)
    zip_path = os.path.join(SRC_ROOT, name + ".zip")
    stray = os.path.join(root, name + ".zip")
    if os.path.exists(stray):
        os.remove(stray); msgs.append("清理了误落入技能目录的 zip")
    msgs.append("package rc=%d -> %s (%d bytes)" % (rc, os.path.basename(zip_path),
                os.path.getsize(zip_path) if os.path.exists(zip_path) else -1))
    ok &= rc == 0 and os.path.exists(zip_path)
    # 同步
    dst = os.path.join(INSTALL, name)
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    os.makedirs(INSTALL, exist_ok=True)
    shutil.copytree(root, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    # md5 校验
    a, bb = file_hashes(root), file_hashes(dst)
    diff = [k for k in set(a) | set(bb) if a.get(k) != bb.get(k)]
    msgs.append("同步 %d 文件，%s" % (len(bb), "MD5 一致" if not diff else "MD5 不一致：%s" % diff))
    ok &= not diff
    # 嵌套 zip 检查
    if os.path.exists(zip_path):
        with zipfile.ZipFile(zip_path) as zf:
            nested = [n for n in zf.namelist() if n.lower().endswith(".zip")]
        msgs.append("嵌套 zip：%s" % (nested or "无"))
        ok &= not nested
    return ok, msgs


def main():
    ap = argparse.ArgumentParser(description="技能交付流水线")
    ap.add_argument("--name", required=True, help="技能目录名")
    ap.add_argument("--root", default=None, help="技能源根（默认 SRC_ROOT）")
    ap.add_argument("--src-root", default=SRC_ROOT)
    ap.add_argument("--check", action="store_true", help="只体检")
    ap.add_argument("--deliver", action="store_true", help="完整交付（含打包同步）")
    ap.add_argument("--py", default=sys.executable)
    args = ap.parse_args()

    root = args.root or os.path.join(args.src_root, args.name)
    if not os.path.isdir(root):
        raise SystemExit("技能目录不存在：%s" % root)

    print("=" * 64); print("体检：%s" % args.name)
    ok, lines, _ = check(args.name, root, args.py)
    for k, good, detail in lines:
        print("  [%s] %-26s %s" % ("OK " if good else "!! ", k, detail))

    if args.deliver:
        clean_pycache(root)
        ok, msgs = deliver(args.name, root, args.py)
        print("-" * 64); print("交付：")
        for m in msgs: print("  -", m)

    print("=" * 64)
    print("结论：%s" % ("全绿 ✓" if ok else "有未通过项 ✗"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

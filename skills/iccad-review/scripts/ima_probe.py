#!/usr/bin/env python3
"""Probe the IMA knowledge-base API used by the review workflow.

Python 3.10+ standard library only. Credentials come from the environment
(IMA_OPENAPI_CLIENTID / IMA_OPENAPI_APIKEY) or from ~/.config/ima/client_id
and ~/.config/ima/api_key. Nothing is written to disk and nothing is logged.

Usage:
    python ima_probe.py                     # diagnose credentials and list knowledge bases
    python ima_probe.py --search 压实度      # search every knowledge base
    python ima_probe.py --search 压实度 --kb 规范库
    python ima_probe.py --json              # machine-readable output

Exit codes: 0 = ok; 2 = credential, network or API failure.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = 'https://ima.qq.com'
API_KB_LIST = 'openapi/wiki/v1/search_knowledge_base'
API_KB_SEARCH = 'openapi/wiki/v1/search_knowledge'
CRED_DIR = Path.home() / '.config' / 'ima'
HINT = ('获取方式：打开 https://ima.qq.com/agent-interface 生成 Client ID 与 API Key，'
        '然后写入 ~/.config/ima/client_id 与 ~/.config/ima/api_key，'
        '或设置环境变量 IMA_OPENAPI_CLIENTID / IMA_OPENAPI_APIKEY。')


def load_credentials():
    cid = os.environ.get('IMA_OPENAPI_CLIENTID') or os.environ.get('IMA_CLIENT_ID') or ''
    key = os.environ.get('IMA_OPENAPI_APIKEY') or os.environ.get('IMA_API_KEY') or ''
    source = 'env' if cid or key else 'none'
    if not cid and (CRED_DIR / 'client_id').is_file():
        cid = (CRED_DIR / 'client_id').read_text(encoding='utf-8', errors='ignore').strip()
        source = 'file'
    if not key and (CRED_DIR / 'api_key').is_file():
        key = (CRED_DIR / 'api_key').read_text(encoding='utf-8', errors='ignore').strip()
        source = 'file' if source == 'none' else source + '+file'
    return cid.strip(), key.strip(), source


def call(path, body, cid, key, timeout=30):
    """POST JSON to the IMA OpenAPI, bypassing any system proxy."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(
        f'{BASE}/{path}',
        data=json.dumps(body, ensure_ascii=False).encode('utf-8'),
        headers={
            'ima-openapi-clientid': cid,
            'ima-openapi-apikey': key,
            'ima-openapi-ctx': 'skill_version=iccad-review-skill',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode('utf-8', 'replace'))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode('utf-8', 'replace')
        try:
            payload = json.loads(raw)
        except ValueError:
            return {'ok': False, 'reason': f'http_{exc.code}', 'msg': raw[:300]}
    except urllib.error.URLError as exc:
        return {'ok': False, 'reason': 'network_error',
                'msg': f'{exc.reason}（检查网络/代理；本脚本已绕过系统代理）'}
    except (ValueError, OSError) as exc:
        return {'ok': False, 'reason': 'bad_response', 'msg': f'{type(exc).__name__}: {exc}'}
    if payload.get('code') != 0:
        result = {'ok': False, 'reason': 'api_error', 'code': payload.get('code'),
                  'msg': payload.get('msg', ''), 'request_id': payload.get('request_id', '')}
        if payload.get('code') == 200002:
            result['reason'] = 'credential_invalid'
            result['msg'] = ('凭据被服务端拒绝（skill auth failed）：API Key 已失效/轮换，或未开通 OpenAPI。'
                             '请到 https://ima.qq.com/agent-interface 重新生成并覆盖本地凭据。')
        return result
    return {'ok': True, 'data': payload.get('data') or {}}


def list_kbs(cid, key):
    result = call(API_KB_LIST, {'query': '', 'cursor': '', 'limit': 20}, cid, key)
    if not result['ok']:
        return result
    items = result['data'].get('info_list') or []
    return {'ok': True, 'count': len(items),
            'knowledge_bases': [{'id': i.get('id'), 'name': i.get('name')} for i in items]}


def search(query, kb, cid, key):
    if kb:
        listing = list_kbs(cid, key)
        if not listing['ok']:
            return listing
        target = next((k for k in listing['knowledge_bases']
                       if kb in (k['name'] or '') or kb == k['id']), None)
        if target is None:
            names = '、'.join(k['name'] or '(未命名)' for k in listing['knowledge_bases']) or '无'
            return {'ok': False, 'reason': 'kb_not_found',
                    'msg': f'未找到知识库「{kb}」。当前可见：{names}'}
        targets = [target]
    else:
        listing = list_kbs(cid, key)
        if not listing['ok']:
            return listing
        targets = listing['knowledge_bases']
        if not targets:
            return {'ok': False, 'reason': 'no_knowledge_base',
                    'msg': '知识库列表为空，请先在 ima 客户端创建知识库并上传文件。'}
    hits, errors = [], []
    for target in targets:
        result = call(API_KB_SEARCH, {'query': query, 'cursor': '',
                                      'knowledge_base_id': target['id']}, cid, key)
        if not result['ok']:
            errors.append({'kb': target['name'], 'reason': result.get('reason'), 'msg': result.get('msg')})
            continue
        for item in result['data'].get('info_list') or []:
            hits.append({
                'kb': target['name'],
                'media_id': item.get('media_id'),
                'title': item.get('title'),
                'highlight': (item.get('highlight_content') or '')[:400],
            })
    return {'ok': True, 'query': query, 'hit_count': len(hits), 'hits': hits, 'errors': errors or None}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--search', default='', help='keyword to search across knowledge bases')
    ap.add_argument('--kb', default='', help='restrict to one knowledge base (name fragment or id)')
    ap.add_argument('--json', action='store_true', help='print JSON only')
    args = ap.parse_args()

    cid, key, source = load_credentials()
    if not cid or not key:
        payload = {'ok': False, 'reason': 'no_credentials',
                   'msg': '未找到 ima 凭证。' + HINT,
                   'checked': [str(CRED_DIR / 'client_id'), str(CRED_DIR / 'api_key'),
                               'env IMA_OPENAPI_CLIENTID / IMA_OPENAPI_APIKEY']}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2

    result = search(args.search, args.kb, cid, key) if args.search else list_kbs(cid, key)
    result['credential_source'] = source
    result['client_id_tail'] = cid[-4:] if len(cid) > 4 else '****'

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif not result['ok']:
        print(f"失败：{result.get('reason')} — {result.get('msg')}")
        if result.get('reason') in {'credential_invalid', 'no_credentials'}:
            print(HINT)
    elif args.search:
        print(f"检索「{result['query']}」命中 {result['hit_count']} 条")
        for hit in result['hits'][:10]:
            print(f"  [{hit['kb']}] {hit['title']}")
            if hit['highlight']:
                print(f"      {hit['highlight'][:160]}")
        if result.get('errors'):
            print(f"  部分知识库检索失败：{result['errors']}")
        if result['hit_count'] == 0:
            print('  未命中。检索词可换成条文关键词，或确认该文件已入库并完成解析。')
    else:
        print(f"连通正常，可见知识库 {result['count']} 个（凭据来源：{source}）")
        for kb in result['knowledge_bases']:
            print(f"  {kb['name']}  ({kb['id']})")
        if result['count'] == 0:
            print('  知识库为空：请先在 ima 客户端上传规范文件并等待解析完成。')
    return 0 if result['ok'] else 2


if __name__ == '__main__':
    sys.exit(main())

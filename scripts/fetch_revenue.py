#!/usr/bin/env python3
"""
月營收抓取腳本
每月 10 日自動跑（公司通常在 10 日前公布上月營收）
輸出：data/revenue.json

TWSE openapi：https://openapi.twse.com.tw/v1/opendata/t187ap06_L
TPEX openapi：https://www.tpex.org.tw/openapi/v1/tpex_monthly_report_by_company
"""

import json, os, time, urllib.request, ssl
from datetime import datetime, date

OUTPUT_PATH = "data/revenue.json"
MONTHS_TO_KEEP = 14   # 保留最近 14 個月

def make_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
    'Referer': 'https://www.twse.com.tw',
}

def fetch_url(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30, context=make_ctx()) as r:
        return json.loads(r.read().decode('utf-8'))

def fetch_twse_revenue():
    """抓上市公司月營收（近期）"""
    # 嘗試最近2個月
    today = date.today()
    results = {}

    for delta in [0, 1, 2]:
        if today.month - delta <= 0:
            y = today.year - 1
            m = today.month - delta + 12
        else:
            y = today.year
            m = today.month - delta

        # 民國年
        roc_y = y - 1911
        url = f"https://openapi.twse.com.tw/v1/opendata/t187ap06_L?yearmonth={roc_y}{m:02d}"
        try:
            data = fetch_url(url)
            print(f"  上市 {roc_y}/{m:02d}: {len(data)} 筆")
            ym = f"{y}-{m:02d}"
            for row in data:
                sym = row.get('公司代號', '').strip()
                rev = row.get('當月營收', '0').replace(',', '').strip()
                yoy = row.get('去年同月增減(%)', '').replace(',', '').strip()
                mom = row.get('上月比較增減(%)', '').replace(',', '').strip()
                if sym and rev:
                    sym_tw = sym + '.TW'
                    if sym_tw not in results:
                        results[sym_tw] = {}
                    try:
                        results[sym_tw][ym] = {
                            'rev': int(rev),
                            'yoy': float(yoy) if yoy and yoy not in ('--', '-') else None,
                            'mom': float(mom) if mom and mom not in ('--', '-') else None,
                        }
                    except (ValueError, TypeError):
                        pass
            time.sleep(1)
        except Exception as e:
            print(f"  上市 {roc_y}/{m:02d} 失敗: {e}")

    return results

def fetch_otc_revenue():
    """抓上櫃公司月營收"""
    today = date.today()
    results = {}

    for delta in [0, 1, 2]:
        if today.month - delta <= 0:
            y = today.year - 1
            m = today.month - delta + 12
        else:
            y = today.year
            m = today.month - delta

        roc_y = y - 1911
        url = f"https://www.tpex.org.tw/openapi/v1/tpex_monthly_report_by_company?l=zh-tw&o=json&d={roc_y}/{m:02d}"
        try:
            data = fetch_url(url)
            # TPEX 格式可能不同，嘗試解析
            print(f"  上櫃 {roc_y}/{m:02d}: {len(data) if isinstance(data, list) else 'non-list'} 筆")
            ym = f"{y}-{m:02d}"
            if isinstance(data, list):
                for row in data:
                    sym = (row.get('SecuritiesCompanyCode') or row.get('公司代號', '')).strip()
                    rev_raw = (row.get('Revenue') or row.get('當月營收', '0')).replace(',', '').strip()
                    yoy_raw = (row.get('YoYGrowthRate') or row.get('去年同月增減(%)', '')).replace(',', '').strip()
                    mom_raw = (row.get('MoMGrowthRate') or row.get('上月比較增減(%)', '')).replace(',', '').strip()
                    if sym and rev_raw:
                        sym_two = sym + '.TWO'
                        if sym_two not in results:
                            results[sym_two] = {}
                        try:
                            results[sym_two][ym] = {
                                'rev': int(rev_raw),
                                'yoy': float(yoy_raw) if yoy_raw and yoy_raw not in ('--', '-') else None,
                                'mom': float(mom_raw) if mom_raw and mom_raw not in ('--', '-') else None,
                            }
                        except (ValueError, TypeError):
                            pass
            time.sleep(1)
        except Exception as e:
            print(f"  上櫃 {roc_y}/{m:02d} 失敗: {e}")

    return results

def merge_existing(new_data):
    """與既有資料合併，保留歷史月份"""
    if not os.path.exists(OUTPUT_PATH):
        return new_data
    try:
        with open(OUTPUT_PATH, encoding='utf-8') as f:
            existing = json.load(f).get('data', {})
    except Exception:
        return new_data

    merged = {}
    all_syms = set(existing.keys()) | set(new_data.keys())
    for sym in all_syms:
        old = existing.get(sym, {})
        new = new_data.get(sym, {})
        combined = {**old, **new}
        # 只保留最近 N 個月
        sorted_months = sorted(combined.keys(), reverse=True)[:MONTHS_TO_KEEP]
        merged[sym] = {m: combined[m] for m in sorted_months}
    return merged

def main():
    os.makedirs('data', exist_ok=True)
    print("抓取月營收...")

    tse = fetch_twse_revenue()
    print(f"上市：{len(tse)} 檔")

    otc = fetch_otc_revenue()
    print(f"上櫃：{len(otc)} 檔")

    combined = {**tse, **otc}
    merged = merge_existing(combined)

    out = {
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'count': len(merged),
        'data': merged,
    }
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))

    sz = os.path.getsize(OUTPUT_PATH) / 1024 / 1024
    print(f"\n完成：{len(merged)} 檔，{sz:.1f} MB → {OUTPUT_PATH}")

if __name__ == '__main__':
    main()

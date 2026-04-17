#!/usr/bin/env python3
"""
外資買賣超抓取腳本
每個交易日跑，抓最近 30 個交易日的外資淨買賣超
輸出：data/foreign.json

TWSE API: https://openapi.twse.com.tw/v1/exchangeReport/MI_QFIIS_sort
"""

import json, os, time, urllib.request, ssl
from datetime import datetime, date, timedelta

OUTPUT_PATH = "data/foreign.json"
DAYS_TO_KEEP = 30   # 保留最近 30 個交易日

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

def fetch_foreign_day(date_str):
    """抓指定日期的外資買賣超 (格式: YYYYMMDD)"""
    url = f"https://openapi.twse.com.tw/v1/exchangeReport/MI_QFIIS_sort?response=json&date={date_str}&selectType=ALLBUT0999"
    try:
        data = fetch_url(url)
        result = {}
        if isinstance(data, list):
            for row in data:
                sym = row.get('Code', '').strip()
                net = row.get('Foreign_Investor_Net_Buy_or_Sell', '0').replace(',', '').strip()
                buy = row.get('Foreign_Investor_Buy', '0').replace(',', '').strip()
                sell= row.get('Foreign_Investor_Sell', '0').replace(',', '').strip()
                if sym:
                    try:
                        result[sym + '.TW'] = {
                            'net':  int(net)  if net  and net  != '--' else 0,
                            'buy':  int(buy)  if buy  and buy  != '--' else 0,
                            'sell': int(sell) if sell and sell != '--' else 0,
                        }
                    except (ValueError, TypeError):
                        pass
        return result
    except Exception as e:
        print(f"  {date_str} 失敗: {e}")
        return {}

def fetch_otc_foreign_day(date_str):
    """抓上櫃外資買賣超"""
    # 轉民國年
    y = int(date_str[:4]) - 1911
    m = date_str[4:6]
    d = date_str[6:8]
    url = f"https://www.tpex.org.tw/web/stock/3insti/foreign_inv/qfiis_result.php?l=zh-tw&se=EW&t=D&d={y}/{m}/{d}&s=0,asc"
    try:
        data = fetch_url(url)
        result = {}
        rows = data.get('aaData', [])
        for row in rows:
            if isinstance(row, list) and len(row) >= 8:
                sym = str(row[0]).strip()
                net_raw = str(row[7]).replace(',', '').strip()
                buy_raw = str(row[5]).replace(',', '').strip()
                sell_raw= str(row[6]).replace(',', '').strip()
                if sym:
                    try:
                        result[sym + '.TWO'] = {
                            'net':  int(net_raw)  if net_raw  not in ('', '--') else 0,
                            'buy':  int(buy_raw)  if buy_raw  not in ('', '--') else 0,
                            'sell': int(sell_raw) if sell_raw not in ('', '--') else 0,
                        }
                    except (ValueError, TypeError):
                        pass
        return result
    except Exception as e:
        print(f"  OTC {date_str} 失敗: {e}")
        return {}

def get_recent_trading_dates(n=5):
    """取最近 n 個可能的交易日（週一到週五）"""
    dates = []
    d = date.today()
    while len(dates) < n:
        if d.weekday() < 5:  # Mon-Fri
            dates.append(d.strftime('%Y%m%d'))
        d -= timedelta(days=1)
    return dates

def merge_existing(new_data):
    """與既有資料合併"""
    if not os.path.exists(OUTPUT_PATH):
        return new_data
    try:
        with open(OUTPUT_PATH, encoding='utf-8') as f:
            existing = json.load(f).get('data', {})
    except Exception:
        return new_data

    # new_data 結構: {date_str: {symbol: {net, buy, sell}}}
    merged = {**existing}
    for dt, syms in new_data.items():
        merged[dt] = syms

    # 只保留最近 N 個交易日
    sorted_dates = sorted(merged.keys(), reverse=True)[:DAYS_TO_KEEP]
    return {d: merged[d] for d in sorted_dates}

def main():
    os.makedirs('data', exist_ok=True)
    print("抓取外資買賣超...")

    dates = get_recent_trading_dates(5)   # 抓最近 5 個交易日
    new_data = {}

    for ds in dates:
        print(f"  {ds}...", end=' ', flush=True)
        tse = fetch_foreign_day(ds)
        otc = fetch_otc_foreign_day(ds)
        combined = {**tse, **otc}
        if combined:
            new_data[ds] = combined
            print(f"✓ {len(combined)} 檔")
        else:
            print("無資料（可能非交易日）")
        time.sleep(1.5)

    merged = merge_existing(new_data)

    # 轉換成 symbol-based 格式，方便前端查詢
    # sym_data: {symbol: [{date, net, buy, sell}, ...]}
    sym_data = {}
    for dt in sorted(merged.keys()):
        for sym, v in merged[dt].items():
            if sym not in sym_data:
                sym_data[sym] = []
            sym_data[sym].append({'d': dt, 'net': v['net'], 'buy': v['buy'], 'sell': v['sell']})

    out = {
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'dates': sorted(merged.keys()),
        'by_date': merged,
        'by_symbol': sym_data,
    }
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))

    sz = os.path.getsize(OUTPUT_PATH) / 1024 / 1024
    print(f"\n完成：{len(sym_data)} 檔，{sz:.1f} MB → {OUTPUT_PATH}")

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
股息資料抓取腳本（yfinance）
每週跑一次即可
輸出：data/dividend.json
"""

import yfinance as yf
import json, os, time
from datetime import datetime
import twstock

OUTPUT_PATH = "data/dividend.json"

def get_all_symbols():
    codes = twstock.codes
    tse = [k + ".TW"  for k, v in codes.items() if v.market == "上市" and v.type == "股票"]
    otc = [k + ".TWO" for k, v in codes.items() if v.market == "上櫃" and v.type == "股票"]
    return tse + otc

def fetch_dividend(symbol):
    try:
        tk = yf.Ticker(symbol)
        divs = tk.dividends
        if divs is None or len(divs) == 0:
            return None
        # 取最近 3 年
        recent = divs.tail(10)
        records = []
        for ts, amount in recent.items():
            records.append({
                'd': ts.strftime('%Y-%m-%d'),
                'a': round(float(amount), 4),
            })
        return records if records else None
    except Exception:
        return None

def main():
    os.makedirs('data', exist_ok=True)
    syms = get_all_symbols()
    print(f"抓取 {len(syms)} 檔股息資料...")

    results = {}
    done = 0
    for sym in syms:
        data = fetch_dividend(sym)
        if data:
            results[sym] = data
            done += 1
        time.sleep(0.3)
        if done % 100 == 0 and done > 0:
            print(f"  進度: {done} 有股息 / {syms.index(sym)+1} 檔已處理")
            time.sleep(3)

    out = {
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'count': len(results),
        'data': results,
    }
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))

    sz = os.path.getsize(OUTPUT_PATH) / 1024
    print(f"\n完成：{len(results)} 檔有股息資料，{sz:.0f} KB → {OUTPUT_PATH}")

if __name__ == '__main__':
    main()

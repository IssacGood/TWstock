#!/usr/bin/env python3
"""
合併三批 JSON 成 data/stocks.json
完全不需要任何第三方套件，只用標準庫
用法：python scripts/merge_data.py
"""

import json, os, glob
from datetime import datetime

OUTPUT_DIR = "data"
OUTPUT_FILE = f"{OUTPUT_DIR}/stocks.json"

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_stocks = []
    all_failed = []

    for batch_id in ["A", "B", "C"]:
        path = f"{OUTPUT_DIR}/stocks_{batch_id}.json"
        if not os.path.exists(path):
            print(f"  ⚠ {path} 不存在，跳過")
            continue
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        stocks  = d.get("stocks", [])
        failed  = d.get("failed", [])
        all_stocks.extend(stocks)
        all_failed.extend(failed)
        print(f"  Batch {batch_id}: {len(stocks)} 檔，失敗 {len(failed)} 檔")

    out = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "count":  len(all_stocks),
        "failed": all_failed,
        "stocks": all_stocks,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    print(f"\n✓ 合併完成：{len(all_stocks)} 檔 → {OUTPUT_FILE}")
    if all_failed:
        print(f"  共 {len(all_failed)} 檔失敗：{all_failed[:10]}{'...' if len(all_failed)>10 else ''}")

if __name__ == "__main__":
    main()

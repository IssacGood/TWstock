#!/usr/bin/env python3
"""
合併三批 JSON → data/stocks.json（index，不含 candles）
K 棒資料保留在 stocks_A/B/C.json，前端依 batch 欄位載入
純標準庫，零依賴
"""

import json, os
from datetime import datetime

OUTPUT_DIR  = "data"
OUTPUT_FILE = f"{OUTPUT_DIR}/stocks.json"

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_index, all_failed = [], []

    for batch_id in ["A", "B", "C"]:
        path = f"{OUTPUT_DIR}/stocks_{batch_id}.json"
        if not os.path.exists(path):
            print(f"  ⚠ {path} 不存在，跳過")
            continue
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        stocks = d.get("stocks", [])
        failed = d.get("failed", [])
        all_failed.extend(failed)
        sz = os.path.getsize(path) / 1024 / 1024
        print(f"  Batch {batch_id}: {len(stocks)} 檔  ({sz:.1f} MB)")

        # ★ 只存 index（不含 candles），batch 欄位永遠寫入
        for s in stocks:
            all_index.append({
                "symbol": s["symbol"],
                "name":   s["name"],
                "group":  s.get("group", ""),
                "lc":     s.get("lc"),
                "chg":    s.get("chg"),
                "ind":    s.get("ind", {}),
                "flags":  s.get("flags", {}),
                "batch":  batch_id,   # ← 明確指定 batch ID
            })

    out = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "count":      len(all_index),
        "failed":     all_failed,
        "stocks":     all_index,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    sz = os.path.getsize(OUTPUT_FILE) / 1024 / 1024
    print(f"\n✓ index 完成：{len(all_index)} 檔 → {OUTPUT_FILE}  ({sz:.1f} MB)")
    if all_failed:
        print(f"  共 {len(all_failed)} 檔失敗")

if __name__ == "__main__":
    main()

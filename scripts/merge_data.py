#!/usr/bin/env python3
"""
合併三批 JSON → data/stocks.json
純標準庫，零依賴
用法：python scripts/merge_data.py
"""

import json, os
from datetime import datetime

OUTPUT_DIR  = "data"
OUTPUT_FILE = f"{OUTPUT_DIR}/stocks.json"
MAX_MB      = 95  # GitHub 限制 100MB，保留緩衝

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_stocks, all_failed = [], []

    for batch_id in ["A", "B", "C"]:
        path = f"{OUTPUT_DIR}/stocks_{batch_id}.json"
        if not os.path.exists(path):
            print(f"  ⚠ {path} 不存在，跳過")
            continue
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        stocks = d.get("stocks", [])
        failed = d.get("failed", [])
        all_stocks.extend(stocks)
        all_failed.extend(failed)
        sz = os.path.getsize(path) / 1024 / 1024
        print(f"  Batch {batch_id}: {len(stocks)} 檔  ({sz:.1f} MB)")

    out = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "count":  len(all_stocks),
        "failed": all_failed,
        "stocks": all_stocks,
    }

    content = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    size_mb = len(content.encode("utf-8")) / 1024 / 1024
    print(f"\n合併後大小：{size_mb:.1f} MB")

    if size_mb > MAX_MB:
        # 超過限制 → 不合併，改存三個獨立檔
        print(f"⚠ 超過 {MAX_MB}MB，改為分開儲存（前端會分批載入）")
        # 在 stocks.json 只存 index（不含 candles）
        index = []
        for s in all_stocks:
            index.append({
                "symbol": s["symbol"],
                "name":   s["name"],
                "lc":     s.get("lc"),
                "chg":    s.get("chg"),
                "ind":    s.get("ind"),
                "flags":  s.get("flags"),
                "batch":  s.get("batch","A"),  # ← 前端用來判斷去哪個檔案拿K棒
            })
        out_index = {
            "updated_at": out["updated_at"],
            "count":      len(index),
            "failed":     all_failed,
            "mode":       "split",   # 前端看這個決定要不要分批載入
            "stocks":     index,
        }
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(out_index, f, ensure_ascii=False, separators=(",", ":"))
        sz2 = os.path.getsize(OUTPUT_FILE) / 1024 / 1024
        print(f"✓ index 檔：{sz2:.1f} MB → {OUTPUT_FILE}")
        print("  K棒資料保留在 stocks_A/B/C.json，前端點開大圖時再載入")
    else:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✓ 合併完成：{len(all_stocks)} 檔 → {OUTPUT_FILE}  ({size_mb:.1f} MB)")

    if all_failed:
        print(f"共 {len(all_failed)} 檔失敗")

if __name__ == "__main__":
    main()

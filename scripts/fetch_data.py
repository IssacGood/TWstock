#!/usr/bin/env python3
"""
台股全量資料抓取腳本
支援分批模式：python fetch_data.py --batch A/B/C
由 GitHub Actions 3 個平行 job 執行，最後合併成 data/stocks.json

依賴：pip install yfinance pandas twstock
"""

import yfinance as yf
import pandas as pd
import json, os, sys, time, argparse
from datetime import datetime
import twstock

# ── 設定 ──────────────────────────────────────────────────
OUTPUT_DIR  = "data"
PERIOD      = "2y"      # 抓 2 年歷史
SLEEP_EACH  = 0.5       # 每檔間隔（秒）
SLEEP_BATCH = 5         # 每 20 檔暫停（秒）
BATCH_SIZE  = 20

def get_all_symbols():
    """從 twstock 內建清單取得全部台股代碼（含中文名）"""
    codes = twstock.codes
    tse = [(k + ".TW",  v.name) for k, v in codes.items()
           if v.market == "上市" and v.type == "股票"]
    otc = [(k + ".TWO", v.name) for k, v in codes.items()
           if v.market == "上櫃" and v.type == "股票"]
    all_stocks = sorted(tse) + sorted(otc)
    return all_stocks   # list of (symbol, zh_name)

def split_batch(all_stocks, batch_id):
    """將清單分成 A/B/C 三批，batch_id = 'A'/'B'/'C'/'ALL'"""
    n = len(all_stocks)
    if batch_id == "ALL":
        return all_stocks
    size = n // 3
    ranges = {
        "A": all_stocks[:size],
        "B": all_stocks[size:size*2],
        "C": all_stocks[size*2:],
    }
    return ranges[batch_id]

# ── 技術指標 ──────────────────────────────────────────────
def sma(s, n): return s.rolling(n).mean()
def ema(s, n): return s.ewm(span=n, adjust=False).mean()

def rsi(s, n=14):
    d = s.diff()
    g = d.clip(lower=0).rolling(n).mean()
    l = (-d.clip(upper=0)).rolling(n).mean()
    return 100 - 100 / (1 + g / l.replace(0, float("nan")))

def macd(s):
    line   = ema(s,12) - ema(s,26)
    signal = ema(line, 9)
    return line, signal, line - signal

def safe(v):
    if v is None: return None
    try:
        f = float(v)
        return None if f != f else round(f, 4)
    except: return None

# ── 單檔抓取 ──────────────────────────────────────────────
def fetch_stock(symbol, zh_name=""):
    try:
        tk = yf.Ticker(symbol)
        df = tk.history(period=PERIOD, auto_adjust=True)
        if df.empty or len(df) < 20:
            return None

        df = df[["Open","High","Low","Close","Volume"]].dropna()
        df.index = df.index.tz_localize(None)
        c = df["Close"]

        df["MA5"]  = sma(c,5);  df["MA10"] = sma(c,10)
        df["MA20"] = sma(c,20); df["MA60"] = sma(c,60)
        df["RSI"]  = rsi(c)
        ml, ms, mh = macd(c)
        df["MACD"] = ml; df["MACDs"] = ms; df["MACDh"] = mh

        mid = sma(c,20); std = c.rolling(20).std()
        df["BBu"] = mid + 2*std; df["BBl"] = mid - 2*std

        df["VM5"]  = df["Volume"].rolling(5).mean()
        df["VM20"] = df["Volume"].rolling(20).mean()

        df = df.dropna(subset=["MA20"])
        if len(df) < 2: return None

        last = df.iloc[-1]; prev = df.iloc[-2]

        # 名稱：優先用 twstock 中文名，再 fallback 到 yfinance
        name = zh_name
        if not name:
            try:
                info  = tk.info
                name  = info.get("shortName") or info.get("longName") or symbol
            except: name = symbol

        candles = []
        for ts, row in df.iterrows():
            candles.append({
                "t": ts.strftime("%Y-%m-%d"),
                "o": safe(row.Open),  "h": safe(row.High),
                "l": safe(row.Low),   "c": safe(row.Close),
                "v": int(row.Volume) if not pd.isna(row.Volume) else 0,
                "ma5":  safe(row.MA5),  "ma10": safe(row.MA10),
                "ma20": safe(row.MA20), "ma60": safe(row.MA60),
                "bb_u": safe(row.BBu),  "bb_l": safe(row.BBl),
                "rsi":  safe(row.RSI),
                "macd": safe(row.MACD), "macd_s": safe(row.MACDs),
                "vol_m20": safe(row.VM20),
            })

        def b(cond):
            try: return bool(cond)
            except: return False

        flags = {
            "above_ma20":     b(last.Close > last.MA20),
            "above_ma60":     b(last.Close > last.MA60),
            "ma5_above_ma20": b(last.MA5   > last.MA20),
            "golden_cross":   b(last.MA5 > last.MA20 and prev.MA5 <= prev.MA20),
            "death_cross":    b(last.MA5 < last.MA20 and prev.MA5 >= prev.MA20),
            "rsi_oversold":   b(safe(last.RSI) is not None and last.RSI < 30),
            "rsi_overbought": b(safe(last.RSI) is not None and last.RSI > 70),
            "macd_bullish":   b(safe(last.MACD) is not None and last.MACD > last.MACDs),
            "vol_surge":      b(safe(last.VM20) is not None and last.Volume > last.VM20 * 1.5),
            "near_bb_upper":  b(safe(last.BBu) is not None and last.Close > last.BBu * 0.98),
            "near_bb_lower":  b(safe(last.BBl) is not None and last.Close < last.BBl * 1.02),
            "bullish_candle": b(last.Close > last.Open),
            "new_high_50":    b(last.Close == df.Close.tail(50).max()),
            "new_low_50":     b(last.Close == df.Close.tail(50).min()),
        }

        chg = safe((last.Close - prev.Close) / prev.Close * 100)
        return {
            "symbol": symbol, "name": name,
            "last_close": safe(last.Close), "change_pct": chg,
            "flags": flags, "candles": candles,
        }

    except Exception as e:
        return None


# ── 主程式 ────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", default="ALL",
                        choices=["A","B","C","ALL"],
                        help="分批執行：A/B/C 或 ALL")
    parser.add_argument("--merge", action="store_true",
                        help="合併 A/B/C 三個 JSON 成 stocks.json")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ── 合併模式 ──────────────────────────────────────────
    if args.merge:
        print("合併 A/B/C 三批資料...")
        all_stocks = []
        failed_all = []
        for bid in ["A","B","C"]:
            path = f"{OUTPUT_DIR}/stocks_{bid}.json"
            if not os.path.exists(path):
                print(f"  ⚠ {path} 不存在，跳過")
                continue
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            all_stocks.extend(d.get("stocks", []))
            failed_all.extend(d.get("failed", []))
            print(f"  Batch {bid}: {len(d.get('stocks',[]))} 檔")

        out = {
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "count":      len(all_stocks),
            "failed":     failed_all,
            "stocks":     all_stocks,
        }
        outpath = f"{OUTPUT_DIR}/stocks.json"
        with open(outpath, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, separators=(",",":"))
        print(f"✓ 合併完成：{len(all_stocks)} 檔 → {outpath}")
        return

    # ── 抓取模式 ──────────────────────────────────────────
    all_syms = get_all_symbols()
    batch    = split_batch(all_syms, args.batch)
    total    = len(batch)
    print(f"Batch {args.batch}：共 {total} 檔（總清單 {len(all_syms)} 檔）")

    results  = []
    failures = []

    for i, (symbol, zh_name) in enumerate(batch):
        print(f"  [{i+1:4d}/{total}] {symbol:<12} {zh_name[:8]:<8}", end=" ", flush=True)
        data = fetch_stock(symbol, zh_name)
        if data:
            results.append(data)
            print(f"✓ ({len(data['candles'])}根)")
        else:
            failures.append(symbol)
            print("✗")
        time.sleep(SLEEP_EACH)
        if (i+1) % BATCH_SIZE == 0 and i+1 < total:
            time.sleep(SLEEP_BATCH)

    out = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "batch":      args.batch,
        "count":      len(results),
        "failed":     failures,
        "stocks":     results,
    }
    outpath = f"{OUTPUT_DIR}/stocks_{args.batch}.json"
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",",":"))

    print(f"\n{'='*50}")
    print(f"Batch {args.batch} 完成：成功 {len(results)} / 失敗 {len(failures)}")
    if failures: print(f"失敗清單：{failures[:20]}{'...' if len(failures)>20 else ''}")
    print(f"已寫入 {outpath}")


if __name__ == "__main__":
    main()

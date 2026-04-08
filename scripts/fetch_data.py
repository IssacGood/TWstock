#!/usr/bin/env python3
"""
台股全量資料抓取腳本
用法：python scripts/fetch_data.py --batch A   (或 B / C)
依賴：pip install yfinance pandas twstock
"""

import yfinance as yf
import pandas as pd
import json, os, time, argparse
from datetime import datetime
import twstock

# ── 設定 ─────────────────────────────────
OUTPUT_DIR  = "data"
PERIOD      = "2y"
SLEEP_EACH  = 0.5
SLEEP_BATCH = 5
BATCH_SIZE  = 20

def get_all_symbols():
    codes = twstock.codes
    tse = [(k + ".TW",  v.name) for k, v in codes.items()
           if v.market == "上市" and v.type == "股票"]
    otc = [(k + ".TWO", v.name) for k, v in codes.items()
           if v.market == "上櫃" and v.type == "股票"]
    return sorted(tse) + sorted(otc)

def split_batch(all_stocks, batch_id):
    n    = len(all_stocks)
    size = n // 3
    return {"A": all_stocks[:size],
            "B": all_stocks[size:size*2],
            "C": all_stocks[size*2:]}[batch_id]

def sma(s, n): return s.rolling(n).mean()
def ema(s, n): return s.ewm(span=n, adjust=False).mean()

def rsi(s, n=14):
    d = s.diff()
    g = d.clip(lower=0).rolling(n).mean()
    l = (-d.clip(upper=0)).rolling(n).mean()
    return 100 - 100 / (1 + g / l.replace(0, float("nan")))

def macd(s):
    line = ema(s,12) - ema(s,26)
    sig  = ema(line, 9)
    return line, sig, line - sig

def safe(v):
    if v is None: return None
    try:
        f = float(v)
        return None if f != f else round(f, 4)
    except: return None

def fetch_stock(symbol, zh_name=""):
    try:
        tk = yf.Ticker(symbol)
        df = tk.history(period=PERIOD, auto_adjust=True)
        if df.empty or len(df) < 20: return None

        df = df[["Open","High","Low","Close","Volume"]].dropna()
        df.index = df.index.tz_localize(None)
        c = df["Close"]

        df["MA5"]  = sma(c,5);  df["MA10"] = sma(c,10)
        df["MA20"] = sma(c,20); df["MA60"] = sma(c,60)
        df["RSI"]  = rsi(c)
        ml, ms, mh = macd(c)
        df["MACD"] = ml; df["MACDs"] = ms

        mid = sma(c,20); std = c.rolling(20).std()
        df["BBu"] = mid + 2*std; df["BBl"] = mid - 2*std

        df["VM20"] = df["Volume"].rolling(20).mean()
        df = df.dropna(subset=["MA20"])
        if len(df) < 2: return None

        last = df.iloc[-1]; prev = df.iloc[-2]

        name = zh_name
        if not name:
            try:
                info = tk.info
                name = info.get("shortName") or info.get("longName") or symbol
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
            "rsi_oversold":   b(safe(last.RSI)  is not None and last.RSI  < 30),
            "rsi_overbought": b(safe(last.RSI)  is not None and last.RSI  > 70),
            "macd_bullish":   b(safe(last.MACD) is not None and last.MACD > last.MACDs),
            "vol_surge":      b(safe(last.VM20) is not None and last.Volume > last.VM20 * 1.5),
            "near_bb_upper":  b(safe(last.BBu)  is not None and last.Close > last.BBu * 0.98),
            "near_bb_lower":  b(safe(last.BBl)  is not None and last.Close < last.BBl * 1.02),
            "bullish_candle": b(last.Close > last.Open),
            "new_high_50":    b(last.Close == df.Close.tail(50).max()),
            "new_low_50":     b(last.Close == df.Close.tail(50).min()),
        }

        return {
            "symbol": symbol, "name": name,
            "last_close": safe(last.Close),
            "change_pct": safe((last.Close - prev.Close) / prev.Close * 100),
            "flags": flags, "candles": candles,
        }
    except: return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", required=True, choices=["A","B","C"])
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    all_syms = get_all_symbols()
    batch    = split_batch(all_syms, args.batch)
    total    = len(batch)
    print(f"Batch {args.batch}：{total} 檔（總清單 {len(all_syms)} 檔）")

    results, failures = [], []
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

    outpath = f"{OUTPUT_DIR}/stocks_{args.batch}.json"
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "batch": args.batch,
            "count": len(results),
            "failed": failures,
            "stocks": results,
        }, f, ensure_ascii=False, separators=(",",":"))

    print(f"\nBatch {args.batch} 完成：成功 {len(results)} / 失敗 {len(failures)}")
    print(f"已寫入 {outpath}")

if __name__ == "__main__":
    main()

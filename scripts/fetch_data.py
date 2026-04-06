#!/usr/bin/env python3
"""
台股資料抓取腳本
每天由 GitHub Actions 自動執行，抓取台股 K 線與篩選指標
輸出：data/stocks.json
"""

import yfinance as yf
import pandas as pd
import json
import os
from datetime import datetime, timedelta
import time

# ── 設定 ──────────────────────────────────────────────────
OUTPUT_PATH = "data/stocks.json"
PERIOD      = "6mo"   # 抓半年資料，前端取最近 50 根 K 棒
BATCH_SIZE  = 20      # 每批抓幾檔，避免被限速

# 監控股票清單（上市+上櫃常見成分股，可自行增減）
WATCH_LIST = [
    # 半導體 / 電子
    "2330.TW","2317.TW","2454.TW","2308.TW","2382.TW",
    "2303.TW","2357.TW","2379.TW","3711.TW","2344.TW",
    "2301.TW","2408.TW","3008.TW","2458.TW","2449.TW",
    "6770.TW","2337.TW","3034.TW","2345.TW","6415.TW",
    # 金融
    "2882.TW","2881.TW","2891.TW","2886.TW","2884.TW",
    "2880.TW","2892.TW","2885.TW","5880.TW","2887.TW",
    # 傳產 / 民生
    "1301.TW","1303.TW","1326.TW","2002.TW","1101.TW",
    "2912.TW","2207.TW","2105.TW","1216.TW","2迷382.TW",
    # 上櫃 (TWO)
    "6669.TWO","3231.TWO","5269.TWO","6278.TWO","3105.TWO",
    "8150.TWO","6598.TWO","4958.TWO","3706.TWO","6770.TWO",
]

# 去除可能的打字錯誤
WATCH_LIST = list(dict.fromkeys(
    s for s in WATCH_LIST if s.replace(".TW","").replace(".TWO","").isdigit() or
    all(c.isdigit() or c.isalpha() for c in s.replace(".TW","").replace(".TWO",""))
))

def sma(series, n):
    return series.rolling(n).mean()

def ema(series, n):
    return series.ewm(span=n, adjust=False).mean()

def rsi(series, n=14):
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(n).mean()
    loss  = (-delta.clip(upper=0)).rolling(n).mean()
    rs    = gain / loss.replace(0, float('nan'))
    return 100 - 100 / (1 + rs)

def macd(series):
    e12 = ema(series, 12)
    e26 = ema(series, 26)
    line   = e12 - e26
    signal = ema(line, 9)
    hist   = line - signal
    return line, signal, hist

def fetch_stock(symbol):
    try:
        tk   = yf.Ticker(symbol)
        hist = tk.fast_info
        df   = tk.history(period=PERIOD, auto_adjust=True)
        if df.empty or len(df) < 20:
            return None

        df = df[["Open","High","Low","Close","Volume"]].dropna()
        df.index = df.index.tz_localize(None)

        close = df["Close"]

        # 技術指標
        df["MA5"]   = sma(close, 5)
        df["MA10"]  = sma(close, 10)
        df["MA20"]  = sma(close, 20)
        df["MA60"]  = sma(close, 60)
        df["RSI14"] = rsi(close, 14)
        macd_line, macd_sig, macd_hist = macd(close)
        df["MACD"]      = macd_line
        df["MACDsig"]   = macd_sig
        df["MACDhist"]  = macd_hist

        # 布林通道
        mid  = sma(close, 20)
        std  = close.rolling(20).std()
        df["BB_upper"] = mid + 2 * std
        df["BB_lower"] = mid - 2 * std
        df["BB_mid"]   = mid

        # 成交量 MA
        df["VolMA5"]  = df["Volume"].rolling(5).mean()
        df["VolMA20"] = df["Volume"].rolling(20).mean()

        df = df.dropna(subset=["MA20"])

        # 取最近 50 根 K 棒
        df50 = df.tail(50)

        last = df50.iloc[-1]
        prev = df50.iloc[-2] if len(df50) >= 2 else last

        # 基本資訊
        try:
            info       = tk.info
            name       = info.get("longName") or info.get("shortName") or symbol
            market_cap = info.get("marketCap", 0)
            revenue    = info.get("totalRevenue", 0)
            pe         = info.get("trailingPE", None)
        except Exception:
            name       = symbol
            market_cap = 0
            revenue    = 0
            pe         = None

        def safe(v):
            if v is None: return None
            if isinstance(v, float):
                if pd.isna(v) or v != v: return None
            return round(float(v), 4)

        candles = []
        for ts, row in df50.iterrows():
            candles.append({
                "t":      ts.strftime("%Y-%m-%d"),
                "o":      safe(row["Open"]),
                "h":      safe(row["High"]),
                "l":      safe(row["Low"]),
                "c":      safe(row["Close"]),
                "v":      int(row["Volume"]) if not pd.isna(row["Volume"]) else 0,
                "ma5":    safe(row["MA5"]),
                "ma10":   safe(row["MA10"]),
                "ma20":   safe(row["MA20"]),
                "ma60":   safe(row["MA60"]),
                "bb_u":   safe(row["BB_upper"]),
                "bb_m":   safe(row["BB_mid"]),
                "bb_l":   safe(row["BB_lower"]),
                "rsi":    safe(row["RSI14"]),
                "macd":   safe(row["MACD"]),
                "macd_s": safe(row["MACDsig"]),
                "macd_h": safe(row["MACDhist"]),
                "vol_m5": safe(row["VolMA5"]),
                "vol_m20":safe(row["VolMA20"]),
            })

        # 篩選旗標（方便前端過濾，不用在前端重算）
        flags = {
            "above_ma20":    bool(last["Close"] > last["MA20"]),
            "above_ma60":    bool(last["Close"] > last["MA60"]),
            "ma5_above_ma20":bool(last["MA5"]  > last["MA20"]) if safe(last["MA5"]) else False,
            "golden_cross":  bool(last["MA5"]  > last["MA20"] and prev["MA5"] <= prev["MA20"]) if safe(prev["MA5"]) else False,
            "death_cross":   bool(last["MA5"]  < last["MA20"] and prev["MA5"] >= prev["MA20"]) if safe(prev["MA5"]) else False,
            "rsi_oversold":  bool(last["RSI14"] < 30) if safe(last["RSI14"]) else False,
            "rsi_overbought":bool(last["RSI14"] > 70) if safe(last["RSI14"]) else False,
            "macd_bullish":  bool(last["MACD"] > last["MACDsig"]) if safe(last["MACD"]) else False,
            "vol_surge":     bool(last["Volume"] > last["VolMA20"] * 1.5) if safe(last["VolMA20"]) else False,
            "near_bb_upper": bool(last["Close"] > last["BB_upper"] * 0.98) if safe(last["BB_upper"]) else False,
            "near_bb_lower": bool(last["Close"] < last["BB_lower"] * 1.02) if safe(last["BB_lower"]) else False,
            "bullish_candle":bool(last["Close"] > last["Open"]),
            "new_high_20":   bool(last["Close"] == df50["Close"].max()),
            "new_low_20":    bool(last["Close"] == df50["Close"].min()),
        }

        # 漲跌幅
        change_pct = safe((last["Close"] - prev["Close"]) / prev["Close"] * 100)

        return {
            "symbol":     symbol,
            "name":       name,
            "last_close": safe(last["Close"]),
            "change_pct": change_pct,
            "market_cap": market_cap,
            "revenue":    revenue,
            "pe":         pe,
            "flags":      flags,
            "candles":    candles,
        }

    except Exception as e:
        print(f"  ✗ {symbol}: {e}")
        return None


def main():
    os.makedirs("data", exist_ok=True)
    results = []
    total   = len(WATCH_LIST)

    print(f"開始抓取 {total} 檔股票資料...")

    for i in range(0, total, BATCH_SIZE):
        batch = WATCH_LIST[i:i+BATCH_SIZE]
        for symbol in batch:
            print(f"  [{i+1}/{total}] {symbol} ...", end=" ", flush=True)
            data = fetch_stock(symbol)
            if data:
                results.append(data)
                print(f"✓  ({data['name']})")
            time.sleep(0.3)   # 輕度限速
        if i + BATCH_SIZE < total:
            print("  暫停 2 秒...")
            time.sleep(2)

    output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "count":      len(results),
        "stocks":     results,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))

    print(f"\n完成！共 {len(results)} 檔，已寫入 {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

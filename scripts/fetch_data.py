#!/usr/bin/env python3
"""
台股全量資料抓取腳本 - 含產業分類
用法：python scripts/fetch_data.py --batch A/B/C
依賴：pip install yfinance pandas twstock
"""

import yfinance as yf
import pandas as pd
import json, os, time, argparse
from datetime import datetime
import twstock

OUTPUT_DIR  = "data"
PERIOD      = "2y"
SLEEP_EACH  = 0.5
SLEEP_BATCH = 5
BATCH_SIZE  = 20

def get_all_symbols():
    codes = twstock.codes
    tse = [(k+".TW",  v.name, v.group or "其他") for k,v in codes.items()
           if v.market == "上市" and v.type == "股票"]
    otc = [(k+".TWO", v.name, v.group or "其他") for k,v in codes.items()
           if v.market == "上櫃" and v.type == "股票"]
    return sorted(tse) + sorted(otc)

def split_batch(all_stocks, batch_id):
    n = len(all_stocks); size = n//3
    return {"A":all_stocks[:size],"B":all_stocks[size:size*2],"C":all_stocks[size*2:]}[batch_id]

def sma(s,n): return s.rolling(n).mean()
def ema(s,n): return s.ewm(span=n,adjust=False).mean()
def rsi(s,n=14):
    d=s.diff(); g=d.clip(lower=0).rolling(n).mean(); l=(-d.clip(upper=0)).rolling(n).mean()
    return 100-100/(1+g/l.replace(0,float("nan")))
def macd_calc(s):
    line=ema(s,12)-ema(s,26); sig=ema(line,9); return line,sig

def safe(v):
    if v is None: return None
    try: f=float(v); return None if f!=f else round(f,2)
    except: return None

def fetch_stock(symbol, zh_name="", group=""):
    try:
        tk = yf.Ticker(symbol)
        df = tk.history(period=PERIOD, auto_adjust=True)
        if df.empty or len(df)<20: return None
        df = df[["Open","High","Low","Close","Volume"]].dropna()
        df.index = df.index.tz_localize(None)
        c = df["Close"]

        df["_ma5"]=sma(c,5); df["_ma20"]=sma(c,20); df["_ma60"]=sma(c,60)
        df["_rsi"]=rsi(c)
        ml,ms=macd_calc(c); df["_macd"]=ml; df["_macds"]=ms
        mid=sma(c,20); std=c.rolling(20).std()
        df["_bbu"]=mid+2*std; df["_bbl"]=mid-2*std
        df["_vm20"]=df["Volume"].rolling(20).mean()
        df = df.dropna(subset=["_ma20"])
        if len(df)<2: return None

        last=df.iloc[-1]; prev=df.iloc[-2]

        name=zh_name
        if not name:
            try:
                info=tk.info; name=info.get("shortName") or info.get("longName") or symbol
            except: name=symbol

        # K棒只存 [日期,開,高,低,收,量] 節省空間
        candles=[]
        for ts,row in df.iterrows():
            candles.append([ts.strftime("%Y-%m-%d"),
                safe(row.Open),safe(row.High),safe(row.Low),safe(row.Close),
                int(row.Volume) if not pd.isna(row.Volume) else 0])

        def b(cond):
            try: return bool(cond)
            except: return False

        flags={
            "above_ma20":     b(last.Close>last._ma20),
            "above_ma60":     b(last.Close>last._ma60),
            "ma5_above_ma20": b(last._ma5>last._ma20),
            "golden_cross":   b(last._ma5>last._ma20 and prev._ma5<=prev._ma20),
            "death_cross":    b(last._ma5<last._ma20 and prev._ma5>=prev._ma20),
            "rsi_oversold":   b(safe(last._rsi) is not None and last._rsi<30),
            "rsi_overbought": b(safe(last._rsi) is not None and last._rsi>70),
            "macd_bullish":   b(safe(last._macd) is not None and last._macd>last._macds),
            "vol_surge":      b(safe(last._vm20) is not None and last.Volume>last._vm20*1.5),
            "near_bb_upper":  b(safe(last._bbu) is not None and last.Close>last._bbu*0.98),
            "near_bb_lower":  b(safe(last._bbl) is not None and last.Close<last._bbl*1.02),
            "bullish_candle": b(last.Close>last.Open),
            "new_high_50":    b(last.Close==df.Close.tail(50).max()),
            "new_low_50":     b(last.Close==df.Close.tail(50).min()),
            "price_u100":     b(last.Close<100),
            "price_u200":     b(last.Close<200),
            "price_u500":     b(last.Close<500),
            "price_u1000":    b(last.Close<1000),
        }

        ind={
            "ma5":safe(last._ma5), "ma20":safe(last._ma20),
            "ma60":safe(last._ma60),"rsi":safe(last._rsi),
            "macd":safe(last._macd),"bbu":safe(last._bbu),"bbl":safe(last._bbl),
        }

        return {
            "symbol":  symbol,
            "name":    name,
            "group":   group,   # ← 產業分類
            "lc":      safe(last.Close),
            "chg":     safe((last.Close-prev.Close)/prev.Close*100),
            "ind":     ind,
            "flags":   flags,
            "candles": candles,
        }
    except: return None

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--batch",required=True,choices=["A","B","C"])
    args=parser.parse_args()
    os.makedirs(OUTPUT_DIR,exist_ok=True)

    all_syms=get_all_symbols()
    batch=split_batch(all_syms,args.batch)
    total=len(batch)
    print(f"Batch {args.batch}：{total} 檔（總清單 {len(all_syms)} 檔）")

    results,failures=[],[]
    for i,(symbol,zh_name,group) in enumerate(batch):
        print(f"  [{i+1:4d}/{total}] {symbol:<12} {zh_name[:8]:<8}", end=" ", flush=True)
        data=fetch_stock(symbol,zh_name,group)
        if data:
            data['batch']=args.batch
            results.append(data)
            print(f"✓ ({len(data['candles'])}根) [{group}]")
        else:
            failures.append(symbol); print("✗")
        time.sleep(SLEEP_EACH)
        if (i+1)%BATCH_SIZE==0 and i+1<total: time.sleep(SLEEP_BATCH)

    outpath=f"{OUTPUT_DIR}/stocks_{args.batch}.json"
    with open(outpath,"w",encoding="utf-8") as f:
        json.dump({"updated_at":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                   "batch":args.batch,"count":len(results),
                   "failed":failures,"stocks":results},
                  f,ensure_ascii=False,separators=(",",":"))
    sz=os.path.getsize(outpath)/1024/1024
    print(f"\nBatch {args.batch} 完成：{len(results)} 檔 / 失敗 {len(failures)} 檔 / {sz:.1f}MB")

if __name__=="__main__": main()

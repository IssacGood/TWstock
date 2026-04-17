# 📈 台股選股系統

每天自動抓取全台股 K 線資料，部署於 GitHub Pages，隨時隨地都能查看。

🌐 **線上網址**：`https://你的帳號.github.io/TWstock/`

---

## 功能頁面

| 頁面 | 功能 |
|------|------|
| `index.html` | **選股篩選**：條件篩選（均線/RSI/MACD/布林/周轉率/股價範圍）、類股快選、K線圖、OHLCV、月營收、外資、股息 |
| `watchlist.html` | **批量搜尋**：貼上多個股票代碼，一次顯示 K 線 |
| `favorites.html` | **我的最愛**：庫存盈虧追蹤，本地儲存，K 線查看，買入價水平線 |
| `market.html` | **大盤/期貨**：TradingView 加權指數、台指期、上櫃、小台指 |
| `stats.html` | **統計**：近一個月每日漲跌折線圖、今日漲跌圓餅、股價分佈 |
| `sectors.html` | **類股排行**：各類股漲跌、外資買賣超 |
| `ai.html` | **AI選股**：7種策略組合篩選（強勢動能/超賣反彈/黃金交叉/低價潛力/突破新高/穩健趨勢/高周轉爆量） |
| `fear.html` | **貪婪指數**：CNN/玩股網 |

---

## 快速部署

### 1. Fork/Clone 後推上 GitHub

```bash
git clone https://github.com/你的帳號/TWstock.git
cd TWstock
git add .
git commit -m "init"
git push -u origin main
```

### 2. 開啟 GitHub Pages

Settings → Pages → Source: `main` / `/ (root)` → Save

### 3. 設定 Actions 寫入權限

Settings → Actions → General → **Read and write permissions** → Save

### 4. 手動跑第一次

Actions → **每日台股資料更新** → **Run workflow** → 選 `all` → Run

等約 25 分鐘，全部 1900+ 檔 K 線資料就會產生。

---

## 自動排程

| 時間（台灣） | 執行內容 |
|------------|---------|
| 每週一～五 18:30 | K 線資料（三批平行，約 25 分鐘） |
| 每週一～五 20:00 | 外資買賣超 |
| 每月 10 日 09:00 | 月營收資料 |
| 每週日 02:00 | 股息資料 |

---

## 手動觸發特定 job

Actions → Run workflow → 選擇 job：
- `kline` — 只跑 K 線
- `foreign` — 只跑外資買賣超
- `revenue` — 只跑月營收
- `dividend` — 只跑股息
- `all` — 全部（預設）

---

## 自訂股票清單

編輯 `scripts/fetch_data.py` 裡的 `WATCH_LIST`，但實際上腳本會自動從 `twstock` 套件取得**全部台股**（上市 1045 + 上櫃 880 = 1925 檔），不需要手動維護清單。

---

## 技術架構

```
GitHub Actions（每日）
  ├── fetch_data.py --batch A/B/C  →  data/stocks_A/B/C.json  (K棒+flags)
  ├── merge_data.py                →  data/stocks.json         (index，不含K棒)
  ├── fetch_foreign.py             →  data/foreign.json        (外資買賣超)
  ├── fetch_revenue.py             →  data/revenue.json        (月營收)
  └── fetch_dividend.py            →  data/dividend.json       (股息)

GitHub Pages（靜態）
  ├── 主頁載入 stocks.json（約2MB，快）
  ├── 點開K線時才載入 stocks_A/B/C.json（約20MB，按需）
  └── 技術指標在前端 JS 即時計算（MA/RSI/MACD/布林）
```

---

## 本地測試

```bash
pip install yfinance pandas twstock
python scripts/fetch_data.py --batch A    # 抓 A 批
python scripts/fetch_data.py --batch B
python scripts/fetch_data.py --batch C
python scripts/merge_data.py              # 合併 index
python -m http.server 8080                # 本地服務
# 打開 http://localhost:8080
```

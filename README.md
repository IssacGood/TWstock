# 📈 台股選股系統

每天自動抓取台股 K 線資料，部署於 GitHub Pages，隨時隨地都能查看。

---

## 功能

| 頁面 | 功能 |
|------|------|
| `index.html` | 條件選股（均線/RSI/MACD/布林通道/成交量），點擊開大圖 |
| `watchlist.html` | 貼上股票代碼，一次顯示多檔 K 線 |

---

## 快速部署到 GitHub Pages

### 步驟 1：建立 repository

1. 在 GitHub 建立一個新的 **public** repository（例如 `twstock`）
2. 把所有檔案推上去：

```bash
git init
git add .
git commit -m "init"
git branch -M main
git remote add origin https://github.com/你的帳號/twstock.git
git push -u origin main
```

### 步驟 2：開啟 GitHub Pages

1. 進入 repo → **Settings** → **Pages**
2. Source 選 **Deploy from a branch**
3. Branch 選 `main`，Folder 選 `/ (root)`
4. 點 **Save**

幾分鐘後就能用 `https://你的帳號.github.io/twstock/` 訪問。

### 步驟 3：確認 GitHub Actions 有寫入權限

1. **Settings** → **Actions** → **General**
2. 往下找 **Workflow permissions**
3. 選 **Read and write permissions** → **Save**

### 步驟 4：手動跑一次取得初始資料

1. 到 **Actions** 頁籤
2. 選 **每日台股資料更新**
3. 點 **Run workflow** → **Run workflow**
4. 等約 2~5 分鐘完成，`data/stocks.json` 就會出現

---

## 自動更新時間

- **平日（週一～週五）台灣時間 18:30** 自動抓取當日收盤資料
- 假日不執行

---

## 自訂股票清單

編輯 `scripts/fetch_data.py` 裡的 `WATCH_LIST`：

```python
WATCH_LIST = [
    "2330.TW",   # 台積電（上市）
    "6669.TWO",  # 緯穎（上櫃）
    # ... 加入你想追蹤的股票
]
```

修改後 push 到 GitHub，下次 Actions 執行就會生效。

---

## 本地測試

```bash
pip install yfinance pandas
python scripts/fetch_data.py     # 先跑一次產生 data/stocks.json
python -m http.server 8080       # 本地 serve
# 打開 http://localhost:8080
```

---

## 檔案結構

```
📁 repo/
├── .github/
│   └── workflows/
│       └── update.yml          # GitHub Actions 自動排程
├── scripts/
│   └── fetch_data.py           # 抓資料 + 計算技術指標
├── data/
│   └── stocks.json             # 自動產生（勿手動編輯）
├── index.html                  # 選股篩選頁面
├── watchlist.html              # 自訂清單頁面
└── README.md
```

---

## 技術指標說明

| 指標 | 說明 |
|------|------|
| MA5 / MA20 / MA60 | 5/20/60 日簡單移動平均線 |
| 黃金交叉 | MA5 由下往上穿越 MA20 |
| 死亡交叉 | MA5 由上往下穿越 MA20 |
| RSI(14) | 14 日相對強弱指標，>70 超買，<30 超賣 |
| MACD | 12/26/9 設定，多頭為 MACD 線 > 訊號線 |
| 布林通道 | 20 日移動平均 ± 2 標準差 |
| 爆量 | 今日成交量 > 20 日均量 × 1.5 |

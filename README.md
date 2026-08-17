# 🛰️ 雲端多功能股票量能慣性雷達控制台

這是一個基於 **FastAPI** 與 **Uvicorn** 打造的輕量化、真·隨用隨開、完全免費的股票自動化掃描系統。透過雲端背景任務技術，實現手機「一鍵戳網址」即刻秒回，並在背景調度四大核心策略，最終將選股報告精準推送到 **Discord** 頻道。

---

## 📂 專案檔案結構 (模組化設計)

```text
我的股票雷達專案/
├── trigger.py                          # 總機：負責網頁端點路由、背景任務分配
├── onepush_breakout.py                 # 大腦1：波動慣性爆發策略 (ATR2.0 + 爆量長紅)
├── onepush_abnormal_volume.py          # 大腦2：當日交易量大於昨天兩倍策略 (量能不平衡)
├── onepush_Volume_Price_Velocity_10d.py # 大腦3：10天短天期量價速度動能策略
├── onepush_Volume_Price_Velocity.py     # 大腦4：長天期量價速度趨勢策略
└── requirements.txt                    # 雲端環境安裝清單 (僅保留 6 行精簡套件，防超載)
```

---

## 🛠️ 雲端後台配置指南 (Render Web Service)

### 1. 核心啟動指令
* **Language**: `Python`
* **Region**: `Singapore` (建議)
* **Build Command**: `pip install -r requirements.txt`
* **Start Command**: `uvicorn 觸發器:app --host 0.0.0.0 --port $PORT`
* **Health Check Path**: `/` (指向空首頁，防止 Render 例行點名誤觸選股策略)

### 2. 進階環境變數 (Environment Variables)
* `DISCORD_WEBHOOK_URL`: 填入您的 Discord Webhook 接收通道長網址。
* `TICKERS`: 填入 193 檔完整的股票代碼字串（以英文逗號隔開，例如：`2330.TW,2317.TW,2454.TW`）。

---

## 📱 日常操作與端點說明

每天中午 **12:30 ~ 13:30** 看盤時，直接用手機或電腦瀏覽器造訪以下對應網址。網頁會在 **0.1秒內秒回** 成功訊息，隨後即可直接關閉網頁。雲端主機會在背景花費約 30 秒下載 `yfinance` 並計算，跑完自動叮咚推送 Discord。



import onepush_breakout

from fastapi import FastAPI, BackgroundTasks
import os
import uvicorn


app = FastAPI()

# ==========================================
# 🎯 調整一：改回安全讀取環境變數 (Render 後台設定)
# ==========================================
# 這樣寫的優點：如果在電腦跑就用你貼的網址，去雲端跑就會自動讀取雲端後台設定！
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "你的Discord網址")

# 這裡也改回雲端讀取名單，後方代表如果沒讀到，本機預設跑這三檔
tickers_env = os.getenv("TICKERS")
if tickers_env:
    tickers = tickers_env.split(",")
else:
    tickers = ["2330.TW", "2454.TW", "2317.TW"]

def run_my_code():
    print("\n🚀 [背景任務] 股票掃描開始執行...")

    onepush_breakout.run_scanner()
    
    print("🎉 [背景任務] 股票掃描與 Discord 發送完畢。")

@app.get("/")
def home():
    return {"status": "正常運作中，請在網址後面加上 /scan 來觸發股票掃描。"}

@app.get("/scan")
def scan(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_my_code)
    return {
        "status": "指令已接收",
        "msg": "掃描程式已在伺服器背景啟動，跑完會直接發送至 Discord，您可以直接關閉網頁了！"
    }

# ==========================================
# 🎯 🎯 調整二：動態適應 Render 的開門暗號 ($PORT)
# ==========================================
if __name__ == "__main__":
    # Render 規定在雲端上必須自動抓取官方給的隨機 $PORT，本機執行則維持預設 8000
    cloud_port = int(os.getenv("PORT", 8000))
    
    # 這裡的 reload 維持 False (預防 Windows 衝突)，host 改為 0.0.0.0 讓外網可以連進來
    uvicorn.run("觸發器:app", host="0.0.0.0", port=cloud_port, reload=False)

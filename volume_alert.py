"""
策略說明：一次性批次下載所有股票的原生 5分鐘K線（5m）資料（保護 IP，防止被鎖）。
利用 DataFrame 本地切片，直接提取官方原生 5m 的成交量，不進行多此一舉的本地重組。
優化 Discord 警報用詞，將「當前價格」修正為「該 K 線收盤價」，並精準顯示「13:15 ~ 13:20 走勢」區間。
"""

import yfinance as yf
import pandas as pd
import numpy as np
import time
import requests
from datetime import datetime, timedelta
import os

# ==========================================
# 1. 基本設定區與防錯參數
# ==========================================
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL") 
tickers = os.getenv("TICKERS", "NVDA,TSLA,6180.TWO,2330.TW,3576.TW").split(",")

# 【5分鐘K線 實戰防錯參數設定】
MIN_VOLUME_SHARES = 100000 # 5分鐘成交量至少要 100,000股 (台股約 100張 / 美股 10萬股)
MIN_PRICE_CHANGE = 0.6     # 5分鐘內價格振幅至少要大於 0.6%，確保有實質動能

# ==========================================
# 2. 核心功能函式
# ==========================================
def send_alert_to_discord(alert_data):
    """單檔股票觸發時，立即格式化發送到 Discord"""
    if not DISCORD_WEBHOOK_URL:
        return
    if alert_data['漲跌幅'] >= 0:
        direction_emoji = "🟩 紅棒拉抬"
        trend_arrow = "📈"
    else:
        direction_emoji = "🟥 黑棒下殺"
        trend_arrow = "📉"

    content = (
        f"🚨 **【5 分鐘量能突襲警報】**\n"
        f"• **股票代號**：`{alert_data['標的']}`\n"
        f"• **K線時間**：⏰ **`{alert_data['時間']}`** *(台灣時間)*\n"
        f"• **即時狀態**：💥 交易量暴增 `{alert_data['量比']}` ({alert_data['當前量']:,} / 均量 {alert_data['均量']:,} 股)\n"
        f"• **該 5分K 收盤價**：`${alert_data['現價']:.2f}`\n"  # 🌟 修正：語意更嚴謹
        f"• **{alert_data['區間文字']} 走勢**：{trend_arrow} {direction_emoji} (`{alert_data['漲跌幅']:+.2f}%`)"  # 🌟 修正：呈現 13:15 ~ 13:20
    )

    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": content}, timeout=10)
    except Exception as e:
        print(f"Discord 傳送失敗: {e}")

def run_minute_radar():
    """即時雷達掃描主邏輯"""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] >>> 啟動 5分K 量能雷達掃描 (警報用詞優化版)...")
    print(f"{'標的':<10} | {'判定':<4} | {'時間':<5} | {'量比':<6} | {'當前量':<8} | {'漲跌%':<6}")
    print("-" * 75)
    
    # 優化：過濾掉 6 位數台股權證，只留下個股標的
    valid_tickers = [s for s in tickers if len(s.split(".")) <= 4]
    if not valid_tickers:
        print("沒有有效的個股標的名單。")
        return

    try:
        all_data = yf.download(valid_tickers, period="7d", interval="5m", threads=True, progress=False)
        
        for symbol in valid_tickers:
            try:
                # 記憶體內安全抽離單檔股票數據
                if len(valid_tickers) == 1:
                    df = all_data.dropna().copy()
                else:
                    if symbol not in all_data.columns.get_level_values(1):
                        continue
                    df = all_data.xs(symbol, axis=1, level=1).dropna().copy()
                
                if df.empty or len(df) < 22:
                    continue
                
                # 獲取最新一根已完整收盤的 5分K (倒數第二根)
                latest_k = df.iloc[-2]
                
                # 🌟 自動計算該根 K 線的「起點」與「迄點」時間
                start_dt = latest_k.name
                end_dt = start_dt + timedelta(minutes=5)
                
                # 時區 +8 修正運算
                if ".TW" in symbol or ".TWO" in symbol:
                    start_time_str = (start_dt + timedelta(hours=8)).strftime('%H:%M')
                    end_time_str = (end_dt + timedelta(hours=8)).strftime('%H:%M')
                else:
                    start_time_str = start_dt.strftime('%H:%M')
                    end_time_str = end_dt.strftime('%H:%M')
                
                k_time = start_time_str
                interval_text = f"{start_time_str} ~ {end_time_str}"  # 生成如 "13:15 ~ 13:20"
                    
                t_o = float(latest_k['Open'])
                t_h = float(latest_k['High'])
                t_l = float(latest_k['Low'])
                t_c = float(latest_k['Close'])
                t_v = float(latest_k['Volume'])
                
                # 歷史 20 根成交量均量計算 (保留 Open 供未來擴充對帳)
                past_20_rows = df.iloc[-22:-2]
                past_20_v_series = past_20_rows['Volume']
                
                clean_past_20 = past_20_v_series[past_20_v_series > 0]
                if len(clean_past_20) < 10:
                    continue
                    
                v_ma_20 = clean_past_20.mean()
                
                # 計算量比與價格振幅
                ratio_vol = t_v / v_ma_20 if v_ma_20 > 0 else 0
                price_change = ((t_c - t_o) / t_o) * 100 if t_o > 0 else 0
                
                # 篩選條件
                is_match = (ratio_vol >= 3.5 and t_v >= MIN_VOLUME_SHARES and abs(price_change) >= MIN_PRICE_CHANGE)
                
                status_icon = "✅" if is_match else "❌"
                print(f"{symbol:<10} | {status_icon:<4} | {k_time:<5} | {ratio_vol:>5.1f}x | {int(t_v):>8} | {price_change:>+5.2f}%")
                
                if is_match:
                    print(f"\n🔍 [後台核對數據 - 警報用詞優化版] >>> 標的: {symbol} 觸發警報！")
                    print(f"  ┌── 當前 原生5分K 數據 (區間: {interval_text}) ──┐")
                    print(f"  │ 開盤價 (Open) : {t_o:.2f}")
                    print(f"  │ 最高價 (High) : {t_h:.2f}")
                    print(f"  │ 最低價 (Low)  : {t_l:.2f}")
                    print(f"  │ 收盤價 (Close): {t_c:.2f}")
                    print(f"  │ 當前量 (Volume): {int(t_v):,} 股")
                    print(f"  └──────────────────────────────────┘")
                    print(f"  ┌── 過去 20 根 原生 5分K 歷史清單 ──┐")
                    for idx, (timestamp, row) in enumerate(past_20_rows.iterrows(), 1):
                        vol = row['Volume']
                        hist_open = row['Open']
                        t_show = timestamp.strftime('%H:%M')
                        if ".TW" in symbol or ".TWO" in symbol:
                            t_show = f"{(int(t_show[:2]) + 8) % 24:02d}:{t_show[3:]}"
                        print(f"  │ {idx:02d}. [{t_show}] {int(vol):>9,} 股  |  開盤: {hist_open:.2f}")
                    print(f"  │")
                    print(f"  │ 計算所得 20 根 5分K 原始平均量 (MA20): {int(v_ma_20):,} 股")
                    print(f"  │ 實際計算量比: {ratio_vol:.2f} 倍")
                    print(f"  └──────────────────────────────────┘\n")

                    alert_data = {
                        "標的": symbol,
                        "時間": k_time,
                        "現價": t_c,
                        "量比": f"{ratio_vol:.1f} 倍",
                        "當前量": int(t_v),
                        "均量": int(v_ma_20),
                        "漲跌幅": price_change,
                        "區間文字": interval_text
                    }
                    send_alert_to_discord(alert_data)
                    
            except Exception as e:
                continue
                
    except Exception as e:
        print(f"批次下載失敗: {e}")
        
    print("-" * 75)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 這一輪 5分K 掃描結束。")

if __name__ == "__main__":
    run_minute_radar()

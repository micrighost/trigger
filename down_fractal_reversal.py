import yfinance as yf
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import os

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL") 
tickers = os.getenv("TICKERS", "NVDA,TSLA,2330.TW,3576.TW,1101.TW,3227.TWO,2889.TW,6488.TWO").split(",")

LOOKBACK_PERIOD = 60       
MAX_BASE_PRICE_GAP_PCT = 1.0  
MIN_FRACT_COUNT = 1        
MONITOR_FRACT_LIMIT = 5    
MIN_SHADOW_PCT = 0.3

def send_alert_to_discord(alert_data):
    if not DISCORD_WEBHOOK_URL: return
    sign = "🟩 紅棒拉抬" if alert_data['漲跌幅'] >= 0 else "🟥 黑棒下殺"
    content = (
        f"🎯 **【5分K 破底翻警報】** `{alert_data['標的']}`\n"
        f"• 時間：⏰ `{alert_data['時間區間']}`\n"
        f"• 撐底：`${alert_data['支撐底價']:.2f}` ({alert_data['分型數量']}個強分型)\n"
        f"• 破底/收盤：`${alert_data['最低摜破']:.2f}` -> `${alert_data['收盤價']:.2f}`\n"
        f"• 走勢：{sign} (`{alert_data['漲跌幅']:+.2f}%` / 影線 `{alert_data['下影線幅度']:.2f}%`)"
    )
    try: requests.post(DISCORD_WEBHOOK_URL, json={"content": content}, timeout=10)
    except Exception as e: print(f"Discord失敗: {e}")

def run_spring_radar():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] >>> 啟動 5分K 破底翻雷達 (修正復活Bug精簡版)...")
    print(f"{'標的':<10} | {'判定':<4} | {'時間區間':<13} | {'強分型':<4} | {'有效撐':<7} | {'最新收':<7}")
    print("-" * 75)
    
    valid_tickers = [s for s in tickers if len(s.split(".")) <= 4]
    if not valid_tickers: return

    try:
        all_data = yf.download(valid_tickers, period="14d", interval="5m", threads=True, progress=False)
        
        for symbol in valid_tickers:
            try:
                if len(valid_tickers) == 1:
                    df = all_data.dropna(subset=['Close', 'Volume']).copy()
                else:
                    if symbol not in all_data.columns.get_level_values(1): continue
                    df = all_data.xs(symbol, axis=1, level=1).dropna(subset=['Close', 'Volume']).copy()
                
                if df.empty or len(df) < (LOOKBACK_PERIOD + 5): continue
                
                latest_k = df.iloc[-2]
                history_df = df.iloc[-(LOOKBACK_PERIOD + 2):-2]
                
                h_list = [{'Time': t, 'Open': r['Open'], 'Low': r['Low'], 'Close': r['Close']} for t, r in history_df.iterrows()]
                all_raw_fracts = []
                for i in range(2, len(h_list) - 2):
                    if (h_list[i]['Low'] < h_list[i-1]['Low'] and h_list[i]['Low'] < h_list[i-2]['Low'] and 
                        h_list[i]['Low'] < h_list[i+1]['Low'] and h_list[i]['Low'] < h_list[i+2]['Low']):
                        all_raw_fracts.append({'time': h_list[i]['Time'], 'low': h_list[i]['Low']})
                
                # 🌟 核心修復：時序單向推進，杜絕舊分型幽靈般重現
                valid_fracts = []
                for k_line in h_list:
                    # B. 鋼鐵破產：先檢查這一分鐘的 Low，有沒有跌破之前的累積大底！
                    if valid_fracts and k_line['Low'] < min([x['low'] for x in valid_fracts]):
                        valid_fracts = []  # 碰穿大底，當場全數破產！
                    
                    # A. 唯有在「此時此刻」剛好產生的新分型，才允許加進來，絕不回頭撈歷史
                    for raw_f in all_raw_fracts:
                        if raw_f['time'] == k_line['Time']:
                            if not valid_fracts: 
                                valid_fracts.append(raw_f)
                            else:
                                # 密集窗口檢查
                                min_e = min([x['low'] for x in valid_fracts])
                                if abs(((raw_f['low'] - min_e) / min_e) * 100) <= MAX_BASE_PRICE_GAP_PCT:
                                    valid_fracts.append(raw_f)
                
                if len(valid_fracts) < MIN_FRACT_COUNT:
                    print(f"{symbol:<10} | ❌    | ---- ~ ---- | {len(valid_fracts):^6} | {'--':^7} | {latest_k['Close']:>7.2f}")
                    continue
                
                all_lows = [x['low'] for x in valid_fracts]
                base_support = np.mean(all_lows)
                abs_bottom = np.min(all_lows)
                
                t_o, t_l, t_c = float(latest_k['Open']), float(latest_k['Low']), float(latest_k['Close'])
                shadow_pct = ((min(t_o, t_c) - t_l) / t_l) * 100 if t_l > 0 else 0

                is_spring_match = (t_l < abs_bottom) and (t_c >= base_support) and (shadow_pct >= MIN_SHADOW_PCT)
                
                is_tw = ".TW" in symbol or ".TWO" in symbol
                s_str = (latest_k.name + timedelta(hours=8 if is_tw else 0)).strftime('%H:%M')
                e_str = (latest_k.name + timedelta(minutes=5) + timedelta(hours=8 if is_tw else 0)).strftime('%H:%M')
                interval_text = f"{s_str} ~ {e_str}"
                
                print(f"{symbol:<10} | {'✅' if is_spring_match else '❌':<4} | {interval_text:<13} | {len(valid_fracts):^6} | {base_support:>7.2f} | {t_c:>7.2f}")
                
                if is_spring_match or len(valid_fracts) >= MONITOR_FRACT_LIMIT:
                    mode = "【訊號觸發】" if is_spring_match else "【大底追蹤】"
                    print(f"\n🔥 {mode} >>> 標的: {symbol}")
                    print(f"  最新5分K: 開盤 {t_o:.2f} | 最低 {t_l:.2f} | 收盤 {t_c:.2f} | 影線 {shadow_pct:.2f}%")
                    print(f"  有效大底: 均撐 {base_support:.2f} | 絕對底 {abs_bottom:.2f}")
                    print(f"  ── 存活未破產強分型清單 (共 {len(valid_fracts)} 個) ──")
                    for idx, item in enumerate(valid_fracts, 1):
                        f_t = (item['time'] + timedelta(hours=8 if is_tw else 0)).strftime('%m/%d %H:%M')
                        print(f"  │ [{idx:02d}] ⏰ {f_t}  |  📉 最低: {item['low']:.2f}")
                    print("")
                    
                    if is_spring_match:
                        send_alert_to_discord({
                            "標的": symbol, "時間區間": interval_text, "支撐底價": base_support,
                            "分型數量": len(valid_fracts), "最低摜破": t_l, "收盤價": t_c,
                            "下影線幅度": shadow_pct, "漲跌幅": ((t_c - t_o) / t_o) * 100
                        })
            except Exception: continue
    except Exception as e: print(f"批次下載失敗: {e}")
    print("-" * 75)

if __name__ == "__main__":
    run_spring_radar()

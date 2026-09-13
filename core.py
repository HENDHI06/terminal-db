def run_scan_accurate(tickers, mode, is_crypto=False):
    tickers = list(set(tickers))
    results = []
    
    if is_crypto:
        if mode == "Santai": min_chg, min_rsi, min_val, vol_m = 0.5, 40, 100_000, 1.0 
        elif mode == "Profesional": min_chg, min_rsi, min_val, vol_m = 1.5, 45, 500_000, 1.2
        else: min_chg, min_rsi, min_val, vol_m = 3.0, 50, 1_000_000, 1.4
    else:
        if mode == "Santai": min_chg, min_rsi, min_val, vol_m = 1.5, 45, 10_000_000, 1.1
        elif mode == "Profesional": min_chg, min_rsi, min_val, vol_m = 2.5, 55, 100_000_000, 1.4
        else: min_chg, min_rsi, min_val, vol_m = 4.0, 60, 500_000_000, 1.8

    hot_news_text = get_hot_news_tickers()
    progress = st.progress(0, text="📡 Memindai Database...")
    
    try: 
        data = yf.download(tickers, period="20d", interval="1d", group_by="ticker", threads=True, progress=False)
    except: 
        progress.empty() # MENGHAPUS LOADING BAR JIKA KONEKSI YAHOO GAGAL
        return pd.DataFrame()

    total = len(tickers)
    for i, t in enumerate(tickers):
        try:
            progress.progress(int((i + 1) / total * 100), text=f"🔍 Analisa {t}")
            df = data[t].copy() if len(tickers) > 1 else data.copy()
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df = df.dropna(subset=['Close', 'Volume']) 
            if df.empty or len(df) < 14: continue

            c_now, c_prev = float(df['Close'].iloc[-1]), float(df['Close'].iloc[-2])
            if math.isnan(c_now) or math.isnan(c_prev) or c_prev == 0: continue

            chg = ((c_now - c_prev) / c_prev) * 100
            val_tr = float(df['Volume'].iloc[-1]) * c_now
            
            delta = df['Close'].diff()
            gain, loss = (delta.where(delta > 0, 0)).rolling(14).mean(), (-delta.where(delta < 0, 0)).rolling(14).mean()
            rsi = 100 - (100 / (1 + (gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] != 0 else 0)))

            high_20 = df['High'].rolling(20).max().iloc[-2] if len(df) >= 20 else c_prev
            vol_avg = df['Volume'].rolling(20).mean().iloc[-1] if len(df) >= 20 else df['Volume'].mean()
            is_breakout = (c_now > high_20) and (df['Volume'].iloc[-1] > vol_avg * vol_m)

            if chg < min_chg or val_tr < min_val: continue

            multiplier = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) / (df['High'] - df['Low'] + 1e-9)
            cmf_series = (multiplier * df['Volume']).rolling(14).sum() / df['Volume'].rolling(14).sum()
            cmf = float(cmf_series.dropna().iloc[-1]) if not cmf_series.dropna().empty else 0
            
            tr = pd.concat([df['High'] - df['Low'], (df['High'] - df['Close'].shift()).abs(), (df['Low'] - df['Close'].shift()).abs()], axis=1).max(axis=1)
            atr_val = float(tr.rolling(14).mean().iloc[-1])
            if math.isnan(atr_val): atr_val = c_now * 0.03
            ideal_e = c_now - (0.4 * atr_val)

            clean_t = t.replace(".JK", "").replace("-USD", "")
            katalis = "🔥 ADA BERITA" if clean_t in hot_news_text and not is_crypto else ("🚀 TRENDING" if is_crypto and chg > 5 else "TIDAK ADA")
            
            vpa_status = "NORMAL (Searah)"
            if float(df['Volume'].iloc[-1]) > (vol_avg * 1.5):
                if chg < 1.0 and chg > -1.0: vpa_status = "⚠️ ANOMALI VPA (Tertahan)"
                elif chg >= 2.0: vpa_status = "🚀 BREAKOUT BESAR"

            results.append({
                "TICKER": clean_t, "LAST": c_now, "CHG%": chg, "VAL(M)": (val_tr / 1_000_000), 
                "BANDAR": "AKUMULASI" if cmf > 0 else "DISTRIBUSI", 
                "VPA_STATUS": vpa_status, "KATALIS": katalis,
                "AI_SCORE": (chg * 0.4) + (rsi * 0.2) + (10 if is_breakout else 0) + (cmf * 20),
                "SCORE_MOM": min(max(rsi, 0), 100), "SCORE_BNDR": min(max((cmf + 0.5) * 100, 0), 100), 
                "SCORE_TRND": 80 if c_now > df['Close'].rolling(20).mean().iloc[-1] else 30, "SCORE_VOL": min(100, (atr_val / c_now) * 1000),
                "ENTRY": ideal_e, "TP 1": ideal_e + (1.5 * atr_val), "TP 2": ideal_e + (2.5 * atr_val), "EXIT/CL": ideal_e - (1.0 * atr_val), "FULL": t
            })
        except: continue
        
    progress.empty() # MENGHAPUS LOADING BAR JIKA BERHASIL
    return pd.DataFrame(results).sort_values(by="AI_SCORE", ascending=False).drop_duplicates(subset=['TICKER']) if results else pd.DataFrame()

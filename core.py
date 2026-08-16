# core.py
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import requests 
import pytz 
import math
import random
import feedparser

# Koneksi Database
conn_gs = st.connection("gsheets", type=GSheetsConnection)

CRYPTO_SET = {
    "BTC", "ETH", "USDT", "BNB", "SOL", "XRP", "DOGE", "ADA", "SHIB", "AVAX", 
    "LINK", "DOT", "MATIC", "UNI", "LTC", "NEAR", "ATOM", "APT", "INJ", "OP", 
    "RNDR", "ARB", "GALA", "FET", "PEPE", "WIF", "FLOKI", "BONK", "CEL", "SUI", 
    "TON", "NOT", "RENDER", "TRX", "XLM", "ETC", "BCH", "FIL", "LDO", "TIA", "SEI"
}

def format_rupiah_bersih(val):
    return f"Rp {val:,.0f}"

def is_crypto_ticker(t):
    clean_t = str(t).strip().upper().replace(".JK", "").replace("-USD", "")
    return ("-" in str(t)) or (clean_t in CRYPTO_SET) or (str(t).upper().endswith("USD"))

def get_yf_ticker(t):
    clean_t = str(t).strip().upper().replace(".JK", "").replace("-USD", "")
    if is_crypto_ticker(t): return f"{clean_t}-USD"
    else: return f"{clean_t}.JK"

def get_visitor_info():
    providers = ['https://ipapi.co/json/', 'https://ipinfo.io/json', 'https://ifconfig.co/json']
    for url in providers:
        try:
            response = requests.get(url, timeout=1.5).json()
            ip = response.get('ip') or response.get('query', 'Unknown')
            city = response.get('city', 'Unknown')
            region = response.get('region', 'Unknown') or response.get('regionName', 'Unknown')
            if ip != 'Unknown': return ip, f"{city}, {region}"
        except: continue
    return "Mobile Node", "Cloud"

def authenticate_user(u, p):
    try:
        df = conn_gs.read(worksheet="users", ttl=0)
        if df.empty: return None
        df['username'] = df['username'].astype(str).str.strip()
        df['password'] = df['password'].astype(str).str.strip()
        user_match = df[(df['username'] == str(u).strip()) & (df['password'] == str(p).strip())]
        if not user_match.empty:
            idx = user_match.index[0]
            role = str(user_match.iloc[0]['role'])
            ip, loc = get_visitor_info()
            tz = pytz.timezone('Asia/Jakarta') 
            now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
            for col in ['last_login', 'ip_address', 'location']:
                if col not in df.columns: df[col] = "" 
                df[col] = df[col].astype(str)
            df.at[idx, 'last_login'] = now
            df.at[idx, 'ip_address'] = ip
            df.at[idx, 'location'] = loc
            conn_gs.update(worksheet="users", data=df)
            return role
        return None
    except Exception: return None

def get_sidebar_log(u):
    df = conn_gs.read(worksheet="users", ttl=60)
    user_data = df[df['username'] == u]
    if not user_data.empty: return user_data.iloc[0]['last_login'], user_data.iloc[0]['ip_address'], user_data.iloc[0]['location']
    return "-", "-", "-"

def add_to_portfolio(u, t, p, l, tp, cl, strategy="Bebas"):
    df = conn_gs.read(worksheet="portfolio", ttl=0)
    next_id = 1
    if not df.empty and 'id' in df.columns:
        valid_ids = pd.to_numeric(df['id'], errors='coerce').dropna()
        if not valid_ids.empty: next_id = int(valid_ids.max()) + 1
    new_row = pd.DataFrame([{
        'id': next_id, 'username': u, 'ticker': t.upper().strip(), 'buy_price': float(p), 
        'lots': float(l), 'tp_price': float(tp), 'cl_price': float(cl), 
        'date': datetime.now(pytz.timezone('Asia/Jakarta')).strftime("%Y-%m-%d"), 'strategy': strategy
    }])
    df = pd.concat([df, new_row], ignore_index=True)
    conn_gs.update(worksheet="portfolio", data=df)

def sell_position(u, row_id, ticker, buy_p, sell_p, total_lots, sold_lots):
    is_cr = is_crypto_ticker(ticker)
    pnl = (sell_p - buy_p) * sold_lots if is_cr else (sell_p - buy_p) * sold_lots * 100
    
    df_port = conn_gs.read(worksheet="portfolio", ttl=0)
    idx = df_port.index[df_port['id'] == row_id].tolist()
    remaining_lots = total_lots - sold_lots
    strat_used = "Bebas"
    if idx:
        if 'strategy' in df_port.columns: strat_used = df_port.at[idx[0], 'strategy']
        if remaining_lots > 0:
            df_port.at[idx[0], 'lots'] = remaining_lots
            msg = f"✅ Penjualan Parsial Berhasil!"
        else:
            df_port = df_port.drop(idx[0]).reset_index(drop=True)
            msg = f"✅ Penjualan Seluruh Berhasil!"
        conn_gs.update(worksheet="portfolio", data=df_port)
    else: msg = "Data portfolio tidak ditemukan!"
    
    df_hist = conn_gs.read(worksheet="history", ttl=0)
    next_hist_id = 1
    if not df_hist.empty and 'id' in df_hist.columns:
        valid_ids = pd.to_numeric(df_hist['id'], errors='coerce').dropna()
        if not valid_ids.empty: next_hist_id = int(valid_ids.max()) + 1
    new_hist = pd.DataFrame([{
        'id': next_hist_id, 'username': u, 'ticker': ticker, 'buy_price': float(buy_p), 
        'sell_price': float(sell_p), 'lots': float(sold_lots), 'pnl': float(pnl), 
        'date': datetime.now(pytz.timezone('Asia/Jakarta')).strftime("%Y-%m-%d"), 'strategy': strat_used
    }])
    df_hist = pd.concat([df_hist, new_hist], ignore_index=True)
    conn_gs.update(worksheet="history", data=df_hist)
    return msg

def get_user_portfolio(u, r):
    df = conn_gs.read(worksheet="portfolio", ttl=0)
    if df.empty or len(df) == 0: return pd.DataFrame()
    df['id'] = pd.to_numeric(df['id'], errors='coerce')
    df['lots'] = pd.to_numeric(df['lots'], errors='coerce')
    df['buy_price'] = pd.to_numeric(df['buy_price'], errors='coerce')
    df = df[df['username'] == u]
    return df.sort_values(by='date', ascending=False)

def get_watchlist(u):
    try:
        df = conn_gs.read(worksheet="watchlist", ttl=0)
        if df.empty: return []
        return df[df['username'] == u]['ticker'].tolist()
    except: return []

def add_watchlist(u, t):
    try:
        df = conn_gs.read(worksheet="watchlist", ttl=0)
        next_id = 1
        if not df.empty and 'id' in df.columns:
            valid_ids = pd.to_numeric(df['id'], errors='coerce').dropna()
            if not valid_ids.empty: next_id = int(valid_ids.max()) + 1
        new_row = pd.DataFrame([{'id': next_id, 'username': u, 'ticker': t.upper().strip()}])
        df = pd.concat([df, new_row], ignore_index=True)
        conn_gs.update(worksheet="watchlist", data=df)
        return True
    except: return False

def remove_watchlist(u, t):
    try:
        df = conn_gs.read(worksheet="watchlist", ttl=0)
        idx = df.index[(df['username'] == u) & (df['ticker'] == t)].tolist()
        if idx:
            df = df.drop(idx[0]).reset_index(drop=True)
            conn_gs.update(worksheet="watchlist", data=df)
            return True
        return False
    except: return False

def add_user_db(u, p, r):
    df = conn_gs.read(worksheet="users", ttl=0)
    if u in df['username'].values: return False
    new_user = pd.DataFrame([{'username': u, 'password': p, 'role': r, 'last_login': '', 'ip_address': '', 'location': ''}])
    df = pd.concat([df, new_user], ignore_index=True)
    conn_gs.update(worksheet="users", data=df)
    return True

def delete_user_db(u):
    if u == 'admin': return False
    df = conn_gs.read(worksheet="users", ttl=0)
    idx = df.index[df['username'] == u].tolist()
    if idx:
        df = df.drop(idx[0]).reset_index(drop=True)
        conn_gs.update(worksheet="users", data=df)
        return True
    return False

def update_password_db(u, new_p):
    df = conn_gs.read(worksheet="users", ttl=0)
    idx = df.index[df['username'] == u].tolist()
    if idx:
        df.at[idx[0], 'password'] = new_p
        conn_gs.update(worksheet="users", data=df)
        return True
    return False

@st.cache_data(ttl=86400)
def get_sector(ticker):
    try: 
        if is_crypto_ticker(ticker): return "Cryptocurrency"
        return yf.Ticker(get_yf_ticker(ticker)).info.get('sector', 'Lainnya')
    except: return "Lainnya"

@st.cache_data(ttl=60) 
def get_ticker_data():
    try:
        data = yf.download(['^JKSE', 'BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'TLKM.JK'], period="7d", interval="1d", progress=False)['Close']
        items = []
        for tk, name in zip(['^JKSE', 'BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'TLKM.JK'], ['IHSG', 'BBCA', 'BBRI', 'BMRI', 'TLKM']):
            try:
                tk_data = data[tk].dropna() 
                if len(tk_data) >= 2:
                    c_now = float(tk_data.iloc[-1])
                    c_prev = float(tk_data.iloc[-2])
                    pct = (c_now - c_prev)/c_prev*100
                    color = "#10B981" if pct > 0 else "#EF4444"
                    items.append(f"<span class='ticker-item'>{name} {c_now:,.0f} <span style='color:{color};'>({pct:+.2f}%)</span></span>")
            except: pass
        return " &nbsp;&nbsp; | &nbsp;&nbsp; ".join(items) * 4 
    except: return ""

@st.cache_data(ttl=30)
def get_indodax_tickers():
    try: return requests.get("https://indodax.com/api/tickers", timeout=5).json().get('tickers', {})
    except: return {}

@st.cache_data(ttl=15)
def get_indodax_depth(pair="btcidr"):
    try: return requests.get(f"https://indodax.com/api/depth/{pair}", timeout=5).json()
    except: return {}

@st.cache_data(ttl=15)
def get_indodax_trades(pair="btcidr"):
    try: return requests.get(f"https://indodax.com/api/trades/{pair}", timeout=5).json()
    except: return []

@st.cache_data(ttl=3600)
def get_crypto_fng():
    try:
        resp = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5).json()
        val = int(resp['data'][0]['value'])
        status = resp['data'][0]['value_classification']
        return val, status
    except: return 50, "Neutral"

@st.cache_data(ttl=600)
def get_hot_news_tickers():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        feed = feedparser.parse(requests.get("https://news.google.com/rss/search?q=saham+indonesia&hl=id&gl=ID&ceid=ID:id", headers=headers, timeout=5).content)
        text_content = " ".join([entry.title for entry in feed.entries]).upper()
        return text_content
    except: return ""

@st.cache_data(ttl=86400)
def load_tickers():
    try:
        url = "https://raw.githubusercontent.com/datasets-id/idx-stocks/main/data/stock_codes.csv"
        df_idx = pd.read_csv(url)
        tickers = [str(t).strip().upper() + ".JK" for t in df_idx['ticker'].tolist() if len(str(t)) <= 5]
        if len(tickers) > 100: return tickers
    except: pass
    try:
        df = pd.read_excel("daftar_saham.xlsx")
        col = 'Kode' if 'Kode' in df.columns else df.columns[0]
        return [f"{str(t).strip().upper()}.JK" for t in df[col].tolist() if len(str(t)) <= 5]
    except: return []

def fetch_live_prices(ticker_list):
    prices = {}
    yf_map = {t: get_yf_ticker(t) for t in ticker_list}
    yf_tickers = list(set(yf_map.values()))
    
    if yf_tickers:
        try:
            df_dl = yf.download(yf_tickers, period="10d", interval="1d", progress=False, threads=True)
            if 'Close' in df_dl:
                close_data = df_dl['Close']
                for raw_t, yf_t in yf_map.items():
                    try:
                        if isinstance(close_data, pd.DataFrame) and yf_t in close_data.columns:
                            s = close_data[yf_t].dropna()
                            if not s.empty: prices[raw_t] = float(s.iloc[-1])
                        elif isinstance(close_data, pd.Series):
                            s = close_data.dropna()
                            if not s.empty: prices[raw_t] = float(s.iloc[-1])
                    except: pass
        except: pass
        
    for raw_t, yf_t in yf_map.items():
        if raw_t not in prices or pd.isna(prices[raw_t]) or prices[raw_t] == 0:
            try:
                tk_obj = yf.Ticker(yf_t)
                p = tk_obj.fast_info.get('lastPrice')
                if p and not math.isnan(p) and p > 0:
                    prices[raw_t] = float(p)
                else:
                    hist = tk_obj.history(period="5d")
                    if not hist.empty and 'Close' in hist:
                        prices[raw_t] = float(hist['Close'].dropna().iloc[-1])
            except: pass
    return prices

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
    except: return pd.DataFrame()

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
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rsi = 100 - (100 / (1 + (gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] != 0 else 0)))

            high_20 = df['High'].rolling(20).max().iloc[-2] if len(df) >= 20 else c_prev
            vol_avg = df['Volume'].rolling(20).mean().iloc[-1] if len(df) >= 20 else df['Volume'].mean()
            is_breakout = (c_now > high_20) and (df['Volume'].iloc[-1] > vol_avg * vol_m)

            if chg < min_chg or val_tr < min_val: continue

            multiplier = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) / (df['High'] - df['Low'] + 1e-9)
            cmf_series = (multiplier * df['Volume']).rolling(14).sum() / df['Volume'].rolling(14).sum()
            cmf = float(cmf_series.dropna().iloc[-1]) if not cmf_series.dropna().empty else 0
            
            tr1 = df['High'] - df['Low']
            tr2 = (df['High'] - df['Close'].shift()).abs()
            tr3 = (df['Low'] - df['Close'].shift()).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr_val = float(tr.rolling(14).mean().iloc[-1])
                
            if math.isnan(atr_val): atr_val = c_now * 0.03
            ideal_entry = c_now - (0.4 * atr_val)
            ai_score = (chg * 0.4) + (rsi * 0.2) + (10 if is_breakout else 0) + (cmf * 20)

            vpa_status = "NORMAL (Searah)"
            if float(df['Volume'].iloc[-1]) > (vol_avg * 1.5):
                if chg < 1.0 and chg > -1.0: vpa_status = "⚠️ ANOMALI VPA (Tertahan)"
                elif chg >= 2.0: vpa_status = "🚀 BREAKOUT BESAR"
            
            clean_ticker = t.replace(".JK", "").replace("-USD", "")
            katalis = "🔥 ADA BERITA" if clean_ticker in hot_news_text and not is_crypto else ("🚀 TRENDING" if is_crypto and chg > 5 else "TIDAK ADA")
            
            score_mom = min(max(rsi, 0), 100)
            score_bndr = min(max((cmf + 0.5) * 100, 0), 100)
            score_trnd = 80 if c_now > df['Close'].rolling(20).mean().iloc[-1] else 30
            score_vol = min(100, (atr_val / c_now) * 1000)

            results.append({
                "TICKER": clean_ticker, 
                "LAST": c_now, 
                "CHG%": chg, 
                "VAL(M)": (val_tr / 1_000_000), 
                "BANDAR": "AKUMULASI" if cmf > 0 else "DISTRIBUSI",
                "VPA_STATUS": vpa_status, "KATALIS": katalis,
                "AI_SCORE": ai_score,
                "SCORE_MOM": score_mom, "SCORE_BNDR": score_bndr, "SCORE_TRND": score_trnd, "SCORE_VOL": score_vol,
                "ENTRY": ideal_entry, 
                "TP 1": ideal_entry + (1.5 * atr_val), 
                "TP 2": ideal_entry + (2.5 * atr_val), 
                "EXIT/CL": ideal_entry - (1.0 * atr_val), 
                "FULL": t
            })
        except: continue
    progress.empty()
    return pd.DataFrame(results).sort_values(by="AI_SCORE", ascending=False).drop_duplicates(subset=['TICKER']) if results else pd.DataFrame()

def get_trend_signals(ticker_list):
    signals = []
    for ticker in ticker_list:
        try:
            df = yf.download(f"{ticker}", period="6mo", interval="1d", progress=False)
            if df.empty: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df = df.dropna(subset=['Close'])
            if len(df) < 50: continue
            
            df['MA20'] = df['Close'].rolling(20).mean()
            df['MA50'] = df['Close'].rolling(50).mean()
            df['Multiplier'] = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) / (df['High'] - df['Low'] + 1e-9)
            df['CMF_20'] = (df['Multiplier'] * df['Volume']).rolling(20).sum() / df['Volume'].rolling(20).sum()
            df['CMF_20'] = df['CMF_20'].fillna(0)
            
            last_ma20, last_ma50 = float(df['MA20'].iloc[-1]), float(df['MA50'].iloc[-1])
            prev_ma20, prev_ma50 = float(df['MA20'].iloc[-2]), float(df['MA50'].iloc[-2])
            current_price, cmf_val = float(df['Close'].iloc[-1]), float(df['CMF_20'].iloc[-1])
            if math.isnan(current_price) or math.isnan(last_ma20) or math.isnan(last_ma50): continue
            
            if prev_ma20 < prev_ma50 and last_ma20 > last_ma50:
                if cmf_val > 0: status_text, color_code = "GOLDEN CROSS + AKUMULASI", "#16A34A"
                else: status_text, color_code = "GOLDEN CROSS (Hati-hati Distribusi)", "#F59E0B"
                signals.append({"ticker": ticker.replace(".JK", "").replace("-USD", ""), "status": status_text, "price": current_price, "color": color_code})
            elif prev_ma20 > prev_ma50 and last_ma20 < last_ma50:
                if cmf_val < 0: status_text, color_code = "DEAD CROSS + DISTRIBUSI BANDAR", "#DC2626"
                else: status_text, color_code = "DEAD CROSS (Koreksi Normal Wajar)", "#EA580C"
                signals.append({"ticker": ticker.replace(".JK", "").replace("-USD", ""), "status": status_text, "price": current_price, "color": color_code})
        except Exception as e: 
            continue
    return signals

def draw_mobile_cards(df, is_crypto=False):
    prefix = "Rp"
    for _, row in df.iterrows():
        chg, chg_color = row.get('CHG%', 0), "#16A34A" if row.get('CHG%', 0) > 0 else "#DC2626"
        val_last, val_entry = row.get('LAST', 0), row.get('ENTRY', row.get('Entry', row.get('LAST', 0)))
        val_tp1, val_cl, val_m = row.get('TP 1', 0), row.get('EXIT/CL', 0), row.get('VAL(M)', 0)

        fmt_p = f"{prefix} {val_last:,.0f}"
        fmt_e = f"{prefix} {val_entry:,.0f}"
        fmt_tp = f"{prefix} {val_tp1:,.0f}"
        fmt_cl = f"{prefix} {val_cl:,.0f}"

        st.markdown(f"""
        <div class="dash-box" style="border-left: 4px solid {chg_color}; padding: 16px; border-top: 1px solid #E2E8F0 !important;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <b style="font-size: 1.2rem; color: #0F172A;">{row.get('TICKER','-')}</b>
                <span style="color: {chg_color}; font-weight: 700; font-family: 'JetBrains Mono';">{'+' if chg>0 else ''}{chg:.2f}%</span>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 12px; font-size: 0.85rem; color: #64748B;">
                <div>Harga Berjalan: <b style="color:#0F172A;">{fmt_p}</b></div>
                <div>Transaksi Vol: <b style="color:#0F172A;">Rp {val_m:,.1f} M</b></div>
                <div style="color: #2563EB; font-weight: 600;">Antre Beli: {fmt_e}</div>
                <div style="color: #16A34A; font-weight: 600;">Jual Untung: {fmt_tp}</div>
                <div style="color: #DC2626; font-weight: 600; grid-column: span 2; text-align: center; margin-top:5px;">Jual Rugi (Cut Loss): {fmt_cl}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

def style_dataframe(val):
    if type(val) in [int, float] and val > 0: return 'background-color: #D1FAE5; color: #065F46; font-weight:bold;'
    elif type(val) in [int, float] and val < 0: return 'background-color: #FEE2E2; color: #991B1B; font-weight:bold;'
    if isinstance(val, str) and "⚠️" in val: return 'color: #DC2626; font-weight:bold;'
    if isinstance(val, str) and "🔥" in val: return 'background-color: #FEF2F2; color: #DC2626; font-weight:bold;'
    return ''

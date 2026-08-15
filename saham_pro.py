import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import time
from time import mktime
import warnings
import os
import requests 
import pytz 
import math
import random
import feedparser

# =========================================================================
# --- 0. CONFIG & APP SETUP ---
# =========================================================================
warnings.filterwarnings("ignore", category=FutureWarning)
st.set_page_config(
    page_title="IDX & CRYPTO PRO TERMINAL", 
    page_icon="📊", 
    layout="wide",
    initial_sidebar_state="collapsed" 
)

# Koneksi ke Google Sheets (Database)
conn_gs = st.connection("gsheets", type=GSheetsConnection)

# =========================================================================
# --- 1. DATABASE & LOGIC FUNGSI UMUM ---
# =========================================================================
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
    pnl = (sell_p - buy_p) * sold_lots * 100 
    if "-" in ticker or "IDR" in ticker: 
        pnl = (sell_p - buy_p) * sold_lots 
    
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


# =========================================================================
# --- 2. FUNGSI PENARIKAN DATA SAHAM & KRIPTO ---
# =========================================================================
@st.cache_data(ttl=86400)
def get_sector(ticker):
    try: return yf.Ticker(ticker).info.get('sector', 'Lainnya')
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

@st.cache_data(ttl=60)
def get_indodax_tickers():
    try:
        resp = requests.get("https://indodax.com/api/tickers", timeout=5).json()
        return resp.get('tickers', {})
    except: return {}

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

# =========================================================================
# --- 3. MESIN SCANNER UNIVERSAL (SAHAM & KRIPTO) ---
# =========================================================================
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
    prefix = "$" if is_crypto else "Rp"
    for _, row in df.iterrows():
        chg, chg_color = row.get('CHG%', 0), "#16A34A" if row.get('CHG%', 0) > 0 else "#DC2626"
        val_last, val_entry = row.get('LAST', 0), row.get('ENTRY', row.get('Entry', row.get('LAST', 0)))
        val_tp1, val_cl, val_m = row.get('TP 1', 0), row.get('EXIT/CL', 0), row.get('VAL(M)', 0)

        if is_crypto and val_last < 1: 
            fmt_p = f"{prefix} {val_last:.4f}"
            fmt_e, fmt_tp, fmt_cl = f"{prefix} {val_entry:.4f}", f"{prefix} {val_tp1:.4f}", f"{prefix} {val_cl:.4f}"
        else:
            fmt_p = f"{prefix} {val_last:,.2f}" if is_crypto else f"{prefix} {val_last:,.0f}"
            fmt_e, fmt_tp, fmt_cl = f"{prefix} {val_entry:,.2f}", f"{prefix} {val_tp1:,.2f}", f"{prefix} {val_cl:,.2f}"

        st.markdown(f"""
        <div class="dash-box" style="border-left: 4px solid {chg_color}; padding: 16px; border-top: 1px solid #E2E8F0 !important;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <b style="font-size: 1.2rem; color: #0F172A;">{row.get('TICKER','-')}</b>
                <span style="color: {chg_color}; font-weight: 700; font-family: 'JetBrains Mono';">{'+' if chg>0 else ''}{chg:.2f}%</span>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 12px; font-size: 0.85rem; color: #64748B;">
                <div>Harga Berjalan: <b style="color:#0F172A;">{fmt_p}</b></div>
                <div>Transaksi Vol: <b style="color:#0F172A;">{val_m:,.1f} M</b></div>
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

# =========================================================================
# --- 4. TEMA TERANG (CLEAN WHITE) & CSS EFEK LENGKAP ---
# =========================================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');

/* --- CUSTOM SCROLLBAR --- */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: #94A3B8; }

/* --- ANIMASI FADE-IN (SMOOTH LOAD) --- */
@keyframes fadeInUp { 0% { opacity: 0; transform: translateY(15px); } 100% { opacity: 1; transform: translateY(0); } }
.dash-box, div[data-testid="stMetric"], div[data-testid="stForm"], div[data-testid="stExpander"], .stDataFrame { animation: fadeInUp 0.6s ease-out forwards; }

/* --- LATAR BELAKANG & TEKS DASAR --- */
.stApp { background-color: #F8FAFC !important; color: #0F172A !important; font-family: 'Inter', sans-serif; }
header {background: transparent !important;}
[data-testid="stHeaderActionElements"], .stDeployButton, #MainMenu { display: none !important; }

/* PAKSA SEMUA TEKS JADI GELAP */
p, span, label, li, div.stMarkdown, .stText { color: #1E293B; }

/* --- HEADING & EFEK GRADASI --- */
h1, h2, h3, h4, h5, h6 { font-family: 'Inter', sans-serif !important; font-weight: 700 !important; color: #0F172A !important; letter-spacing: -0.5px; }
.gradient-text { background: linear-gradient(90deg, #2563EB, #10B981); -webkit-background-clip: text; -webkit-text-fill-color: transparent; display: inline-block; }
.stCaptionContainer p, [data-testid="stCaptionContainer"] p { color: #64748B !important; }

/* --- EFEK 1: RUNNING TICKER TAPE --- */
.ticker-wrap {
    position: sticky; top: 0; z-index: 9999; width: 100%; overflow: hidden; 
    background-color: rgba(15, 23, 42, 0.95); backdrop-filter: blur(10px); 
    color: #FFFFFF !important; padding: 10px 0; border-radius: 8px; margin-bottom: 20px; white-space: nowrap; box-shadow: 0 4px 10px rgba(0, 0, 0, 0.15);
}
.ticker { display: inline-block; white-space: nowrap; padding-right: 100%; box-sizing: content-box; animation: ticker 40s linear infinite; }
.ticker:hover { animation-play-state: paused; }
.ticker-item { display: inline-block; padding: 0 20px; font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; font-weight: 600; color: #F8FAFC; }
@keyframes ticker { 0% { transform: translate3d(0, 0, 0); } 100% { transform: translate3d(-50%, 0, 0); } }

/* --- EFEK 2: PULSING DOT ONLINE --- */
.pulsing-dot {
    display: inline-block; width: 10px; height: 10px; border-radius: 50%; background-color: #10B981; margin-right: 5px;
    box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); animation: pulse-dot 1.5s infinite;
}
@keyframes pulse-dot { 0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); } 70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); } 100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); } }

/* --- EFEK 3: PILL BADGES --- */
.badge-green { background-color: #D1FAE5; color: #065F46; padding: 4px 12px; border-radius: 9999px; font-size: 0.8rem; font-weight: 700; display: inline-block;}
.badge-red { background-color: #FEE2E2; color: #991B1B; padding: 4px 12px; border-radius: 9999px; font-size: 0.8rem; font-weight: 700; display: inline-block;}
.badge-blue { background-color: #DBEAFE; color: #1E40AF; padding: 4px 12px; border-radius: 9999px; font-size: 0.8rem; font-weight: 700; display: inline-block;}
.badge-gray { background-color: #F1F5F9; color: #475569; padding: 4px 12px; border-radius: 9999px; font-size: 0.8rem; font-weight: 700; display: inline-block;}

/* --- EFEK 4: TAMPILAN TAB iOS --- */
.stTabs [data-baseweb="tab-list"] { background-color: #E2E8F0 !important; border-radius: 12px; padding: 4px; gap: 4px; border-bottom: none !important; }
.stTabs [data-baseweb="tab"] { background-color: transparent !important; border-radius: 8px !important; padding: 8px 16px !important; border: none !important; margin: 0 !important; }
.stTabs [data-baseweb="tab"] p { color: #64748B !important; transition: all 0.3s ease; font-weight: 600 !important; }
.stTabs [aria-selected="true"] { background-color: #FFFFFF !important; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.stTabs [aria-selected="true"] p { color: #2563EB !important; font-weight: 800 !important; }
.stTabs [data-baseweb="tab-highlight"] { display: none !important; }

/* --- EFEK 5: SIDEBAR MENU GLASSMORPHISM --- */
section[data-testid="stSidebar"], [data-testid="stSidebarContent"] { background-color: rgba(255, 255, 255, 0.95) !important; backdrop-filter: blur(12px) !important; border-right: 1px solid #E2E8F0 !important; }
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label { background: transparent !important; border: none !important; border-radius: 8px !important; padding: 10px 14px !important; margin-bottom: 4px !important; }
section[data-testid="stSidebar"] .stRadio p, section[data-testid="stSidebar"] .stRadio span, section[data-testid="stSidebar"] .stRadio label { font-family: 'Inter', sans-serif !important; font-size: 0.95rem !important; color: #334155 !important; font-weight: 600 !important; }
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] [aria-checked="true"] { background-color: #F8FAFC !important; border: 1px solid #E2E8F0 !important; border-left: 4px solid #2563EB !important; }
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] [aria-checked="true"] p, section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] [aria-checked="true"] span { color: #2563EB !important; font-weight: 800 !important; }

/* --- EFEK 6: KOTAK GLOWING HOVER & NEUMORPHISM --- */
div[data-testid="stForm"], div[data-testid="stExpander"], div[data-testid="stMetric"], .dash-box {
    background-color: #FFFFFF !important; border: 1px solid #E2E8F0 !important; border-radius: 12px; padding: 16px !important; margin-bottom: 16px !important; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03); transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.25s cubic-bezier(0.4, 0, 0.2, 1); 
}
div[data-testid="stForm"]:hover, div[data-testid="stMetric"]:hover, .dash-box:hover {
    transform: translateY(-4px); box-shadow: 0 12px 20px -5px rgba(37, 99, 235, 0.15), 0 8px 10px -6px rgba(37, 99, 235, 0.1) !important; border-color: #BFDBFE !important; 
}
.dash-box { border-top: 1px solid #E2E8F0 !important; }

/* --- EFEK 7: INPUT NEUMORPHISM (INNER SHADOW 3D) --- */
div[data-testid="stForm"] label p, .stTextInput label p, .stNumberInput label p, .stSelectbox label p { color: #2563EB !important; font-size: 0.85rem !important; font-weight: 600 !important; }
input, select, textarea { background-color: #F8FAFC !important; border: 1px solid #CBD5E1 !important; color: #0F172A !important; font-family: 'JetBrains Mono', monospace !important; border-radius: 8px !important; height: 44px !important; font-size: 15px !important; font-weight: 600 !important; box-shadow: inset 0px 2px 4px rgba(0,0,0,0.06) !important; transition: border-color 0.2s ease, box-shadow 0.2s ease; }
input:focus, select:focus { border-color: #38BDF8 !important; box-shadow: inset 0px 2px 4px rgba(0,0,0,0.06), 0 0 0 3px rgba(56, 189, 248, 0.2) !important; }
[data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace !important; font-size: 1.8rem !important; color: #0F172A !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"] * { color: #64748B !important; font-weight: 600 !important; font-size: 0.85rem !important; }
.streamlit-expanderHeader * { color: #0F172A !important; font-weight: 600 !important; }

/* --- EFEK 8: SHIMMER SWEEP PADA TOMBOL --- */
.stButton>button { background-color: #2563EB !important; border: none !important; border-radius: 8px !important; min-height: 44px; width: 100%; margin-top: 5px; margin-bottom: 5px; transition: background-color 0.2s ease, transform 0.1s ease; position: relative; overflow: hidden; }
.stButton>button p, .stButton>button span, .stButton>button div { color: #FFFFFF !important; font-family: 'Inter', sans-serif !important; font-weight: 600 !important; font-size: 0.9rem !important; position: relative; z-index: 2; }
.stButton>button:hover { background-color: #1D4ED8 !important; transform: scale(1.02); }
.stButton>button::after { content: ""; position: absolute; top: 0; left: -100%; width: 50%; height: 100%; background: linear-gradient(to right, rgba(255,255,255,0) 0%, rgba(255,255,255,0.2) 50%, rgba(255,255,255,0) 100%); transform: skewX(-20deg); animation: shimmer 3s infinite; z-index: 1; }
@keyframes shimmer { 100% { left: 200%; } }

/* Warna Custom Teks Utility */
.text-green { color: #16A34A !important; } .text-red { color: #DC2626 !important; } .text-blue { color: #2563EB !important; } .text-muted { color: #64748B !important; font-size: 13px; }
</style>
""", unsafe_allow_html=True)

# =========================================================================
# --- 5. LOGIN CONTROL ---
# =========================================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.role = None

if not st.session_state.logged_in:
    _, col2, _ = st.columns([1,1.5,1])
    with col2:
        st.markdown("<div style='text-align:center; padding:50px 0;'><h1 class='gradient-text'>IDX PRO TERMINAL</h1><p class='text-muted' style='letter-spacing:2px; margin-top:5px;'>INSTITUTIONAL QUANT SUITE</p></div>", unsafe_allow_html=True)
        with st.form("login_form"):
            u = st.text_input("User ID").strip()
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Masuk Sistem", width="stretch"):
                with st.spinner("🔑 Memeriksa kredensial..."):
                    role = authenticate_user(u, p)
                    if role:
                        st.session_state.logged_in = True
                        st.session_state.user = u
                        st.session_state.role = role
                        st.rerun()
                    else: st.error("Akses Ditolak. User ID atau Password salah.")
    st.stop()

# =========================================================================
# --- 6. SIDEBAR & ZONA NAVIGASI ---
# =========================================================================
role = st.session_state.role
user_now = st.session_state.user
last_l, ip_l, loc_l = get_sidebar_log(user_now)

st.sidebar.markdown(f"""
    <div style='padding:16px; background-color:rgba(255,255,255,0.7); border-radius:12px; border:1px solid #E2E8F0; margin-bottom:15px; text-align:center;'>
        <h3 style='margin:0; font-size:1.1rem; color:#0F172A;'>{user_now.upper()}</h3>
        <p style='margin:0; font-size:11px; color:#16A34A; font-weight:700; margin-top:4px;'><span class='pulsing-dot'></span> ONLINE | {role.upper()}</p>
        <p style='font-size:10px; color:#64748B; margin:8px 0 0 0;'>IP : {ip_l}</p>
    </div>
    """, unsafe_allow_html=True)

st.sidebar.markdown("<p style='font-size:12px; font-weight:700; color:#64748B; margin-bottom:5px; text-align:center;'>PILIH ZONA MARKET</p>", unsafe_allow_html=True)
zona_market = st.sidebar.selectbox("ZONA", ["🏢 ZONA SAHAM (IDX)", "🪙 ZONA KRIPTO (INDODAX)"], label_visibility="collapsed")
st.sidebar.write("---")

if zona_market == "🏢 ZONA SAHAM (IDX)":
    menu_list = [
        "🖥️ DASHBOARD UTAMA", "🛰️ AUTO SCANNER", "⚡ STRATEGY SCANNER", "🕯️ POLA CANDLE AI",         
        "⭐ WATCHLIST FAVORIT", "🎯 AUTO SUP/RES", "📅 SIKLUS MUSIMAN", "📟 CEK FUNDAMENTAL", 
        "⚔️ ADU SAHAM", "🌐 PETA SEKTOR", "🧮 KALKULATOR TRADING", "💰 PEMBURU DIVIDEN", 
        "🧬 KORELASI SAHAM", "🏛️ JEJAK BANDAR", "📰 BERITA PASAR"
    ]
else:
    menu_list = [
        "🪙 DASBOR INDODAX", "🚀 RADAR ALTCOIN", "🔮 PREDIKSI KRIPTO", 
        "⚔️ ADU KRIPTO", "🌐 PETA KRIPTO", "🧮 KALKULATOR TRADING"
    ]

# MENU OMNI-WALLET BERADA DI KEDUA ZONA
menu_list.append("💼 DOMPET TRADING")
menu_list.append("🔒 KEAMANAN")
if role == "admin": menu_list.append("⚙️ USER MANAGEMENT")

menu = st.sidebar.radio("Navigasi", menu_list, key="side_menu", label_visibility="collapsed")

st.sidebar.write("---")
if st.sidebar.button("🔄 Refresh Data Server", use_container_width=True):
    st.cache_data.clear(); st.rerun()
if st.sidebar.button("Keluar (Logout)", use_container_width=True):
    st.session_state.logged_in = False; st.session_state.user = None; st.session_state.role = None; st.rerun()

ticker_html = get_ticker_data()
if ticker_html and zona_market == "🏢 ZONA SAHAM (IDX)":
    st.markdown(f"<div class='ticker-wrap'><div class='ticker'>{ticker_html}</div></div>", unsafe_allow_html=True)


# =========================================================================
# =========================================================================
# 🪙 MENU KHUSUS ZONA KRIPTO
# =========================================================================
# =========================================================================

if menu == "🪙 DASBOR INDODAX":
    st.markdown(f"<h2 class='gradient-text' style='margin-bottom:5px;'>Live Indodax Command Center</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Bermain Kripto Tanpa Bangkrut:**
        * **Top Coins:** Ini adalah harga *live* Bitcoin dan koin utama lain dalam Rupiah (IDR) dari server Indodax.
        * **Fear & Greed Index:** Grafik speedometer ini adalah radar psikologi masa kripto global. Jika jarum di angka 10-25 (Extreme Fear), market sedang panik parah, ini adalah waktu **EMAS untuk memborong**. Jika jarum di atas 75 (Extreme Greed), orang sedang tamak/FOMO, **SEGERA JUAL** barang Anda sebelum dibanting turun.
        * **Top Volume (Whale Radar):** Tabel ini menunjukkan koin apa yang sedang dipompa Triliunan Rupiah oleh Bandar (Paus Kripto) hari ini di Indodax. Ikuti arus uangnya.
        """)
    st.write("---")
    
    with st.spinner("Menghubungkan ke API Indodax..."):
        indo_tickers = get_indodax_tickers()
        if indo_tickers:
            c1, c2, c3, c4 = st.columns(4)
            try:
                btc = indo_tickers.get('btc_idr', {})
                eth = indo_tickers.get('eth_idr', {})
                usdt = indo_tickers.get('usdt_idr', {})
                bnb = indo_tickers.get('bnb_idr', {})
                
                c1.metric("BITCOIN (BTC)", f"Rp {int(btc.get('last', 0)):,.0f}" if btc else "N/A")
                c2.metric("ETHEREUM (ETH)", f"Rp {int(eth.get('last', 0)):,.0f}" if eth else "N/A")
                c3.metric("TETHER (USDT)", f"Rp {int(usdt.get('last', 0)):,.0f}" if usdt else "N/A")
                c4.metric("BINANCE (BNB)", f"Rp {int(bnb.get('last', 0)):,.0f}" if bnb else "N/A")
            except: st.error("Gagal menarik metrik utama.")
            
            st.write("---")
            col_fg, col_vol = st.columns([1, 1.5])
            
            with col_fg:
                st.markdown("<h4 style='text-align:center; color:#2563EB;'>Crypto Fear & Greed Index</h4>", unsafe_allow_html=True)
                fg_val, fg_status = get_crypto_fng()
                if fg_val <= 25: fg_color = "#DC2626"
                elif fg_val <= 45: fg_color = "#F59E0B"
                elif fg_val <= 55: fg_color = "#38BDF8"
                elif fg_val <= 75: fg_color = "#10B981"
                else: fg_color = "#059669"
                
                fig_fg = go.Figure(go.Indicator(
                    mode = "gauge+number", value = fg_val,
                    number = {'font': {'color': fg_color, 'size':40, 'family': 'Inter'}},
                    title = {'text': f"<br><span style='color:{fg_color}; font-size:18px; font-weight:700;'>{fg_status.upper()}</span>", 'font': {'size': 14, 'family': 'Inter'}},
                    gauge = {
                        'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#334155", 'visible': False},
                        'bar': {'color': fg_color, 'thickness': 0.3}, 'bgcolor': "#FFFFFF",
                        'steps': [
                            {'range': [0, 25], 'color': "rgba(239, 68, 68, 0.15)"}, {'range': [25, 45], 'color': "rgba(245, 158, 11, 0.15)"},
                            {'range': [45, 55], 'color': "rgba(56, 189, 248, 0.15)"}, {'range': [55, 75], 'color': "rgba(16, 185, 129, 0.15)"},
                            {'range': [75, 100], 'color': "rgba(5, 150, 105, 0.15)"}],
                    }
                ))
                fig_fg.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_fg, use_container_width=True)
                
            with col_vol:
                st.markdown("<h4 style='text-align:center; color:#2563EB;'>🔥 Top Volume Indodax (24 Jam)</h4>", unsafe_allow_html=True)
                vol_list = []
                for pair, data in indo_tickers.items():
                    if '_idr' in pair:
                        try:
                            coin_name = pair.replace('_idr', '').upper()
                            vol_rp = float(data.get('vol_idr', 0))
                            last_price = float(data.get('last', 0))
                            if vol_rp > 0: vol_list.append({'Koin': coin_name, 'Harga (IDR)': last_price, 'Volume (Rp)': vol_rp})
                        except: pass
                
                if vol_list:
                    df_vol = pd.DataFrame(vol_list).sort_values(by='Volume (Rp)', ascending=False).head(5)
                    for _, row in df_vol.iterrows():
                        st.markdown(f"<div class='dash-box' style='background-color:#F8FAFC; border-left: 4px solid #10B981; padding: 12px;'><b style='font-size:16px; color:#0F172A;'>{row['Koin']}</b> <span style='margin-left:10px; font-weight:600;'>Rp {row['Harga (IDR)']:,.0f}</span> <span class='badge-green' style='float:right;'>Vol: Rp {row['Volume (Rp)']/1e9:,.1f} Miliar</span></div>", unsafe_allow_html=True)
        else: st.warning("Gagal mengambil data Live Indodax. Periksa koneksi internet server.")

elif menu == "🚀 RADAR ALTCOIN":
    st.markdown(f"<h2 class='gradient-text'>Altcoin Pump Radar (VPA AI)</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Mencari Koin yang Sedang di-"Pump" (Goreng):**
        * Kripto bergerak karena sentimen dan aliran uang global. Scanner ini menggunakan likuiditas Dolar (USD) untuk akurasi pelacakan tertinggi.
        * Carilah koin dengan **AI_SCORE** tertinggi.
        * Jika status VPA tertulis **🚀 VALID BREAKOUT**, artinya koin tersebut baru saja menembus atap (*resistance*) dengan volume raksasa. Waktunya Anda masuk mengekor Cukong!
        * Beli koin di area harga **ENTRY ($)** untuk mendapatkan titik aman, dan segera Take Profit di angka yang disarankan.
        """)
        
    c1, c2 = st.columns([2, 1])
    with c1: mode_scan = st.radio("SENSITIVITAS:", ["Santai", "Profesional", "Pro"], horizontal=True)
    with c2: 
        st.write("##")
        btn_scan = st.button("Mulai Scan Altcoin", use_container_width=True)

    if btn_scan:
        top_crypto = ["BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD", "DOGE-USD", "ADA-USD", "SHIB-USD", "AVAX-USD", "LINK-USD", "DOT-USD", "MATIC-USD", "UNI-USD", "LTC-USD", "NEAR-USD", "ATOM-USD", "APT-USD", "INJ-USD", "OP-USD", "RNDR-USD", "ARB-USD", "GALA-USD", "FET-USD", "PEPE-USD", "WIF-USD", "FLOKI-USD", "BONK-USD"]
        res = run_scan_accurate(top_crypto, mode_scan, is_crypto=True)
        if not res.empty:
            st.session_state.res_crypto = res
            st.rerun()
        else: st.warning("Scan selesai: Belum ada koin yang mengalami anomali volume hari ini. Coba turunkan sensitivitas ke 'Santai'.")

    if 'res_crypto' in st.session_state and st.session_state.res_crypto is not None and not st.session_state.res_crypto.empty:
        df = st.session_state.res_crypto
        st.info(f"💡 **Hasil:** Ditemukan **{len(df)} Koin Kripto** yang sedang diakumulasi paus global.")

        tab1, tab3 = st.tabs(["📱 RINGKASAN SIGNAL", "📊 DATA LENGKAP AI"])
        
        with tab1: draw_mobile_cards(df, is_crypto=True)
            
        with tab3: 
            def highlight_cols(s):
                if s.name == 'CHG%': return ['background-color: #D1FAE5; color: #065F46; font-weight:bold;' if pd.to_numeric(v, errors='coerce') > 0 else 'background-color: #FEE2E2; color: #991B1B; font-weight:bold;' for v in s]
                return ['' for _ in s]
                
            format_mapping = {
                'LAST': '$ {:,.4f}', 'CHG%': '{:.2f}%', 'VAL(M)': '${:,.1f} M', 'AI_SCORE': '{:.1f}',
                'ENTRY': '$ {:,.4f}', 'TP 1': '$ {:,.4f}', 'TP 2': '$ {:,.4f}', 'EXIT/CL': '$ {:,.4f}'
            }
            
            styled_df = df.drop(columns=['FULL', 'SCORE_MOM', 'SCORE_BNDR', 'SCORE_TRND', 'SCORE_VOL'], errors='ignore').style.format(format_mapping).applymap(style_dataframe).apply(highlight_cols)
            st.dataframe(styled_df, use_container_width=True, hide_index=True)

elif menu == "🔮 PREDIKSI KRIPTO":
    st.markdown(f"<h2 class='gradient-text'>Pola AI & Proyeksi Kripto</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Membaca Masa Depan Koin Kripto:**
        * Ketik simbol koin yang ingin Anda cek (contoh: BTC, ETH, DOGE, PEPE). Sistem akan mencarinya di Database Global.
        * **Monte Carlo Simulation:** Karena Kripto sangat fluktuatif, AI akan membuat 100 jalur kemungkinan harga 30 hari ke depan. Lihat garis tebal merah (Rata-rata). Jika menjulang naik, Hold koin Anda.
        """)
        
    tab_candle, tab_monte = st.tabs(["🕯️ DETEKSI POLA CANDLE", "🔮 PROYEKSI MONTE CARLO (AI)"])
    
    with tab_candle:
        with st.form("f_candle_cr"):
            c1, c2 = st.columns(2)
            tk_candle = c1.text_input("Ketik Simbol Koin (Contoh: BTC, DOGE)", value="BTC").upper().strip()
            tf_candle = c2.selectbox("Pilih Timeframe (Gambaran Besar)", ["Harian (Daily)", "Mingguan (Weekly)", "Bulanan (Monthly)"])
            btn_candle = st.form_submit_button("Deteksi Pola Sekarang", width="stretch")
            
        if btn_candle:
            with st.spinner("Mendeteksi anatomi grafik koin..."):
                try:
                    full_tk = f"{tk_candle}-USD"
                    tf_map = {"Harian (Daily)": "1d", "Mingguan (Weekly)": "1wk", "Bulanan (Monthly)": "1mo"}
                    p_map_c = {"Harian (Daily)": "2mo", "Mingguan (Weekly)": "6mo", "Bulanan (Monthly)": "2y"}
                    
                    df_c_full = yf.download(full_tk, period=p_map_c[tf_candle], interval=tf_map[tf_candle], progress=False).dropna()
                    
                    if not df_c_full.empty and len(df_c_full) >= 14:
                        if isinstance(df_c_full.columns, pd.MultiIndex): df_c_full.columns = df_c_full.columns.get_level_values(0)
                        
                        prev, curr = df_c_full.iloc[-2], df_c_full.iloc[-1]
                        p_o, p_c = float(prev['Open']), float(prev['Close'])
                        c_o, c_c, c_h, c_l = float(curr['Open']), float(curr['Close']), float(curr['High']), float(curr['Low'])
                        
                        body = abs(c_c - c_o)
                        lower_shadow = (c_o - c_l) if c_c >= c_o else (c_c - c_l)
                        upper_shadow = (c_h - c_c) if c_c >= c_o else (c_h - c_o)
                        
                        is_bull_engulfing = (p_c < p_o) and (c_c > c_o) and (c_o <= p_c) and (c_c >= p_o)
                        is_bear_engulfing = (p_c > p_o) and (c_c < c_o) and (c_o >= p_c) and (c_c <= p_o)
                        is_hammer = (lower_shadow >= 2 * body) and (upper_shadow <= body) and body > 0
                        is_shooting_star = (upper_shadow >= 2 * body) and (lower_shadow <= body) and body > 0
                        is_doji = body <= (c_h - c_l) * 0.1
                        
                        pola, warna, badge_c = "TIDAK ADA POLA SPESIFIK", "#64748B", "badge-gray"
                        kesimpulan = "Grafik berjalan normal tanpa adanya pola pembalikan arah yang mencolok. Dianjurkan Wait and See."
                        
                        tr1 = df_c_full['High'] - df_c_full['Low']
                        tr2 = (df_c_full['High'] - df_c_full['Close'].shift()).abs()
                        tr3 = (df_c_full['Low'] - df_c_full['Close'].shift()).abs()
                        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                        atr = float(tr.rolling(14).mean().iloc[-1])
                        if math.isnan(atr): atr = c_c * 0.05
                        
                        target_price = c_c + (2 * atr)
                        stop_loss = c_c - atr
                        
                        if is_bull_engulfing:
                            pola, warna, badge_c = "BULLISH ENGULFING TERDETEKSI", "#16A34A", "badge-green"
                            kesimpulan = "Luar Biasa! Pembeli koin masuk dalam jumlah besar menelan penjualan hari sebelumnya."
                        elif is_hammer:
                            pola, warna, badge_c = "HAMMER (PALU) TERDETEKSI", "#16A34A", "badge-green"
                            kesimpulan = "Bagus! Cukong menahan harga jatuh dan memborong di bawah (Ekor bawah panjang)."
                        elif is_bear_engulfing:
                            pola, warna, badge_c = "BEARISH ENGULFING TERDETEKSI", "#DC2626", "badge-red"
                            kesimpulan = "BAHAYA! Paus (Whales) mulai buang barang besar-besaran."
                        elif is_shooting_star:
                            pola, warna, badge_c = "SHOOTING STAR TERDETEKSI", "#DC2626", "badge-red"
                            kesimpulan = "Hati-hati! Kenaikan harga diguyur oleh penjualan masif di atas."
                        elif is_doji:
                            pola, warna, badge_c = "POLA DOJI TERDETEKSI", "#2563EB", "badge-blue"
                            kesimpulan = "Pasar sedang galau. Kekuatan bull dan bear seimbang."
                            
                        st.markdown(f"<div class='dash-box' style='border-top: 3px solid {warna}; text-align:center;'><br><span class='{badge_c}' style='font-size:1.2rem; padding:8px 16px;'>{pola}</span><p style='font-size:15px; margin-top:15px; color:#0F172A;'>{kesimpulan}</p></div>", unsafe_allow_html=True)
                        
                        if pola != "TIDAK ADA POLA SPESIFIK" and warna == "#16A34A":
                            st.info(f"🎯 **AI Smart Target:** Disarankan Jual Untung di **$ {target_price:,.4f}** dan Cut Loss jika harga turun ke **$ {stop_loss:,.4f}**.")
                        
                        df_chart = df_c_full.tail(20)
                        fig = go.Figure(data=[go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'], name='Candle', increasing_line_color='#16A34A', decreasing_line_color='#DC2626')])
                        
                        if pola != "TIDAK ADA POLA SPESIFIK" and warna == "#16A34A":
                            fig.add_hline(y=target_price, line_dash="dash", line_color="#16A34A", annotation_text="TARGET (TP)")
                            fig.add_hline(y=stop_loss, line_dash="dash", line_color="#DC2626", annotation_text="STOP LOSS")
                            
                        fig.update_layout(template="plotly_white", height=400, margin=dict(l=0,r=0,t=10,b=0), xaxis_rangeslider_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                        st.plotly_chart(fig, use_container_width=True)
                except: st.error("Data koin tidak ditemukan.")

    with tab_monte:
        with st.form("f_mc_cr"):
            tk_mc = st.text_input("Ketik Simbol Koin (Contoh: BTC, PEPE)", value="BTC").upper().strip()
            btn_mc = st.form_submit_button("Mulai Simulasi Proyeksi Kripto", width="stretch")
            
        if btn_mc:
            with st.spinner("Menghitung 100 skenario masa depan koin..."):
                try:
                    df_mc = yf.download(f"{tk_mc}-USD", period="1y", interval="1d", progress=False)['Close'].dropna()
                    if len(df_mc) > 50:
                        returns = df_mc.pct_change().dropna()
                        mu = returns.mean()
                        vol = returns.std()
                        
                        last_price = float(df_mc.iloc[-1])
                        days_to_simulate = 30
                        simulations = 100
                        
                        paths = []
                        for i in range(simulations):
                            path = [last_price]
                            for j in range(days_to_simulate):
                                shock = random.gauss(0, 1)
                                price = path[-1] * math.exp(mu - 0.5 * vol**2 + vol * shock)
                                path.append(price)
                            paths.append(path)
                        
                        fig_mc = go.Figure()
                        for p in paths:
                            fig_mc.add_trace(go.Scatter(y=p, mode='lines', line=dict(color='rgba(37, 99, 235, 0.1)', width=1), showlegend=False))
                            
                        avg_path = np.mean(paths, axis=0)
                        fig_mc.add_trace(go.Scatter(y=avg_path, mode='lines', line=dict(color='#DC2626', width=3), name='Rata-Rata Proyeksi'))
                        
                        fig_mc.update_layout(title=f"Proyeksi Harga {tk_mc} (30 Hari ke Depan)", template="plotly_white", height=400, margin=dict(l=0,r=0,t=40,b=0))
                        st.plotly_chart(fig_mc, use_container_width=True)
                        
                        final_prices = [p[-1] for p in paths]
                        prob_up = sum([1 for p in final_prices if p > last_price]) / simulations * 100
                        st.info(f"💡 **Kesimpulan AI Kripto:** Berdasarkan perhitungan matematika probabilitas acak, ada **{prob_up:.0f}%** peluang harga koin {tk_mc} 30 hari lagi akan lebih tinggi dari harga saat ini ($ {last_price:,.4f}).")
                    else: st.warning("Data koin terlalu sedikit untuk disimulasikan.")
                except Exception as e: st.error("Gagal melakukan simulasi kuantitatif kripto.")

elif menu == "⚔️ ADU KRIPTO":
    st.markdown(f"<h2 class='gradient-text'>Adu Kekuatan Koin (Head-to-Head)</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Mencari Pemenang Duel Koin:**
        * Masukkan dua simbol koin (misal: BTC vs ETH).
        * Perhatikan baris **Tingkat Kenaikan (1 Bulan)**. Koin mana yang naiknya lebih cepat dan stabil?
        * Jika momentum harga koin A sedang hijau/meroket dan koin B memerah, ikut beli koin A.
        """)
    col_in1, col_in2 = st.columns(2)
    with col_in1: tk1 = st.text_input("Koin Pilihan 1 (Contoh: BTC)", value="BTC").upper().strip()
    with col_in2: tk2 = st.text_input("Koin Pilihan 2 (Contoh: ETH)", value="ETH").upper().strip()

    if st.button("Bandingkan Koin", width="stretch"):
        with st.spinner("Membandingkan performa pasar..."):
            try:
                df1 = yf.download(f"{tk1}-USD", period="1mo", interval="1d", progress=False)['Close']
                df2 = yf.download(f"{tk2}-USD", period="1mo", interval="1d", progress=False)['Close']
                
                c_now1, c_prev1 = float(df1.iloc[-1]), float(df1.iloc[0])
                c_now2, c_prev2 = float(df2.iloc[-1]), float(df2.iloc[0])
                chg1 = ((c_now1 - c_prev1) / c_prev1) * 100
                chg2 = ((c_now2 - c_prev2) / c_prev2) * 100

                st.markdown(f"<h2 style='text-align:center; color:#2563EB;'>{tk1} <span style='color:#DC2626;'>VS</span> {tk2}</h2>", unsafe_allow_html=True)
                df_compare = pd.DataFrame({
                    "METRIK ANALISIS": ["Harga Pasar (USD)", "Perubahan Harga (1 Bulan)", "Status Bulan Ini"],
                    tk1: [f"$ {c_now1:,.4f}", f"{chg1:+.2f}%", "🚀 Melesat" if chg1 > 0 else "📉 Koreksi"],
                    tk2: [f"$ {c_now2:,.4f}", f"{chg2:+.2f}%", "🚀 Melesat" if chg2 > 0 else "📉 Koreksi"]
                })
                st.table(df_compare.set_index("METRIK ANALISIS"))
            except: st.error("Simbol koin tidak valid atau gagal terhubung ke satelit data.")

elif menu == "🌐 PETA KRIPTO":
    st.markdown(f"<h2 class='gradient-text'>Peta Dominasi Altcoin</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Membaca Radar Uang Global:**
        * Menunjukkan performa koin kripto utama selama 5 hari terakhir.
        * Koin dengan batang tertinggi (hijau pekat) berarti sedang menerima aliran suntikan dana Paus (Whales) dari seluruh dunia.
        * Anda bisa menumpang (*riding the wave*) pada koin-koin yang baru mulai merangkak naik.
        """)
        
    if st.button("Pantau Pergerakan Kripto Terkini", use_container_width=True):
        with st.spinner("Memetakan arus Dolar..."):
            coin_data = []
            coins = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "PEPE", "SHIB", "AVAX"]
            all_tickers = [f"{c}-USD" for c in coins]
            try:
                data = yf.download(all_tickers, period="5d", interval="1d", progress=False)['Close'].dropna()
                for c, t in zip(coins, all_tickers):
                    try:
                        c_now, c_prev = float(data[t].iloc[-1]), float(data[t].iloc[-2])
                        sec_changes = ((c_now - c_prev) / c_prev) * 100
                        coin_data.append({"Koin": c, "Perubahan (%)": round(sec_changes, 2)})
                    except: pass
            except: pass
            
            if coin_data:
                df_sec = pd.DataFrame(coin_data).sort_values(by="Perubahan (%)", ascending=False)
                fig_sec = px.bar(df_sec, x="Koin", y="Perubahan (%)", color="Perubahan (%)", color_continuous_scale=["#EF4444", "#1E293B", "#10B981"])
                fig_sec.update_layout(template="plotly_white", height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_sec, use_container_width=True)

# =========================================================================
# =========================================================================
# 🏢 MENU KHUSUS ZONA SAHAM (IDX)
# =========================================================================
# =========================================================================

elif menu == "🖥️ DASHBOARD UTAMA":
    st.markdown(f"<h2 class='gradient-text' style='margin-bottom:5px;'>Ringkasan Pasar & Portofolio</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Membaca Dashboard Seperti Profesional:**
        * **IHSG (Indeks Harga Saham Gabungan):** Ini adalah rapor bursa kita. Jika statusnya `BULLISH 🚀`, artinya aman untuk membeli saham. Jika `BEARISH ⚠️`, lebih baik simpan uang tunai (*cash*).
        * **Market Breadth:** Lihat angka `Naik` vs `Turun`. Walaupun IHSG hijau, tapi kalau saham yang 'Turun' lebih banyak, artinya kenaikan indeks hanya tipuan dari beberapa saham raksasa saja.
        * **Arus Dana Asing (Net Buy/Sell):** Uang asing adalah bensin bursa kita. Selalu trading searah dengan asing. Jika status `NET BUY`, ikutlah masuk pasar.
        * **Fear & Greed:** Beli saat pasar ketakutan (Jarum di area merah / Extreme Fear), dan juallah barang Anda saat pasar sedang serakah (Jarum di area hijau / Extreme Greed).
        * **Top Traded Value:** Ini adalah tempat uang besar (Triliunan) sedang berpesta hari ini. Sangat disarankan *trading* di 3 saham ini karena sangat liquid (gampang masuk dan keluar).
        """)
    st.write("---")
    
    proxy_market = ["BBCA.JK","BBRI.JK","BMRI.JK","BBNI.JK","ASII.JK","TLKM.JK","AMRT.JK","ADRO.JK",
                    "PTBA.JK","ITMG.JK","UNVR.JK","ICBP.JK","INDF.JK","KLBF.JK","PGAS.JK","GOTO.JK",
                    "ARTO.JK","BRPT.JK","MDKA.JK","ANTM.JK","INCO.JK","CPIN.JK","AKRA.JK","MEDC.JK",
                    "HRUM.JK","EXCL.JK","ISAT.JK","INKP.JK","TKIM.JK","PGEO.JK"]
    big_banks = ["BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "TLKM.JK", "ASII.JK"]

    up, down, flat = 0, 0, 0
    try:
        ihsg_data = yf.download("^JKSE", period="10d", interval="1d", progress=False)['Close'].dropna()
        if not ihsg_data.empty and len(ihsg_data) >= 2:
            ihsg_last, ihsg_prev = float(ihsg_data.iloc[-1].item() if isinstance(ihsg_data.iloc[-1], pd.Series) else ihsg_data.iloc[-1]), float(ihsg_data.iloc[-2].item() if isinstance(ihsg_data.iloc[-2], pd.Series) else ihsg_data.iloc[-2])
            ihsg_pct = ((ihsg_last - ihsg_prev) / ihsg_prev) * 100
            ihsg_color = "#16A34A" if ihsg_pct > 0 else "#DC2626"
            ihsg_status = "BULLISH 🚀" if ihsg_pct > 0.5 else ("BEARISH ⚠️" if ihsg_pct < -0.5 else "SIDEWAYS 💤")
            badge_ihsg = "badge-green" if ihsg_pct > 0 else "badge-red" 
            
            st.markdown(f"""<div class='dash-box' style='border-left: 4px solid {ihsg_color}; border-top: 1px solid #E2E8F0 !important; padding: 20px; margin-bottom: 0px !important;'>
                <p class='text-muted' style='margin:0; font-weight:600;'>IHSG (HARGA SAHAM GABUNGAN)</p>
                <h2 style='margin:5px 0; color:{ihsg_color}; font-family:"JetBrains Mono";'>{ihsg_last:,.2f} <span style='font-size:1rem;'>({'+' if ihsg_pct>0 else ''}{ihsg_pct:.2f}%)</span></h2>
                <p style='margin:0; font-size:14px; color:#0F172A;'>Status Pasar Terakhir: <span class='{badge_ihsg}'>{ihsg_status}</span></p>
            </div>""", unsafe_allow_html=True)
            
            try:
                if len(ihsg_data) >= 7:
                    spark_y = ihsg_data.tail(7).values.flatten()
                    spark_x = ihsg_data.tail(7).index
                    fig_spark = go.Figure(go.Scatter(x=spark_x, y=spark_y, mode='lines', line=dict(color=ihsg_color, width=3)))
                    fig_spark.update_layout(height=60, margin=dict(l=0, r=0, t=0, b=0), xaxis=dict(visible=False), yaxis=dict(visible=False), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False, hovermode=False)
                    st.plotly_chart(fig_spark, use_container_width=True, config={'displayModeBar': False})
            except: pass
    except: st.warning("Sedang memproses sambungan IHSG...")

    with st.spinner("Memindai Kesehatan Pasar..."):
        try:
            br_data_full = yf.download(proxy_market, period="10d", interval="1d", progress=False)
            br_data = br_data_full['Close']
            vol_data_today = br_data_full['Volume']
            
            for tk in proxy_market:
                try:
                    tk_data = br_data[tk].dropna()
                    if len(tk_data) >= 2:
                        c_l, c_p = float(tk_data.iloc[-1]), float(tk_data.iloc[-2])
                        if c_l > c_p: up += 1
                        elif c_l < c_p: down += 1
                        else: flat += 1
                except: pass
            total_valid = up + down + flat
            if total_valid > 0:
                st.markdown(f"""<div class='dash-box' style='padding: 20px; border-top: 1px solid #E2E8F0 !important;'>
                    <p class='text-muted' style='margin:0 0 15px 0; text-align:center; font-weight:600;'>📊 MARKET BREADTH (KESEHATAN PASAR)</p>
                    <div style='display:flex; justify-content:space-around;'>
                        <div style='text-align:center;'><h2 class='text-green' style='margin:0;'>{up}</h2><span class='text-muted'>Naik 📈</span></div>
                        <div style='text-align:center;'><h2 style='margin:0; color:#64748B;'>{flat}</h2><span class='text-muted'>Mandek ➖</span></div>
                        <div style='text-align:center;'><h2 class='text-red' style='margin:0;'>{down}</h2><span class='text-muted'>Turun 📉</span></div>
                    </div>
                </div>""", unsafe_allow_html=True)
        except: pass

    with st.spinner("Melacak Sentimen dan Asing..."):
        try:
            flow_data = yf.download(big_banks, period="1mo", interval="1d", progress=False)
            if isinstance(flow_data.columns, pd.MultiIndex): flow_data.columns = flow_data.columns.get_level_values(0)
            avg_cmfs = []
            for tk in big_banks:
                try:
                    df_f = pd.DataFrame({'High': flow_data['High'][tk], 'Low': flow_data['Low'][tk], 'Close': flow_data['Close'][tk], 'Volume': flow_data['Volume'][tk]}).dropna()
                    if len(df_f) > 20:
                        mult = ((df_f['Close'] - df_f['Low']) - (df_f['High'] - df_f['Close'])) / (df_f['High'] - df_f['Low'] + 1e-9)
                        cmf_20 = (mult * df_f['Volume']).rolling(20).sum() / df_f['Volume'].rolling(20).sum()
                        cmf_20 = cmf_20.dropna()
                        if not cmf_20.empty: avg_cmfs.append(cmf_20.iloc[-1])
                except: pass
            
            net_flow = sum(avg_cmfs) / len(avg_cmfs) if avg_cmfs else 0
            flow_color = "#10B981" if net_flow > 0 else "#EF4444"
            flow_status = "NET BUY (Masuk)" if net_flow > 0.05 else ("NET SELL (Keluar)" if net_flow < -0.05 else "NETRAL")
            badge_flow = "badge-green" if net_flow > 0.05 else ("badge-red" if net_flow < -0.05 else "badge-blue")
            
            st.markdown(f"""<div class='dash-box' style='border-top: 3px solid {flow_color} !important; text-align:center; padding: 20px;'>
                <p class='text-muted' style='margin:0 0 5px 0; font-weight:600;'>🦅 ARUS DANA ASING (BIG CAPS)</p>
                <div style='margin:15px 0;'><span class='{badge_flow}' style='font-size:1.1rem; padding: 8px 16px;'>{flow_status}</span></div>
                <p style='font-size:13px; color:#0F172A;'>Indikator Kekuatan: <b>{net_flow:.2f}</b></p>
            </div>""", unsafe_allow_html=True)
        except: pass
            
        try:
            fg_ratio = up / (up + down + 0.0001) * 100
            fg_value = int(fg_ratio)
            if fg_value <= 30: fg_status, fg_color = "EXTREME FEAR", "#EF4444"
            elif fg_value <= 45: fg_status, fg_color = "FEAR", "#F59E0B"
            elif fg_value <= 55: fg_status, fg_color = "NEUTRAL", "#38BDF8"
            elif fg_value <= 70: fg_status, fg_color = "GREED", "#10B981"
            else: fg_status, fg_color = "EXTREME GREED", "#059669"
            
            fig_fg = go.Figure(go.Indicator(
                mode = "gauge+number", value = fg_value,
                number = {'font': {'color': fg_color, 'size':30, 'family': 'Inter'}},
                title = {'text': f"<br><span style='color:{fg_color}; font-size:16px; font-weight:700;'>{fg_status}</span>", 'font': {'size': 14, 'family': 'Inter'}},
                gauge = {
                    'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#334155", 'visible': False},
                    'bar': {'color': fg_color, 'thickness': 0.3}, 'bgcolor': "#FFFFFF",
                    'steps': [
                        {'range': [0, 30], 'color': "rgba(239, 68, 68, 0.15)"}, {'range': [30, 45], 'color': "rgba(245, 158, 11, 0.15)"},
                        {'range': [45, 55], 'color': "rgba(56, 189, 248, 0.15)"}, {'range': [55, 70], 'color': "rgba(16, 185, 129, 0.15)"},
                        {'range': [70, 100], 'color': "rgba(5, 150, 105, 0.15)"}],
                }
            ))
            fig_fg.update_layout(height=200, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)")
            
            st.markdown("<div class='dash-box' style='padding:15px; border-top: 1px solid #E2E8F0 !important;'><p class='text-muted' style='margin:0 0 0 0; text-align:center; font-weight:600;'>🌡️ FEAR & GREED SENTIMENT</p>", unsafe_allow_html=True)
            st.plotly_chart(fig_fg, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        except: pass

    st.write("---")
    
    c_vol, c_mov = st.columns(2)
    with c_vol:
        st.markdown("<h3 class='text-blue'>🔥 Top Traded Value (Paling Laris)</h3>", unsafe_allow_html=True)
        with st.spinner("Menghitung perputaran uang terbesar..."):
            try:
                val_list = []
                for tk in proxy_market:
                    try:
                        tk_close = float(br_data[tk].dropna().iloc[-1])
                        tk_vol = float(vol_data_today[tk].dropna().iloc[-1])
                        val_tr = tk_close * tk_vol
                        if val_tr > 0: val_list.append({"Ticker": tk.replace(".JK",""), "Value": val_tr})
                    except: pass
                df_val = pd.DataFrame(val_list).sort_values("Value", ascending=False).head(3)
                if not df_val.empty:
                    for _, row in df_val.iterrows():
                        st.markdown(f"<div class='dash-box' style='background-color:#F8FAFC; border-left: 4px solid #10B981; border-top:1px solid #E2E8F0 !important; padding: 14px;'><b style='font-size:16px; color:#0F172A;'>{row['Ticker']}</b> <span class='badge-green' style='float:right;'>Trx: Rp {row['Value']/1e9:,.1f} Miliar 💵</span></div>", unsafe_allow_html=True)
                else: st.info("Data transaksi saham belum tersedia.")
            except: st.info("Sistem radar volume sedang menyesuaikan data.")

    with c_mov:
        st.markdown("<h3 class='text-blue'>📈 Top Movers (Blue Chips)</h3>", unsafe_allow_html=True)
        with st.spinner("Menarik data penggerak..."):
            try:
                mov_list = []
                for tk in proxy_market:
                    try:
                        tk_mov = br_data[tk].dropna()
                        if len(tk_mov) >= 2:
                            c_last, c_prev = float(tk_mov.iloc[-1]), float(tk_mov.iloc[-2])
                            mov_list.append({"Ticker": tk.replace(".JK",""), "Chg": ((c_last-c_prev)/c_prev)*100})
                    except: pass
                df_mov = pd.DataFrame(mov_list).sort_values("Chg", ascending=False)
                if len(df_mov) >= 2:
                    st.success(f"🚀 **Top Gainer:** {df_mov.iloc[0]['Ticker']} (+{df_mov.iloc[0]['Chg']:.2f}%)")
                    st.error(f"⚠️ **Top Loser:** {df_mov.iloc[-1]['Ticker']} ({df_mov.iloc[-1]['Chg']:.2f}%)")
            except: st.info("Data Movers belum tersedia.")


elif menu == "🛰️ AUTO SCANNER":
    st.markdown(f"<h2 class='gradient-text'>Auto Scanner AI (VPA & Radar)</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **1. CARA MEMILIH SAHAM (Cari Bintang Utama):**
        * Fokus pada saham dengan **AI_SCORE** paling tinggi.
        * Pilih yang status Bandar-nya **AKUMULASI** (Bandar sedang kumpul barang).
        * Pilih yang **VPA_STATUS** berstatus "NORMAL" atau "VALID BREAKOUT". Hindari "ANOMALI VPA" karena rawan diguyur bandar.
        * Sangat direkomendasikan memilih saham yang memiliki label **🔥 ADA BERITA** (artinya sedang di-goreng sentimen publik).

        **2. CARA EKSEKUSI TRADING PLAN (Beli & Jual):**
        * **ENTRY (Area Beli Aman):** JANGAN kejar harga pucuk (LAST). Lakukan antre beli (*Buy on Weakness*) di angka **ENTRY** agar Anda dapat harga diskon.
        * **TP 1 & TP 2 (Target Jual Untung):** Segera pasang antrean jual otomatis (Take Profit) di angka ini agar tidak keburu turun lagi.
        * **EXIT/CL (Cut Loss):** PENTING! Jika prediksi salah dan harga malah anjlok menembus angka ini, **SEGERA JUAL RUGI** tanpa mikir. Ini akan menyelamatkan uang Anda dari nyangkut parah.
        """)
        
    if 'results_saham' not in st.session_state: st.session_state.results_saham = None
    tickers = load_tickers()
    
    c1, c2, c3 = st.columns([1.5, 1.5, 1])
    with c1: mode_scan = st.radio("SENSITIVITAS:", ["Santai", "Profesional", "Pro"], horizontal=True)
    with c2: filter_sektor = st.selectbox("Filter Sektor Khusus:", ["Semua Sektor", "Financials", "Energy", "Basic Materials", "Consumer Defensive", "Consumer Cyclical", "Technology", "Healthcare", "Industrials"])
    with c3: 
        st.write("##")
        btn_scan = st.button("Mulai Scan Pasar", use_container_width=True)

    if btn_scan:
        res = run_scan_accurate(tickers, mode_scan, is_crypto=False)
        if not res.empty: 
            if filter_sektor != "Semua Sektor":
                res['SEKTOR'] = res['FULL'].apply(get_sector)
                res = res[res['SEKTOR'] == filter_sektor]
            else:
                res['SEKTOR'] = res['FULL'].apply(get_sector)
            st.session_state.results_saham = res
            st.rerun()
        else: st.warning("Scan selesai: Belum ada saham yang momentumnya cukup kuat di kriteria ini.")

    if st.session_state.results_saham is not None and not st.session_state.results_saham.empty:
        df = st.session_state.results_saham
        st.info(f"💡 **Hasil:** Ditemukan **{len(df)} Saham** yang berhasil lolos radar AI.")

        tab1, tab2, tab3, tab4 = st.tabs(["📱 RINGKASAN", "🗺️ PETA VISUAL (TREEMAP)", "📊 DATA LENGKAP (VPA)", "🕸️ RADAR AI & GRAFIK"])
        
        with tab1: draw_mobile_cards(df)
        
        with tab2:
            st.markdown("<h4 style='color:#2563EB;'>Peta Dominasi Perputaran Uang</h4>", unsafe_allow_html=True)
            st.caption("Semakin besar kotaknya, semakin besar uang yang berputar. Warna Hijau = Naik, Merah = Turun.")
            fig_tree = px.treemap(df, path=[px.Constant("Bursa"), 'SEKTOR', 'TICKER'], values='VAL(M)', color='CHG%', color_continuous_scale=["#DC2626", "#F8FAFC", "#16A34A"], color_continuous_midpoint=0)
            fig_tree.update_layout(template="plotly_white", margin=dict(t=10, l=10, r=10, b=10))
            st.plotly_chart(fig_tree, use_container_width=True)
            
        with tab3: 
            def highlight_cols(s):
                if s.name == 'CHG%': return ['background-color: #D1FAE5; color: #065F46; font-weight:bold;' if pd.to_numeric(v, errors='coerce') > 0 else 'background-color: #FEE2E2; color: #991B1B; font-weight:bold;' for v in s]
                return ['' for _ in s]
                
            format_mapping = {
                'LAST': 'Rp {:,.0f}', 'CHG%': '{:.2f}%', 'VAL(M)': '{:,.1f} M', 'AI_SCORE': '{:.1f}',
                'ENTRY': 'Rp {:,.0f}', 'TP 1': 'Rp {:,.0f}', 'TP 2': 'Rp {:,.0f}', 'EXIT/CL': 'Rp {:,.0f}'
            }
            
            styled_df = df.drop(columns=['FULL', 'SCORE_MOM', 'SCORE_BNDR', 'SCORE_TRND', 'SCORE_VOL'], errors='ignore').style.format(format_mapping).applymap(style_dataframe).apply(highlight_cols)
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            csv = df.drop(columns=['FULL', 'SCORE_MOM', 'SCORE_BNDR', 'SCORE_TRND', 'SCORE_VOL'], errors='ignore').to_csv(index=False).encode('utf-8')
            st.download_button("💾 Download Hasil Scan (CSV)", csv, f"scanner_results_{datetime.now(pytz.timezone('Asia/Jakarta')).strftime('%d%m%Y')}.csv", "text/csv", use_container_width=True)
            
        with tab4:
            c_sel, c_rad = st.columns([1, 2])
            with c_sel:
                sel_t = st.selectbox("Pilih Saham untuk Analisis Mendalam:", df['TICKER'].tolist())
                sel_row = df[df['TICKER'] == sel_t].iloc[0]
                full_t = sel_row['FULL']
                st.markdown(f"<div class='dash-box' style='text-align:center;'><h1 class='text-blue' style='margin:0;'>{sel_t}</h1><p class='badge-blue'>Skor Keseluruhan: {sel_row['AI_SCORE']:.1f}</p></div>", unsafe_allow_html=True)
            
            with c_rad:
                categories = ['Momentum Kenaikan', 'Kekuatan Bandar', 'Tren Menengah', 'Volatilitas Kuat', 'Fundamental Umum']
                fig_radar = go.Figure()
                fig_radar.add_trace(go.Scatterpolar(
                    r=[sel_row['SCORE_MOM'], sel_row['SCORE_BNDR'], sel_row['SCORE_TRND'], sel_row['SCORE_VOL'], 75], 
                    theta=categories, fill='toself', name=sel_t, marker_color='#2563EB'
                ))
                fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), showlegend=False, margin=dict(t=20, b=20, l=20, r=20), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_radar, use_container_width=True)

            c_data = yf.download(full_t, period="6mo", interval="1d", progress=False).dropna()
            if not c_data.empty:
                c_data.columns = [c[0] if isinstance(c, tuple) else c for c in c_data.columns]
                c_data['MA20'] = c_data['Close'].rolling(20).mean()
                c_data['MA50'] = c_data['Close'].rolling(50).mean()
                
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=c_data.index, open=c_data['Open'], high=c_data['High'], low=c_data['Low'], close=c_data['Close'], increasing_line_color='#16A34A', decreasing_line_color='#DC2626', name='Price'), row=1, col=1)
                fig.add_trace(go.Scatter(x=c_data.index, y=c_data['MA20'], line=dict(color='#2563EB', width=1.5), name='MA 20'), row=1, col=1)
                fig.add_trace(go.Scatter(x=c_data.index, y=c_data['MA50'], line=dict(color='#F59E0B', width=1.5), name='MA 50'), row=1, col=1)
                colors = ['#16A34A' if row['Close'] >= row['Open'] else '#DC2626' for index, row in c_data.iterrows()]
                fig.add_trace(go.Bar(x=c_data.index, y=c_data['Volume'], marker_color=colors, name='Volume'), row=2, col=1)
                fig.update_layout(template="plotly_white", height=450, margin=dict(l=0,r=0,t=10,b=0), xaxis_rangeslider_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)


elif menu == "⚡ STRATEGY SCANNER":
    st.markdown(f"<h2 class='gradient-text'>Strategy Scanner (Crossover)</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Menggunakan Sinyal Crossover:**
        * Menu ini mendeteksi perubahan tren utama dengan melihat persilangan Moving Average (MA20 dan MA50).
        * 🟢 **Beli (Entry):** Jika statusnya **GOLDEN CROSS**. Artinya tren harga baru saja berbalik dari turun menjadi naik. Sangat aman untuk di-hold mingguan/bulanan.
        * 🔴 **Jual (Exit):** Jika statusnya **DEAD CROSS**. Artinya tren naik sudah patah dan akan terjun bebas. Segera jual atau hindari membeli saham ini.
        """)
    try:
        df_saham = pd.read_excel("daftar_saham.xlsx")
        watchlist = [t.strip() + ".JK" for t in df_saham['Kode'].dropna().astype(str).tolist()]
    except:
        st.error("Error file Excel."); watchlist = []

    if st.button("Mulai Cari Sinyal", use_container_width=True):
        with st.spinner(f"Menganalisis perpaduan Tren..."):
            results = get_trend_signals(watchlist)
            if results:
                st.success("💡 **Ditemukan!** Cari saham dengan status **Golden Cross (Hijau)** untuk momentum beli tren yang sehat.")
                for res in results:
                    bg_badge = "badge-green" if "Sangat Kuat" in res['status'] or "AKUMULASI" in res['status'] else ("badge-red" if "DISTRIBUSI" in res['status'] else "badge-blue")
                    st.markdown(f"<div class='dash-box' style='border-left: 4px solid {res['color']}; padding: 15px;'><span class='{bg_badge}' style='margin-bottom:8px;'>{res['status']}</span><p style='margin:8px 0 0 0; color:#0F172A;'>Saham: <b style='color:#0F172A; font-size:1.1rem;'>{res['ticker']}</b> | Harga: Rp {res['price']:,.0f}</p></div>", unsafe_allow_html=True)
            else: st.info("Belum ada perpotongan tren yang signifikan hari ini.")


elif menu == "⭐ WATCHLIST FAVORIT":
    st.markdown(f"<h2 class='gradient-text'>Watchlist Pribadi</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Fungsi Laci Saham Pribadi:**
        * Masukkan kode saham andalan Anda di sini (misal: BBCA, AMMN, BREN).
        * Cukup tekan **"Scan Saham Favorit Saya"** setiap malam atau pagi.
        * AI akan memberitahu apakah saham-saham pilihan Anda ini sedang memiliki momentum tarikan bandar hari ini atau malah sedang lesu.
        """)
    my_wl = get_watchlist(user_now)
    c_add, c_del = st.columns(2)
    with c_add:
        new_wl = st.text_input("Tambah Kode Saham").upper()
        if st.button("Simpan Saham", use_container_width=True):
            if new_wl and f"{new_wl}.JK" not in my_wl: 
                add_watchlist(user_now, f"{new_wl}.JK"); st.success("Ditambahkan!"); st.rerun()
    with c_del:
        if my_wl:
            del_wl = st.selectbox("Hapus Daftar", [t.replace(".JK","") for t in my_wl])
            if st.button("Hapus Saham", use_container_width=True):
                remove_watchlist(user_now, f"{del_wl}.JK"); st.warning("Dihapus!"); st.rerun()
                
    st.markdown("---")
    if my_wl:
        if st.button("Scan Saham Favorit Saya", use_container_width=True):
            res_wl = run_scan_accurate(my_wl, "Santai", is_crypto=False)
            if not res_wl.empty: draw_mobile_cards(res_wl)
            else: st.info("Belum ada momentum tarikan pada daftar sahammu.")


elif menu == "🎯 AUTO SUP/RES":
    st.markdown(f"<h2 class='gradient-text'>Auto Support & Resistance</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Titik Pantul Harga (Pivot Strategy):**
        * 🟢 **Beli (ENTRY):** Lakukan pembelian saat "Harga Saat Ini" mendekati atau menyentuh garis **SUPPORT 1** atau **SUPPORT 2**. Ini adalah area lantai di mana harga susah turun lagi.
        * 🔴 **Jual (TAKE PROFIT):** Segera lepas barang (jual) saat harga mendekati **RESISTANCE 1** atau **RESISTANCE 2**. Ini adalah area atap di mana harga biasanya akan membentur dan kembali turun.
        * 🔵 **Titik Pivot:** Ini adalah batas tengah (Garis netral).
        """)
        
    with st.form("f_pivot"):
        tk_pivot = st.text_input("Masukkan Kode Saham", value="BBRI").upper().strip()
        btn_pivot = st.form_submit_button("Analisis Batas Harga", width="stretch")
        
    if btn_pivot:
        with st.spinner("Menghitung kalkulasi Pivot Point..."):
            try:
                full_tk = f"{tk_pivot}.JK" if not tk_pivot.endswith(".JK") else tk_pivot
                df_piv = yf.download(full_tk, period="1mo", interval="1d", progress=False).dropna()
                if not df_piv.empty and len(df_piv) >= 20:
                    if isinstance(df_piv.columns, pd.MultiIndex): df_piv.columns = df_piv.columns.get_level_values(0)
                    
                    recent_high = float(df_piv['High'][-20:].max())
                    recent_low = float(df_piv['Low'][-20:].min())
                    recent_close = float(df_piv['Close'].iloc[-1])
                    
                    pivot = (recent_high + recent_low + recent_close) / 3
                    r1 = (2 * pivot) - recent_low
                    s1 = (2 * pivot) - recent_high
                    r2 = pivot + (recent_high - recent_low)
                    s2 = pivot - (recent_high - recent_low)
                    
                    st.markdown(f"### Target Harga: {tk_pivot}")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("🔴 RESISTANCE 2", f"Rp {r2:,.0f}")
                    c2.metric("🔴 RESISTANCE 1", f"Rp {r1:,.0f}")
                    c3.metric("🔵 TITIK PIVOT", f"Rp {pivot:,.0f}")
                    
                    c4, c5, c6 = st.columns(3)
                    c4.metric("🟢 SUPPORT 1", f"Rp {s1:,.0f}")
                    c5.metric("🟢 SUPPORT 2", f"Rp {s2:,.0f}")
                    c6.metric("HARGA SAAT INI", f"Rp {recent_close:,.0f}")
                    
                    if recent_close <= s1: st.success(f"💡 Harga mendekati **SUPPORT**. Waktu yang ideal untuk mulai masuk pasar sedikit demi sedikit.")
                    elif recent_close >= r1: st.error(f"💡 Harga mendekati **RESISTANCE**. Berisiko untuk dibeli, bersiaplah untuk taking profit.")
                    else: st.info(f"💡 Harga berada di area konsolidasi tengah (Netral).")
                    
                    df_chart = df_piv.tail(30)
                    fig = go.Figure(data=[go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'], increasing_line_color='#16A34A', decreasing_line_color='#DC2626', name='Harga')])
                    fig.add_hline(y=r2, line_dash="dash", line_color="#DC2626", annotation_text="R2"); fig.add_hline(y=r1, line_dash="solid", line_color="#DC2626", annotation_text="R1")
                    fig.add_hline(y=pivot, line_dash="dot", line_color="#2563EB", annotation_text="PIVOT")
                    fig.add_hline(y=s1, line_dash="solid", line_color="#16A34A", annotation_text="S1"); fig.add_hline(y=s2, line_dash="dash", line_color="#16A34A", annotation_text="S2")
                    fig.update_layout(template="plotly_white", height=450, margin=dict(l=0,r=0,t=10,b=0), xaxis_rangeslider_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig, use_container_width=True)
            except: st.error("Data tidak mencukupi untuk menghitung batas support.")


elif menu == "📅 SIKLUS MUSIMAN":
    st.markdown(f"<h2 class='gradient-text'>Siklus Musiman (Seasonality)</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Mencuri Start dengan Siklus:**
        * Grafik menampilkan persentase kemungkinan (*Win Rate*) saham tersebut naik di bulan-bulan tertentu.
        * **Kapan Beli?** Belilah saham tersebut di akhir bulan atau **1 bulan sebelum** bulan hijau tertingginya. (Contoh: Jika BBCA selalu naik 100% di bulan April, maka belilah BBCA di akhir bulan Maret).
        * Jangan sentuh saham ini di bulan-bulan yang barnya paling pendek/merah.
        """)
    with st.form("f_season"):
        tk_season = st.text_input("Ketik Kode Saham", value="BBCA").upper().strip()
        btn_season = st.form_submit_button("Analisis Data 5 Tahun", width="stretch")
        
    if btn_season:
        with st.spinner("Mengekstrak sejarah harga 5 tahun terakhir..."):
            try:
                full_tk = f"{tk_season}.JK" if not tk_season.endswith(".JK") else tk_season
                df_season = yf.download(full_tk, period="5y", interval="1mo", progress=False)
                if not df_season.empty:
                    if isinstance(df_season.columns, pd.MultiIndex): df_season.columns = df_season.columns.get_level_values(0)
                    df_season['Bulan'] = df_season.index.month
                    df_season['Return %'] = df_season['Close'].pct_change() * 100
                    df_season = df_season.dropna()
                    
                    monthly_stats = df_season.groupby('Bulan')['Return %'].agg(Rata2_Kenaikan='mean', Tahun_Data='count', Bulan_Positif=lambda x: (x > 0).sum()).reset_index()
                    monthly_stats['Win Rate (%)'] = (monthly_stats['Bulan_Positif'] / monthly_stats['Tahun_Data']) * 100
                    nama_bulan = {1:"Jan", 2:"Feb", 3:"Mar", 4:"Apr", 5:"Mei", 6:"Jun", 7:"Jul", 8:"Agu", 9:"Sep", 10:"Okt", 11:"Nov", 12:"Des"}
                    monthly_stats['Bulan'] = monthly_stats['Bulan'].map(nama_bulan)
                    
                    best_month = monthly_stats.loc[monthly_stats['Win Rate (%)'].idxmax()]
                    st.success(f"💡 Secara historis, peluang menang terbaik di saham **{tk_season}** jatuh pada bulan **{best_month['Bulan']}** (Akurasi: {best_month['Win Rate (%)']:.0f}%).")
                    
                    fig_season = px.bar(monthly_stats, x='Bulan', y='Win Rate (%)', color='Win Rate (%)', color_continuous_scale=["#EF4444", "#F8FAFC", "#16A34A"], text_auto='.0f')
                    fig_season.update_layout(template="plotly_white", height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_season, use_container_width=True)
            except: st.error("Data rentang waktu belum mencukupi.")


elif menu == "📟 CEK FUNDAMENTAL":
    st.markdown("""<style>.stMetric {border-left: 4px solid #2563EB !important;}</style>""", unsafe_allow_html=True)
    st.markdown(f"<h2 class='gradient-text'>Cek Laporan Fundamental</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Menggunakan Radar Investor Miliarder:**
        * **Pilih Saham Undervalued:** Fokuslah membeli saham yang status "Benjamin Graham"-nya bertuliskan **MURAH** (Harga berjalan lebih rendah dari Harga Wajar).
        * **Pilih Growth:** Jika Anda mencari saham teknologi/tambang yang sedang ekspansi, pastikan "Peter Lynch" PEG Ratio-nya di bawah angka 1 (**SANGAT MURAH**).
        * **Beli untuk Pensiun (DDM):** Jika Anda ingin makan dari dividen seumur hidup tanpa jual saham, pastikan saham tersebut "LAYAK DITABUNG" di kolom DDM Model.
        """)
    col_in1, col_in2 = st.columns([3, 1])
    with col_in1: target_f = st.text_input("Ketik Kode Saham", value="BBCA").upper().strip()
    with col_in2: st.write("##"); btn_analyze = st.button("Periksa Emiten", width="stretch")

    if btn_analyze:
        full_tk = f"{target_f}.JK" if not target_f.endswith(".JK") else target_f
        with st.spinner("Memuat data laporan keuangan terakhir..."):
            try:
                info = yf.Ticker(full_tk).info
                current_price = info.get('currentPrice') or info.get('previousClose', 1)
                eps, bvps, per, pbv = info.get('trailingEps', 0) or 0, info.get('bookValue', 0) or 0, info.get('trailingPE', 0) or 0, info.get('priceToBook', 0) or 0
                roe = (info.get('returnOnEquity', 0) or 0) * 100
                der = info.get('debtToEquity', 0) or 0
                peg = info.get('pegRatio', 0) or 0
                div_rate = info.get('trailingAnnualDividendRate', 0) or 0
                
                st.markdown(f"### 🏢 {info.get('longName', target_f)}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("P/E RATIO", f"{per:,.2f}x"); c2.metric("PBV RATIO", f"{pbv:,.2f}x")
                c3.metric("ROE (Profit)", f"{roe:,.2f}%"); c4.metric("DER (Utang)", f"{der:,.1f}%")

                st.markdown("---")
                st.markdown("<h4 style='color:#2563EB;'>🧠 Analisis Valuasi Multi-Guru</h4>", unsafe_allow_html=True)
                
                c_grah, c_lyn, c_ddm = st.columns(3)
                
                with c_grah:
                    st.markdown("**1. Benjamin Graham**")
                    st.caption("Fokus: Nilai Aset Laba")
                    graham = math.sqrt(22.5 * eps * bvps) if (eps > 0 and bvps > 0) else 0
                    if graham == 0:
                        st.warning("Data EPS/BVPS minus.")
                    elif current_price < graham: 
                        st.success(f"💡 **MURAH (Undervalued)**\n\nNilai Wajar: Rp {graham:,.0f}")
                    else: 
                        st.error(f"💡 **MAHAL (Overvalued)**\n\nNilai Wajar: Rp {graham:,.0f}")
                
                with c_lyn:
                    st.markdown("**2. Peter Lynch**")
                    st.caption("Fokus: Growth (PEG)")
                    if peg > 0 and peg <= 1:
                        st.success(f"💡 **SANGAT MURAH 🚀**\n\nPEG Ratio: {peg}x")
                    elif peg > 1 and peg <= 1.5:
                        st.info(f"💡 **WAJAR (Fair) ⚖️**\n\nPEG Ratio: {peg}x")
                    elif peg > 1.5:
                        st.error(f"💡 **MAHAL ⚠️**\n\nPEG Ratio: {peg}x")
                    else:
                        st.warning("Data PEG Tidak Tersedia")
                        
                with c_ddm:
                    st.markdown("**3. DDM Model**")
                    st.caption("Fokus: Pasif Income Dividen")
                    if div_rate > 0:
                        r_expected = 0.10
                        g_expected = 0.05
                        ddm_value = (div_rate * (1 + g_expected)) / (r_expected - g_expected)
                        if current_price < ddm_value:
                            st.success(f"💡 **LAYAK DITABUNG 💰**\n\nNilai Wajar: Rp {ddm_value:,.0f}")
                        else:
                            st.error(f"💡 **DIVIDEN KEKECILAN 📉**\n\nNilai Wajar: Rp {ddm_value:,.0f}")
                    else:
                        st.warning("Bukan Saham Pembagi Dividen.")
            except: st.error("Data rasio fundamental tidak ditemukan di server.")


elif menu == "⚔️ ADU SAHAM":
    st.markdown(f"<h2 class='gradient-text'>Adu Saham (Head-to-Head)</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Mencari Pemenang Duel:**
        * Adu 2 saham di industri yang sama (Contoh: BBCA vs BBRI).
        * **Pemenang Sejati:** Pilih saham yang angka **P/E dan PBV-nya LEBIH KECIL** (artinya lebih murah harganya), tapi angka **ROE-nya LEBIH BESAR** (artinya perusahaan tersebut lebih pintar mencetak untung dari uang Anda).
        """)
    col_in1, col_in2 = st.columns(2)
    with col_in1: tk1 = st.text_input("Saham Pilihan 1", value="BBCA").upper().strip()
    with col_in2: tk2 = st.text_input("Saham Pilihan 2", value="BBRI").upper().strip()

    if st.button("Bandingkan Emiten", width="stretch"):
        with st.spinner("Membandingkan rasio..."):
            try:
                i1, i2 = yf.Ticker(f"{tk1}.JK").info, yf.Ticker(f"{tk2}.JK").info
                get_val = lambda d, k: d.get(k, 0) or 0
                st.markdown(f"<h2 style='text-align:center; color:#2563EB;'>{tk1} <span style='color:#DC2626;'>VS</span> {tk2}</h2>", unsafe_allow_html=True)
                df_compare = pd.DataFrame({
                    "METRIK ANALISIS": ["Harga Pasar", "P/E Ratio", "PBV Ratio", "Tingkat Profit (ROE)"],
                    tk1: [f"Rp {get_val(i1, 'currentPrice'):,.0f}", f"{get_val(i1, 'trailingPE'):,.2f}x", f"{get_val(i1, 'priceToBook'):,.2f}x", f"{get_val(i1, 'returnOnEquity')*100:.2f}%"],
                    tk2: [f"Rp {get_val(i2, 'currentPrice'):,.0f}", f"{get_val(i2, 'trailingPE'):,.2f}x", f"{get_val(i2, 'priceToBook'):,.2f}x", f"{get_val(i2, 'returnOnEquity')*100:.2f}%"]
                })
                st.table(df_compare.set_index("METRIK ANALISIS"))
            except: st.error("Gagal menarik perbandingan data.")


elif menu == "🌐 PETA SEKTOR":
    st.markdown(f"<h2 class='gradient-text'>Peta Rotasi Sektor Industri</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        * **Leading (Kanan Atas):** Sektor sedang jadi primadona bandar dan mengalahkan IHSG. (Waktunya Tahan Barang / Hold).
        * **Weakening (Kanan Bawah):** Sektor masih kuat tapi mulai lelah. (Waktunya Take Profit).
        * **Lagging (Kiri Bawah):** Sektor sedang mati atau dihindari. (Waktunya Jauhi / Cut Loss).
        * **Improving (Kiri Atas):** Sektor sedang diakumulasi diam-diam untuk meledak. (Waktunya Cicil Beli).
        """)
    sectors = {
        "Financials": "BBCA.JK",
        "Energy": "ADRO.JK",
        "Basic Mat": "MDKA.JK",
        "Consumer": "ICBP.JK",
        "Telco": "TLKM.JK"
    }
    
    tab_bar, tab_rrg = st.tabs(["📊 PERBANDINGAN SEKTOR", "🧭 ROTASI SEKTOR (RRG)"])
    
    with tab_bar:
        if st.button("Pantau Pergerakan Harga", use_container_width=True):
            with st.spinner("Memetakan arus sektor..."):
                sector_data = []
                all_tickers = list(sectors.values())
                try:
                    data = yf.download(all_tickers, period="5d", interval="1d", progress=False)['Close'].dropna()
                    for sec_name, t in sectors.items():
                        try:
                            c_now, c_prev = float(data[t].iloc[-1]), float(data[t].iloc[-2])
                            sec_changes = ((c_now - c_prev) / c_prev) * 100
                            sector_data.append({"Sektor": sec_name, "Perubahan (%)": round(sec_changes, 2)})
                        except: pass
                except: pass
                
                if sector_data:
                    df_sec = pd.DataFrame(sector_data).sort_values(by="Perubahan (%)", ascending=False)
                    fig_sec = px.bar(df_sec, x="Sektor", y="Perubahan (%)", color="Perubahan (%)", color_continuous_scale=["#EF4444", "#1E293B", "#10B981"])
                    fig_sec.update_layout(template="plotly_white", height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_sec, use_container_width=True)

    with tab_rrg:
        if st.button("Analisis Rotasi Sektor (RRG)", use_container_width=True):
            with st.spinner("Mengkalkulasi kekuatan relatif terhadap IHSG..."):
                try:
                    all_tickers = list(sectors.values()) + ['^JKSE']
                    data = yf.download(all_tickers, period="3mo", interval="1d", progress=False)['Close'].dropna()
                    
                    rrg_data = []
                    for sec_name, t in sectors.items():
                        try:
                            rs = data[t] / data['^JKSE']
                            rs_ratio = (rs / rs.rolling(14).mean()) * 100
                            rs_momentum = (rs_ratio / rs_ratio.rolling(14).mean()) * 100
                            
                            r_r = float(rs_ratio.dropna().iloc[-1])
                            r_m = float(rs_momentum.dropna().iloc[-1])
                            
                            rrg_data.append({"Sektor": sec_name, "RS-Ratio": r_r, "RS-Momentum": r_m})
                        except: pass
                    
                    if rrg_data:
                        df_rrg = pd.DataFrame(rrg_data)
                        fig_rrg = px.scatter(df_rrg, x="RS-Ratio", y="RS-Momentum", text="Sektor", size=[10]*len(df_rrg), color="Sektor", title="Relative Rotation Graph (RRG)")
                        fig_rrg.add_hline(y=100, line_dash="dash", line_color="gray")
                        fig_rrg.add_vline(x=100, line_dash="dash", line_color="gray")
                        fig_rrg.add_annotation(x=102, y=102, text="LEADING 🚀", showarrow=False, font=dict(color="#16A34A", size=14))
                        fig_rrg.add_annotation(x=102, y=98, text="WEAKENING 📉", showarrow=False, font=dict(color="#F59E0B", size=14))
                        fig_rrg.add_annotation(x=98, y=98, text="LAGGING 🛑", showarrow=False, font=dict(color="#DC2626", size=14))
                        fig_rrg.add_annotation(x=98, y=102, text="IMPROVING 📈", showarrow=False, font=dict(color="#2563EB", size=14))
                        
                        fig_rrg.update_traces(textposition='top center')
                        fig_rrg.update_layout(template="plotly_white", height=500, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
                        st.plotly_chart(fig_rrg, use_container_width=True)
                except Exception as e: st.error("Data tidak cukup untuk membangun Peta Rotasi (RRG).")


elif menu == "💰 PEMBURU DIVIDEN":
    st.markdown(f"<h2 class='gradient-text'>Pemburu Dividen</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Mencari Saham Pensiun:**
        * Masukkan saham pertambangan/bank besar.
        * Perhatikan angka **PERSENTASE YIELD TAHUNAN**.
        * Jika angkanya **di atas 6%** (Mengalahkan bunga deposito Bank/SBN), saham tersebut sangat bagus untuk ditabung jangka panjang.
        * Cek tabel riwayat di bawahnya. Apakah mereka rutin bagi dividen setiap tahun? Jika banyak bolongnya, lupakan!
        """)
    div_tk = st.text_input("Ketik Kode Saham", value="ITMG").upper().strip()
    if st.button("Lacak Riwayat Dividen", width="stretch"):
        with st.spinner("Memproses rekam jejak..."):
            try:
                t_obj = yf.Ticker(f"{div_tk}.JK" if not div_tk.endswith(".JK") else div_tk)
                div_yield = (t_obj.info.get('dividendYield', 0) or 0) * 100
                st.metric("PERSENTASE YIELD TAHUNAN", f"{div_yield:.2f}%")
                divs = t_obj.dividends
                if not divs.empty:
                    df_divs = pd.DataFrame(divs).reset_index()
                    df_divs.columns = ['Tanggal Penyaluran', 'Nominal Pembayaran (Rp)']
                    df_divs['Tanggal Penyaluran'] = pd.to_datetime(df_divs['Tanggal Penyaluran']).dt.strftime('%Y-%m-%d')
                    st.dataframe(df_divs.sort_values(by='Tanggal Penyaluran', ascending=False).head(10), use_container_width=True, hide_index=True)
            except: st.error("Laporan riwayat dividen tidak ditemukan.")


elif menu == "🧬 KORELASI SAHAM":
    st.markdown(f"<h2 class='gradient-text'>Korelasi Silang Saham</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Mengatur Proteksi Portofolio:**
        * Jangan taruh telur di keranjang yang sama!
        * Di dalam grafik kotak, cari angka korelasinya. Jika **mendekati +1** (warna merah pekat), berarti kedua saham itu bergerak searah. (Jika satu anjlok, yang lain ikut anjlok).
        * Jika angka **mendekati 0 atau Negatif** (warna biru), artinya saham tersebut tahan banting (saling menyeimbangkan). **Belilah saham-saham ini untuk diversifikasi!**
        """)
    input_tkrs = st.text_input("MASUKKAN KODE SAHAM (DIPISAH KOMA)", value="BBCA, BBRI, AMRT, TLKM")
    if st.button("Kalkulasi Matriks Korelasi", width="stretch"):
        with st.spinner("Melakukan perbandingan algoritma..."):
            try:
                raw_list = [t.strip().upper() + ".JK" for t in input_tkrs.split(",")]
                data_corr = yf.download(raw_list, period="6mo", interval="1d", progress=False)['Close'].dropna()
                if not data_corr.empty:
                    if isinstance(data_corr.columns, pd.MultiIndex): data_corr.columns = data_corr.columns.get_level_values(0)
                    data_corr.columns = [c.replace(".JK", "") for c in data_corr.columns]
                    fig_corr = px.imshow(data_corr.corr(), text_auto=True, color_continuous_scale="RdBu_r", zmin=-1, zmax=1)
                    fig_corr.update_layout(template="plotly_white", height=400, margin=dict(l=0,r=0,t=20,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_corr, use_container_width=True)
            except: st.error("Kalkulasi terhambat akibat data saham tidak valid.")


elif menu == "🏛️ JEJAK BANDAR":
    st.markdown(f"<h2 class='gradient-text'>Jejak Institusi & Bandar</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Membongkar Manipulasi Pasar:**
        * **Tab CMF Arus Dana:** Pantau statusnya. JANGAN beli jika statusnya "DISTRIBUSI BESAR" (Bandar sedang kabur/jualan). Beli HANYA jika tertulis "AKUMULASI BESAR".
        * **Tab VWAP Harga Modal:** Garis VWAP adalah Harga Rata-Rata Bandar. Jika "Harga Saat Ini" ADA DI BAWAH Garis VWAP, berarti saham lagi Diskon di bawah harga bandar. Waktunya SEROK BAWAH!
        * **Tab Divergensi:** Ini untuk mencari cuci piring (manipulasi). Jika Harga Saham Turun TAPI Garis Biru (Akumulasi) Naik, artinya harga sedang ditekan turun secara paksa padahal aslinya bandar sedang kumpul barang (Siap Meledak 🚀).
        """)
        
    tab_cmf, tab_vwap, tab_div = st.tabs(["🌊 CMF ARUS DANA", "🎯 VWAP HARGA MODAL", "🚨 RADAR DIVERGENSI"])
    
    with tab_cmf:
        ff_tk = st.text_input("Ketik Kode Saham", value="BBRI", key="tk_cmf").upper().strip()
        if st.button("Lacak Arus Masuk Keluar", width="stretch"):
            with st.spinner("Membongkar distribusi aliran..."):
                try:
                    df_ff = yf.download(f"{ff_tk}.JK" if not ff_tk.endswith(".JK") else ff_tk, period="3mo", interval="1d", progress=False).dropna()
                    if not df_ff.empty and len(df_ff) > 20:
                        if isinstance(df_ff.columns, pd.MultiIndex): df_ff.columns = df_ff.columns.get_level_values(0)
                        df_ff['Multiplier'] = ((df_ff['Close'] - df_ff['Low']) - (df_ff['High'] - df_ff['Close'])) / (df_ff['High'] - df_ff['Low'] + 1e-9)
                        df_ff['CMF_20'] = (df_ff['Multiplier'] * df_ff['Volume']).rolling(20).sum() / df_ff['Volume'].rolling(20).sum()
                        df_ff['CMF_20'] = df_ff['CMF_20'].fillna(0) 
                        latest_cmf = float(df_ff['CMF_20'].iloc[-1])
                        
                        if latest_cmf > 0.05: status_flow, badge_c = "AKUMULASI BESAR", "badge-green"
                        elif latest_cmf < -0.05: status_flow, badge_c = "DISTRIBUSI BESAR", "badge-red"
                        else: status_flow, badge_c = "PERGERAKAN NETRAL", "badge-blue"
                        
                        st.markdown(f"<div class='dash-box' style='text-align:center;'><br><span class='{badge_c}' style='font-size:1.2rem; padding:8px 16px;'>{status_flow}</span><br><br></div>", unsafe_allow_html=True)
                        fig_mf = px.area(df_ff.reset_index(), x='Date', y='CMF_20')
                        fig_mf.add_hline(y=0, line_dash="dash", line_color="gray")
                        fig_mf.update_layout(template="plotly_white", height=300, margin=dict(l=0,r=0,t=10,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                        st.plotly_chart(fig_mf, use_container_width=True)
                except: st.error("Kode saham tidak terdeteksi oleh radar arus.")

    with tab_vwap:
        with st.form("f_vwap"):
            c1, c2 = st.columns(2)
            vwap_tk = c1.text_input("Ketik Kode Saham", value="BBRI", key="tk_vwap").upper().strip()
            period_vwap = c2.selectbox("Periode Ekstraksi Modal?", ["1 Minggu Terakhir", "1 Bulan Terakhir", "3 Bulan Terakhir"])
            btn_vwap = st.form_submit_button("Lacak Posisi Harga Bandar", width="stretch")

        if btn_vwap:
            with st.spinner("Menghitung ekuilibrium titik harga..."):
                try:
                    full_tk = f"{vwap_tk}.JK" if not vwap_tk.endswith(".JK") else vwap_tk
                    p_map = {"1 Minggu Terakhir": "5d", "1 Bulan Terakhir": "1mo", "3 Bulan Terakhir": "3mo"}
                    df_v = yf.download(full_tk, period=p_map[period_vwap], interval="1d", progress=False).dropna()

                    if not df_v.empty:
                        if isinstance(df_v.columns, pd.MultiIndex): df_v.columns = df_v.columns.get_level_values(0)

                        df_v['Typical_Price'] = (df_v['High'] + df_v['Low'] + df_v['Close']) / 3
                        df_v['Volume_Price'] = df_v['Typical_Price'] * df_v['Volume']

                        total_volume = float(df_v['Volume'].sum())
                        total_volume_price = float(df_v['Volume_Price'].sum())

                        if total_volume > 0:
                            vwap_price = total_volume_price / total_volume
                            current_price = float(df_v['Close'].iloc[-1])

                            st.markdown("---")
                            c_a, c_b, c_c = st.columns(3)
                            c_a.metric("HARGA SAAT INI", f"Rp {current_price:,.0f}")
                            c_b.metric("ESTIMASI MODAL BANDAR", f"Rp {vwap_price:,.0f}")

                            jarak = ((current_price - vwap_price) / vwap_price) * 100
                            c_c.metric("SELESIH JARAK", f"{jarak:,.2f}%", delta_color="normal" if jarak > 0 else "inverse")

                            if current_price < vwap_price:
                                st.success(f"Harga berada DI BAWAH modal rata-rata bandar (Diskon). Area koleksi optimal.")
                            elif current_price > vwap_price and jarak <= 5:
                                st.info(f"Harga menempel dekat area modal bandar. Aman untuk masuk mengekor momentum.")
                            else:
                                st.error(f"Harga sudah jauh meroket menjauhi zona modal dasar bandar. Sangat rentan area Taking Profit.")

                            fig = go.Figure(data=[go.Candlestick(x=df_v.index, open=df_v['Open'], high=df_v['High'], low=df_v['Low'], close=df_v['Close'], increasing_line_color='#16A34A', decreasing_line_color='#DC2626')])
                            fig.add_hline(y=vwap_price, line_dash="dash", line_color="#2563EB", annotation_text="GARIS MODAL INSTITUSI (VWAP)")
                            fig.update_layout(template="plotly_white", height=400, margin=dict(l=0,r=0,t=10,b=0), xaxis_rangeslider_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.error("Transaksi nihil pada rentang periode yang diminta.")
                except: st.error("Data tidak berhasil ditarik.")

    with tab_div:
        div_tk = st.text_input("Ketik Kode Saham", value="BBRI", key="tk_div").upper().strip()
        if st.button("Mulai Analisis Anomali", width="stretch"):
            with st.spinner("Mengecek pergerakan di balik layar..."):
                try:
                    full_tk = f"{div_tk}.JK" if not div_tk.endswith(".JK") else div_tk
                    df_div = yf.download(full_tk, period="3mo", interval="1d", progress=False).dropna()
                    if not df_div.empty and len(df_div) > 20:
                        if isinstance(df_div.columns, pd.MultiIndex): df_div.columns = df_div.columns.get_level_values(0)
                        
                        df_div['MFM'] = ((df_div['Close'] - df_div['Low']) - (df_div['High'] - df_div['Close'])) / (df_div['High'] - df_div['Low'] + 1e-9)
                        df_div['MFV'] = df_div['MFM'] * df_div['Volume']
                        df_div['ADL'] = df_div['MFV'].cumsum()
                        
                        recent_df = df_div.tail(14)
                        price_start = float(recent_df['Close'].iloc[0])
                        price_end = float(recent_df['Close'].iloc[-1])
                        price_change = (price_end - price_start) / price_start * 100
                        
                        adl_start = float(recent_df['ADL'].iloc[0])
                        adl_end = float(recent_df['ADL'].iloc[-1])
                        adl_trend = adl_end - adl_start 
                        
                        if price_change < -2 and adl_trend > 0:
                            status_div, badge_div = "HIDDEN ACCUMULATION TERDETEKSI", "badge-green"
                            desc = "Perhatian! Harga dimanipulasi turun untuk menakuti pasar ritel. Namun data di layar belakang mendeteksi Institusi sedang melakukan pembelian akumulatif secara diam-diam. Momentum mantulan sangat dekat!"
                        elif price_change > 2 and adl_trend < 0:
                            status_div, badge_div = "HIDDEN DISTRIBUTION TERDETEKSI", "badge-red"
                            desc = "Awas! Harga saham dikerek tinggi memancing kehebohan, namun Institusi perlahan mendistribusikan barang keluar jaring. Rentan menghadapi jatuhnya harga secara agresif."
                        elif price_change > 0 and adl_trend > 0:
                            status_div, badge_div = "NORMAL UPTREND", "badge-blue"
                            desc = "Kenaikan harga seiring dengan sehatnya permintaan pembelian. Tren valid tanpa sinyal anomali negatif."
                        elif price_change < 0 and adl_trend < 0:
                            status_div, badge_div = "NORMAL DOWNTREND", "badge-gray"
                            desc = "Kejatuhan harga memang murni divalidasi oleh tingginya suplai penjualan. Dianjurkan posisi menunggu."
                        else:
                            status_div, badge_div = "SIDEWAYS KONSOLIDASI", "badge-gray"
                            desc = "Pergerakan volatilitas terhitung normal. Belum ada tanda intervensi bandar secara dominan."

                        st.markdown(f"<div class='dash-box' style='text-align:center;'><br><span class='{badge_div}' style='font-size:1.1rem; padding:8px 16px;'>{status_div}</span><p style='font-size:14px; margin-top:15px; color:#0F172A;'>{desc}</p></div>", unsafe_allow_html=True)
                        
                        fig_div = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.6, 0.4])
                        fig_div.add_trace(go.Candlestick(x=df_div.index, open=df_div['Open'], high=df_div['High'], low=df_div['Low'], close=df_div['Close'], increasing_line_color='#16A34A', decreasing_line_color='#DC2626', name='Harga'), row=1, col=1)
                        fig_div.add_trace(go.Scatter(x=df_div.index, y=df_div['ADL'], line=dict(color='#2563EB', width=2), name='Accumulation Line'), row=2, col=1)
                        fig_div.update_layout(template="plotly_white", height=500, margin=dict(l=0,r=0,t=10,b=0), xaxis_rangeslider_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                        st.plotly_chart(fig_div, use_container_width=True)
                except: st.error("Malfungsi sistem saat mengkalkulasi divergensi tren.")

elif menu == "📰 BERITA PASAR":
    st.markdown(f"<h2 class='gradient-text'>Financial Intelligence Center</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Mencari Bensin Market:**
        * Saham sulit terbang tanpa sentimen (berita). Mesin ini menyaring puluhan portal berita keuangan untuk Anda secara otomatis.
        * Carilah berita dengan lencana **POSITIF** (hijau) atau tulisan **🔥 HOT NEWS** (berita belum basi/baru rilis kurang dari 12 jam).
        * Jika saham incaran Anda di Scanner muncul di Tab Corporate Action (jadwal bagi dividen), itu adalah waktu yang tepat untuk melakukan akumulasi pembelian!
        """)
        
    st.markdown("### 🌍 Global Macro Radar")
    with st.spinner("Mensinkronisasi dengan bursa global..."):
        try:
            macro_tickers = {"Dow Jones": "^DJI", "Nasdaq": "^IXIC", "Minyak (WTI)": "CL=F", "Kurs (USD/IDR)": "IDR=X"}
            macro_data = yf.download(list(macro_tickers.values()), period="5d", interval="1d", progress=False).ffill()
            c1, c2, c3, c4 = st.columns(4)
            columns = [c1, c2, c3, c4]
            for i, (name, symbol) in enumerate(macro_tickers.items()):
                try:
                    close_data = macro_data['Close'][symbol].dropna()
                    if len(close_data) >= 2:
                        last_price, prev_price = float(close_data.iloc[-1]), float(close_data.iloc[-2])
                        pct_change = ((last_price - prev_price) / prev_price) * 100
                        if name == "Kurs (USD/IDR)": columns[i].metric(label=name, value=f"Rp {last_price:,.0f}", delta=f"{pct_change:.2f}%", delta_color="inverse")
                        else: columns[i].metric(label=name, value=f"{last_price:,.2f}", delta=f"{pct_change:.2f}%")
                except: columns[i].metric(label=name, value="N/A", delta="0.00%")
        except: st.warning("Pengambilan transmisi radar makro tertunda.")

    st.markdown("---")
    t_gen, t_spec, t_corp = st.tabs(["🌐 HEADLINE PASAR", "🔍 CARI BERITA EMITEN", "📅 CORPORATE ACTION"])
    
    def analyze_sentiment(text):
        pos_words = ['naik', 'laba', 'untung', 'lonjak', 'akuisisi', 'investasi', 'meroket', 'cuan', 'diborong', 'dividen', 'rekor']
        neg_words = ['turun', 'rugi', 'anjlok', 'suspend', 'kasus', 'gagal', 'merosot', 'jeblok', 'dilepas', 'resesi', 'denda']
        score = sum(1 for w in pos_words if w in text.lower()) - sum(1 for w in neg_words if w in text.lower())
        if score > 0: return "POSITIF", "badge-green"
        elif score < 0: return "NEGATIF", "badge-red"
        else: return "NETRAL", "badge-gray"

    def check_if_new(p_parsed):
        if p_parsed and (time.time() - mktime(p_parsed)) < (12 * 3600): return "🔥 HOT NEWS"
        return ""

    headers = {'User-Agent': 'Mozilla/5.0'}

    with t_gen:
        with st.spinner("Memindai berita sekuritas harian..."):
            try:
                feed = feedparser.parse(requests.get("https://news.google.com/rss/search?q=saham+indonesia+ihsg&hl=id&gl=ID&ceid=ID:id", headers=headers, timeout=5).content)
                for entry in feed.entries[:10]: 
                    sent_text, badge_c = analyze_sentiment(entry.title)
                    fire_badge = check_if_new(entry.published_parsed if hasattr(entry, 'published_parsed') else None)
                    pub_date = entry.published if hasattr(entry, 'published') else ""
                    st.markdown(f"<div class='dash-box'><div style='display:flex; justify-content:space-between; margin-bottom:8px;'><span class='{badge_c}'>{sent_text}</span><span style='font-size:11px; color:#EF4444; font-weight:700;'>{fire_badge}</span></div><a href='{entry.link}' target='_blank' style='color:#0F172A; text-decoration:none; font-size:1rem; font-weight:600;'>{entry.title}</a><p class='text-muted' style='margin-top:8px; margin-bottom:0;'>⏰ {pub_date}</p></div>", unsafe_allow_html=True)
            except: st.error("Malfungsi sambungan internet saat penarikan RSS.")
                
    with t_spec:
        with st.form("f_news"):
            search_t = st.text_input("Masukkan Kode Saham Emiten").upper().strip()
            btn_news = st.form_submit_button("Lacak Berita", width="stretch")
        if btn_news and search_t:
            with st.spinner(f"Menyisir portal berita untuk {search_t}..."):
                try:
                    feed_spec = feedparser.parse(requests.get(f"https://news.google.com/rss/search?q={search_t}+saham&hl=id&gl=ID&ceid=ID:id", headers=headers, timeout=5).content)
                    if not feed_spec.entries: st.warning("Catatan berita tidak ditemukan terkait emiten tersebut.")
                    for entry in feed_spec.entries[:8]: 
                        sent_text, badge_c = analyze_sentiment(entry.title)
                        fire_badge = check_if_new(entry.published_parsed if hasattr(entry, 'published_parsed') else None)
                        pub_date = entry.published if hasattr(entry, 'published') else ""
                        st.markdown(f"<div class='dash-box'><div style='display:flex; justify-content:space-between; margin-bottom:8px;'><span class='{badge_c}'>{sent_text}</span><span style='font-size:11px; color:#EF4444; font-weight:700;'>{fire_badge}</span></div><a href='{entry.link}' target='_blank' style='color:#0F172A; text-decoration:none; font-size:1rem; font-weight:600;'>{entry.title}</a><p class='text-muted' style='margin-top:8px; margin-bottom:0;'>⏰ {pub_date}</p></div>", unsafe_allow_html=True)
                except: st.error("Layanan filter RSS sedang tidak beroperasi.")
                
    with t_corp:
        with st.spinner("Memindai almanak korporasi..."):
            try:
                feed_corp = feedparser.parse(requests.get("https://news.google.com/rss/search?q=jadwal+dividen+OR+right+issue+OR+cum+date+saham+indonesia&hl=id&gl=ID&ceid=ID:id", headers=headers, timeout=5).content)
                for entry in feed_corp.entries[:10]: 
                    fire_badge = check_if_new(entry.published_parsed if hasattr(entry, 'published_parsed') else None)
                    pub_date = entry.published if hasattr(entry, 'published') else ""
                    st.markdown(f"<div class='dash-box'><div style='display:flex; justify-content:space-between; margin-bottom:8px;'><span class='badge-blue'>📅 INFO CORPORATE ACTION</span><span style='font-size:11px; color:#EF4444; font-weight:700;'>{fire_badge}</span></div><a href='{entry.link}' target='_blank' style='color:#0F172A; text-decoration:none; font-size:1rem; font-weight:600;'>{entry.title}</a><p class='text-muted' style='margin-top:8px; margin-bottom:0;'>⏰ {pub_date}</p></div>", unsafe_allow_html=True)
            except: st.error("Kesalahan jaringan sewaktu meretas kalender bursa.")


# =========================================================================
# 🧮 MENU UNIVERSAL 1: KALKULATOR TRADING (OMNI-CALCULATOR)
# =========================================================================
elif menu == "🧮 KALKULATOR TRADING":
    st.markdown(f"<h2 class='gradient-text'>Kalkulator Manajemen Risiko</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Menyelamatkan Uang Anda:**
        * **Kalkulator Risiko:** Sebelum beli aset, masukkan modal dan batas rugi. Beli lot sesuai angka "BELI MAKSIMAL". Jangan serakah!
        * **Averaging Down:** Khusus kalau Anda sudah nyangkut parah. Kalkulator ini mencari titik impas baru (BEP) jika Anda membeli lagi di harga bawah.
        * **Kelly Criterion:** Rumus Anti-Bangkrut kasino. AI akan melihat rekam jejak jurnal Anda (Win Rate). Jika disarankan alokasi 10%, berarti jangan beli 1 aset pakai 100% uang Anda!
        """)
        
    tab_risk, tab_avg, tab_comp, tab_kelly = st.tabs(["🛡️ KALK. RISIKO", "🛟 AVERAGING DOWN", "📈 JALUR 1 MILIAR", "⚖️ KELLY CRITERION"])
    
    with tab_risk:
        st.info("Hitung lot/unit maksimal agar modal tidak habis saat terpaksa Cut Loss.")
        with st.form("risk_calc_form"):
            c1, c2 = st.columns(2)
            capital = c1.number_input("Modal Trading Disiapkan (Rp / $)", min_value=100.0, value=10000000.0, step=50000.0)
            risk_pct = c2.number_input("Toleransi Rugi Maksimal (%)", min_value=0.1, max_value=10.0, value=2.0, step=0.1)
            c3, c4 = st.columns(2)
            entry_p = c3.number_input("Rencana Harga Beli / Entry (Rp / $)", min_value=0.0001, value=5000.0)
            stop_loss_p = c4.number_input("Batas Harga Cut Loss (Rp / $)", min_value=0.0001, value=4800.0)
            calc_btn = st.form_submit_button("Kalkulasi Lot/Unit Aman", width="stretch")
            
        if calc_btn:
            if stop_loss_p >= entry_p: st.error("⚠️ Batas Harga Cut Loss harus lebih rendah dari Harga Beli!")
            else:
                max_risk_idr = capital * (risk_pct / 100)
                risk_per_share = entry_p - stop_loss_p
                total_lots = math.floor((max_risk_idr / risk_per_share) / 100) if zona_market == "🏢 ZONA SAHAM (IDX)" else (max_risk_idr / risk_per_share)
                actual_shares = total_lots * 100 if zona_market == "🏢 ZONA SAHAM (IDX)" else total_lots
                st.markdown("---")
                m1, m2, m3 = st.columns(3)
                if zona_market == "🏢 ZONA SAHAM (IDX)":
                    m1.metric("BELI MAKSIMAL", f"{total_lots:,} Lot")
                    m2.metric("MODAL DIBUTUHKAN", f"Rp {actual_shares * entry_p:,.0f}")
                    m3.metric("UANG HILANG (JIKA CL)", f"Rp {actual_shares * risk_per_share:,.0f}", delta_color="inverse")
                else:
                    m1.metric("BELI MAKSIMAL", f"{total_lots:,.4f} Unit")
                    m2.metric("MODAL DIBUTUHKAN", f"$ {actual_shares * entry_p:,.2f}")
                    m3.metric("UANG HILANG (JIKA CL)", f"$ {actual_shares * risk_per_share:,.2f}", delta_color="inverse")
                
    with tab_avg:
        st.info("Penyelamat portofolio: Hitung lot/unit tambahan yang diperlukan untuk menurunkan beban harga rata-rata pada posisi yang menyangkut (Average Down).")
        with st.form("avg_calc_form"):
            c1, c2 = st.columns(2)
            p1 = c1.number_input("Harga Tersangkut (Atas)", min_value=0.0001, value=1000.0)
            l1 = c2.number_input("Jumlah Lot/Unit Nyangkut", min_value=0.0001, value=10.0)
            c3, c4 = st.columns(2)
            p2 = c3.number_input("Harga Bawah Saat Ini", min_value=0.0001, value=800.0)
            l2 = c4.number_input("Rencana Pembelian Baru", min_value=0.0001, value=20.0)
            calc_avg_btn = st.form_submit_button("Hitung Harga Penyelamatan", width="stretch")
            
        if calc_avg_btn:
            if p2 >= p1: st.error("⚠️ Harga pembelian tambahan harus lebih murah dari harga nyangkut!")
            else:
                pengali = 100 if zona_market == "🏢 ZONA SAHAM (IDX)" else 1
                total_modal_lama = p1 * l1 * pengali
                total_modal_baru = p2 * l2 * pengali
                total_lot_akhir = l1 + l2
                new_avg = (total_modal_lama + total_modal_baru) / (total_lot_akhir * pengali)
                st.markdown("---")
                a1, a2, a3 = st.columns(3)
                
                if zona_market == "🏢 ZONA SAHAM (IDX)":
                    a1.metric("HARGA BEP BARU", f"Rp {new_avg:,.0f}")
                    a2.metric("TOTAL KESELURUHAN LOT", f"{total_lot_akhir:,.0f} Lot")
                    a3.metric("DANA TAMBAHAN DIPERLUKAN", f"Rp {total_modal_baru:,.0f}")
                    st.success(f"Harga rata-ratamu berhasil turun ke level aman **Rp {new_avg:,.0f}**. Jual posisi segera ketika harga mencapai titik ini.")
                else:
                    a1.metric("HARGA BEP BARU", f"$ {new_avg:,.4f}")
                    a2.metric("TOTAL KESELURUHAN UNIT", f"{total_lot_akhir:,.4f} Unit")
                    a3.metric("DANA TAMBAHAN DIPERLUKAN", f"$ {total_modal_baru:,.2f}")
                    st.success(f"Harga rata-ratamu berhasil turun ke level aman **$ {new_avg:,.4f}**.")
                
    with tab_comp:
        st.info("Kalkulator Bunga Berbunga (Compounding). Hitung secara presisi kapan portofoliomu akan menembus Rp 1 Miliar!")
        with st.form("comp_form"):
            c1, c2 = st.columns(2)
            p_awal = c1.number_input("Modal Awal Saat Ini (Rp)", min_value=100000, value=10000000, step=1000000)
            r_bulan = c2.number_input("Target Profit Konsisten per Bulan (%)", min_value=0.1, max_value=100.0, value=5.0, step=0.5)
            btn_comp = st.form_submit_button("Hitung Peta Jalan 1 Miliar", width="stretch")
        
        if btn_comp:
            target_fv = 1000000000
            if p_awal >= target_fv:
                st.success("🎉 Luar Biasa! Anda sudah memiliki lebih dari 1 Miliar di tangan Anda!")
            else:
                r_decimal = r_bulan / 100
                months_needed = math.log(target_fv / p_awal) / math.log(1 + r_decimal)
                years = int(months_needed // 12)
                months = int(math.ceil(months_needed % 12))
                
                if months == 12:
                    years += 1
                    months = 0
                
                st.markdown("---")
                st.markdown(f"<h3 style='text-align:center; color:#2563EB;'>Pencapaian 1 Miliar Anda:</h3>", unsafe_allow_html=True)
                st.markdown(f"<h1 style='text-align:center; color:#10B981; font-size:3.5rem; margin-bottom:0;'>{years} Tahun {months} Bulan</h1>", unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                st.info(f"💡 Dengan modal awal **Rp {p_awal:,.0f}** dan konsistensi profit **{r_bulan}% tiap bulan** tanpa ditarik, kekuatan bunga berbunga (*compounding interest*) akan melipatgandakan aset Anda menjadi Rp 1 Miliar dalam waktu **{years} tahun {months} bulan**. Tetap disiplin dan bersabar!")

    with tab_kelly:
        with st.form("kelly_form"):
            c1, c2 = st.columns(2)
            w_rate = c1.number_input("Win Rate Trading Anda (%) (Lihat Jurnal AI)", min_value=1.0, max_value=100.0, value=55.0)
            rr_ratio = c2.number_input("Risk/Reward Ratio (Misal 2 untuk target cuan 2x lipat dari risiko cut loss)", min_value=0.1, max_value=10.0, value=2.0)
            btn_kelly = st.form_submit_button("Hitung Batas Maksimal Pembelian", width="stretch")
            
        if btn_kelly:
            W = w_rate / 100
            R = rr_ratio
            kelly_pct = W - ((1 - W) / R)
            
            st.markdown("---")
            if kelly_pct <= 0:
                st.error("⚠️ **STOP TRADING SEMENTARA!** Sistem Anda saat ini merugikan secara matematis. Anda harus memperbaiki Win Rate atau memperbesar target keuntungan Anda (Risk/Reward) sebelum menaruh uang lagi ke market.")
            else:
                st.markdown(f"<h3 style='text-align:center; color:#2563EB;'>Alokasi Dana Maksimal (Per Transaksi):</h3>", unsafe_allow_html=True)
                st.markdown(f"<h1 style='text-align:center; color:#10B981; font-size:3.5rem; margin-bottom:0;'>{kelly_pct*100:.1f}%</h1>", unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                st.success(f"💡 Pemenang Nobel Matematika menyarankan Anda untuk TIDAK menggunakan lebih dari **{kelly_pct*100:.1f}% total modal Anda** untuk 1 posisi transaksi (berdasarkan statistik pribadi Anda). Ini adalah batas pertahanan agar portofolio Anda tidak akan pernah hancur (margin call).")


# =========================================================================
# 💼 MENU UNIVERSAL 2: DOMPET TRADING (OMNI-WALLET SAHAM + KRIPTO)
# =========================================================================
elif menu == "💼 DOMPET TRADING":
    st.markdown(f"<h2 class='gradient-text'>Dompet Omni-Wallet & AI Jurnal</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Sistem Akumulasi Kekayaan Pintar (Saham + Kripto):**
        * Jika membeli Saham, ketik kodenya (`BBCA`) dan Harga Dasar Beli dalam Rupiah (misal: 10000). Satuan otomatis dihitung Lot (x100 lembar).
        * Jika membeli Kripto, WAJIB gunakan format Dolar seperti `BTC-USD` atau `PEPE-USD`. Masukkan harga beli dalam Dolar (misal: 60000.50) dan satuan Koin.
        * **Kecerdasan AI:** Sistem akan menarik nilai tukar (Kurs) Dolar ke Rupiah hari ini secara live, mengubah profit Kripto Anda ke Rupiah, lalu menggabungkannya dengan aset saham Anda menjadi **Total Kekayaan Bersih**.
        """)
        
    c_title, c_toggle = st.columns([3, 1])
    show_saldo = c_toggle.checkbox("👁️ Penampakan Saldo", value=False)
    format_privacy = lambda v: f"Rp {v:,.0f}" if show_saldo else "Rp *****"

    tab1, tab2, tab3 = st.tabs(["📈 KEPEMILIKAN ASET", "📜 RIWAYAT", "📊 AUDIT AI JURNAL"])
    
    with tab1:
        with st.expander("➕ DAFTARKAN PEMBELIAN ASET BARU", expanded=False):
            with st.form("form_add_portfolio", clear_on_submit=True):
                c1, c2 = st.columns(2)
                t_in = c1.text_input("Kode Saham/Kripto (Cth: BBCA atau BTC-USD)")
                l_in = c2.number_input("Besaran Lot Saham / Unit Koin?", min_value=0.000001, value=1.0, format="%.6f")
                c3, c4 = st.columns(2)
                p_in = c3.number_input("Harga Dasar Beli (Rp utk Saham / $ u/ Kripto)", min_value=0.000001, value=100.0, format="%.6f")
                strat_in = c4.selectbox("Faktor Justifikasi Beli?", ["Golden Cross MA", "Breakout Resistance", "Serok Bawah (Support)", "Ikut Berita", "Fundamental Bagus", "Feeling / FOMO"])
                if st.form_submit_button("MASUKKAN DALAM SISTEM", width="stretch"):
                    if t_in and p_in > 0: 
                        add_to_portfolio(user_now, t_in, p_in, l_in, 0, 0, strat_in)
                        st.success("Berkas Berhasil Tersimpan di Cloud!"); st.rerun()

        df_p = get_user_portfolio(user_now, role)
        if not df_p.empty:
            # Ambil Nilai Tukar USD/IDR Terbaru untuk konversi kripto
            try:
                kurs_idr = float(yf.download("IDR=X", period="1d", progress=False)['Close'].iloc[-1])
            except:
                kurs_idr = 15500.0 # Harga cadangan jika API putus
                
            tickers_raw = df_p['ticker'].unique()
            # Pisahkan mana yang butuh ditambah .JK dan mana yang kripto (-USD)
            tickers_yf = [f"{t}.JK" if "-" not in t else t for t in tickers_raw]
            
            try:
                live_prices_df = yf.download(tickers_yf, period="5d", progress=False, threads=True)['Close'].dropna()
                live_prices = live_prices_df.iloc[-1].to_dict() if len(tickers_yf) > 1 else {tickers_yf[0]: float(live_prices_df.iloc[-1])}
            except: live_prices = {}

            def calc_omni_active(row):
                tk_asli = row['ticker']
                tk_yf = f"{tk_asli}.JK" if "-" not in tk_asli else tk_asli
                is_crypto = "-" in tk_asli
                
                bp = float(row['buy_price'])
                lots = float(row['lots'])
                curr_price = float(live_prices.get(tk_yf, bp))
                
                if not is_crypto:
                    # Saham Indonesia (Sudah Rupiah)
                    cost_rp = bp * lots * 100
                    val_rp = curr_price * lots * 100
                else:
                    # Kripto (Masih USD, kalikan dengan kurs IDR)
                    cost_usd = bp * lots
                    val_usd = curr_price * lots
                    cost_rp = cost_usd * kurs_idr
                    val_rp = val_usd * kurs_idr
                    
                pnl_rp = val_rp - cost_rp
                return pd.Series([curr_price, cost_rp, val_rp, pnl_rp])

            df_p[['Live', 'Cost_IDR', 'Value_IDR', 'PnL_IDR']] = df_p.apply(calc_omni_active, axis=1)
            t_inv_rp, t_pl_rp = df_p['Cost_IDR'].sum(), df_p['PnL_IDR'].sum()
            
            # --- GRAND TOTAL OMNI-WALLET ---
            st.markdown(f"<div style='text-align:center;'><p style='margin:0; font-size:12px; color:#64748B;'>Estimasi Kurs USD: Rp {kurs_idr:,.0f}</p></div>", unsafe_allow_html=True)
            m1, m2, m3 = st.columns(3)
            m1.metric("TOTAL MODAL (Rp)", format_privacy(t_inv_rp))
            m2.metric("TOTAL CUAN/RUGI (Rp)", format_privacy(t_pl_rp), f"{(t_pl_rp/t_inv_rp*100 if t_inv_rp!=0 else 0):.2f}%" if show_saldo else "*****")
            m3.metric("TOTAL KEKAYAAN (Rp)", format_privacy(t_inv_rp + t_pl_rp))

            st.markdown("---")
            for i, row in df_p.iterrows():
                strat_label = row.get('strategy', 'Bebas')
                is_cr = "-" in row['ticker']
                satuan = "Unit" if is_cr else "Lot"
                simbol_uang = "$" if is_cr else "Rp"
                
                with st.expander(f"{'🪙' if is_cr else '🏢'} {row['ticker']} | {row['lots']} {satuan} | Profit: Rp {row['PnL_IDR']:,.0f}"):
                    st.markdown(f"<span class='badge-blue'>Kategori: {strat_label}</span>", unsafe_allow_html=True)
                    st.write("")
                    c_price, c_lots, c_btn = st.columns([2, 2, 1])
                    s_price = c_price.number_input(f"Eksekusi Jual di Harga ({simbol_uang})", value=float(row['Live']), format="%.6f", key=f"s_prc_{row['id']}")
                    s_lots = c_lots.number_input(f"Berapa {satuan} Dilepas?", min_value=0.000001, max_value=float(row['lots']), value=float(row['lots']), format="%.6f", key=f"s_lot_{row['id']}")
                    if c_btn.button("LIKUIDASI", key=f"btn_s_{row['id']}", use_container_width=True):
                        st.toast(sell_position(user_now, row['id'], row['ticker'], row['buy_price'], s_price, row['lots'], s_lots)); time.sleep(1); st.rerun()
        else: st.info("Sistem perbendaharaan belum mencatatkan transaksi apapun.")

    with tab2:
        df_h = conn_gs.read(worksheet="history", ttl=0)
        if not df_h.empty:
            df_h['pnl'] = pd.to_numeric(df_h['pnl'], errors='coerce')
            if role != 'admin': df_h = df_h[df_h['username'] == user_now]
            for idx, h_row in df_h.sort_values(by='date', ascending=False).iterrows():
                with st.expander(f"{h_row['date']} | {h_row['ticker']}"):
                    c_t, c_b = st.columns([4,1])
                    c_t.write(f"Dasar Strategi: **{h_row.get('strategy', 'Tidak Terekam')}**")
                    satuan_h = "Unit" if "-" in h_row['ticker'] else "Lot"
                    uang_h = "$" if "-" in h_row['ticker'] else "Rp"
                    c_t.write(f"Avg Beli: {uang_h} {h_row['buy_price']} | Avg Jual: {uang_h} {h_row['sell_price']} | Pelepasan: {h_row['lots']} {satuan_h} | Profit: {format_privacy(h_row['pnl'])}")
                    if c_b.button("🗑️ Hapus Bukti", key=f"del_h_{h_row['id']}"):
                        df_h_all = conn_gs.read(worksheet="history", ttl=0)
                        idx_del_h = df_h_all.index[df_h_all['id'] == h_row['id']].tolist()
                        if idx_del_h: conn_gs.update(worksheet="history", data=df_h_all.drop(idx_del_h[0]).reset_index(drop=True)); st.rerun()

    with tab3: 
        if 'df_h' in locals() and not df_h.empty:
            df_h_sorted = df_h.sort_values('date')
            df_h_sorted['Cumulative_PnL'] = df_h_sorted['pnl'].cumsum()
            
            fig_eq = px.area(df_h_sorted, x='date', y='Cumulative_PnL', title="📈 Kurva Pertumbuhan Ekuitas (Kinerja Trading Saham & Kripto)")
            fig_eq.update_traces(line_color='#2563EB', fillcolor='rgba(37, 99, 235, 0.2)')
            fig_eq.update_layout(template="plotly_white", height=300, margin=dict(l=0,r=0,t=40,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_eq, use_container_width=True)
            
            if 'strategy' in df_h.columns:
                strat_analysis = df_h.groupby('strategy').apply(
                    lambda x: pd.Series({'Total Trading': len(x), 'Win Rate (%)': (x['pnl'] > 0).mean() * 100})
                ).reset_index()
                
                if not strat_analysis.empty:
                    best_strat = strat_analysis.loc[strat_analysis['Win Rate (%)'].idxmax()]
                    st.success(f"💡 **Saran Sistem AI:** Statistik mencatat bahwa Anda paling handal ketika menggunakan justifikasi **'{best_strat['strategy']}'** dengan tingkat konfirmasi profit {best_strat['Win Rate (%)']:.0f}%. Disarankan untuk lebih disiplin menunggu sinyal dari metode ini.")
            
            total_trades = len(df_h)
            win_trades = len(df_h[df_h['pnl'] > 0])
            win_rate = (win_trades / total_trades) * 100 if total_trades > 0 else 0
            
            c1, c2 = st.columns(2)
            c1.metric("KEMAMPUAN MENANG (WIN RATE)", f"{win_rate:.1f}%")
            c2.metric("REKAMAN FREKUENSI TRANSAKSI", f"{total_trades} Entri")


# =========================================================================
# ⚙️ MENU UNIVERSAL 3: PORTAL ADMINISTRATIF
# =========================================================================
elif menu == "⚙️ USER MANAGEMENT":
    st.markdown(f"<h2 class='gradient-text'>Portal Administratif</h2>", unsafe_allow_html=True)
    st.caption("Super-user dashboard untuk pengurusan identitas anggota sistem terminal.")
    df_u = conn_gs.read(worksheet="users", ttl=0)
    st.dataframe(df_u[['username', 'role', 'last_login', 'location']], use_container_width=True, hide_index=True)
    with st.form("add_u"):
        nu, np, nr = st.text_input("Registrasi Node ID"), st.text_input("Sandikunci", type="password"), st.selectbox("Role Izin", ["user", "admin"])
        if st.form_submit_button("SETUJUI KREDENSIAL BARU", width="stretch"):
            if add_user_db(nu, np, nr): st.success("Basis Data Diperbarui!"); st.rerun()
    with st.form("del_u"):
        du = st.text_input("Masukan ID Node Terminal untuk dihapus")
        if st.form_submit_button("BLOKIR AKSES PERMANEN", width="stretch"):
            if delete_user_db(du): st.warning("Akses Terminal Berhasil Dihanguskan!"); st.rerun()


# =========================================================================
# 🔒 MENU UNIVERSAL 4: KEAMANAN
# =========================================================================
elif menu == "🔒 KEAMANAN":
    st.markdown(f"<h2 class='gradient-text'>Keamanan Node Terminal</h2>", unsafe_allow_html=True)
    st.caption("Pusat perlindungan enkripsi akses ke modul portofolio privat Anda.")
    with st.form("p"):
        new_p = st.text_input("Ketikan Sandikunci Baru", type="password")
        if st.form_submit_button("ENKRIPSI DAN SIMPAN", width="stretch"):
            if update_password_db(user_now, new_p): st.success("Sandikunci berhasil diubah dan diamankan oleh sistem!")

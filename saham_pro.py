# -*- coding: utf-8 -*-
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
    page_title="IDX & INDODAX PRO TERMINAL", 
    page_icon="📊", 
    layout="wide",
    initial_sidebar_state="collapsed" 
)

# Koneksi Database Google Sheets
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
    indo_tickers = get_indodax_tickers()
    clean_t = ticker.replace('.JK','').replace('-USD','').lower() + "_idr"
    is_cr = clean_t in indo_tickers
    
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


# =========================================================================
# --- 2. FUNGSI PENARIKAN DATA LIVE INDODAX & YAHOO FINANCE ---
# =========================================================================
@st.cache_data(ttl=30)
def get_indodax_tickers():
    try:
        resp = requests.get("https://indodax.com/api/tickers", timeout=5).json()
        return resp.get('tickers', {})
    except: return {}

@st.cache_data(ttl=15)
def get_indodax_depth(pair="btcidr"):
    try: return requests.get(f"https://indodax.com/api/depth/{pair}", timeout=5).json()
    except: return {}

@st.cache_data(ttl=15)
def get_indodax_trades(pair="btcidr"):
    try: return requests.get(f"https://indodax.com/api/trades/{pair}", timeout=5).json()
    except: return []

@st.cache_data(ttl=86400)
def get_sector(ticker):
    try: 
        indo_tickers = get_indodax_tickers()
        clean_t = ticker.replace('.JK','').replace('-USD','').lower() + "_idr"
        if clean_t in indo_tickers: return "Cryptocurrency"
        return yf.Ticker(f"{ticker}.JK").info.get('sector', 'Lainnya')
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
# --- 3. MESIN SCANNER UNIVERSAL & FUNGSI PEMBANTU ---
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
    prefix = "Rp"
    for _, row in df.iterrows():
        chg, chg_color = row.get('CHG%', 0), "#16A34A" if row.get('CHG%', 0) > 0 else "#DC2626"
        val_last, val_entry = row.get('LAST', 0), row.get('ENTRY', row.get('Entry', row.get('LAST', 0)))
        val_tp1, val_cl, val_m = row.get('TP 1', 0), row.get('EXIT/CL', 0), row.get('VAL(M)', 0)

        fmt_p = f"{prefix} {val_last:,.0f}"
        fmt_e, fmt_tp, fmt_cl = f"{prefix} {val_entry:,.0f}", f"{prefix} {val_tp1:,.0f}", f"{prefix} {val_cl:,.0f}"

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

p, span, label, li, div.stMarkdown, .stText { color: #1E293B; }

h1, h2, h3, h4, h5, h6 { font-family: 'Inter', sans-serif !important; font-weight: 700 !important; color: #0F172A !important; letter-spacing: -0.5px; }
.gradient-text { background: linear-gradient(90deg, #2563EB, #10B981); -webkit-background-clip: text; -webkit-text-fill-color: transparent; display: inline-block; }
.stCaptionContainer p, [data-testid="stCaptionContainer"] p { color: #64748B !important; }

.ticker-wrap {
    position: sticky; top: 0; z-index: 9999; width: 100%; overflow: hidden; 
    background-color: rgba(15, 23, 42, 0.95); backdrop-filter: blur(10px); 
    color: #FFFFFF !important; padding: 10px 0; border-radius: 8px; margin-bottom: 20px; white-space: nowrap; box-shadow: 0 4px 10px rgba(0, 0, 0, 0.15);
}
.ticker { display: inline-block; white-space: nowrap; padding-right: 100%; box-sizing: content-box; animation: ticker 40s linear infinite; }
.ticker:hover { animation-play-state: paused; }
.ticker-item { display: inline-block; padding: 0 20px; font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; font-weight: 600; color: #F8FAFC; }
@keyframes ticker { 0% { transform: translate3d(0, 0, 0); } 100% { transform: translate3d(-50%, 0, 0); } }

.pulsing-dot {
    display: inline-block; width: 10px; height: 10px; border-radius: 50%; background-color: #10B981; margin-right: 5px;
    box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); animation: pulse-dot 1.5s infinite;
}
@keyframes pulse-dot { 0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); } 70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); } 100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); } }

.badge-green { background-color: #D1FAE5; color: #065F46; padding: 4px 12px; border-radius: 9999px; font-size: 0.8rem; font-weight: 700; display: inline-block;}
.badge-red { background-color: #FEE2E2; color: #991B1B; padding: 4px 12px; border-radius: 9999px; font-size: 0.8rem; font-weight: 700; display: inline-block;}
.badge-blue { background-color: #DBEAFE; color: #1E40AF; padding: 4px 12px; border-radius: 9999px; font-size: 0.8rem; font-weight: 700; display: inline-block;}
.badge-gray { background-color: #F1F5F9; color: #475569; padding: 4px 12px; border-radius: 9999px; font-size: 0.8rem; font-weight: 700; display: inline-block;}

.stTabs [data-baseweb="tab-list"] { background-color: #E2E8F0 !important; border-radius: 12px; padding: 4px; gap: 4px; border-bottom: none !important; }
.stTabs [data-baseweb="tab"] { background-color: transparent !important; border-radius: 8px !important; padding: 8px 16px !important; border: none !important; margin: 0 !important; }
.stTabs [data-baseweb="tab"] p { color: #64748B !important; transition: all 0.3s ease; font-weight: 600 !important; }
.stTabs [aria-selected="true"] { background-color: #FFFFFF !important; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.stTabs [aria-selected="true"] p { color: #2563EB !important; font-weight: 800 !important; }
.stTabs [data-baseweb="tab-highlight"] { display: none !important; }

section[data-testid="stSidebar"], [data-testid="stSidebarContent"] { background-color: rgba(255, 255, 255, 0.95) !important; backdrop-filter: blur(12px) !important; border-right: 1px solid #E2E8F0 !important; }
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label { background: transparent !important; border: none !important; border-radius: 8px !important; padding: 10px 14px !important; margin-bottom: 4px !important; }
section[data-testid="stSidebar"] .stRadio p, section[data-testid="stSidebar"] .stRadio span, section[data-testid="stSidebar"] .stRadio label { font-family: 'Inter', sans-serif !important; font-size: 0.95rem !important; color: #334155 !important; font-weight: 600 !important; }
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] [aria-checked="true"] { background-color: #F8FAFC !important; border: 1px solid #E2E8F0 !important; border-left: 4px solid #2563EB !important; }
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] [aria-checked="true"] p, section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] [aria-checked="true"] span { color: #2563EB !important; font-weight: 800 !important; }

div[data-testid="stForm"], div[data-testid="stExpander"], div[data-testid="stMetric"], .dash-box {
    background-color: #FFFFFF !important; border: 1px solid #E2E8F0 !important; border-radius: 12px; padding: 16px !important; margin-bottom: 16px !important; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03); transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.25s cubic-bezier(0.4, 0, 0.2, 1); 
}
div[data-testid="stForm"]:hover, div[data-testid="stMetric"]:hover, .dash-box:hover {
    transform: translateY(-4px); box-shadow: 0 12px 20px -5px rgba(37, 99, 235, 0.15), 0 8px 10px -6px rgba(37, 99, 235, 0.1) !important; border-color: #BFDBFE !important; 
}
.dash-box { border-top: 1px solid #E2E8F0 !important; }

div[data-testid="stForm"] label p, .stTextInput label p, .stNumberInput label p, .stSelectbox label p { color: #2563EB !important; font-size: 0.85rem !important; font-weight: 600 !important; }
input, select, textarea { background-color: #F8FAFC !important; border: 1px solid #CBD5E1 !important; color: #0F172A !important; font-family: 'JetBrains Mono', monospace !important; border-radius: 8px !important; height: 44px !important; font-size: 15px !important; font-weight: 600 !important; box-shadow: inset 0px 2px 4px rgba(0,0,0,0.06) !important; transition: border-color 0.2s ease, box-shadow 0.2s ease; }
input:focus, select:focus { border-color: #38BDF8 !important; box-shadow: inset 0px 2px 4px rgba(0,0,0,0.06), 0 0 0 3px rgba(56, 189, 248, 0.2) !important; }
[data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace !important; font-size: 1.8rem !important; color: #0F172A !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"] * { color: #64748B !important; font-weight: 600 !important; font-size: 0.85rem !important; }
.streamlit-expanderHeader * { color: #0F172A !important; font-weight: 600 !important; }

.stButton>button { background-color: #2563EB !important; border: none !important; border-radius: 8px !important; min-height: 44px; width: 100%; margin-top: 5px; margin-bottom: 5px; transition: background-color 0.2s ease, transform 0.1s ease; position: relative; overflow: hidden; }
.stButton>button p, .stButton>button span, .stButton>button div { color: #FFFFFF !important; font-family: 'Inter', sans-serif !important; font-weight: 600 !important; font-size: 0.9rem !important; position: relative; z-index: 2; }
.stButton>button:hover { background-color: #1D4ED8 !important; transform: scale(1.02); }
.stButton>button::after { content: ""; position: absolute; top: 0; left: -100%; width: 50%; height: 100%; background: linear-gradient(to right, rgba(255,255,255,0) 0%, rgba(255,255,255,0.2) 50%, rgba(255,255,255,0) 100%); transform: skewX(-20deg); animation: shimmer 3s infinite; z-index: 1; }
@keyframes shimmer { 100% { left: 200%; } }

.text-green { color: #16A34A !important; } .text-red { color: #DC2626 !important; } .text-blue { color: #2563EB !important; } .text-muted { color: #64748B !important; font-size: 13px; }
</style>""", unsafe_allow_html=True)

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
        "⚔️ ADU SAHAM", "🌐 PETA SEKTOR", "💰 PEMBURU DIVIDEN", 
        "🧬 KORELASI SAHAM", "🏛️ JEJAK BANDAR", "📰 BERITA PASAR"
    ]
else:
    menu_list = [
        "🪙 DASBOR INDODAX", "🚀 RADAR ALTCOIN", "🐋 WHALE TRACKER INDODAX", "🔮 PREDIKSI KRIPTO", 
        "⚔️ ADU KRIPTO", "🌐 PETA KRIPTO"
    ]

menu_list.append("🧮 KALKULATOR TRADING")
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
# 🪙 MENU KHUSUS ZONA KRIPTO (INDODAX)
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
    st.markdown(f"<h2 class='gradient-text'>Altcoin Pump Radar (100% Indodax IDR)</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Mencari Koin yang Sedang di-"Pump" (Goreng):**
        * Radar ini memindai seluruh pasangan koin di Indodax secara *Real-Time* dalam Rupiah.
        * Carilah koin dengan **AI_SCORE** tertinggi.
        * **VPA STATUS:** Jika tertulis "🚀 BREAKOUT BESAR", artinya volume transaksi koin tersebut melonjak drastis. Beli di harga **ENTRY (Rp)** dan pasang target jual di **TP 1 / TP 2**.
        """)
        
    c1, c2 = st.columns([2, 1])
    with c1: mode_scan = st.radio("SENSITIVITAS:", ["Santai", "Profesional", "Pro"], horizontal=True)
    with c2: 
        st.write("##")
        btn_scan = st.button("Mulai Scan Indodax Market", use_container_width=True)

    if btn_scan:
        with st.spinner("Memindai seluruh pasar Indodax..."):
            indo_tickers = get_indodax_tickers()
            res_crypto = []
            
            if mode_scan == "Santai": min_vol = 100_000_000
            elif mode_scan == "Profesional": min_vol = 500_000_000
            else: min_vol = 1_000_000_000
            
            for pair, data in indo_tickers.items():
                if pair.endswith('_idr'):
                    try:
                        coin = pair.replace('_idr', '').upper()
                        last_p = float(data.get('last', 0))
                        high_p = float(data.get('high', last_p))
                        low_p = float(data.get('low', last_p))
                        vol_rp = float(data.get('vol_idr', 0))
                        
                        if vol_rp >= min_vol and last_p > 0:
                            chg_pct = ((last_p - low_p) / low_p * 100) if low_p > 0 else 0
                            ai_score = (chg_pct * 0.6) + ((vol_rp / 1e9) * 0.4)
                            
                            vpa_st = "🚀 BREAKOUT BESAR" if last_p >= (high_p * 0.97) else "NORMAL (Searah)"
                            entry_p = last_p * 0.98
                            tp1_p = last_p * 1.05
                            tp2_p = last_p * 1.10
                            cl_p = last_p * 0.95
                            
                            res_crypto.append({
                                "TICKER": coin, "LAST": last_p, "CHG%": chg_pct,
                                "VAL(M)": (vol_rp / 1_000_000), "BANDAR": "AKUMULASI" if chg_pct > 2 else "NETRAL",
                                "VPA_STATUS": vpa_st, "KATALIS": "🚀 INDODAX HOT",
                                "AI_SCORE": ai_score, "ENTRY": entry_p, "TP 1": tp1_p, "TP 2": tp2_p, "EXIT/CL": cl_p
                            })
                    except: pass
            
            if res_crypto:
                df_c = pd.DataFrame(res_crypto).sort_values(by='AI_SCORE', ascending=False)
                st.session_state.res_crypto = df_c
                st.rerun()
            else: st.warning("Belum ada koin di Indodax yang memenuhi kriteria lonjakan volume hari ini.")

    if 'res_crypto' in st.session_state and st.session_state.res_crypto is not None and not st.session_state.res_crypto.empty:
        df = st.session_state.res_crypto
        st.info(f"💡 **Hasil:** Ditemukan **{len(df)} Koin Indodax** yang sedang ramai ditransaksikan.")

        tab1, tab3 = st.tabs(["📱 RINGKASAN SIGNAL", "📊 DATA LENGKAP AI"])
        
        with tab1: draw_mobile_cards(df, is_crypto=True)
            
        with tab3: 
            def highlight_cols(s):
                if s.name == 'CHG%': return ['background-color: #D1FAE5; color: #065F46; font-weight:bold;' if pd.to_numeric(v, errors='coerce') > 0 else 'background-color: #FEE2E2; color: #991B1B; font-weight:bold;' for v in s]
                return ['' for _ in s]
                
            format_mapping = {
                'LAST': 'Rp {:,.0f}', 'CHG%': '{:.2f}%', 'VAL(M)': 'Rp {:,.1f} M', 'AI_SCORE': '{:.1f}',
                'ENTRY': 'Rp {:,.0f}', 'TP 1': 'Rp {:,.0f}', 'TP 2': 'Rp {:,.0f}', 'EXIT/CL': 'Rp {:,.0f}'
            }
            styled_df = df.style.format(format_mapping).applymap(style_dataframe).apply(highlight_cols)
            st.dataframe(styled_df, use_container_width=True, hide_index=True)


elif menu == "🐋 WHALE TRACKER INDODAX":
    st.markdown(f"<h2 class='gradient-text'>Indodax Live Tape & Order Book</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Melacak Pergerakan Paus (Whales) di Indodax:**
        * **Buku Order (Tembok Bandar):** Lihat Total Antrean. Jika kolom BID jauh lebih besar dari kolom ASK, artinya banyak yang antre beli di bawah (Harga akan susah turun/mantul).
        * **Transaksi Terkini (Tape Reading):** Jika muncul deretan transaksi dengan kolom Tipe "Beli" (Hijau) dalam jumlah Rupiah yang masif beruntun, bersiaplah harga akan meroket (Pump).
        """)

    with st.form("f_whale"):
        pilihan_koin = st.selectbox("Pilih Koin untuk Diintai (Rupiah Market):", ["BTC", "ETH", "USDT", "DOGE", "PEPE", "SOL", "BNB", "XRP", "CEL"])
        btn_whale = st.form_submit_button("Lacak Data Live Indodax", width="stretch")

    if btn_whale:
        pair_id = f"{pilihan_koin.lower()}idr"
        with st.spinner(f"Menyadap server pesanan {pilihan_koin} di Indodax..."):
            depth_data = get_indodax_depth(pair_id)
            trade_data = get_indodax_trades(pair_id)

            if depth_data and trade_data:
                tab_book, tab_tape = st.tabs(["📚 BUKU ORDER (BID/ASK)", "⚡ TRANSAKSI LIVE (TAPE)"])

                with tab_book:
                    c_bid, c_ask = st.columns(2)
                    bids = depth_data.get('buy', [])[:15] 
                    asks = depth_data.get('sell', [])[:15]
                    
                    df_bids = pd.DataFrame(bids, columns=['Harga Antre Beli (Rp)', 'Jumlah Koin'])
                    df_bids['Harga Antre Beli (Rp)'] = pd.to_numeric(df_bids['Harga Antre Beli (Rp)'])
                    df_bids['Jumlah Koin'] = pd.to_numeric(df_bids['Jumlah Koin'])
                    df_bids['Total Nilai (Rp)'] = df_bids['Harga Antre Beli (Rp)'] * df_bids['Jumlah Koin']
                    
                    df_asks = pd.DataFrame(asks, columns=['Harga Antre Jual (Rp)', 'Jumlah Koin'])
                    df_asks['Harga Antre Jual (Rp)'] = pd.to_numeric(df_asks['Harga Antre Jual (Rp)'])
                    df_asks['Jumlah Koin'] = pd.to_numeric(df_asks['Jumlah Koin'])
                    df_asks['Total Nilai (Rp)'] = df_asks['Harga Antre Jual (Rp)'] * df_asks['Jumlah Koin']

                    with c_bid:
                        st.markdown("<h4 style='color:#16A34A; text-align:center;'>🟢 Tembok Pembeli (BID)</h4>", unsafe_allow_html=True)
                        st.dataframe(df_bids.style.format({"Harga Antre Beli (Rp)": "{:,.0f}", "Jumlah Koin": "{:,.4f}", "Total Nilai (Rp)": "{:,.0f}"}), use_container_width=True, hide_index=True)

                    with c_ask:
                        st.markdown("<h4 style='color:#DC2626; text-align:center;'>🔴 Tembok Penjual (ASK)</h4>", unsafe_allow_html=True)
                        st.dataframe(df_asks.style.format({"Harga Antre Jual (Rp)": "{:,.0f}", "Jumlah Koin": "{:,.4f}", "Total Nilai (Rp)": "{:,.0f}"}), use_container_width=True, hide_index=True)

                with tab_tape:
                    st.markdown("<h4 style='color:#2563EB;'>⚡ Transaksi Tereksekusi (Detik Terakhir)</h4>", unsafe_allow_html=True)
                    trades_list = trade_data[:20] 
                    if trades_list:
                        df_trades = pd.DataFrame(trades_list)
                        df_trades['Tipe'] = df_trades['type'].apply(lambda x: "🟢 BELI" if x == 'buy' else "🔴 JUAL")
                        df_trades['Harga Eksekusi (Rp)'] = pd.to_numeric(df_trades['price'])
                        df_trades['Jumlah Koin'] = pd.to_numeric(df_trades['amount'])
                        df_trades['Total Nilai (Rp)'] = df_trades['Harga Eksekusi (Rp)'] * df_trades['Jumlah Koin']
                        df_trades['Waktu'] = pd.to_datetime(df_trades['date'], unit='s', utc=True).dt.tz_convert('Asia/Jakarta').dt.strftime('%H:%M:%S')
                        
                        df_show = df_trades[['Waktu', 'Tipe', 'Harga Eksekusi (Rp)', 'Jumlah Koin', 'Total Nilai (Rp)']]
                        
                        def highlight_type(s):
                            if s.name == 'Tipe': return ['background-color: #D1FAE5; color: #065F46; font-weight:bold;' if 'BELI' in v else 'background-color: #FEE2E2; color: #991B1B; font-weight:bold;' for v in s]
                            return ['' for _ in s]

                        st.dataframe(df_show.style.format({"Harga Eksekusi (Rp)": "{:,.0f}", "Jumlah Koin": "{:,.4f}", "Total Nilai (Rp)": "{:,.0f}"}).apply(highlight_type), use_container_width=True, hide_index=True)
            else: st.error("Gagal menarik data langsung dari Indodax.")


elif menu == "🔮 PREDIKSI KRIPTO":
    st.markdown(f"<h2 class='gradient-text'>Pola AI & Proyeksi Kripto</h2>", unsafe_allow_html=True)
    with st.form("f_mc_cr"):
        tk_mc = st.text_input("Ketik Simbol Koin (Contoh: BTC, ETH, DOGE)", value="BTC").upper().strip()
        btn_mc = st.form_submit_button("Mulai Proyeksi Masa Depan", width="stretch")
        
    if btn_mc:
        with st.spinner("Menghitung 100 skenario masa depan koin..."):
            try:
                df_mc = yf.download(f"{tk_mc}-USD", period="1y", interval="1d", progress=False)['Close'].dropna()
                if len(df_mc) > 50:
                    returns = df_mc.pct_change().dropna()
                    mu, vol = returns.mean(), returns.std()
                    last_price = float(df_mc.iloc[-1])
                    
                    paths = []
                    for i in range(100):
                        path = [last_price]
                        for j in range(30):
                            shock = random.gauss(0, 1)
                            price = path[-1] * math.exp(mu - 0.5 * vol**2 + vol * shock)
                            path.append(price)
                        paths.append(path)
                    
                    fig_mc = go.Figure()
                    for p in paths: fig_mc.add_trace(go.Scatter(y=p, mode='lines', line=dict(color='rgba(37, 99, 235, 0.1)', width=1), showlegend=False))
                    fig_mc.add_trace(go.Scatter(y=np.mean(paths, axis=0), mode='lines', line=dict(color='#DC2626', width=3), name='Rata-Rata Proyeksi'))
                    fig_mc.update_layout(title=f"Proyeksi Harga {tk_mc} (30 Hari ke Depan)", template="plotly_white", height=400)
                    st.plotly_chart(fig_mc, use_container_width=True)
                else: st.warning("Data koin terlalu sedikit.")
            except: st.error("Gagal melakukan simulasi.")


elif menu == "⚔️ ADU KRIPTO":
    st.markdown(f"<h2 class='gradient-text'>Adu Kekuatan Koin Indodax</h2>", unsafe_allow_html=True)
    col_in1, col_in2 = st.columns(2)
    with col_in1: tk1 = st.text_input("Koin Pilihan 1 (Contoh: BTC)", value="BTC").upper().strip()
    with col_in2: tk2 = st.text_input("Koin Pilihan 2 (Contoh: ETH)", value="ETH").upper().strip()

    if st.button("Bandingkan Koin", width="stretch"):
        indo_tickers = get_indodax_tickers()
        data1 = indo_tickers.get(f"{tk1.lower()}_idr", {})
        data2 = indo_tickers.get(f"{tk2.lower()}_idr", {})
        
        if data1 and data2:
            st.markdown(f"<h2 style='text-align:center; color:#2563EB;'>{tk1} <span style='color:#DC2626;'>VS</span> {tk2}</h2>", unsafe_allow_html=True)
            df_compare = pd.DataFrame({
                "METRIK ANALISIS": ["Harga Terakhir (IDR)", "Harga Tertinggi 24 Jam", "Harga Terendah 24 Jam", "Total Volume (Rp)"],
                tk1: [f"Rp {int(data1.get('last',0)):,.0f}", f"Rp {int(data1.get('high',0)):,.0f}", f"Rp {int(data1.get('low',0)):,.0f}", f"Rp {float(data1.get('vol_idr',0))/1e9:,.1f} M"],
                tk2: [f"Rp {int(data2.get('last',0)):,.0f}", f"Rp {int(data2.get('high',0)):,.0f}", f"Rp {int(data2.get('low',0)):,.0f}", f"Rp {float(data2.get('vol_idr',0))/1e9:,.1f} M}"]
            })
            st.table(df_compare.set_index("METRIK ANALISIS"))
        else: st.error("Salah satu koin tidak ditemukan di pasar Indodax.")


elif menu == "🌐 PETA KRIPTO":
    st.markdown(f"<h2 class='gradient-text'>Peta Dominasi Kripto Indodax</h2>", unsafe_allow_html=True)
    if st.button("Pantau Pergerakan Kripto Terkini", use_container_width=True):
        indo_tickers = get_indodax_tickers()
        coin_data = []
        for pair, data in indo_tickers.items():
            if pair.endswith('_idr'):
                try:
                    c = pair.replace('_idr', '').upper()
                    last_p = float(data.get('last', 0))
                    low_p = float(data.get('low', last_p))
                    vol_rp = float(data.get('vol_idr', 0))
                    if vol_rp > 500_000_000:
                        chg_pct = ((last_p - low_p) / low_p * 100) if low_p > 0 else 0
                        coin_data.append({"Koin": c, "Perubahan (%)": round(chg_pct, 2)})
                except: pass
        if coin_data:
            df_sec = pd.DataFrame(coin_data).sort_values(by="Perubahan (%)", ascending=False).head(10)
            fig_sec = px.bar(df_sec, x="Koin", y="Perubahan (%)", color="Perubahan (%)", color_continuous_scale=["#EF4444", "#1E293B", "#10B981"])
            fig_sec.update_layout(template="plotly_white", height=400)
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
            
            st.markdown(f"""<div class='dash-box' style='border-left: 4px solid {ihsg_color}; padding: 20px;'>
                <p class='text-muted' style='margin:0; font-weight:600;'>IHSG (HARGA SAHAM GABUNGAN)</p>
                <h2 style='margin:5px 0; color:{ihsg_color}; font-family:"JetBrains Mono";'>{ihsg_last:,.2f} <span style='font-size:1rem;'>({'+' if ihsg_pct>0 else ''}{ihsg_pct:.2f}%)</span></h2>
                <p style='margin:0; font-size:14px; color:#0F172A;'>Status Pasar Terakhir: <span class='{badge_ihsg}'>{ihsg_status}</span></p>
            </div>""", unsafe_allow_html=True)
            
            try:
                if len(ihsg_data) >= 7:
                    spark_y = ihsg_data.tail(7).values.flatten()
                    spark_x = ihsg_data.tail(7).index
                    fig_spark = go.Figure(go.Scatter(x=spark_x, y=spark_y, mode='lines', line=dict(color=ihsg_color, width=3)))
                    fig_spark.update_layout(height=60, margin=dict(l=0, r=0, t=0, b=0), xaxis=dict(visible=False), yaxis=dict(visible=False), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
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
                st.markdown(f"""<div class='dash-box' style='padding: 20px;'>
                    <p class='text-muted' style='margin:0 0 15px 0; text-align:center; font-weight:600;'>📊 MARKET BREADTH (KESEHATAN PASAR)</p>
                    <div style='display:flex; justify-content:space-around;'>
                        <div style='text-align:center;'><h2 class='text-green' style='margin:0;'>{up}</h2><span class='text-muted'>Naik 📈</span></div>
                        <div style='text-align:center;'><h2 style='margin:0; color:#64748B;'>{flat}</h2><span class='text-muted'>Mandek ➖</span></div>
                        <div style='text-align:center;'><h2 class='text-red' style='margin:0;'>{down}</h2><span class='text-muted'>Turun 📉</span></div>
                    </div>
                </div>""", unsafe_allow_html=True)
        except: pass


elif menu == "🏎️ STRATEGY SCANNER":
    st.markdown(f"<h2 class='gradient-text'>Strategy Scanner (Crossover)</h2>", unsafe_allow_html=True)
    try:
        df_saham = pd.read_excel("daftar_saham.xlsx")
        watchlist = [t.strip() + ".JK" for t in df_saham['Kode'].dropna().astype(str).tolist()]
    except: watchlist = []

    if st.button("Mulai Cari Sinyal", use_container_width=True):
        with st.spinner(f"Menganalisis perpaduan Tren..."):
            results = get_trend_signals(watchlist)
            if results:
                for res in results:
                    st.markdown(f"<div class='dash-box' style='border-left: 4px solid {res['color']}; padding: 15px;'><span class='badge-green'>{res['status']}</span><p style='margin:8px 0 0 0;'>Saham: <b>{res['ticker']}</b> | Harga: Rp {res['price']:,.0f}</p></div>", unsafe_allow_html=True)
            else: st.info("Belum ada perpotongan tren yang signifikan hari ini.")


elif menu == "⭐ WATCHLIST FAVORIT":
    st.markdown(f"<h2 class='gradient-text'>Watchlist Pribadi</h2>", unsafe_allow_html=True)
    my_wl = get_watchlist(user_now)
    c_add, c_del = st.columns(2)
    with c_add:
        new_wl = st.text_input("Tambah Kode Saham").upper()
        if st.button("Simpan Saham", use_container_width=True):
            if new_wl: add_watchlist(user_now, f"{new_wl}.JK"); st.success("Ditambahkan!"); st.rerun()
    with c_del:
        if my_wl:
            del_wl = st.selectbox("Hapus Daftar", [t.replace(".JK","") for t in my_wl])
            if st.button("Hapus Saham", use_container_width=True):
                remove_watchlist(user_now, f"{del_wl}.JK"); st.warning("Dihapus!"); st.rerun()


elif menu == "🎯 AUTO SUP/RES":
    st.markdown(f"<h2 class='gradient-text'>Auto Support & Resistance</h2>", unsafe_allow_html=True)
    tk_pivot = st.text_input("Masukkan Kode Saham", value="BBRI").upper().strip()
    if st.button("Analisis Batas Harga", width="stretch"):
        full_tk = f"{tk_pivot}.JK" if not tk_pivot.endswith(".JK") else tk_pivot
        df_piv = yf.download(full_tk, period="1mo", interval="1d", progress=False).dropna()
        if not df_piv.empty and len(df_piv) >= 20:
            if isinstance(df_piv.columns, pd.MultiIndex): df_piv.columns = df_piv.columns.get_level_values(0)
            r_high, r_low, r_close = float(df_piv['High'][-20:].max()), float(df_piv['Low'][-20:].min()), float(df_piv['Close'].iloc[-1])
            pivot = (r_high + r_low + r_close) / 3
            r1, s1 = (2 * pivot) - r_low, (2 * pivot) - r_high
            
            c1, c2, c3 = st.columns(3)
            c1.metric("🔴 RESISTANCE 1", f"Rp {r1:,.0f}")
            c2.metric("🔵 TITIK PIVOT", f"Rp {pivot:,.0f}")
            c3.metric("🟢 SUPPORT 1", f"Rp {s1:,.0f}")


elif menu == "📅 SIKLUS MUSIMAN":
    st.markdown(f"<h2 class='gradient-text'>Siklus Musiman (Seasonality)</h2>", unsafe_allow_html=True)
    tk_season = st.text_input("Ketik Kode Saham", value="BBCA").upper().strip()
    if st.button("Analisis Data 5 Tahun", width="stretch"):
        full_tk = f"{tk_season}.JK" if not tk_season.endswith(".JK") else tk_season
        df_season = yf.download(full_tk, period="5y", interval="1mo", progress=False)
        if not df_season.empty:
            if isinstance(df_season.columns, pd.MultiIndex): df_season.columns = df_season.columns.get_level_values(0)
            df_season['Bulan'] = df_season.index.month
            df_season['Return %'] = df_season['Close'].pct_change() * 100
            monthly_stats = df_season.dropna().groupby('Bulan')['Return %'].agg(Rata2='mean', WinRate=lambda x: (x > 0).mean()*100).reset_index()
            fig = px.bar(monthly_stats, x='Bulan', y='WinRate', color='WinRate', color_continuous_scale=["#EF4444", "#16A34A"])
            st.plotly_chart(fig, use_container_width=True)


elif menu == "📟 CEK FUNDAMENTAL":
    st.markdown(f"<h2 class='gradient-text'>Cek Laporan Fundamental</h2>", unsafe_allow_html=True)
    target_f = st.text_input("Ketik Kode Saham", value="BBCA").upper().strip()
    if st.button("Periksa Emiten", width="stretch"):
        info = yf.Ticker(f"{target_f}.JK").info
        c1, c2, c3 = st.columns(3)
        c1.metric("P/E RATIO", f"{info.get('trailingPE', 0):,.2f}x")
        c2.metric("PBV RATIO", f"{info.get('priceToBook', 0):,.2f}x")
        c3.metric("ROE (Profit)", f"{(info.get('returnOnEquity', 0) or 0)*100:.2f}%")


elif menu == "💰 PEMBURU DIVIDEN":
    st.markdown(f"<h2 class='gradient-text'>Pemburu Dividen</h2>", unsafe_allow_html=True)
    div_tk = st.text_input("Ketik Kode Saham", value="ITMG").upper().strip()
    if st.button("Lacak Riwayat Dividen", width="stretch"):
        t_obj = yf.Ticker(f"{div_tk}.JK")
        st.metric("YIELD TAHUNAN", f"{(t_obj.info.get('dividendYield', 0) or 0)*100:.2f}%")


elif menu == "🧬 KORELASI SAHAM":
    st.markdown(f"<h2 class='gradient-text'>Korelasi Silang Saham</h2>", unsafe_allow_html=True)
    input_tkrs = st.text_input("MASUKKAN KODE SAHAM (KOMA)", value="BBCA, BBRI, TLKM")
    if st.button("Kalkulasi Matriks", width="stretch"):
        raw_list = [t.strip().upper() + ".JK" for t in input_tkrs.split(",")]
        data_corr = yf.download(raw_list, period="6mo", interval="1d", progress=False)['Close'].dropna()
        fig = px.imshow(data_corr.corr(), text_auto=True, color_continuous_scale="RdBu_r")
        st.plotly_chart(fig, use_container_width=True)


elif menu == "🏛️ JEJAK BANDAR":
    st.markdown(f"<h2 class='gradient-text'>Jejak Institusi & Bandar</h2>", unsafe_allow_html=True)
    ff_tk = st.text_input("Ketik Kode Saham", value="BBRI").upper().strip()
    if st.button("Lacak Arus Masuk Keluar", width="stretch"):
        df_ff = yf.download(f"{ff_tk}.JK", period="3mo", interval="1d", progress=False).dropna()
        if not df_ff.empty:
            if isinstance(df_ff.columns, pd.MultiIndex): df_ff.columns = df_ff.columns.get_level_values(0)
            mult = ((df_ff['Close'] - df_ff['Low']) - (df_ff['High'] - df_ff['Close'])) / (df_ff['High'] - df_ff['Low'] + 1e-9)
            cmf = (mult * df_ff['Volume']).rolling(20).sum() / df_ff['Volume'].rolling(20).sum()
            fig = px.area(x=df_ff.index, y=cmf)
            st.plotly_chart(fig, use_container_width=True)


elif menu == "📰 BERITA PASAR":
    st.markdown(f"<h2 class='gradient-text'>Financial Intelligence Center</h2>", unsafe_allow_html=True)
    feed = feedparser.parse(requests.get("https://news.google.com/rss/search?q=saham+indonesia&hl=id&gl=ID&ceid=ID:id").content)
    for entry in feed.entries[:8]:
        st.markdown(f"<div class='dash-box'><a href='{entry.link}' target='_blank'><b>{entry.title}</b></a></div>", unsafe_allow_html=True)


# =========================================================================
# =========================================================================
# 💼 MENU UNIVERSAL: OMNI-WALLET & KALKULATOR (SAHAM + KRIPTO FIX 100% IDR)
# =========================================================================
# =========================================================================

elif menu == "💼 DOMPET TRADING":
    st.markdown(f"<h2 class='gradient-text'>Dompet Omni-Wallet & AI Jurnal</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Sistem Akumulasi Kekayaan Pintar (Saham + Kripto 100% Rupiah):**
        * **Saham:** Ketik kodenya (`BBCA`), Beli & Live dalam **Rupiah**, Satuan **Lot**.
        * **Kripto Indodax:** Ketik kodenya (`CEL`, `BTC`, `PEPE`), Beli & Live otomatis 100% **Rupiah**, Satuan **Unit**.
        """)
        
    c_title, c_toggle = st.columns([3, 1])
    show_saldo = c_toggle.checkbox("👁️ Tampilkan Saldo", value=False)
    format_privacy = lambda v: f"Rp {v:,.0f}" if show_saldo else "Rp *****"

    tab1, tab2, tab3 = st.tabs(["📈 KEPEMILIKAN ASET", "📜 RIWAYAT", "📊 AUDIT AI JURNAL"])
    
    with tab1:
        with st.expander("➕ DAFTARKAN PEMBELIAN ASET BARU", expanded=False):
            with st.form("form_add_portfolio", clear_on_submit=True):
                c1, c2 = st.columns(2)
                t_in = c1.text_input("Kode Saham/Kripto (Cth: BBCA atau CEL/BTC)").upper().strip()
                
                # Cek apakah kode yang diketik pengguna adalah Kripto
                indo_tickers_check = get_indodax_tickers()
                clean_check = t_in.lower() + "_idr"
                is_crypto_input = clean_check in indo_tickers_check
                
                label_satuan = "Besaran Koin/Unit?" if is_crypto_input else "Besaran Lot?"
                step_val = 0.0001 if is_crypto_input else 1.0
                fmt_val = "%.4f" if is_crypto_input else "%.0f"
                
                l_in = c2.number_input(label_satuan, min_value=0.000001, value=1.0, step=step_val, format=fmt_val)
                c3, c4 = st.columns(2)
                p_in = c3.number_input("Harga Dasar Beli (Rp)", min_value=1.0, value=1000.0, step=1.0, format="%.0f")
                strat_in = c4.selectbox("Faktor Justifikasi Beli?", ["Golden Cross MA", "Breakout Resistance", "Serok Bawah (Support)", "Ikut Berita", "Fundamental Bagus", "Feeling / FOMO"])
                
                if st.form_submit_button("MASUKKAN DALAM SISTEM", width="stretch"):
                    if t_in and p_in > 0: 
                        add_to_portfolio(user_now, t_in, p_in, l_in, 0, 0, strat_in)
                        st.success("Aset Berhasil Tersimpan di Cloud!"); st.rerun()

        df_p = get_user_portfolio(user_now, role)
        if not df_p.empty:
            indo_tickers = get_indodax_tickers()
            
            # Tarik harga live saham dari YF
            saham_tickers = [f"{t}.JK" for t in df_p['ticker'].unique() if (f"{t.lower()}_idr" not in indo_tickers)]
            live_prices_saham = {}
            if saham_tickers:
                try:
                    df_dl = yf.download(saham_tickers, period="5d", progress=False, threads=True)['Close']
                    for st_tk in saham_tickers:
                        try:
                            s = df_dl[st_tk].dropna() if isinstance(df_dl, pd.DataFrame) else df_dl.dropna()
                            if not s.empty: live_prices_saham[st_tk] = float(s.iloc[-1])
                        except: pass
                except: pass

            def calc_omni_active_idr(row):
                tk_asli = row['ticker'].strip().upper()
                clean_t = tk_asli.lower() + "_idr"
                is_crypto = clean_t in indo_tickers
                
                bp = float(row['buy_price'])
                lots = float(row['lots'])
                
                if is_crypto:
                    # Ambil Harga Live 100% IDR dari Indodax
                    curr_price = float(indo_tickers[clean_t].get('last', bp))
                    cost_rp = bp * lots
                    val_rp = curr_price * lots
                else:
                    # Ambil Harga Live Saham Rupiah dari YF
                    tk_yf = f"{tk_asli}.JK"
                    curr_price = float(live_prices_saham.get(tk_yf, bp))
                    cost_rp = bp * lots * 100
                    val_rp = curr_price * lots * 100
                    
                pnl_rp = val_rp - cost_rp
                return pd.Series([curr_price, cost_rp, val_rp, pnl_rp, is_crypto])

            df_p[['Live_Rp', 'Cost_IDR', 'Value_IDR', 'PnL_IDR', 'Is_Crypto']] = df_p.apply(calc_omni_active_idr, axis=1)
            t_inv_rp, t_pl_rp = df_p['Cost_IDR'].sum(), df_p['PnL_IDR'].sum()
            
            m1, m2, m3 = st.columns(3)
            m1.metric("TOTAL MODAL (Rp)", format_privacy(t_inv_rp))
            m2.metric("TOTAL CUAN/RUGI (Rp)", format_privacy(t_pl_rp), f"{(t_pl_rp/t_inv_rp*100 if t_inv_rp!=0 else 0):.2f}%" if show_saldo else "*****")
            m3.metric("TOTAL KEKAYAAN (Rp)", format_privacy(t_inv_rp + t_pl_rp))

            st.markdown("---")
            for i, row in df_p.iterrows():
                strat_label = row.get('strategy', 'Bebas')
                is_cr = row['Is_Crypto']
                satuan = "Unit" if is_cr else "Lot"
                
                bp_val = float(row['buy_price'])
                live_val = float(row['Live_Rp'])
                pnl_val = float(row['PnL_IDR'])
                
                pct_val = (pnl_val / row['Cost_IDR'] * 100) if row['Cost_IDR'] > 0 else 0
                sign_str = "+" if pnl_val > 0 else ""
                
                # Format Judul Bersih Tanpa Desimal Panjang
                fmt_qty = f"{row['lots']:.4f}" if is_cr else f"{row['lots']:.0f}"
                icon = "🪙" if is_cr else "🏢"
                title_text = f"{icon} {row['ticker']} | {fmt_qty} {satuan} | Beli: Rp {bp_val:,.0f} | Live: Rp {live_val:,.0f} | Profit: {sign_str}Rp {pnl_val:,.0f} ({sign_str}{pct_val:.2f}%)"

                with st.expander(title_text):
                    st.markdown(f"<span class='badge-blue'>Kategori: {strat_label}</span>", unsafe_allow_html=True)
                    st.write("")
                    c_price, c_lots, c_btn = st.columns([2, 2, 1])
                    
                    s_price = c_price.number_input("Eksekusi Jual di Harga (Rp)", value=live_val, step=1.0, format="%.0f", key=f"s_prc_{row['id']}")
                    s_lots = c_lots.number_input(f"Berapa {satuan} Dilepas?", min_value=0.000001, max_value=float(row['lots']), value=float(row['lots']), step=(0.01 if is_cr else 1.0), format=("%.4f" if is_cr else "%.0f"), key=f"s_lot_{row['id']}")
                    
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
                    c_t.write(f"Avg Beli: Rp {h_row['buy_price']:,.0f} | Avg Jual: Rp {h_row['sell_price']:,.0f} | Pelepasan: {h_row['lots']} | Profit: {format_privacy(h_row['pnl'])}")
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


elif menu == "🧮 KALKULATOR TRADING":
    st.markdown(f"<h2 class='gradient-text'>Kalkulator Manajemen Risiko</h2>", unsafe_allow_html=True)
    tab_risk, tab_avg, tab_comp, tab_kelly = st.tabs(["🛡️ KALK. RISIKO", "🛟 AVERAGING DOWN", "📈 JALUR 1 MILIAR", "⚖️ KELLY CRITERION"])
    
    with tab_risk:
        with st.form("risk_calc_form"):
            c1, c2 = st.columns(2)
            capital = c1.number_input("Modal Disiapkan (Rp)", min_value=100.0, value=10000000.0, step=50000.0)
            risk_pct = c2.number_input("Toleransi Rugi (%)", min_value=0.1, max_value=10.0, value=2.0, step=0.1)
            c3, c4 = st.columns(2)
            entry_p = c3.number_input("Rencana Beli (Rp)", min_value=1.0, value=5000.0)
            stop_loss_p = c4.number_input("Batas Cut Loss (Rp)", min_value=1.0, value=4800.0)
            calc_btn = st.form_submit_button("Hitung Lot/Unit Aman", width="stretch")
            
        if calc_btn:
            max_risk_idr = capital * (risk_pct / 100)
            risk_per_share = entry_p - stop_loss_p
            total_lots = math.floor((max_risk_idr / risk_per_share) / 100)
            actual_shares = total_lots * 100
            st.metric("BELI MAKSIMAL", f"{total_lots:,} Lot")


elif menu == "⚙️ USER MANAGEMENT":
    st.markdown(f"<h2 class='gradient-text'>Portal Administratif</h2>", unsafe_allow_html=True)
    df_u = conn_gs.read(worksheet="users", ttl=0)
    st.dataframe(df_u[['username', 'role', 'last_login', 'location']], use_container_width=True, hide_index=True)


elif menu == "🔒 KEAMANAN":
    st.markdown(f"<h2 class='gradient-text'>Keamanan Node Terminal</h2>", unsafe_allow_html=True)
    with st.form("p"):
        new_p = st.text_input("Ketikan Sandikunci Baru", type="password")
        if st.form_submit_button("SIMPAN SANDI", width="stretch"):
            if update_password_db(user_now, new_p): st.success("Sandi berhasil diperbarui!")

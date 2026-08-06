import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import time
import warnings
import os
import requests 
import pytz 
import math
import feedparser

# --- 0. CONFIG, THEME STATE & APP SETUP ---
warnings.filterwarnings("ignore", category=FutureWarning)
st.set_page_config(
    page_title="IDX WALLET TERMINAL", 
    page_icon="⚡", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Inisialisasi Tema (Dark/Light)
if "theme" not in st.session_state:
    st.session_state["theme"] = "dark"

is_dark = st.session_state["theme"] == "dark"

# Variabel Warna Dinamis
c_prim = "#00f0ff" if is_dark else "#0284c7"       # Cyan (Dark) / Blue (Light)
c_sec = "#78ff00" if is_dark else "#16a34a"        # Lime (Dark) / Green (Light)
c_bg_card = "rgba(15, 23, 42, 0.9)" if is_dark else "rgba(255, 255, 255, 0.95)"
c_text = "#ffffff" if is_dark else "#0f172a"
c_muted = "#94a3b8" if is_dark else "#64748b"
plot_theme = "plotly_dark" if is_dark else "plotly_white"

conn_gs = st.connection("gsheets", type=GSheetsConnection)

def get_visitor_info():
    providers = ['https://ipapi.co/json/', 'https://ipinfo.io/json', 'https://ifconfig.co/json']
    for url in providers:
        try:
            response = requests.get(url, timeout=3).json()
            ip = response.get('ip') or response.get('query', 'Unknown')
            city = response.get('city', 'Unknown')
            region = response.get('region', 'Unknown') or response.get('regionName', 'Unknown')
            if ip != 'Unknown': return ip, f"{city}, {region}"
        except: continue
    return "Mobile Node", "Cloud"

def update_login_info(u):
    ip, loc = get_visitor_info()
    tz = pytz.timezone('Asia/Jakarta') 
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    
    df = conn_gs.read(worksheet="users", ttl=0)
    for col in ['last_login', 'ip_address', 'location']:
        if col not in df.columns: df[col] = "" 
        df[col] = df[col].astype(str)
        
    idx = df.index[df['username'] == u].tolist()
    if idx:
        df.at[idx[0], 'last_login'] = now
        df.at[idx[0], 'ip_address'] = ip
        df.at[idx[0], 'location'] = loc
        conn_gs.update(worksheet="users", data=df)

def get_sidebar_log(u):
    df = conn_gs.read(worksheet="users", ttl=60)
    user_data = df[df['username'] == u]
    if not user_data.empty:
        return user_data.iloc[0]['last_login'], user_data.iloc[0]['ip_address'], user_data.iloc[0]['location']
    return "-", "-", "-"

def check_login_db(u, p):
    df = conn_gs.read(worksheet="users", ttl=0)
    if df.empty: return None
    df['username'] = df['username'].astype(str).str.strip()
    df['password'] = df['password'].astype(str).str.strip()
    user_match = df[(df['username'] == str(u).strip()) & (df['password'] == str(p).strip())]
    if not user_match.empty: return str(user_match.iloc[0]['role'])
    return None

def add_to_portfolio(u, t, p, l, tp, cl):
    df = conn_gs.read(worksheet="portfolio", ttl=0)
    next_id = 1
    if not df.empty and 'id' in df.columns:
        valid_ids = pd.to_numeric(df['id'], errors='coerce').dropna()
        if not valid_ids.empty: next_id = int(valid_ids.max()) + 1

    new_row = pd.DataFrame([{'id': next_id, 'username': u, 'ticker': t.upper().strip(), 'buy_price': float(p), 'lots': int(l), 'tp_price': float(tp), 'cl_price': float(cl), 'date': datetime.now(pytz.timezone('Asia/Jakarta')).strftime("%Y-%m-%d")}])
    df = pd.concat([df, new_row], ignore_index=True)
    conn_gs.update(worksheet="portfolio", data=df)

def sell_position(u, row_id, ticker, buy_p, sell_p, total_lots, sold_lots):
    pnl = (sell_p - buy_p) * sold_lots * 100
    df_port = conn_gs.read(worksheet="portfolio", ttl=0)
    idx = df_port.index[df_port['id'] == row_id].tolist()
    
    remaining_lots = total_lots - sold_lots
    if idx:
        if remaining_lots > 0:
            df_port.at[idx[0], 'lots'] = remaining_lots
            msg = f"✅ PARTIAL_SELL: {sold_lots} Lot {ticker} Terjual!"
        else:
            df_port = df_port.drop(idx[0]).reset_index(drop=True)
            msg = f"✅ FULL_SELL: {sold_lots} Lot {ticker} Terjual!"
        conn_gs.update(worksheet="portfolio", data=df_port)
    else: msg = "Data portfolio tidak ditemukan!"

    df_hist = conn_gs.read(worksheet="history", ttl=0)
    next_hist_id = 1
    if not df_hist.empty and 'id' in df_hist.columns:
        valid_ids = pd.to_numeric(df_hist['id'], errors='coerce').dropna()
        if not valid_ids.empty: next_hist_id = int(valid_ids.max()) + 1
            
    new_hist = pd.DataFrame([{'id': next_hist_id, 'username': u, 'ticker': ticker, 'buy_price': float(buy_p), 'sell_price': float(sell_p), 'lots': int(sold_lots), 'pnl': float(pnl), 'date': datetime.now(pytz.timezone('Asia/Jakarta')).strftime("%Y-%m-%d")}])
    df_hist = pd.concat([df_hist, new_hist], ignore_index=True)
    conn_gs.update(worksheet="history", data=df_hist)
    return msg

def get_user_portfolio(u, r):
    df = conn_gs.read(worksheet="portfolio", ttl=0)
    if df.empty or len(df) == 0: return pd.DataFrame()
    df['id'], df['lots'], df['buy_price'] = pd.to_numeric(df['id'], errors='coerce'), pd.to_numeric(df['lots'], errors='coerce'), pd.to_numeric(df['buy_price'], errors='coerce')
    if r != 'admin': df = df[df['username'] == u]
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


# --- 1. DYNAMIC CSS (DARK/LIGHT MODE & HUGE TOUCH MENU) ---
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;700&family=Orbitron:wght@600;800;900&display=swap');

/* Base App Theme */
.stApp {{
    background: {'#090c15' if is_dark else '#f4f6f9'};
    background-image: {'radial-gradient(circle at 50% -20%, rgba(0, 240, 255, 0.1) 0%, transparent 60%)' if is_dark else 'none'};
    font-family: 'Plus Jakarta Sans', sans-serif;
    color: {'#f1f5f9' if is_dark else '#0f172a'};
}}
header {{background: transparent !important;}}
[data-testid="stHeaderActionElements"], .stDeployButton, #MainMenu {{ display: none !important; }}

h1, h2, h3 {{ font-family: 'Orbitron', sans-serif; letter-spacing: 0.5px; }}
h1 {{
    font-weight: 800; font-size: 1.6rem;
    background: linear-gradient(135deg, {c_prim} 0%, {c_sec} 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}}
h2 {{ color: {c_prim}; font-weight: 700; font-size: 1.2rem; margin-bottom: 20px;}}

/* Card, Expander & Forms */
div[data-testid="stForm"], div[data-testid="stExpander"], .stDataFrame {{
    background: {c_bg_card} !important;
    border: {'none' if is_dark else '1px solid rgba(0,0,0,0.05)'} !important;
    box-shadow: {'0 10px 30px rgba(0, 0, 0, 0.5)' if is_dark else '0 8px 25px rgba(0, 0, 0, 0.05)'};
    border-radius: 20px !important; 
    padding: 15px !important; backdrop-filter: blur(15px);
    margin-bottom: 15px;
}}
div[data-testid="stForm"] label p, div[data-testid="stExpander"] label p {{
    font-family: 'Orbitron', sans-serif !important; color: {c_sec} !important; font-size: 0.7rem !important;
}}
div[data-testid="stForm"] input {{
    background: {'rgba(0, 0, 0, 0.3)' if is_dark else '#ffffff'} !important;
    border: {'1px solid rgba(0, 240, 255, 0.2)' if is_dark else '1px solid #cbd5e1'} !important;
    color: {'#00f0ff' if is_dark else '#0284c7'} !important; 
    font-family: 'JetBrains Mono', monospace !important;
    border-radius: 12px; height: 50px; font-size: 16px;
}}

/* Metrics */
div[data-testid="stMetric"] {{
    background: {'linear-gradient(145deg, rgba(15, 23, 42, 0.9), rgba(9, 12, 21, 0.9))' if is_dark else '#ffffff'} !important;
    border: {'1px solid rgba(255, 255, 255, 0.05)' if is_dark else '1px solid #e2e8f0'} !important;
    border-radius: 20px !important; backdrop-filter: blur(10px);
    padding: 20px !important; text-align: center;
    box-shadow: {'0 8px 20px rgba(0,0,0,0.4)' if is_dark else '0 4px 15px rgba(0,0,0,0.05)'};
}}
[data-testid="stMetricValue"] {{ font-family: 'JetBrains Mono', monospace !important; font-size: 1.6rem !important; color: {c_sec} !important; }}
[data-testid="stMetricLabel"] {{ color: {c_muted} !important; font-weight: 600; text-transform: uppercase; font-size: 0.7rem; }}

/* Sidebar & ENLARGED MENU UI */
[data-testid="stSidebar"] {{ background: {'#050810' if is_dark else '#ffffff'}; border-right: 1px solid {'rgba(255,255,255,0.05)' if is_dark else '#e2e8f0'}; }}

div[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label {{
    background: {'rgba(255,255,255,0.03)' if is_dark else '#f1f5f9'} !important; 
    border: none !important;
    border-radius: 18px !important; 
    padding: 16px 20px !important; /* UKURAN TOMBOL MENU BESAR */
    margin-bottom: 12px !important; /* JARAK ANTAR MENU LUAS */
}}
div[data-testid="stSidebar"] .stRadio label p {{
    font-family: 'Orbitron', sans-serif !important; 
    font-size: 1.05rem !important; /* UKURAN TEKS MENU BESAR */
    font-weight: 600 !important;
    color: {'#94a3b8' if is_dark else '#475569'} !important; 
}}
div[data-testid="stSidebar"] .stRadio div[role="radiogroup"] [aria-checked="true"] {{
    background: {'rgba(0, 240, 255, 0.15)' if is_dark else '#e0f2fe'} !important;
    border-left: 6px solid {c_prim} !important;
}}
div[data-testid="stSidebar"] .stRadio div[role="radiogroup"] [aria-checked="true"] p {{ 
    color: {'#ffffff' if is_dark else '#0369a1'} !important; 
    font-weight: 800 !important; 
}}

/* Tombol Aksi */
.stButton>button {{
    background: linear-gradient(135deg, {c_prim}, {c_sec});
    color: {'#000000' if is_dark else '#ffffff'} !important;
    border: none !important;
    border-radius: 50px !important; 
    font-family: 'Orbitron', sans-serif; font-weight: 800; font-size: 0.85rem;
    min-height: 52px; width: 100%; 
    box-shadow: {'0 6px 15px rgba(0, 240, 255, 0.2)' if is_dark else '0 6px 15px rgba(2, 132, 199, 0.3)'};
}}
</style>
""", unsafe_allow_html=True)


# --- 2. AUTHENTICATION ---
if not st.session_state["auth"]["logged_in"]:
    _, col2, _ = st.columns([0.05, 1, 0.05])
    with col2:
        st.markdown(f"<div style='text-align:center; padding:40px 0;'><h1 style='font-size:2.2rem; margin-bottom:0;'>IDX WALLET</h1><p style='color:{c_prim}; letter-spacing:3px; font-family:Orbitron; font-size:0.7rem;'>MOBILE QUANT TERMINAL</p></div>", unsafe_allow_html=True)
        with st.form("login_form"):
            u = st.text_input("NODE ID").strip()
            p = st.text_input("ACCESS KEY", type="password")
            st.write("")
            if st.form_submit_button("LOGIN WALLET", width="stretch"):
                role = check_login_db(u, p)
                if role:
                    update_login_info(u)
                    st.session_state["auth"] = {"logged_in": True, "user": u, "role": role}
                    st.rerun()
                else: st.error("Akses Ditolak!")
    st.stop()


# --- 3. DATA ENGINE & MARKET LOGIC ---
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

def run_scan(tickers, mode):
    tickers = list(set(tickers))
    results = []
    
    if mode == "Santai": min_chg, min_rsi, min_val, vol_m = 1.5, 45, 100_000_000, 1.1
    elif mode == "Profesional": min_chg, min_rsi, min_val, vol_m = 2.5, 55, 1_000_000_000, 1.4
    elif mode == "Pro": min_chg, min_rsi, min_val, vol_m = 4.0, 60, 2_000_000_000, 1.8
    else: min_chg, min_rsi, min_val, vol_m = 2.0, 50, 500_000_000, 1.3

    progress = st.progress(0, text="📡 Syncing Exchange Data...")
    try:
        data = yf.download(tickers, period="2mo", interval="1d", group_by="ticker", threads=True, progress=False)
    except:
        st.error("Failed to connect to market data.")
        return pd.DataFrame()

    total = len(tickers)
    for i, t in enumerate(tickers):
        try:
            progress.progress(int((i + 1) / total * 100), text=f"🔍 Analyzing {t}")
            df = data[t].copy() if len(tickers) > 1 else data.copy()
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            if df.empty or len(df) < 20: continue

            c_now, c_prev = df['Close'].iloc[-1], df['Close'].iloc[-2]
            if pd.isna(c_now) or pd.isna(c_prev): continue

            chg = ((c_now - c_prev) / c_prev) * 100
            val_tr = df['Volume'].iloc[-1] * c_now
            ma20 = df['Close'].rolling(20).mean().iloc[-1]
            
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rsi = 100 - (100 / (1 + (gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] != 0 else 0)))

            high_20 = df['High'].rolling(20).max().iloc[-2]
            vol_avg = df['Volume'].rolling(20).mean().iloc[-1]
            is_breakout = (c_now > high_20) and (df['Volume'].iloc[-1] > vol_avg * vol_m)

            if chg < min_chg or val_tr < min_val: continue

            tr1 = df['High'] - df['Low']
            tr2 = (df['High'] - df['Close'].shift()).abs()
            tr3 = (df['Low'] - df['Close'].shift()).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr_val = tr.rolling(14).mean().iloc[-1]
            if pd.isna(atr_val): atr_val = c_now * 0.03
                
            results.append({
                "TICKER": t.replace(".JK", ""), "LAST": int(c_now), "CHG%": round(chg, 2),
                "RSI": round(rsi, 1), "VAL(M)": round(val_tr / 1_000_000, 1), 
                "AI_SCORE": round((chg * 0.4) + (rsi * 0.2) + ((val_tr / 1e9) * 0.2) + (10 if is_breakout else 0), 2),
                "BREAKOUT": "YES" if is_breakout else "NO",
                "REKOMENDASI": "🚀 BUY" if chg > 4 else "💎 HOLD",
                "TP 1": int(c_now + (1.5 * atr_val)), "TP 2": int(c_now + (2.5 * atr_val)), "EXIT/CL": int(c_now - (1.0 * atr_val)), "FULL": t
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
            df['MA20'] = df['Close'].rolling(20).mean()
            df['MA50'] = df['Close'].rolling(50).mean()
            last_ma20, last_ma50 = df['MA20'].iloc[-1], df['MA50'].iloc[-1]
            prev_ma20, prev_ma50 = df['MA20'].iloc[-2], df['MA50'].iloc[-2]
            current_price = df['Close'].iloc[-1]
            
            if prev_ma20 < prev_ma50 and last_ma20 > last_ma50:
                signals.append({"ticker": ticker.replace(".JK", ""), "status": "GOLDEN CROSS", "price": current_price, "color": c_sec})
            elif prev_ma20 > prev_ma50 and last_ma20 < last_ma50:
                signals.append({"ticker": ticker.replace(".JK", ""), "status": "DEAD CROSS", "price": current_price, "color": "#ff4b4b"})
        except: continue
    return signals

def draw_mobile_cards(df):
    for _, row in df.iterrows():
        chg = row.get('CHG%', 0)
        chg_color = c_sec if chg > 0 else "#ff4b4b"
        val_last  = row.get('LAST', '-')
        val_entry = row.get('ENTRY', row.get('Entry', val_last)) 
        val_tp1   = row.get('TP 1', '-')
        val_tp2   = row.get('TP 2', '-')
        val_cl    = row.get('EXIT/CL', '-')

        st.markdown(f"""
        <div style="background: {c_bg_card}; border: 1px solid {'rgba(0, 240, 255, 0.15)' if is_dark else 'rgba(0,0,0,0.05)'}; 
                    border-radius: 20px; padding: 18px; margin-bottom: 12px; box-shadow: 0 5px 15px rgba(0,0,0,0.1);">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(128,128,128,0.2); padding-bottom: 10px;">
                <b style="font-size: 1.2rem; color: {c_prim}; font-family: Orbitron;">{row.get('TICKER','-')}</b>
                <div style="text-align: right;">
                    <div style="font-size: 1.1rem; color: {c_text}; font-weight: bold;">Rp {val_last}</div>
                    <div style="color: {chg_color}; font-size: 0.8rem; font-weight: bold;">{'+' if chg>0 else ''}{chg}%</div>
                </div>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 5px; margin-top: 15px; font-size: 0.75rem; text-align: center;">
                <div style="background: rgba(128,128,128,0.1); padding: 8px; border-radius: 10px;">
                    <div style="color: {c_muted};">ENTRY</div><b style="color:{c_prim};">{val_entry}</b>
                </div>
                <div style="background: rgba(120,255,0,0.05); padding: 8px; border-radius: 10px;">
                    <div style="color: {c_muted};">TARGET</div><b style="color:{c_sec};">{val_tp1}</b>
                </div>
                <div style="background: rgba(255,75,75,0.05); padding: 8px; border-radius: 10px;">
                    <div style="color: {c_muted};">CUTLOSS</div><b style="color:#ff4b4b;">{val_cl}</b>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# --- 4. NAVIGATION & SIDEBAR ---
role = st.session_state["auth"]["role"]
user_now = st.session_state["auth"]["user"]
last_l, ip_l, loc_l = get_sidebar_log(user_now)

st.sidebar.markdown(f"""
    <div style='padding:18px; border:none; border-radius:20px; background:{c_bg_card}; margin-bottom:20px; box-shadow:0 4px 15px rgba(0,0,0,0.1);'>
        <h3 style='margin:0; color:{c_prim}; font-family:Orbitron; font-size:1rem;'>{user_now.upper()}</h3>
        <p style='margin:0; font-size:9px; color:{c_sec}; font-family:Orbitron; margin-top:4px;'>WALLET SECURED | {role.upper()}</p>
    </div>
    """, unsafe_allow_html=True)

if st.sidebar.button("🌓 GANTI TEMA (GELAP/TERANG)", use_container_width=True):
    st.session_state["theme"] = "light" if is_dark else "dark"
    st.rerun()
st.sidebar.write("---")

menu_list = [
    "SCANNER", "STRATEGY SCANNER", "WATCHLIST", "FUNDAMENTAL", 
    "TICKER COMPARISON", "SECTOR HEATMAP", "RISK CALCULATOR", 
    "DIVIDEND TRACKER", "CORRELATION MATRIX", "FOREIGN & BROKER FLOW", 
    "MARKET_NEWS", "MONEY MANAGEMENT", "SECURITY SETTINGS"
]
if role == "admin": 
    menu_list.insert(7, "USER MANAGEMENT")

menu = st.sidebar.radio("Menu", menu_list, label_visibility="collapsed")

st.sidebar.write("---")
if st.sidebar.button("🔒 KUNCI WALLET", use_container_width=True):
    st.session_state["auth"] = {"logged_in": False}
    st.rerun()


# --- 5. CONTENT AREA ---

if menu == "SCANNER":
    st.title("🛰️ AUTO SCANNER")
    with st.expander("📖 BUKU PANDUAN: CARA AMBIL POSISI", expanded=False):
        st.markdown("""
        * **AI Score:** Kekuatan momentum (di atas 5 berarti sangat kuat).
        * **TP 1 & TP 2 (Take Profit):** Antre jual di harga ini untuk bungkus cuan secara bertahap.
        * **EXIT/CL (Stop Loss):** Disiplin! Jual rugi seketika jika harga turun menyentuh level ini agar modal tidak nyangkut.
        """)

    if 'results' not in st.session_state: st.session_state.results = None
    tickers = load_tickers()
    
    mode_scan = st.radio("PILIH MODE SENSITIVITAS:", ["Santai", "Profesional", "Pro"], horizontal=True, label_visibility="collapsed")
    if st.button("⚡ MULAI SCAN PASAR", use_container_width=True):
        res = run_scan(tickers, mode_scan)
        if not res.empty: st.session_state.results = res; st.rerun()
        else: st.warning("Scan selesai: Belum ada saham yang memenuhi kriteria kuat saat ini.")

    if st.session_state.results is not None:
        df = st.session_state.results
        
        st.markdown(f"""
        <div style='background: rgba(128,128,128, 0.1); padding:12px; border-left:4px solid {c_prim}; margin-bottom:15px; border-radius:0 10px 10px 0;'>
            <span style='color:{c_prim}; font-family:Orbitron; font-weight:bold; font-size:0.8rem;'>🧠 QUANT AI STATUS: COMPLETE</span><br>
            <span style='font-size:0.75rem; color:{c_muted};'>📊 PROCESSED: {len(df)} STOCKS ANALYZED</span>
        </div>
        """, unsafe_allow_html=True)

        tab1, tab2, tab3 = st.tabs(["📱 KARTU", "📊 TABEL", "📈 CHART"])
        with tab1: draw_mobile_cards(df)
        with tab2: st.dataframe(df.drop(columns=['FULL'], errors='ignore'), use_container_width=True, hide_index=True)
        with tab3:
            sel_t = st.selectbox("PILIH SAHAM UNTUK GRAFIK", df['TICKER'].tolist())
            full_t = df[df['TICKER'] == sel_t]['FULL'].values[0]
            c_data = yf.download(full_t, period="6mo", interval="1d", progress=False)
            if not c_data.empty:
                c_data.columns = [c[0] if isinstance(c, tuple) else c for c in c_data.columns]
                c_data['MA20'], c_data['MA50'] = c_data['Close'].rolling(20).mean(), c_data['Close'].rolling(50).mean()
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=c_data.index, open=c_data['Open'], high=c_data['High'], low=c_data['Low'], close=c_data['Close'], name='Price'), row=1, col=1)
                fig.add_trace(go.Scatter(x=c_data.index, y=c_data['MA20'], line=dict(color=c_prim, width=1.5), name='MA 20'), row=1, col=1)
                fig.add_trace(go.Scatter(x=c_data.index, y=c_data['MA50'], line=dict(color=c_sec, width=1.5), name='MA 50'), row=1, col=1)
                colors = [c_sec if row['Close'] >= row['Open'] else '#ff4b4b' for index, row in c_data.iterrows()]
                fig.add_trace(go.Bar(x=c_data.index, y=c_data['Volume'], marker_color=colors, name='Volume'), row=2, col=1)
                fig.update_layout(template=plot_theme, height=420, margin=dict(l=0,r=0,t=10,b=0), xaxis_rangeslider_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)

elif menu == "STRATEGY SCANNER":
    st.title("⚡ STRATEGY SCANNER")
    with st.expander("📖 BUKU PANDUAN: SINYAL TREND", expanded=False):
        st.markdown("""
        Fitur ini otomatis mencari perpotongan garis rata-rata harga (MA).
        * 🟢 **Golden Cross (Peluang Beli):** Harga rata-rata 20 hari memotong ke atas 50 hari. Saham bersiap *uptrend*.
        * 🔴 **Dead Cross (Waspada):** Garis 20 hari memotong ke bawah. Momentum melemah, siap-siap jual.
        """)
    
    try:
        df_saham = pd.read_excel("daftar_saham.xlsx")
        watchlist = [t.strip() + ".JK" for t in df_saham['Kode'].dropna().astype(str).tolist()]
    except:
        st.error("File 'daftar_saham.xlsx' tidak ditemukan."); watchlist = []

    if st.button("🚀 SCAN SINYAL CROSSOVER", use_container_width=True) and watchlist:
        with st.spinner("Menganalisis ratusan saham..."):
            results = get_trend_signals(watchlist)
            if results:
                for res in results:
                    st.markdown(f"<div style='border: 1px solid {res['color']}; background: {c_bg_card}; padding: 18px; border-radius: 20px; margin-bottom: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);'><h3 style='color:{res['color']}; margin:0; font-family:Orbitron; font-size:1.1rem;'>{res['status']}!</h3><p style='margin:6px 0 0 0; color:{c_text}; font-size:0.9rem;'>{res['ticker']} <span style='color:{c_muted};'>| Last: Rp {res['price']:,.0f}</span></p></div>", unsafe_allow_html=True)
            else: st.info("Tidak ada sinyal saat ini.")

elif menu == "WATCHLIST":
    st.title("⭐ WATCHLIST FAVORIT")
    with st.expander("📖 BUKU PANDUAN: WATCHLIST", expanded=False):
        st.markdown("""
        Masukkan kode saham incaranmu ke sini (keranjang pantau). 
        Klik **SCAN WATCHLIST** untuk memeriksa apakah saham-saham di keranjangmu sedang ada momentum beli hari ini.
        """)
        
    my_wl = get_watchlist(user_now)
    with st.form("form_add_wl", clear_on_submit=True):
        new_wl = st.text_input("Ketik Kode Saham (Misal: BBCA)").upper()
        if st.form_submit_button("➕ TAMBAH KE FAVORIT"):
            if new_wl and f"{new_wl}.JK" not in my_wl: 
                add_watchlist(user_now, f"{new_wl}.JK"); st.success("Ditambahkan!"); st.rerun()
                
    if my_wl:
        st.write("### 🗑️ Hapus dari Daftar")
        with st.form("form_del_wl"):
            del_wl = st.selectbox("Pilih yang ingin dihapus", [t.replace(".JK","") for t in my_wl])
            if st.form_submit_button("HAPUS DARI DAFTAR"):
                remove_watchlist(user_now, f"{del_wl}.JK"); st.warning("Dihapus!"); st.rerun()
                
        st.markdown("---")
        if st.button("⚡ SCAN WATCHLIST SAYA", use_container_width=True):
            res_wl = run_scan(my_wl, "Santai")
            if not res_wl.empty: draw_mobile_cards(res_wl)
            else: st.info("Belum ada pergerakan momentum di saham favoritmu.")
    else: st.info("Watchlist kamu masih kosong.")

elif menu == "FUNDAMENTAL":
    st.title("📟 CEK FUNDAMENTAL")
    with st.expander("📖 BUKU PANDUAN: CARA BACA VALUASI", expanded=False):
        st.markdown("""
        * **Graham Value:** Estimasi harga wajar/murah sebuah saham. Jika harga pasar lebih rendah, berarti *Undervalued* (Diskon).
        * **ROE:** Semakin tinggi persenannya, semakin efisien perusahaan mencetak laba.
        """)
    
    with st.form("f_fund"):
        target_f = st.text_input("Ketik Kode Saham", value="BBCA").upper().strip()
        btn_analyze = st.form_submit_button("CEK KESEHATAN PERUSAHAAN")

    if btn_analyze:
        full_tk = f"{target_f}.JK" if not target_f.endswith(".JK") else target_f
        with st.spinner("Menarik data laporan keuangan..."):
            try:
                info = yf.Ticker(full_tk).info
                current_price = info.get('currentPrice') or info.get('previousClose', 1)
                eps, bvps, roe = info.get('trailingEps', 0), info.get('bookValue', 0), (info.get('returnOnEquity', 0) or 0) * 100
                graham = math.sqrt(22.5 * eps * bvps) if (eps > 0 and bvps > 0) else 0
                
                st.markdown(f"### 🏢 {info.get('longName', target_f)}")
                c1, c2 = st.columns(2)
                c1.metric("PE RATIO (Valuasi)", f"{info.get('trailingPE', 0):,.1f}x")
                c2.metric("ROE (Profitabilitas)", f"{roe:.1f}%")

                status = 'DI BAWAH HARGA WAJAR (MURAH) 🟢' if current_price < graham else 'DI ATAS HARGA WAJAR (MAHAL) 🔴'
                st.markdown(f"<div style='background:{c_bg_card}; padding:18px; border-radius:20px; border:1px solid {c_prim}; text-align:center; box-shadow:0 5px 15px rgba(0,0,0,0.1);'><p style='color:{c_muted}; font-size:10px; margin:0;'>HARGA WAJAR (GRAHAM)</p><h2 style='color:{c_sec}; margin:5px 0;'>Rp {graham:,.0f}</h2><p style='font-size:10px; color:{c_text}; margin:0;'>{status}</p></div>", unsafe_allow_html=True)
            except Exception as e: st.error("Data tidak ditemukan.")

elif menu == "TICKER COMPARISON":
    st.title("⚔️ ADU SAHAM (BATTLE)")
    with st.expander("📖 BUKU PANDUAN: ADU MEKANIK", expanded=False):
        st.markdown("""
        Bandingkan dua saham di sektor yang sama (misal: BBCA vs BBRI). 
        Pilih saham yang memiliki **PE & PBV lebih rendah** (lebih murah) tetapi memiliki **ROE lebih tinggi** (laba lebih efisien).
        """)
        
    with st.form("f_battle"):
        c1, c2 = st.columns(2)
        tk1 = c1.text_input("Saham 1", value="BBCA").upper().strip()
        tk2 = c2.text_input("Saham 2", value="BBRI").upper().strip()
        btn = st.form_submit_button("ADU SEKARANG")

    if btn:
        with st.spinner("Menghitung skor..."):
            try:
                i1, i2 = yf.Ticker(f"{tk1}.JK").info, yf.Ticker(f"{tk2}.JK").info
                get_val = lambda d, k: d.get(k, 0) or 0
                df_compare = pd.DataFrame({
                    "METRIK": ["Harga", "Valuasi (PE)", "Valuasi (PBV)", "Profit (ROE)", "Utang (DER)"],
                    tk1: [f"Rp {get_val(i1, 'currentPrice'):,.0f}", f"{get_val(i1, 'trailingPE'):,.1f}x", f"{get_val(i1, 'priceToBook'):,.1f}x", f"{get_val(i1, 'returnOnEquity')*100:.1f}%", f"{get_val(i1, 'debtToEquity'):,.1f}%"],
                    tk2: [f"Rp {get_val(i2, 'currentPrice'):,.0f}", f"{get_val(i2, 'trailingPE'):,.1f}x", f"{get_val(i2, 'priceToBook'):,.1f}x", f"{get_val(i2, 'returnOnEquity')*100:.1f}%", f"{get_val(i2, 'debtToEquity'):,.1f}%"]
                })
                st.dataframe(df_compare, use_container_width=True, hide_index=True)
            except: st.error("Gagal menarik data.")

elif menu == "SECTOR HEATMAP":
    st.title("🌐 PETA SEKTOR")
    with st.expander("📖 BUKU PANDUAN: ROTASI SEKTOR", expanded=False):
        st.markdown("""
        Uang besar selalu berputar antar sektor.
        * **Balok Hijau (Kanan):** Sektor sedang banyak diminati dan naik. Cocok untuk cari saham momentum.
        * **Balok Merah (Kiri):** Sektor sedang koreksi/dihindari.
        """)
    
    sectors = {
        "Bank": ["BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK"],
        "Energi": ["ADRO.JK", "PTBA.JK", "HRUM.JK", "MEDC.JK"],
        "Telko": ["TLKM.JK", "ISAT.JK", "EXCL.JK"],
        "Konsumer": ["ICBP.JK", "INDF.JK", "UNVR.JK", "AMRT.JK"]
    }
    
    if st.button("CEK ARUS SEKTOR HARI INI", use_container_width=True):
        with st.spinner("Memindai bursa..."):
            sector_data = []
            all_tickers = [t for lst in sectors.values() for t in lst]
            try:
                data = yf.download(all_tickers, period="5d", interval="1d", progress=False, group_by="ticker", threads=True)
                for sec_name, t_list in sectors.items():
                    sec_changes = []
                    for t in t_list:
                        try:
                            df_t = data[t] if len(all_tickers) > 1 else data
                            if isinstance(df_t.columns, pd.MultiIndex): df_t.columns = df_t.columns.get_level_values(0)
                            if not df_t.empty and len(df_t) >= 2:
                                chg = ((df_t['Close'].iloc[-1] - df_t['Close'].iloc[-2]) / df_t['Close'].iloc[-2]) * 100
                                sec_changes.append(chg)
                        except: continue
                    if sec_changes:
                        sector_data.append({"Sektor": sec_name, "Perubahan %": round(sum(sec_changes)/len(sec_changes), 2)})
            except: pass
            
            if sector_data:
                df_sec = pd.DataFrame(sector_data).sort_values(by="Perubahan %", ascending=False)
                fig = px.bar(df_sec, y="Sektor", x="Perubahan %", orientation='h', color="Perubahan %", color_continuous_scale=["#ff4b4b", c_muted, c_sec])
                fig.update_layout(template=plot_theme, height=300, margin=dict(l=0,r=0,t=10,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)

elif menu == "RISK CALCULATOR":
    st.title("🧮 KALKULATOR RISIKO")
    with st.expander("📖 BUKU PANDUAN: AMAN DARI BANGKRUT", expanded=False):
        st.markdown("""
        Jangan tebak-tebakan saat beli saham. 
        Gunakan fitur ini untuk mengetahui **Berapa Lot maksimal** yang boleh kamu beli agar modalmu tidak habis jika terpaksa harus *Cut Loss*. (Disarankan risiko per transaksi maksimal 1% - 2% dari modal).
        """)
    
    with st.form("risk_calc_form"):
        capital = st.number_input("Total Modal Kamu (Rp)", value=10000000, step=500000)
        risk_pct = st.number_input("Toleransi Rugi (%)", value=2.0, step=0.1)
        entry_p = st.number_input("Rencana Harga Beli", value=5000)
        stop_loss_p = st.number_input("Batas Harga Cut Loss", value=4800)
        
        calc_btn = st.form_submit_button("HITUNG BERAPA LOT HARUS BELI")
        
    if calc_btn:
        if stop_loss_p >= entry_p:
            st.error("Harga Cut Loss harus lebih rendah dari harga beli!")
        else:
            max_risk = capital * (risk_pct / 100)
            risk_per_share = entry_p - stop_loss_p
            total_lots = math.floor((max_risk / risk_per_share) / 100)
            actual_inv = total_lots * 100 * entry_p
            
            st.markdown("### 🎯 KESIMPULAN:")
            c1, c2 = st.columns(2)
            c1.metric("BELI MAKSIMAL", f"{total_lots:,} Lot")
            c2.metric("MODAL DIBUTUHKAN", f"Rp {actual_inv:,.0f}")

elif menu == "DIVIDEND TRACKER":
    st.title("💰 PEMBURU DIVIDEN")
    with st.expander("📖 BUKU PANDUAN: DIVIDEND YIELD", expanded=False):
        st.markdown("""
        Mencari saham yang rutin bagi-bagi uang? 
        Cek persentase keuntungannya (Yield) di sini. Bunga deposito bank hanya sekitar 4% setahun. Jika Yield saham di atas 5%, itu sangat menarik!
        """)
        
    with st.form("f_div"):
        div_tk = st.text_input("Kode Saham", value="ITMG").upper().strip()
        btn = st.form_submit_button("CEK RIWAYAT DIVIDEN")
        
    if btn:
        try:
            t_obj = yf.Ticker(f"{div_tk}.JK")
            st.metric("ESTIMASI YIELD TAHUNAN", f"{(t_obj.info.get('dividendYield', 0) or 0)*100:.2f}%")
            divs = t_obj.dividends
            if not divs.empty:
                df = pd.DataFrame(divs).reset_index()
                df.columns = ['Tanggal', 'Nominal (Rp)']
                df['Tanggal'] = pd.to_datetime(df['Tanggal']).dt.strftime('%Y-%m-%d')
                st.dataframe(df.sort_values(by='Tanggal', ascending=False).head(10), use_container_width=True, hide_index=True)
            else: st.info("Emiten pelit, belum ada data bagi dividen.")
        except: st.error("Data tidak ditemukan.")

elif menu == "CORRELATION MATRIX":
    st.title("🧬 CEK KORELASI SAHAM")
    with st.expander("📖 BUKU PANDUAN: DIVERSIFIKASI", expanded=False):
        st.markdown("""
        Jangan menaruh semua telur di keranjang yang sama! 
        * **Biru (-1):** Sangat bagus! Jika satu saham turun, yang lain biasanya naik menyeimbangkan portofolio.
        * **Merah (+1):** Saham-saham ini gerakannya kembar. Bahaya jika pasar anjlok, semuanya ikut anjlok bareng.
        """)
        
    with st.form("f_cor"):
        input_tkrs = st.text_input("Ketik Kode (Pisahkan Koma)", value="BBCA, ADRO, TLKM, AMRT")
        btn = st.form_submit_button("BUAT MATRIKS KORELASI")
        
    if btn:
        with st.spinner("Menghitung..."):
            try:
                raw_list = [t.strip().upper() + ".JK" for t in input_tkrs.split(",")]
                data_corr = yf.download(raw_list, period="6mo", interval="1d", progress=False)['Close']
                if not data_corr.empty:
                    if isinstance(data_corr.columns, pd.MultiIndex): data_corr.columns = data_corr.columns.get_level_values(0)
                    data_corr.columns = [c.replace(".JK", "") for c in data_corr.columns]
                    fig_corr = px.imshow(data_corr.corr(), text_auto=True, color_continuous_scale="RdBu_r", zmin=-1, zmax=1)
                    fig_corr.update_layout(template=plot_theme, height=350, margin=dict(l=0,r=0,t=10,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_corr, use_container_width=True)
            except: st.error("Format salah atau data gagal ditarik.")

elif menu == "FOREIGN & BROKER FLOW":
    st.title("🏛️ JEJAK BANDAR & ASING")
    with st.expander("📖 BUKU PANDUAN: IKUTI UANG BESAR", expanded=False):
        st.markdown("""
        Indikator *Chaikin Money Flow* (CMF) mendeteksi jejak kaki institusi/asing.
        * **Angka Positif:** Bandar sedang akumulasi/borong barang. Harga siap terbang.
        * **Angka Negatif:** Distribusi/Buang barang. Bandar sedang cuci gudang, hati-hati tertimpa!
        """)
        
    with st.form("f_ff"):
        ff_tk = st.text_input("Kode Saham", value="BBRI").upper().strip()
        btn = st.form_submit_button("LACAK JEJAK DANA")
        
    if btn:
        with st.spinner("Membaca pergerakan volume besar..."):
            try:
                df_ff = yf.download(f"{ff_tk}.JK", period="3mo", interval="1d", progress=False)
                if not df_ff.empty:
                    if isinstance(df_ff.columns, pd.MultiIndex): df_ff.columns = df_ff.columns.get_level_values(0)
                    df_ff['Multiplier'] = ((df_ff['Close'] - df_ff['Low']) - (df_ff['High'] - df_ff['Close'])) / (df_ff['High'] - df_ff['Low'] + 1e-9)
                    df_ff['CMF_20'] = (df_ff['Multiplier'] * df_ff['Volume']).rolling(20).sum() / df_ff['Volume'].rolling(20).sum()
                    latest = df_ff['CMF_20'].iloc[-1]
                    
                    status = "AKUMULASI (BANDAR MASUK) 🚀" if latest > 0 else "DISTRIBUSI (BANDAR KELUAR) ⚠️"
                    st.markdown(f"<div style='text-align:center; padding:20px; background:{c_bg_card}; border-radius:20px; box-shadow:0 5px 15px rgba(0,0,0,0.1);'><h2 style='color:{c_sec if latest>0 else '#ff4b4b'}; margin:0;'>{latest:.3f}</h2><p style='color:{c_text}; margin:0;'>{status}</p></div>", unsafe_allow_html=True)
            except: st.error("Gagal melacak dana.")

elif menu == "MARKET_NEWS":
    st.title("📰 BERITA PASAR")
    with st.expander("📖 BUKU PANDUAN: SENTIMEN PASAR", expanded=False):
        st.markdown("Harga bergerak karena fundamental dan sentimen. Baca tajuk berita utama hari ini untuk melihat apakah pasar merespon positif atau panik (koreksi).")
    
    with st.spinner("Mengambil tajuk berita terbaru..."):
        try:
            feed = feedparser.parse("https://news.google.com/rss/search?q=saham+indonesia+ihsg&hl=id&gl=ID&ceid=ID:id")
            for entry in feed.entries[:8]: 
                st.markdown(f"<div style='background:{c_bg_card}; padding:18px; border-radius:18px; margin-bottom:12px; box-shadow:0 4px 10px rgba(0,0,0,0.05);'><b><a href='{entry.link}' style='color:{c_prim}; text-decoration:none;'>{entry.title}</a></b><br><small style='color:{c_muted};'>{entry.published}</small></div>", unsafe_allow_html=True)
        except: st.error("Koneksi feed berita terputus.")

elif menu == "MONEY MANAGEMENT":
    st.title("💼 DOMPET PORTOFOLIO")
    with st.expander("📖 BUKU PANDUAN: KELOLA PORTOFOLIO", expanded=False):
        st.markdown("""
        Ini adalah buku tabungan trading-mu.
        * **Catat** setiap kali kamu membeli saham di tab "TAMBAH PEMBELIAN".
        * **Eksekusi Jual** saham yang sudah mencapai target atau batas Cut Loss langsung dari kartu portofoliomu.
        """)
        
    privacy_mode = st.checkbox("🕶️ Mode Privasi (Sembunyikan Saldo)", value=False)
    format_privacy = lambda v: "Rp *****" if privacy_mode else f"Rp {v:,.0f}"

    df_p = get_user_portfolio(user_now, role)
    
    # HITUNG SALDO UNTUK HEADER WALLET
    t_inv, t_pl = 0, 0
    if not df_p.empty:
        tickers_jk = [f"{t}.JK" for t in df_p['ticker'].unique()]
        try:
            live_prices = yf.download(tickers_jk, period="1d", progress=False, threads=True)['Close'].iloc[-1].to_dict() if len(tickers_jk) > 1 else {tickers_jk[0]: yf.download(tickers_jk, period="1d", progress=False)['Close'].iloc[-1]}
        except: live_prices = {}

        def calc_active(row):
            tk, bp, lots = f"{row['ticker']}.JK", row['buy_price'], row['lots']
            curr = live_prices.get(tk, bp)
            curr = curr.iloc[-1] if isinstance(curr, (pd.Series, pd.DataFrame)) else curr
            cost, val = float(bp * lots * 100), float(curr * lots * 100)
            return pd.Series([float(curr), cost, val, (val-cost)])

        df_p[['Live', 'Cost', 'Value', 'P/L']] = df_p.apply(calc_active, axis=1)
        t_inv, t_pl = df_p['Cost'].sum(), df_p['P/L'].sum()

    # TAMPILAN SALDO WALLET BESAR
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, {c_bg_card}, rgba(128,128,128,0.1)); border:1px solid {c_prim}; border-radius:24px; padding:25px; text-align:center; margin-bottom:20px; box-shadow: 0 10px 25px rgba(0,0,0,0.1);'>
        <p style='color:{c_muted}; font-family:Orbitron; margin:0; font-size:12px; letter-spacing:2px;'>TOTAL SALDO INVESTASI</p>
        <h1 style='color:{c_text}; font-family:JetBrains Mono; font-size:2.2rem; margin:10px 0;'>{format_privacy(t_inv + t_pl)}</h1>
        <div style='display:flex; justify-content:center; gap:20px; margin-top:10px;'>
            <div><span style='color:{c_muted}; font-size:10px;'>MODAL AWAL:</span><br><b style='color:{c_prim};'>{format_privacy(t_inv)}</b></div>
            <div><span style='color:{c_muted}; font-size:10px;'>UNREALIZED P/L:</span><br><b style='color:{c_sec if t_pl>=0 else '#ff4b4b'};'>{'+' if t_pl>0 else ''}{format_privacy(t_pl)}</b></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🛒 PORTOFOLIO AKTIF", "📜 RIWAYAT (HISTORY)"])
    with tab1:
        with st.expander("➕ TAMBAH PEMBELIAN BARU", expanded=False):
            with st.form("form_add", clear_on_submit=True):
                t_in = st.text_input("Kode Saham (Misal: BBCA)").upper()
                p_in = st.number_input("Harga Beli (Rp)", min_value=0)
                l_in = st.number_input("Jumlah Beli (Lot)", min_value=1)
                if st.form_submit_button("SIMPAN KE DOMPET", width="stretch"):
                    if t_in and p_in > 0: add_to_portfolio(user_now, t_in, p_in, l_in, 0, 0); st.success("Tersimpan!"); st.rerun()

        if not df_p.empty:
            for i, row in df_p.iterrows():
                pnl_color = c_sec if row['P/L'] >= 0 else "#ff4b4b"
                with st.expander(f"📦 {row['ticker']} | {int(row['lots'])} Lot | {('+' if row['P/L']>0 else '')}{row['P/L']:,.0f} Rp"):
                    st.markdown(f"**Harga Beli:** Rp {row['buy_price']:,.0f} | **Harga Skrg:** Rp {row['Live']:,.0f}")
                    with st.form(f"f_sell_{row['id']}"):
                        s_price = st.number_input("Harga Jual (Rp)", value=float(row['Live']))
                        s_lots = st.number_input("Berapa Lot mau dijual?", min_value=1, max_value=int(row['lots']), value=int(row['lots']))
                        if st.form_submit_button("JUAL SEKARANG", width="stretch"):
                            st.toast(sell_position(user_now, row['id'], row['ticker'], row['buy_price'], s_price, row['lots'], s_lots)); time.sleep(1); st.rerun()
        else: st.info("Dompet investasi masih kosong. Ayo mulai trading!")

    with tab2:
        df_h = conn_gs.read(worksheet="history", ttl=0)
        if not df_h.empty:
            df_h['pnl'] = pd.to_numeric(df_h['pnl'], errors='coerce')
            if role != 'admin': df_h = df_h[df_h['username'] == user_now]
            for idx, h_row in df_h.sort_values(by='date', ascending=False).iterrows():
                pnl_color = c_sec if h_row['pnl'] >= 0 else "#ff4b4b"
                st.markdown(f"<div style='background:{c_bg_card}; padding:16px; border-radius:16px; border-left:4px solid {pnl_color}; margin-bottom:10px; box-shadow:0 4px 10px rgba(0,0,0,0.05);'><b style='color:{c_text}'>{h_row['ticker']}</b> <span style='color:{c_muted}; font-size:11px;'>({h_row['date']})</span><br><span style='color:{c_text}'>Beli: {h_row['buy_price']} | Jual: {h_row['sell_price']}</span> | <b style='color:{pnl_color};'>{'+' if h_row['pnl']>0 else ''}Rp {h_row['pnl']:,.0f}</b></div>", unsafe_allow_html=True)
        else: st.info("Belum ada riwayat penjualan.")

elif menu == "USER MANAGEMENT":
    st.title("👤 USER ADMIN PUSAT")
    with st.expander("📖 PANDUAN ADMIN", expanded=False):
        st.markdown("Halaman khusus admin untuk mengatur akses akun pengguna (Tambah/Hapus Kunci Akses).")
    
    df_u = conn_gs.read(worksheet="users", ttl=0)
    st.dataframe(df_u[['username', 'role', 'last_login', 'location']], use_container_width=True, hide_index=True)
    c1, c2 = st.columns(2)
    with c1:
        with st.form("add_u"):
            nu, np, nr = st.text_input("User ID Baru"), st.text_input("Password", type="password"), st.selectbox("Role", ["user", "admin"])
            if st.form_submit_button("BUAT AKUN"):
                if add_user_db(nu, np, nr): st.success("Dibuat!"); st.rerun()
    with c2:
        with st.form("del_u"):
            du = st.text_input("ID yang mau dihapus")
            if st.form_submit_button("HAPUS AKUN"):
                if delete_user_db(du): st.warning("Dihapus!"); st.rerun()

elif menu == "SECURITY SETTINGS":
    st.title("🔒 PENGATURAN KEAMANAN")
    with st.expander("📖 PANDUAN KEAMANAN", expanded=False):
        st.markdown("Ubah kunci akses (password) kamu secara berkala untuk menjaga keamanan Wallet-mu.")
        
    with st.form("p"):
        new_p = st.text_input("Ketik Kunci Akses (Password) Baru", type="password")
        if st.form_submit_button("PERBARUI PASSWORD", width="stretch"):
            if update_password_db(user_now, new_p): st.success("Berhasil diubah!")
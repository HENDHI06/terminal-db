import streamlit as st
import yfinance as yf
import pandas as pd
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
import feedparser

# --- 0. CONFIG & APP SETUP ---
warnings.filterwarnings("ignore", category=FutureWarning)
st.set_page_config(
    page_title="IDX CYBER TERMINAL", 
    page_icon="⚡", 
    layout="wide",
    initial_sidebar_state="collapsed" 
)

conn_gs = st.connection("gsheets", type=GSheetsConnection)

# --- DATABASE & LOGIC FUNGSI ---
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
    new_row = pd.DataFrame([{'id': next_id, 'username': u, 'ticker': t.upper().strip(), 'buy_price': float(p), 'lots': int(l), 'tp_price': float(tp), 'cl_price': float(cl), 'date': datetime.now(pytz.timezone('Asia/Jakarta')).strftime("%Y-%m-%d"), 'strategy': strategy}])
    df = pd.concat([df, new_row], ignore_index=True)
    conn_gs.update(worksheet="portfolio", data=df)

def sell_position(u, row_id, ticker, buy_p, sell_p, total_lots, sold_lots):
    pnl = (sell_p - buy_p) * sold_lots * 100
    df_port = conn_gs.read(worksheet="portfolio", ttl=0)
    idx = df_port.index[df_port['id'] == row_id].tolist()
    remaining_lots = total_lots - sold_lots
    strat_used = "Bebas"
    if idx:
        if 'strategy' in df_port.columns: strat_used = df_port.at[idx[0], 'strategy']
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
    new_hist = pd.DataFrame([{'id': next_hist_id, 'username': u, 'ticker': ticker, 'buy_price': float(buy_p), 'sell_price': float(sell_p), 'lots': int(sold_lots), 'pnl': float(pnl), 'date': datetime.now(pytz.timezone('Asia/Jakarta')).strftime("%Y-%m-%d"), 'strategy': strat_used}])
    df_hist = pd.concat([df_hist, new_hist], ignore_index=True)
    conn_gs.update(worksheet="history", data=df_hist)
    return msg

def get_user_portfolio(u, r):
    df = conn_gs.read(worksheet="portfolio", ttl=0)
    if df.empty or len(df) == 0: return pd.DataFrame()
    df['id'], df['lots'], df['buy_price'] = pd.to_numeric(df['id'], errors='coerce'), pd.to_numeric(df['lots'], errors='coerce'), pd.to_numeric(df['buy_price'], errors='coerce')
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
    try: return yf.Ticker(ticker).info.get('sector', 'Lainnya')
    except: return "Lainnya"

# --- 1. TEMA AWAL (DARK CYBER) + OPTIMASI HP ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;700&family=Orbitron:wght@600;800;900&display=swap');

.stApp {
    background: #07090f;
    background-image: radial-gradient(circle at 10% 10%, rgba(0, 240, 255, 0.04) 0%, transparent 40%),
                      radial-gradient(circle at 90% 90%, rgba(120, 255, 0, 0.03) 0%, transparent 40%);
    font-family: 'Plus Jakarta Sans', sans-serif;
    color: #e2e8f0;
}
header {background: transparent !important;}
[data-testid="stHeaderActionElements"], .stDeployButton, #MainMenu { display: none !important; }

h1, h2, h3 { font-family: 'Orbitron', sans-serif; letter-spacing: 1px; }
h1 {
    font-weight: 900; font-size: 2.2rem;
    background: linear-gradient(135deg, #00f0ff 0%, #78ff00 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    text-shadow: 0 0 30px rgba(0, 240, 255, 0.2);
}
h2, h3 { color: #00f0ff; font-weight: 800; }

div[data-testid="stForm"], div[data-testid="stExpander"], div[data-testid="stMetric"], .stDataFrame {
    background: rgba(13, 18, 30, 0.85) !important;
    border: 1px solid rgba(0, 240, 255, 0.25) !important;
    border-top: 3px solid #00f0ff !important;
    border-radius: 16px; padding: 15px !important; backdrop-filter: blur(20px);
    margin-bottom: 16px !important;
}
div[data-testid="stForm"] label p { font-family: 'Orbitron', sans-serif !important; color: #78ff00 !important; font-size: 0.75rem !important; letter-spacing: 2px;}
div[data-testid="stForm"] input, div[data-testid="stForm"] select {
    background: rgba(3, 6, 12, 0.8) !important;
    border: 1px solid rgba(0, 240, 255, 0.2) !important;
    color: #00f0ff !important; font-family: 'JetBrains Mono', monospace !important;
    border-radius: 8px; height: 48px; font-weight:bold; font-size:16px;
}

[data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace !important; font-size: 1.8rem !important; color: #78ff00 !important; }
[data-testid="stMetricLabel"] { color: #94a3b8 !important; font-weight: 600; text-transform: uppercase; font-size: 0.8rem; }
[data-testid="stSidebar"] { background: #090d16; border-right: 1px solid rgba(255, 255, 255, 0.05); }

div[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label {
    background: rgba(255, 255, 255, 0.01) !important; 
    border: 1px solid rgba(255, 255, 255, 0.03) !important;
    border-radius: 8px !important; padding: 14px 16px !important; margin-bottom: 8px !important;
}
div[data-testid="stSidebar"] .stRadio label p { font-family: 'Orbitron', sans-serif !important; font-size: 0.8rem !important; color: #64748b !important; letter-spacing: 1.5px;}
div[data-testid="stSidebar"] .stRadio div[role="radiogroup"] [aria-checked="true"] {
    background: linear-gradient(90deg, rgba(0, 240, 255, 0.12), rgba(120, 255, 0, 0.05)) !important;
    border: 1px solid rgba(0, 240, 255, 0.4) !important; border-left: 4px solid #78ff00 !important;
}
div[data-testid="stSidebar"] .stRadio div[role="radiogroup"] [aria-checked="true"] p { color: #ffffff !important; }

.stButton>button {
    background: linear-gradient(135deg, rgba(0, 240, 255, 0.15), rgba(120, 255, 0, 0.15));
    border: 1px solid rgba(0, 240, 255, 0.4); color: #78ff00 !important;
    border-radius: 8px; font-family: 'Orbitron', sans-serif; font-weight: 700; font-size: 0.8rem;
    min-height: 48px; width: 100%; margin-top: 5px; margin-bottom: 5px;
}
.stButton>button:hover { background: linear-gradient(135deg, #00f0ff, #78ff00); color: #07090f !important; }

/* Custom Styling untuk kotak Dashboard agar flexibel/melar dan tidak dempet */
.dash-box {
    background:rgba(13,18,30,0.85); 
    padding:18px; 
    border-radius:14px; 
    margin-bottom:20px; 
    box-shadow:0 8px 20px rgba(0,0,0,0.4);
}
</style>
""", unsafe_allow_html=True)

# --- STATE CONTROL ---
if 'active_menu' not in st.session_state:
    st.session_state.active_menu = "🖥️ DASHBOARD UTAMA"

# --- 2. AUTHENTICATION ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.role = None

if not st.session_state.logged_in:
    _, col2, _ = st.columns([1,1.5,1])
    with col2:
        st.markdown("<div style='text-align:center; padding:40px 0;'><h1 style='font-size:2.8rem; margin-bottom:0;'>IDX TERMINAL</h1><p style='color:#00f0ff; letter-spacing:6px; font-family:Orbitron; font-size:0.8rem;'>INSTITUTIONAL QUANT SUITE</p></div>", unsafe_allow_html=True)
        with st.form("login_form"):
            u = st.text_input("NODE ID").strip()
            p = st.text_input("ACCESS KEY", type="password")
            if st.form_submit_button("INITIALIZE SESSION", width="stretch"):
                with st.spinner("🔑 Mengautentikasi Database..."):
                    role = authenticate_user(u, p)
                    if role:
                        st.session_state.logged_in = True
                        st.session_state.user = u
                        st.session_state.role = role
                        st.rerun()
                    else: st.error("ACCESS DENIED / AUTHENTICATION FAILED")
    st.stop()


# --- 3. MARKET DATA LOGIC ---
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
    else: min_chg, min_rsi, min_val, vol_m = 4.0, 60, 2_000_000_000, 1.8

    progress = st.progress(0, text="📡 Memindai Bursa Efek...")
    try:
        data = yf.download(tickers, period="2mo", interval="1d", group_by="ticker", threads=True, progress=False)
    except:
        st.error("Failed to connect to market data.")
        return pd.DataFrame()

    total = len(tickers)
    for i, t in enumerate(tickers):
        try:
            progress.progress(int((i + 1) / total * 100), text=f"🔍 Analisa {t}")
            df = data[t].copy() if len(tickers) > 1 else data.copy()
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            if df.empty or len(df) < 20: continue

            c_now, c_prev = float(df['Close'].iloc[-1]), float(df['Close'].iloc[-2])
            if math.isnan(c_now) or math.isnan(c_prev): continue

            chg = ((c_now - c_prev) / c_prev) * 100
            val_tr = float(df['Volume'].iloc[-1]) * c_now
            
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rsi = 100 - (100 / (1 + (gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] != 0 else 0)))

            high_20 = df['High'].rolling(20).max().iloc[-2]
            vol_avg = df['Volume'].rolling(20).mean().iloc[-1]
            is_breakout = (c_now > high_20) and (df['Volume'].iloc[-1] > vol_avg * vol_m)

            if chg < min_chg or val_tr < min_val: continue

            multiplier = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) / (df['High'] - df['Low'] + 1e-9)
            cmf_series = (multiplier * df['Volume']).rolling(20).sum() / df['Volume'].rolling(20).sum()
            cmf_series = cmf_series.fillna(0)
            cmf = float(cmf_series.iloc[-1])

            tr1 = df['High'] - df['Low']
            tr2 = (df['High'] - df['Close'].shift()).abs()
            tr3 = (df['Low'] - df['Close'].shift()).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr_val = float(tr.rolling(14).mean().iloc[-1])
            if math.isnan(atr_val): atr_val = c_now * 0.03
                
            ai_score = (chg * 0.4) + (rsi * 0.2) + ((val_tr / 1e9) * 0.2) + (10 if is_breakout else 0) + (cmf * 20)

            results.append({
                "TICKER": t.replace(".JK", ""), "LAST": c_now, "CHG%": round(chg, 2),
                "RSI": round(rsi, 1), "VAL(M)": round(val_tr / 1_000_000, 1), 
                "BANDAR": "AKUMULASI 🚀" if cmf > 0 else "DISTRIBUSI ⚠️",
                "AI_SCORE": round(ai_score, 2),
                "BREAKOUT": "YA" if is_breakout else "TDK",
                "TP 1": c_now + (1.5 * atr_val), "TP 2": c_now + (2.5 * atr_val), "EXIT/CL": c_now - (1.0 * atr_val), "FULL": t
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
            
            if isinstance(df.columns, pd.MultiIndex): 
                df.columns = df.columns.get_level_values(0)
                
            df['MA20'] = df['Close'].rolling(20).mean()
            df['MA50'] = df['Close'].rolling(50).mean()
            
            df['Multiplier'] = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) / (df['High'] - df['Low'] + 1e-9)
            df['CMF_20'] = (df['Multiplier'] * df['Volume']).rolling(20).sum() / df['Volume'].rolling(20).sum()
            df['CMF_20'] = df['CMF_20'].fillna(0)
            
            last_ma20 = float(df['MA20'].iloc[-1])
            last_ma50 = float(df['MA50'].iloc[-1])
            prev_ma20 = float(df['MA20'].iloc[-2])
            prev_ma50 = float(df['MA50'].iloc[-2])
            current_price = float(df['Close'].iloc[-1])
            cmf_val = float(df['CMF_20'].iloc[-1])
            
            if math.isnan(current_price) or math.isnan(last_ma20) or math.isnan(last_ma50): 
                continue
            
            if prev_ma20 < prev_ma50 and last_ma20 > last_ma50:
                if cmf_val > 0:
                    status_text = "🟢 GOLDEN CROSS + AKUMULASI BANDAR (Sangat Kuat)"
                    color_code = "#78ff00"
                else:
                    status_text = "🟡 GOLDEN CROSS (Hati-hati, Bandar Distribusi)"
                    color_code = "#ffcc00"
                signals.append({"ticker": ticker.replace(".JK", ""), "status": status_text, "price": current_price, "color": color_code})
            
            elif prev_ma20 > prev_ma50 and last_ma20 < last_ma50:
                if cmf_val < 0:
                    status_text = "🔴 DEAD CROSS + DISTRIBUSI BANDAR (Sangat Bahaya)"
                    color_code = "#ff4b4b"
                else:
                    status_text = "🟠 DEAD CROSS (Koreksi Normal Wajar)"
                    color_code = "#ff9900"
                signals.append({"ticker": ticker.replace(".JK", ""), "status": status_text, "price": current_price, "color": color_code})
        except Exception as e: 
            continue
    return signals

def draw_mobile_cards(df):
    for _, row in df.iterrows():
        chg = row.get('CHG%', 0)
        chg_color = "#78ff00" if chg > 0 else "#ff4b4b"
        val_last  = row.get('LAST', 0)
        val_entry = row.get('ENTRY', row.get('Entry', val_last)) 
        val_tp1   = row.get('TP 1', 0)
        val_tp2   = row.get('TP 2', 0)
        val_cl    = row.get('EXIT/CL', 0)
        val_m     = row.get('VAL(M)', 0)

        st.markdown(f"""
        <div style="background: rgba(13, 18, 30, 0.8); border: 1px solid rgba(0, 240, 255, 0.2); 
                    border-radius: 12px; padding: 16px; margin-bottom: 12px; border-left: 4px solid {chg_color};">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <b style="font-size: 1.2rem; color: #00f0ff; font-family: Orbitron;">{row.get('TICKER','-')}</b>
                <span style="color: {chg_color}; font-weight: bold; font-family: JetBrains Mono; font-size: 1rem;">{'+' if chg>0 else ''}{chg}%</span>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 12px; font-size: 0.85rem; color: #94a3b8;">
                <div>Harga: <b style="color:#fff;">Rp {val_last:,.0f}</b></div>
                <div>Trx: <b style="color:#fff;">{val_m} Miliar</b></div>
                <div style="color: #00f0ff; font-weight: bold;">Rencana Beli: Rp {float(val_entry):,.0f}</div>
                <div style="color: #78ff00; font-weight: bold;">Jual Untung: Rp {float(val_tp1):,.0f}</div>
                <div style="color: #ff4b4b; font-weight: bold; grid-column: span 2; text-align: center; margin-top:5px;">Jual Rugi (Cut Loss): Rp {float(val_cl):,.0f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)


# --- 4. NAVIGATION & SIDEBAR ---
role = st.session_state.role
user_now = st.session_state.user
last_l, ip_l, loc_l = get_sidebar_log(user_now)

st.sidebar.markdown(f"""
    <div style='padding:16px; border:1px solid rgba(0, 240, 255, 0.2); border-radius:12px; background:rgba(13, 18, 30, 0.9); margin-bottom:15px;'>
        <h3 style='margin:0; color:#00f0ff; font-family:Orbitron; font-size:1rem;'>{user_now.upper()}</h3>
        <p style='margin:0; font-size:9px; color:#78ff00; font-family:Orbitron; margin-top:4px;'>NODE ACTIVE | {role.upper()}</p>
        <hr style='border:0.1px solid rgba(255,255,255,0.08); margin:10px 0;'>
        <p style='font-size:9px; color:#94a3b8; margin:2px 0; font-family:JetBrains Mono;'>LST: {last_l}</p>
        <p style='font-size:9px; color:#94a3b8; margin:2px 0; font-family:JetBrains Mono;'>IP : {ip_l}</p>
    </div>
    """, unsafe_allow_html=True)

menu_list = [
    "🖥️ DASHBOARD UTAMA",
    "🛰️ AUTO SCANNER", 
    "⚡ STRATEGY SCANNER",
    "🕯️ POLA CANDLE AI",         
    "⭐ WATCHLIST FAVORIT", 
    "🎯 AUTO SUP/RES",           
    "📅 SIKLUS MUSIMAN",         
    "📟 CEK FUNDAMENTAL", 
    "⚔️ ADU SAHAM", 
    "🌐 PETA SEKTOR", 
    "🧮 KALKULATOR TRADING",     
    "💰 PEMBURU DIVIDEN", 
    "🧬 KORELASI SAHAM", 
    "🏛️ JEJAK BANDAR", 
    "📰 BERITA PASAR", 
    "💼 DOMPET TRADING",         
    "🔒 KEAMANAN"
]
if role == "admin" and "⚙️ USER MANAGEMENT" not in menu_list: 
    menu_list.insert(16, "⚙️ USER MANAGEMENT")

# PENGGUNAAN KEY DI RADIO BUTTON AGAR MENU TIDAK NGEBALIK SENDIRI
menu = st.sidebar.radio("Navigasi", menu_list, key="side_menu", label_visibility="collapsed")

st.sidebar.write("---")
if st.sidebar.button("🔴 KELUAR APLIKASI", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.role = None
    st.rerun()


# --- 5. CONTENT AREA ---

# =========================================================================
# 🔥 MASTER COMMAND CENTER (DASHBOARD) - ULTIMATE DENGAN SENTIMEN & ASING
# =========================================================================
if menu == "🖥️ DASHBOARD UTAMA":
    st.markdown(f"<h2 style='color:#fff; margin-bottom:5px;'>Selamat Datang, <span style='color:#00f0ff;'>{user_now.upper()}!</span></h2>", unsafe_allow_html=True)
    st.caption("Beranda utama yang merangkum kesehatan pasar modal, psikologi trader, aliran uang asing, dan portofolio pribadimu.")
    st.write("---")
    
    proxy_market = ["BBCA.JK","BBRI.JK","BMRI.JK","BBNI.JK","ASII.JK","TLKM.JK","AMRT.JK","ADRO.JK",
                    "PTBA.JK","ITMG.JK","UNVR.JK","ICBP.JK","INDF.JK","KLBF.JK","PGAS.JK","GOTO.JK",
                    "ARTO.JK","BRPT.JK","MDKA.JK","ANTM.JK","INCO.JK","CPIN.JK","AKRA.JK","MEDC.JK",
                    "HRUM.JK","EXCL.JK","ISAT.JK","INKP.JK","TKIM.JK","PGEO.JK"]
    
    big_banks = ["BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "TLKM.JK", "ASII.JK"] # Proxy pergerakan Asing

    up, down, flat = 0, 0, 0
    # --- BAGIAN 1: IHSG & MARKET BREADTH ---
    c_ihsg, c_breadth = st.columns([1, 1.2])
    with c_ihsg:
        try:
            ihsg_data = yf.download("^JKSE", period="2d", interval="1d", progress=False)
            if not ihsg_data.empty and len(ihsg_data) >= 2:
                if isinstance(ihsg_data.columns, pd.MultiIndex): ihsg_data.columns = ihsg_data.columns.get_level_values(0)
                ihsg_last, ihsg_prev = float(ihsg_data['Close'].iloc[-1]), float(ihsg_data['Close'].iloc[-2])
                ihsg_pct = ((ihsg_last - ihsg_prev) / ihsg_prev) * 100
                ihsg_color = "#78ff00" if ihsg_pct > 0 else "#ff4b4b"
                ihsg_status = "BULLISH 🚀" if ihsg_pct > 0.5 else ("BEARISH ⚠️" if ihsg_pct < -0.5 else "SIDEWAYS 💤")
                st.markdown(f"""<div class='dash-box' style='border:1px solid {ihsg_color};'>
                    <p style='margin:0; font-size:11px; color:#94a3b8; font-family:Orbitron; letter-spacing:1px;'>IHSG (HARGA SAHAM GABUNGAN)</p>
                    <h2 style='margin:8px 0; color:{ihsg_color}; font-family:JetBrains Mono;'>{ihsg_last:,.2f} <span style='font-size:1rem;'>({'+' if ihsg_pct>0 else ''}{ihsg_pct:.2f}%)</span></h2>
                    <p style='margin:0; font-size:13px; color:#fff;'>Status Pasar: <b style='color:{ihsg_color};'>{ihsg_status}</b></p>
                </div>""", unsafe_allow_html=True)
                st.caption("📈 **IHSG:** Indikator utama pergerakan rata-rata seluruh saham di Bursa Efek Indonesia.")
        except: st.warning("Gagal memuat IHSG.")

    with c_breadth:
        with st.spinner("Memindai Kesehatan Pasar..."):
            try:
                br_data = yf.download(proxy_market, period="2d", interval="1d", progress=False)['Close']
                if isinstance(br_data.columns, pd.MultiIndex): br_data.columns = br_data.columns.get_level_values(0)
                for tk in proxy_market:
                    try:
                        c_l, c_p = float(br_data[tk].iloc[-1]), float(br_data[tk].iloc[-2])
                        if c_l > c_p: up += 1
                        elif c_l < c_p: down += 1
                        else: flat += 1
                    except: pass
                total_valid = up + down + flat
                if total_valid > 0:
                    st.markdown(f"""<div class='dash-box' style='border:1px solid rgba(0,240,255,0.25);'>
                        <p style='margin:0 0 12px 0; font-size:11px; color:#94a3b8; font-family:Orbitron; text-align:center; letter-spacing:1px;'>📊 MARKET BREADTH (KESEHATAN PASAR)</p>
                        <div style='display:flex; justify-content:space-around;'>
                            <div style='text-align:center;'><h2 style='color:#78ff00; margin:0;'>{up}</h2><span style='font-size:12px; color:#94a3b8;'>Naik 📈</span></div>
                            <div style='text-align:center;'><h2 style='color:#94a3b8; margin:0;'>{flat}</h2><span style='font-size:12px; color:#94a3b8;'>Mandek ➖</span></div>
                            <div style='text-align:center;'><h2 style='color:#ff4b4b; margin:0;'>{down}</h2><span style='font-size:12px; color:#94a3b8;'>Turun 📉</span></div>
                        </div>
                    </div>""", unsafe_allow_html=True)
                    st.caption("⚖️ **Market Breadth:** Menghitung saham yang nyata-nyata naik vs turun untuk mendeteksi apakah IHSG naik hanya karena 1 saham besar, atau memang bursa sedang sehat.")
            except: pass
        
    st.write("---")

    # --- BAGIAN 2: RADAR SENTIMEN & ARUS DANA ASING ---
    c_flow, c_fg = st.columns(2)
    with c_flow:
        with st.spinner("Melacak Dana Asing..."):
            try:
                flow_data = yf.download(big_banks, period="1mo", interval="1d", progress=False)
                if isinstance(flow_data.columns, pd.MultiIndex): flow_data.columns = flow_data.columns.get_level_values(0)
                avg_cmfs = []
                for tk in big_banks:
                    try:
                        df_f = pd.DataFrame({'High': flow_data['High'][tk], 'Low': flow_data['Low'][tk], 'Close': flow_data['Close'][tk], 'Volume': flow_data['Volume'][tk]})
                        mult = ((df_f['Close'] - df_f['Low']) - (df_f['High'] - df_f['Close'])) / (df_f['High'] - df_f['Low'] + 1e-9)
                        cmf_20 = (mult * df_f['Volume']).rolling(20).sum() / df_f['Volume'].rolling(20).sum()
                        avg_cmfs.append(cmf_20.iloc[-1])
                    except: pass
                
                net_flow = sum(avg_cmfs) / len(avg_cmfs) if avg_cmfs else 0
                flow_color = "#78ff00" if net_flow > 0 else "#ff4b4b"
                flow_status = "NET BUY (Masuk) 🛒" if net_flow > 0.05 else ("NET SELL (Keluar) 💸" if net_flow < -0.05 else "NETRAL ⚖️")
                
                st.markdown(f"""<div class='dash-box' style='border:1px solid {flow_color}; text-align:center;'>
                    <p style='margin:0 0 10px 0; font-size:11px; color:#94a3b8; font-family:Orbitron;'>🦅 ARUS DANA ASING (BIG CAPS)</p>
                    <h3 style='color:{flow_color}; margin:15px 0;'>{flow_status}</h3>
                    <p style='font-size:12px; color:#fff;'>Indikator Kekuatan: {net_flow:.2f}</p>
                </div>""", unsafe_allow_html=True)
                st.caption("🦅 **Dana Asing:** Melacak apakah hari ini uang institusi asing sedang disuntik masuk (akumulasi) atau ditarik keluar (distribusi) dari bursa kita.")
            except: st.info("Data Arus Dana belum tersedia.")
            
    with c_fg:
        try:
            fg_ratio = up / (up + down + 0.0001) * 100
            fg_value = int(fg_ratio)
            if fg_value <= 30: fg_status, fg_color = "EXTREME FEAR", "#ff4b4b"
            elif fg_value <= 45: fg_status, fg_color = "FEAR", "#ff9900"
            elif fg_value <= 55: fg_status, fg_color = "NEUTRAL", "#00f0ff"
            elif fg_value <= 70: fg_status, fg_color = "GREED", "#78ff00"
            else: fg_status, fg_color = "EXTREME GREED", "#00ff00"
            
            fig_fg = go.Figure(go.Indicator(
                mode = "gauge+number", value = fg_value,
                number = {'font': {'color': fg_color, 'size':30}},
                title = {'text': f"<br><span style='color:{fg_color}; font-size:16px; font-weight:bold;'>{fg_status}</span>", 'font': {'size': 14}},
                gauge = {
                    'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white", 'visible': False},
                    'bar': {'color': fg_color, 'thickness': 0.3}, 'bgcolor': "rgba(255,255,255,0.1)",
                    'steps': [
                        {'range': [0, 30], 'color': "rgba(255, 75, 75, 0.2)"}, {'range': [30, 45], 'color': "rgba(255, 153, 0, 0.2)"},
                        {'range': [45, 55], 'color': "rgba(0, 240, 255, 0.2)"}, {'range': [55, 70], 'color': "rgba(120, 255, 0, 0.2)"},
                        {'range': [70, 100], 'color': "rgba(0, 255, 0, 0.2)"}],
                }
            ))
            fig_fg.update_layout(height=200, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)")
            
            with st.container():
                st.markdown("<div class='dash-box' style='border:1px solid rgba(0,240,255,0.25); text-align:center;'>", unsafe_allow_html=True)
                st.markdown("<p style='margin:0 0 5px 0; font-size:11px; color:#94a3b8; font-family:Orbitron;'>🌡️ FEAR & GREED SENTIMENT</p>", unsafe_allow_html=True)
                st.plotly_chart(fig_fg, use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
            
            st.caption("🌡️ **Fear & Greed:** Mengukur kepanikan bursa. Belilah (Serok) saat pasar ketakutan (Fear), dan waspada/juallah saat orang terlalu serakah (Greed).")
        except: st.info("Termometer Sentimen belum siap.")

    st.write("---")

    # --- BAGIAN 3: PRIVASI SALDO & RINGKASAN PORTOFOLIO ---
    c_title, c_toggle = st.columns([2.5, 1.5])
    c_title.markdown("<h3 style='font-size:1.2rem; color:#00f0ff; margin-top:5px;'>💼 Portofolio & AI Auditor</h3>", unsafe_allow_html=True)
    show_saldo_dash = c_toggle.checkbox("👁️ Tampilkan Saldo", value=False, key="privasi_dash")
    fmt_dash = lambda v: f"Rp {v:,.0f}" if show_saldo_dash else "Rp *****"

    df_p = get_user_portfolio(user_now, role)
    t_inv, t_pl = 0, 0
    if not df_p.empty:
        tickers_jk = [f"{t}.JK" for t in df_p['ticker'].unique()]
        try:
            live_prices = yf.download(tickers_jk, period="1d", progress=False, threads=True)['Close'].iloc[-1].to_dict() if len(tickers_jk) > 1 else {tickers_jk[0]: float(yf.download(tickers_jk, period="1d", progress=False)['Close'].iloc[-1])}
        except: live_prices = {}
        def calc_active(row):
            tk, bp, lots = f"{row['ticker']}.JK", row['buy_price'], row['lots']
            curr = float(live_prices.get(tk, bp))
            cost, val = float(bp * lots * 100), float(curr * lots * 100)
            return pd.Series([curr, cost, val, (val-cost)])
        df_p[['Live', 'Cost', 'Value', 'P/L']] = df_p.apply(calc_active, axis=1)
        t_inv, t_pl = df_p['Cost'].sum(), df_p['P/L'].sum()
        
    c1, c2, c3 = st.columns(3)
    c1.metric("MODAL", fmt_dash(t_inv))
    c2.metric("P/L", fmt_dash(t_pl), f"{(t_pl/t_inv*100 if t_inv!=0 else 0):.2f}%" if show_saldo_dash else "*****")
    c3.metric("SEKARANG", fmt_dash(t_inv + t_pl))
    st.caption("💼 **Portofolio:** Ringkasan sisa modal dan total kerugian/keuntungan (P/L) dari saham yang kamu miliki saat ini.")

    # --- AI PORTFOLIO AUDITOR ---
    if not df_p.empty and t_inv > 0:
        df_p_aud = df_p[df_p['lots'] > 0].copy()
        if not df_p_aud.empty:
            df_p_aud['Sector'] = df_p_aud['ticker'].apply(lambda x: get_sector(f"{x}.JK"))
            sec_weights = df_p_aud.groupby('Sector')['Cost'].sum() / t_inv * 100
            max_sec = sec_weights.idxmax()
            max_w = sec_weights.max()
            
            if max_w > 60:
                st.markdown(f"<div class='dash-box' style='background:rgba(255,75,75,0.1); border:1px solid #ff4b4b;'><b style='color:#ff4b4b;'>🛡️ AI Auditor Warning:</b> {max_w:.1f}% uangmu menumpuk di sektor <b>{max_sec}</b>. Portofoliomu sangat berisiko jika sektor ini ambruk. Segera diversifikasi!</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='dash-box' style='background:rgba(120,255,0,0.1); border:1px solid #78ff00;'><b style='color:#78ff00;'>🛡️ AI Auditor Aman:</b> Diversifikasi portofoliomu sehat (Maks sektor: {max_sec} {max_w:.1f}%). Terus pertahankan!</div>", unsafe_allow_html=True)
            
            fig_pie = px.pie(df_p_aud, values='Cost', names='Sector', title="📊 Alokasi Aset per Sektor", hole=0.4, color_discrete_sequence=px.colors.sequential.Teal)
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            fig_pie.update_layout(template="plotly_dark", height=350, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=40, b=0, l=0, r=0))
            st.plotly_chart(fig_pie, use_container_width=True)
            st.caption("🛡️ **AI Auditor:** Mengawasi porsi uangmu agar tidak menumpuk di satu sektor (Diversifikasi) guna meminimalisir risiko kebangkrutan massal.")
    
    st.write("---")
    
    # --- BAGIAN 4: UNUSUAL VOLUME & TOP MOVERS ---
    c_vol, c_mov = st.columns(2)
    
    with c_vol:
        st.markdown("<h3 style='font-size:1.2rem; color:#00f0ff;'>🌋 Unusual Volume (Radar Bandar)</h3>", unsafe_allow_html=True)
        with st.spinner("Melacak ledakan volume..."):
            try:
                vol_data = yf.download(proxy_market, period="1mo", interval="1d", progress=False)['Volume']
                if isinstance(vol_data.columns, pd.MultiIndex): vol_data.columns = vol_data.columns.get_level_values(0)
                spikes = []
                for tk in proxy_market:
                    try:
                        v_today = float(vol_data[tk].iloc[-1])
                        v_avg20 = float(vol_data[tk][-21:-1].mean())
                        if v_avg20 > 0 and v_today > (v_avg20 * 1.5):
                            spikes.append({"Ticker": tk.replace(".JK",""), "Spike": v_today / v_avg20})
                    except: pass
                
                df_spikes = pd.DataFrame(spikes).sort_values("Spike", ascending=False).head(3)
                if not df_spikes.empty:
                    for _, row in df_spikes.iterrows():
                        st.markdown(f"<div class='dash-box' style='border-left:4px solid #00f0ff; padding:12px;'><b style='color:#fff;'>{row['Ticker']}</b> <span style='float:right; color:#00f0ff; font-weight:bold;'>Vol {row['Spike']:.1f}x Lipat 🌋</span></div>", unsafe_allow_html=True)
                else: st.info("Tidak ada anomali ledakan volume hari ini.")
            except: st.info("Sistem volume radar sedang menyesuaikan data.")
        st.caption("🌋 **Unusual Volume:** Radar yang mendeteksi saham jika transaksinya tiba-tiba meledak miliaran rupiah melebihi hari biasanya (Tanda bandar mulai masuk).")

    with c_mov:
        st.markdown("<h3 style='font-size:1.2rem; color:#ff4b4b;'>📈 Top Movers (Blue Chips)</h3>", unsafe_allow_html=True)
        with st.spinner("Menarik data penggerak..."):
            try:
                mov_data = yf.download(proxy_market, period="2d", interval="1d", progress=False)['Close']
                if isinstance(mov_data.columns, pd.MultiIndex): mov_data.columns = mov_data.columns.get_level_values(0)
                mov_list = []
                for tk in proxy_market:
                    try:
                        c_last, c_prev = float(mov_data[tk].iloc[-1]), float(mov_data[tk].iloc[-2])
                        mov_list.append({"Ticker": tk.replace(".JK",""), "Chg": ((c_last-c_prev)/c_prev)*100})
                    except: pass
                
                df_mov = pd.DataFrame(mov_list).sort_values("Chg", ascending=False)
                if len(df_mov) >= 2:
                    st.success(f"🚀 **Top Gainer:** {df_mov.iloc[0]['Ticker']} (+{df_mov.iloc[0]['Chg']:.2f}%)")
                    st.error(f"⚠️ **Top Loser:** {df_mov.iloc[-1]['Ticker']} ({df_mov.iloc[-1]['Chg']:.2f}%)")
            except: st.info("Data Movers belum tersedia.")
        st.caption("🏆 **Top Movers:** Menampilkan saham penggerak (kategori aman/liquid) yang hari ini memimpin kenaikan dan penurunan terdalam.")


# =========================================================================
# 🔥 FITUR 2: AI CANDLESTICK PATTERN DETECTOR
# =========================================================================
elif menu == "🕯️ POLA CANDLE AI":
    st.title("🕯️ AI CANDLESTICK DETECTOR")
    st.caption("Fitur ini menganalisa bentuk grafik terakhir untuk mencari tahu titik balik arah. Kamu tidak perlu lagi menghafal pola grafik, biarkan AI membacanya untukmu.")
    with st.expander("📖 CARA KERJA DETEKTOR CANDLESTICK", expanded=False):
        st.markdown("""
        * **Bullish Engulfing / Hammer:** Tanda bandar mulai menadah barang di bawah. Harga siap naik! 🚀
        * **Bearish Engulfing / Shooting Star:** Tanda bandar jualan di pucuk. Harga rawan longsor! ⚠️
        """)

    with st.form("f_candle"):
        tk_candle = st.text_input("Ketik Kode Saham", value="BBRI").upper().strip()
        btn_candle = st.form_submit_button("DETEKSI POLA SEKARANG", width="stretch")
        
    if btn_candle:
        with st.spinner("Mendeteksi anatomi grafik terakhir..."):
            try:
                full_tk = f"{tk_candle}.JK" if not tk_candle.endswith(".JK") else tk_candle
                df_c = yf.download(full_tk, period="1mo", interval="1d", progress=False)
                
                if not df_c.empty and len(df_c) >= 3:
                    if isinstance(df_c.columns, pd.MultiIndex): df_c.columns = df_c.columns.get_level_values(0)
                    
                    prev = df_c.iloc[-2]
                    curr = df_c.iloc[-1]
                    
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
                    
                    pola, warna = "TIDAK ADA POLA SPESIFIK", "#94a3b8"
                    kesimpulan = "Grafik berjalan normal tanpa adanya tanda-tanda pembalikan arah yang kuat. *Wait and See*."
                    
                    if is_bull_engulfing:
                        pola, warna = "🚀 BULLISH ENGULFING TERDETEKSI!", "#78ff00"
                        kesimpulan = "Luar Biasa! Terdapat candle hijau besar yang 'menelan' candle merah sebelumnya. Sinyal kuat bandar mulai akumulasi agresif."
                    elif is_hammer:
                        pola, warna = "🔨 HAMMER (PALU) TERDETEKSI!", "#78ff00"
                        kesimpulan = "Bagus! Ekor bawah yang panjang menandakan perlawanan kuat dari *buyer* (pembeli) saat harga dijatuhkan."
                    elif is_bear_engulfing:
                        pola, warna = "⚠️ BEARISH ENGULFING TERDETEKSI!", "#ff4b4b"
                        kesimpulan = "BAHAYA! Candle merah besar menelan candle hijau sebelumnya. Sinyal kuat bandar sedang guyur/buang barang massal."
                    elif is_shooting_star:
                        pola, warna = "🌠 SHOOTING STAR TERDETEKSI!", "#ff4b4b"
                        kesimpulan = "Hati-hati! Ekor atas panjang menandakan *buyer* gagal mengangkat harga karena tekanan jual bandar di atas sangat kuat."
                    elif is_doji:
                        pola, warna = "⚖️ POLA DOJI TERDETEKSI!", "#00f0ff"
                        kesimpulan = "Pasar sedang bimbang/bingung. Bersiap untuk ledakan arah harga berikutnya."
                        
                    st.markdown(f"<div class='dash-box' style='border:2px solid {warna}; text-align:center;'><h3 style='margin:0; color:{warna};'>{pola}</h3><p style='color:#fff; font-size:14px; margin-top:10px;'>{kesimpulan}</p></div>", unsafe_allow_html=True)
                    
                    df_chart = df_c.tail(15)
                    fig = go.Figure(data=[go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'], name='Candle')])
                    fig.update_layout(template="plotly_dark", height=400, margin=dict(l=0,r=0,t=10,b=0), xaxis_rangeslider_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig, use_container_width=True)
            except: st.error("Data tidak cukup untuk deteksi.")

elif menu == "🛰️ AUTO SCANNER":
    st.title("🛰️ ALGORITHMIC SCANNER")
    st.caption("Mesin pencari otomatis yang menscan ratusan saham di Bursa untuk mencarikan mana saham yang siap meledak/naik berdasarkan AI Score.")
    if 'results' not in st.session_state: st.session_state.results = None
    tickers = load_tickers()
    
    c1, c2 = st.columns([4,1])
    with c1: mode_scan = st.radio("PILIH SENSITIVITAS SCANNER:", ["Santai", "Profesional", "Pro"], horizontal=True)
    with c2: 
        if st.button("⚡ MULAI SCAN PASAR", use_container_width=True):
            res = run_scan(tickers, mode_scan)
            if not res.empty: st.session_state.results = res; st.rerun()
            else: st.warning("Scan selesai: Belum ada saham yang momentumnya cukup kuat saat ini.")

    if st.session_state.results is not None:
        df = st.session_state.results
        st.info(f"💡 **Kesimpulan:** Ditemukan **{len(df)} Saham** yang sedang memiliki momentum kenaikan yang bagus.")

        tab1, tab2, tab3 = st.tabs(["📱 KARTU RINGKAS", "📊 TABEL DATA", "📈 GRAFIK (CHART)"])
        with tab1: draw_mobile_cards(df)
        with tab2: st.dataframe(df.drop(columns=['FULL'], errors='ignore'), use_container_width=True, hide_index=True)
        with tab3:
            sel_t = st.selectbox("PILIH SAHAM UNTUK CEK GRAFIK:", df['TICKER'].tolist())
            full_t = df[df['TICKER'] == sel_t]['FULL'].values[0]
            c_data = yf.download(full_t, period="6mo", interval="1d", progress=False)
            if not c_data.empty:
                c_data.columns = [c[0] if isinstance(c, tuple) else c for c in c_data.columns]
                c_data['MA20'] = c_data['Close'].rolling(20).mean()
                c_data['MA50'] = c_data['Close'].rolling(50).mean()
                
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=c_data.index, open=c_data['Open'], high=c_data['High'], low=c_data['Low'], close=c_data['Close'], name='Price'), row=1, col=1)
                fig.add_trace(go.Scatter(x=c_data.index, y=c_data['MA20'], line=dict(color='#00f0ff', width=1.5), name='MA 20'), row=1, col=1)
                fig.add_trace(go.Scatter(x=c_data.index, y=c_data['MA50'], line=dict(color='#78ff00', width=1.5), name='MA 50'), row=1, col=1)
                colors = ['#78ff00' if row['Close'] >= row['Open'] else '#ff4b4b' for index, row in c_data.iterrows()]
                fig.add_trace(go.Bar(x=c_data.index, y=c_data['Volume'], marker_color=colors, name='Volume'), row=2, col=1)
                fig.update_layout(template="plotly_dark", height=500, margin=dict(l=0,r=0,t=20,b=0), xaxis_rangeslider_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)

elif menu == "⚡ STRATEGY SCANNER":
    st.markdown("<h2 style='color:#00f0ff;'>⚡ STRATEGY SCANNER (MA CROSSOVER)</h2>", unsafe_allow_html=True)
    st.caption("Pendeteksi persilangan (crossover) pada Moving Average. Mencari titik di mana tren harga sedang berubah dari turun menjadi naik tajam.")
    try:
        df_saham = pd.read_excel("daftar_saham.xlsx")
        watchlist = [t.strip() + ".JK" for t in df_saham['Kode'].dropna().astype(str).tolist()]
    except:
        st.error("Error membaca file Excel 'daftar_saham.xlsx'."); watchlist = []

    if st.button("🚀 MULAI CARI SINYAL", use_container_width=True):
        with st.spinner(f"Menganalisis perpaduan Tren & Jejak Bandar..."):
            results = get_trend_signals(watchlist)
            if results:
                st.info("💡 **Kesimpulan:** Cari saham yang bersatus **Golden Cross + AKUMULASI BANDAR (Warna Hijau)**, ini adalah sinyal beli paling matang dan aman.")
                for res in results:
                    st.markdown(f"<div class='dash-box' style='border: 1px solid {res['color']};'><h3 style='color:{res['color']}; margin:0; font-family:Orbitron; font-size:1.1rem;'>{res['status']}</h3><p style='margin:6px 0 0 0; color:#94a3b8;'>Saham: <b style='color:#fff;'>{res['ticker']}</b> | Harga: Rp {res['price']:,.0f}</p></div>", unsafe_allow_html=True)
            else: st.info("Tidak ada sinyal pembalikan tren (Cross) yang terdeteksi hari ini.")

elif menu == "⭐ WATCHLIST FAVORIT":
    st.title("⭐ WATCHLIST FAVORIT")
    st.caption("Simpan daftar saham andalanmu di sini agar sistem bisa menscan pergerakannya setiap hari khusus untukmu.")
    my_wl = get_watchlist(user_now)
    c_add, c_del = st.columns(2)
    with c_add:
        new_wl = st.text_input("Tambah Saham").upper()
        if st.button("➕ Tambah", use_container_width=True):
            if new_wl and f"{new_wl}.JK" not in my_wl: 
                add_watchlist(user_now, f"{new_wl}.JK"); st.success("Berhasil ditambahkan!"); st.rerun()
    with c_del:
        if my_wl:
            del_wl = st.selectbox("Hapus Saham", [t.replace(".JK","") for t in my_wl])
            if st.button("🗑️ Hapus", use_container_width=True):
                remove_watchlist(user_now, f"{del_wl}.JK"); st.warning("Berhasil dihapus!"); st.rerun()
                
    st.markdown("---")
    if my_wl:
        if st.button("⚡ SCAN SAHAM FAVORIT SAYA", use_container_width=True):
            res_wl = run_scan(my_wl, "Santai")
            if not res_wl.empty: draw_mobile_cards(res_wl)
            else: st.info("Belum ada momentum bagus dari daftar saham favoritmu hari ini.")

elif menu == "🎯 AUTO SUP/RES":
    st.title("🎯 AUTO SUPPORT & RESISTANCE")
    st.caption("AI otomatis melukis garis lantai (Support - area serok) dan garis atap (Resistance - area jual) agar kamu tidak tersesat beli di pucuk.")
    with st.expander("📖 CARA MEMBACA LEVEL KUNCI (PIVOT)", expanded=False):
        st.markdown("""
        * 🟢 **SUPPORT (S1, S2):** Lantai harga. Area **TERBAIK UNTUK BELI (Serok Bawah)**.
        * 🔴 **RESISTANCE (R1, R2):** Atap harga. Area **TERBAIK UNTUK JUAL (Take Profit)**.
        """)
        
    with st.form("f_pivot"):
        tk_pivot = st.text_input("Ketik Kode Saham", value="BBRI").upper().strip()
        btn_pivot = st.form_submit_button("ANALISIS LEVEL KUNCI", width="stretch")
        
    if btn_pivot:
        with st.spinner("Menghitung formula Pivot Point..."):
            try:
                full_tk = f"{tk_pivot}.JK" if not tk_pivot.endswith(".JK") else tk_pivot
                df_piv = yf.download(full_tk, period="1mo", interval="1d", progress=False)
                if not df_piv.empty:
                    if isinstance(df_piv.columns, pd.MultiIndex): df_piv.columns = df_piv.columns.get_level_values(0)
                    
                    recent_high = float(df_piv['High'][-20:].max())
                    recent_low = float(df_piv['Low'][-20:].min())
                    recent_close = float(df_piv['Close'].iloc[-1])
                    
                    pivot = (recent_high + recent_low + recent_close) / 3
                    r1 = (2 * pivot) - recent_low
                    s1 = (2 * pivot) - recent_high
                    r2 = pivot + (recent_high - recent_low)
                    s2 = pivot - (recent_high - recent_low)
                    
                    st.markdown(f"### Level Kunci: {tk_pivot}")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("🔴 RESISTANCE 2", f"Rp {r2:,.0f}")
                    c2.metric("🔴 RESISTANCE 1", f"Rp {r1:,.0f}")
                    c3.metric("🔵 PIVOT", f"Rp {pivot:,.0f}")
                    
                    c4, c5, c6 = st.columns(3)
                    c4.metric("🟢 SUPPORT 1", f"Rp {s1:,.0f}")
                    c5.metric("🟢 SUPPORT 2", f"Rp {s2:,.0f}")
                    c6.metric("➡️ HARGA SAAT INI", f"Rp {recent_close:,.0f}")
                    
                    if recent_close <= s1: st.success(f"💡 **Kesimpulan:** Harga di area **SUPPORT (Bawah)**. Saatnya cicil beli (*Buy on Weakness*).")
                    elif recent_close >= r1: st.error(f"💡 **Kesimpulan:** Harga di area **RESISTANCE (Atas)**. Rawan bantingan, hindari beli / Siap Jual.")
                    else: st.info(f"💡 **Kesimpulan:** Harga di area tengah (Netral).")
                    
                    df_chart = df_piv.tail(30)
                    fig = go.Figure(data=[go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'], name='Harga')])
                    fig.add_hline(y=r2, line_dash="dash", line_color="#ff4b4b", annotation_text="R2"); fig.add_hline(y=r1, line_dash="solid", line_color="#ff4b4b", annotation_text="R1")
                    fig.add_hline(y=pivot, line_dash="dot", line_color="#00f0ff", annotation_text="PIVOT")
                    fig.add_hline(y=s1, line_dash="solid", line_color="#78ff00", annotation_text="S1"); fig.add_hline(y=s2, line_dash="dash", line_color="#78ff00", annotation_text="S2")
                    fig.update_layout(template="plotly_dark", height=450, margin=dict(l=0,r=0,t=10,b=0), xaxis_rangeslider_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig, use_container_width=True)
            except: st.error("Data tidak cukup.")

elif menu == "📅 SIKLUS MUSIMAN":
    st.title("📅 SIKLUS MUSIMAN (SEASONALITY)")
    st.caption("Membongkar sejarah masa lalu. Mengetahui di bulan apa saja saham ini punya kebiasaan naik (Naik Terus) atau turun (Bulan Sial).")
    with st.form("f_season"):
        tk_season = st.text_input("Ketik Kode Saham", value="BBCA").upper().strip()
        btn_season = st.form_submit_button("ANALISIS DATA 5 TAHUN", width="stretch")
        
    if btn_season:
        with st.spinner("Membongkar sejarah harga 5 tahun terakhir..."):
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
                    st.info(f"💡 **Fakta Sejarah:** Saham **{tk_season}** paling sering **NAIK di bulan {best_month['Bulan']}** (Akurasi kemenangan: {best_month['Win Rate (%)']:.0f}%).")
                    
                    fig_season = px.bar(monthly_stats, x='Bulan', y='Win Rate (%)', color='Win Rate (%)', color_continuous_scale=["#ff4b4b", "#1e293b", "#78ff00"], text_auto='.0f')
                    fig_season.update_layout(template="plotly_dark", height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_season, use_container_width=True)
            except: st.error("Data sejarah tidak cukup.")

elif menu == "📟 CEK FUNDAMENTAL":
    st.markdown("""<style>.stMetric {border-left: 4px solid #00f0ff !important;}</style>""", unsafe_allow_html=True)
    st.title("📟 CEK FUNDAMENTAL")
    st.caption("Memeriksa kesehatan laporan keuangan perusahaan (Laba, Utang, Aset) untuk investasi jangka panjang yang aman.")
    col_in1, col_in2 = st.columns([3, 1])
    with col_in1: target_f = st.text_input("Ketik Kode Saham", value="BBCA").upper().strip()
    with col_in2: st.write("##"); btn_analyze = st.button("CEK PERUSAHAAN", width="stretch")

    if btn_analyze:
        full_tk = f"{target_f}.JK" if not target_f.endswith(".JK") else target_f
        with st.spinner("Menarik data laporan keuangan..."):
            try:
                info = yf.Ticker(full_tk).info
                current_price = info.get('currentPrice') or info.get('previousClose', 1)
                eps, bvps, per, pbv = info.get('trailingEps', 0) or 0, info.get('bookValue', 0) or 0, info.get('trailingPE', 0) or 0, info.get('priceToBook', 0) or 0
                roe = (info.get('returnOnEquity', 0) or 0) * 100
                der = info.get('debtToEquity', 0) or 0
                cr = info.get('currentRatio', 0) or 0
                
                st.markdown(f"### 🏢 {info.get('longName', target_f)}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("PE RATIO", f"{per:,.2f}x"); c2.metric("PBV RATIO", f"{pbv:,.2f}x")
                c3.metric("ROE (Profit)", f"{roe:,.2f}%"); c4.metric("DER (Utang)", f"{der:,.1f}%")

                graham = math.sqrt(22.5 * eps * bvps) if (eps > 0 and bvps > 0) else 0
                if current_price < graham: st.success(f"💡 Saham **MURAH / UNDERVALUED**. Harga Wajar Asli: Rp {graham:,.0f}")
                else: st.error(f"💡 Saham **MAHAL / OVERVALUED**. Harga Wajar Asli: Rp {graham:,.0f}")
            except: st.error("Data tidak ditemukan.")

elif menu == "⚔️ ADU SAHAM":
    st.title("⚔️ ADU SAHAM (BATTLE)")
    st.caption("Bandingkan dua saham dari sektor yang sama secara *Head-to-Head* untuk melihat mana yang valuasinya lebih murah dan untungnya lebih besar.")
    col_in1, col_in2 = st.columns(2)
    with col_in1: tk1 = st.text_input("Saham 1", value="BBCA").upper().strip()
    with col_in2: tk2 = st.text_input("Saham 2", value="BBRI").upper().strip()

    if st.button("🚀 ADU SEKARANG", width="stretch"):
        with st.spinner("Menghitung perbandingan..."):
            try:
                i1, i2 = yf.Ticker(f"{tk1}.JK").info, yf.Ticker(f"{tk2}.JK").info
                get_val = lambda d, k: d.get(k, 0) or 0
                st.markdown(f"<h1 style='text-align:center; color:#00f0ff;'>{tk1} VS {tk2}</h1>", unsafe_allow_html=True)
                df_compare = pd.DataFrame({
                    "METRIK": ["Harga Saat Ini", "PE Ratio", "PBV Ratio", "ROE"],
                    tk1: [f"Rp {get_val(i1, 'currentPrice'):,.0f}", f"{get_val(i1, 'trailingPE'):,.2f}x", f"{get_val(i1, 'priceToBook'):,.2f}x", f"{get_val(i1, 'returnOnEquity')*100:.2f}%"],
                    tk2: [f"Rp {get_val(i2, 'currentPrice'):,.0f}", f"{get_val(i2, 'trailingPE'):,.2f}x", f"{get_val(i2, 'priceToBook'):,.2f}x", f"{get_val(i2, 'returnOnEquity')*100:.2f}%"]
                })
                st.table(df_compare.set_index("METRIK"))
            except: st.error("Gagal menarik data.")

elif menu == "🌐 PETA SEKTOR":
    st.title("🌐 PETA PERGERAKAN SEKTOR")
    st.caption("Lihat sektor industri mana (Bank, Batu Bara, Konsumsi, dll) yang sedang diserbu uang besar hari ini. Berenanglah searah arus uang!")
    sectors = {
        "Perbankan": ["BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK"],
        "Energi/Batu Bara": ["ADRO.JK", "PTBA.JK", "HRUM.JK", "MEDC.JK"],
        "Bahan Baku/Emas": ["INCO.JK", "MDKA.JK", "ANTM.JK", "TPIA.JK"],
        "Ritel & Konsumsi": ["ASII.JK", "ACES.JK", "ERAA.JK", "MAPI.JK", "UNVR.JK", "ICBP.JK"],
        "Telekomunikasi": ["TLKM.JK", "ISAT.JK", "EXCL.JK"]
    }
    
    if st.button("⚡ CEK ARUS SEKTOR HARI INI", use_container_width=True):
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
                                c_now, c_prev = df_t['Close'].iloc[-1], df_t['Close'].iloc[-2]
                                sec_changes.append(((c_now - c_prev) / c_prev) * 100)
                        except: continue
                    if sec_changes: sector_data.append({"Sektor": sec_name, "Perubahan (%)": round(sum(sec_changes) / len(sec_changes), 2)})
            except: pass
            
            if sector_data:
                df_sec = pd.DataFrame(sector_data).sort_values(by="Perubahan (%)", ascending=False)
                fig_sec = px.bar(df_sec, x="Sektor", y="Perubahan (%)", color="Perubahan (%)", color_continuous_scale=["#ff4b4b", "#1e293b", "#78ff00"])
                fig_sec.update_layout(template="plotly_dark", height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_sec, use_container_width=True)

# =========================================================================
# 🔥 KALKULATOR TRADING (RISIKO & AVERAGING DOWN)
# =========================================================================
elif menu == "🧮 KALKULATOR TRADING":
    st.title("🧮 KALKULATOR TRADING")
    st.caption("Penyelamat nyawa dan modal. Gunakan kalkulator ini SEBELUM membeli saham agar porsi uangmu diatur dengan logika, bukan nafsu/emosi.")
    tab_risk, tab_avg = st.tabs(["🛡️ KALKULATOR RISIKO", "🛟 AVERAGING DOWN (NYANGKUT)"])
    
    with tab_risk:
        st.info("Hitung lot maksimal agar modal tidak habis saat terpaksa Cut Loss.")
        with st.form("risk_calc_form"):
            c1, c2 = st.columns(2)
            capital = c1.number_input("Modal Keseluruhan (Rp)", min_value=100000, value=10000000, step=500000)
            risk_pct = c2.number_input("Rela Rugi Maksimal (%)", min_value=0.1, max_value=10.0, value=2.0, step=0.1)
            c3, c4 = st.columns(2)
            entry_p = c3.number_input("Rencana Harga Beli (Rp)", min_value=1, value=5000)
            stop_loss_p = c4.number_input("Batas Harga Cut Loss (Rp)", min_value=1, value=4800)
            calc_btn = st.form_submit_button("HITUNG LOT AMAN", width="stretch")
            
        if calc_btn:
            if stop_loss_p >= entry_p: st.error("⚠️ Harga Cut Loss harus di bawah Harga Beli!")
            else:
                max_risk_idr = capital * (risk_pct / 100)
                risk_per_share = entry_p - stop_loss_p
                total_lots = math.floor((max_risk_idr / risk_per_share) / 100)
                actual_shares = total_lots * 100
                st.markdown("---")
                m1, m2, m3 = st.columns(3)
                m1.metric("BELI MAKSIMAL", f"{total_lots:,} Lot")
                m2.metric("MODAL TERPAKAI", f"Rp {actual_shares * entry_p:,.0f}")
                m3.metric("POTENSI RUGI (JIKA CL)", f"Rp {actual_shares * risk_per_share:,.0f}", delta_color="inverse")
                
    with tab_avg:
        st.info("💡 Penyelamat Mental: Jika sahammu nyangkut di atas, hitung berapa lot yang harus kamu beli di bawah untuk menurunkan harga rata-rata (Average Down).")
        with st.form("avg_calc_form"):
            c1, c2 = st.columns(2)
            p1 = c1.number_input("Harga Nyangkut (Di Atas)", min_value=1, value=1000)
            l1 = c2.number_input("Jumlah Lot Nyangkut", min_value=1, value=10)
            c3, c4 = st.columns(2)
            p2 = c3.number_input("Harga Saham Sekarang (Bawah)", min_value=1, value=800)
            l2 = c4.number_input("Rencana Beli Lot Baru", min_value=1, value=20)
            calc_avg_btn = st.form_submit_button("HITUNG AVERAGE BARU", width="stretch")
            
        if calc_avg_btn:
            if p2 >= p1: st.error("⚠️ Harga Baru harus lebih murah dari Harga Nyangkut!")
            else:
                total_modal_lama = p1 * l1 * 100
                total_modal_baru = p2 * l2 * 100
                total_lot_akhir = l1 + l2
                new_avg = (total_modal_lama + total_modal_baru) / (total_lot_akhir * 100)
                st.markdown("---")
                a1, a2, a3 = st.columns(3)
                a1.metric("AVERAGE BARUMU", f"Rp {new_avg:,.0f}")
                a2.metric("TOTAL LOT SEKARANG", f"{total_lot_akhir:,} Lot")
                a3.metric("BUTUH TAMBAHAN MODAL", f"Rp {total_modal_baru:,.0f}")
                st.success(f"💡 Cukup tunggu harga saham mantul naik ke **Rp {new_avg:,.0f}** dan kamu sudah bisa jual impas tanpa rugi (BEP).")

elif menu == "💰 PEMBURU DIVIDEN":
    st.title("💰 PEMBURU DIVIDEN")
    st.caption("Cari tahu riwayat bagi-bagi hasil (dividen) perusahaan kepada investornya. Sangat cocok untuk investor pasif (nabung saham).")
    div_tk = st.text_input("Ketik Kode Saham", value="ITMG").upper().strip()
    if st.button("CEK DIVIDEN", width="stretch"):
        with st.spinner("Menggali riwayat dividen..."):
            try:
                t_obj = yf.Ticker(f"{div_tk}.JK" if not div_tk.endswith(".JK") else div_tk)
                div_yield = (t_obj.info.get('dividendYield', 0) or 0) * 100
                st.metric("YIELD (BUNGA TAHUNAN)", f"{div_yield:.2f}%")
                divs = t_obj.dividends
                if not divs.empty:
                    df_divs = pd.DataFrame(divs).reset_index()
                    df_divs.columns = ['Tanggal Cair', 'Nominal (Rp/lembar)']
                    df_divs['Tanggal Cair'] = pd.to_datetime(df_divs['Tanggal Cair']).dt.strftime('%Y-%m-%d')
                    st.dataframe(df_divs.sort_values(by='Tanggal Cair', ascending=False).head(10), use_container_width=True, hide_index=True)
            except: st.error("Gagal memuat riwayat dividen.")

elif menu == "🧬 KORELASI SAHAM":
    st.title("🧬 CEK KORELASI SAHAM")
    st.caption("Fitur untuk melihat 'Saudara Kembar' saham. Jangan membeli saham yang pergerakannya selalu searah (angka mendekati +1.0) untuk menjaga portofolio tetap terdiversifikasi.")
    input_tkrs = st.text_input("MASUKKAN KODE SAHAM (PISAHKAN KOMA)", value="BBCA, BBRI, AMRT, TLKM")
    if st.button("CEK HUBUNGAN SAHAM", width="stretch"):
        with st.spinner("Memproses hubungan matematika..."):
            try:
                raw_list = [t.strip().upper() + ".JK" for t in input_tkrs.split(",")]
                data_corr = yf.download(raw_list, period="6mo", interval="1d", progress=False)['Close']
                if not data_corr.empty:
                    if isinstance(data_corr.columns, pd.MultiIndex): data_corr.columns = data_corr.columns.get_level_values(0)
                    data_corr.columns = [c.replace(".JK", "") for c in data_corr.columns]
                    fig_corr = px.imshow(data_corr.corr(), text_auto=True, color_continuous_scale="RdBu_r", zmin=-1, zmax=1)
                    fig_corr.update_layout(template="plotly_dark", height=400, margin=dict(l=0,r=0,t=20,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_corr, use_container_width=True)
            except: st.error("Gagal mengunduh data.")

elif menu == "🏛️ JEJAK BANDAR":
    st.title("🏛️ JEJAK BANDAR (MONEY FLOW)")
    st.caption("Detektor aliran dana institusi / paus (Chaikin Money Flow). Lacak diam-diam apakah bandar sedang menimbun barang secara diam-diam.")
    ff_tk = st.text_input("Ketik Kode Saham", value="BBRI").upper().strip()
    if st.button("LACAK BANDAR SEKARANG", width="stretch"):
        with st.spinner("Melacak aktivitas paus..."):
            try:
                df_ff = yf.download(f"{ff_tk}.JK" if not ff_tk.endswith(".JK") else ff_tk, period="3mo", interval="1d", progress=False)
                if not df_ff.empty:
                    if isinstance(df_ff.columns, pd.MultiIndex): df_ff.columns = df_ff.columns.get_level_values(0)
                    df_ff['Multiplier'] = ((df_ff['Close'] - df_ff['Low']) - (df_ff['High'] - df_ff['Close'])) / (df_ff['High'] - df_ff['Low'] + 1e-9)
                    df_ff['CMF_20'] = (df_ff['Multiplier'] * df_ff['Volume']).rolling(20).sum() / df_ff['Volume'].rolling(20).sum()
                    df_ff['CMF_20'] = df_ff['CMF_20'].fillna(0) 
                    latest_cmf = df_ff['CMF_20'].iloc[-1]
                    
                    if latest_cmf > 0.05: status_flow, color_flow = "AKUMULASI (DIBORONG BANDAR) 🚀", "#78ff00"
                    elif latest_cmf < -0.05: status_flow, color_flow = "DISTRIBUSI (DIBUANG BANDAR) ⚠️", "#ff4b4b"
                    else: status_flow, color_flow = "NETRAL / SIDEWAYS 💤", "#00f0ff"
                    
                    st.markdown(f"<div class='dash-box' style='text-align:center; border: 1px solid {color_flow};'><h3 style='color:#fff; margin:0;'>Status: <span style='color:{color_flow};'>{status_flow}</span></h3></div>", unsafe_allow_html=True)
                    fig_mf = px.area(df_ff.reset_index(), x='Date', y='CMF_20')
                    fig_mf.add_hline(y=0, line_dash="dash", line_color="gray")
                    fig_mf.update_layout(template="plotly_dark", height=300, margin=dict(l=0,r=0,t=10,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_mf, use_container_width=True)
            except: st.error("Data saham tidak ditemukan.")

elif menu == "📰 BERITA PASAR":
    st.title("📰 FINANCIAL INTELLIGENCE CENTER")
    st.caption("Pusat intelijen yang mengumpulkan tajuk berita pasar modal dan memisahkan berita bersentimen Positif atau Negatif.")
    
    st.markdown("### 🌍 Global Macro & Commodity Radar")
    with st.spinner("Menarik data pasar global..."):
        try:
            macro_tickers = {"Dow Jones": "^DJI", "Nasdaq": "^IXIC", "Minyak (WTI)": "CL=F", "Emas (Gold)": "GC=F", "Kurs (USD/IDR)": "IDR=X", "Batu Bara": "MTF=F"}
            macro_data = yf.download(list(macro_tickers.values()), period="5d", interval="1d", progress=False)
            c1, c2, c3 = st.columns(3); c4, c5, c6 = st.columns(3)
            columns = [c1, c2, c3, c4, c5, c6]
            for i, (name, symbol) in enumerate(macro_tickers.items()):
                try:
                    close_data = macro_data['Close'][symbol].dropna()
                    if len(close_data) >= 2:
                        last_price, prev_price = float(close_data.iloc[-1]), float(close_data.iloc[-2])
                        pct_change = ((last_price - prev_price) / prev_price) * 100
                        if name == "Kurs (USD/IDR)": columns[i].metric(label=name, value=f"Rp {last_price:,.0f}", delta=f"{pct_change:.2f}%", delta_color="inverse")
                        else: columns[i].metric(label=name, value=f"{last_price:,.2f}", delta=f"{pct_change:.2f}%")
                except: columns[i].metric(label=name, value="N/A", delta="0.00%")
        except: st.warning("Data Global Macro tidak dapat diakses.")

    st.markdown("---")
    t_gen, t_spec, t_corp = st.tabs(["🌐 BERITA PASAR", "🔍 CARI BERITA SAHAM", "📅 CORPORATE ACTION"])
    
    def analyze_sentiment(text):
        pos_words = ['naik', 'laba', 'untung', 'lonjak', 'akuisisi', 'investasi', 'meroket', 'cuan', 'diborong', 'dividen']
        neg_words = ['turun', 'rugi', 'anjlok', 'suspend', 'kasus', 'gagal', 'merosot', 'jeblok', 'dilepas', 'resesi']
        score = sum(1 for w in pos_words if w in text.lower()) - sum(1 for w in neg_words if w in text.lower())
        if score > 0: return "🟢 POSITIF", "#78ff00"
        elif score < 0: return "🔴 NEGATIF", "#ff4b4b"
        else: return "⚪ NETRAL", "#94a3b8"

    def check_if_new(p_parsed):
        if p_parsed and (time.time() - mktime(p_parsed)) < (12 * 3600): return "🔥 NEW"
        return ""

    headers = {'User-Agent': 'Mozilla/5.0'}

    with t_gen:
        with st.spinner("Menarik tajuk berita..."):
            try:
                feed = feedparser.parse(requests.get("https://news.google.com/rss/search?q=saham+indonesia+ihsg&hl=id&gl=ID&ceid=ID:id", headers=headers, timeout=5).content)
                for entry in feed.entries[:10]: 
                    sent_text, sent_color = analyze_sentiment(entry.title)
                    fire_badge = check_if_new(entry.published_parsed if hasattr(entry, 'published_parsed') else None)
                    st.markdown(f"<div class='dash-box' style='border:1px solid rgba(0, 240, 255, 0.2); padding:16px; margin-bottom:12px;'><div style='display:flex; justify-content:space-between; margin-bottom:8px;'><span style='font-size:11px; font-weight:bold; color:{sent_color};'>{sent_text}</span><span style='font-size:11px; color:#ff4b4b; font-weight:bold;'>{fire_badge}</span></div><a href='{entry.link}' target='_blank' style='color:#00f0ff; text-decoration:none; font-size:1rem; font-weight:bold;'>{entry.title}</a><p style='color:#94a3b8; font-size:0.8rem; margin-top:8px; margin-bottom:0;'>⏰ {entry.published}</p></div>", unsafe_allow_html=True)
            except: st.error("Koneksi berita terputus.")
                
    with t_spec:
        with st.form("f_news"):
            search_t = st.text_input("Ketik Kode Saham").upper().strip()
            btn_news = st.form_submit_button("CARI BERITA", width="stretch")
        if btn_news and search_t:
            with st.spinner(f"Mencari berita {search_t}..."):
                try:
                    feed_spec = feedparser.parse(requests.get(f"https://news.google.com/rss/search?q={search_t}+saham&hl=id&gl=ID&ceid=ID:id", headers=headers, timeout=5).content)
                    if not feed_spec.entries: st.warning("Berita tidak ditemukan.")
                    for entry in feed_spec.entries[:8]: 
                        sent_text, sent_color = analyze_sentiment(entry.title)
                        st.markdown(f"<div class='dash-box' style='border:1px solid rgba(0, 240, 255, 0.2); padding:16px; margin-bottom:12px;'><div style='display:flex; justify-content:space-between; margin-bottom:8px;'><span style='font-size:11px; font-weight:bold; color:{sent_color};'>{sent_text}</span></div><a href='{entry.link}' target='_blank' style='color:#00f0ff; text-decoration:none; font-size:1rem; font-weight:bold;'>{entry.title}</a></div>", unsafe_allow_html=True)
                except: st.error("Pencarian berita gagal.")
                
    with t_corp:
        st.info("💡 Pantau berita jadwal *Cum Date* Dividen atau Right Issue terbaru di sini agar tidak ketinggalan kereta.")
        with st.spinner("Memindai aksi korporasi..."):
            try:
                feed_corp = feedparser.parse(requests.get("https://news.google.com/rss/search?q=jadwal+dividen+OR+right+issue+OR+cum+date+saham+indonesia&hl=id&gl=ID&ceid=ID:id", headers=headers, timeout=5).content)
                for entry in feed_corp.entries[:10]: 
                    st.markdown(f"<div class='dash-box' style='border:1px solid #78ff00; padding:16px; margin-bottom:12px;'><div style='display:flex; justify-content:space-between; margin-bottom:8px;'><span style='font-size:11px; font-weight:bold; color:#78ff00;'>🟢 INFO CORPORATE ACTION</span></div><a href='{entry.link}' target='_blank' style='color:#fff; text-decoration:none; font-size:1rem; font-weight:bold;'>{entry.title}</a></div>", unsafe_allow_html=True)
            except: st.error("Koneksi jadwal terputus.")

elif menu == "💼 DOMPET TRADING":
    st.title("💼 BUKU DOMPET TRADING & JURNAL")
    st.caption("Pusat pencatatan transaksi pembelian dan penjualan sahammu. AI akan bertindak sebagai mentor yang menilai akurasi dari setiap strategi yang kamu pakai.")
    
    c_title, c_toggle = st.columns([3, 1])
    show_saldo = c_toggle.checkbox("👁️ Tampilkan Saldo", value=False)
    format_privacy = lambda v: f"Rp {v:,.0f}" if show_saldo else "Rp *****"

    tab1, tab2, tab3 = st.tabs(["📈 SAHAM DIMILIKI", "📜 HISTORY JUAL", "📊 JURNAL AI"])
    
    with tab1:
        with st.expander("➕ CATAT PEMBELIAN BARU", expanded=False):
            with st.form("form_add_portfolio", clear_on_submit=True):
                c1, c2 = st.columns(2)
                t_in = c1.text_input("Kode Saham")
                l_in = c2.number_input("Berapa Lot?", min_value=1)
                c3, c4 = st.columns(2)
                p_in = c3.number_input("Harga Beli (Rp)", min_value=0)
                strat_in = c4.selectbox("Strategi (Alasan Kamu Beli)?", ["Golden Cross MA", "Breakout Resistance", "Serok Bawah (Support)", "Ikut Berita", "Fundamental Bagus", "Feeling / FOMO"])
                if st.form_submit_button("SIMPAN KE DOMPET", width="stretch"):
                    if t_in and p_in > 0: 
                        add_to_portfolio(user_now, t_in, p_in, l_in, 0, 0, strat_in)
                        st.success("Berhasil dicatat!"); st.rerun()

        df_p = get_user_portfolio(user_now, role)
        if not df_p.empty:
            tickers_jk = [f"{t}.JK" for t in df_p['ticker'].unique()]
            try:
                live_prices = yf.download(tickers_jk, period="1d", progress=False, threads=True)['Close'].iloc[-1].to_dict() if len(tickers_jk) > 1 else {tickers_jk[0]: float(yf.download(tickers_jk, period="1d", progress=False)['Close'].iloc[-1])}
            except: live_prices = {}

            def calc_active(row):
                tk, bp, lots = f"{row['ticker']}.JK", row['buy_price'], row['lots']
                curr = float(live_prices.get(tk, bp))
                cost, val = float(bp * lots * 100), float(curr * lots * 100)
                return pd.Series([curr, cost, val, (val-cost)])

            df_p[['Live', 'Cost', 'Value', 'P/L']] = df_p.apply(calc_active, axis=1)
            t_inv, t_pl = df_p['Cost'].sum(), df_p['P/L'].sum()
            
            m1, m2, m3 = st.columns(3)
            m1.metric("MODAL AWAL", format_privacy(t_inv))
            m2.metric("UNTUNG/RUGI", format_privacy(t_pl), f"{(t_pl/t_inv*100 if t_inv!=0 else 0):.2f}%" if show_saldo else "*****")
            m3.metric("UANG SEKARANG", format_privacy(t_inv + t_pl))

            st.markdown("---")
            for i, row in df_p.iterrows():
                strat_label = row.get('strategy', 'Bebas')
                with st.expander(f"📦 {row['ticker']} | {int(row['lots'])} Lots"):
                    st.markdown(f"<span style='background:#1e293b; color:#00f0ff; padding:4px 8px; border-radius:4px; font-size:10px;'>Strategi Waktu Beli: {strat_label}</span>", unsafe_allow_html=True)
                    st.write("")
                    c_price, c_lots, c_btn = st.columns([2, 2, 1])
                    s_price = c_price.number_input("Harga Laku Dijual (Rp)", value=float(row['Live']), key=f"s_prc_{row['id']}")
                    s_lots = c_lots.number_input("Berapa Lot Yang Dijual?", min_value=1, max_value=int(row['lots']), value=int(row['lots']), key=f"s_lot_{row['id']}")
                    if c_btn.button("CATAT JUAL", key=f"btn_s_{row['id']}", use_container_width=True):
                        st.toast(sell_position(user_now, row['id'], row['ticker'], row['buy_price'], s_price, row['lots'], s_lots)); time.sleep(1); st.rerun()
        else: st.info("Dompetmu masih kosong.")

    with tab2:
        df_h = conn_gs.read(worksheet="history", ttl=0)
        if not df_h.empty:
            df_h['pnl'] = pd.to_numeric(df_h['pnl'], errors='coerce')
            if role != 'admin': df_h = df_h[df_h['username'] == user_now]
            for idx, h_row in df_h.sort_values(by='date', ascending=False).iterrows():
                with st.expander(f"{h_row['date']} | {h_row['ticker']}"):
                    c_t, c_b = st.columns([4,1])
                    c_t.write(f"Strategi: **{h_row.get('strategy', 'Tidak Tercatat')}**")
                    c_t.write(f"Beli: Rp {h_row['buy_price']} | Jual: Rp {h_row['sell_price']} | Laku: {h_row['lots']} Lot | Cuan/Rugi: {format_privacy(h_row['pnl'])}")
                    if c_b.button("🗑️ Hapus", key=f"del_h_{h_row['id']}"):
                        df_h_all = conn_gs.read(worksheet="history", ttl=0)
                        idx_del_h = df_h_all.index[df_h_all['id'] == h_row['id']].tolist()
                        if idx_del_h: conn_gs.update(worksheet="history", data=df_h_all.drop(idx_del_h[0]).reset_index(drop=True)); st.rerun()

    with tab3: 
        if 'df_h' in locals() and not df_h.empty:
            st.markdown("### 🤖 JURNAL EVALUASI MENTOR AI")
            st.caption("AI akan mengevaluasi strategi mana yang paling sering membuatmu untung berdasarkan histori transaksimu.")
            if 'strategy' in df_h.columns:
                strat_analysis = df_h.groupby('strategy').apply(
                    lambda x: pd.Series({'Total Trading': len(x), 'Win Rate (%)': (x['pnl'] > 0).mean() * 100})
                ).reset_index()
                
                if not strat_analysis.empty:
                    best_strat = strat_analysis.loc[strat_analysis['Win Rate (%)'].idxmax()]
                    st.success(f"💡 **Saran AI:** Kamu paling jago saat pakai strategi **'{best_strat['strategy']}'** (Akurasi kemenangan {best_strat['Win Rate (%)']:.0f}%). Tingkatkan strategi ini!")
            
            total_trades = len(df_h)
            win_trades = len(df_h[df_h['pnl'] > 0])
            win_rate = (win_trades / total_trades) * 100 if total_trades > 0 else 0
            
            c1, c2 = st.columns(2)
            c1.metric("WIN RATE KESELURUHAN", f"{win_rate:.1f}%")
            c2.metric("TOTAL TRANSAKSI JUAL", f"{total_trades}x")

elif menu == "⚙️ USER MANAGEMENT":
    st.title("⚙️ USER MANAGEMENT")
    st.caption("Panel khusus Admin untuk mengelola data anggota.")
    df_u = conn_gs.read(worksheet="users", ttl=0)
    st.dataframe(df_u[['username', 'role', 'last_login', 'location']], use_container_width=True, hide_index=True)
    with st.form("add_u"):
        nu, np, nr = st.text_input("User ID Baru"), st.text_input("Password", type="password"), st.selectbox("Role", ["user", "admin"])
        if st.form_submit_button("BUAT AKUN BARU", width="stretch"):
            if add_user_db(nu, np, nr): st.success("Dibuat!"); st.rerun()
    with st.form("del_u"):
        du = st.text_input("ID yang mau dihapus")
        if st.form_submit_button("HAPUS AKUN", width="stretch"):
            if delete_user_db(du): st.warning("Dihapus!"); st.rerun()

elif menu == "🔒 KEAMANAN":
    st.title("🔒 GANTI PASSWORD")
    st.caption("Gunakan kombinasi angka dan huruf untuk mengamankan data portofoliomu.")
    with st.form("p"):
        new_p = st.text_input("Ketik Password Barumu di sini", type="password")
        if st.form_submit_button("SIMPAN PASSWORD", width="stretch"):
            if update_password_db(user_now, new_p): st.success("Password berhasil diubah!")

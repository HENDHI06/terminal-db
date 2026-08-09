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
    if not user_data.empty: return user_data.iloc[0]['last_login'], user_data.iloc[0]['ip_address'], user_data.iloc[0]['location']
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

# --- 1. TEMA AWAL (DARK CYBER) + OPTIMASI SENTUHAN HP ---
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

div[data-testid="stForm"] {
    background: rgba(13, 18, 30, 0.85) !important;
    border: 1px solid rgba(0, 240, 255, 0.25) !important;
    border-top: 3px solid #00f0ff !important;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.7);
    border-radius: 16px; padding: 25px !important; backdrop-filter: blur(20px);
}
div[data-testid="stForm"] label p {
    font-family: 'Orbitron', sans-serif !important; color: #78ff00 !important; font-size: 0.75rem !important; letter-spacing: 2px;
}
div[data-testid="stForm"] input {
    background: rgba(3, 6, 12, 0.8) !important;
    border: 1px solid rgba(0, 240, 255, 0.2) !important;
    color: #00f0ff !important; font-family: 'JetBrains Mono', monospace !important;
    border-radius: 8px; height: 48px; font-weight:bold; font-size:16px;
}

div[data-testid="stMetric"], .stDataFrame, .stTabs, div[data-testid="stExpander"] {
    background: rgba(13, 18, 30, 0.7) !important;
    border: 1px solid rgba(255, 255, 255, 0.07) !important;
    border-radius: 12px !important; backdrop-filter: blur(12px);
}
[data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace !important; font-size: 1.8rem !important; color: #78ff00 !important; }
[data-testid="stMetricLabel"] { color: #94a3b8 !important; font-weight: 600; text-transform: uppercase; font-size: 0.8rem; }

[data-testid="stSidebar"] { background: #090d16; border-right: 1px solid rgba(255, 255, 255, 0.05); }

/* Menu Radio Button (Ukuran Sentuh HP Diperbesar & Empuk) */
div[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label {
    background: rgba(255, 255, 255, 0.01) !important; 
    border: 1px solid rgba(255, 255, 255, 0.03) !important;
    border-radius: 8px !important; 
    padding: 14px 16px !important; 
    margin-bottom: 8px !important;
}
div[data-testid="stSidebar"] .stRadio label p {
    font-family: 'Orbitron', sans-serif !important; font-size: 0.8rem !important; color: #64748b !important; letter-spacing: 1.5px;
}
div[data-testid="stSidebar"] .stRadio div[role="radiogroup"] [aria-checked="true"] {
    background: linear-gradient(90deg, rgba(0, 240, 255, 0.12), rgba(120, 255, 0, 0.05)) !important;
    border: 1px solid rgba(0, 240, 255, 0.4) !important; border-left: 4px solid #78ff00 !important;
}
div[data-testid="stSidebar"] .stRadio div[role="radiogroup"] [aria-checked="true"] p { color: #ffffff !important; }

.stButton>button {
    background: linear-gradient(135deg, rgba(0, 240, 255, 0.15), rgba(120, 255, 0, 0.15));
    border: 1px solid rgba(0, 240, 255, 0.4); color: #78ff00 !important;
    border-radius: 8px; font-family: 'Orbitron', sans-serif; font-weight: 700; font-size: 0.8rem;
    min-height: 48px;
}
.stButton>button:hover {
    background: linear-gradient(135deg, #00f0ff, #78ff00); color: #07090f !important;
}
</style>
""", unsafe_allow_html=True)

# --- 2. AUTHENTICATION (ANTI ERROR) ---
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
                role = check_login_db(u, p)
                if role:
                    update_login_info(u)
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

            multiplier = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) / (df['High'] - df['Low'] + 1e-9)
            cmf_series = (multiplier * df['Volume']).rolling(20).sum() / df['Volume'].rolling(20).sum()
            cmf_series = cmf_series.fillna(0)
            cmf = cmf_series.iloc[-1]

            tr1 = df['High'] - df['Low']
            tr2 = (df['High'] - df['Close'].shift()).abs()
            tr3 = (df['Low'] - df['Close'].shift()).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr_val = tr.rolling(14).mean().iloc[-1]
            if pd.isna(atr_val): atr_val = c_now * 0.03
                
            ai_score = (chg * 0.4) + (rsi * 0.2) + ((val_tr / 1e9) * 0.2) + (10 if is_breakout else 0) + (cmf * 20)

            results.append({
                "TICKER": t.replace(".JK", ""), "LAST": float(c_now), "CHG%": round(chg, 2),
                "RSI": round(rsi, 1), "VAL(M)": round(val_tr / 1_000_000, 1), 
                "BANDAR": "AKUMULASI 🚀" if cmf > 0 else "DISTRIBUSI ⚠️",
                "AI_SCORE": round(ai_score, 2),
                "BREAKOUT": "YA" if is_breakout else "TDK",
                "TP 1": float(c_now + (1.5 * atr_val)), "TP 2": float(c_now + (2.5 * atr_val)), "EXIT/CL": float(c_now - (1.0 * atr_val)), "FULL": t
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
        <p style='font-size:9px; color:#94a3b8; margin:2px 0; font-family:JetBrains Mono;'>LOC: {loc_l}</p>
    </div>
    """, unsafe_allow_html=True)

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
if st.sidebar.button("🔴 KELUAR APLIKASI", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.role = None
    st.rerun()


# --- 5. CONTENT AREA ---

if menu == "SCANNER":
    st.title("🛰️ ALGORITHMIC SCANNER")
    with st.expander("📖 PANDUAN & WAKTU EKSEKUSI", expanded=False):
        st.markdown("""
        **🕒 WAKTU TERBAIK PENGGUNAAN:**
        * **09:15 - 10:00 WIB:** Untuk cari saham momentum yang meloncat di awal sesi buka.
        * **15:30 - 15:50 WIB:** Saat *Pre-Closing* untuk beli dan tahan (swing) ke esok hari.
        
        **CARA BACA:**
        * **AI Score:** Kekuatan momentum (Makin tinggi angkanya, makin kuat sinyal belinya).
        * **Jual Untung (TP):** Harga antre jual untuk mengamankan keuntungan.
        * **Jual Rugi (CL):** Harga batas bawah. Segera jual jika harga turun menyentuh angka ini.
        """)

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
        st.info(f"💡 **Kesimpulan:** Ditemukan **{len(df)} Saham** yang sedang memiliki momentum kenaikan yang sangat bagus hari ini.")

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

elif menu == "STRATEGY SCANNER":
    st.markdown("<h2 style='color:#00f0ff;'>⚡ STRATEGY SCANNER (MA CROSSOVER)</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN & WAKTU EKSEKUSI", expanded=False):
        st.markdown("""
        **🕒 WAKTU TERBAIK PENGGUNAAN:**
        * **16:00 WIB ke atas (Bursa Tutup):** Sinyal MA dihitung paling akurat menggunakan harga penutupan bursa.
        """)
    
    try:
        df_saham = pd.read_excel("daftar_saham.xlsx")
        watchlist = [t.strip() + ".JK" for t in df_saham['Kode'].dropna().astype(str).tolist()]
    except:
        st.error("Error membaca file Excel 'daftar_saham.xlsx'."); watchlist = []

    if st.button("🚀 MULAI CARI SINYAL", use_container_width=True):
        with st.spinner(f"Menganalisis perpaduan Tren & Jejak Bandar..."):
            results = get_trend_signals(watchlist)
            if results:
                st.info("💡 **Kesimpulan:** Perhatikan status di bawah ini. Cari saham yang bersatus **Golden Cross + AKUMULASI BANDAR**, ini adalah sinyal beli paling matang dan aman.")
                for res in results:
                    st.markdown(f"<div style='border: 1px solid {res['color']}; background: rgba(13,18,30,0.8); padding: 16px; border-radius: 12px; margin-bottom: 12px;'><h3 style='color:{res['color']}; margin:0; font-family:Orbitron; font-size:1rem;'>{res['status']}</h3><p style='margin:6px 0 0 0; color:#94a3b8;'>Saham: <b style='color:#fff;'>{res['ticker']}</b> | Harga: Rp {res['price']:,.0f}</p></div>", unsafe_allow_html=True)
            else: st.info("Tidak ada sinyal pembalikan tren (Cross) yang terdeteksi hari ini.")

elif menu == "WATCHLIST":
    st.title("⭐ WATCHLIST FAVORIT")
    with st.expander("📖 PANDUAN & WAKTU EKSEKUSI", expanded=False):
        st.markdown("""
        **🕒 WAKTU TERBAIK PENGGUNAAN:**
        * Bebas kapan saja selama jam bursa.
        """)
        
    my_wl = get_watchlist(user_now)
    c_add, c_del = st.columns(2)
    with c_add:
        new_wl = st.text_input("Tambah Saham (Contoh: BBCA)").upper()
        if st.button("➕ Tambah ke Favorit", use_container_width=True):
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
            if not res_wl.empty: 
                st.info("💡 **Kesimpulan:** Saham di bawah ini adalah saham favoritmu yang sedang memunculkan sinyal momentum bagus hari ini.")
                draw_mobile_cards(res_wl)
            else: st.info("Belum ada pergerakan atau momentum yang bagus dari daftar saham favoritmu hari ini.")
    else: st.info("Daftar pantauanmu masih kosong.")

elif menu == "FUNDAMENTAL":
    st.markdown("""<style>.stMetric {border-left: 4px solid #00f0ff !important;}</style>""", unsafe_allow_html=True)
    st.title("📟 CEK FUNDAMENTAL PERUSAHAAN")
    with st.expander("📖 PANDUAN & WAKTU EKSEKUSI", expanded=False):
        st.markdown("""
        **🕒 WAKTU TERBAIK PENGGUNAAN:**
        * Akhir pekan (Sabtu/Minggu) untuk meriset saham yang cocok untuk tabungan investasi jangka panjang.
        """)
    
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
                target_mean = info.get('targetMeanPrice', current_price) or current_price
                div_yield = (info.get('dividendYield', 0) or 0) * 100
                cr = info.get('currentRatio', 0) or 0
                
                st.markdown(f"### 🏢 {info.get('longName', target_f)} <span style='color:#64748b; font-size:0.8rem;'>| Sektor: {info.get('sector', 'N/A')}</span>", unsafe_allow_html=True)
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("PE RATIO", f"{per:,.2f}x")
                c2.metric("PBV RATIO", f"{pbv:,.2f}x")
                c3.metric("ROE (Profit)", f"{roe:,.2f}%")
                c4.metric("DIV YIELD", f"{div_yield:,.2f}%")

                graham = math.sqrt(22.5 * eps * bvps) if (eps > 0 and bvps > 0) else 0
                
                if current_price < graham:
                    st.success(f"💡 **Kesimpulan Valuasi:** Harga wajar saham ini seharusnya **Rp {graham:,.0f}**, tetapi harga di pasar sekarang baru Rp {current_price:,.0f}. Berarti saham ini masih sangat **MURAH / UNDERVALUED**.")
                else:
                    st.error(f"💡 **Kesimpulan Valuasi:** Harga wajar saham ini seharusnya cuma **Rp {graham:,.0f}**, tetapi harga pasar sekarang sudah Rp {current_price:,.0f}. Berarti saham ini sudah tergolong **MAHAL / OVERVALUED**.")

                st.markdown("---")
                st.write("🛡️ **RISK ASSESSMENT MATRIX (TINGKAT KEAMANAN)**")
                t_assets, t_debt = info.get('totalAssets', 1) or 1, info.get('totalDebt', 1) or 1
                z = (1.2 * (info.get('workingCapital',0)/t_assets)) + (3.3 * (info.get('ebitda',0)/t_assets)) + (0.6 * (info.get('marketCap',0)/t_debt))
                z_color = "#78ff00" if z > 2.9 else "#ffcc00" if z > 1.8 else "#ff4b4b"
                
                rc1, rc2, rc3 = st.columns(3)
                rc1.metric("Current Ratio", f"{cr:.2f}x", delta="Aman" if cr > 1.5 else "Rentan")
                rc2.metric("Rasio Utang (DER)", f"{der:.1f}%", delta="Bahaya" if der > 150 else "Aman", delta_color="inverse")
                with rc3: st.markdown(f"<div style='background:rgba(13,18,30,0.8); border:1px solid {z_color}; padding:14px; border-radius:12px; text-align:center;'><p style='margin:0; font-size:10px; color:{z_color}; font-family:Orbitron;'>ALTMAN Z-SCORE</p><h3 style='margin:4px 0 0 0; color:{z_color}; font-family:JetBrains Mono;'>{z:.2f}</h3></div>", unsafe_allow_html=True)

                if z > 2.9:
                    st.info(f"💡 **Kesimpulan Keuangan:** Perusahaan ini **SANGAT SEHAT** dan sangat jauh dari risiko kebangkrutan.")
                elif z > 1.8:
                    st.warning(f"💡 **Kesimpulan Keuangan:** Perusahaan ini **CUKUP AMAN**, namun perlu dipantau tingkat utangnya.")
                else:
                    st.error(f"💡 **Kesimpulan Keuangan:** HATI-HATI! Perusahaan ini **RAWAN KEBANGKRUTAN** karena rasio utang yang buruk atau profit yang minim.")

            except Exception as e: st.error("Data tidak ditemukan atau belum rilis laporan keuangan.")

elif menu == "TICKER COMPARISON":
    st.title("⚔️ ADU SAHAM (BATTLE)")
    with st.expander("📖 PANDUAN & WAKTU EKSEKUSI", expanded=False):
        st.markdown("""
        **🕒 WAKTU TERBAIK PENGGUNAAN:**
        * Kapan pun (Sangat cocok saat kamu bingung mau pilih saham A atau saham B di sektor yang sama, contoh: BBCA vs BBRI).
        """)
        
    col_in1, col_in2 = st.columns(2)
    with col_in1: tk1 = st.text_input("Saham 1", value="BBCA").upper().strip()
    with col_in2: tk2 = st.text_input("Saham 2", value="BBRI").upper().strip()

    if st.button("🚀 ADU SEKARANG", width="stretch"):
        with st.spinner("Menghitung perbandingan kekuatan..."):
            try:
                i1, i2 = yf.Ticker(f"{tk1}.JK").info, yf.Ticker(f"{tk2}.JK").info
                get_val = lambda d, k: d.get(k, 0) or 0
                st.markdown(f"<div style='display: flex; justify-content: space-around; align-items: center; background: rgba(13,18,30,0.8); padding: 20px; border-radius: 14px; border: 1px solid rgba(0,240,255,0.3);'><div style='text-align: center;'><h1 style='margin:0; color:#00f0ff; font-size:2rem;'>{tk1}</h1></div><h2 style='color: #ff4b4b; font-family: Orbitron;'>VS</h2><div style='text-align: center;'><h1 style='margin:0; color:#78ff00; font-size:2rem;'>{tk2}</h1></div></div>", unsafe_allow_html=True)
                
                st.info("💡 **Cara Memilih Pemenang:** Pilih saham yang angka **PE dan PBV-nya LEBIH KECIL** (berarti harganya lebih murah), tetapi memiliki persentase **ROE LEBIH BESAR** (berarti lebih jago mencetak untung).")
                
                df_compare = pd.DataFrame({
                    "METRIK": ["Harga Saat Ini", "Valuasi (PE Ratio)", "Valuasi (PBV Ratio)", "Profitabilitas (ROE)", "Rasio Utang (DER)", "Bunga Dividen (Yield)"],
                    tk1: [f"Rp {get_val(i1, 'currentPrice'):,.0f}", f"{get_val(i1, 'trailingPE'):,.2f}x", f"{get_val(i1, 'priceToBook'):,.2f}x", f"{get_val(i1, 'returnOnEquity')*100:.2f}%", f"{get_val(i1, 'debtToEquity'):,.2f}%", f"{get_val(i1, 'dividendYield')*100:.2f}%"],
                    tk2: [f"Rp {get_val(i2, 'currentPrice'):,.0f}", f"{get_val(i2, 'trailingPE'):,.2f}x", f"{get_val(i2, 'priceToBook'):,.2f}x", f"{get_val(i2, 'returnOnEquity')*100:.2f}%", f"{get_val(i2, 'debtToEquity'):,.2f}%", f"{get_val(i2, 'dividendYield')*100:.2f}%"]
                })
                st.table(df_compare.set_index("METRIK"))
            except Exception as e: st.error("Gagal menarik data.")

elif menu == "SECTOR HEATMAP":
    st.title("🌐 PETA PERGERAKAN SEKTOR")
    with st.expander("📖 PANDUAN & WAKTU EKSEKUSI", expanded=False):
        st.markdown("""
        **🕒 WAKTU TERBAIK PENGGUNAAN:**
        * **15:30 WIB:** Melihat ke arah mana uang triliunan rupiah berotasi untuk persiapan trading esok hari.
        """)
    
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
                    if sec_changes:
                        sector_data.append({"Sektor": sec_name, "Perubahan (%)": round(sum(sec_changes) / len(sec_changes), 2)})
            except: pass
            
            if sector_data:
                st.info("💡 **Kesimpulan:** Perhatikan balok warna hijau yang menjorok ke kanan. Sektor tersebut sedang menjadi primadona (banyak dana masuk). Jika ingin trading harian, carilah saham di sektor tersebut.")
                
                df_sec = pd.DataFrame(sector_data).sort_values(by="Perubahan (%)", ascending=False)
                fig_sec = px.bar(df_sec, x="Sektor", y="Perubahan (%)", color="Perubahan (%)", color_continuous_scale=["#ff4b4b", "#1e293b", "#78ff00"])
                fig_sec.update_layout(template="plotly_dark", height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_sec, use_container_width=True)

elif menu == "RISK CALCULATOR":
    st.title("🧮 KALKULATOR RISIKO (POSITION SIZING)")
    with st.expander("📖 PANDUAN & WAKTU EKSEKUSI", expanded=False):
        st.markdown("""
        **🕒 WAKTU TERBAIK PENGGUNAAN:**
        * **WAJIB** digunakan sebelum kamu menekan tombol *Buy* (Beli) di aplikasi Sekuritasmu.
        """)
    
    with st.form("risk_calc_form"):
        c1, c2 = st.columns(2)
        capital = c1.number_input("Berapa Total Uang Modalmu? (Rp)", min_value=100000, value=10000000, step=500000)
        risk_pct = c2.number_input("Rela Rugi Maksimal Berapa % per Transaksi?", min_value=0.1, max_value=10.0, value=2.0, step=0.1)
        
        c3, c4, c5 = st.columns(3)
        entry_p = c3.number_input("Harga Beli Saham (Rp)", min_value=1, value=5000)
        stop_loss_p = c4.number_input("Harga Buang Rugi / Cut Loss (Rp)", min_value=1, value=4800)
        target_p = c5.number_input("Harga Target Untung (Rp)", min_value=1, value=5500)
        
        calc_btn = st.form_submit_button("HITUNG ALOKASI AMAN SEKARANG", width="stretch")
        
    if calc_btn:
        if stop_loss_p >= entry_p:
            st.error("⚠️ Harga Stop Loss (Jual Rugi) harus lebih rendah dari Harga Beli!")
        else:
            max_risk_idr = capital * (risk_pct / 100)
            risk_per_share = entry_p - stop_loss_p
            total_lots = math.floor((max_risk_idr / risk_per_share) / 100)
            actual_shares = total_lots * 100
            
            st.markdown("---")
            m1, m2, m3 = st.columns(3)
            m1.metric("BELI MAKSIMAL", f"{total_lots:,} Lot")
            m2.metric("MODAL TERPAKAI", f"Rp {actual_shares * entry_p:,.0f}")
            m3.metric("UANG YG HILANG JIKA CUT LOSS", f"Rp {actual_shares * risk_per_share:,.0f}", delta_color="inverse")
            
            st.info(f"💡 **Kesimpulan Beli:** Berdasarkan rumus keamanan profesional, untuk membeli saham ini kamu **HANYA BOLEH BELI MAKSIMAL {total_lots:,} LOT**. Jangan serakah beli full pakai semua modalmu! Jika harganya turun menyentuh Rp {stop_loss_p}, segera jual paksa (Cut Loss). Kamu hanya akan kehilangan Rp {actual_shares * risk_per_share:,.0f}, sisa modalmu masih sangat aman untuk transaksi berikutnya.")

elif menu == "DIVIDEND TRACKER":
    st.title("💰 PEMBURU DIVIDEN")
    with st.expander("📖 PANDUAN & WAKTU EKSEKUSI", expanded=False):
        st.markdown("""
        **🕒 WAKTU TERBAIK PENGGUNAAN:**
        * Kapan saja untuk mencari saham tabungan pemberi *passive income*.
        """)
    
    div_tk = st.text_input("Ketik Kode Saham", value="ITMG").upper().strip()
    full_div_tk = f"{div_tk}.JK" if not div_tk.endswith(".JK") else div_tk
    
    if st.button("CEK BAGAIMANA DIVIDENNYA", width="stretch"):
        with st.spinner("Menggali riwayat dividen..."):
            try:
                t_obj = yf.Ticker(full_div_tk)
                divs = t_obj.dividends
                div_yield = (t_obj.info.get('dividendYield', 0) or 0) * 100
                
                st.markdown(f"### 🏢 {t_obj.info.get('longName', div_tk)}")
                st.metric("BUNGA KEUNTUNGAN (YIELD) TAHUNAN", f"{div_yield:.2f}%")
                
                if div_yield > 5:
                    st.success(f"💡 **Kesimpulan:** Saham ini **SANGAT MENARIK** untuk ditabung! Bunga deposito bank saat ini hanya 4-5% per tahun. Saham ini memberikan bunga dividen sebesar {div_yield:.2f}%, jauh lebih menguntungkan dari naruh uang di bank.")
                elif div_yield > 0:
                    st.warning(f"💡 **Kesimpulan:** Bunga dividen saham ini hanya {div_yield:.2f}%. Ini setara atau **LEBIH KECIL** dari bunga deposito bank. Kurang menarik jika kamu hanya mengincar dividennya saja.")
                else:
                    st.error("💡 **Kesimpulan:** Saham ini **TIDAK PERNAH BAGA-BAGI DIVIDEN** atau datanya belum tercatat. Tidak cocok untuk investasi pasif.")
                
                if not divs.empty:
                    df_divs = pd.DataFrame(divs).reset_index()
                    df_divs.columns = ['Tanggal Cair', 'Nominal Diterima (Rp per lembar)']
                    df_divs['Tanggal Cair'] = pd.to_datetime(df_divs['Tanggal Cair']).dt.strftime('%Y-%m-%d')
                    st.dataframe(df_divs.sort_values(by='Tanggal Cair', ascending=False).head(10), use_container_width=True, hide_index=True)
            except Exception as e: st.error("Gagal memuat riwayat dividen.")

elif menu == "CORRELATION MATRIX":
    st.title("🧬 CEK KORELASI (DIVERSIFIKASI)")
    with st.expander("📖 PANDUAN & WAKTU EKSEKUSI", expanded=False):
        st.markdown("""
        **🕒 WAKTU TERBAIK PENGGUNAAN:**
        * Saat ingin mengatur ulang porsi isi keranjang saham (Akhir Pekan/Bulan).
        """)
    
    input_tkrs = st.text_input("MASUKKAN KODE SAHAM (PISAHKAN KOMA)", value="BBCA, BBRI, AMRT, TLKM")
    if st.button("CEK HUBUNGAN SAHAM", width="stretch"):
        with st.spinner("Memproses hubungan matematika..."):
            try:
                raw_list = [t.strip().upper() + ".JK" for t in input_tkrs.split(",")]
                data_corr = yf.download(raw_list, period="6mo", interval="1d", progress=False)['Close']
                if not data_corr.empty:
                    if isinstance(data_corr.columns, pd.MultiIndex): data_corr.columns = data_corr.columns.get_level_values(0)
                    data_corr.columns = [c.replace(".JK", "") for c in data_corr.columns]
                    
                    st.info("💡 **Cara Baca Kotak Warna-warni:** Cari pertemuan warna yang **Biru Gelap (-1)**, saham-saham tersebut sangat cocok disatukan karena gerakannya saling melengkapi (satu merah, satu hijau menolong). **HINDARI** mengoleksi terlalu banyak saham yang kotaknya **Merah Gelap (+1)** karena gerakannya kembar, kalau IHSG hancur portofoliomu akan ikut hancur lebur.")
                    
                    fig_corr = px.imshow(data_corr.corr(), text_auto=True, color_continuous_scale="RdBu_r", zmin=-1, zmax=1)
                    fig_corr.update_layout(template="plotly_dark", height=400, margin=dict(l=0,r=0,t=20,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_corr, use_container_width=True)
            except: st.error("Gagal mengunduh data korelasi.")

elif menu == "FOREIGN & BROKER FLOW":
    st.title("🏛️ JEJAK BANDAR & ASING (MONEY FLOW)")
    with st.expander("📖 PANDUAN & WAKTU EKSEKUSI", expanded=False):
        st.markdown("""
        **🕒 WAKTU TERBAIK PENGGUNAAN:**
        * **Setelah 16:15 WIB:** Di sinilah rekap aktivitas uang bandar harian sudah terekam sempurna.
        """)
    
    ff_tk = st.text_input("Ketik Kode Saham", value="BBRI").upper().strip()
    
    if st.button("LACAK UANG BANDAR SEKARANG", width="stretch"):
        with st.spinner("Melacak aktivitas paus (bandar)..."):
            try:
                df_ff = yf.download(f"{ff_tk}.JK" if not ff_tk.endswith(".JK") else ff_tk, period="3mo", interval="1d", progress=False)
                if not df_ff.empty:
                    if isinstance(df_ff.columns, pd.MultiIndex): df_ff.columns = df_ff.columns.get_level_values(0)
                    
                    df_ff['Multiplier'] = ((df_ff['Close'] - df_ff['Low']) - (df_ff['High'] - df_ff['Close'])) / (df_ff['High'] - df_ff['Low'] + 1e-9)
                    df_ff['CMF_20'] = (df_ff['Multiplier'] * df_ff['Volume']).rolling(20).sum() / df_ff['Volume'].rolling(20).sum()
                    df_ff['CMF_20'] = df_ff['CMF_20'].fillna(0) 
                    latest_cmf = df_ff['CMF_20'].iloc[-1]
                    
                    if latest_cmf > 0.05:
                        status_flow = "AKUMULASI BESAR (BANDAR MEMBORONG BARANG) 🚀"
                        color_flow = "#78ff00"
                        kesimpulan = "💡 **Kesimpulan:** Dana-dana besar (Institusi/Bandar) terlihat sedang **aktif memborong dan menimbun** saham ini secara masif dalam 20 hari terakhir. Ini adalah sinyal bahwa harga bersiap diterbangkan."
                    elif latest_cmf < -0.05:
                        status_flow = "DISTRIBUSI BESAR (BANDAR BUANG BARANG) ⚠️"
                        color_flow = "#ff4b4b"
                        kesimpulan = "💡 **Kesimpulan:** AWAS! Dana besar (Institusi/Bandar) sedang **mencuci gudang dan membuang** saham ini ke pasar ritel. Harga rawan dibanting turun dalam waktu dekat."
                    else:
                        status_flow = "NETRAL / SIDEWAYS (BANDAR TIDUR) 💤"
                        color_flow = "#00f0ff"
                        kesimpulan = "💡 **Kesimpulan:** Tidak ada pergerakan arus uang yang signifikan. Bandar sedang tidak aktif memborong maupun jualan (atau sahamnya tidak ada transaksi/suspend). Harga akan cenderung bergerak mendatar."
                    
                    st.markdown(f"<div style='text-align:center; padding:20px; background:rgba(13, 18, 30, 0.9); border: 1px solid {color_flow}; border-radius:16px;'><h3 style='color:#fff; margin:0;'>Status Bandar: <span style='color:{color_flow};'>{status_flow}</span></h3></div>", unsafe_allow_html=True)
                    st.metric("Skor Chaikin Money Flow (CMF)", f"{latest_cmf:.3f}")
                    st.info(kesimpulan)
                    
                    fig_mf = px.area(df_ff.reset_index(), x='Date', y='CMF_20')
                    fig_mf.add_hline(y=0, line_dash="dash", line_color="gray")
                    fig_mf.update_layout(template="plotly_dark", height=300, margin=dict(l=0,r=0,t=10,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_mf, use_container_width=True)
            except: st.error("Data saham tidak ditemukan.")


# =========================================================================
# 🔥 FITUR BARU: MARKET NEWS (FINANCIAL INTELLIGENCE CENTER)
# =========================================================================
elif menu == "MARKET_NEWS":
    st.title("📰 FINANCIAL INTELLIGENCE CENTER")
    
    st.markdown("### 🌍 Global Macro & Commodity Radar")
    st.write("Pergerakan harga dunia yang mempengaruhi IHSG hari ini:")
    
    with st.spinner("Menarik data pasar global..."):
        try:
            # Mengambil Ticker Global: Dow Jones, Nasdaq, Minyak Mentah (WTI), Emas
            macro_tickers = {"Dow Jones": "^DJI", "Nasdaq": "^IXIC", "Minyak (WTI)": "CL=F", "Emas (Gold)": "GC=F"}
            macro_data = yf.download(list(macro_tickers.values()), period="5d", interval="1d", progress=False)
            
            mc1, mc2, mc3, mc4 = st.columns(4)
            columns = [mc1, mc2, mc3, mc4]
            
            for i, (name, symbol) in enumerate(macro_tickers.items()):
                try:
                    close_data = macro_data['Close'][symbol]
                    if len(close_data) >= 2:
                        last_price = close_data.iloc[-1]
                        prev_price = close_data.iloc[-2]
                        pct_change = ((last_price - prev_price) / prev_price) * 100
                        
                        columns[i].metric(label=name, value=f"{last_price:,.2f}", delta=f"{pct_change:.2f}%")
                except:
                    columns[i].metric(label=name, value="N/A", delta="0.00%")
        except Exception as e:
            st.warning("Data Global Macro sedang tidak dapat diakses saat ini.")

    st.markdown("---")
    
    with st.expander("📖 CARA MEMBACA SENTIMEN BERITA", expanded=False):
        st.markdown("""
        **Sistem AI sederhana akan memberikan warna pada berita:**
        * 🟢 **POSITIF:** Berita baik (laba naik, investasi, dll). Bagus untuk harga saham.
        * 🔴 **NEGATIF:** Berita buruk (rugi, kasus, anjlok). Hati-hati harga saham turun.
        * ⚪ **NETRAL:** Berita umum.
        * 🔥 **NEW (HOT):** Berita sangat baru yang rilis dalam 12 jam terakhir!
        """)
        
    t_gen, t_spec = st.tabs(["🌐 BERITA PASAR UMUM", "🔍 CARI BERITA SAHAM SPESIFIK"])
    
    # Fungsi Pembaca Sentimen Otomatis
    def analyze_sentiment(text):
        text = text.lower()
        pos_words = ['naik', 'laba', 'untung', 'lonjak', 'akuisisi', 'investasi', 'meroket', 'rekor', 'cuan', 'diborong', 'tumbuh', 'bullish', 'dividen', 'melonjak']
        neg_words = ['turun', 'rugi', 'anjlok', 'suspend', 'kasus', 'skandal', 'gagal', 'merosot', 'jeblok', 'dilepas', 'bearish', 'koreksi', 'inflasi', 'resesi']
        
        score = 0
        for w in pos_words:
            if w in text: score += 1
        for w in neg_words:
            if w in text: score -= 1
            
        if score > 0: return "🟢 SENTIMEN: POSITIF", "#78ff00"
        elif score < 0: return "🔴 SENTIMEN: NEGATIF", "#ff4b4b"
        else: return "⚪ SENTIMEN: NETRAL", "#94a3b8"

    # Fungsi Deteksi Waktu Berita Baru
    def check_if_new(published_parsed):
        if published_parsed:
            entry_time = mktime(published_parsed)
            current_time = time.time()
            if (current_time - entry_time) < (12 * 3600): # Kurang dari 12 jam
                return "🔥 NEW (HOT)"
        return ""

    with t_gen:
        with st.spinner("Menarik tajuk berita dari media..."):
            try:
                feed = feedparser.parse("https://news.google.com/rss/search?q=saham+indonesia+ihsg&hl=id&gl=ID&ceid=ID:id")
                for entry in feed.entries[:10]: 
                    sent_text, sent_color = analyze_sentiment(entry.title)
                    fire_badge = check_if_new(entry.published_parsed if hasattr(entry, 'published_parsed') else None)
                    
                    st.markdown(f"""
                    <div style='background:rgba(13, 18, 30, 0.8); border:1px solid rgba(0, 240, 255, 0.2); padding:16px; border-radius:12px; margin-bottom:12px;'>
                        <div style='display:flex; justify-content:space-between; margin-bottom:8px;'>
                            <span style='font-size:11px; font-weight:bold; color:{sent_color};'>{sent_text}</span>
                            <span style='font-size:11px; color:#ff4b4b; font-weight:bold; animation: blink 1s linear infinite;'>{fire_badge}</span>
                        </div>
                        <a href='{entry.link}' target='_blank' style='color:#00f0ff; text-decoration:none; font-size:1.05rem; font-weight:bold; font-family:Plus Jakarta Sans;'>{entry.title}</a>
                        <p style='color:#94a3b8; font-size:0.8rem; margin-top:8px; margin-bottom:0;'>⏰ {entry.published}</p>
                    </div>
                    """, unsafe_allow_html=True)
            except Exception as e: st.error("Koneksi feed berita terputus.")
            
    with t_spec:
        with st.form("f_news"):
            search_t = st.text_input("Ketik Kode Saham (Contoh: BBCA)").upper().strip()
            btn_news = st.form_submit_button("CARI BERITA", width="stretch")
            
        if btn_news and search_t:
            with st.spinner(f"Mencari sentimen berita untuk {search_t}..."):
                try:
                    feed_spec = feedparser.parse(f"https://news.google.com/rss/search?q={search_t}+saham&hl=id&gl=ID&ceid=ID:id")
                    if not feed_spec.entries: 
                        st.warning("Berita tidak ditemukan.")
                    else:
                        for entry in feed_spec.entries[:8]: 
                            sent_text, sent_color = analyze_sentiment(entry.title)
                            fire_badge = check_if_new(entry.published_parsed if hasattr(entry, 'published_parsed') else None)
                            
                            st.markdown(f"""
                            <div style='background:rgba(13, 18, 30, 0.8); border:1px solid rgba(0, 240, 255, 0.2); padding:16px; border-radius:12px; margin-bottom:12px;'>
                                <div style='display:flex; justify-content:space-between; margin-bottom:8px;'>
                                    <span style='font-size:11px; font-weight:bold; color:{sent_color};'>{sent_text}</span>
                                    <span style='font-size:11px; color:#ff4b4b; font-weight:bold;'>{fire_badge}</span>
                                </div>
                                <a href='{entry.link}' target='_blank' style='color:#00f0ff; text-decoration:none; font-size:1.05rem; font-weight:bold; font-family:Plus Jakarta Sans;'>{entry.title}</a>
                                <p style='color:#94a3b8; font-size:0.8rem; margin-top:8px; margin-bottom:0;'>⏰ {entry.published}</p>
                            </div>
                            """, unsafe_allow_html=True)
                except: st.error("Pencarian berita gagal.")

elif menu == "MONEY MANAGEMENT":
    st.title("💼 BUKU DOMPET TRADING")
    with st.expander("📖 PANDUAN & WAKTU EKSEKUSI", expanded=False):
        st.markdown("""
        **🕒 WAKTU TERBAIK PENGGUNAAN:**
        * Sesegera mungkin setelah kamu melakukan transaksi Beli/Jual di aplikasi sekuritas aslimu, agar portofolio di sini selalu sama persis saldonya.
        """)
        
    privacy_mode = st.checkbox("🕶️ Sembunyikan Saldo", value=False)
    format_privacy = lambda v, c=True: ("Rp *****" if c else "*****") if privacy_mode else (f"Rp {v:,.0f}" if c else f"{v:,.0f}")

    tab1, tab2, tab3 = st.tabs(["📈 DAFTAR SAHAM DIMILIKI", "📜 RIWAYAT KEUNTUNGAN (HISTORY)", "📊 STATISTIK PRIBADI"])
    
    with tab1:
        with st.expander("➕ CATAT PEMBELIAN BARU", expanded=False):
            with st.form("form_add_portfolio", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                t_in, p_in, l_in = c1.text_input("Kode Saham"), c2.number_input("Harga Beli", min_value=0), c3.number_input("Berapa Lot?", min_value=1)
                if st.form_submit_button("SIMPAN KE DOMPET"):
                    if t_in and p_in > 0: add_to_portfolio(user_now, t_in, p_in, l_in, 0, 0); st.success("Berhasil dicatat!"); st.rerun()

        df_p = get_user_portfolio(user_now, role)
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
            
            m1, m2, m3 = st.columns(3)
            t_inv, t_pl = df_p['Cost'].sum(), df_p['P/L'].sum()
            m1.metric("TOTAL UANG BELI (MODAL)", format_privacy(t_inv))
            m2.metric("UNTUNG/RUGI BERJALAN", format_privacy(t_pl), f"{(t_pl/t_inv*100 if t_inv!=0 else 0):.2f}%")
            m3.metric("NILAI UANG SEKARANG (EQUITY)", format_privacy(t_inv + t_pl))

            st.markdown("---")
            for i, row in df_p.iterrows():
                with st.expander(f"📦 {row['ticker']} | {int(row['lots'])} Lots | {('+' if row['P/L']>0 else '')}{row['P/L']:,.0f} Rp"):
                    c_price, c_lots, c_btn = st.columns([2, 2, 1])
                    s_price = c_price.number_input("Harga Jual Laku (Rp)", value=float(row['Live']), key=f"s_prc_{row['id']}")
                    s_lots = c_lots.number_input("Berapa Lot yang Terjual?", min_value=1, max_value=int(row['lots']), value=int(row['lots']), key=f"s_lot_{row['id']}")
                    st.write("")
                    if c_btn.button("CATAT JUAL", key=f"btn_s_{row['id']}", use_container_width=True):
                        st.toast(sell_position(user_now, row['id'], row['ticker'], row['buy_price'], s_price, row['lots'], s_lots)); time.sleep(1); st.rerun()
        else: st.info("Kamu belum mencatat kepemilikan saham apa pun.")

    with tab2:
        df_h = conn_gs.read(worksheet="history", ttl=0)
        if not df_h.empty:
            df_h['pnl'] = pd.to_numeric(df_h['pnl'], errors='coerce')
            if role != 'admin': df_h = df_h[df_h['username'] == user_now]
            for idx, h_row in df_h.sort_values(by='date', ascending=False).iterrows():
                with st.expander(f"{h_row['date']} | {h_row['ticker']} | {format_privacy(h_row['pnl'])}"):
                    c_t, c_b = st.columns([4,1])
                    c_t.write(f"Harga Beli: Rp {h_row['buy_price']} | Harga Jual: Rp {h_row['sell_price']} | Terjual: {h_row['lots']} Lot")
                    if c_b.button("🗑️ Hapus Catatan", key=f"del_h_{h_row['id']}"):
                        df_h_all = conn_gs.read(worksheet="history", ttl=0)
                        idx_del_h = df_h_all.index[df_h_all['id'] == h_row['id']].tolist()
                        if idx_del_h: conn_gs.update(worksheet="history", data=df_h_all.drop(idx_del_h[0]).reset_index(drop=True)); st.rerun()
        else: st.info("Belum ada riwayat penjualan saham.")

    with tab3: 
        if 'df_h' in locals() and not df_h.empty:
            total_trades = len(df_h)
            win_trades = len(df_h[df_h['pnl'] > 0])
            loss_trades = len(df_h[df_h['pnl'] < 0])
            win_rate = (win_trades / total_trades) * 100 if total_trades > 0 else 0
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("WIN RATE (AKURASI)", f"{win_rate:.1f}%")
            c2.metric("TOTAL JUAL", f"{total_trades}x")
            c3.metric("RATA-RATA CUAN", format_privacy(df_h[df_h['pnl'] > 0]['pnl'].mean() if win_trades > 0 else 0))
            c4.metric("RATA-RATA RUGI", format_privacy(df_h[df_h['pnl'] < 0]['pnl'].mean() if loss_trades > 0 else 0), delta_color="inverse")
            
            st.markdown("---")
            df_curve = df_h.sort_values('date')
            df_curve['cum_pnl'] = df_curve['pnl'].cumsum()
            fig_curve = go.Figure(go.Scatter(x=df_curve['date'], y=df_curve['cum_pnl'], mode='lines', fill='tozeroy', line=dict(color='#00f0ff')))
            fig_curve.update_layout(title="Grafik Pertumbuhan Uang Kamu", template="plotly_dark", height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_curve, use_container_width=True)

elif menu == "SECURITY SETTINGS":
    st.title("🔒 GANTI PASSWORD")
    with st.form("p"):
        new_p = st.text_input("Ketik Password Barumu di sini", type="password")
        if st.form_submit_button("SIMPAN PASSWORD", width="stretch"):
            if update_password_db(user_now, new_p): st.success("Password berhasil diubah!")

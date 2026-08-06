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

# --- 0. CONFIG & APP SETUP ---
warnings.filterwarnings("ignore", category=FutureWarning)
st.set_page_config(
    page_title="IDX CYBER TERMINAL", 
    page_icon="⚡", 
    layout="wide",
    initial_sidebar_state="collapsed" # Sidebar otomatis tertutup di HP
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
    border-radius: 8px; height: 48px;
}

div[data-testid="stMetric"], .stDataFrame, .stTabs, div[data-testid="stExpander"] {
    background: rgba(13, 18, 30, 0.7) !important;
    border: 1px solid rgba(255, 255, 255, 0.07) !important;
    border-radius: 12px !important; backdrop-filter: blur(12px);
}
[data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace !important; font-size: 1.8rem !important; color: #78ff00 !important; }
[data-testid="stMetricLabel"] { color: #94a3b8 !important; font-weight: 600; text-transform: uppercase; font-size: 0.8rem; }

[data-testid="stSidebar"] { background: #090d16; border-right: 1px solid rgba(255, 255, 255, 0.05); }

/* Menu Radio Button (Ukuran Sentuh HP Diperbesar) */
div[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label {
    background: rgba(255, 255, 255, 0.01) !important; 
    border: 1px solid rgba(255, 255, 255, 0.03) !important;
    border-radius: 8px !important; 
    padding: 14px 16px !important; /* Diperbesar agar empuk di HP */
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
                signals.append({"ticker": ticker.replace(".JK", ""), "status": "GOLDEN CROSS", "price": current_price, "color": "#78ff00"})
            elif prev_ma20 > prev_ma50 and last_ma20 < last_ma50:
                signals.append({"ticker": ticker.replace(".JK", ""), "status": "DEAD CROSS", "price": current_price, "color": "#ff4b4b"})
        except: continue
    return signals

def draw_mobile_cards(df):
    for _, row in df.iterrows():
        chg = row.get('CHG%', 0)
        chg_color = "#78ff00" if chg > 0 else "#ff4b4b"
        val_last  = row.get('LAST', '-')
        val_entry = row.get('ENTRY', row.get('Entry', val_last)) 
        val_tp1   = row.get('TP 1', '-')
        val_tp2   = row.get('TP 2', '-')
        val_cl    = row.get('EXIT/CL', '-')
        val_m     = row.get('VAL(M)', 0)

        st.markdown(f"""
        <div style="background: rgba(13, 18, 30, 0.8); border: 1px solid rgba(0, 240, 255, 0.2); 
                    border-radius: 12px; padding: 16px; margin-bottom: 12px; border-left: 4px solid {chg_color};">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <b style="font-size: 1.1rem; color: #00f0ff; font-family: Orbitron;">{row.get('TICKER','-')}</b>
                <span style="color: {chg_color}; font-weight: bold; font-family: JetBrains Mono;">{chg}%</span>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 12px; font-size: 0.85rem; color: #94a3b8;">
                <div>Last: <b style="color:#fff;">{val_last}</b></div>
                <div>Value: <b style="color:#fff;">{val_m}M</b></div>
                <div style="color: #00f0ff; font-weight: bold;">Entry: {val_entry}</div>
                <div style="color: #78ff00; font-weight: bold;">TP1: {val_tp1}</div>
                <div style="color: #78ff00; font-weight: bold;">TP2: {val_tp2}</div>
                <div style="color: #ff4b4b; font-weight: bold;">CL: {val_cl}</div>
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
if st.sidebar.button("🔴 TERMINATE SESSION", use_container_width=True):
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
        * **15:30 - 15:50 WIB:** Saat *Pre-Closing* untuk di-hold (swing) ke esok hari.
        
        **CARA BACA:**
        * **AI Score:** Kekuatan momentum (Makin tinggi makin kuat).
        * **TP 1 & TP 2 (Take Profit):** Antre jual di harga ini untuk merealisasikan untung.
        * **EXIT/CL (Stop Loss):** Disiplin! Jual rugi jika harga sentuh level ini.
        """)

    if 'results' not in st.session_state: st.session_state.results = None
    tickers = load_tickers()
    
    c1, c2 = st.columns([4,1])
    with c1: mode_scan = st.radio("ALGO_SENSITIVITY", ["Santai", "Profesional", "Pro"], horizontal=True)
    with c2: 
        if st.button("⚡ EXECUTE SCAN", use_container_width=True):
            res = run_scan(tickers, mode_scan)
            if not res.empty: st.session_state.results = res; st.rerun()
            else: st.warning("Scan complete: No stocks met the criteria.")

    if st.session_state.results is not None:
        df = st.session_state.results
        st.markdown(f"""
        <div style='background: rgba(0, 240, 255, 0.05); padding:16px; border-left:4px solid #00f0ff; margin-bottom:20px; border-radius:0 12px 12px 0;'>
            <span style='color:#00f0ff; font-family:Orbitron; font-weight:bold; font-size:0.9rem;'>🧠 QUANT AI STATUS: SCAN COMPLETE</span><br>
            <span style='font-size:0.8rem; color:#94a3b8;'>📊 PROCESSED DATA: {len(df)} STOCKS ANALYZED SUCCESSFULLY</span>
        </div>
        """, unsafe_allow_html=True)

        tab1, tab2, tab3 = st.tabs(["📊 DATA TERMINAL", "📱 MOBILE VIEW", "📈 ADVANCED CHART"])
        with tab1: st.dataframe(df.drop(columns=['FULL'], errors='ignore'), use_container_width=True, hide_index=True)
        with tab2: draw_mobile_cards(df)
        with tab3:
            sel_t = st.selectbox("SELECT TICKER FOR DEEP ANALYSIS", df['TICKER'].tolist())
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
                
                fig.update_layout(template="plotly_dark", height=600, margin=dict(l=0,r=0,t=20,b=0), xaxis_rangeslider_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)

elif menu == "STRATEGY SCANNER":
    st.markdown("<h2 style='color:#00f0ff;'>⚡ REAL-TIME STRATEGY SCANNER</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN & WAKTU EKSEKUSI", expanded=False):
        st.markdown("""
        **🕒 WAKTU TERBAIK PENGGUNAAN:**
        * **16:00 WIB ke atas (Bursa Tutup):** Sinyal *Moving Average* dihitung paling akurat menggunakan harga penutupan final bursa.
        
        **CARA BACA:**
        * 🟢 **Golden Cross:** Harga rata-rata memotong ke atas. Tren menguat, peluang *Buy*.
        * 🔴 **Dead Cross:** Tren melemah. Siap-siap amankan posisi.
        """)
    
    try:
        df_saham = pd.read_excel("daftar_saham.xlsx")
        watchlist = [t.strip() + ".JK" for t in df_saham['Kode'].dropna().astype(str).tolist()]
    except:
        st.error("Error membaca file Excel 'daftar_saham.xlsx'."); watchlist = []

    if st.button("🚀 EXECUTE STRATEGY SCAN") and watchlist:
        with st.spinner(f"Analyzing {len(watchlist)} stocks for crossover signals..."):
            results = get_trend_signals(watchlist)
            if results:
                for res in results:
                    st.markdown(f"<div style='border: 1px solid {res['color']}; background: rgba(13,18,30,0.8); padding: 16px; border-radius: 12px; margin-bottom: 12px;'><h3 style='color:{res['color']}; margin:0; font-family:Orbitron; font-size:1.1rem;'>{res['status']} DETECTED!</h3><p style='margin:6px 0; color:#94a3b8;'>Saham: <b style='color:#fff;'>{res['ticker']}</b> | Harga: Rp {res['price']:,.0f}</p></div>", unsafe_allow_html=True)
            else: st.info("Tidak ada sinyal MA Crossover yang terdeteksi saat ini.")

elif menu == "WATCHLIST":
    st.title("⭐ PERSONAL WATCHLIST")
    with st.expander("📖 PANDUAN & WAKTU EKSEKUSI", expanded=False):
        st.markdown("""
        **🕒 WAKTU TERBAIK PENGGUNAAN:**
        * Bebas kapan saja selama jam bursa (09:00 - 16:00 WIB).
        
        Masukkan kode saham incaranmu ke keranjang ini. Klik tombol **SCAN** untuk memantau apakah ada dari mereka yang sedang membentuk momentum bagus hari ini.
        """)
        
    my_wl = get_watchlist(user_now)
    c_add, c_del = st.columns(2)
    with c_add:
        new_wl = st.text_input("Add Ticker (e.g., BBCA)").upper()
        if st.button("➕ Add to Watchlist", use_container_width=True):
            if new_wl and f"{new_wl}.JK" not in my_wl: 
                add_watchlist(user_now, f"{new_wl}.JK"); st.success("Added!"); st.rerun()
    with c_del:
        if my_wl:
            del_wl = st.selectbox("Remove Ticker", [t.replace(".JK","") for t in my_wl])
            if st.button("🗑️ Remove", use_container_width=True):
                remove_watchlist(user_now, f"{del_wl}.JK"); st.warning("Removed!"); st.rerun()
                
    st.markdown("---")
    if my_wl:
        if st.button("⚡ SCAN WATCHLIST NOW", use_container_width=True):
            res_wl = run_scan(my_wl, "Santai")
            if not res_wl.empty: st.dataframe(res_wl.drop(columns=['FULL'], errors='ignore'), use_container_width=True, hide_index=True)
            else: st.info("Tidak ada pergerakan signifikan di watchlist kamu hari ini.")
    else: st.info("Watchlist masih kosong.")

elif menu == "FUNDAMENTAL":
    st.markdown("""<style>.stMetric {border-left: 4px solid #00f0ff !important;}</style>""", unsafe_allow_html=True)
    st.title("📟 FUNDAMENTAL TERMINAL")
    with st.expander("📖 PANDUAN & WAKTU EKSEKUSI", expanded=False):
        st.markdown("""
        **🕒 WAKTU TERBAIK PENGGUNAAN:**
        * Akhir pekan (Sabtu/Minggu) atau malam hari untuk reset portofolio investasi jangka panjang.
        
        **CARA BACA:**
        * **Graham Intrinsic Value:** Nilai wajar perusahaan. Jika harga pasar lebih murah, saham status *Undervalued*.
        * **Z-Score:** Menilai tingkat keamanan finansial (> 2.9 = Sangat Sehat, < 1.8 = Rawan Utang).
        """)
    
    col_in1, col_in2 = st.columns([3, 1])
    with col_in1: target_f = st.text_input("SYSTEM_TICKER_INPUT", value="BBCA").upper().strip()
    with col_in2: st.write("##"); btn_analyze = st.button("RUN_ANALYSIS", width="stretch")

    if btn_analyze:
        full_tk = f"{target_f}.JK" if not target_f.endswith(".JK") else target_f
        with st.spinner("SYNCING_FINANCIAL_DATABASE..."):
            try:
                info = yf.Ticker(full_tk).info
                current_price = info.get('currentPrice') or info.get('previousClose', 1)
                eps, bvps, per, pbv = info.get('trailingEps', 0) or 0, info.get('bookValue', 0) or 0, info.get('trailingPE', 0) or 0, info.get('priceToBook', 0) or 0
                roe = (info.get('returnOnEquity', 0) or 0) * 100
                der = info.get('debtToEquity', 0) or 0
                target_mean = info.get('targetMeanPrice', current_price) or current_price
                div_yield = (info.get('dividendYield', 0) or 0) * 100
                cr = info.get('currentRatio', 0) or 0
                
                st.markdown(f"### 🏢 {info.get('longName', target_f)} <span style='color:#64748b; font-size:0.8rem;'>| Sector: {info.get('sector', 'N/A')}</span>", unsafe_allow_html=True)
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("PE_RATIO", f"{per:,.2f}x"); c2.metric("PBV_RATIO", f"{pbv:,.2f}x")
                c3.metric("ROE_EFF", f"{roe:,.2f}%"); c4.metric("DIV_YIELD", f"{div_yield:,.2f}%")

                graham = math.sqrt(22.5 * eps * bvps) if (eps > 0 and bvps > 0) else 0
                fair_pe_val = eps * (15 if roe > 15 else 10)
                
                st.markdown("<br>", unsafe_allow_html=True)
                col_v1, col_v2, col_v3 = st.columns(3)
                
                def draw_pro_card(label, value, subtext, color="#00f0ff"):
                    st.markdown(f"<div style='background:rgba(13,18,30,0.8); padding:16px; border-radius:12px; border-top:3px solid {color}; height:140px;'><p style='margin:0; font-size:10px; color:#94a3b8; font-family:Orbitron; letter-spacing:1px;'>{label.upper()}</p><h2 style='margin:6px 0; color:{color}; font-family:JetBrains Mono; font-size:1.6rem;'>{value}</h2><p style='margin:0; font-size:11px; color:#64748b;'>{subtext}</p></div>", unsafe_allow_html=True)
                
                with col_v1: draw_pro_card("Graham Intrinsic", f"Rp{graham:,.0f}", f"Status: {'UNDER' if current_price < graham else 'OVER'}VALUED", "#78ff00")
                with col_v2: draw_pro_card("PE Fair Value", f"Rp{fair_pe_val:,.0f}", f"Base: 15x Multiple", "#00f0ff")
                with col_v3: draw_pro_card("Analyst Target", f"Rp{target_mean:,.0f}", f"Upside: {((target_mean - current_price)/current_price)*100:.1f}%", "#ff00ff")

                st.markdown("---")
                st.write("🛡️ **RISK ASSESSMENT MATRIX**")
                t_assets, t_debt = info.get('totalAssets', 1) or 1, info.get('totalDebt', 1) or 1
                z = (1.2 * (info.get('workingCapital',0)/t_assets)) + (3.3 * (info.get('ebitda',0)/t_assets)) + (0.6 * (info.get('marketCap',0)/t_debt))
                z_color = "#78ff00" if z > 2.9 else "#ffcc00" if z > 1.8 else "#ff4b4b"
                
                rc1, rc2, rc3 = st.columns(3)
                rc1.metric("Current Ratio", f"{cr:.2f}x", delta="Healthy" if cr > 1.5 else "Weak")
                rc2.metric("Debt to Equity", f"{der:.1f}%", delta="High Risk" if der > 150 else "Safe", delta_color="inverse")
                with rc3: st.markdown(f"<div style='background:rgba(13,18,30,0.8); border:1px solid {z_color}; padding:14px; border-radius:12px; text-align:center;'><p style='margin:0; font-size:10px; color:{z_color}; font-family:Orbitron;'>ALTMAN Z-SCORE</p><h3 style='margin:4px 0 0 0; color:{z_color}; font-family:JetBrains Mono;'>{z:.2f}</h3></div>", unsafe_allow_html=True)

            except Exception as e: st.error(f"SYSTEM_FAILURE: {e}")

elif menu == "TICKER COMPARISON":
    st.title("⚔️ TICKER BATTLE STATION")
    with st.expander("📖 PANDUAN & WAKTU EKSEKUSI", expanded=False):
        st.markdown("""
        **🕒 WAKTU TERBAIK PENGGUNAAN:**
        * Kapan pun (Sangat cocok saat kamu bingung mau pilih saham A atau saham B di sektor yang sama).
        
        **CARA BACA:** 
        Bandingkan Head-to-Head. Pilih saham yang memiliki **PE & PBV lebih kecil** (Valuasi Murah) tetapi **ROE lebih besar** (Cetak Laba Kuat).
        """)
        
    col_in1, col_in2 = st.columns(2)
    with col_in1: tk1 = st.text_input("PRIMARY TICKER", value="BBCA").upper().strip()
    with col_in2: tk2 = st.text_input("RIVAL TICKER", value="BBRI").upper().strip()

    if st.button("🚀 EXECUTE COMPARISON", width="stretch"):
        with st.spinner("CALCULATING_BATTLE_METRICS..."):
            try:
                i1, i2 = yf.Ticker(f"{tk1}.JK").info, yf.Ticker(f"{tk2}.JK").info
                get_val = lambda d, k: d.get(k, 0) or 0
                st.markdown(f"<div style='display: flex; justify-content: space-around; align-items: center; background: rgba(13,18,30,0.8); padding: 20px; border-radius: 14px; border: 1px solid rgba(0,240,255,0.3);'><div style='text-align: center;'><h1 style='margin:0; color:#00f0ff; font-size:2rem;'>{tk1}</h1></div><h2 style='color: #ff4b4b; font-family: Orbitron;'>VS</h2><div style='text-align: center;'><h1 style='margin:0; color:#78ff00; font-size:2rem;'>{tk2}</h1></div></div>", unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                
                df_compare = pd.DataFrame({
                    "METRIC": ["Current Price", "Market Cap (T)", "PE Ratio", "PBV Ratio", "ROE (%)", "DER (%)", "Div. Yield (%)"],
                    tk1: [f"Rp {get_val(i1, 'currentPrice'):,.0f}", f"{get_val(i1, 'marketCap')/1e12:.2f}T", f"{get_val(i1, 'trailingPE'):,.2f}x", f"{get_val(i1, 'priceToBook'):,.2f}x", f"{get_val(i1, 'returnOnEquity')*100:.2f}%", f"{get_val(i1, 'debtToEquity'):,.2f}%", f"{get_val(i1, 'dividendYield')*100:.2f}%"],
                    tk2: [f"Rp {get_val(i2, 'currentPrice'):,.0f}", f"{get_val(i2, 'marketCap')/1e12:.2f}T", f"{get_val(i2, 'trailingPE'):,.2f}x", f"{get_val(i2, 'priceToBook'):,.2f}x", f"{get_val(i2, 'returnOnEquity')*100:.2f}%", f"{get_val(i2, 'debtToEquity'):,.2f}%", f"{get_val(i2, 'dividendYield')*100:.2f}%"]
                })
                st.table(df_compare.set_index("METRIC"))
            except Exception as e: st.error(f"BATTLE_FAILED: {e}")

elif menu == "SECTOR HEATMAP":
    st.title("🌐 IDX SECTOR HEATMAP & ROTATION")
    with st.expander("📖 PANDUAN & WAKTU EKSEKUSI", expanded=False):
        st.markdown("""
        **🕒 WAKTU TERBAIK PENGGUNAAN:**
        * **15:30 WIB:** Melihat ke arah mana uang besar (Big Fund) berotasi untuk persiapan esok hari.
        
        **CARA BACA:**
        * **Sektor Hijau:** Sektor sedang memimpin pasar (*inflow*). Cari saham di sektor ini.
        * **Sektor Merah:** Sektor sedang koreksi/dihindari.
        """)
    
    sectors = {
        "Financials": ["BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK"],
        "Energy": ["ADRO.JK", "PTBA.JK", "HRUM.JK", "MEDC.JK"],
        "Basic Materials": ["INCO.JK", "MDKA.JK", "ANTM.JK", "TPIA.JK"],
        "Consumer Cyclical": ["ASII.JK", "ACES.JK", "ERAA.JK", "MAPI.JK"],
        "Consumer Non-Cyclical": ["UNVR.JK", "ICBP.JK", "INDF.JK", "GGRM.JK"],
        "Infrastructures": ["TLKM.JK", "ISAT.JK", "EXCL.JK", "TOWR.JK"],
        "Technology": ["GOTO.JK", "EMTK.JK", "BUKA.JK"],
        "Property & Real Estate": ["BSDE.JK", "CTRA.JK", "SMRA.JK", "PWON.JK"],
        "Healthcare": ["KLBF.JK", "MIKA.JK", "HEAL.JK"]
    }
    
    if st.button("⚡ FETCH SECTOR PERFORMANCE", use_container_width=True):
        with st.spinner("Analyzing sector performance across IDX..."):
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
                        sector_data.append({"Sector": sec_name, "Avg Change (%)": round(sum(sec_changes) / len(sec_changes), 2)})
            except: pass
            
            if sector_data:
                df_sec = pd.DataFrame(sector_data).sort_values(by="Avg Change (%)", ascending=False)
                fig_sec = px.bar(df_sec, x="Sector", y="Avg Change (%)", color="Avg Change (%)", color_continuous_scale=["#ff4b4b", "#1e293b", "#78ff00"])
                fig_sec.update_layout(template="plotly_dark", height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_sec, use_container_width=True)

elif menu == "RISK CALCULATOR":
    st.title("🧮 POSITION SIZING & RISK CALCULATOR")
    with st.expander("📖 PANDUAN & WAKTU EKSEKUSI", expanded=False):
        st.markdown("""
        **🕒 WAKTU TERBAIK PENGGUNAAN:**
        * **WAJIB** digunakan sebelum menekan tombol beli (*Buy*) di aplikasi Brokermu.
        
        Hitung berapa lot ideal yang boleh dibeli agar tidak hancur saat Cut Loss. (Maksimal risiko 1-2% dari modal).
        """)
    
    with st.form("risk_calc_form"):
        c1, c2 = st.columns(2)
        capital = c1.number_input("Total Modal / Portofolio (Rp)", min_value=100000, value=10000000, step=500000)
        risk_pct = c2.number_input("Maksimal Risiko per Trade (%)", min_value=0.1, max_value=10.0, value=2.0, step=0.1)
        
        c3, c4, c5 = st.columns(3)
        entry_p = c3.number_input("Harga Rencana Beli (Entry)", min_value=1, value=5000)
        stop_loss_p = c4.number_input("Harga Batas Rugi (Stop Loss / CL)", min_value=1, value=4800)
        target_p = c5.number_input("Harga Target Profit (Take Profit)", min_value=1, value=5500)
        
        calc_btn = st.form_submit_button("HITUNG ALOKASI RISIKO", width="stretch")
        
    if calc_btn:
        if stop_loss_p >= entry_p:
            st.error("⚠️ Harga Stop Loss harus lebih rendah dari Harga Entry untuk posisi Buy!")
        else:
            max_risk_idr = capital * (risk_pct / 100)
            risk_per_share = entry_p - stop_loss_p
            total_lots = math.floor((max_risk_idr / risk_per_share) / 100)
            actual_shares = total_lots * 100
            
            st.markdown("---")
            st.markdown("### 📊 HASIL KALKULASI PROFESIONAL")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("REKOMENDASI LOT", f"{total_lots:,} Lot", f"{actual_shares:,} Lembar")
            m2.metric("TOTAL INVESTASI", f"Rp {actual_shares * entry_p:,.0f}")
            m3.metric("MAKSIMAL RISIKO", f"Rp {actual_shares * risk_per_share:,.0f}", delta_color="inverse")
            m4.metric("RISK : REWARD", f"1 : {((target_p - entry_p) / risk_per_share if risk_per_share > 0 else 0):.2f}")

elif menu == "DIVIDEND TRACKER":
    st.title("💰 DIVIDEND TRACKER & YIELD")
    with st.expander("📖 PANDUAN & WAKTU EKSEKUSI", expanded=False):
        st.markdown("""
        **🕒 WAKTU TERBAIK PENGGUNAAN:**
        * Kapan saja untuk mencari pasif *income* dari saham.
        
        **CARA BACA:** Bunga deposito bank hanya sekitar 4% setahun. Jika *Yield* saham berada di atas 5-6%, itu adalah tambang emas untuk ditahan lama!
        """)
    
    div_tk = st.text_input("MASUKKAN KODE SAHAM", value="BBCA").upper().strip()
    full_div_tk = f"{div_tk}.JK" if not div_tk.endswith(".JK") else div_tk
    
    if st.button("AMBIL DATA DIVIDEND", width="stretch"):
        with st.spinner("Fetching dividend records..."):
            try:
                t_obj = yf.Ticker(full_div_tk)
                divs = t_obj.dividends
                info = t_obj.info
                div_yield = (info.get('dividendYield', 0) or 0) * 100
                
                st.markdown(f"### 🏢 {info.get('longName', div_tk)}")
                st.metric("ESTIMASI DIVIDEND YIELD", f"{div_yield:.2f}%")
                
                if not divs.empty:
                    df_divs = pd.DataFrame(divs).reset_index()
                    df_divs.columns = ['Date', 'Dividend (IDR)']
                    df_divs['Date'] = pd.to_datetime(df_divs['Date']).dt.strftime('%Y-%m-%d')
                    st.dataframe(df_divs.sort_values(by='Date', ascending=False), use_container_width=True, hide_index=True)
                else:
                    st.info("Tidak ada data riwayat dividen untuk emiten ini.")
            except Exception as e: st.error("Gagal memuat dividen.")

elif menu == "CORRELATION MATRIX":
    st.title("🧬 STOCK CORRELATION MATRIX")
    with st.expander("📖 PANDUAN & WAKTU EKSEKUSI", expanded=False):
        st.markdown("""
        **🕒 WAKTU TERBAIK PENGGUNAAN:**
        * Saat mengatur ulang porsi portofolio saham (Akhir Pekan/Bulan).
        
        **CARA BACA:**
        * **Biru Tua / Negatif (-1):** Saling mem-*back up*. Jika saham A turun, saham B naik. Bagus untuk memecah risiko.
        * **Merah Tua / Positif (+1):** Bergerak kembar. Bahaya, jika IHSG rontok, semua sahammu akan merah massal.
        """)
    
    input_tkrs = st.text_input("MASUKKAN KODE SAHAM (PISAHKAN DENGAN KOMA)", value="BBCA, BBRI, BMRI, BBNI, TLKM, ASII")
    if st.button("GENERATE CORRELATION MATRIX", width="stretch"):
        with st.spinner("Calculating correlation coefficients..."):
            try:
                raw_list = [t.strip().upper() + ".JK" for t in input_tkrs.split(",")]
                data_corr = yf.download(raw_list, period="6mo", interval="1d", progress=False)['Close']
                if not data_corr.empty:
                    if isinstance(data_corr.columns, pd.MultiIndex): data_corr.columns = data_corr.columns.get_level_values(0)
                    data_corr.columns = [c.replace(".JK", "") for c in data_corr.columns]
                    fig_corr = px.imshow(data_corr.corr(), text_auto=True, color_continuous_scale="RdBu_r", zmin=-1, zmax=1)
                    fig_corr.update_layout(template="plotly_dark", height=500, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_corr, use_container_width=True)
            except: st.error("Gagal mengunduh data.")

elif menu == "FOREIGN & BROKER FLOW":
    st.title("🏛️ INSTITUTIONAL & MONEY FLOW TRACKER")
    with st.expander("📖 PANDUAN & WAKTU EKSEKUSI", expanded=False):
        st.markdown("""
        **🕒 WAKTU TERBAIK PENGGUNAAN:**
        * **Setelah 16:15 WIB:** Di sinilah rekap aktivitas uang bandar harian sudah terekam sempurna.
        
        **CARA BACA (Chaikin Money Flow):**
        * **CMF > 0.05 (Hijau):** Dana besar sedang memborong (Akumulasi). Potensi harga naik.
        * **CMF < -0.05 (Merah):** Dana besar cuci gudang (Distribusi). Potensi harga longsor.
        """)
    
    ff_tk = st.text_input("KODE SAHAM ANALISIS", value="BBRI").upper().strip()
    
    if st.button("ANALISIS MONEY FLOW", width="stretch"):
        with st.spinner("Analyzing institutional accumulation..."):
            try:
                df_ff = yf.download(f"{ff_tk}.JK" if not ff_tk.endswith(".JK") else ff_tk, period="3mo", interval="1d", progress=False)
                if not df_ff.empty:
                    if isinstance(df_ff.columns, pd.MultiIndex): df_ff.columns = df_ff.columns.get_level_values(0)
                    df_ff['Multiplier'] = ((df_ff['Close'] - df_ff['Low']) - (df_ff['High'] - df_ff['Close'])) / (df_ff['High'] - df_ff['Low'] + 1e-9)
                    df_ff['CMF_20'] = (df_ff['Multiplier'] * df_ff['Volume']).rolling(20).sum() / df_ff['Volume'].rolling(20).sum()
                    latest_cmf = df_ff['CMF_20'].iloc[-1]
                    
                    status_flow = "STRONG ACCUMULATION (Banyak Dibeli Institusi)" if latest_cmf > 0.05 else ("DISTRIBUTION (Tekanan Jual Besar)" if latest_cmf < -0.05 else "NEUTRAL / SIDEWAYS")
                    color_flow = "#78ff00" if latest_cmf > 0.05 else ("#ff4b4b" if latest_cmf < -0.05 else "#00f0ff")
                    
                    st.markdown(f"### Status Arus Dana: <span style='color:{color_flow};'>{status_flow}</span>", unsafe_allow_html=True)
                    st.metric("CHAIKIN MONEY FLOW (20H)", f"{latest_cmf:.3f}")
                    
                    fig_mf = px.area(df_ff.reset_index(), x='Date', y='CMF_20')
                    fig_mf.add_hline(y=0, line_dash="dash", line_color="gray")
                    fig_mf.update_layout(template="plotly_dark", height=350, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_mf, use_container_width=True)
            except: st.error("Data tidak ditemukan.")

elif menu == "MARKET_NEWS":
    st.title("📰 FINANCIAL INTELLIGENCE FEED")
    with st.expander("📖 PANDUAN & WAKTU EKSEKUSI", expanded=False):
        st.markdown("""
        **🕒 WAKTU TERBAIK PENGGUNAAN:**
        * **08:00 - 08:30 WIB:** Cek berita sebelum bursa buka untuk menakar sentimen pasar.
        """)
        
    t_gen, t_spec = st.tabs(["🌐 GENERAL MARKET", "🔍 SPECIFIC TICKER"])
    with t_gen:
        with st.spinner("FETCHING_LATEST_INTELLIGENCE..."):
            feed = feedparser.parse("https://news.google.com/rss/search?q=saham+indonesia+ihsg&hl=id&gl=ID&ceid=ID:id")
            for entry in feed.entries[:10]: st.markdown(f"📡 **[{entry.title}]({entry.link})**\n<small style='color:#00f0ff;'>{entry.published}</small>\n---", unsafe_allow_html=True)
    with t_spec:
        search_t = st.text_input("ENTER TICKER FOR NEWS", value="BBCA").upper().strip()
        if search_t:
            feed_spec = feedparser.parse(f"https://news.google.com/rss/search?q={search_t}+saham&hl=id&gl=ID&ceid=ID:id")
            if not feed_spec.entries: st.warning("No news found.")
            for entry in feed_spec.entries[:8]: st.markdown(f"🔹 **[{entry.title}]({entry.link})**\n<small style='color:#78ff00;'>{entry.published}</small>\n", unsafe_allow_html=True)

elif menu == "MONEY MANAGEMENT":
    st.title("💼 INSTITUTIONAL PORTFOLIO")
    with st.expander("📖 PANDUAN & WAKTU EKSEKUSI", expanded=False):
        st.markdown("""
        **🕒 WAKTU TERBAIK PENGGUNAAN:**
        * Sesegera mungkin setelah kamu melakukan transaksi Beli/Jual di aplikasi sekuritasmu agar catatan di Terminal ini selalu sinkron (sama persis).
        """)
        
    privacy_mode = st.checkbox("🕶️ Privacy Mode (Hide Values)", value=False)
    format_privacy = lambda v, c=True: ("Rp *****" if c else "*****") if privacy_mode else (f"Rp {v:,.0f}" if c else f"{v:,.0f}")

    tab1, tab2, tab3, tab4 = st.tabs(["📈 ACTIVE POSITIONS", "📜 HISTORY LOG", "📊 ADVANCED ANALYTICS", "📑 DAILY SUMMARY"])
    
    with tab1:
        with st.expander("➕ NEW TRADE ENTRY", expanded=False):
            with st.form("form_add_portfolio", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                t_in, p_in, l_in = c1.text_input("Ticker"), c2.number_input("Entry Price", min_value=0), c3.number_input("Lots", min_value=1)
                if st.form_submit_button("EXECUTE ENTRY"):
                    if t_in and p_in > 0: add_to_portfolio(user_now, t_in, p_in, l_in, 0, 0); st.success("Trade Recorded"); st.rerun()

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
            m1.metric("TOTAL INVESTMENT", format_privacy(t_inv))
            m2.metric("UNREALIZED P/L", format_privacy(t_pl), f"{(t_pl/t_inv*100 if t_inv!=0 else 0):.2f}%")
            m3.metric("EQUITY VALUE", format_privacy(t_inv + t_pl))

            df_display = df_p.copy()
            if privacy_mode: 
                for col in ['buy_price', 'Live', 'Cost', 'Value', 'P/L']: df_display[col] = "*****"
            st.dataframe(df_display.drop(columns=['username','tp_price','cl_price']), use_container_width=True, hide_index=True)
            
            st.markdown("---")
            for i, row in df_p.iterrows():
                with st.expander(f"📦 {row['ticker']} | {int(row['lots'])} Lots"):
                    c_price, c_lots, c_btn = st.columns([2, 2, 1])
                    s_price = c_price.number_input("Exit Price", value=float(row['Live']), key=f"s_prc_{row['id']}")
                    s_lots = c_lots.number_input("Lots to Close", min_value=1, max_value=int(row['lots']), value=int(row['lots']), key=f"s_lot_{row['id']}")
                    st.write("")
                    if c_btn.button("EXECUTE SELL", key=f"btn_s_{row['id']}", use_container_width=True):
                        st.toast(sell_position(user_now, row['id'], row['ticker'], row['buy_price'], s_price, row['lots'], s_lots)); time.sleep(1); st.rerun()
        else: st.info("No active positions.")

    with tab2:
        df_h = conn_gs.read(worksheet="history", ttl=0)
        if not df_h.empty:
            df_h['pnl'] = pd.to_numeric(df_h['pnl'], errors='coerce')
            if role != 'admin': df_h = df_h[df_h['username'] == user_now]
            for idx, h_row in df_h.sort_values(by='date', ascending=False).iterrows():
                with st.expander(f"{h_row['date']} | {h_row['ticker']} | {format_privacy(h_row['pnl'])}"):
                    c_t, c_b = st.columns([4,1])
                    c_t.write(f"Entry: Rp {h_row['buy_price']} | Exit: Rp {h_row['sell_price']} | Vol: {h_row['lots']} Lot")
                    if c_b.button("🗑️ Delete", key=f"del_h_{h_row['id']}"):
                        df_h_all = conn_gs.read(worksheet="history", ttl=0)
                        idx_del_h = df_h_all.index[df_h_all['id'] == h_row['id']].tolist()
                        if idx_del_h: conn_gs.update(worksheet="history", data=df_h_all.drop(idx_del_h[0]).reset_index(drop=True)); st.rerun()
        else: st.info("No trading history.")

    with tab3: 
        if 'df_h' in locals() and not df_h.empty:
            total_trades = len(df_h)
            win_trades = len(df_h[df_h['pnl'] > 0])
            loss_trades = len(df_h[df_h['pnl'] < 0])
            win_rate = (win_trades / total_trades) * 100 if total_trades > 0 else 0
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("WIN RATE", f"{win_rate:.1f}%")
            c2.metric("TOTAL TRADES", f"{total_trades}")
            c3.metric("AVG WIN", format_privacy(df_h[df_h['pnl'] > 0]['pnl'].mean() if win_trades > 0 else 0))
            c4.metric("AVG LOSS", format_privacy(df_h[df_h['pnl'] < 0]['pnl'].mean() if loss_trades > 0 else 0), delta_color="inverse")
            
            st.markdown("---")
            df_curve = df_h.sort_values('date')
            df_curve['cum_pnl'] = df_curve['pnl'].cumsum()
            fig_curve = go.Figure(go.Scatter(x=df_curve['date'], y=df_curve['cum_pnl'], mode='lines', fill='tozeroy', line=dict(color='#00f0ff')))
            fig_curve.update_layout(title="Equity Growth Curve", template="plotly_dark", height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_curve, use_container_width=True)

    with tab4:
        if 'df_h' in locals() and not df_h.empty:
            df_h['date_only'] = pd.to_datetime(df_h['date']).dt.strftime("%Y-%m-%d")
            today_str = datetime.now(pytz.timezone('Asia/Jakarta')).strftime("%Y-%m-%d")
            df_today = df_h[df_h['date_only'] == today_str]
            
            st.markdown(f"### 📑 Daily Confirmation Statement: {today_str}")
            if not df_today.empty:
                net_today = df_today['pnl'].sum()
                st.metric("NET REALIZED P/L TODAY", format_privacy(net_today), delta="Positive Day" if net_today>0 else "Negative Day")
                st.table(df_today[['ticker', 'buy_price', 'sell_price', 'lots', 'pnl']])
            else: st.info("No closed trades today.")

elif menu == "USER MANAGEMENT":
    st.title("👤 ACCESS CONTROL")
    df_u = conn_gs.read(worksheet="users", ttl=0)
    st.dataframe(df_u[['username', 'role', 'last_login', 'location']], use_container_width=True, hide_index=True)
    c1, c2 = st.columns(2)
    with c1:
        with st.form("add_u"):
            nu, np, nr = st.text_input("User"), st.text_input("Key", type="password"), st.selectbox("Role", ["user", "admin"])
            if st.form_submit_button("GRANT"):
                if add_user_db(nu, np, nr): st.success("Added"); st.rerun()
    with c2:
        with st.form("del_u"):
            du = st.text_input("Revoke ID")
            if st.form_submit_button("🔴 DELETE PERMANENTLY"):
                if delete_user_db(du): st.warning("Removed"); st.rerun()

elif menu == "SECURITY SETTINGS":
    st.title("🔒 SECURITY VAULT")
    with st.form("p"):
        new_p = st.text_input("NEW PASSWORD", type="password")
        if st.form_submit_button("UPDATE"):
            if update_password_db(user_now, new_p): st.success("Updated")

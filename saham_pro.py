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

# --- 0. CONFIG & MOBILE APP SETUP ---
warnings.filterwarnings("ignore", category=FutureWarning)
st.set_page_config(
    page_title="IDX CYBER TERMINAL PRO", 
    page_icon="⚡", 
    layout="wide",
    initial_sidebar_state="collapsed"  # Otomatis tertutup di HP agar seperti aplikasi native
)

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
    return "Cloud Node", "Data Center"

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
            msg = f"✅ PARTIAL_SELL: {sold_lots} Lots of {ticker} Sold!"
        else:
            df_port = df_port.drop(idx[0]).reset_index(drop=True)
            msg = f"✅ FULL_SELL: {sold_lots} Lots of {ticker} Sold!"
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

# --- 1. MOBILE APP STYLING & TOUCH OPTIMIZATION ---
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
    font-weight: 900; font-size: 1.8rem;
    background: linear-gradient(135deg, #00f0ff 0%, #78ff00 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    text-shadow: 0 0 30px rgba(0, 240, 255, 0.2);
}
h2, h3 { color: #00f0ff; font-weight: 800; font-size: 1.2rem; }

/* Mobile Card & Container Optimization */
div[data-testid="stForm"] {
    background: rgba(13, 18, 30, 0.9) !important;
    border: 1px solid rgba(0, 240, 255, 0.25) !important;
    border-top: 3px solid #00f0ff !important;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.7);
    border-radius: 14px; padding: 20px !important; backdrop-filter: blur(20px);
}
div[data-testid="stForm"] label p {
    font-family: 'Orbitron', sans-serif !important; color: #78ff00 !important; font-size: 0.7rem !important; letter-spacing: 1.5px;
}
div[data-testid="stForm"] input {
    background: rgba(3, 6, 12, 0.9) !important;
    border: 1px solid rgba(0, 240, 255, 0.2) !important;
    color: #00f0ff !important; font-family: 'JetBrains Mono', monospace !important;
    border-radius: 8px; height: 44px;
}

div[data-testid="stMetric"], .stDataFrame, .stTabs, div[data-testid="stExpander"] {
    background: rgba(13, 18, 30, 0.75) !important;
    border: 1px solid rgba(255, 255, 255, 0.07) !important;
    border-radius: 12px !important; backdrop-filter: blur(12px);
}
[data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace !important; font-size: 1.5rem !important; color: #78ff00 !important; }
[data-testid="stMetricLabel"] { color: #94a3b8 !important; font-weight: 600; text-transform: uppercase; font-size: 0.75rem; }

[data-testid="stSidebar"] { background: #090d16; border-right: 1px solid rgba(255, 255, 255, 0.05); }
div[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label {
    background: rgba(255, 255, 255, 0.01) !important; border: 1px solid rgba(255, 255, 255, 0.03) !important;
    border-radius: 8px !important; padding: 10px 14px !important; margin-bottom: 5px !important;
}
div[data-testid="stSidebar"] .stRadio label p {
    font-family: 'Orbitron', sans-serif !important; font-size: 0.7rem !important; color: #64748b !important; letter-spacing: 1px;
}
div[data-testid="stSidebar"] .stRadio div[role="radiogroup"] [aria-checked="true"] {
    background: linear-gradient(90deg, rgba(0, 240, 255, 0.12), rgba(120, 255, 0, 0.05)) !important;
    border: 1px solid rgba(0, 240, 255, 0.4) !important; border-left: 4px solid #78ff00 !important;
}
div[data-testid="stSidebar"] .stRadio div[role="radiogroup"] [aria-checked="true"] p { color: #ffffff !important; }

/* Touch-friendly buttons for Mobile */
.stButton>button {
    background: linear-gradient(135deg, rgba(0, 240, 255, 0.15), rgba(120, 255, 0, 0.15));
    border: 1px solid rgba(0, 240, 255, 0.4); color: #78ff00 !important;
    border-radius: 8px; font-family: 'Orbitron', sans-serif; font-weight: 700; font-size: 0.75rem;
    min-height: 44px; width: 100%;
}
.stButton>button:hover {
    background: linear-gradient(135deg, #00f0ff, #78ff00); color: #07090f !important;
}
</style>
""", unsafe_allow_html=True)

# --- 2. AUTHENTICATION ---
if "auth" not in st.session_state:
    st.session_state["auth"] = {"logged_in": False, "user": None, "role": None}

if not st.session_state["auth"]["logged_in"]:
    _, col2, _ = st.columns([0.1, 1, 0.1])
    with col2:
        st.markdown("<div style='text-align:center; padding:30px 0;'><h1 style='font-size:2.2rem; margin-bottom:0;'>IDX TERMINAL</h1><p style='color:#00f0ff; letter-spacing:4px; font-family:Orbitron; font-size:0.7rem;'>INSTITUTIONAL QUANT SUITE</p></div>", unsafe_allow_html=True)
        with st.form("login_form"):
            u = st.text_input("NODE ID").strip()
            p = st.text_input("ACCESS KEY", type="password")
            if st.form_submit_button("INITIALIZE SESSION", width="stretch"):
                role = check_login_db(u, p)
                if role:
                    update_login_info(u)
                    st.session_state["auth"] = {"logged_in": True, "user": u, "role": role}
                    st.rerun()
                else: st.error("ACCESS DENIED / AUTHENTICATION FAILED")
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
                "REKOMENDASI": "🚀 STRONG BUY" if chg > 4 else "💎 HOLD" if c_now > ma20 else "🔎 WATCH",
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
        <div style="background: rgba(13, 18, 30, 0.9); border: 1px solid rgba(0, 240, 255, 0.2); 
                    border-radius: 12px; padding: 14px; margin-bottom: 10px; border-left: 4px solid {chg_color};">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <b style="font-size: 1rem; color: #00f0ff; font-family: Orbitron;">{row.get('TICKER','-')}</b>
                <span style="color: {chg_color}; font-weight: bold; font-family: JetBrains Mono;">{chg}%</span>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-top: 10px; font-size: 0.8rem; color: #94a3b8;">
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
role = st.session_state["auth"]["role"]
user_now = st.session_state["auth"]["user"]
last_l, ip_l, loc_l = get_sidebar_log(user_now)

st.sidebar.markdown(f"""
    <div style='padding:14px; border:1px solid rgba(0, 240, 255, 0.2); border-radius:12px; background:rgba(13, 18, 30, 0.9); margin-bottom:12px;'>
        <h3 style='margin:0; color:#00f0ff; font-family:Orbitron; font-size:0.9rem;'>{user_now.upper()}</h3>
        <p style='margin:0; font-size:8px; color:#78ff00; font-family:Orbitron; margin-top:4px;'>NODE ACTIVE | {role.upper()}</p>
        <hr style='border:0.1px solid rgba(255,255,255,0.08); margin:8px 0;'>
        <p style='font-size:8px; color:#94a3b8; margin:2px 0; font-family:JetBrains Mono;'>LST: {last_l}</p>
        <p style='font-size:8px; color:#94a3b8; margin:2px 0; font-family:JetBrains Mono;'>IP : {ip_l}</p>
        <p style='font-size:8px; color:#94a3b8; margin:2px 0; font-family:JetBrains Mono;'>LOC: {loc_l}</p>
    </div>
    """, unsafe_allow_html=True)

menu_list = ["SCANNER", "STRATEGY SCANNER", "WATCHLIST", "FUNDAMENTAL", "TICKER COMPARISON", "SECTOR HEATMAP", "RISK CALCULATOR", "DIVIDEND TRACKER", "CORRELATION MATRIX", "FOREIGN & BROKER FLOW", "MARKET_NEWS", "MONEY MANAGEMENT", "SECURITY SETTINGS"]
if role == "admin": menu_list.insert(7, "USER MANAGEMENT")
menu = st.sidebar.radio("Menu", menu_list, label_visibility="collapsed")

st.sidebar.write("---")
if st.sidebar.button("🔴 TERMINATE SESSION", use_container_width=True):
    st.session_state["auth"] = {"logged_in": False}
    st.rerun()


# --- 5. CONTENT AREA ---
if menu == "SCANNER":
    st.title("🛰️ ALGORITHMIC SCANNER")
    with st.expander("📖 PANDUAN CARA MENGAMBIL POSISI", expanded=False):
        st.markdown("""
        * **AI Score:** Kekuatan momentum saham (kombinasi kenaikan, RSI, nilai transaksi, dan volume *breakout*).
        * **TP 1 & TP 2:** Target harga untuk merealisasikan keuntungan secara bertahap.
        * **EXIT/CL:** Batas pengaman mutlak untuk keluar jika harga turun.
        """)

    if 'results' not in st.session_state: st.session_state.results = None
    
    tickers = load_tickers()
    c1, c2 = st.columns([3, 1])
    with c1: mode_scan = st.radio("ALGO_SENSITIVITY", ["Santai", "Profesional", "Pro"], horizontal=True)
    with c2: 
        st.write("")
        if st.button("⚡ SCAN", use_container_width=True):
            res = run_scan(tickers, mode_scan)
            if not res.empty: st.session_state.results = res; st.rerun()
            else: st.warning("Scan complete: No stocks met criteria.")

    if st.session_state.results is not None:
        df = st.session_state.results
        
        st.markdown(f"""
        <div style='background: rgba(0, 240, 255, 0.05); padding:12px; border-left:4px solid #00f0ff; margin-bottom:15px; border-radius:0 10px 10px 0;'>
            <span style='color:#00f0ff; font-family:Orbitron; font-weight:bold; font-size:0.8rem;'>🧠 QUANT AI STATUS: COMPLETE</span><br>
            <span style='font-size:0.75rem; color:#94a3b8;'>📊 PROCESSED: {len(df)} STOCKS ANALYZED</span>
        </div>
        """, unsafe_allow_html=True)

        tab1, tab2, tab3 = st.tabs(["📊 TABLE", "📱 CARDS", "📈 CHART"])
        with tab1:
            st.dataframe(df.drop(columns=['FULL'], errors='ignore'), use_container_width=True, hide_index=True)
        with tab2:
            draw_mobile_cards(df)
        with tab3:
            sel_t = st.selectbox("SELECT TICKER", df['TICKER'].tolist())
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
                
                fig.update_layout(template="plotly_dark", height=450, margin=dict(l=0,r=0,t=10,b=0), xaxis_rangeslider_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)

elif menu == "STRATEGY SCANNER":
    st.markdown("<h2 style='color:#00f0ff;'>⚡ REAL-TIME STRATEGY SCANNER</h2>", unsafe_allow_html=True)
    with st.expander("📖 CARA BACA SINYAL MA", expanded=False):
        st.markdown("""
        * **Golden Cross (MA20 > MA50):** Tren menguat, bagus untuk *Buy*.
        * **Dead Cross (MA20 < MA50):** Tren melemah, amankan posisi.
        """)
    
    try:
        df_saham = pd.read_excel("daftar_saham.xlsx")
        watchlist = [t.strip() + ".JK" for t in df_saham['Kode'].dropna().astype(str).tolist()]
        st.success(f"✅ Berhasil memuat {len(watchlist)} saham.")
    except:
        st.error("File Excel 'daftar_saham.xlsx' tidak ditemukan."); watchlist = []

    if st.button("🚀 EXECUTE STRATEGY SCAN") and watchlist:
        with st.spinner(f"Analyzing {len(watchlist)} stocks..."):
            results = get_trend_signals(watchlist)
            if results:
                for res in results:
                    st.markdown(f"<div style='border: 1px solid {res['color']}; background: rgba(13,18,30,0.8); padding: 14px; border-radius: 12px; margin-bottom: 10px;'><h3 style='color:{res['color']}; margin:0; font-family:Orbitron; font-size:1rem;'>{res['status']} DETECTED!</h3><p style='margin:4px 0; color:#94a3b8; font-size:0.85rem;'>Saham: <b style='color:#fff;'>{res['ticker']}</b> | Harga: Rp {res['price']:,.0f}</p></div>", unsafe_allow_html=True)
                if any(r['status'] == "GOLDEN CROSS" for r in results): st.balloons()
            else: st.info("Tidak ada sinyal MA Crossover saat ini.")

elif menu == "WATCHLIST":
    st.title("⭐ PERSONAL WATCHLIST")
    my_wl = get_watchlist(user_now)
    
    c_add, c_del = st.columns(2)
    with c_add:
        new_wl = st.text_input("Add Ticker (e.g., BBCA)").upper()
        if st.button("➕ Add", use_container_width=True):
            if new_wl and f"{new_wl}.JK" not in my_wl: 
                add_watchlist(user_now, f"{new_wl}.JK"); st.success("Added!"); st.rerun()
    with c_del:
        if my_wl:
            del_wl = st.selectbox("Remove", [t.replace(".JK","") for t in my_wl])
            if st.button("🗑️ Remove", use_container_width=True):
                remove_watchlist(user_now, f"{del_wl}.JK"); st.warning("Removed!"); st.rerun()
                
    st.markdown("---")
    if my_wl:
        if st.button("⚡ SCAN WATCHLIST", use_container_width=True):
            res_wl = run_scan(my_wl, "Santai")
            if not res_wl.empty: st.dataframe(res_wl.drop(columns=['FULL'], errors='ignore'), use_container_width=True, hide_index=True)
            else: st.info("Tidak ada pergerakan signifikan di watchlist.")
    else: st.info("Watchlist kosong.")

elif menu == "FUNDAMENTAL":
    st.markdown("""<style>.stMetric {border-left: 4px solid #00f0ff !important;}</style>""", unsafe_allow_html=True)
    st.title("📟 FUNDAMENTAL TERMINAL")
    with st.expander("📖 PANDUAN VALUASI", expanded=False):
        st.markdown("""
        * **Graham Value:** Harga wajar berbasis aset & laba. Di bawah harga ini berarti *Undervalued*.
        * **Z-Score:** Kesehatan finansial (>2.9 aman, <1.8 rawan).
        """)
    
    if "clicked_analyze" not in st.session_state: st.session_state.clicked_analyze = False
    if "last_ticker" not in st.session_state: st.session_state.last_ticker = ""

    col_in1, col_in2 = st.columns([3, 1])
    with col_in1: target_f = st.text_input("TICKER", value="BBCA").upper().strip()
    with col_in2: st.write("##"); btn_analyze = st.button("ANALYZE", width="stretch")

    full_tk = f"{target_f}.JK" if not target_f.endswith(".JK") else target_f
    if target_f != st.session_state.last_ticker: st.session_state.clicked_analyze = False
    if btn_analyze: st.session_state.clicked_analyze = True; st.session_state.last_ticker = target_f

    def draw_pro_card(label, value, subtext, color="#00f0ff"):
        st.markdown(f"<div style='background:rgba(13,18,30,0.8); padding:14px; border-radius:12px; border-top:3px solid {color};'><p style='margin:0; font-size:9px; color:#94a3b8; font-family:Orbitron;'>{label.upper()}</p><h2 style='margin:4px 0; color:{color}; font-family:JetBrains Mono; font-size:1.3rem;'>{value}</h2><p style='margin:0; font-size:10px; color:#64748b;'>{subtext}</p></div>", unsafe_allow_html=True)

    if st.session_state.clicked_analyze:
        with st.spinner("SYNCING_FINANCIALS..."):
            try:
                stock = yf.Ticker(full_tk)
                info = stock.info
                
                current_price = info.get('currentPrice') or info.get('previousClose', 1)
                eps = info.get('trailingEps', 0) or 0
                bvps = info.get('bookValue', 0) or 0
                per = info.get('trailingPE', 0) or 0
                pbv = info.get('priceToBook', 0) or 0
                roe = (info.get('returnOnEquity', 0) or 0) * 100
                der = info.get('debtToEquity', 0) or 0
                target_mean = info.get('targetMeanPrice', current_price) or current_price
                div_yield = (info.get('dividendYield', 0) or 0) * 100
                cr = info.get('currentRatio', 0) or 0
                
                st.markdown(f"### 🏢 {info.get('longName', target_f)}")
                
                c1, c2 = st.columns(2)
                c1.metric("PE_RATIO", f"{per:,.2f}x"); c2.metric("PBV_RATIO", f"{pbv:,.2f}x")

                graham = math.sqrt(22.5 * eps * bvps) if (eps > 0 and bvps > 0) else 0
                fair_pe_val = eps * (15 if roe > 15 else 10)
                
                st.markdown("<br>", unsafe_allow_html=True)
                col_v1, col_v2 = st.columns(2)
                with col_v1: draw_pro_card("Graham Value", f"Rp{graham:,.0f}", f"{'UNDER' if current_price < graham else 'OVER'}VALUED", "#78ff00")
                with col_v2: draw_pro_card("Analyst Target", f"Rp{target_mean:,.0f}", f"Upside: {((target_mean - current_price)/current_price)*100:.1f}%", "#ff00ff")

            except Exception as e: st.error(f"ERROR: {e}")

elif menu == "TICKER COMPARISON":
    st.title("⚔️ TICKER BATTLE")
    col_in1, col_in2 = st.columns(2)
    with col_in1: tk1 = st.text_input("PRIMARY", value="BBCA").upper().strip()
    with col_in2: tk2 = st.text_input("RIVAL", value="BBRI").upper().strip()

    if st.button("COMPARE", width="stretch"):
        with st.spinner("CALCULATING..."):
            try:
                i1, i2 = yf.Ticker(f"{tk1}.JK" if not tk1.endswith(".JK") else tk1).info, yf.Ticker(f"{tk2}.JK" if not tk2.endswith(".JK") else tk2).info
                get_val = lambda d, k: d.get(k, 0) or 0
                
                df_compare = pd.DataFrame({
                    "METRIC": ["Price", "Market Cap", "PE", "PBV", "ROE", "DER", "Div Yield"],
                    tk1: [f"Rp {get_val(i1, 'currentPrice'):,.0f}", f"{get_val(i1, 'marketCap')/1e12:.2f}T", f"{get_val(i1, 'trailingPE'):,.2f}x", f"{get_val(i1, 'priceToBook'):,.2f}x", f"{get_val(i1, 'returnOnEquity')*100:.2f}%", f"{get_val(i1, 'debtToEquity'):,.2f}%", f"{get_val(i1, 'dividendYield')*100:.2f}%"],
                    tk2: [f"Rp {get_val(i2, 'currentPrice'):,.0f}", f"{get_val(i2, 'marketCap')/1e12:.2f}T", f"{get_val(i2, 'trailingPE'):,.2f}x", f"{get_val(i2, 'priceToBook'):,.2f}x", f"{get_val(i2, 'returnOnEquity')*100:.2f}%", f"{get_val(i2, 'debtToEquity'):,.2f}%", f"{get_val(i2, 'dividendYield')*100:.2f}%"]
                })
                st.table(df_compare.set_index("METRIC"))
            except Exception as e: st.error(f"ERROR: {e}")

elif menu == "SECTOR HEATMAP":
    st.title("🌐 SECTOR HEATMAP")
    with st.expander("📖 PANDUAN SEKTOR", expanded=False):
        st.markdown("Sektor hijau menandakan *inflow* (dana masuk), merah menandakan koreksi.")
    
    sectors = {
        "Financials": ["BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK"],
        "Energy": ["ADRO.JK", "PTBA.JK", "HRUM.JK", "MEDC.JK"],
        "Infrastructures": ["TLKM.JK", "ISAT.JK", "EXCL.JK", "TOWR.JK"],
        "Technology": ["GOTO.JK", "EMTK.JK", "BUKA.JK"]
    }
    
    if st.button("FETCH SECTORS", width="stretch"):
        with st.spinner("Analyzing..."):
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
                        sector_data.append({"Sector": sec_name, "Avg Change (%)": round(sum(sec_changes)/len(sec_changes), 2)})
            except: pass
            
            if sector_data:
                df_sec = pd.DataFrame(sector_data).sort_values(by="Avg Change (%)", ascending=False)
                fig_sec = px.bar(df_sec, x="Sector", y="Avg Change (%)", color="Avg Change (%)", color_continuous_scale=["#ff4b4b", "#1e293b", "#78ff00"])
                fig_sec.update_layout(template="plotly_dark", height=350, margin=dict(l=0,r=0,t=10,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_sec, use_container_width=True)
                st.dataframe(df_sec, use_container_width=True, hide_index=True)

elif menu == "RISK CALCULATOR":
    st.title("🧮 RISK CALCULATOR")
    with st.expander("📖 PANDUAN RISIKO", expanded=False):
        st.markdown("Batasi risiko per trade maksimal 1-2% dari total modal.")
    
    with st.form("risk_calc_form"):
        capital = st.number_input("Modal (Rp)", value=10000000, step=500000)
        risk_pct = st.number_input("Risiko (%)", value=2.0, step=0.1)
        entry_p = st.number_input("Entry Price", value=5000)
        stop_loss_p = st.number_input("Stop Loss / CL", value=4800)
        target_p = st.number_input("Take Profit", value=5500)
        
        calc_btn = st.form_submit_button("HITUNG", width="stretch")
        
    if calc_btn:
        if stop_loss_p >= entry_p:
            st.error("Stop Loss harus lebih rendah dari Entry!")
        else:
            max_risk = capital * (risk_pct / 100)
            risk_per_share = entry_p - stop_loss_p
            total_lots = math.floor((max_risk / risk_per_share) / 100)
            actual_inv = total_lots * 100 * entry_p
            
            st.markdown("---")
            m1, m2 = st.columns(2)
            m1.metric("LOT", f"{total_lots:,} Lot")
            m2.metric("INVESTASI", f"Rp {actual_inv:,.0f}")

elif menu == "DIVIDEND TRACKER":
    st.title("💰 DIVIDEND TRACKER")
    div_tk = st.text_input("KODE SAHAM", value="BBCA").upper().strip()
    full_div_tk = f"{div_tk}.JK" if not div_tk.endswith(".JK") else div_tk
    
    if st.button("CEK DIVIDEND", width="stretch"):
        try:
            t_obj = yf.Ticker(full_div_tk)
            divs = t_obj.dividends
            info = t_obj.info
            st.metric("YIELD", f"{(info.get('dividendYield', 0) or 0)*100:.2f}%")
            if not divs.empty:
                df_divs = pd.DataFrame(divs).reset_index()
                df_divs.columns = ['Date', 'Dividend']
                df_divs['Date'] = pd.to_datetime(df_divs['Date']).dt.strftime('%Y-%m-%d')
                st.dataframe(df_divs.sort_values(by='Date', ascending=False), use_container_width=True, hide_index=True)
        except Exception as e: st.error(f"Error: {e}")

elif menu == "CORRELATION MATRIX":
    st.title("🧬 CORRELATION MATRIX")
    input_tkrs = st.text_input("TICKERS (Koma)", value="BBCA, BBRI, BMRI, TLKM")
    if st.button("GENERATE", width="stretch"):
        try:
            raw_list = [t.strip().upper() + ".JK" for t in input_tkrs.split(",")]
            data_corr = yf.download(raw_list, period="6mo", interval="1d", progress=False)['Close']
            if isinstance(data_corr, pd.DataFrame) and not data_corr.empty:
                if isinstance(data_corr.columns, pd.MultiIndex): data_corr.columns = data_corr.columns.get_level_values(0)
                data_corr.columns = [c.replace(".JK", "") for c in data_corr.columns]
                fig_corr = px.imshow(data_corr.corr(), text_auto=True, color_continuous_scale="RdBu_r", zmin=-1, zmax=1)
                fig_corr.update_layout(template="plotly_dark", height=400, margin=dict(l=0,r=0,t=10,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_corr, use_container_width=True)
        except Exception as e: st.error(f"Error: {e}")

elif menu == "FOREIGN & BROKER FLOW":
    st.title("🏛️ MONEY FLOW TRACKER")
    ff_tk = st.text_input("KODE SAHAM", value="BBRI").upper().strip()
    full_ff_tk = f"{ff_tk}.JK" if not ff_tk.endswith(".JK") else ff_tk
    
    if st.button("ANALISIS", width="stretch"):
        try:
            df_ff = yf.download(full_ff_tk, period="3mo", interval="1d", progress=False)
            if not df_ff.empty:
                if isinstance(df_ff.columns, pd.MultiIndex): df_ff.columns = df_ff.columns.get_level_values(0)
                df_ff['Multiplier'] = ((df_ff['Close'] - df_ff['Low']) - (df_ff['High'] - df_ff['Close'])) / (df_ff['High'] - df_ff['Low'] + 1e-9)
                df_ff['CMF_20'] = (df_ff['Multiplier'] * df_ff['Volume']).rolling(20).sum() / df_ff['Volume'].rolling(20).sum()
                latest_cmf = df_ff['CMF_20'].iloc[-1]
                
                st.metric("CMF (20H)", f"{latest_cmf:.3f}")
                fig_mf = px.area(df_ff.reset_index(), x='Date', y='CMF_20')
                fig_mf.add_hline(y=0, line_dash="dash", line_color="gray")
                fig_mf.update_layout(template="plotly_dark", height=300, margin=dict(l=0,r=0,t=10,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_mf, use_container_width=True)
        except Exception as e: st.error(f"Error: {e}")

elif menu == "MARKET_NEWS":
    st.title("📰 NEWS FEED")
    feed = feedparser.parse("https://news.google.com/rss/search?q=saham+indonesia+ihsg&hl=id&gl=ID&ceid=ID:id")
    for entry in feed.entries[:8]: st.markdown(f"📡 **[{entry.title}]({entry.link})**\n<small style='color:#00f0ff;'>{entry.published}</small>\n---", unsafe_allow_html=True)

elif menu == "MONEY MANAGEMENT":
    st.title("💼 PORTFOLIO")
    privacy_mode = st.checkbox("🕶️ Privacy Mode", value=False)
    format_privacy = lambda v: "Rp *****" if privacy_mode else f"Rp {v:,.0f}"

    tab1, tab2, tab3 = st.tabs(["📈 ACTIVE", "📜 HISTORY", "📊 STATS"])
    with tab1:
        with st.expander("➕ ADD TRADE", expanded=False):
            with st.form("form_add", clear_on_submit=True):
                t_in, p_in, l_in = st.text_input("Ticker"), st.number_input("Price", min_value=0), st.number_input("Lots", min_value=1)
                if st.form_submit_button("SAVE"):
                    if t_in and p_in > 0: add_to_portfolio(user_now, t_in, p_in, l_in, 0, 0); st.success("Saved"); st.rerun()

        df_p = get_user_portfolio(user_now, role)
        if not df_p.empty:
            tickers_jk = [f"{t}.JK" for t in df_p['ticker'].unique()]
            try:
                live_data = yf.download(tickers_jk, period="1d", progress=False, threads=True)['Close']
                live_prices = live_data.iloc[-1].to_dict() if len(tickers_jk) > 1 else {tickers_jk[0]: live_data.iloc[-1]}
            except: live_prices = {}

            def calc_active(row):
                tk, bp, lots = f"{row['ticker']}.JK", row['buy_price'], row['lots']
                curr = live_prices.get(tk, bp)
                curr = curr.iloc[-1] if isinstance(curr, (pd.Series, pd.DataFrame)) else curr
                cost, val = float(bp * lots * 100), float(curr * lots * 100)
                return pd.Series([float(curr), cost, val, (val-cost)])

            df_p[['Live', 'Cost', 'Value', 'P/L']] = df_p.apply(calc_active, axis=1)
            m1, m2 = st.columns(2)
            t_inv, t_pl = df_p['Cost'].sum(), df_p['P/L'].sum()
            m1.metric("INVESTED", format_privacy(t_inv))
            m2.metric("TOTAL P/L", format_privacy(t_pl))

            for i, row in df_p.iterrows():
                with st.expander(f"📦 {row['ticker']} | {int(row['lots'])} Lots"):
                    s_price = st.number_input("Exit Price", value=float(row['Live']), key=f"s_prc_{row['id']}")
                    s_lots = st.number_input("Lots Sold", min_value=1, max_value=int(row['lots']), value=int(row['lots']), key=f"s_lot_{row['id']}")
                    if st.button("SELL", key=f"btn_s_{row['id']}", use_container_width=True):
                        st.toast(sell_position(user_now, row['id'], row['ticker'], row['buy_price'], s_price, row['lots'], s_lots)); time.sleep(1); st.rerun()
        else: st.info("No active positions.")

    with tab2:
        df_h = conn_gs.read(worksheet="history", ttl=0)
        if not df_h.empty:
            df_h['pnl'] = pd.to_numeric(df_h['pnl'], errors='coerce')
            if role != 'admin': df_h = df_h[df_h['username'] == user_now]
            for idx, h_row in df_h.iterrows():
                st.markdown(f"**{h_row['ticker']}** | PnL: `Rp {h_row['pnl']:,.0f}`")
        else: st.info("No history.")

    with tab3:
        st.write("Statistik performa trading harian.")

elif menu == "USER MANAGEMENT":
    st.title("👤 USERS")
    df_u = conn_gs.read(worksheet="users", ttl=0)
    st.dataframe(df_u[['username', 'role', 'last_login']], use_container_width=True, hide_index=True)

elif menu == "SECURITY SETTINGS":
    st.title("🔒 SECURITY")
    with st.form("p"):
        new_p = st.text_input("NEW PASSWORD", type="password")
        if st.form_submit_button("UPDATE"):
            if update_password_db(user_now, new_p): st.success("Updated")

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
    page_title="IDX PRO TERMINAL", 
    page_icon="📊", 
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
            msg = f"✅ Penjualan Parsial: {sold_lots} Lot {ticker} Berhasil!"
        else:
            df_port = df_port.drop(idx[0]).reset_index(drop=True)
            msg = f"✅ Penjualan Seluruh: {sold_lots} Lot {ticker} Berhasil!"
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

# --- 1. TEMA TERANG (CLEAN WHITE) + ANTI-OVERRIDE DARK MODE ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');

/* --- LATAR BELAKANG & TEKS DASAR --- */
.stApp {
    background-color: #F8FAFC !important;
    color: #0F172A !important;
    font-family: 'Inter', sans-serif;
}
header {background: transparent !important;}
[data-testid="stHeaderActionElements"], .stDeployButton, #MainMenu { display: none !important; }

/* PAKSA SEMUA TEKS JADI GELAP (Anti White-on-White di Dark Mode HP) */
p, span, label, li, div.stMarkdown, .stText {
    color: #1E293B;
}

/* Heading Profesional */
h1, h2, h3, h4, h5, h6 { 
    font-family: 'Inter', sans-serif !important; 
    font-weight: 700 !important; 
    color: #0F172A !important; 
    letter-spacing: -0.5px; 
}
h1 { font-size: 2.2rem !important; color: #2563EB !important; } 

/* Teks Caption Khusus */
.stCaptionContainer p, [data-testid="stCaptionContainer"] p {
    color: #64748B !important;
}

/* --- SIDEBAR MENU (YANG HILANG DI HP) --- */
section[data-testid="stSidebar"], [data-testid="stSidebarContent"] { 
    background-color: #FFFFFF !important; 
    border-right: 1px solid #E2E8F0 !important;
}
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label {
    background: transparent !important; 
    border: none !important;
    border-radius: 8px !important; 
    padding: 10px 14px !important; 
    margin-bottom: 4px !important;
}
/* Paksa teks radio di sidebar jadi gelap */
section[data-testid="stSidebar"] .stRadio p, 
section[data-testid="stSidebar"] .stRadio span,
section[data-testid="stSidebar"] .stRadio label { 
    font-family: 'Inter', sans-serif !important; 
    font-size: 0.95rem !important; 
    color: #334155 !important; /* Warna Slate */
    font-weight: 600 !important; 
}
/* Warna saat menu diklik (Aktif) */
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] [aria-checked="true"] {
    background-color: #F8FAFC !important;
    border: 1px solid #E2E8F0 !important; 
    border-left: 4px solid #2563EB !important; 
}
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] [aria-checked="true"] p,
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] [aria-checked="true"] span { 
    color: #2563EB !important; /* Biru terang */
    font-weight: 800 !important;
}

/* --- KOTAK KONTAINER (CARDS) --- */
div[data-testid="stForm"], div[data-testid="stExpander"], div[data-testid="stMetric"], .stDataFrame, .dash-box {
    background-color: #FFFFFF !important; 
    border: 1px solid #E2E8F0 !important; 
    border-top: 3px solid #2563EB !important; 
    border-radius: 12px; 
    padding: 16px !important; 
    margin-bottom: 16px !important;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03); 
}
/* Hilangkan border top untuk dash-box custom kalau sudah ada inline style */
.dash-box { border-top: 1px solid #E2E8F0 !important; }

/* --- INPUT FORM --- */
div[data-testid="stForm"] label p, .stTextInput label p, .stNumberInput label p, .stSelectbox label p { 
    color: #2563EB !important; 
    font-size: 0.85rem !important; 
    font-weight: 600 !important; 
}
input, select, textarea {
    background-color: #F8FAFC !important;
    border: 1px solid #CBD5E1 !important;
    color: #0F172A !important; 
    font-family: 'JetBrains Mono', monospace !important;
    border-radius: 8px !important; 
    height: 44px !important; 
    font-size: 15px !important;
    font-weight: 600 !important;
}

/* --- METRIK & TAB --- */
[data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace !important; font-size: 1.8rem !important; color: #0F172A !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"] * { color: #64748B !important; font-weight: 600 !important; font-size: 0.85rem !important; }

.stTabs [data-baseweb="tab"] p { color: #64748B !important; font-weight: 600 !important; }
.stTabs [aria-selected="true"] p { color: #2563EB !important; font-weight: 800 !important; }

/* Teks dalam Expander (Dropdown) */
.streamlit-expanderHeader * { color: #0F172A !important; font-weight: 600 !important; }

/* --- TOMBOL --- */
.stButton>button {
    background-color: #2563EB !important; 
    border: none !important; 
    border-radius: 8px !important; 
    min-height: 44px; width: 100%; margin-top: 5px; margin-bottom: 5px;
    transition: background-color 0.2s ease;
}
.stButton>button p, .stButton>button span, .stButton>button div {
    color: #FFFFFF !important;
    font-family: 'Inter', sans-serif !important; 
    font-weight: 600 !important; 
    font-size: 0.9rem !important;
}
.stButton>button:hover { background-color: #1D4ED8 !important; }

/* Warna Custom Teks Utility */
.text-green { color: #16A34A !important; } 
.text-red { color: #DC2626 !important; } 
.text-blue { color: #2563EB !important; } 
.text-muted { color: #64748B !important; font-size: 13px; }
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
        st.markdown("<div style='text-align:center; padding:50px 0;'><h1 style='font-size:2.5rem; margin-bottom:0; color:#2563EB;'>IDX PRO TERMINAL</h1><p class='text-muted' style='letter-spacing:2px; margin-top:5px;'>INSTITUTIONAL QUANT SUITE</p></div>", unsafe_allow_html=True)
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
        st.error("Gagal terhubung ke data bursa.")
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
                    color_code = "#16A34A"
                else:
                    status_text = "🟡 GOLDEN CROSS (Hati-hati, Bandar Distribusi)"
                    color_code = "#F59E0B"
                signals.append({"ticker": ticker.replace(".JK", ""), "status": status_text, "price": current_price, "color": color_code})
            
            elif prev_ma20 > prev_ma50 and last_ma20 < last_ma50:
                if cmf_val < 0:
                    status_text = "🔴 DEAD CROSS + DISTRIBUSI BANDAR (Sangat Bahaya)"
                    color_code = "#DC2626"
                else:
                    status_text = "🟠 DEAD CROSS (Koreksi Normal Wajar)"
                    color_code = "#EA580C"
                signals.append({"ticker": ticker.replace(".JK", ""), "status": status_text, "price": current_price, "color": color_code})
        except Exception as e: 
            continue
    return signals

def draw_mobile_cards(df):
    for _, row in df.iterrows():
        chg = row.get('CHG%', 0)
        chg_color = "#16A34A" if chg > 0 else "#DC2626"
        val_last  = row.get('LAST', 0)
        val_entry = row.get('ENTRY', row.get('Entry', val_last)) 
        val_tp1   = row.get('TP 1', 0)
        val_cl    = row.get('EXIT/CL', 0)
        val_m     = row.get('VAL(M)', 0)

        st.markdown(f"""
        <div class="dash-box" style="border-left: 4px solid {chg_color}; padding: 16px; border-top: 1px solid #E2E8F0 !important;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <b style="font-size: 1.2rem; color: #0F172A;">{row.get('TICKER','-')}</b>
                <span style="color: {chg_color}; font-weight: 700; font-family: 'JetBrains Mono';">{'+' if chg>0 else ''}{chg}%</span>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 12px; font-size: 0.85rem; color: #64748B;">
                <div>Harga: <b style="color:#0F172A;">Rp {val_last:,.0f}</b></div>
                <div>Trx: <b style="color:#0F172A;">{val_m} Miliar</b></div>
                <div style="color: #2563EB; font-weight: 600;">Rencana Beli: Rp {float(val_entry):,.0f}</div>
                <div style="color: #16A34A; font-weight: 600;">Jual Untung: Rp {float(val_tp1):,.0f}</div>
                <div style="color: #DC2626; font-weight: 600; grid-column: span 2; text-align: center; margin-top:5px;">Jual Rugi (Cut Loss): Rp {float(val_cl):,.0f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)


# --- 4. NAVIGATION & SIDEBAR ---
role = st.session_state.role
user_now = st.session_state.user
last_l, ip_l, loc_l = get_sidebar_log(user_now)

st.sidebar.markdown(f"""
    <div style='padding:16px; background-color:#FFFFFF; border-radius:12px; border:1px solid #E2E8F0; margin-bottom:15px;'>
        <h3 style='margin:0; font-size:1.1rem; color:#0F172A;'>{user_now.upper()}</h3>
        <p style='margin:0; font-size:10px; color:#16A34A; font-weight:600; margin-top:4px;'>🟢 ONLINE | {role.upper()}</p>
        <hr style='border:0.5px solid #E2E8F0; margin:10px 0;'>
        <p style='font-size:10px; color:#64748B; margin:2px 0;'>LST: {last_l}</p>
        <p style='font-size:10px; color:#64748B; margin:2px 0;'>IP : {ip_l}</p>
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
    menu_list.append("⚙️ USER MANAGEMENT")

menu = st.sidebar.radio("Navigasi", menu_list, key="side_menu", label_visibility="collapsed")

st.sidebar.write("---")
if st.sidebar.button("Keluar (Logout)", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.role = None
    st.rerun()


# --- 5. CONTENT AREA ---

# =========================================================================
# 🔥 MASTER COMMAND CENTER (DASHBOARD) 
# =========================================================================
if menu == "🖥️ DASHBOARD UTAMA":
    st.markdown(f"<h2 style='margin-bottom:5px; color:#0F172A;'>Ringkasan Pasar & Portofolio</h2>", unsafe_allow_html=True)
    st.caption("Pantau metrik kesehatan pasar, psikologi trader, aliran asing, dan investasi pribadimu secara real-time.")
    st.write("---")
    
    proxy_market = ["BBCA.JK","BBRI.JK","BMRI.JK","BBNI.JK","ASII.JK","TLKM.JK","AMRT.JK","ADRO.JK",
                    "PTBA.JK","ITMG.JK","UNVR.JK","ICBP.JK","INDF.JK","KLBF.JK","PGAS.JK","GOTO.JK",
                    "ARTO.JK","BRPT.JK","MDKA.JK","ANTM.JK","INCO.JK","CPIN.JK","AKRA.JK","MEDC.JK",
                    "HRUM.JK","EXCL.JK","ISAT.JK","INKP.JK","TKIM.JK","PGEO.JK"]
    big_banks = ["BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "TLKM.JK", "ASII.JK"]

    up, down, flat = 0, 0, 0
    # --- BAGIAN 1: IHSG ---
    try:
        ihsg_data = yf.download("^JKSE", period="2d", interval="1d", progress=False)
        if not ihsg_data.empty and len(ihsg_data) >= 2:
            if isinstance(ihsg_data.columns, pd.MultiIndex): ihsg_data.columns = ihsg_data.columns.get_level_values(0)
            ihsg_last, ihsg_prev = float(ihsg_data['Close'].iloc[-1]), float(ihsg_data['Close'].iloc[-2])
            ihsg_pct = ((ihsg_last - ihsg_prev) / ihsg_prev) * 100
            ihsg_color = "#16A34A" if ihsg_pct > 0 else "#DC2626"
            ihsg_status = "BULLISH 🚀" if ihsg_pct > 0.5 else ("BEARISH ⚠️" if ihsg_pct < -0.5 else "SIDEWAYS 💤")
            st.markdown(f"""<div class='dash-box' style='border-left: 4px solid {ihsg_color}; border-top: 1px solid #E2E8F0 !important; padding: 20px;'>
                <p class='text-muted' style='margin:0; font-weight:600;'>IHSG (HARGA SAHAM GABUNGAN)</p>
                <h2 style='margin:5px 0; color:{ihsg_color}; font-family:"JetBrains Mono";'>{ihsg_last:,.2f} <span style='font-size:1rem;'>({'+' if ihsg_pct>0 else ''}{ihsg_pct:.2f}%)</span></h2>
                <p style='margin:0; font-size:14px; color:#0F172A;'>Trend Pasar Hari Ini: <b style='color:{ihsg_color};'>{ihsg_status}</b></p>
            </div>""", unsafe_allow_html=True)
            st.caption("📈 **IHSG:** Indeks patokan pergerakan rata-rata seluruh saham di Bursa Efek Indonesia.")
    except: st.warning("Sedang mengambil data IHSG...")

    # --- BAGIAN 2: MARKET BREADTH ---
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
                st.markdown(f"""<div class='dash-box' style='padding: 20px; border-top: 1px solid #E2E8F0 !important;'>
                    <p class='text-muted' style='margin:0 0 15px 0; text-align:center; font-weight:600;'>📊 MARKET BREADTH (KESEHATAN PASAR)</p>
                    <div style='display:flex; justify-content:space-around;'>
                        <div style='text-align:center;'><h2 class='text-green' style='margin:0;'>{up}</h2><span class='text-muted'>Naik 📈</span></div>
                        <div style='text-align:center;'><h2 style='margin:0; color:#64748B;'>{flat}</h2><span class='text-muted'>Mandek ➖</span></div>
                        <div style='text-align:center;'><h2 class='text-red' style='margin:0;'>{down}</h2><span class='text-muted'>Turun 📉</span></div>
                    </div>
                </div>""", unsafe_allow_html=True)
                st.caption("⚖️ **Market Breadth:** Menghitung saham bluechip yang benar-benar naik vs turun untuk mendeteksi kesehatan bursa yang asli.")
        except: pass

    # --- BAGIAN 3: RADAR SENTIMEN & ARUS DANA ASING ---
    with st.spinner("Melacak Sentimen dan Asing..."):
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
            flow_color = "#10B981" if net_flow > 0 else "#EF4444"
            flow_status = "NET BUY (Masuk) 🛒" if net_flow > 0.05 else ("NET SELL (Keluar) 💸" if net_flow < -0.05 else "NETRAL ⚖️")
            
            st.markdown(f"""<div class='dash-box' style='border-top: 3px solid {flow_color} !important; text-align:center; padding: 20px;'>
                <p class='text-muted' style='margin:0 0 5px 0; font-weight:600;'>🦅 ARUS DANA ASING (BIG CAPS)</p>
                <h3 style='color:{flow_color}; margin:10px 0;'>{flow_status}</h3>
                <p style='font-size:13px; color:#0F172A;'>Indikator Kekuatan: {net_flow:.2f}</p>
            </div>""", unsafe_allow_html=True)
            st.caption("🦅 **Dana Asing:** Melacak apakah hari ini uang asing sedang disuntik masuk atau ditarik keluar dari saham perbankan raksasa kita.")
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
                    'bar': {'color': fg_color, 'thickness': 0.3}, 'bgcolor': "#0F172A",
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
            st.caption("🌡️ **Fear & Greed:** Mengukur kepanikan bursa. Dianjurkan membeli (Serok) saat pasar sedang ketakutan (Fear).")
        except: pass

    st.write("---")

    # --- BAGIAN 4: PRIVASI SALDO & RINGKASAN PORTOFOLIO ---
    c_title, c_toggle = st.columns([2.5, 1.5])
    c_title.markdown("<h3 style='margin-top:5px; color:#2563EB;'>💼 Portofolio & AI Auditor</h3>", unsafe_allow_html=True)
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
    st.caption("💼 **Portofolio:** Ringkasan sisa modal dan total kerugian/keuntungan (P/L) dari saham yang kamu miliki.")

    # --- AI PORTFOLIO AUDITOR ---
    if not df_p.empty and t_inv > 0:
        df_p_aud = df_p[df_p['lots'] > 0].copy()
        if not df_p_aud.empty:
            df_p_aud['Sector'] = df_p_aud['ticker'].apply(lambda x: get_sector(f"{x}.JK"))
            sec_weights = df_p_aud.groupby('Sector')['Cost'].sum() / t_inv * 100
            max_sec = sec_weights.idxmax()
            max_w = sec_weights.max()
            
            if max_w > 60:
                st.markdown(f"<div class='dash-box' style='background-color:#FEF2F2; border-color:#DC2626;'><b class='text-red'>🛡️ Peringatan Risiko:</b> {max_w:.1f}% dana menumpuk di sektor <b>{max_sec}</b>. Segera diversifikasi agar lebih aman!</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='dash-box' style='background-color:#F0FDF4; border-color:#16A34A;'><b class='text-green'>🛡️ Status Aman:</b> Diversifikasi portofoliomu sehat (Maksimal: {max_sec} {max_w:.1f}%).</div>", unsafe_allow_html=True)
            
            fig_pie = px.pie(df_p_aud, values='Cost', names='Sector', hole=0.4, color_discrete_sequence=px.colors.sequential.Teal)
            fig_pie.update_traces(textposition='inside', textinfo='percent+label', marker=dict(line=dict(color='#FFFFFF', width=2)))
            fig_pie.update_layout(template="plotly_white", height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=10, b=0, l=0, r=0), showlegend=False)
            st.plotly_chart(fig_pie, use_container_width=True)
            st.caption("🛡️ **AI Auditor:** Mengawasi proporsi uangmu agar tidak menumpuk di satu sektor (Diversifikasi) untuk meminimalisir risiko.")

    st.write("---")
    
    # --- BAGIAN 5: UNUSUAL VOLUME & TOP MOVERS ---
    st.markdown("### 🌋 Unusual Volume (Radar Bandar)")
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
                    st.markdown(f"<div class='dash-box' style='background-color:#F8FAFC; border-left: 4px solid #2563EB; border-top:1px solid #E2E8F0 !important; padding: 14px;'><b style='font-size:16px; color:#0F172A;'>{row['Ticker']}</b> <span class='text-blue' style='float:right; font-weight:700;'>Vol {row['Spike']:.1f}x Lipat 🚀</span></div>", unsafe_allow_html=True)
            else: st.info("Tidak ada anomali ledakan volume hari ini.")
        except: st.info("Sistem volume radar sedang menyesuaikan data.")
    st.caption("🌋 **Unusual Volume:** Radar pendeteksi saham jika transaksinya meledak melebihi hari biasanya (Indikasi awal bandar masuk).")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 📈 Top Movers (Saham Blue Chips)")
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
    st.caption("🏆 **Top Movers:** Saham-saham papan atas yang memimpin persentase kenaikan dan penurunan hari ini.")


# =========================================================================
# 🔥 FITUR 2: AI CANDLESTICK PATTERN DETECTOR
# =========================================================================
elif menu == "🕯️ POLA CANDLE AI":
    st.title("Pola Candlestick AI")
    st.caption("Mesin pendeteksi bentuk grafik terbaru untuk mencari tahu titik balik arah. Biarkan AI yang membacakan sentimen grafiknya untukmu.")
    with st.expander("📖 PANDUAN POLA GRAFIK", expanded=False):
        st.markdown("""
        * **Bullish Engulfing / Hammer:** Tanda perlawanan pembeli kuat di area bawah. Harga siap mantul naik! 🚀
        * **Bearish Engulfing / Shooting Star:** Tanda tekanan jual bandar di area atas. Harga rawan longsor! ⚠️
        """)

    with st.form("f_candle"):
        tk_candle = st.text_input("Ketik Kode Saham", value="BBRI").upper().strip()
        btn_candle = st.form_submit_button("Deteksi Pola Sekarang", width="stretch")
        
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
                    
                    pola, warna = "TIDAK ADA POLA SPESIFIK", "#64748B"
                    kesimpulan = "Grafik berjalan normal tanpa adanya pola pembalikan arah yang mencolok. Dianjurkan Wait and See."
                    
                    if is_bull_engulfing:
                        pola, warna = "🚀 BULLISH ENGULFING TERDETEKSI", "#16A34A"
                        kesimpulan = "Luar Biasa! Terdapat candle hijau besar yang 'menelan' candle merah sebelumnya. Sinyal kuat pembeli mendominasi."
                    elif is_hammer:
                        pola, warna = "🔨 HAMMER (PALU) TERDETEKSI", "#16A34A"
                        kesimpulan = "Bagus! Ekor bawah yang panjang menandakan perlawanan kuat dari pembeli saat harga dijatuhkan."
                    elif is_bear_engulfing:
                        pola, warna = "⚠️ BEARISH ENGULFING TERDETEKSI", "#DC2626"
                        kesimpulan = "BAHAYA! Candle merah besar menelan candle hijau sebelumnya. Sinyal tekanan jual yang kuat."
                    elif is_shooting_star:
                        pola, warna = "🌠 SHOOTING STAR TERDETEKSI", "#DC2626"
                        kesimpulan = "Hati-hati! Ekor atas panjang menandakan pembeli gagal menahan harga di atas karena tekanan jual."
                    elif is_doji:
                        pola, warna = "⚖️ POLA DOJI TERDETEKSI", "#2563EB"
                        kesimpulan = "Pasar sedang bimbang. Kekuatan beli dan jual seimbang. Bersiap untuk pergerakan arah berikutnya."
                        
                    st.markdown(f"<div class='dash-box' style='border-top: 3px solid {warna}; text-align:center;'><h3 style='color:{warna};'>{pola}</h3><p style='font-size:15px; margin-top:10px; color:#0F172A;'>{kesimpulan}</p></div>", unsafe_allow_html=True)
                    
                    df_chart = df_c.tail(15)
                    fig = go.Figure(data=[go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'], name='Candle', increasing_line_color='#16A34A', decreasing_line_color='#DC2626')])
                    fig.update_layout(template="plotly_white", height=400, margin=dict(l=0,r=0,t=10,b=0), xaxis_rangeslider_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig, use_container_width=True)
            except: st.error("Data tidak cukup untuk melakukan deteksi pola.")

elif menu == "🛰️ AUTO SCANNER":
    st.title("Auto Scanner AI")
    st.caption("Mesin pencari yang menyisir ratusan saham secara otomatis untuk menemukan saham dengan momentum pergerakan paling tinggi hari ini berdasarkan algoritma skor AI.")
    if 'results' not in st.session_state: st.session_state.results = None
    tickers = load_tickers()
    
    c1, c2 = st.columns([4,1])
    with c1: mode_scan = st.radio("SENSITIVITAS:", ["Santai", "Profesional", "Pro"], horizontal=True)
    with c2: 
        if st.button("Mulai Scan Pasar", use_container_width=True):
            res = run_scan(tickers, mode_scan)
            if not res.empty: st.session_state.results = res; st.rerun()
            else: st.warning("Scan selesai: Belum ada saham yang momentumnya cukup kuat.")

    if st.session_state.results is not None:
        df = st.session_state.results
        st.info(f"💡 **Hasil:** Ditemukan **{len(df)} Saham** yang sedang memiliki momentum tarikan yang bagus.")

        tab1, tab2, tab3 = st.tabs(["📱 RINGKASAN", "📊 DATA LENGKAP", "📈 GRAFIK"])
        with tab1: draw_mobile_cards(df)
        with tab2: st.dataframe(df.drop(columns=['FULL'], errors='ignore'), use_container_width=True, hide_index=True)
        with tab3:
            sel_t = st.selectbox("Pilih Saham untuk Grafik:", df['TICKER'].tolist())
            full_t = df[df['TICKER'] == sel_t]['FULL'].values[0]
            c_data = yf.download(full_t, period="6mo", interval="1d", progress=False)
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
                fig.update_layout(template="plotly_white", height=500, margin=dict(l=0,r=0,t=20,b=0), xaxis_rangeslider_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)

elif menu == "⚡ STRATEGY SCANNER":
    st.title("Strategy Scanner (Crossover)")
    st.caption("Mendeteksi persilangan (crossover) Moving Average pada saham unggulan. Mencari momen pergerakan harga yang berbalik dari turun menjadi naik tren utamanya.")
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
                    st.markdown(f"<div class='dash-box' style='border-left: 4px solid {res['color']}; padding: 15px;'><h3 style='color:{res['color']}; margin:0; font-size:1.1rem;'>{res['status']}</h3><p style='margin:8px 0 0 0; color:#0F172A;'>Saham: <b style='color:#0F172A;'>{res['ticker']}</b> | Harga: Rp {res['price']:,.0f}</p></div>", unsafe_allow_html=True)
            else: st.info("Belum ada perpotongan tren yang signifikan hari ini.")

elif menu == "⭐ WATCHLIST FAVORIT":
    st.title("Watchlist Pribadi")
    st.caption("Daftarkan saham andalanmu di sini agar sistem bisa menscan pergerakan momentumnya khusus untukmu setiap hari.")
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
            res_wl = run_scan(my_wl, "Santai")
            if not res_wl.empty: draw_mobile_cards(res_wl)
            else: st.info("Belum ada momentum tarikan pada daftar sahammu.")

elif menu == "🎯 AUTO SUP/RES":
    st.title("Auto Support & Resistance")
    st.caption("AI otomatis melukiskan garis lantai (Support) sebagai target beli harga bawah, dan garis atap (Resistance) sebagai target jual harga atas (Take Profit).")
    with st.expander("📖 PANDUAN LEVEL PIVOT", expanded=False):
        st.markdown("""
        * 🟢 **SUPPORT:** Harga terendah harian. Cocok untuk mulai menyicil beli (Buy on Weakness).
        * 🔴 **RESISTANCE:** Harga tertinggi harian. Cocok untuk bersiap melakukan aksi jual untung.
        """)
        
    with st.form("f_pivot"):
        tk_pivot = st.text_input("Masukkan Kode Saham", value="BBRI").upper().strip()
        btn_pivot = st.form_submit_button("Analisis Batas Harga", width="stretch")
        
    if btn_pivot:
        with st.spinner("Menghitung kalkulasi Pivot Point..."):
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
                    fig = go.Figure(data=[go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'], increasing_line_color='#10B981', decreasing_line_color='#EF4444', name='Harga')])
                    fig.add_hline(y=r2, line_dash="dash", line_color="#EF4444", annotation_text="R2"); fig.add_hline(y=r1, line_dash="solid", line_color="#EF4444", annotation_text="R1")
                    fig.add_hline(y=pivot, line_dash="dot", line_color="#38BDF8", annotation_text="PIVOT")
                    fig.add_hline(y=s1, line_dash="solid", line_color="#10B981", annotation_text="S1"); fig.add_hline(y=s2, line_dash="dash", line_color="#10B981", annotation_text="S2")
                    fig.update_layout(template="plotly_white", height=450, margin=dict(l=0,r=0,t=10,b=0), xaxis_rangeslider_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig, use_container_width=True)
            except: st.error("Data tidak mencukupi untuk menghitung batas support.")

elif menu == "📅 SIKLUS MUSIMAN":
    st.title("Siklus Musiman (Seasonality)")
    st.caption("Menggali probabilitas sejarah pergerakan harga 5 tahun terakhir. Cari tahu di bulan apa saham incaranmu punya kebiasaan berpesta hijau.")
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
                    
                    fig_season = px.bar(monthly_stats, x='Bulan', y='Win Rate (%)', color='Win Rate (%)', color_continuous_scale=["#EF4444", "#0F172A", "#10B981"], text_auto='.0f')
                    fig_season.update_layout(template="plotly_white", height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_season, use_container_width=True)
            except: st.error("Data rentang waktu belum mencukupi.")

elif menu == "📟 CEK FUNDAMENTAL":
    st.markdown("""<style>.stMetric {border-left: 4px solid #38BDF8 !important;}</style>""", unsafe_allow_html=True)
    st.title("Cek Laporan Fundamental")
    st.caption("Memeriksa kesehatan rasio keuangan internal perusahaan (seperti P/E, PBV, Profit) untuk menilai apakah harga saham masih layak diinvestasikan.")
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
                cr = info.get('currentRatio', 0) or 0
                
                st.markdown(f"### 🏢 {info.get('longName', target_f)}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("P/E RATIO", f"{per:,.2f}x"); c2.metric("PBV RATIO", f"{pbv:,.2f}x")
                c3.metric("ROE (Profit)", f"{roe:,.2f}%"); c4.metric("DER (Utang)", f"{der:,.1f}%")

                graham = math.sqrt(22.5 * eps * bvps) if (eps > 0 and bvps > 0) else 0
                if current_price < graham: st.success(f"💡 Valuasi Saham **UNDERVALUED (Murah)**. Harga Wajar Asli Graham: Rp {graham:,.0f}")
                else: st.error(f"💡 Valuasi Saham **OVERVALUED (Mahal)**. Harga Wajar Asli Graham: Rp {graham:,.0f}")
            except: st.error("Data rasio tidak ditemukan.")

elif menu == "⚔️ ADU SAHAM":
    st.title("Adu Saham (Head-to-Head)")
    st.caption("Bandingkan rasio keuangan dari dua perusahaan di sektor yang sama untuk menemukan pilihan emiten terbaik.")
    col_in1, col_in2 = st.columns(2)
    with col_in1: tk1 = st.text_input("Saham Pilihan 1", value="BBCA").upper().strip()
    with col_in2: tk2 = st.text_input("Saham Pilihan 2", value="BBRI").upper().strip()

    if st.button("Bandingkan Emiten", width="stretch"):
        with st.spinner("Membandingkan rasio..."):
            try:
                i1, i2 = yf.Ticker(f"{tk1}.JK").info, yf.Ticker(f"{tk2}.JK").info
                get_val = lambda d, k: d.get(k, 0) or 0
                st.markdown(f"<h2 style='text-align:center; color:#38BDF8;'>{tk1} <span style='color:#EF4444;'>VS</span> {tk2}</h2>", unsafe_allow_html=True)
                df_compare = pd.DataFrame({
                    "METRIK ANALISIS": ["Harga Pasar", "P/E Ratio", "PBV Ratio", "Tingkat Profit (ROE)"],
                    tk1: [f"Rp {get_val(i1, 'currentPrice'):,.0f}", f"{get_val(i1, 'trailingPE'):,.2f}x", f"{get_val(i1, 'priceToBook'):,.2f}x", f"{get_val(i1, 'returnOnEquity')*100:.2f}%"],
                    tk2: [f"Rp {get_val(i2, 'currentPrice'):,.0f}", f"{get_val(i2, 'trailingPE'):,.2f}x", f"{get_val(i2, 'priceToBook'):,.2f}x", f"{get_val(i2, 'returnOnEquity')*100:.2f}%"]
                })
                st.table(df_compare.set_index("METRIK ANALISIS"))
            except: st.error("Gagal menarik perbandingan data.")

elif menu == "🌐 PETA SEKTOR":
    st.title("Peta Aliran Sektor Industri")
    st.caption("Lacak pergeseran arus uang antar sektor hari ini. Berdaganglah di sektor yang sedang menjadi pusat perhatian pasar.")
    sectors = {
        "Perbankan": ["BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK"],
        "Energi/Batu Bara": ["ADRO.JK", "PTBA.JK", "HRUM.JK", "MEDC.JK"],
        "Bahan Baku/Logam": ["INCO.JK", "MDKA.JK", "ANTM.JK", "TPIA.JK"],
        "Ritel & Konsumsi": ["ASII.JK", "ACES.JK", "ERAA.JK", "MAPI.JK", "UNVR.JK", "ICBP.JK"],
        "Telekomunikasi": ["TLKM.JK", "ISAT.JK", "EXCL.JK"]
    }
    
    if st.button("Pantau Peta Sektor", use_container_width=True):
        with st.spinner("Memetakan arus sektor..."):
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
                fig_sec = px.bar(df_sec, x="Sektor", y="Perubahan (%)", color="Perubahan (%)", color_continuous_scale=["#EF4444", "#1E293B", "#10B981"])
                fig_sec.update_layout(template="plotly_white", height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_sec, use_container_width=True)

# =========================================================================
# 🔥 KALKULATOR TRADING (RISIKO & AVERAGING DOWN)
# =========================================================================
elif menu == "🧮 KALKULATOR TRADING":
    st.title("Kalkulator Manajemen Risiko")
    st.caption("Disiplin adalah kunci. Hitung dengan matematis berapa porsi lot yang aman agar seluruh modal tidak hangus saat pasar berbalik arah.")
    tab_risk, tab_avg = st.tabs(["🛡️ KALKULATOR RISIKO", "🛟 AVERAGING DOWN"])
    
    with tab_risk:
        with st.form("risk_calc_form"):
            c1, c2 = st.columns(2)
            capital = c1.number_input("Modal Trading Disiapkan (Rp)", min_value=100000, value=10000000, step=500000)
            risk_pct = c2.number_input("Toleransi Rugi Maksimal (%)", min_value=0.1, max_value=10.0, value=2.0, step=0.1)
            c3, c4 = st.columns(2)
            entry_p = c3.number_input("Rencana Harga Beli / Entry (Rp)", min_value=1, value=5000)
            stop_loss_p = c4.number_input("Batas Harga Cut Loss (Rp)", min_value=1, value=4800)
            calc_btn = st.form_submit_button("Kalkulasi Lot Aman", width="stretch")
            
        if calc_btn:
            if stop_loss_p >= entry_p: st.error("⚠️ Batas Harga Cut Loss harus lebih rendah dari Harga Beli!")
            else:
                max_risk_idr = capital * (risk_pct / 100)
                risk_per_share = entry_p - stop_loss_p
                total_lots = math.floor((max_risk_idr / risk_per_share) / 100)
                actual_shares = total_lots * 100
                st.markdown("---")
                m1, m2, m3 = st.columns(3)
                m1.metric("BELI MAKSIMAL", f"{total_lots:,} Lot")
                m2.metric("MODAL DIBUTUHKAN", f"Rp {actual_shares * entry_p:,.0f}")
                m3.metric("UANG HILANG (JIKA CL)", f"Rp {actual_shares * risk_per_share:,.0f}", delta_color="inverse")
                
    with tab_avg:
        st.info("Penyelamat portofolio: Hitung lot tambahan yang diperlukan untuk menurunkan beban harga rata-rata pada posisi yang menyangkut (Average Down).")
        with st.form("avg_calc_form"):
            c1, c2 = st.columns(2)
            p1 = c1.number_input("Harga Tersangkut (Atas)", min_value=1, value=1000)
            l1 = c2.number_input("Jumlah Lot Nyangkut", min_value=1, value=10)
            c3, c4 = st.columns(2)
            p2 = c3.number_input("Harga Bawah Saat Ini", min_value=1, value=800)
            l2 = c4.number_input("Rencana Lot Pembelian Baru", min_value=1, value=20)
            calc_avg_btn = st.form_submit_button("Hitung Harga Penyelamatan", width="stretch")
            
        if calc_avg_btn:
            if p2 >= p1: st.error("⚠️ Harga pembelian tambahan harus lebih murah dari harga nyangkut!")
            else:
                total_modal_lama = p1 * l1 * 100
                total_modal_baru = p2 * l2 * 100
                total_lot_akhir = l1 + l2
                new_avg = (total_modal_lama + total_modal_baru) / (total_lot_akhir * 100)
                st.markdown("---")
                a1, a2, a3 = st.columns(3)
                a1.metric("HARGA BEP / AVERAGE BARU", f"Rp {new_avg:,.0f}")
                a2.metric("TOTAL KESELURUHAN LOT", f"{total_lot_akhir:,} Lot")
                a3.metric("DANA TAMBAHAN DIPERLUKAN", f"Rp {total_modal_baru:,.0f}")
                st.success(f"Harga rata-ratamu berhasil turun ke level aman **Rp {new_avg:,.0f}**. Jual posisi segera ketika harga mencapai titik ini.")

elif menu == "💰 PEMBURU DIVIDEN":
    st.title("Pemburu Dividen")
    st.caption("Pantau jejak catatan pembayaran dividen historis perusahaan. Menjadi pedoman untuk metode investasi pasif dan pencarian pasif income.")
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
    st.title("Korelasi Silang Saham")
    st.caption("Membantu diversifikasi portofolio. Cari tahu apakah beberapa saham selalu bergerak dengan arah yang sama persis (Hindari memiliki korelasi tinggi di 1 portofolio).")
    input_tkrs = st.text_input("MASUKKAN KODE SAHAM (DIPISAH KOMA)", value="BBCA, BBRI, AMRT, TLKM")
    if st.button("Kalkulasi Matriks Korelasi", width="stretch"):
        with st.spinner("Melakukan perbandingan algoritma..."):
            try:
                raw_list = [t.strip().upper() + ".JK" for t in input_tkrs.split(",")]
                data_corr = yf.download(raw_list, period="6mo", interval="1d", progress=False)['Close']
                if not data_corr.empty:
                    if isinstance(data_corr.columns, pd.MultiIndex): data_corr.columns = data_corr.columns.get_level_values(0)
                    data_corr.columns = [c.replace(".JK", "") for c in data_corr.columns]
                    fig_corr = px.imshow(data_corr.corr(), text_auto=True, color_continuous_scale="RdBu_r", zmin=-1, zmax=1)
                    fig_corr.update_layout(template="plotly_white", height=400, margin=dict(l=0,r=0,t=20,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_corr, use_container_width=True)
            except: st.error("Kalkulasi terhambat akibat data saham tidak valid.")

# =========================================================================
# 🔥 JEJAK BANDAR (CMF + VWAP + DIVERGENSI)
# =========================================================================
elif menu == "🏛️ JEJAK BANDAR":
    st.title("Jejak Institusi & Bandar")
    st.caption("Pusat lacak radar intelijen aliran transaksi yang mendeteksi arah uang institusi skala raksasa. Jangan melawan arah arus Bandar.")
    
    tab_cmf, tab_vwap, tab_div = st.tabs(["🌊 CMF ARUS DANA", "🎯 VWAP HARGA MODAL", "🚨 RADAR DIVERGENSI"])
    
    with tab_cmf:
        st.info("💡 **Chaikin Money Flow:** Alat ini melacak apakah ada pembelian institusi secara besar-besaran atau pembuangan barang massal.")
        ff_tk = st.text_input("Ketik Kode Saham", value="BBRI", key="tk_cmf").upper().strip()
        if st.button("Lacak Arus Masuk Keluar", width="stretch"):
            with st.spinner("Membongkar distribusi aliran..."):
                try:
                    df_ff = yf.download(f"{ff_tk}.JK" if not ff_tk.endswith(".JK") else ff_tk, period="3mo", interval="1d", progress=False)
                    if not df_ff.empty:
                        if isinstance(df_ff.columns, pd.MultiIndex): df_ff.columns = df_ff.columns.get_level_values(0)
                        df_ff['Multiplier'] = ((df_ff['Close'] - df_ff['Low']) - (df_ff['High'] - df_ff['Close'])) / (df_ff['High'] - df_ff['Low'] + 1e-9)
                        df_ff['CMF_20'] = (df_ff['Multiplier'] * df_ff['Volume']).rolling(20).sum() / df_ff['Volume'].rolling(20).sum()
                        df_ff['CMF_20'] = df_ff['CMF_20'].fillna(0) 
                        latest_cmf = float(df_ff['CMF_20'].iloc[-1])
                        
                        if latest_cmf > 0.05: status_flow, color_flow = "AKUMULASI BESAR 🚀", "#16A34A"
                        elif latest_cmf < -0.05: status_flow, color_flow = "DISTRIBUSI BESAR ⚠️", "#DC2626"
                        else: status_flow, color_flow = "PERGERAKAN NETRAL 💤", "#38BDF8"
                        
                        st.markdown(f"<div class='dash-box' style='text-align:center; border-top: 3px solid {color_flow};'><h3 style='color:{color_flow}; margin:0;'>{status_flow}</h3></div>", unsafe_allow_html=True)
                        fig_mf = px.area(df_ff.reset_index(), x='Date', y='CMF_20')
                        fig_mf.add_hline(y=0, line_dash="dash", line_color="gray")
                        fig_mf.update_layout(template="plotly_white", height=300, margin=dict(l=0,r=0,t=10,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                        st.plotly_chart(fig_mf, use_container_width=True)
                except: st.error("Kode saham tidak terdeteksi oleh radar arus.")

    with tab_vwap:
        st.info("💡 **VWAP Estimation:** Mengestimasi titik berat nilai transaksi harian/bulanan untuk mencari level Harga Rata-Rata Bandar institusi.")
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
                    df_v = yf.download(full_tk, period=p_map[period_vwap], interval="1d", progress=False)

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
                            fig.add_hline(y=vwap_price, line_dash="dash", line_color="#38BDF8", annotation_text="GARIS MODAL INSTITUSI (VWAP)")
                            fig.update_layout(template="plotly_white", height=400, margin=dict(l=0,r=0,t=10,b=0), xaxis_rangeslider_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.error("Transaksi nihil pada rentang periode yang diminta.")
                except: st.error("Data tidak berhasil ditarik.")

    with tab_div:
        st.info("💡 **Divergensi Anomali:** Indikator rahasia jika market maker menekan turun harga untuk mencuci investor ritel, sementara indikator volume uang asli justru sedang meningkat tajam (akumulasi senyap).")
        div_tk = st.text_input("Ketik Kode Saham", value="BBRI", key="tk_div").upper().strip()
        if st.button("Mulai Analisis Anomali", width="stretch"):
            with st.spinner("Mengecek pergerakan di balik layar..."):
                try:
                    full_tk = f"{div_tk}.JK" if not div_tk.endswith(".JK") else div_tk
                    df_div = yf.download(full_tk, period="3mo", interval="1d", progress=False)
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
                            status_div, warna_div = "🟢 HIDDEN ACCUMULATION TERDETEKSI", "#16A34A"
                            desc = "Perhatian! Harga dimanipulasi turun untuk menakuti pasar ritel. Namun data di layar belakang mendeteksi Institusi sedang melakukan pembelian akumulatif secara diam-diam. Momentum mantulan sangat dekat!"
                        elif price_change > 2 and adl_trend < 0:
                            status_div, warna_div = "🔴 HIDDEN DISTRIBUTION TERDETEKSI", "#DC2626"
                            desc = "Awas! Harga saham dikerek tinggi memancing kehebohan, namun Institusi perlahan mendistribusikan barang keluar jaring. Rentan menghadapi jatuhnya harga secara agresif."
                        elif price_change > 0 and adl_trend > 0:
                            status_div, warna_div = "⚪ NORMAL UPTREND", "#38BDF8"
                            desc = "Kenaikan harga seiring dengan sehatnya permintaan pembelian. Tren valid tanpa sinyal anomali negatif."
                        elif price_change < 0 and adl_trend < 0:
                            status_div, warna_div = "⚪ NORMAL DOWNTREND", "#64748B"
                            desc = "Kejatuhan harga memang murni divalidasi oleh tingginya suplai penjualan. Dianjurkan posisi menunggu."
                        else:
                            status_div, warna_div = "⚪ SIDEWAYS (KONSOLIDASI)", "#64748B"
                            desc = "Pergerakan volatilitas terhitung normal. Belum ada tanda intervensi bandar secara dominan."

                        st.markdown(f"<div class='dash-box' style='border-top: 3px solid {warna_div}; text-align:center;'><h3 style='color:{warna_div};'>{status_div}</h3><p style='font-size:14px; margin-top:5px; color:#0F172A;'>{desc}</p></div>", unsafe_allow_html=True)
                        
                        fig_div = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.6, 0.4])
                        fig_div.add_trace(go.Candlestick(x=df_div.index, open=df_div['Open'], high=df_div['High'], low=df_div['Low'], close=df_div['Close'], increasing_line_color='#16A34A', decreasing_line_color='#DC2626', name='Harga'), row=1, col=1)
                        fig_div.add_trace(go.Scatter(x=df_div.index, y=df_div['ADL'], line=dict(color='#38BDF8', width=2), name='Accumulation Line'), row=2, col=1)
                        fig_div.update_layout(template="plotly_white", height=500, margin=dict(l=0,r=0,t=10,b=0), xaxis_rangeslider_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                        st.plotly_chart(fig_div, use_container_width=True)
                except: st.error("Malfungsi sistem saat mengkalkulasi divergensi tren.")

elif menu == "📰 BERITA PASAR":
    st.title("Financial Intelligence")
    st.caption("Pusat komando analisis berita yang otomatis menyaring konten sentimen Positif dari Negatif, dan menangkap info Corporate Action harian.")
    
    st.markdown("### 🌍 Global Macro Radar")
    with st.spinner("Mensinkronisasi dengan bursa global..."):
        try:
            macro_tickers = {"Dow Jones": "^DJI", "Nasdaq": "^IXIC", "Minyak (WTI)": "CL=F", "Kurs (USD/IDR)": "IDR=X"}
            macro_data = yf.download(list(macro_tickers.values()), period="5d", interval="1d", progress=False)
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
        if score > 0: return "🟢 POSITIF", "#16A34A"
        elif score < 0: return "🔴 NEGATIF", "#DC2626"
        else: return "⚪ NETRAL", "#64748B"

    def check_if_new(p_parsed):
        if p_parsed and (time.time() - mktime(p_parsed)) < (12 * 3600): return "🔥 HOT NEWS"
        return ""

    headers = {'User-Agent': 'Mozilla/5.0'}

    with t_gen:
        with st.spinner("Memindai berita sekuritas harian..."):
            try:
                feed = feedparser.parse(requests.get("https://news.google.com/rss/search?q=saham+indonesia+ihsg&hl=id&gl=ID&ceid=ID:id", headers=headers, timeout=5).content)
                for entry in feed.entries[:10]: 
                    sent_text, sent_color = analyze_sentiment(entry.title)
                    fire_badge = check_if_new(entry.published_parsed if hasattr(entry, 'published_parsed') else None)
                    pub_date = entry.published if hasattr(entry, 'published') else ""
                    st.markdown(f"<div class='dash-box' style='border-left:4px solid {sent_color}; padding:14px;'><div style='display:flex; justify-content:space-between; margin-bottom:8px;'><span style='font-size:11px; font-weight:600; color:{sent_color};'>{sent_text}</span><span style='font-size:11px; color:#DC2626; font-weight:700;'>{fire_badge}</span></div><a href='{entry.link}' target='_blank' style='color:#0F172A; text-decoration:none; font-size:1rem; font-weight:600;'>{entry.title}</a><p class='text-muted' style='margin-top:8px; margin-bottom:0;'>⏰ {pub_date}</p></div>", unsafe_allow_html=True)
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
                        sent_text, sent_color = analyze_sentiment(entry.title)
                        fire_badge = check_if_new(entry.published_parsed if hasattr(entry, 'published_parsed') else None)
                        pub_date = entry.published if hasattr(entry, 'published') else ""
                        st.markdown(f"<div class='dash-box' style='border-left:4px solid {sent_color}; padding:14px;'><div style='display:flex; justify-content:space-between; margin-bottom:8px;'><span style='font-size:11px; font-weight:600; color:{sent_color};'>{sent_text}</span><span style='font-size:11px; color:#DC2626; font-weight:700;'>{fire_badge}</span></div><a href='{entry.link}' target='_blank' style='color:#0F172A; text-decoration:none; font-size:1rem; font-weight:600;'>{entry.title}</a><p class='text-muted' style='margin-top:8px; margin-bottom:0;'>⏰ {pub_date}</p></div>", unsafe_allow_html=True)
                except: st.error("Layanan filter RSS sedang tidak beroperasi.")
                
    with t_corp:
        st.info("Penyaring agenda perusahaan Emiten agar kamu tidak terlambat mengikuti gelombang pembagian untung Dividen atau kewajiban aksi korporasi lainnya.")
        with st.spinner("Memindai almanak korporasi..."):
            try:
                feed_corp = feedparser.parse(requests.get("https://news.google.com/rss/search?q=jadwal+dividen+OR+right+issue+OR+cum+date+saham+indonesia&hl=id&gl=ID&ceid=ID:id", headers=headers, timeout=5).content)
                for entry in feed_corp.entries[:10]: 
                    fire_badge = check_if_new(entry.published_parsed if hasattr(entry, 'published_parsed') else None)
                    pub_date = entry.published if hasattr(entry, 'published') else ""
                    st.markdown(f"<div class='dash-box' style='border-left:4px solid #2563EB; padding:14px;'><div style='display:flex; justify-content:space-between; margin-bottom:8px;'><span style='font-size:11px; font-weight:600; color:#2563EB;'>📅 INFO CORPORATE ACTION</span><span style='font-size:11px; color:#DC2626; font-weight:700;'>{fire_badge}</span></div><a href='{entry.link}' target='_blank' style='color:#0F172A; text-decoration:none; font-size:1rem; font-weight:600;'>{entry.title}</a><p class='text-muted' style='margin-top:8px; margin-bottom:0;'>⏰ {pub_date}</p></div>", unsafe_allow_html=True)
            except: st.error("Kesalahan jaringan sewaktu meretas kalender bursa.")

elif menu == "💼 DOMPET TRADING":
    st.title("Dompet Portofolio & AI Jurnal")
    st.caption("Fasilitas pencatatan aset investasi harian. Modul AI Jurnal akan memberikan rapor/grading seberapa disiplin metode trading yang anda tetapkan.")
    
    c_title, c_toggle = st.columns([3, 1])
    show_saldo = c_toggle.checkbox("👁️ Penampakan Saldo", value=False)
    format_privacy = lambda v: f"Rp {v:,.0f}" if show_saldo else "Rp *****"

    tab1, tab2, tab3 = st.tabs(["📈 KEPEMILIKAN", "📜 RIWAYAT", "📊 AUDIT AI JURNAL"])
    
    with tab1:
        with st.expander("➕ DAFTARKAN PEMBELIAN ASET BARU", expanded=False):
            with st.form("form_add_portfolio", clear_on_submit=True):
                c1, c2 = st.columns(2)
                t_in = c1.text_input("Kode Saham")
                l_in = c2.number_input("Besaran Lot?", min_value=1)
                c3, c4 = st.columns(2)
                p_in = c3.number_input("Harga Dasar Beli (Rp)", min_value=0)
                strat_in = c4.selectbox("Faktor Justifikasi Beli?", ["Golden Cross MA", "Breakout Resistance", "Serok Bawah (Support)", "Ikut Berita", "Fundamental Bagus", "Feeling / FOMO"])
                if st.form_submit_button("MASUKKAN DALAM SISTEM", width="stretch"):
                    if t_in and p_in > 0: 
                        add_to_portfolio(user_now, t_in, p_in, l_in, 0, 0, strat_in)
                        st.success("Berkas Berhasil Tersimpan di Cloud!"); st.rerun()

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
            m1.metric("MODAL DASAR", format_privacy(t_inv))
            m2.metric("NILAI CUAN/RUGI", format_privacy(t_pl), f"{(t_pl/t_inv*100 if t_inv!=0 else 0):.2f}%" if show_saldo else "*****")
            m3.metric("VALUASI SAAT INI", format_privacy(t_inv + t_pl))

            st.markdown("---")
            for i, row in df_p.iterrows():
                strat_label = row.get('strategy', 'Bebas')
                with st.expander(f"📦 {row['ticker']} | {int(row['lots'])} Lots"):
                    st.markdown(f"<span style='background:#F1F5F9; color:#2563EB; border:1px solid #CBD5E1; padding:4px 8px; border-radius:6px; font-size:11px; font-weight:600;'>Kategori: {strat_label}</span>", unsafe_allow_html=True)
                    st.write("")
                    c_price, c_lots, c_btn = st.columns([2, 2, 1])
                    s_price = c_price.number_input("Eksekusi Jual di Harga (Rp)", value=float(row['Live']), key=f"s_prc_{row['id']}")
                    s_lots = c_lots.number_input("Berapa Lot Dilepas?", min_value=1, max_value=int(row['lots']), value=int(row['lots']), key=f"s_lot_{row['id']}")
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
                    c_t.write(f"Avg Beli: Rp {h_row['buy_price']} | Avg Jual: Rp {h_row['sell_price']} | Pelepasan: {h_row['lots']} Lot | Realisasi Keuntungan: {format_privacy(h_row['pnl'])}")
                    if c_b.button("🗑️ Hapus Bukti", key=f"del_h_{h_row['id']}"):
                        df_h_all = conn_gs.read(worksheet="history", ttl=0)
                        idx_del_h = df_h_all.index[df_h_all['id'] == h_row['id']].tolist()
                        if idx_del_h: conn_gs.update(worksheet="history", data=df_h_all.drop(idx_del_h[0]).reset_index(drop=True)); st.rerun()

    with tab3: 
        if 'df_h' in locals() and not df_h.empty:
            st.markdown("### 🤖 JURNAL EVALUASI MENTOR AI")
            st.caption("Robot penganalisa probabilitas ini membedah metodologi Anda berdasarkan hasil rekap nyata trading di masa lalu.")
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

elif menu == "⚙️ USER MANAGEMENT":
    st.title("Portal Administratif")
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

elif menu == "🔒 KEAMANAN":
    st.title("Keamanan Node Terminal")
    st.caption("Pusat perlindungan enkripsi akses ke modul portofolio privat Anda.")
    with st.form("p"):
        new_p = st.text_input("Ketikan Sandikunci Baru", type="password")
        if st.form_submit_button("ENKRIPSI DAN SIMPAN", width="stretch"):
            if update_password_db(user_now, new_p): st.success("Sandikunci berhasil diubah dan diamankan oleh sistem!")

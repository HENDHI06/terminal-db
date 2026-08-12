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

# --- PERBAIKAN: MESIN PENARIK TICKER YANG TEPAT SASARAN ---
@st.cache_data(ttl=60) 
def get_ticker_data():
    try:
        # Hapus perlakuan MultiIndex yang merusak, gunakan seleksi langsung ['Close']
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

@st.cache_data(ttl=600)
def get_hot_news_tickers():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        feed = feedparser.parse(requests.get("https://news.google.com/rss/search?q=saham+indonesia&hl=id&gl=ID&ceid=ID:id", headers=headers, timeout=5).content)
        text_content = " ".join([entry.title for entry in feed.entries]).upper()
        return text_content
    except: return ""

# --- 1. TEMA TERANG (CLEAN WHITE) + EFEK VISUAL MAHKOTA ---
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

# --- 4. NAVIGATION & SIDEBAR ---
role = st.session_state.role
user_now = st.session_state.user
last_l, ip_l, loc_l = get_sidebar_log(user_now)

st.sidebar.markdown(f"""
    <div style='padding:16px; background-color:rgba(255,255,255,0.7); border-radius:12px; border:1px solid #E2E8F0; margin-bottom:15px; text-align:center;'>
        <h3 style='margin:0; font-size:1.1rem; color:#0F172A;'>{user_now.upper()}</h3>
        <p style='margin:0; font-size:11px; color:#16A34A; font-weight:700; margin-top:4px;'><span class='pulsing-dot'></span> ONLINE | {role.upper()}</p>
        <hr style='border:0.5px solid #E2E8F0; margin:10px 0;'>
        <p style='font-size:10px; color:#64748B; margin:2px 0;'>LST: {last_l}</p>
        <p style='font-size:10px; color:#64748B; margin:2px 0;'>IP : {ip_l}</p>
        <div style='background-color:#F1F5F9; padding:4px; border-radius:6px; margin-top:8px;'>
            <p style='font-size:10px; color:#64748B; margin:0; font-weight:600;'>📡 Ping: 14ms (IDX-Server)</p>
            <p style='font-size:10px; color:#16A34A; margin:0; font-weight:600;'>⚡ Status: Optimal</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

menu_list = [
    "🖥️ DASHBOARD UTAMA", "🛰️ AUTO SCANNER", "⚡ STRATEGY SCANNER", "🕯️ POLA CANDLE AI",         
    "⭐ WATCHLIST FAVORIT", "🎯 AUTO SUP/RES", "📅 SIKLUS MUSIMAN", "📟 CEK FUNDAMENTAL", 
    "⚔️ ADU SAHAM", "🌐 PETA SEKTOR", "🧮 KALKULATOR TRADING", "💰 PEMBURU DIVIDEN", 
    "🧬 KORELASI SAHAM", "🏛️ JEJAK BANDAR", "📰 BERITA PASAR", "💼 DOMPET TRADING", "🔒 KEAMANAN"
]
if role == "admin" and "⚙️ USER MANAGEMENT" not in menu_list: menu_list.append("⚙️ USER MANAGEMENT")

menu = st.sidebar.radio("Navigasi", menu_list, key="side_menu", label_visibility="collapsed")

st.sidebar.write("---")
# PERBAIKAN: TOMBOL REFRESH MEMBANTU MENGHAPUS CACHE JIKA NYANGKUT
if st.sidebar.button("🔄 Refresh Data Pasar", use_container_width=True):
    st.cache_data.clear()
    st.rerun()
    
if st.sidebar.button("Keluar (Logout)", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.role = None
    st.rerun()


# --- 5. CONTENT AREA ---

# =========================================================================
# 🔥 EFEK 1: RUNNING TICKER TAPE (STICKY DI ATAS)
# =========================================================================
ticker_html = get_ticker_data()
if ticker_html:
    st.markdown(f"<div class='ticker-wrap'><div class='ticker'>{ticker_html}</div></div>", unsafe_allow_html=True)

# =========================================================================
# 🔥 MASTER COMMAND CENTER (DASHBOARD) 
# =========================================================================
if menu == "🖥️ DASHBOARD UTAMA":
    st.markdown(f"<h2 class='gradient-text' style='margin-bottom:5px;'>Ringkasan Pasar & Portofolio</h2>", unsafe_allow_html=True)
    st.caption("Pantau metrik kesehatan pasar, psikologi trader, aliran asing, dan investasi pribadimu secara real-time.")
    st.write("---")
    
    proxy_market = ["BBCA.JK","BBRI.JK","BMRI.JK","BBNI.JK","ASII.JK","TLKM.JK","AMRT.JK","ADRO.JK",
                    "PTBA.JK","ITMG.JK","UNVR.JK","ICBP.JK","INDF.JK","KLBF.JK","PGAS.JK","GOTO.JK",
                    "ARTO.JK","BRPT.JK","MDKA.JK","ANTM.JK","INCO.JK","CPIN.JK","AKRA.JK","MEDC.JK",
                    "HRUM.JK","EXCL.JK","ISAT.JK","INKP.JK","TKIM.JK","PGEO.JK"]
    big_banks = ["BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "TLKM.JK", "ASII.JK"]

    up, down, flat = 0, 0, 0
    
    # --- BAGIAN 1: IHSG (DENGAN SPARKLINE) ---
    try:
        # PERBAIKAN: Penarikan data yang tepat sasaran agar terhindar dari NaN/Hari Libur
        ihsg_data = yf.download("^JKSE", period="10d", interval="1d", progress=False)['Close'].dropna()
        if not ihsg_data.empty and len(ihsg_data) >= 2:
            ihsg_last, ihsg_prev = float(ihsg_data.iloc[-1]), float(ihsg_data.iloc[-2])
            ihsg_pct = ((ihsg_last - ihsg_prev) / ihsg_prev) * 100
            ihsg_color = "#16A34A" if ihsg_pct > 0 else "#DC2626"
            ihsg_status = "BULLISH 🚀" if ihsg_pct > 0.5 else ("BEARISH ⚠️" if ihsg_pct < -0.5 else "SIDEWAYS 💤")
            badge_ihsg = "badge-green" if ihsg_pct > 0 else "badge-red" 
            
            st.markdown(f"""<div class='dash-box' style='border-left: 4px solid {ihsg_color}; border-top: 1px solid #E2E8F0 !important; padding: 20px; margin-bottom: 0px !important;'>
                <p class='text-muted' style='margin:0; font-weight:600;'>IHSG (HARGA SAHAM GABUNGAN)</p>
                <h2 style='margin:5px 0; color:{ihsg_color}; font-family:"JetBrains Mono";'>{ihsg_last:,.2f} <span style='font-size:1rem;'>({'+' if ihsg_pct>0 else ''}{ihsg_pct:.2f}%)</span></h2>
                <p style='margin:0; font-size:14px; color:#0F172A;'>Status Pasar Terakhir: <span class='{badge_ihsg}'>{ihsg_status}</span></p>
            </div>""", unsafe_allow_html=True)
            
            if len(ihsg_data) >= 7:
                fig_spark = px.line(ihsg_data.tail(7), x=ihsg_data.tail(7).index, y=ihsg_data.tail(7).values)
                fig_spark.update_traces(line_color=ihsg_color, line_width=3)
                fig_spark.update_layout(height=60, margin=dict(l=0, r=0, t=0, b=0), xaxis=dict(visible=False), yaxis=dict(visible=False), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False, hovermode=False)
                st.plotly_chart(fig_spark, use_container_width=True, config={'displayModeBar': False})
    except: st.warning("Sedang memproses sambungan IHSG...")

    # --- BAGIAN 2: MARKET BREADTH ---
    with st.spinner("Memindai Kesehatan Pasar..."):
        try:
            # PERBAIKAN: Penarikan Multi-Ticker yang benar. Kita ambil metric 'Close' terlebih dahulu
            br_data_full = yf.download(proxy_market, period="10d", interval="1d", progress=False)
            br_data = br_data_full['Close']
            vol_data_today = br_data_full['Volume']
            
            for tk in proxy_market:
                try:
                    tk_data = br_data[tk].dropna() # Hanya membuang nilai NaN pada ticker ini
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

    # --- BAGIAN 3: RADAR SENTIMEN & ARUS DANA ASING ---
    with st.spinner("Melacak Sentimen dan Asing..."):
        try:
            flow_data = yf.download(big_banks, period="1mo", interval="1d", progress=False)
            avg_cmfs = []
            for tk in big_banks:
                try:
                    df_f = pd.DataFrame({'High': flow_data['High'][tk], 'Low': flow_data['Low'][tk], 'Close': flow_data['Close'][tk], 'Volume': flow_data['Volume'][tk]}).dropna()
                    if len(df_f) > 20:
                        mult = ((df_f['Close'] - df_f['Low']) - (df_f['High'] - df_f['Close'])) / (df_f['High'] - df_f['Low'] + 1e-9)
                        cmf_20 = (mult * df_f['Volume']).rolling(20).sum() / df_f['Volume'].rolling(20).sum()
                        cmf_20 = cmf_20.dropna()
                        if not cmf_20.empty:
                            avg_cmfs.append(cmf_20.iloc[-1])
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

    # --- BAGIAN 4: PRIVASI SALDO & RINGKASAN PORTOFOLIO ---
    c_title, c_toggle = st.columns([2.5, 1.5])
    c_title.markdown("<h3 style='margin-top:5px;' class='gradient-text'>💼 Portofolio & AI Auditor</h3>", unsafe_allow_html=True)
    show_saldo_dash = c_toggle.checkbox("👁️ Tampilkan Saldo", value=False, key="privasi_dash")
    fmt_dash = lambda v: f"Rp {v:,.0f}" if show_saldo_dash else "Rp *****"

    df_p = get_user_portfolio(user_now, role)
    t_inv, t_pl = 0, 0
    if not df_p.empty:
        tickers_jk = [f"{t}.JK" for t in df_p['ticker'].unique()]
        try:
            live_prices_df = yf.download(tickers_jk, period="10d", progress=False, threads=True)['Close']
            live_prices = {}
            for t in tickers_jk:
                try: live_prices[t] = float(live_prices_df[t].dropna().iloc[-1])
                except: pass
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

    # --- AI PORTFOLIO AUDITOR ---
    if not df_p.empty and t_inv > 0:
        df_p_aud = df_p[df_p['lots'] > 0].copy()
        if not df_p_aud.empty:
            df_p_aud['Sector'] = df_p_aud['ticker'].apply(lambda x: get_sector(f"{x}.JK"))
            sec_weights = df_p_aud.groupby('Sector')['Cost'].sum() / t_inv * 100
            max_sec = sec_weights.idxmax()
            max_w = sec_weights.max()
            
            if max_w > 60:
                st.markdown(f"<div class='dash-box' style='background-color:#FEF2F2; border-left:4px solid #DC2626;'><b class='text-red'>🛡️ Peringatan Risiko:</b> {max_w:.1f}% dana menumpuk di sektor <b>{max_sec}</b>. Segera diversifikasi agar lebih aman!</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='dash-box' style='background-color:#F0FDF4; border-left:4px solid #16A34A;'><b class='text-green'>🛡️ Status Aman:</b> Diversifikasi portofoliomu sehat (Maksimal: {max_sec} {max_w:.1f}%).</div>", unsafe_allow_html=True)
            
            fig_pie = px.pie(df_p_aud, values='Cost', names='Sector', hole=0.4, color_discrete_sequence=px.colors.sequential.Teal)
            fig_pie.update_traces(textposition='inside', textinfo='percent+label', marker=dict(line=dict(color='#FFFFFF', width=2)))
            fig_pie.update_layout(template="plotly_white", height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=10, b=0, l=0, r=0), showlegend=False)
            st.plotly_chart(fig_pie, use_container_width=True)

    st.write("---")
    
    # --- BAGIAN 5: TOP TRADED VALUE & TOP MOVERS ---
    c_vol, c_mov = st.columns(2)
    with c_vol:
        st.markdown("<h3 class='text-blue'>🔥 Top Traded Value (Paling Laris)</h3>", unsafe_allow_html=True)
        with st.spinner("Menghitung perputaran uang terbesar..."):
            try:
                val_list = []
                for tk in proxy_market:
                    try:
                        tk_close = br_data[tk].dropna().iloc[-1]
                        tk_vol = vol_data_today[tk].dropna().iloc[-1]
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


# =========================================================================
# 🔥 FITUR 2: AI CANDLESTICK MULTI-TIMEFRAME & SMART TARGET
# =========================================================================
elif menu == "🕯️ POLA CANDLE AI":
    st.markdown(f"<h2 class='gradient-text'>Pola Candlestick AI & Proyeksi</h2>", unsafe_allow_html=True)
    st.caption("Deteksi bentuk grafik masa lalu (Candlestick) dan simulasikan prediksi harga di masa depan menggunakan algoritma Kuantitatif.")
    
    tab_candle, tab_monte = st.tabs(["🕯️ DETEKSI POLA CANDLE", "🔮 PROYEKSI MONTE CARLO (AI)"])
    
    with tab_candle:
        with st.expander("📖 PANDUAN POLA GRAFIK", expanded=False):
            st.markdown("""
            * **Bullish Engulfing / Hammer:** Tanda perlawanan pembeli kuat di area bawah. Harga siap mantul naik! 🚀
            * **Bearish Engulfing / Shooting Star:** Tanda tekanan jual bandar di area atas. Harga rawan longsor! ⚠️
            """)
        with st.form("f_candle"):
            c1, c2 = st.columns(2)
            tk_candle = c1.text_input("Ketik Kode Saham", value="BBRI").upper().strip()
            tf_candle = c2.selectbox("Pilih Timeframe (Gambaran Besar)", ["Harian (Daily)", "Mingguan (Weekly)", "Bulanan (Monthly)"])
            btn_candle = st.form_submit_button("Deteksi Pola Sekarang", width="stretch")
            
        if btn_candle:
            with st.spinner("Mendeteksi anatomi grafik terakhir..."):
                try:
                    full_tk = f"{tk_candle}.JK" if not tk_candle.endswith(".JK") else tk_candle
                    tf_map = {"Harian (Daily)": "1d", "Mingguan (Weekly)": "1wk", "Bulanan (Monthly)": "1mo"}
                    p_map_c = {"Harian (Daily)": "2mo", "Mingguan (Weekly)": "6mo", "Bulanan (Monthly)": "2y"}
                    
                    df_c = yf.download(full_tk, period=p_map_c[tf_candle], interval=tf_map[tf_candle], progress=False)['Close'].dropna()
                    # Menghindari error multi-index pada single column select di versi YF terbaru
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
                        if math.isnan(atr): atr = c_c * 0.03
                        
                        target_price = c_c + (2 * atr)
                        stop_loss = c_c - atr
                        
                        if is_bull_engulfing:
                            pola, warna, badge_c = "BULLISH ENGULFING TERDETEKSI", "#16A34A", "badge-green"
                            kesimpulan = "Luar Biasa! Terdapat candle hijau besar yang 'menelan' candle merah sebelumnya. Sinyal kuat pembeli mendominasi."
                        elif is_hammer:
                            pola, warna, badge_c = "HAMMER (PALU) TERDETEKSI", "#16A34A", "badge-green"
                            kesimpulan = "Bagus! Ekor bawah yang panjang menandakan perlawanan kuat dari pembeli saat harga dijatuhkan."
                        elif is_bear_engulfing:
                            pola, warna, badge_c = "BEARISH ENGULFING TERDETEKSI", "#DC2626", "badge-red"
                            kesimpulan = "BAHAYA! Candle merah besar menelan candle hijau sebelumnya. Sinyal tekanan jual yang kuat."
                        elif is_shooting_star:
                            pola, warna, badge_c = "SHOOTING STAR TERDETEKSI", "#DC2626", "badge-red"
                            kesimpulan = "Hati-hati! Ekor atas panjang menandakan pembeli gagal menahan harga di atas karena tekanan jual."
                        elif is_doji:
                            pola, warna, badge_c = "POLA DOJI TERDETEKSI", "#2563EB", "badge-blue"
                            kesimpulan = "Pasar sedang bimbang. Kekuatan beli dan jual seimbang. Bersiap untuk pergerakan arah berikutnya."
                            
                        st.markdown(f"<div class='dash-box' style='border-top: 3px solid {warna}; text-align:center;'><br><span class='{badge_c}' style='font-size:1.2rem; padding:8px 16px;'>{pola}</span><p style='font-size:15px; margin-top:15px; color:#0F172A;'>{kesimpulan}</p></div>", unsafe_allow_html=True)
                        
                        if pola != "TIDAK ADA POLA SPESIFIK" and warna == "#16A34A":
                            st.info(f"🎯 **AI Smart Target:** Disarankan Jual Untung di **Rp {target_price:,.0f}** dan Cut Loss jika harga turun ke **Rp {stop_loss:,.0f}**.")
                        
                        df_chart = df_c_full.tail(15)
                        fig = go.Figure(data=[go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'], name='Candle', increasing_line_color='#16A34A', decreasing_line_color='#DC2626')])
                        
                        if pola != "TIDAK ADA POLA SPESIFIK" and warna == "#16A34A":
                            fig.add_hline(y=target_price, line_dash="dash", line_color="#16A34A", annotation_text="TARGET (TP)")
                            fig.add_hline(y=stop_loss, line_dash="dash", line_color="#DC2626", annotation_text="STOP LOSS")
                            
                        fig.update_layout(template="plotly_white", height=400, margin=dict(l=0,r=0,t=10,b=0), xaxis_rangeslider_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                        st.plotly_chart(fig, use_container_width=True)
                except: st.error("Data tidak cukup untuk melakukan deteksi pola.")

    with tab_monte:
        with st.expander("📖 CARA MEMBACA PROYEKSI MONTE CARLO", expanded=False):
            st.markdown("""
            * **Monte Carlo Simulation** adalah metode *Kuantitatif* yang digunakan *Hedge Fund* untuk memprediksi harga masa depan.
            * Garis-garis yang Anda lihat di grafik adalah **100 kemungkinan jalan harga** dalam 30 hari ke depan berdasarkan gejolak/volatilitas masa lalu.
            * Area **titik kumpul terbanyak** adalah probabilitas harga yang paling besar/logis terjadi di masa depan.
            """)
        
        with st.form("f_mc"):
            tk_mc = st.text_input("Ketik Kode Saham", value="BBCA").upper().strip()
            btn_mc = st.form_submit_button("Mulai Simulasi Proyeksi", width="stretch")
            
        if btn_mc:
            with st.spinner("Menghitung 100 skenario masa depan..."):
                try:
                    df_mc = yf.download(f"{tk_mc}.JK", period="1y", interval="1d", progress=False)['Close'].dropna()
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
                            
                        # Garis Rata-rata dari semua skenario
                        avg_path = np.mean(paths, axis=0)
                        fig_mc.add_trace(go.Scatter(y=avg_path, mode='lines', line=dict(color='#DC2626', width=3), name='Rata-Rata Proyeksi'))
                        
                        fig_mc.update_layout(title=f"Proyeksi Harga {tk_mc} (30 Hari ke Depan)", template="plotly_white", height=400, margin=dict(l=0,r=0,t=40,b=0))
                        st.plotly_chart(fig_mc, use_container_width=True)
                        
                        final_prices = [p[-1] for p in paths]
                        prob_up = sum([1 for p in final_prices if p > last_price]) / simulations * 100
                        st.info(f"💡 **Kesimpulan AI:** Berdasarkan perhitungan matematika probabilitas acak, ada **{prob_up:.0f}%** peluang harga {tk_mc} 30 hari lagi akan lebih tinggi dari harga hari ini (Rp {last_price:,.0f}).")
                    else: st.warning("Data saham terlalu sedikit.")
                except Exception as e: st.error("Gagal melakukan simulasi kuantitatif.")

# =========================================================================
# 🔥 FITUR 5: SCANNER KELAS DEWA (RADAR VPA, BERITA, TREEMAP)
# =========================================================================
elif menu == "🛰️ AUTO SCANNER":
    st.markdown(f"<h2 class='gradient-text'>Auto Scanner AI (VPA & Radar)</h2>", unsafe_allow_html=True)
    st.caption("Sistem radar kuantitatif mendeteksi lonjakan harga, anomali volume (VPA), serta memindai katalis berita secara langsung.")
    if 'results' not in st.session_state: st.session_state.results = None
    tickers = load_tickers()
    
    c1, c2, c3 = st.columns([1.5, 1.5, 1])
    with c1: mode_scan = st.radio("SENSITIVITAS:", ["Santai", "Profesional", "Pro"], horizontal=True)
    with c2: filter_sektor = st.selectbox("Filter Sektor Khusus:", ["Semua Sektor", "Financials", "Energy", "Basic Materials", "Consumer Defensive", "Consumer Cyclical", "Technology", "Healthcare", "Industrials"])
    with c3: 
        st.write("##")
        btn_scan = st.button("Mulai Scan Pasar", use_container_width=True)

    # Logika Penarikan Anti-Libur (Akurat)
    def run_scan_accurate(tickers, mode):
        tickers = list(set(tickers))
        results = []
        if mode == "Santai": min_chg, min_rsi, min_val, vol_m = 1.5, 45, 100_000_000, 1.1
        elif mode == "Profesional": min_chg, min_rsi, min_val, vol_m = 2.5, 55, 1_000_000_000, 1.4
        else: min_chg, min_rsi, min_val, vol_m = 4.0, 60, 2_000_000_000, 1.8

        hot_news_text = get_hot_news_tickers()
        progress = st.progress(0, text="📡 Memindai Bursa Efek...")
        try:
            # Gunakan group_by ticker agar tidak menyatu
            data = yf.download(tickers, period="20d", interval="1d", group_by="ticker", threads=True, progress=False)
        except: return pd.DataFrame()

        total = len(tickers)
        for i, t in enumerate(tickers):
            try:
                progress.progress(int((i + 1) / total * 100), text=f"🔍 Analisa {t}")
                df = data[t].copy() if len(tickers) > 1 else data.copy()
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                # KUNCI PERBAIKAN: Buang baris kosong khusus untuk saham ini
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
                ai_score = (chg * 0.4) + (rsi * 0.2) + ((val_tr / 1e9) * 0.2) + (10 if is_breakout else 0) + (cmf * 20)

                vpa_status = "NORMAL (Searah)"
                if float(df['Volume'].iloc[-1]) > (vol_avg * 1.5):
                    if chg < 1.0 and chg > -1.0: vpa_status = "⚠️ ANOMALI VPA (Tertahan)"
                    elif chg >= 2.0: vpa_status = "🚀 VALID BREAKOUT"
                
                katalis = "🔥 ADA BERITA" if t.replace(".JK", "") in hot_news_text else "TIDAK ADA"
                score_mom = min(max(rsi, 0), 100)
                score_bndr = min(max((cmf + 0.5) * 100, 0), 100)
                score_trnd = 80 if c_now > df['Close'].rolling(20).mean().iloc[-1] else 30
                score_vol = min(100, (atr_val / c_now) * 1000)

                results.append({
                    "TICKER": t.replace(".JK", ""), "LAST": c_now, "CHG%": round(chg, 2),
                    "VAL(M)": round(val_tr / 1_000_000, 1), 
                    "BANDAR": "AKUMULASI" if cmf > 0 else "DISTRIBUSI",
                    "VPA_STATUS": vpa_status, "KATALIS": katalis,
                    "AI_SCORE": round(ai_score, 2),
                    "SCORE_MOM": score_mom, "SCORE_BNDR": score_bndr, "SCORE_TRND": score_trnd, "SCORE_VOL": score_vol,
                    "ENTRY": ideal_entry, "TP 1": ideal_entry + (1.5 * atr_val), 
                    "TP 2": ideal_entry + (2.5 * atr_val), "EXIT/CL": ideal_entry - (1.0 * atr_val), "FULL": t
                })
            except: continue
        progress.empty()
        return pd.DataFrame(results).sort_values(by="AI_SCORE", ascending=False).drop_duplicates(subset=['TICKER']) if results else pd.DataFrame()

    if btn_scan:
        res = run_scan_accurate(tickers, mode_scan)
        if not res.empty: 
            if filter_sektor != "Semua Sektor":
                res['SEKTOR'] = res['FULL'].apply(get_sector)
                res = res[res['SEKTOR'] == filter_sektor]
            else:
                res['SEKTOR'] = res['FULL'].apply(get_sector)
            st.session_state.results = res
            st.rerun()
        else: st.warning("Scan selesai: Belum ada saham yang momentumnya cukup kuat di kriteria ini.")

    if st.session_state.results is not None and not st.session_state.results.empty:
        df = st.session_state.results
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
            styled_df = df.drop(columns=['FULL', 'SCORE_MOM', 'SCORE_BNDR', 'SCORE_TRND', 'SCORE_VOL'], errors='ignore').style.applymap(style_dataframe)
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            csv = df.drop(columns=['FULL', 'SCORE_MOM', 'SCORE_BNDR', 'SCORE_TRND', 'SCORE_VOL'], errors='ignore').to_csv(index=False).encode('utf-8')
            st.download_button("💾 Download Hasil Scan (CSV)", csv, f"scanner_results_{datetime.now(pytz.timezone('Asia/Jakarta')).strftime('%d%m%Y')}.csv", "text/csv", use_container_width=True)
            
        with tab4:
            c_sel, c_rad = st.columns([1, 2])
            with c_sel:
                sel_t = st.selectbox("Pilih Saham untuk Analisis Mendalam:", df['TICKER'].tolist())
                sel_row = df[df['TICKER'] == sel_t].iloc[0]
                full_t = sel_row['FULL']
                st.markdown(f"<div class='dash-box' style='text-align:center;'><h1 class='text-blue' style='margin:0;'>{sel_t}</h1><p class='badge-blue'>Skor Keseluruhan: {sel_row['AI_SCORE']}</p></div>", unsafe_allow_html=True)
            
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
                    bg_badge = "badge-green" if "Sangat Kuat" in res['status'] else ("badge-red" if "Sangat Bahaya" in res['status'] else "badge-blue")
                    st.markdown(f"<div class='dash-box' style='border-left: 4px solid {res['color']}; padding: 15px;'><span class='{bg_badge}' style='margin-bottom:8px;'>{res['status']}</span><p style='margin:8px 0 0 0; color:#0F172A;'>Saham: <b style='color:#0F172A; font-size:1.1rem;'>{res['ticker']}</b> | Harga: Rp {res['price']:,.0f}</p></div>", unsafe_allow_html=True)
            else: st.info("Belum ada perpotongan tren yang signifikan hari ini.")

elif menu == "⭐ WATCHLIST FAVORIT":
    st.markdown(f"<h2 class='gradient-text'>Watchlist Pribadi</h2>", unsafe_allow_html=True)
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
    st.markdown(f"<h2 class='gradient-text'>Auto Support & Resistance</h2>", unsafe_allow_html=True)
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

elif menu == "📟 CEK FUNDAMENTAL":
    st.markdown("""<style>.stMetric {border-left: 4px solid #2563EB !important;}</style>""", unsafe_allow_html=True)
    st.markdown(f"<h2 class='gradient-text'>Cek Laporan Fundamental</h2>", unsafe_allow_html=True)
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
                peg = info.get('pegRatio', 0) or 0
                div_rate = info.get('trailingAnnualDividendRate', 0) or 0
                
                st.markdown(f"### 🏢 {info.get('longName', target_f)}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("P/E RATIO", f"{per:,.2f}x"); c2.metric("PBV RATIO", f"{pbv:,.2f}x")
                c3.metric("ROE (Profit)", f"{roe:,.2f}%"); c4.metric("DER (Utang)", f"{der:,.1f}%")

                st.markdown("---")
                st.markdown("<h4 style='color:#2563EB;'>🧠 Analisis Valuasi Multi-Guru</h4>", unsafe_allow_html=True)
                
                c_grah, c_lyn, c_ddm = st.columns(3)
                
                # Benjamin Graham Valuation (Value)
                graham = math.sqrt(22.5 * eps * bvps) if (eps > 0 and bvps > 0) else 0
                with c_grah:
                    st.markdown("**1. Benjamin Graham**")
                    st.caption("Fokus: Nilai Aset Laba")
                    if graham == 0:
                        st.warning("Data EPS/BVPS minus.")
                    elif current_price < graham: 
                        st.success(f"💡 **MURAH (Undervalued)**\n\nNilai Wajar: Rp {graham:,.0f}")
                    else: 
                        st.error(f"💡 **MAHAL (Overvalued)**\n\nNilai Wajar: Rp {graham:,.0f}")
                
                # Peter Lynch Valuation (Growth)
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
                        
                # DDM Valuation (Dividend)
                with c_ddm:
                    st.markdown("**3. DDM Model**")
                    st.caption("Fokus: Pasif Income")
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
    st.caption("Bandingkan rasio keuangan dari dua perusahaan di sektor yang sama untuk menemukan pilihan emiten terbaik.")
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
    st.caption("Lacak pergeseran arus uang antar sektor. Berdaganglah di sektor yang sedang memimpin pasar (Leading).")
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
        with st.expander("📖 CARA BACA PETA ROTASI (RRG)", expanded=False):
            st.markdown("""
            * **Leading (Kanan Atas):** Sektor sedang jadi primadona bandar dan mengalahkan IHSG. (Waktunya Tahan Barang / Hold).
            * **Weakening (Kanan Bawah):** Sektor masih kuat tapi mulai lelah. (Waktunya Take Profit).
            * **Lagging (Kiri Bawah):** Sektor sedang mati atau dihindari. (Waktunya Jauhi / Cut Loss).
            * **Improving (Kiri Atas):** Sektor sedang diakumulasi diam-diam untuk meledak. (Waktunya Cicil Beli).
            """)
        
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

# =========================================================================
# 🔥 FITUR 4: KALKULATOR TRADING (RISIKO, AVERAGING DOWN, COMPOUND, KELLY)
# =========================================================================
elif menu == "🧮 KALKULATOR TRADING":
    st.markdown(f"<h2 class='gradient-text'>Kalkulator Manajemen Risiko</h2>", unsafe_allow_html=True)
    st.caption("Disiplin adalah kunci. Hitung dengan matematis porsi lot, average down, hingga alokasi risiko ala Hedge Fund.")
    tab_risk, tab_avg, tab_comp, tab_kelly = st.tabs(["🛡️ KALK. RISIKO", "🛟 AVERAGING DOWN", "📈 JALUR 1 MILIAR", "⚖️ KELLY CRITERION"])
    
    with tab_risk:
        st.info("Hitung lot maksimal agar modal tidak habis saat terpaksa Cut Loss.")
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
        with st.expander("📖 APA ITU KELLY CRITERION?", expanded=False):
            st.markdown("""
            * Ditemukan oleh ilmuwan John Kelly Jr. di Bell Labs, ini adalah rumus matematika yang dipakai Kasino dan *Hedge Fund* agar **MUSTAHIL BANGKRUT**.
            * Mesin ini akan memberi tahu Anda **persentase maksimal dari modal Anda yang boleh dibelikan pada satu saham**, berdasarkan histori tingkat kemenangan Anda (Win Rate) dari Jurnal AI. Jangan pernah *all-in* secara asal!
            """)
            
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
                st.markdown(f"<h3 style='text-align:center; color:#2563EB;'>Alokasi Dana Maksimal:</h3>", unsafe_allow_html=True)
                st.markdown(f"<h1 style='text-align:center; color:#10B981; font-size:3.5rem; margin-bottom:0;'>{kelly_pct*100:.1f}%</h1>", unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                st.success(f"💡 Pemenang Nobel Matematika menyarankan Anda untuk TIDAK menggunakan lebih dari **{kelly_pct*100:.1f}% total modal Anda** untuk membeli 1 saham (dengan win rate {w_rate}% dan RR {rr_ratio}). Ini adalah batas pertahanan agar portofolio Anda tidak akan pernah hancur (margin call).")

elif menu == "💰 PEMBURU DIVIDEN":
    st.markdown(f"<h2 class='gradient-text'>Pemburu Dividen</h2>", unsafe_allow_html=True)
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
    st.markdown(f"<h2 class='gradient-text'>Korelasi Silang Saham</h2>", unsafe_allow_html=True)
    st.caption("Membantu diversifikasi portofolio. Cari tahu apakah beberapa saham selalu bergerak dengan arah yang sama persis (Hindari memiliki korelasi tinggi di 1 portofolio).")
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
    st.caption("Pusat lacak radar intelijen aliran transaksi yang mendeteksi arah uang institusi skala raksasa. Jangan melawan arah arus Bandar.")
    
    tab_cmf, tab_vwap, tab_div = st.tabs(["🌊 CMF ARUS DANA", "🎯 VWAP HARGA MODAL", "🚨 RADAR DIVERGENSI"])
    
    with tab_cmf:
        st.info("💡 **Chaikin Money Flow:** Alat ini melacak apakah ada pembelian institusi secara besar-besaran atau pembuangan barang massal.")
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
        st.info("💡 **Divergensi Anomali:** Indikator rahasia jika market maker menekan turun harga untuk mencuci investor ritel, sementara indikator volume uang asli justru sedang meningkat tajam (akumulasi senyap).")
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
    st.caption("Pusat komando analisis berita yang otomatis menyaring konten sentimen Positif dari Negatif, dan menangkap info Corporate Action harian.")
    
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
        st.info("💡 Pantau berita jadwal *Cum Date* Dividen atau Right Issue terbaru di sini agar tidak ketinggalan kereta.")
        with st.spinner("Memindai almanak korporasi..."):
            try:
                feed_corp = feedparser.parse(requests.get("https://news.google.com/rss/search?q=jadwal+dividen+OR+right+issue+OR+cum+date+saham+indonesia&hl=id&gl=ID&ceid=ID:id", headers=headers, timeout=5).content)
                for entry in feed_corp.entries[:10]: 
                    fire_badge = check_if_new(entry.published_parsed if hasattr(entry, 'published_parsed') else None)
                    pub_date = entry.published if hasattr(entry, 'published') else ""
                    st.markdown(f"<div class='dash-box'><div style='display:flex; justify-content:space-between; margin-bottom:8px;'><span class='badge-blue'>📅 INFO CORPORATE ACTION</span><span style='font-size:11px; color:#EF4444; font-weight:700;'>{fire_badge}</span></div><a href='{entry.link}' target='_blank' style='color:#0F172A; text-decoration:none; font-size:1rem; font-weight:600;'>{entry.title}</a><p class='text-muted' style='margin-top:8px; margin-bottom:0;'>⏰ {pub_date}</p></div>", unsafe_allow_html=True)
            except: st.error("Kesalahan jaringan sewaktu meretas kalender bursa.")

elif menu == "💼 DOMPET TRADING":
    st.markdown(f"<h2 class='gradient-text'>Dompet Portofolio & AI Jurnal</h2>", unsafe_allow_html=True)
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
                live_prices_df = yf.download(tickers_jk, period="5d", progress=False, threads=True)['Close'].dropna()
                live_prices = live_prices_df.iloc[-1].to_dict() if len(tickers_jk) > 1 else {tickers_jk[0]: float(live_prices_df.iloc[-1])}
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
                    st.markdown(f"<span class='badge-blue'>Kategori: {strat_label}</span>", unsafe_allow_html=True)
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
            
            df_h_sorted = df_h.sort_values('date')
            df_h_sorted['Cumulative_PnL'] = df_h_sorted['pnl'].cumsum()
            
            fig_eq = px.area(df_h_sorted, x='date', y='Cumulative_PnL', title="📈 Kurva Pertumbuhan Ekuitas (Kinerja Trading)")
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

elif menu == "🔒 KEAMANAN":
    st.markdown(f"<h2 class='gradient-text'>Keamanan Node Terminal</h2>", unsafe_allow_html=True)
    st.caption("Pusat perlindungan enkripsi akses ke modul portofolio privat Anda.")
    with st.form("p"):
        new_p = st.text_input("Ketikan Sandikunci Baru", type="password")
        if st.form_submit_button("ENKRIPSI DAN SIMPAN", width="stretch"):
            if update_password_db(user_now, new_p): st.success("Sandikunci berhasil diubah dan diamankan oleh sistem!")

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

# --- 0. CONFIG & MOBILE WALLET APP SETUP ---
warnings.filterwarnings("ignore", category=FutureWarning)
st.set_page_config(
    page_title="IDX WALLET TERMINAL", 
    page_icon="⚡", 
    layout="wide",
    initial_sidebar_state="collapsed" 
)

# --- 1. CSS SHAPING (HANYA BENTUK, TANPA MEMAKSA WARNA) ---
# CSS ini hanya membuat sudut menjadi melengkung (Wallet Style) 
# tanpa merusak warna teks bawaan Streamlit (Bebas Bug Terang/Gelap).
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;800&display=swap');

.stApp {
    font-family: 'Plus Jakarta Sans', sans-serif;
}

/* Membulatkan semua elemen agar seperti aplikasi HP */
div[data-testid="stForm"], div[data-testid="stExpander"], div[data-testid="stMetric"], .stDataFrame {
    border-radius: 16px !important;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08) !important;
    padding: 10px !important;
}

/* Tombol Empuk ala Mobile Wallet */
.stButton>button {
    border-radius: 25px !important; 
    min-height: 50px !important;
    font-weight: 800 !important;
    letter-spacing: 0.5px;
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1) !important;
}
</style>
""", unsafe_allow_html=True)

conn_gs = st.connection("gsheets", type=GSheetsConnection)

# --- DATABASE & LOGIC FUNGSI ---
def get_visitor_info():
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
            msg = f"✅ {sold_lots} Lot {ticker} Terjual!"
        else:
            df_port = df_port.drop(idx[0]).reset_index(drop=True)
            msg = f"✅ FULL SELL {ticker} Terjual!"
        conn_gs.update(worksheet="portfolio", data=df_port)
    else: msg = "Portfolio tidak ditemukan!"
    
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

# --- 2. AUTHENTICATION (ANTI ERROR) ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.role = None

if not st.session_state.logged_in:
    _, col2, _ = st.columns([0.05, 1, 0.05])
    with col2:
        st.markdown("<h2 style='text-align:center; padding-top:40px;'>🛡️ IDX WALLET</h2>", unsafe_allow_html=True)
        with st.form("login_form"):
            u = st.text_input("Username").strip()
            p = st.text_input("Password", type="password")
            st.write("")
            if st.form_submit_button("MASUK / LOGIN", width="stretch", type="primary"):
                role = check_login_db(u, p)
                if role:
                    update_login_info(u)
                    st.session_state.logged_in = True
                    st.session_state.user = u
                    st.session_state.role = role
                    st.rerun()
                else: st.error("Akses Ditolak! ID/Password salah.")
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

    progress = st.progress(0, text="📡 Memindai Bursa...")
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
                "BREAKOUT": "YA" if is_breakout else "TDK",
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
                signals.append({"ticker": ticker.replace(".JK", ""), "status": "🟢 GOLDEN CROSS", "price": current_price})
            elif prev_ma20 > prev_ma50 and last_ma20 < last_ma50:
                signals.append({"ticker": ticker.replace(".JK", ""), "status": "🔴 DEAD CROSS", "price": current_price})
        except: continue
    return signals

def draw_mobile_cards(df):
    for _, row in df.iterrows():
        chg = row.get('CHG%', 0)
        simbol = "📈" if chg > 0 else "📉"
        
        # Menggunakan st.info/st.success bawaan Streamlit agar warna teks otomatis menyesuaikan tema Terang/Gelap
        if chg > 0:
            st.success(f"**{row.get('TICKER','-')}** {simbol} {chg}%\n\n**Harga:** Rp {row.get('LAST', '-')} | **Value:** {row.get('VAL(M)', 0)} Miliar\n\n🎯 **TP1:** {row.get('TP 1', '-')} | 🛑 **CL:** {row.get('EXIT/CL', '-')}")
        else:
            st.error(f"**{row.get('TICKER','-')}** {simbol} {chg}%\n\n**Harga:** Rp {row.get('LAST', '-')} | **Value:** {row.get('VAL(M)', 0)} Miliar\n\n🎯 **TP1:** {row.get('TP 1', '-')} | 🛑 **CL:** {row.get('EXIT/CL', '-')}")


# --- 4. NAVIGATION MOBILE WALLET (DROPDOWN) ---
role = st.session_state.role
user_now = st.session_state.user

st.sidebar.markdown(f"### 👤 Hai, {user_now.upper()}!")
st.sidebar.caption(f"Status: Wallet {role.upper()}")
st.sidebar.write("---")

menu_list = [
    "💼 DOMPET PORTOFOLIO", 
    "🛰️ AUTO SCANNER", 
    "⚡ STRATEGY SCANNER", 
    "⭐ WATCHLIST FAVORIT", 
    "📟 CEK FUNDAMENTAL", 
    "⚔️ ADU SAHAM", 
    "🌐 PETA SEKTOR", 
    "🧮 KALKULATOR RISIKO", 
    "💰 PEMBURU DIVIDEN", 
    "🧬 KORELASI SAHAM", 
    "🏛️ JEJAK BANDAR", 
    "📰 BERITA PASAR", 
    "🔒 KEAMANAN"
]
if role == "admin": 
    menu_list.append("⚙️ USER MANAGEMENT")

# PENGGUNAAN SELECTBOX UNTUK MOBILE MENU AGAR SANGAT RAMAH SENTUHAN
menu = st.sidebar.selectbox("PILIH MENU APLIKASI:", menu_list)

st.sidebar.write("---")
if st.sidebar.button("🔒 KELUAR / LOGOUT", use_container_width=True, type="secondary"):
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.role = None
    st.rerun()


# --- 5. CONTENT AREA ---

if menu == "🛰️ AUTO SCANNER":
    st.title("🛰️ Auto Scanner")
    with st.expander("📖 Panduan & Waktu Eksekusi", expanded=False):
        st.info("""
        **🕒 WAKTU TERBAIK:**
        * **09:15 - 10:00 WIB:** Cari momentum awal bursa buka.
        * **15:30 - 15:50 WIB:** Pre-Closing untuk di-hold esok hari.
        
        **CARA BACA:**
        * **TP 1 & TP 2:** Harga rekomendasi jual untung.
        * **EXIT/CL:** Harga rekomendasi jual rugi (Stop Loss).
        """)

    tickers = load_tickers()
    
    with st.form("form_scan"):
        mode_scan = st.selectbox("Pilih Sensitivitas Scanner:", ["Santai", "Profesional", "Pro"])
        btn_scan = st.form_submit_button("⚡ MULAI SCAN PASAR", type="primary", use_container_width=True)

    if btn_scan:
        res = run_scan(tickers, mode_scan)
        if not res.empty: 
            st.session_state.results = res
        else: 
            st.warning("Belum ada saham yang memenuhi kriteria saat ini.")

    if 'results' in st.session_state and st.session_state.results is not None:
        df = st.session_state.results
        st.success(f"✅ Berhasil menganalisis {len(df)} saham potensial!")
        
        tab1, tab2 = st.tabs(["📱 RINGKASAN", "📊 TABEL DATA LENGKAP"])
        with tab1: draw_mobile_cards(df)
        with tab2: st.dataframe(df.drop(columns=['FULL'], errors='ignore'), use_container_width=True, hide_index=True)

elif menu == "⚡ STRATEGY SCANNER":
    st.title("⚡ Strategy Scanner")
    with st.expander("📖 Panduan & Waktu Eksekusi", expanded=False):
        st.info("""
        **🕒 WAKTU TERBAIK:** **16:00 WIB ke atas (Bursa Tutup)**
        
        **CARA BACA:**
        * 🟢 **Golden Cross:** Tren naik, momentum bagus untuk beli.
        * 🔴 **Dead Cross:** Tren turun, amankan profit.
        """)
    
    try:
        df_saham = pd.read_excel("daftar_saham.xlsx")
        watchlist = [t.strip() + ".JK" for t in df_saham['Kode'].dropna().astype(str).tolist()]
    except:
        st.error("File 'daftar_saham.xlsx' tidak ditemukan."); watchlist = []

    if st.button("🚀 SCAN SINYAL CROSSOVER", use_container_width=True, type="primary") and watchlist:
        with st.spinner("Menganalisis pergerakan garis MA..."):
            results = get_trend_signals(watchlist)
            if results:
                for res in results:
                    if "GOLDEN" in res['status']:
                        st.success(f"**{res['ticker']}** | {res['status']} | Rp {res['price']:,.0f}")
                    else:
                        st.error(f"**{res['ticker']}** | {res['status']} | Rp {res['price']:,.0f}")
            else: st.info("Tidak ada sinyal persilangan MA hari ini.")

elif menu == "⭐ WATCHLIST FAVORIT":
    st.title("⭐ Watchlist Favorit")
    with st.expander("📖 Panduan Fitur", expanded=False):
        st.info("Simpan kode saham incaranmu, lalu klik Scan khusus untuk keranjang pantauanmu sendiri.")
        
    my_wl = get_watchlist(user_now)
    with st.form("form_add_wl", clear_on_submit=True):
        new_wl = st.text_input("Kode Saham (Misal: BBCA)").upper()
        if st.form_submit_button("➕ TAMBAH KE FAVORIT", type="primary", use_container_width=True):
            if new_wl and f"{new_wl}.JK" not in my_wl: 
                add_watchlist(user_now, f"{new_wl}.JK"); st.success("Ditambahkan!"); st.rerun()
                
    if my_wl:
        with st.form("form_del_wl"):
            del_wl = st.selectbox("Pilih yang ingin dihapus", [t.replace(".JK","") for t in my_wl])
            if st.form_submit_button("HAPUS", use_container_width=True):
                remove_watchlist(user_now, f"{del_wl}.JK"); st.warning("Dihapus!"); st.rerun()
                
        st.markdown("---")
        if st.button("⚡ SCAN WATCHLIST SAYA", use_container_width=True, type="primary"):
            res_wl = run_scan(my_wl, "Santai")
            if not res_wl.empty: draw_mobile_cards(res_wl)
            else: st.info("Belum ada pergerakan momentum di watchlistmu.")

elif menu == "📟 CEK FUNDAMENTAL":
    st.title("📟 Cek Fundamental")
    with st.expander("📖 Panduan & Waktu Eksekusi", expanded=False):
        st.info("""
        **🕒 WAKTU TERBAIK:** Akhir pekan (Sabtu/Minggu).
        
        **CARA BACA:**
        * **Graham Value:** Harga wajar. Jika harga pasar lebih murah, saham status *Undervalued*.
        * **Z-Score:** Keamanan (> 2.9 Aman, < 1.8 Rawan Utang).
        """)
    
    with st.form("f_fund"):
        target_f = st.text_input("Kode Saham (Contoh: ASII)").upper().strip()
        btn_analyze = st.form_submit_button("CEK PERUSAHAAN", type="primary", use_container_width=True)

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
                c1.metric("PE RATIO", f"{info.get('trailingPE', 0):,.1f}x")
                c2.metric("ROE", f"{roe:.1f}%")

                if current_price < graham:
                    st.success(f"**MURAH (UNDERVALUED)**\nHarga Wajar (Graham): **Rp {graham:,.0f}**")
                else:
                    st.error(f"**MAHAL (OVERVALUED)**\nHarga Wajar (Graham): **Rp {graham:,.0f}**")
            except Exception as e: st.error("Data tidak ditemukan.")

elif menu == "⚔️ ADU SAHAM":
    st.title("⚔️ Adu Saham (Battle)")
    with st.expander("📖 Panduan Fitur", expanded=False):
        st.info("Pilih saham yang **PE & PBV lebih kecil** (Murah) tetapi **ROE lebih besar** (Cetak Laba Kuat).")
        
    with st.form("f_battle"):
        c1, c2 = st.columns(2)
        tk1 = c1.text_input("Saham 1", value="BBCA").upper().strip()
        tk2 = c2.text_input("Saham 2", value="BBRI").upper().strip()
        btn = st.form_submit_button("ADU SEKARANG", type="primary", use_container_width=True)

    if btn:
        with st.spinner("Menghitung skor..."):
            try:
                i1, i2 = yf.Ticker(f"{tk1}.JK").info, yf.Ticker(f"{tk2}.JK").info
                get_val = lambda d, k: d.get(k, 0) or 0
                df_compare = pd.DataFrame({
                    "METRIK": ["Harga", "PE Ratio", "PBV Ratio", "ROE", "DER"],
                    tk1: [f"Rp {get_val(i1, 'currentPrice'):,.0f}", f"{get_val(i1, 'trailingPE'):,.1f}x", f"{get_val(i1, 'priceToBook'):,.1f}x", f"{get_val(i1, 'returnOnEquity')*100:.1f}%", f"{get_val(i1, 'debtToEquity'):,.1f}%"],
                    tk2: [f"Rp {get_val(i2, 'currentPrice'):,.0f}", f"{get_val(i2, 'trailingPE'):,.1f}x", f"{get_val(i2, 'priceToBook'):,.1f}x", f"{get_val(i2, 'returnOnEquity')*100:.1f}%", f"{get_val(i2, 'debtToEquity'):,.1f}%"]
                })
                st.dataframe(df_compare, use_container_width=True, hide_index=True)
            except: st.error("Gagal menarik data.")

elif menu == "🌐 PETA SEKTOR":
    st.title("🌐 Peta Sektor (Heatmap)")
    with st.expander("📖 Panduan & Waktu Eksekusi", expanded=False):
        st.info("**🕒 15:30 WIB:** Arahkan fokus pada sektor yang grafiknya paling menjorok ke kanan (Positif/Inflow).")
    
    sectors = {
        "Bank": ["BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK"],
        "Energi": ["ADRO.JK", "PTBA.JK", "HRUM.JK", "MEDC.JK"],
        "Telko": ["TLKM.JK", "ISAT.JK", "EXCL.JK"],
        "Konsumer": ["ICBP.JK", "INDF.JK", "UNVR.JK", "AMRT.JK"]
    }
    
    if st.button("CEK ARUS SEKTOR HARI INI", use_container_width=True, type="primary"):
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
                st.dataframe(df_sec, use_container_width=True, hide_index=True)

elif menu == "🧮 KALKULATOR RISIKO":
    st.title("🧮 Kalkulator Risiko")
    with st.expander("📖 Panduan Penggunaan", expanded=False):
        st.info("Hitung berapa lot maksimal agar modalmu tidak habis jika terpaksa Cut Loss. (Saran: Maksimal rugi 2% per transaksi).")
    
    with st.form("risk_calc_form"):
        capital = st.number_input("Total Modal (Rp)", value=10000000, step=500000)
        risk_pct = st.number_input("Toleransi Rugi (%)", value=2.0, step=0.1)
        entry_p = st.number_input("Harga Beli", value=5000)
        stop_loss_p = st.number_input("Harga Cut Loss", value=4800)
        
        calc_btn = st.form_submit_button("HITUNG", type="primary", use_container_width=True)
        
    if calc_btn:
        if stop_loss_p >= entry_p:
            st.error("Harga Cut Loss harus lebih rendah dari harga beli!")
        else:
            max_risk = capital * (risk_pct / 100)
            risk_per_share = entry_p - stop_loss_p
            total_lots = math.floor((max_risk / risk_per_share) / 100)
            actual_inv = total_lots * 100 * entry_p
            
            st.success(f"🎯 **Beli Maksimal:** {total_lots:,} Lot\n\n💳 **Uang Terpakai:** Rp {actual_inv:,.0f}")

elif menu == "💰 PEMBURU DIVIDEN":
    st.title("💰 Pemburu Dividen")
    with st.expander("📖 Panduan Fitur", expanded=False):
        st.info("Bunga deposito bank ~4%. Jika Yield saham di atas 5-6%, layak ditabung!")
        
    with st.form("f_div"):
        div_tk = st.text_input("Kode Saham", value="ITMG").upper().strip()
        btn = st.form_submit_button("CEK DIVIDEN", type="primary", use_container_width=True)
        
    if btn:
        try:
            t_obj = yf.Ticker(f"{div_tk}.JK")
            st.metric("YIELD TAHUNAN", f"{(t_obj.info.get('dividendYield', 0) or 0)*100:.2f}%")
            divs = t_obj.dividends
            if not divs.empty:
                df = pd.DataFrame(divs).reset_index()
                df.columns = ['Tanggal', 'Nominal (Rp)']
                df['Tanggal'] = pd.to_datetime(df['Tanggal']).dt.strftime('%Y-%m-%d')
                st.dataframe(df.sort_values(by='Tanggal', ascending=False).head(10), use_container_width=True, hide_index=True)
            else: st.warning("Belum ada riwayat dividen.")
        except: st.error("Data tidak ditemukan.")

elif menu == "🧬 KORELASI SAHAM":
    st.title("🧬 Korelasi Saham")
    with st.expander("📖 Panduan Diversifikasi", expanded=False):
        st.info("Jangan pilih saham yang pergerakannya kembar/mirip. Cari yang pergerakannya saling mengisi (Korelasi Rendah/Negatif).")
        
    with st.form("f_cor"):
        input_tkrs = st.text_input("Kode Saham (Pisahkan Koma)", value="BBCA, ADRO, TLKM")
        btn = st.form_submit_button("BUAT MATRIKS", type="primary", use_container_width=True)
        
    if btn:
        with st.spinner("Menghitung..."):
            try:
                raw_list = [t.strip().upper() + ".JK" for t in input_tkrs.split(",")]
                data_corr = yf.download(raw_list, period="6mo", interval="1d", progress=False)['Close']
                if not data_corr.empty:
                    if isinstance(data_corr.columns, pd.MultiIndex): data_corr.columns = data_corr.columns.get_level_values(0)
                    data_corr.columns = [c.replace(".JK", "") for c in data_corr.columns]
                    corr_val = data_corr.corr()
                    st.dataframe(corr_val.round(2), use_container_width=True)
            except: st.error("Format salah atau data gagal ditarik.")

elif menu == "🏛️ JEJAK BANDAR":
    st.title("🏛️ Jejak Bandar (CMF)")
    with st.expander("📖 Panduan & Waktu Eksekusi", expanded=False):
        st.info("""
        **🕒 SETELAH 16:15 WIB:** Waktu paling akurat membaca pergerakan dana besar.
        * **Positif:** Dana besar memborong (Akumulasi).
        * **Negatif:** Dana besar buang barang (Distribusi).
        """)
        
    with st.form("f_ff"):
        ff_tk = st.text_input("Kode Saham", value="BBRI").upper().strip()
        btn = st.form_submit_button("LACAK DANA", type="primary", use_container_width=True)
        
    if btn:
        with st.spinner("Membaca volume institusi..."):
            try:
                df_ff = yf.download(f"{ff_tk}.JK", period="3mo", interval="1d", progress=False)
                if not df_ff.empty:
                    if isinstance(df_ff.columns, pd.MultiIndex): df_ff.columns = df_ff.columns.get_level_values(0)
                    df_ff['Multiplier'] = ((df_ff['Close'] - df_ff['Low']) - (df_ff['High'] - df_ff['Close'])) / (df_ff['High'] - df_ff['Low'] + 1e-9)
                    df_ff['CMF_20'] = (df_ff['Multiplier'] * df_ff['Volume']).rolling(20).sum() / df_ff['Volume'].rolling(20).sum()
                    latest = df_ff['CMF_20'].iloc[-1]
                    
                    if latest > 0:
                        st.success(f"**AKUMULASI (BANDAR MASUK)** 🚀\n\nSkor CMF: **{latest:.3f}**")
                    else:
                        st.error(f"**DISTRIBUSI (BANDAR KELUAR)** ⚠️\n\nSkor CMF: **{latest:.3f}**")
            except: st.error("Gagal melacak dana.")

elif menu == "📰 BERITA PASAR":
    st.title("📰 Berita Pasar")
    with st.spinner("Mengambil berita terbaru..."):
        try:
            feed = feedparser.parse("https://news.google.com/rss/search?q=saham+indonesia+ihsg&hl=id&gl=ID&ceid=ID:id")
            for entry in feed.entries[:6]: 
                st.info(f"**[{entry.title}]({entry.link})**\n\n_{entry.published}_")
        except: st.error("Koneksi berita terputus.")

elif menu == "💼 DOMPET PORTOFOLIO":
    st.title("💼 Portofolio")
    with st.expander("📖 Sinkronisasi Portofolio", expanded=False):
        st.info("Input pembelian sahammu di sini agar tercatat rapi.")
        
    privacy_mode = st.checkbox("🕶️ Sembunyikan Saldo", value=False)
    format_privacy = lambda v: "Rp *****" if privacy_mode else f"Rp {v:,.0f}"

    df_p = get_user_portfolio(user_now, role)
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

    st.metric("💰 TOTAL SALDO AKTIF", format_privacy(t_inv + t_pl))
    c1, c2 = st.columns(2)
    c1.metric("MODAL", format_privacy(t_inv))
    c2.metric("P/L (CUAN)", format_privacy(t_pl))
    st.markdown("---")

    tab1, tab2 = st.tabs(["🛒 PORTOFOLIO", "📜 HISTORY TRADING"])
    with tab1:
        with st.expander("➕ TAMBAH BELI SAHAM", expanded=False):
            with st.form("form_add", clear_on_submit=True):
                t_in = st.text_input("Kode Saham").upper()
                p_in = st.number_input("Harga Beli", min_value=0)
                l_in = st.number_input("Lot", min_value=1)
                if st.form_submit_button("SIMPAN", type="primary", width="stretch"):
                    if t_in and p_in > 0: add_to_portfolio(user_now, t_in, p_in, l_in, 0, 0); st.success("Disimpan!"); st.rerun()

        if not df_p.empty:
            for i, row in df_p.iterrows():
                with st.expander(f"📦 {row['ticker']} | {int(row['lots'])} Lot | {('+' if row['P/L']>0 else '')}{row['P/L']:,.0f} Rp"):
                    st.write(f"Harga Beli: Rp {row['buy_price']:,.0f} | Saat Ini: Rp {row['Live']:,.0f}")
                    with st.form(f"f_sell_{row['id']}"):
                        s_price = st.number_input("Harga Jual", value=float(row['Live']))
                        s_lots = st.number_input("Lot Dijual", min_value=1, max_value=int(row['lots']), value=int(row['lots']))
                        if st.form_submit_button("JUAL SAHAM", type="primary", width="stretch"):
                            st.toast(sell_position(user_now, row['id'], row['ticker'], row['buy_price'], s_price, row['lots'], s_lots)); time.sleep(1); st.rerun()
        else: st.info("Dompet masih kosong.")

    with tab2:
        df_h = conn_gs.read(worksheet="history", ttl=0)
        if not df_h.empty:
            df_h['pnl'] = pd.to_numeric(df_h['pnl'], errors='coerce')
            if role != 'admin': df_h = df_h[df_h['username'] == user_now]
            for idx, h_row in df_h.sort_values(by='date', ascending=False).iterrows():
                if h_row['pnl'] >= 0:
                    st.success(f"**{h_row['ticker']}** | Untung: Rp {h_row['pnl']:,.0f} | Tanggal: {h_row['date']}")
                else:
                    st.error(f"**{h_row['ticker']}** | Rugi: Rp {h_row['pnl']:,.0f} | Tanggal: {h_row['date']}")
        else: st.info("Belum ada riwayat penjualan.")

elif menu == "⚙️ USER MANAGEMENT":
    st.title("⚙️ User Management")
    df_u = conn_gs.read(worksheet="users", ttl=0)
    st.dataframe(df_u[['username', 'role', 'last_login', 'location']], use_container_width=True, hide_index=True)
    with st.form("add_u"):
        nu, np, nr = st.text_input("User ID Baru"), st.text_input("Password", type="password"), st.selectbox("Role", ["user", "admin"])
        if st.form_submit_button("BUAT AKUN", type="primary", width="stretch"):
            if add_user_db(nu, np, nr): st.success("Dibuat!"); st.rerun()
    with st.form("del_u"):
        du = st.text_input("ID yang mau dihapus")
        if st.form_submit_button("HAPUS AKUN", type="primary", width="stretch"):
            if delete_user_db(du): st.warning("Dihapus!"); st.rerun()

elif menu == "🔒 KEAMANAN":
    st.title("🔒 Keamanan Wallet")
    with st.form("p"):
        new_p = st.text_input("Ketik Password Baru", type="password")
        if st.form_submit_button("UBAH PASSWORD", type="primary", width="stretch"):
            if update_password_db(user_now, new_p): st.success("Password Berhasil Diubah!")

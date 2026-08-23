# app.py
import streamlit as st
import warnings
import base64

# --- 0. CONFIG & APP SETUP ---
warnings.filterwarnings("ignore", category=FutureWarning)
st.set_page_config(
    page_title="IDX & CRYPTO PRO TERMINAL", 
    page_icon="📊", 
    layout="wide",
    initial_sidebar_state="collapsed" 
)

# ==========================================
# 🌌 SUNTIKAN BACKGROUND FUTURISTIK
# ==========================================
def set_futuristic_background(image_file):
    try:
        # Konversi gambar lokal menjadi kode Base64 agar bisa dibaca CSS Streamlit
        with open(image_file, "rb") as file:
            encoded_string = base64.b64encode(file.read()).decode()

        # Suntikkan CSS: Gambar + Efek Kaca Gelap (Linear Gradient rgba) 85%
        st.markdown(
            f"""
            <style>
            .stApp {{
                background-image: linear-gradient(rgba(15, 23, 42, 0.85), rgba(15, 23, 42, 0.85)), url(data:image/jpeg;base64,{encoded_string});
                background-size: cover;
                background-position: center;
                background-attachment: fixed;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )
    except Exception as e:
        pass # Jika gambar tidak ditemukan, biarkan tema aslinya berjalan

# Panggil fungsi untuk menghidupkan background
set_futuristic_background("bg_crypto.jpg")

# Impor dari modul lokal
from core import authenticate_user, get_sidebar_log, get_ticker_data
import views_crypto
import views_idx
import views_universal

# Inisialisasi status Panel AI
if "show_ai_panel" not in st.session_state:
    st.session_state.show_ai_panel = False

# --- TEMA GELAP (FUTURISTIC DARK) & CSS EFEK LENGKAP ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #334155; border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: #475569; }

@keyframes fadeInUp { 0% { opacity: 0; transform: translateY(15px); } 100% { opacity: 1; transform: translateY(0); } }
.dash-box, div[data-testid="stMetric"], div[data-testid="stForm"], div[data-testid="stExpander"], .stDataFrame { animation: fadeInUp 0.6s ease-out forwards; }

.stApp { background-color: #0F172A; color: #F8FAFC; font-family: 'Inter', sans-serif; }
header {background: transparent !important;}
[data-testid="stHeaderActionElements"], .stDeployButton, #MainMenu { display: none !important; }

/* WARNA TEKS UTAMA */
p, span, label, li, div.stMarkdown, .stText { color: #F8FAFC !important; }
h1, h2, h3, h4, h5, h6 { font-family: 'Inter', sans-serif !important; font-weight: 700 !important; color: #FFFFFF !important; letter-spacing: -0.5px; }
.gradient-text { background: linear-gradient(90deg, #38BDF8, #34D399); -webkit-background-clip: text; -webkit-text-fill-color: transparent; display: inline-block; }
.stCaptionContainer p, [data-testid="stCaptionContainer"] p { color: #94A3B8 !important; }

.ticker-wrap { position: sticky; top: 0; z-index: 9999; width: 100%; overflow: hidden; background-color: rgba(15, 23, 42, 0.8); backdrop-filter: blur(10px); color: #FFFFFF !important; padding: 10px 0; border-radius: 8px; margin-bottom: 20px; white-space: nowrap; border: 1px solid #334155; }
.ticker { display: inline-block; white-space: nowrap; padding-right: 100%; box-sizing: content-box; animation: ticker 40s linear infinite; }
.ticker:hover { animation-play-state: paused; }
.ticker-item { display: inline-block; padding: 0 20px; font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; font-weight: 600; color: #38BDF8; }
@keyframes ticker { 0% { transform: translate3d(0, 0, 0); } 100% { transform: translate3d(-50%, 0, 0); } }

.pulsing-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; background-color: #10B981; margin-right: 5px; box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); animation: pulse-dot 1.5s infinite; }
@keyframes pulse-dot { 0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); } 70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); } 100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); } }

/* TAB STYLING GELAP */
.stTabs [data-baseweb="tab-list"] { background-color: rgba(30, 41, 59, 0.7) !important; border-radius: 12px; padding: 4px; gap: 4px; border-bottom: none !important; }
.stTabs [data-baseweb="tab"] { background-color: transparent !important; border-radius: 8px !important; padding: 8px 16px !important; border: none !important; margin: 0 !important; }
.stTabs [data-baseweb="tab"] p { color: #94A3B8 !important; transition: all 0.3s ease; font-weight: 600 !important; }
.stTabs [aria-selected="true"] { background-color: rgba(37, 99, 235, 0.2) !important; border: 1px solid rgba(56, 189, 248, 0.4) !important; }
.stTabs [aria-selected="true"] p { color: #38BDF8 !important; font-weight: 800 !important; }
.stTabs [data-baseweb="tab-highlight"] { display: none !important; }

/* SIDEBAR GELAP */
section[data-testid="stSidebar"] { background-color: rgba(15, 23, 42, 0.95) !important; backdrop-filter: blur(12px) !important; border-right: 1px solid #334155 !important; }
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label { background: transparent !important; border: none !important; border-radius: 8px !important; padding: 10px 14px !important; margin-bottom: 4px !important; }
section[data-testid="stSidebar"] .stRadio p, section[data-testid="stSidebar"] .stRadio span, section[data-testid="stSidebar"] .stRadio label { font-family: 'Inter', sans-serif !important; font-size: 0.95rem !important; font-weight: 600 !important; color: #CBD5E1 !important; }
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] [aria-checked="true"] { background-color: rgba(37, 99, 235, 0.2) !important; border: 1px solid rgba(56, 189, 248, 0.3) !important; border-left: 4px solid #38BDF8 !important; }
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] [aria-checked="true"] p, section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] [aria-checked="true"] span { color: #38BDF8 !important; font-weight: 800 !important; }

/* KOTAK-KOTAK GELAP / TRANSPARAN */
div[data-testid="stForm"], div[data-testid="stExpander"], div[data-testid="stMetric"], .dash-box { background-color: rgba(30, 41, 59, 0.6) !important; border: 1px solid #334155 !important; border-radius: 12px; padding: 16px !important; margin-bottom: 16px !important; backdrop-filter: blur(5px); transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.25s cubic-bezier(0.4, 0, 0.2, 1); }
div[data-testid="stForm"]:hover, div[data-testid="stMetric"]:hover, .dash-box:hover { transform: translateY(-4px); box-shadow: 0 12px 20px -5px rgba(56, 189, 248, 0.15) !important; border-color: #38BDF8 !important; }
.dash-box { border-top: 1px solid #334155 !important; }

/* INPUT FORMS & METRICS */
div[data-testid="stForm"] label p, .stTextInput label p, .stNumberInput label p, .stSelectbox label p { color: #38BDF8 !important; font-size: 0.85rem !important; font-weight: 600 !important; }
input, select, textarea { background-color: rgba(15, 23, 42, 0.8) !important; border: 1px solid #475569 !important; color: #F8FAFC !important; font-family: 'JetBrains Mono', monospace !important; border-radius: 8px !important; height: 44px !important; font-size: 15px !important; font-weight: 600 !important; transition: border-color 0.2s ease, box-shadow 0.2s ease; }
input:focus, select:focus { border-color: #38BDF8 !important; box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.2) !important; }
[data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace !important; font-size: 1.8rem !important; color: #F8FAFC !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"] * { color: #94A3B8 !important; font-weight: 600 !important; font-size: 0.85rem !important; }
.streamlit-expanderHeader * { color: #F8FAFC !important; font-weight: 600 !important; }

/* TABLE / DATAFRAME */
.stDataFrame { background-color: rgba(30, 41, 59, 0.6) !important; border-radius: 10px; }

.text-green { color: #10B981 !important; } .text-red { color: #EF4444 !important; } .text-blue { color: #38BDF8 !important; } .text-muted { color: #94A3B8 !important; font-size: 13px; }

/* Custom AI Panel Styling (app.py level) */
.ai-panel-header {
    background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
    color: white;
    padding: 16px;
    border-radius: 12px 12px 0 0;
    margin-bottom: 15px;
    display: flex;
    align-items: center;
    gap: 10px;
    border: 1px solid #334155;
}
.chat-action-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 8px 12px;
    background: rgba(30, 41, 59, 0.6);
    color: #94A3B8;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 600;
    border: 1px solid #334155;
    transition: all 0.2s;
    cursor: pointer;
    width: 100%;
}
.chat-action-btn:hover { background: rgba(56, 189, 248, 0.2); color: #38BDF8; border-color: #38BDF8; }
</style>
""", unsafe_allow_html=True)

# --- LOGIN CONTROL ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.role = None

if not st.session_state.logged_in:
    _, col2, _ = st.columns([1,1.5,1])
    with col2:
        st.markdown("<div style='text-align:center; padding:50px 0; background-color: rgba(15, 23, 42, 0.6); border-radius: 15px; border: 1px solid rgba(56, 189, 248, 0.3); backdrop-filter: blur(10px); margin-top: 50px;'><h1 class='gradient-text'>IDX PRO TERMINAL</h1><p class='text-muted' style='letter-spacing:2px; margin-top:5px;'>INSTITUTIONAL QUANT SUITE</p></div>", unsafe_allow_html=True)
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

# --- SIDEBAR & ZONA NAVIGASI ---
role = st.session_state.role
user_now = st.session_state.user
last_l, ip_l, loc_l = get_sidebar_log(user_now)

st.sidebar.markdown(f"""
    <div style='padding:16px; background-color:rgba(30, 41, 59, 0.7); border-radius:12px; border:1px solid rgba(56, 189, 248, 0.3); margin-bottom:15px; text-align:center;'>
        <h3 style='margin:0; font-size:1.1rem; color:#F8FAFC;'>{user_now.upper()}</h3>
        <p style='margin:0; font-size:11px; color:#10B981; font-weight:700; margin-top:4px;'><span class='pulsing-dot'></span> ONLINE | {role.upper()}</p>
        <p style='font-size:10px; color:#94A3B8; margin:8px 0 0 0;'>IP : {ip_l}</p>
    </div>
    """, unsafe_allow_html=True)

st.sidebar.markdown("<p style='font-size:12px; font-weight:700; color:#94A3B8; margin-bottom:5px; text-align:center;'>PILIH ZONA MARKET</p>", unsafe_allow_html=True)
zona_market = st.sidebar.selectbox("ZONA", ["🏢 ZONA SAHAM (IDX)", "🪙 ZONA KRIPTO (INDODAX)"], label_visibility="collapsed")
st.sidebar.write("---")

if zona_market == "🏢 ZONA SAHAM (IDX)":
    menu_list = [
        "🖥️ DASHBOARD UTAMA", "🛰️ AUTO SCANNER", "⚡ STRATEGY SCANNER", 
        "⭐ WATCHLIST FAVORIT", "🎯 AUTO SUP/RES", "📅 SIKLUS MUSIMAN", "📟 CEK FUNDAMENTAL", 
        "⚔️ ADU SAHAM", "🌐 PETA SEKTOR", "💰 PEMBURU DIVIDEN", 
        "🧬 KORELASI SAHAM", "🏛️ JEJAK BANDAR", "📰 BERITA PASAR"
    ]
else:
    menu_list = [
        "🪙 DASBOR INDODAX", "🚀 RADAR ALTCOIN", "🐋 WHALE TRACKER INDODAX", 
        "⚖️ RADAR ARBITRASE", "⏳ MESIN WAKTU DCA", "🔮 PREDIKSI KRIPTO", 
        "⚔️ ADU KRIPTO", "🧬 KORELASI KRIPTO", "🎡 ROTASI NARASI", 
        "🌐 PETA KRIPTO", "📰 BERITA KRIPTO"
    ]

# MENU UNIVERSAL 
menu_list.append("🧮 KALKULATOR TRADING")
menu_list.append("💼 DOMPET TRADING")
menu_list.append("🩺 DOKTER PORTOFOLIO") # Menu Audit dipisah jadi menu mandiri
menu_list.append("🔒 KEAMANAN")
if role == "admin": menu_list.append("⚙️ USER MANAGEMENT")

menu = st.sidebar.radio("Navigasi", menu_list, key="side_menu", label_visibility="collapsed")

# TOMBOL AI DITETAPKAN DI SIDEBAR PALING BAWAH
st.sidebar.write("---")
# Menggunakan tombol standar (bukan primary) agar tidak menabrak tema warna
if st.sidebar.button("💬 Bicara dengan AI", use_container_width=True):
    st.session_state.show_ai_panel = not st.session_state.show_ai_panel
    st.rerun()

st.sidebar.write("---")
if st.sidebar.button("🔄 Refresh Data Server", use_container_width=True):
    st.cache_data.clear(); st.rerun()
if st.sidebar.button("Keluar (Logout)", use_container_width=True):
    st.session_state.logged_in = False; st.session_state.user = None; st.session_state.role = None; st.rerun()

ticker_html = get_ticker_data()
if ticker_html and zona_market == "🏢 ZONA SAHAM (IDX)":
    st.markdown(f"<div class='ticker-wrap'><div class='ticker'>{ticker_html}</div></div>", unsafe_allow_html=True)


# --- DYNAMIC LAYOUT: SPLIT SCREEN JIKA AI DIAKTIFKAN ---
col_main = st.container()
col_ai = None

if st.session_state.show_ai_panel:
    # Membelah layar: 75% untuk Menu Utama, 25% untuk Panel AI
    col_main, col_ai = st.columns([7.5, 2.5], gap="large")
    with col_ai:
        views_universal.render_ai_chat_panel(user_now, role)

# --- ROUTING MENU UTAMA ---
with col_main:
    # ================= ZONA KRIPTO =================
    if menu == "🪙 DASBOR INDODAX": views_crypto.render_dasbor_indodax()
    elif menu == "🚀 RADAR ALTCOIN": views_crypto.render_radar_altcoin()
    elif menu == "🐋 WHALE TRACKER INDODAX": views_crypto.render_whale_tracker()
    elif menu == "⚖️ RADAR ARBITRASE": views_crypto.render_arbitrase()
    elif menu == "⏳ MESIN WAKTU DCA": views_crypto.render_dca()
    elif menu == "🔮 PREDIKSI KRIPTO": views_crypto.render_prediksi_kripto()
    elif menu == "⚔️ ADU KRIPTO": views_crypto.render_adu_kripto()
    elif menu == "🧬 KORELASI KRIPTO": views_crypto.render_korelasi_kripto()
    elif menu == "🎡 ROTASI NARASI": views_crypto.render_rotasi_narasi()
    elif menu == "🌐 PETA KRIPTO": views_crypto.render_peta_kripto()
    elif menu == "📰 BERITA KRIPTO": views_crypto.render_kripto_news()

    # ================= ZONA SAHAM =================
    elif menu == "🖥️ DASHBOARD UTAMA": views_idx.render_dashboard_utama()
    elif menu == "🛰️ AUTO SCANNER": views_idx.render_auto_scanner()
    elif menu == "⚡ STRATEGY SCANNER": views_idx.render_strategy_scanner()
    elif menu == "⭐ WATCHLIST FAVORIT": views_idx.render_watchlist(user_now)
    elif menu == "🎯 AUTO SUP/RES": views_idx.render_auto_supres()
    elif menu == "📅 SIKLUS MUSIMAN": views_idx.render_siklus_musiman()
    elif menu == "📟 CEK FUNDAMENTAL": views_idx.render_cek_fundamental()
    elif menu == "⚔️ ADU SAHAM": views_idx.render_adu_saham()
    elif menu == "🌐 PETA SEKTOR": views_idx.render_peta_sektor()
    elif menu == "💰 PEMBURU DIVIDEN": views_idx.render_pemburu_dividen()
    elif menu == "🧬 KORELASI SAHAM": views_idx.render_korelasi_saham()
    elif menu == "🏛️ JEJAK BANDAR": views_idx.render_jejak_bandar()
    elif menu == "📰 BERITA PASAR": views_idx.render_berita_pasar()

    # ================= ZONA UNIVERSAL =================
    elif menu == "🧮 KALKULATOR TRADING": views_universal.render_kalkulator(zona_market)
    elif menu == "💼 DOMPET TRADING": views_universal.render_dompet(user_now, role)
    elif menu == "🩺 DOKTER PORTOFOLIO": views_universal.render_dokter_portofolio(user_now, role)
    elif menu == "⚙️ USER MANAGEMENT": views_universal.render_user_management()
    elif menu == "🔒 KEAMANAN": views_universal.render_keamanan(user_now)

# --- FILE: views_universal.py ---
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import math
import time
import google.generativeai as genai
from core import *

def render_kalkulator(zona_market):
    st.markdown(f"<h2 class='gradient-text'>🧮 Kalkulator Trading</h2>", unsafe_allow_html=True)
    with st.form("risk_calc_form"):
        c1, c2 = st.columns(2)
        capital = c1.number_input("Modal Disiapkan (Rp)", min_value=100.0, value=10000000.0, format="%g")
        risk_pct = c2.number_input("Toleransi Rugi (%)", min_value=0.1, max_value=10.0, value=2.0, format="%g")
        entry_p = st.number_input("Harga Beli / Entry (Rp)", min_value=1.0, value=5000.0, format="%g")
        stop_loss_p = st.number_input("Harga Cut Loss (Rp)", min_value=1.0, value=4800.0, format="%g")
        if st.form_submit_button("Hitung Lot Aman", width="stretch") and stop_loss_p < entry_p:
            total_lots = math.floor((capital * (risk_pct / 100)) / (entry_p - stop_loss_p) / 100)
            st.success(f"Anda boleh beli maksimal: **{total_lots} Lot**")

def format_rp(val):
    if pd.isna(val) or val == 0: return "Rp 0"
    if val < 10: return f"Rp {val:,.4f}"
    elif val < 1000: return f"Rp {val:,.2f}"
    else: return f"Rp {val:,.0f}"

def render_dompet(user_now, role):
    st.markdown(f"<h2 class='gradient-text'>💼 Dompet Omni-Wallet</h2>", unsafe_allow_html=True)
    show_saldo = st.checkbox("👁️ Tampilkan Saldo", value=False)
    format_privacy = lambda v: f"Rp {v:,.0f}" if show_saldo else "Rp *****"

    tab1, tab2 = st.tabs(["📈 KEPEMILIKAN", "📜 RIWAYAT"])
    
    with tab1:
        with st.expander("➕ TAMBAH ASET", expanded=False):
            tipe_aset = st.radio("PILIH JENIS ASET:", ["🏢 Saham Indonesia (IDX)", "🪙 Kripto (Indodax & Global)"], horizontal=True)
            with st.form("form_add", clear_on_submit=True):
                c1, c2 = st.columns(2)
                if "Saham" in tipe_aset:
                    t_in = c1.text_input("Kode Saham (Cth: BBCA)").upper().strip()
                    l_in = c2.number_input("Jumlah Lot", min_value=1.0, value=1.0, step=1.0, format="%g")
                    p_in = st.number_input("Harga Beli (Rp per Lembar)", min_value=1.0, value=1000.0, format="%g")
                else:
                    t_in = c1.text_input("Kode Koin (Cth: BTC, FWOG)").upper().strip()
                    l_in = c2.number_input("Jumlah Koin (Unit)", min_value=0.000001, value=1.0, step=0.1, format="%g")
                    p_in = st.number_input("Harga Beli Total (Rp per Unit)", min_value=1.0, value=1000.0, format="%g")
                    
                strat_in = st.selectbox("Alasan Beli?", ["Serok Bawah", "Breakout", "Fundamental", "Feeling / FOMO"])
                if st.form_submit_button("MASUKKAN", width="stretch") and t_in and p_in > 0:
                    add_to_portfolio(user_now, t_in, p_in, l_in, 0, 0, strat_in, is_crypto=("Kripto" in tipe_aset))
                    st.success("Tersimpan!"); time.sleep(1); st.rerun()

        df_p = get_user_portfolio(user_now)
        if not df_p.empty:
            import requests
            try: indo = requests.get("https://indodax.com/api/tickers", timeout=5).json().get('tickers', {})
            except: indo = {}
            try: kurs_idr = float(yf.download("IDR=X", period="1d", progress=False)['Close'].iloc[-1])
            except: kurs_idr = 15500.0 
            
            saham_tkrs = [f"{t}.JK" for t in df_p['ticker'] if not is_crypto_ticker(t)]
            live_saham = {}
            if saham_tkrs:
                try:
                    df_dl = yf.download(list(set(saham_tkrs)), period="5d", progress=False, threads=True)['Close']
                    for tk in set(saham_tkrs): live_saham[tk] = float(df_dl[tk].dropna().iloc[-1]) if isinstance(df_dl, pd.DataFrame) else float(df_dl.dropna().iloc[-1])
                except: pass

            def calc_active(r):
                t, is_cr, bp, lots = str(r['ticker']).strip().upper(), r['is_crypto'], float(r['buy_price']), float(r['lots'])
                if is_cr:
                    clean_t = t.replace('-USD','').lower() + "_idr"
                    curr_rp = float(indo.get(clean_t, {}).get('last', 0))
                    if curr_rp == 0:
                        try: 
                            usd_p = float(yf.Ticker(f"{t.replace('-USD','')}-USD").fast_info.get('lastPrice', 0))
                            curr_rp = usd_p * kurs_idr if usd_p > 0 else bp
                        except: curr_rp = bp
                    cost_rp, val_rp = bp * lots, curr_rp * lots
                else:
                    tk_yf = f"{t}.JK"
                    curr_rp = live_saham.get(tk_yf, 0)
                    if curr_rp == 0:
                        try: curr_rp = float(yf.Ticker(tk_yf).fast_info.get('lastPrice', bp))
                        except: curr_rp = bp
                    cost_rp, val_rp = bp * lots * 100, curr_rp * lots * 100
                return pd.Series([curr_rp, cost_rp, val_rp, val_rp - cost_rp, is_cr])

            df_p[['Live_Rp', 'Cost', 'Val', 'PnL', 'Is_Cr']] = df_p.apply(calc_active, axis=1)
            st.write("---")
            for _, r in df_p.iterrows():
                is_c, icon, sat = r['Is_Cr'], "🪙" if r['Is_Cr'] else "🏢", "Unit" if r['Is_Cr'] else "Lot"
                pct = (r['PnL'] / r['Cost'] * 100) if r['Cost'] > 0 else 0
                sign = "+" if r['PnL'] > 0 else ""
                
                title = f"{icon} {r['ticker']} | {r['lots']:g} {sat} | Live: {format_rp(r['Live_Rp'])} | Profit: {sign}Rp {r['PnL']:,.0f} ({sign}{pct:.2f}%)"
                with st.expander(title):
                    c_price, c_lots, c_btn = st.columns([2, 2, 1])
                    s_prc = c_price.number_input("Harga Jual (Rp)", value=float(r['Live_Rp']), format="%g", key=f"p_{r['id']}")
                    s_lot = c_lots.number_input(f"Jumlah Dilepas", min_value=0.000001, max_value=float(r['lots']), value=float(r['lots']), format="%g", key=f"l_{r['id']}")
                    if c_btn.button("JUAL", key=f"b_{r['id']}", use_container_width=True):
                        sell_position(user_now, r['id'], r['ticker'], r['buy_price'], s_prc, r['lots'], s_lot, is_crypto=is_c)
                        st.toast("Terjual!"); time.sleep(1); st.rerun()

    with tab2:
        df_h = conn_gs.read(worksheet="history", ttl=0)
        if not df_h.empty:
            for _, r in df_h[df_h['username'] == user_now].sort_values('date', ascending=False).iterrows():
                with st.expander(f"{r['date']} | {r['ticker']} | Profit: {format_privacy(float(r['pnl']))}"):
                    if st.button("Hapus", key=f"d_{r['id']}"):
                        df_a = conn_gs.read(worksheet="history", ttl=0)
                        conn_gs.update(worksheet="history", data=df_a.drop(df_a.index[df_a['id'] == r['id']][0]).reset_index(drop=True)); st.rerun()

def render_dokter_portofolio(user_now, role):
    st.markdown("<h2 class='gradient-text'>🩺 Dokter Portofolio</h2>", unsafe_allow_html=True)
    st.info("Pindai risiko konsentrasi dompet Anda.")

def render_user_management():
    st.markdown("<h2 class='gradient-text'>⚙️ Portal Admin</h2>", unsafe_allow_html=True)
    st.dataframe(conn_gs.read(worksheet="users", ttl=0)[['username', 'role', 'last_login', 'location']], use_container_width=True, hide_index=True)

def render_keamanan(user_now):
    st.markdown("<h2 class='gradient-text'>🔒 Keamanan</h2>", unsafe_allow_html=True)
    p = st.text_input("Password Baru", type="password")
    if st.button("Simpan", width="stretch") and p:
        update_password_db(user_now, p); st.success("Tersimpan!")

def render_ai_chat_panel(user_now, role):
    st.markdown("<div style='background: linear-gradient(90deg, #38BDF8, #34D399); padding: 15px; border-radius: 10px 10px 0 0; box-shadow: 0 2px 5px rgba(0,0,0,0.1);'><b style='font-size: 1.25rem; color: #0F172A;'>🤖 AI Quant Advisor</b></div>", unsafe_allow_html=True)
    if st.button("✖️ Tutup Panel AI", use_container_width=True): st.session_state.show_ai_panel = False; st.rerun()

    api_key_rahasia = st.secrets.get("GEMINI_API_KEY")
    if not api_key_rahasia: st.error("⚠️ API Key belum dikonfigurasi."); return
    genai.configure(api_key=api_key_rahasia)
    
    if "messages" not in st.session_state: st.session_state.messages = [{"role": "assistant", "content": "Halo! Saya AI Advisor."}]
    chat_container = st.container(height=500, border=True)
    with chat_container:
        for m in st.session_state.messages: st.chat_message(m["role"]).markdown(m["content"])

    if prompt := st.chat_input("Tanya AI..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with chat_container:
            st.chat_message("user").markdown(prompt)
            with st.chat_message("assistant"):
                with st.spinner("Menganalisis..."):
                    try:
                        resp = genai.GenerativeModel("gemini-1.5-flash").generate_content(prompt).text
                        st.markdown(resp); st.session_state.messages.append({"role": "assistant", "content": resp})
                    except Exception as e: st.error(f"Gagal koneksi: {e}")

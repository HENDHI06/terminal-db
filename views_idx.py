# --- FILE: views_idx.py ---
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import yfinance as yf
import requests
import feedparser
import time
from datetime import datetime
from core import *

def render_dashboard_utama():
    st.markdown(f"<h2 class='gradient-text'>Dashboard Saham IDX</h2>", unsafe_allow_html=True)
    try:
        ihsg = yf.download("^JKSE", period="5d", progress=False)['Close'].dropna()
        l, p = float(ihsg.iloc[-1]), float(ihsg.iloc[-2])
        st.markdown(f"<div class='dash-box'><p>IHSG (Indeks Harga Saham Gabungan)</p><h2>{l:,.2f} <span style='color:{'#34D399' if l>p else '#EF4444'};'>({(l-p)/p*100:+.2f}%)</span></h2></div>", unsafe_allow_html=True)
    except: pass

def render_stock_chart():
    st.markdown("<h2 class='gradient-text'>📈 Interaktif Stock Chart</h2>", unsafe_allow_html=True)
    tk = st.text_input("Masukkan Kode Saham (Contoh: BBCA)", "BBCA").upper().strip()
    if st.button("Tampilkan Grafik", width="stretch"):
        with st.spinner("Memuat grafik profesional..."):
            try:
                df = yf.download(f"{tk}.JK", period="1y", progress=False).dropna()
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                df['MA20'] = df['Close'].rolling(20).mean()
                df['MA50'] = df['Close'].rolling(50).mean()
                
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Candle'), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#38BDF8', width=1.5), name='MA 20'), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['MA50'], line=dict(color='#FBBF24', width=1.5), name='MA 50'), row=1, col=1)
                fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=['#34D399' if row['Close'] >= row['Open'] else '#EF4444' for _, row in df.iterrows()], name='Volume'), row=2, col=1)
                fig.update_layout(template="plotly_dark", height=600, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)
            except: st.error("Gagal memuat grafik.")

def render_auto_scanner():
    st.markdown("<h2 class='gradient-text'>Auto Scanner AI (VPA & Radar)</h2>", unsafe_allow_html=True)
    if st.button("Mulai Scan", width="stretch"):
        res = run_scan_accurate(load_tickers(), "Santai", is_crypto=False)
        if not res.empty: 
            st.session_state.results_saham = res
            st.rerun()

    if 'results_saham' in st.session_state and not st.session_state.results_saham.empty:
        df = st.session_state.results_saham
        tab1, tab3 = st.tabs(["📱 RINGKASAN", "📊 DATA LENGKAP"])
        with tab1: draw_mobile_cards(df)
        with tab3:
            # FIX: Menggunakan map() untuk versi Pandas terbaru!
            def highlight_cols(s):
                if s.name == 'CHG%': return ['background-color: rgba(52, 211, 153, 0.2); color: #34D399; font-weight:bold;' if pd.to_numeric(v, errors='coerce') > 0 else 'background-color: rgba(239, 68, 68, 0.2); color: #EF4444; font-weight:bold;' for v in s]
                return ['' for _ in s]
            fmt = {'LAST': 'Rp {:,.0f}', 'CHG%': '{:.2f}%', 'VAL(M)': '{:,.1f} M', 'ENTRY': 'Rp {:,.0f}', 'TP 1': 'Rp {:,.0f}', 'TP 2': 'Rp {:,.0f}', 'EXIT/CL': 'Rp {:,.0f}'}
            styled_df = df.drop(columns=['FULL', 'SCORE_MOM', 'SCORE_BNDR', 'SCORE_TRND', 'SCORE_VOL'], errors='ignore').style.format(fmt).map(style_dataframe).apply(highlight_cols)
            st.dataframe(styled_df, use_container_width=True, hide_index=True)

def render_strategy_scanner():
    st.markdown("<h2 class='gradient-text'>Strategy Scanner (Crossover)</h2>", unsafe_allow_html=True)
    if st.button("Cari Sinyal Golden Cross", width="stretch"):
        with st.spinner("Menganalisis Moving Average..."):
            res = get_trend_signals(load_tickers()[:50]) # Ambil 50 saham paling likuid agar cepat
            if res:
                for r in res: st.markdown(f"<div class='dash-box'><span class='badge-green'>{r['status']}</span><br>Saham: <b>{r['ticker']}</b> | Harga: Rp {r['price']:,.0f}</div>", unsafe_allow_html=True)
            else: st.info("Belum ada perpotongan hari ini.")

def render_whale_alert():
    st.markdown("<h2 class='gradient-text'>🐋 Whale Alert (Volume Spike)</h2>", unsafe_allow_html=True)
    st.info("Mendeteksi aktivitas akumulasi paus (Bandar) melalui anomali Volume Transaksi yang melonjak ratusan persen dari rata-rata harian.")
    
    if st.button("Pindai Anomali Volume (Whale Scanner)", width="stretch"):
        with st.spinner("Mencari anomali volume di ratusan emiten (Proses ini butuh waktu)..."):
            tickers = load_tickers()[:100] # Batasi top 100 agar server tidak timeout
            alerts = []
            try:
                data = yf.download(tickers, period="20d", interval="1d", group_by="ticker", progress=False)
                for t in tickers:
                    try:
                        df = data[t].copy() if len(tickers) > 1 else data.copy()
                        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                        df = df.dropna()
                        if len(df) < 10: continue
                        
                        vol_today = float(df['Volume'].iloc[-1])
                        vol_avg = float(df['Volume'].tail(15).mean())
                        if vol_avg == 0: continue
                        
                        spike_pct = (vol_today / vol_avg) * 100
                        if spike_pct > 250: # Trigger jika volume meledak lebih dari 2.5x lipat
                            alerts.append({
                                "EMITEN": t.replace(".JK", ""),
                                "HARGA (Rp)": float(df['Close'].iloc[-1]),
                                "VOL HARI INI": vol_today,
                                "RATA-RATA VOL": vol_avg,
                                "LONJAKAN (%)": spike_pct
                            })
                    except: pass
                    
                if alerts:
                    st.success(f"🚨 ALERT! Terdeteksi {len(alerts)} emiten dengan injeksi dana masif hari ini.")
                    df_alert = pd.DataFrame(alerts).sort_values("LONJAKAN (%)", ascending=False)
                    df_alert['VOL HARI INI'] = df_alert['VOL HARI INI'].apply(lambda x: f"{x:,.0f}")
                    df_alert['RATA-RATA VOL'] = df_alert['RATA-RATA VOL'].apply(lambda x: f"{x:,.0f}")
                    df_alert['LONJAKAN (%)'] = df_alert['LONJAKAN (%)'].apply(lambda x: f"🔥 {x:,.0f}%")
                    st.dataframe(df_alert, hide_index=True, use_container_width=True)
                else:
                    st.warning("Belum ada pergerakan Whale ekstrem hari ini.")
            except: st.error("Koneksi data terputus.")

def render_pergerakan_asing():
    st.markdown("<h2 class='gradient-text'>🌍 Pergerakan Asing (Foreign Flow Proxy)</h2>", unsafe_allow_html=True)
    st.info("Estimasi arus keluar/masuk dana asing berbasis logika Chaikin Money Flow (CMF) pada saham-saham Blue Chips.")
    
    with st.spinner("Melacak distribusi asing..."):
        big_caps = ["BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "ASII.JK", "TLKM.JK", "GOTO.JK"]
        try:
            flow_data = yf.download(big_caps, period="1mo", interval="1d", progress=False)
            if isinstance(flow_data.columns, pd.MultiIndex): flow_data.columns = flow_data.columns.get_level_values(0)
            
            results = []
            for tk in big_caps:
                try:
                    df = pd.DataFrame({'High': flow_data['High'][tk], 'Low': flow_data['Low'][tk], 'Close': flow_data['Close'][tk], 'Volume': flow_data['Volume'][tk]}).dropna()
                    if len(df) > 20:
                        mult = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) / (df['High'] - df['Low'] + 1e-9)
                        cmf = float(((mult * df['Volume']).rolling(20).sum() / df['Volume'].rolling(20).sum()).dropna().iloc[-1])
                        
                        status = "🟢 AKUMULASI (Asing Masuk)" if cmf > 0.05 else "🔴 DISTRIBUSI (Asing Keluar)" if cmf < -0.05 else "⚪ NETRAL"
                        results.append({"Saham": tk.replace(".JK", ""), "Skor Aliran": f"{cmf:+.2f}", "Status": status})
                except: pass
            
            if results:
                st.dataframe(pd.DataFrame(results), hide_index=True, use_container_width=True)
        except: st.error("Gagal menarik data pergerakan asing.")

def render_broker_flow():
    st.markdown("<h2 class='gradient-text'>👥 Broker Flow & Pemegang Saham</h2>", unsafe_allow_html=True)
    st.error("🔒 **AKSES TERKUNCI (BUTUH API PREMIUM)**")
    st.markdown("""
    <div class='dash-box' style='background-color: rgba(30, 41, 59, 0.5); opacity: 0.7;'>
        <h4 style='color: #94A3B8;'>Rekapitulasi Broker Harian (Simulasi)</h4>
        <table style='width:100%; color: #94A3B8; text-align: left;'>
            <tr style='border-bottom: 1px solid #334155;'><th>Broker</th><th>Tipe</th><th>Aksi</th><th>Nilai (Rp)</th></tr>
            <tr><td>CP</td><td>DOMESTIC</td><td>🟢 BUY</td><td>13.9 B</td></tr>
            <tr><td>AK</td><td>FOREIGN</td><td>🔴 SELL</td><td>12.7 B</td></tr>
            <tr><td>CC</td><td>DOMESTIC</td><td>🟢 BUY</td><td>12.3 B</td></tr>
        </table>
        <br>
        <p><i>Data Bandarmologi riil (Kode Broker, Tipe Asing/Lokal, Kepemilikan 1%) merupakan data privat yang tidak disediakan oleh Yahoo Finance. Anda perlu mengintegrasikan layanan API Pihak Ketiga (Bursa Efek Indonesia / Layanan Data Feed Berbayar) untuk menghidupkan menu ini.</i></p>
    </div>
    """, unsafe_allow_html=True)

def render_watchlist(user_now):
    st.markdown(f"<h2 class='gradient-text'>Watchlist Pribadi</h2>", unsafe_allow_html=True)
    my_wl = get_watchlist(user_now)
    c_add, c_del = st.columns(2)
    with c_add:
        new_wl = st.text_input("Tambah Kode Saham").upper()
        if st.button("Simpan Saham", use_container_width=True) and new_wl: add_watchlist(user_now, f"{new_wl}.JK"); st.rerun()
    with c_del:
        if my_wl:
            del_wl = st.selectbox("Hapus Daftar", [t.replace(".JK","") for t in my_wl])
            if st.button("Hapus Saham", use_container_width=True): remove_watchlist(user_now, f"{del_wl}.JK"); st.rerun()

def render_auto_supres():
    st.markdown(f"<h2 class='gradient-text'>Auto Support & Resistance</h2>", unsafe_allow_html=True)
    with st.form("f_pivot"):
        tk_pivot = st.text_input("Masukkan Kode Saham", value="BBRI").upper().strip()
        if st.form_submit_button("Analisis Batas Harga", width="stretch"):
            with st.spinner("Menghitung kalkulasi..."):
                try:
                    df_piv = yf.download(f"{tk_pivot}.JK", period="1mo", interval="1d", progress=False).dropna()
                    if not df_piv.empty:
                        if isinstance(df_piv.columns, pd.MultiIndex): df_piv.columns = df_piv.columns.get_level_values(0)
                        pivot = (float(df_piv['High'][-20:].max()) + float(df_piv['Low'][-20:].min()) + float(df_piv['Close'].iloc[-1])) / 3
                        st.metric("🔵 TITIK PIVOT (Garis Aman)", f"Rp {pivot:,.0f}")
                except: st.error("Data gagal ditarik.")

def render_siklus_musiman():
    st.markdown("<h2 class='gradient-text'>Siklus Musiman</h2>", unsafe_allow_html=True)
    st.info("Modul ini sedang disempurnakan. Anda bisa mengakses Stock Chart atau Auto Scanner untuk analisis visual lainnya.")

def render_cek_fundamental():
    st.markdown(f"<h2 class='gradient-text'>Cek Laporan Fundamental</h2>", unsafe_allow_html=True)
    target_f = st.text_input("Ketik Kode Saham", value="BBCA").upper().strip()
    if st.button("Periksa Emiten", width="stretch"):
        info = yf.Ticker(f"{target_f}.JK").info
        c1, c2, c3 = st.columns(3)
        c1.metric("P/E RATIO", f"{info.get('trailingPE', 0):,.2f}x")
        c2.metric("PBV RATIO", f"{info.get('priceToBook', 0):,.2f}x")
        c3.metric("ROE", f"{(info.get('returnOnEquity', 0) or 0)*100:.2f}%")

def render_adu_saham():
    st.markdown(f"<h2 class='gradient-text'>Adu Saham</h2>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: tk1 = st.text_input("Saham 1", value="BBCA").upper().strip()
    with c2: tk2 = st.text_input("Saham 2", value="BBRI").upper().strip()
    if st.button("Bandingkan Emiten", width="stretch"):
        i1, i2 = yf.Ticker(f"{tk1}.JK").info, yf.Ticker(f"{tk2}.JK").info
        st.table(pd.DataFrame({"METRIK": ["P/E Ratio", "PBV Ratio"], tk1: [f"{i1.get('trailingPE',0):.2f}x", f"{i1.get('priceToBook',0):.2f}x"], tk2: [f"{i2.get('trailingPE',0):.2f}x", f"{i2.get('priceToBook',0):.2f}x"]}).set_index("METRIK"))

def render_peta_sektor():
    st.markdown(f"<h2 class='gradient-text'>Peta Sektor Industri</h2>", unsafe_allow_html=True)
    st.info("Peta Sektor RRG masih dalam tahap sinkronisasi data.")

def render_pemburu_dividen():
    st.markdown(f"<h2 class='gradient-text'>Pemburu Dividen</h2>", unsafe_allow_html=True)
    div_tk = st.text_input("Ketik Kode Saham", value="ITMG").upper().strip()
    if st.button("Lacak Dividen", width="stretch"):
        st.metric("YIELD", f"{(yf.Ticker(f'{div_tk}.JK').info.get('dividendYield', 0) or 0) * 100:.2f}%")

def render_korelasi_saham():
    st.markdown(f"<h2 class='gradient-text'>Korelasi Silang Saham</h2>", unsafe_allow_html=True)
    st.info("Gunakan formasi saham andalan Anda di Watchlist.")

def render_jejak_bandar():
    st.markdown(f"<h2 class='gradient-text'>Jejak Institusi & Bandar</h2>", unsafe_allow_html=True)
    st.info("Gunakan tab Pergerakan Asing atau Whale Alert di sidebar untuk melihat aliran dana masif.")

def render_berita_pasar():
    st.markdown(f"<h2 class='gradient-text'>Financial Intelligence Center</h2>", unsafe_allow_html=True)
    feed = feedparser.parse(requests.get("https://news.google.com/rss/search?q=saham+indonesia+ihsg&hl=id&gl=ID&ceid=ID:id", headers={'User-Agent': 'Mozilla/5.0'}).content)
    for entry in feed.entries[:8]: st.markdown(f"<div class='dash-box'><a href='{entry.link}' target='_blank' style='color:#38BDF8; font-weight:600;'>{entry.title}</a></div>", unsafe_allow_html=True)

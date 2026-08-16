# views_idx.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import yfinance as yf
import math
import requests
import feedparser
import time
from time import mktime
from datetime import datetime
import pytz
from core import *

def render_dashboard_utama():
    st.markdown(f"<h2 class='gradient-text' style='margin-bottom:5px;'>Ringkasan Pasar & Portofolio</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Membaca Dashboard Seperti Profesional:**
        * **IHSG (Indeks Harga Saham Gabungan):** Ini adalah rapor bursa kita. Jika statusnya `BULLISH 🚀`, artinya aman untuk membeli saham. Jika `BEARISH ⚠️`, lebih baik simpan uang tunai (*cash*).
        * **Market Breadth:** Lihat angka `Naik` vs `Turun`. Walaupun IHSG hijau, tapi kalau saham yang 'Turun' lebih banyak, artinya kenaikan indeks hanya tipuan dari beberapa saham raksasa saja.
        * **Arus Dana Asing (Net Buy/Sell):** Uang asing adalah bensin bursa kita. Selalu trading searah dengan asing. Jika status `NET BUY`, ikutlah masuk pasar.
        * **Fear & Greed:** Beli saat pasar ketakutan (Jarum di area merah / Extreme Fear), dan juallah barang Anda saat pasar sedang serakah (Jarum di area hijau / Extreme Greed).
        * **Top Traded Value:** Ini adalah tempat uang besar (Triliunan) sedang berpesta hari ini. Sangat disarankan *trading* di 3 saham ini karena sangat liquid (gampang masuk dan keluar).
        """)
    st.write("---")
    
    proxy_market = ["BBCA.JK","BBRI.JK","BMRI.JK","BBNI.JK","ASII.JK","TLKM.JK","AMRT.JK","ADRO.JK",
                    "PTBA.JK","ITMG.JK","UNVR.JK","ICBP.JK","INDF.JK","KLBF.JK","PGAS.JK","GOTO.JK",
                    "ARTO.JK","BRPT.JK","MDKA.JK","ANTM.JK","INCO.JK","CPIN.JK","AKRA.JK","MEDC.JK",
                    "HRUM.JK","EXCL.JK","ISAT.JK","INKP.JK","TKIM.JK","PGEO.JK"]
    big_banks = ["BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "TLKM.JK", "ASII.JK"]

    up, down, flat = 0, 0, 0
    try:
        ihsg_data = yf.download("^JKSE", period="10d", interval="1d", progress=False)['Close'].dropna()
        if not ihsg_data.empty and len(ihsg_data) >= 2:
            ihsg_last, ihsg_prev = float(ihsg_data.iloc[-1].item() if isinstance(ihsg_data.iloc[-1], pd.Series) else ihsg_data.iloc[-1]), float(ihsg_data.iloc[-2].item() if isinstance(ihsg_data.iloc[-2], pd.Series) else ihsg_data.iloc[-2])
            ihsg_pct = ((ihsg_last - ihsg_prev) / ihsg_prev) * 100
            ihsg_color = "#16A34A" if ihsg_pct > 0 else "#DC2626"
            ihsg_status = "BULLISH 🚀" if ihsg_pct > 0.5 else ("BEARISH ⚠️" if ihsg_pct < -0.5 else "SIDEWAYS 💤")
            badge_ihsg = "badge-green" if ihsg_pct > 0 else "badge-red" 
            
            st.markdown(f"""<div class='dash-box' style='border-left: 4px solid {ihsg_color}; border-top: 1px solid #E2E8F0 !important; padding: 20px; margin-bottom: 0px !important;'>
                <p class='text-muted' style='margin:0; font-weight:600;'>IHSG (HARGA SAHAM GABUNGAN)</p>
                <h2 style='margin:5px 0; color:{ihsg_color}; font-family:"JetBrains Mono";'>{ihsg_last:,.2f} <span style='font-size:1rem;'>({'+' if ihsg_pct>0 else ''}{ihsg_pct:.2f}%)</span></h2>
                <p style='margin:0; font-size:14px; color:#0F172A;'>Status Pasar Terakhir: <span class='{badge_ihsg}'>{ihsg_status}</span></p>
            </div>""", unsafe_allow_html=True)
            
            try:
                if len(ihsg_data) >= 7:
                    spark_y = ihsg_data.tail(7).values.flatten()
                    spark_x = ihsg_data.tail(7).index
                    fig_spark = go.Figure(go.Scatter(x=spark_x, y=spark_y, mode='lines', line=dict(color=ihsg_color, width=3)))
                    fig_spark.update_layout(height=60, margin=dict(l=0, r=0, t=0, b=0), xaxis=dict(visible=False), yaxis=dict(visible=False), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False, hovermode=False)
                    st.plotly_chart(fig_spark, use_container_width=True, config={'displayModeBar': False})
            except: pass
    except: st.warning("Sedang memproses sambungan IHSG...")

    with st.spinner("Memindai Kesehatan Pasar..."):
        try:
            br_data_full = yf.download(proxy_market, period="10d", interval="1d", progress=False)
            br_data = br_data_full['Close']
            vol_data_today = br_data_full['Volume']
            
            for tk in proxy_market:
                try:
                    tk_data = br_data[tk].dropna()
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

    with st.spinner("Melacak Sentimen dan Asing..."):
        try:
            flow_data = yf.download(big_banks, period="1mo", interval="1d", progress=False)
            if isinstance(flow_data.columns, pd.MultiIndex): flow_data.columns = flow_data.columns.get_level_values(0)
            avg_cmfs = []
            for tk in big_banks:
                try:
                    df_f = pd.DataFrame({'High': flow_data['High'][tk], 'Low': flow_data['Low'][tk], 'Close': flow_data['Close'][tk], 'Volume': flow_data['Volume'][tk]}).dropna()
                    if len(df_f) > 20:
                        mult = ((df_f['Close'] - df_f['Low']) - (df_f['High'] - df_f['Close'])) / (df_f['High'] - df_f['Low'] + 1e-9)
                        cmf_20 = (mult * df_f['Volume']).rolling(20).sum() / df_f['Volume'].rolling(20).sum()
                        cmf_20 = cmf_20.dropna()
                        if not cmf_20.empty: avg_cmfs.append(cmf_20.iloc[-1])
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
                        {'range': [45, 55], 'color': "rgba(56, 189, 248, 0.15)"}, {'range': [55, 75], 'color': "rgba(16, 185, 129, 0.15)"},
                        {'range': [75, 100], 'color': "rgba(5, 150, 105, 0.15)"}],
                }
            ))
            fig_fg.update_layout(height=200, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)")
            
            st.markdown("<div class='dash-box' style='padding:15px; border-top: 1px solid #E2E8F0 !important;'><p class='text-muted' style='margin:0 0 0 0; text-align:center; font-weight:600;'>🌡️ FEAR & GREED SENTIMENT</p>", unsafe_allow_html=True)
            st.plotly_chart(fig_fg, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        except: pass

    st.write("---")
    
    c_vol, c_mov = st.columns(2)
    with c_vol:
        st.markdown("<h3 class='text-blue'>🔥 Top Traded Value (Paling Laris)</h3>", unsafe_allow_html=True)
        with st.spinner("Menghitung perputaran uang terbesar..."):
            try:
                val_list = []
                for tk in proxy_market:
                    try:
                        tk_close = float(br_data[tk].dropna().iloc[-1])
                        tk_vol = float(vol_data_today[tk].dropna().iloc[-1])
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

def render_auto_scanner():
    st.markdown(f"<h2 class='gradient-text'>Auto Scanner AI (VPA & Radar)</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **1. CARA MEMILIH SAHAM (Cari Bintang Utama):**
        * Fokus pada saham dengan **AI_SCORE** paling tinggi.
        * Pilih yang status Bandar-nya **AKUMULASI** (Bandar sedang kumpul barang).
        * Pilih yang **VPA_STATUS** berstatus "NORMAL" atau "VALID BREAKOUT". Hindari "ANOMALI VPA" karena rawan diguyur bandar.
        * Sangat direkomendasikan memilih saham yang memiliki label **🔥 ADA BERITA** (artinya sedang di-goreng sentimen publik).

        **2. CARA EKSEKUSI TRADING PLAN (Beli & Jual):**
        * **ENTRY (Area Beli Aman):** JANGAN kejar harga pucuk (LAST). Lakukan antre beli (*Buy on Weakness*) di angka **ENTRY** agar Anda dapat harga diskon.
        * **TP 1 & TP 2 (Target Jual Untung):** Segera pasang antrean jual otomatis (Take Profit) di angka ini agar tidak keburu turun lagi.
        * **EXIT/CL (Cut Loss):** PENTING! Jika prediksi salah dan harga malah anjlok menembus angka ini, **SEGERA JUAL RUGI** tanpa mikir. Ini akan menyelamatkan uang Anda dari nyangkut parah.
        """)
        
    if 'results_saham' not in st.session_state: st.session_state.results_saham = None
    tickers = load_tickers()
    
    c1, c2, c3 = st.columns([1.5, 1.5, 1])
    with c1: mode_scan = st.radio("SENSITIVITAS:", ["Santai", "Profesional", "Pro"], horizontal=True)
    with c2: filter_sektor = st.selectbox("Filter Sektor Khusus:", ["Semua Sektor", "Financials", "Energy", "Basic Materials", "Consumer Defensive", "Consumer Cyclical", "Technology", "Healthcare", "Industrials"])
    with c3: 
        st.write("##")
        btn_scan = st.button("Mulai Scan Pasar", use_container_width=True)

    if btn_scan:
        res = run_scan_accurate(tickers, mode_scan, is_crypto=False)
        if not res.empty: 
            if filter_sektor != "Semua Sektor":
                res['SEKTOR'] = res['FULL'].apply(get_sector)
                res = res[res['SEKTOR'] == filter_sektor]
            else:
                res['SEKTOR'] = res['FULL'].apply(get_sector)
            st.session_state.results_saham = res
            st.rerun()
        else: st.warning("Scan selesai: Belum ada saham yang momentumnya cukup kuat di kriteria ini.")

    if st.session_state.results_saham is not None and not st.session_state.results_saham.empty:
        df = st.session_state.results_saham
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
            def highlight_cols(s):
                if s.name == 'CHG%': return ['background-color: #D1FAE5; color: #065F46; font-weight:bold;' if pd.to_numeric(v, errors='coerce') > 0 else 'background-color: #FEE2E2; color: #991B1B; font-weight:bold;' for v in s]
                return ['' for _ in s]
                
            format_mapping = {
                'LAST': 'Rp {:,.0f}', 'CHG%': '{:.2f}%', 'VAL(M)': '{:,.1f} M', 'AI_SCORE': '{:.1f}',
                'ENTRY': 'Rp {:,.0f}', 'TP 1': 'Rp {:,.0f}', 'TP 2': 'Rp {:,.0f}', 'EXIT/CL': 'Rp {:,.0f}'
            }
            
            styled_df = df.drop(columns=['FULL', 'SCORE_MOM', 'SCORE_BNDR', 'SCORE_TRND', 'SCORE_VOL'], errors='ignore').style.format(format_mapping).applymap(style_dataframe).apply(highlight_cols)
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            csv = df.drop(columns=['FULL', 'SCORE_MOM', 'SCORE_BNDR', 'SCORE_TRND', 'SCORE_VOL'], errors='ignore').to_csv(index=False).encode('utf-8')
            st.download_button("💾 Download Hasil Scan (CSV)", csv, f"scanner_results_{datetime.now(pytz.timezone('Asia/Jakarta')).strftime('%d%m%Y')}.csv", "text/csv", use_container_width=True)
            
        with tab4:
            c_sel, c_rad = st.columns([1, 2])
            with c_sel:
                sel_t = st.selectbox("Pilih Saham untuk Analisis Mendalam:", df['TICKER'].tolist())
                sel_row = df[df['TICKER'] == sel_t].iloc[0]
                full_t = sel_row['FULL']
                st.markdown(f"<div class='dash-box' style='text-align:center;'><h1 class='text-blue' style='margin:0;'>{sel_t}</h1><p class='badge-blue'>Skor Keseluruhan: {sel_row['AI_SCORE']:.1f}</p></div>", unsafe_allow_html=True)
            
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

def render_strategy_scanner():
    st.markdown(f"<h2 class='gradient-text'>Strategy Scanner (Crossover)</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Menggunakan Sinyal Crossover:**
        * Menu ini mendeteksi perubahan tren utama dengan melihat persilangan Moving Average (MA20 dan MA50).
        * 🟢 **Beli (Entry):** Jika statusnya **GOLDEN CROSS**. Artinya tren harga baru saja berbalik dari turun menjadi naik. Sangat aman untuk di-hold mingguan/bulanan.
        * 🔴 **Jual (Exit):** Jika statusnya **DEAD CROSS**. Artinya tren naik sudah patah dan akan terjun bebas. Segera jual atau hindari membeli saham ini.
        """)
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
                    bg_badge = "badge-green" if "Sangat Kuat" in res['status'] or "AKUMULASI" in res['status'] else ("badge-red" if "DISTRIBUSI" in res['status'] else "badge-blue")
                    st.markdown(f"<div class='dash-box' style='border-left: 4px solid {res['color']}; padding: 15px;'><span class='{bg_badge}' style='margin-bottom:8px;'>{res['status']}</span><p style='margin:8px 0 0 0; color:#0F172A;'>Saham: <b style='color:#0F172A; font-size:1.1rem;'>{res['ticker']}</b> | Harga: Rp {res['price']:,.0f}</p></div>", unsafe_allow_html=True)
            else: st.info("Belum ada perpotongan tren yang signifikan hari ini.")

def render_watchlist(user_now):
    st.markdown(f"<h2 class='gradient-text'>Watchlist Pribadi</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Fungsi Laci Saham Pribadi:**
        * Masukkan kode saham andalan Anda di sini (misal: BBCA, AMMN, BREN).
        * Cukup tekan **"Scan Saham Favorit Saya"** setiap malam atau pagi.
        * AI akan memberitahu apakah saham-saham pilihan Anda ini sedang memiliki momentum tarikan bandar hari ini atau malah sedang lesu.
        """)
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
            res_wl = run_scan_accurate(my_wl, "Santai", is_crypto=False)
            if not res_wl.empty: draw_mobile_cards(res_wl)
            else: st.info("Belum ada momentum tarikan pada daftar sahammu.")

def render_auto_supres():
    st.markdown(f"<h2 class='gradient-text'>Auto Support & Resistance</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Titik Pantul Harga (Pivot Strategy):**
        * 🟢 **Beli (ENTRY):** Lakukan pembelian saat "Harga Saat Ini" mendekati atau menyentuh garis **SUPPORT 1** atau **SUPPORT 2**. Ini adalah area lantai di mana harga susah turun lagi.
        * 🔴 **Jual (TAKE PROFIT):** Segera lepas barang (jual) saat harga mendekati **RESISTANCE 1** atau **RESISTANCE 2**. Ini adalah area atap di mana harga biasanya akan membentur dan kembali turun.
        * 🔵 **Titik Pivot:** Ini adalah batas tengah (Garis netral).
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

def render_siklus_musiman():
    st.markdown(f"<h2 class='gradient-text'>Siklus Musiman (Seasonality)</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Mencuri Start dengan Siklus:**
        * Grafik menampilkan persentase kemungkinan (*Win Rate*) saham tersebut naik di bulan-bulan tertentu.
        * **Kapan Beli?** Belilah saham tersebut di akhir bulan atau **1 bulan sebelum** bulan hijau tertingginya. (Contoh: Jika BBCA selalu naik 100% di bulan April, maka belilah BBCA di akhir bulan Maret).
        * Jangan sentuh saham ini di bulan-bulan yang barnya paling pendek/merah.
        """)
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
                    
                    fig_season = px.bar(monthly_stats, x='Bulan', y='Win Rate (%)', color='Win Rate (%)', color_continuous_scale=["#EF4444", "#F8FAFC", "#16A34A"], text_auto='.0f')
                    fig_season.update_layout(template="plotly_white", height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_season, use_container_width=True)
            except: st.error("Data rentang waktu belum mencukupi.")

def render_cek_fundamental():
    st.markdown("""<style>.stMetric {border-left: 4px solid #2563EB !important;}</style>""", unsafe_allow_html=True)
    st.markdown(f"<h2 class='gradient-text'>Cek Laporan Fundamental</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Menggunakan Radar Investor Miliarder:**
        * **Pilih Saham Undervalued:** Fokuslah membeli saham yang status "Benjamin Graham"-nya bertuliskan **MURAH** (Harga berjalan lebih rendah dari Harga Wajar).
        * **Pilih Growth:** Jika Anda mencari saham teknologi/tambang yang sedang ekspansi, pastikan "Peter Lynch" PEG Ratio-nya di bawah angka 1 (**SANGAT MURAH**).
        * **Beli untuk Pensiun (DDM):** Jika Anda ingin makan dari dividen seumur hidup tanpa jual saham, pastikan saham tersebut "LAYAK DITABUNG" di kolom DDM Model.
        """)
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
                
                with c_grah:
                    st.markdown("**1. Benjamin Graham**")
                    st.caption("Fokus: Nilai Aset Laba")
                    graham = math.sqrt(22.5 * eps * bvps) if (eps > 0 and bvps > 0) else 0
                    if graham == 0:
                        st.warning("Data EPS/BVPS minus.")
                    elif current_price < graham: 
                        st.success(f"💡 **MURAH (Undervalued)**\n\nNilai Wajar: Rp {graham:,.0f}")
                    else: 
                        st.error(f"💡 **MAHAL (Overvalued)**\n\nNilai Wajar: Rp {graham:,.0f}")
                
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
                        
                with c_ddm:
                    st.markdown("**3. DDM Model**")
                    st.caption("Fokus: Pasif Income Dividen")
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

def render_adu_saham():
    st.markdown(f"<h2 class='gradient-text'>Adu Saham (Head-to-Head)</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Mencari Pemenang Duel:**
        * Adu 2 saham di industri yang sama (Contoh: BBCA vs BBRI).
        * **Pemenang Sejati:** Pilih saham yang angka **P/E dan PBV-nya LEBIH KECIL** (artinya lebih murah harganya), tapi angka **ROE-nya LEBIH BESAR** (artinya perusahaan tersebut lebih pintar mencetak untung dari uang Anda).
        """)
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

def render_peta_sektor():
    st.markdown(f"<h2 class='gradient-text'>Peta Rotasi Sektor Industri</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        * **Leading (Kanan Atas):** Sektor sedang jadi primadona bandar dan mengalahkan IHSG. (Waktunya Tahan Barang / Hold).
        * **Weakening (Kanan Bawah):** Sektor masih kuat tapi mulai lelah. (Waktunya Take Profit).
        * **Lagging (Kiri Bawah):** Sektor sedang mati atau dihindari. (Waktunya Jauhi / Cut Loss).
        * **Improving (Kiri Atas):** Sektor sedang diakumulasi diam-diam untuk meledak. (Waktunya Cicil Beli).
        """)
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
                    data_full = yf.download(all_tickers, period="5d", interval="1d", progress=False)
                    if isinstance(data_full.columns, pd.MultiIndex):
                        data_close = data_full['Close']
                    else:
                        data_close = data_full
                        
                    for sec_name, t in sectors.items():
                        try:
                            tk_data = data_close[t].dropna()
                            if len(tk_data) >= 2:
                                c_now, c_prev = float(tk_data.iloc[-1]), float(tk_data.iloc[-2])
                                sec_changes = ((c_now - c_prev) / c_prev) * 100
                                sector_data.append({"Sektor": sec_name, "Perubahan (%)": round(sec_changes, 2)})
                        except: pass
                except: pass
                
                if sector_data:
                    df_sec = pd.DataFrame(sector_data).sort_values(by="Perubahan (%)", ascending=False)
                    fig_sec = px.bar(df_sec, x="Sektor", y="Perubahan (%)", color="Perubahan (%)", color_continuous_scale=["#EF4444", "#1E293B", "#10B981"])
                    fig_sec.update_layout(template="plotly_white", height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_sec, use_container_width=True)
                else:
                    st.warning("Gagal menarik data perbandingan sektor dari server. Koneksi sedang terputus.")

    with tab_rrg:
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

def render_pemburu_dividen():
    st.markdown(f"<h2 class='gradient-text'>Pemburu Dividen</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Mencari Saham Pensiun:**
        * Masukkan saham pertambangan/bank besar.
        * Perhatikan angka **PERSENTASE YIELD TAHUNAN**.
        * Jika angkanya **di atas 6%** (Mengalahkan bunga deposito Bank/SBN), saham tersebut sangat bagus untuk ditabung jangka panjang.
        * Cek tabel riwayat di bawahnya. Apakah mereka rutin bagi dividen setiap tahun? Jika banyak bolongnya, lupakan!
        """)
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

def render_korelasi_saham():
    st.markdown(f"<h2 class='gradient-text'>Korelasi Silang Saham</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Mengatur Proteksi Portofolio:**
        * Jangan taruh telur di keranjang yang sama!
        * Di dalam grafik kotak, cari angka korelasinya. Jika **mendekati +1** (warna merah pekat), berarti kedua saham itu bergerak searah. (Jika satu anjlok, yang lain ikut anjlok).
        * Jika angka **mendekati 0 atau Negatif** (warna biru), artinya saham tersebut tahan banting (saling menyeimbangkan). **Belilah saham-saham ini untuk diversifikasi!**
        """)
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

def render_jejak_bandar():
    st.markdown(f"<h2 class='gradient-text'>Jejak Institusi & Bandar</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Membongkar Manipulasi Pasar:**
        * **Tab CMF Arus Dana:** Pantau statusnya. JANGAN beli jika statusnya "DISTRIBUSI BESAR" (Bandar sedang kabur/jualan). Beli HANYA jika tertulis "AKUMULASI BESAR".
        * **Tab VWAP Harga Modal:** Garis VWAP adalah Harga Rata-Rata Bandar. Jika "Harga Saat Ini" ADA DI BAWAH Garis VWAP, berarti saham lagi Diskon di bawah harga bandar. Waktunya SEROK BAWAH!
        * **Tab Divergensi:** Ini untuk mencari cuci piring (manipulasi). Jika Harga Saham Turun TAPI Garis Biru (Akumulasi) Naik, artinya harga sedang ditekan turun secara paksa padahal aslinya bandar sedang kumpul barang (Siap Meledak 🚀).
        """)
        
    tab_cmf, tab_vwap, tab_div = st.tabs(["🌊 CMF ARUS DANA", "🎯 VWAP HARGA MODAL", "🚨 RADAR DIVERGENSI"])
    
    with tab_cmf:
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

def render_berita_pasar():
    st.markdown(f"<h2 class='gradient-text'>Financial Intelligence Center</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Mencari Bensin Market:**
        * Saham sulit terbang tanpa sentimen (berita). Mesin ini menyaring puluhan portal berita keuangan untuk Anda secara otomatis.
        * Carilah berita dengan lencana **POSITIF** (hijau) atau tulisan **🔥 HOT NEWS** (berita belum basi/baru rilis kurang dari 12 jam).
        * Jika saham incaran Anda di Scanner muncul di Tab Corporate Action (jadwal bagi dividen), itu adalah waktu yang tepat untuk melakukan akumulasi pembelian!
        """)
        
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
        with st.spinner("Memindai almanak korporasi..."):
            try:
                feed_corp = feedparser.parse(requests.get("https://news.google.com/rss/search?q=jadwal+dividen+OR+right+issue+OR+cum+date+saham+indonesia&hl=id&gl=ID&ceid=ID:id", headers=headers, timeout=5).content)
                for entry in feed_corp.entries[:10]: 
                    fire_badge = check_if_new(entry.published_parsed if hasattr(entry, 'published_parsed') else None)
                    pub_date = entry.published if hasattr(entry, 'published') else ""
                    st.markdown(f"<div class='dash-box'><div style='display:flex; justify-content:space-between; margin-bottom:8px;'><span class='badge-blue'>📅 INFO CORPORATE ACTION</span><span style='font-size:11px; color:#EF4444; font-weight:700;'>{fire_badge}</span></div><a href='{entry.link}' target='_blank' style='color:#0F172A; text-decoration:none; font-size:1rem; font-weight:600;'>{entry.title}</a><p class='text-muted' style='margin-top:8px; margin-bottom:0;'>⏰ {pub_date}</p></div>", unsafe_allow_html=True)
            except: st.error("Kesalahan jaringan sewaktu meretas kalender bursa.")

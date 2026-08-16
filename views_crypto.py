# views_crypto.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf
import math
import random
import requests
import feedparser
import time
from time import mktime
from datetime import datetime
from core import *

def render_dasbor_indodax():
    st.markdown(f"<h2 class='gradient-text' style='margin-bottom:5px;'>Live Indodax Command Center</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Bermain Kripto Tanpa Bangkrut:**
        * **Top Coins:** Ini adalah harga *live* Bitcoin dan koin utama lain dalam Rupiah (IDR) dari server Indodax.
        * **Fear & Greed Index:** Grafik speedometer ini adalah radar psikologi masa kripto global. Jika jarum di angka 10-25 (Extreme Fear), market sedang panik parah, ini adalah waktu **EMAS untuk memborong**. Jika jarum di atas 75 (Extreme Greed), orang sedang tamak/FOMO, **SEGERA JUAL** barang Anda sebelum dibanting turun.
        * **Top Volume (Whale Radar):** Tabel ini menunjukkan koin apa yang sedang dipompa Triliunan Rupiah oleh Bandar (Paus Kripto) hari ini di Indodax. Ikuti arus uangnya.
        """)
    st.write("---")
    
    with st.spinner("Menghubungkan ke API Indodax..."):
        indo_tickers = get_indodax_tickers()
        if indo_tickers:
            c1, c2, c3, c4 = st.columns(4)
            try:
                btc = indo_tickers.get('btc_idr', {})
                eth = indo_tickers.get('eth_idr', {})
                usdt = indo_tickers.get('usdt_idr', {})
                bnb = indo_tickers.get('bnb_idr', {})
                
                c1.metric("BITCOIN (BTC)", f"Rp {int(btc.get('last', 0)):,.0f}" if btc else "N/A")
                c2.metric("ETHEREUM (ETH)", f"Rp {int(eth.get('last', 0)):,.0f}" if eth else "N/A")
                c3.metric("TETHER (USDT)", f"Rp {int(usdt.get('last', 0)):,.0f}" if usdt else "N/A")
                c4.metric("BINANCE (BNB)", f"Rp {int(bnb.get('last', 0)):,.0f}" if bnb else "N/A")
            except: st.error("Gagal menarik metrik utama.")
            
            st.write("---")
            col_fg, col_vol = st.columns([1, 1.5])
            
            with col_fg:
                st.markdown("<h4 style='text-align:center; color:#2563EB;'>Crypto Fear & Greed Index</h4>", unsafe_allow_html=True)
                fg_val, fg_status = get_crypto_fng()
                if fg_val <= 25: fg_color = "#DC2626"
                elif fg_val <= 45: fg_color = "#F59E0B"
                elif fg_val <= 55: fg_color = "#38BDF8"
                elif fg_val <= 75: fg_color = "#10B981"
                else: fg_color = "#059669"
                
                fig_fg = go.Figure(go.Indicator(
                    mode = "gauge+number", value = fg_val,
                    number = {'font': {'color': fg_color, 'size':40, 'family': 'Inter'}},
                    title = {'text': f"<br><span style='color:{fg_color}; font-size:18px; font-weight:700;'>{fg_status.upper()}</span>", 'font': {'size': 14, 'family': 'Inter'}},
                    gauge = {
                        'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#334155", 'visible': False},
                        'bar': {'color': fg_color, 'thickness': 0.3}, 'bgcolor': "#FFFFFF",
                        'steps': [
                            {'range': [0, 25], 'color': "rgba(239, 68, 68, 0.15)"}, {'range': [25, 45], 'color': "rgba(245, 158, 11, 0.15)"},
                            {'range': [45, 55], 'color': "rgba(56, 189, 248, 0.15)"}, {'range': [55, 75], 'color': "rgba(16, 185, 129, 0.15)"},
                            {'range': [75, 100], 'color': "rgba(5, 150, 105, 0.15)"}],
                    }
                ))
                fig_fg.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_fg, use_container_width=True)
                
            with col_vol:
                st.markdown("<h4 style='text-align:center; color:#2563EB;'>🔥 Top Volume Indodax (24 Jam)</h4>", unsafe_allow_html=True)
                vol_list = []
                for pair, data in indo_tickers.items():
                    if '_idr' in pair:
                        try:
                            coin_name = pair.replace('_idr', '').upper()
                            vol_rp = float(data.get('vol_idr', 0))
                            last_price = float(data.get('last', 0))
                            if vol_rp > 0: vol_list.append({'Koin': coin_name, 'Harga (IDR)': last_price, 'Volume (Rp)': vol_rp})
                        except: pass
                
                if vol_list:
                    df_vol = pd.DataFrame(vol_list).sort_values(by='Volume (Rp)', ascending=False).head(5)
                    for _, row in df_vol.iterrows():
                        st.markdown(f"<div class='dash-box' style='background-color:#F8FAFC; border-left: 4px solid #10B981; padding: 12px;'><b style='font-size:16px; color:#0F172A;'>{row['Koin']}</b> <span style='margin-left:10px; font-weight:600;'>Rp {row['Harga (IDR)']:,.0f}</span> <span class='badge-green' style='float:right;'>Vol: Rp {row['Volume (Rp)']/1e9:,.1f} Miliar</span></div>", unsafe_allow_html=True)
        else: st.warning("Gagal mengambil data Live Indodax. Periksa koneksi internet server.")

def render_radar_altcoin():
    st.markdown(f"<h2 class='gradient-text'>Altcoin Pump Radar (100% Indodax IDR)</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Mencari Koin yang Sedang di-"Pump" (Goreng):**
        * Radar ini memindai seluruh pasangan koin di Indodax secara *Real-Time* dalam Rupiah.
        * Carilah koin dengan **AI_SCORE** tertinggi.
        * **VPA STATUS:** Jika tertulis "🚀 BREAKOUT BESAR", artinya volume transaksi koin tersebut melonjak drastis. Beli di harga **ENTRY (Rp)** dan pasang target jual di **TP 1 / TP 2**.
        """)
        
    c1, c2 = st.columns([2, 1])
    with c1: mode_scan = st.radio("SENSITIVITAS:", ["Santai", "Profesional", "Pro"], horizontal=True)
    with c2: 
        st.write("##")
        btn_scan = st.button("Mulai Scan Indodax Market", use_container_width=True)

    if btn_scan:
        with st.spinner("Memindai seluruh pasar Indodax..."):
            indo_tickers = get_indodax_tickers()
            res_crypto = []
            
            if mode_scan == "Santai": min_vol = 100_000_000
            elif mode_scan == "Profesional": min_vol = 500_000_000
            else: min_vol = 1_000_000_000
            
            for pair, data in indo_tickers.items():
                if pair.endswith('_idr'):
                    try:
                        coin = pair.replace('_idr', '').upper()
                        last_p = float(data.get('last', 0))
                        high_p = float(data.get('high', last_p))
                        low_p = float(data.get('low', last_p))
                        vol_rp = float(data.get('vol_idr', 0))
                        
                        if vol_rp >= min_vol and last_p > 0:
                            chg_pct = ((last_p - low_p) / low_p * 100) if low_p > 0 else 0
                            ai_score = (chg_pct * 0.6) + ((vol_rp / 1e9) * 0.4)
                            
                            vpa_st = "🚀 BREAKOUT BESAR" if last_p >= (high_p * 0.97) else "NORMAL (Searah)"
                            entry_p = last_p * 0.98
                            tp1_p = last_p * 1.05
                            tp2_p = last_p * 1.10
                            cl_p = last_p * 0.95
                            
                            res_crypto.append({
                                "TICKER": coin, "LAST": last_p, "CHG%": chg_pct,
                                "VAL(M)": (vol_rp / 1_000_000), "BANDAR": "AKUMULASI" if chg_pct > 2 else "NETRAL",
                                "VPA_STATUS": vpa_st, "KATALIS": "🚀 INDODAX HOT",
                                "AI_SCORE": ai_score, "ENTRY": entry_p, "TP 1": tp1_p, "TP 2": tp2_p, "EXIT/CL": cl_p
                            })
                    except: pass
            
            if res_crypto:
                df_c = pd.DataFrame(res_crypto).sort_values(by='AI_SCORE', ascending=False)
                st.session_state.res_crypto = df_c
                st.rerun()
            else: st.warning("Belum ada koin di Indodax yang memenuhi kriteria lonjakan volume hari ini.")

    if 'res_crypto' in st.session_state and st.session_state.res_crypto is not None and not st.session_state.res_crypto.empty:
        df = st.session_state.res_crypto
        st.info(f"💡 **Hasil:** Ditemukan **{len(df)} Koin Indodax** yang sedang ramai ditransaksikan.")

        tab1, tab3 = st.tabs(["📱 RINGKASAN SIGNAL", "📊 DATA LENGKAP AI"])
        
        with tab1: draw_mobile_cards(df, is_crypto=True)
            
        with tab3: 
            def highlight_cols(s):
                if s.name == 'CHG%': return ['background-color: #D1FAE5; color: #065F46; font-weight:bold;' if pd.to_numeric(v, errors='coerce') > 0 else 'background-color: #FEE2E2; color: #991B1B; font-weight:bold;' for v in s]
                return ['' for _ in s]
                
            format_mapping = {
                'LAST': 'Rp {:,.0f}', 'CHG%': '{:.2f}%', 'VAL(M)': 'Rp {:,.1f} M', 'AI_SCORE': '{:.1f}',
                'ENTRY': 'Rp {:,.0f}', 'TP 1': 'Rp {:,.0f}', 'TP 2': 'Rp {:,.0f}', 'EXIT/CL': 'Rp {:,.0f}'
            }
            styled_df = df.style.format(format_mapping).applymap(style_dataframe).apply(highlight_cols)
            st.dataframe(styled_df, use_container_width=True, hide_index=True)

def render_whale_tracker():
    st.markdown(f"<h2 class='gradient-text'>Indodax Live Tape & Order Book</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Melacak Pergerakan Paus (Whales) di Indodax:**
        * Sistem ini akan membaca antrean jual-beli (Bid/Offer) secara langsung dari server.
        * **Buku Order (Tembok Bandar):** Lihat Total Antrean. Jika kolom BID jauh lebih besar dari kolom ASK, artinya banyak yang antre beli di bawah (Harga akan susah turun/mantul).
        * **Transaksi Terkini (Tape Reading):** Jika muncul deretan transaksi dengan kolom Tipe "Beli" (Hijau) dalam jumlah Rupiah yang masif beruntun, bersiaplah harga akan meroket (Pump).
        """)

    with st.form("f_whale"):
        pilihan_koin = st.selectbox("Pilih Koin untuk Diintai (Rupiah Market):", ["BTC", "ETH", "USDT", "DOGE", "PEPE", "SOL", "BNB", "XRP", "CEL"])
        btn_whale = st.form_submit_button("Lacak Data Live Indodax", width="stretch")

    if btn_whale:
        pair_id = f"{pilihan_koin.lower()}idr"
        with st.spinner(f"Menyadap server pesanan {pilihan_koin} di Indodax..."):
            depth_data = get_indodax_depth(pair_id)
            trade_data = get_indodax_trades(pair_id)

            if depth_data and trade_data:
                tab_book, tab_tape = st.tabs(["📚 BUKU ORDER (BID/ASK)", "⚡ TRANSAKSI LIVE (TAPE)"])

                with tab_book:
                    c_bid, c_ask = st.columns(2)
                    bids = depth_data.get('buy', [])[:15] 
                    asks = depth_data.get('sell', [])[:15]
                    
                    df_bids = pd.DataFrame(bids, columns=['Harga Antre Beli (Rp)', 'Jumlah Koin'])
                    df_bids['Harga Antre Beli (Rp)'] = pd.to_numeric(df_bids['Harga Antre Beli (Rp)'])
                    df_bids['Jumlah Koin'] = pd.to_numeric(df_bids['Jumlah Koin'])
                    df_bids['Total Nilai (Rp)'] = df_bids['Harga Antre Beli (Rp)'] * df_bids['Jumlah Koin']
                    
                    df_asks = pd.DataFrame(asks, columns=['Harga Antre Jual (Rp)', 'Jumlah Koin'])
                    df_asks['Harga Antre Jual (Rp)'] = pd.to_numeric(df_asks['Harga Antre Jual (Rp)'])
                    df_asks['Jumlah Koin'] = pd.to_numeric(df_asks['Jumlah Koin'])
                    df_asks['Total Nilai (Rp)'] = df_asks['Harga Antre Jual (Rp)'] * df_asks['Jumlah Koin']

                    with c_bid:
                        st.markdown("<h4 style='color:#16A34A; text-align:center;'>🟢 Tembok Pembeli (BID)</h4>", unsafe_allow_html=True)
                        st.dataframe(df_bids.style.format({"Harga Antre Beli (Rp)": "{:,.0f}", "Jumlah Koin": "{:,.4f}", "Total Nilai (Rp)": "{:,.0f}"}), use_container_width=True, hide_index=True)

                    with c_ask:
                        st.markdown("<h4 style='color:#DC2626; text-align:center;'>🔴 Tembok Penjual (ASK)</h4>", unsafe_allow_html=True)
                        st.dataframe(df_asks.style.format({"Harga Antre Jual (Rp)": "{:,.0f}", "Jumlah Koin": "{:,.4f}", "Total Nilai (Rp)": "{:,.0f}"}), use_container_width=True, hide_index=True)
                    
                    total_bid_rp = df_bids['Total Nilai (Rp)'].sum()
                    total_ask_rp = df_asks['Total Nilai (Rp)'].sum()
                    st.markdown("---")
                    st.markdown(f"**Total Nilai Pertahanan (Top 15):** Beli (Bid) **Rp {total_bid_rp:,.0f}** VS Jual (Ask) **Rp {total_ask_rp:,.0f}**")

                with tab_tape:
                    st.markdown("<h4 style='color:#2563EB;'>⚡ Transaksi Tereksekusi (Detik Terakhir)</h4>", unsafe_allow_html=True)
                    trades_list = trade_data[:20] 
                    if trades_list:
                        df_trades = pd.DataFrame(trades_list)
                        df_trades['Tipe'] = df_trades['type'].apply(lambda x: "🟢 BELI" if x == 'buy' else "🔴 JUAL")
                        df_trades['Harga Eksekusi (Rp)'] = pd.to_numeric(df_trades['price'])
                        df_trades['Jumlah Koin'] = pd.to_numeric(df_trades['amount'])
                        df_trades['Total Nilai (Rp)'] = df_trades['Harga Eksekusi (Rp)'] * df_trades['Jumlah Koin']
                        df_trades['Waktu'] = pd.to_datetime(df_trades['date'], unit='s', utc=True).dt.tz_convert('Asia/Jakarta').dt.strftime('%H:%M:%S')
                        
                        df_show = df_trades[['Waktu', 'Tipe', 'Harga Eksekusi (Rp)', 'Jumlah Koin', 'Total Nilai (Rp)']]
                        
                        def highlight_type(s):
                            if s.name == 'Tipe': return ['background-color: #D1FAE5; color: #065F46; font-weight:bold;' if 'BELI' in v else 'background-color: #FEE2E2; color: #991B1B; font-weight:bold;' for v in s]
                            return ['' for _ in s]

                        st.dataframe(df_show.style.format({"Harga Eksekusi (Rp)": "{:,.0f}", "Jumlah Koin": "{:,.4f}", "Total Nilai (Rp)": "{:,.0f}"}).apply(highlight_type), use_container_width=True, hide_index=True)
            else:
                st.error("Gagal menarik data langsung dari Indodax. Coba beberapa saat lagi.")

# --- FITUR BARU 1: RADAR ARBITRASE ---
def render_arbitrase():
    st.markdown(f"<h2 class='gradient-text'>Radar Arbitrase Global vs Lokal</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Mengambil Keuntungan dari Celah Harga:**
        * Fitur ini membandingkan Harga Wajar Koin di pasar Internasional (Yahoo/Binance) dengan Harga di Indodax.
        * Jika muncul status **PREMIUM (Lokal Lebih Mahal)**: Ini adalah kesempatan Emas untuk **JUAL** koin Anda di Indodax, karena harganya sedang tidak wajar mahalnya dibanding harga dunia.
        * Jika muncul status **DISCOUNT (Lokal Lebih Murah)**: Waktunya **BELI** di Indodax karena sedang ada cuci gudang di bawah harga global.
        """)
        
    koin_arb = st.text_input("Ketik Kode Koin (Contoh: BTC, ETH, DOGE)", value="BTC").upper().strip()
    
    if st.button("Pindai Celah Harga", width="stretch"):
        with st.spinner(f"Menganalisis selisih harga {koin_arb} antar benua..."):
            try:
                # Ambil Kurs USD ke IDR hari ini dari Yahoo
                df_kurs = yf.download("IDR=X", period="1d", progress=False)['Close']
                kurs_idr = float(df_kurs.iloc[-1])
                
                # Ambil Harga Koin Global (USD) dari Yahoo
                df_coin_global = yf.download(f"{koin_arb}-USD", period="1d", progress=False)['Close']
                harga_global_usd = float(df_coin_global.iloc[-1])
                harga_global_idr = harga_global_usd * kurs_idr
                
                # Ambil Harga Koin Lokal (IDR) dari Indodax
                indo_tickers = get_indodax_tickers()
                harga_lokal_idr = float(indo_tickers.get(f"{koin_arb.lower()}_idr", {}).get('last', 0))
                
                if harga_lokal_idr == 0:
                    st.error("Koin ini tidak ditemukan di pasar Indodax (Rupiah).")
                else:
                    selisih_persen = ((harga_lokal_idr - harga_global_idr) / harga_global_idr) * 100
                    
                    st.markdown("---")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("🌍 HARGA DUNIA (Konversi)", f"Rp {harga_global_idr:,.0f}", f"$ {harga_global_usd:,.2f}")
                    c2.metric("🇮🇩 HARGA INDODAX", f"Rp {harga_lokal_idr:,.0f}")
                    
                    if selisih_persen > 1.5:
                        status_arb, warna_arb = f"PREMIUM LOKAL (+{selisih_persen:.2f}%)", "#DC2626"
                        saran = "⚠️ Harga Indodax SANGAT MAHAL dibanding harga dunia. Waktunya Jual Cepat (Take Profit)!"
                    elif selisih_persen < -1.5:
                        status_arb, warna_arb = f"DISCOUNT LOKAL ({selisih_persen:.2f}%)", "#16A34A"
                        saran = "✅ Harga Indodax SEDANG DISKON dibanding harga dunia. Waktunya Borong (Serok Bawah)!"
                    else:
                        status_arb, warna_arb = f"HARGA WAJAR ({selisih_persen:+.2f}%)", "#2563EB"
                        saran = "⚖️ Harga Indodax sejalan dengan pasar global. Tidak ada celah arbitrase yang signifikan."
                    
                    c3.metric("CELAH HARGA", f"{selisih_persen:+.2f}%", delta_color="inverse" if selisih_persen > 0 else "normal")
                    
                    st.markdown(f"<div class='dash-box' style='border-left: 5px solid {warna_arb}; text-align:center;'><h3 style='color:{warna_arb}; margin:0;'>{status_arb}</h3><p style='margin-top:10px; font-weight:600;'>{saran}</p></div>", unsafe_allow_html=True)
            except:
                st.error("Koneksi ke data satelit global/lokal gagal. Pastikan simbol koin benar.")

# --- FITUR BARU 2: MESIN WAKTU DCA ---
def render_dca():
    st.markdown(f"<h2 class='gradient-text'>Mesin Waktu DCA Kripto</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Dollar Cost Averaging (Nabung Rutin):**
        * Kripto sangat bergejolak. Cara teraman untuk kaya dari kripto adalah menabung nominal yang sama setiap bulan, berapapun harganya.
        * Mesin ini akan melakukan *backtest* (melihat ke masa lalu). Jika Anda rutin menabung 1 juta Rupiah tiap bulan ke Bitcoin sejak 2 tahun lalu, berapa total kekayaan Anda sekarang?
        """)
        
    with st.form("dca_form"):
        c1, c2, c3 = st.columns(3)
        koin_dca = c1.text_input("Koin Tabungan", value="BTC").upper().strip()
        nominal_dca = c2.number_input("Nabung Per Bulan (Rp)", min_value=10000.0, value=1000000.0, step=100000.0)
        tahun_mulai = c3.selectbox("Sejak Kapan?", ["1 Tahun Lalu", "2 Tahun Lalu", "3 Tahun Lalu", "4 Tahun Lalu"])
        btn_dca = st.form_submit_button("Jalankan Mesin Waktu", width="stretch")
        
    if btn_dca:
        with st.spinner("Memutar kembali waktu untuk perhitungan aset..."):
            try:
                periode = {"1 Tahun Lalu": "1y", "2 Tahun Lalu": "2y", "3 Tahun Lalu": "3y", "4 Tahun Lalu": "4y"}
                
                # Ambil data koin bulanan
                df_hist = yf.download(f"{koin_dca}-USD", period=periode[tahun_mulai], interval="1mo", progress=False)['Close'].dropna()
                
                if len(df_hist) < 12:
                    st.warning("Data koin tidak cukup panjang untuk simulasi ini.")
                else:
                    # Asumsi Kurs Fix agar cepat (bisa diganti dinamis jika perlu)
                    kurs_estimasi = 15500
                    
                    df_dca = pd.DataFrame(df_hist)
                    if isinstance(df_dca.columns, pd.MultiIndex): df_dca.columns = df_dca.columns.get_level_values(0)
                    df_dca.columns = ['Harga_USD']
                    df_dca['Harga_IDR'] = df_dca['Harga_USD'] * kurs_estimasi
                    
                    # Logika DCA
                    total_investasi_rp = 0
                    total_koin_terkumpul = 0
                    nilai_portfolio = []
                    modal_kumulatif = []
                    
                    for harga in df_dca['Harga_IDR']:
                        koin_didapat = nominal_dca / harga
                        total_koin_terkumpul += koin_didapat
                        total_investasi_rp += nominal_dca
                        
                        nilai_portfolio.append(total_koin_terkumpul * harga)
                        modal_kumulatif.append(total_investasi_rp)
                        
                    df_dca['Nilai_Aset_Rp'] = nilai_portfolio
                    df_dca['Modal_Ditanam_Rp'] = modal_kumulatif
                    
                    nilai_akhir = df_dca['Nilai_Aset_Rp'].iloc[-1]
                    persen_cuan = ((nilai_akhir - total_investasi_rp) / total_investasi_rp) * 100
                    
                    st.markdown("---")
                    col1, col2, col3 = st.columns(3)
                    col1.metric("TOTAL UANG DITABUNG", f"Rp {total_investasi_rp:,.0f}")
                    col2.metric(f"TOTAL KOIN ({koin_dca})", f"{total_koin_terkumpul:,.4f} Unit")
                    col3.metric("NILAI ASET SEKARANG", f"Rp {nilai_akhir:,.0f}", f"{persen_cuan:+.2f}%")
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=df_dca.index, y=df_dca['Modal_Ditanam_Rp'], mode='lines', line=dict(color='#64748B', width=2, dash='dash'), name='Modal Ditanam'))
                    fig.add_trace(go.Scatter(x=df_dca.index, y=df_dca['Nilai_Aset_Rp'], mode='lines', line=dict(color='#10B981', width=3), fill='tonexty', fillcolor='rgba(16, 185, 129, 0.2)', name='Nilai Aset Kripto'))
                    fig.update_layout(title="Grafik Pertumbuhan Nabung Rutin", template="plotly_white", height=400, margin=dict(l=0,r=0,t=40,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig, use_container_width=True)
            except:
                st.error("Gagal menarik data masa lalu untuk koin ini.")

def render_prediksi_kripto():
    st.markdown(f"<h2 class='gradient-text'>Pola AI & Proyeksi Kripto</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Membaca Masa Depan Koin Kripto:**
        * Ketik simbol koin yang ingin Anda cek (contoh: BTC, ETH, DOGE, PEPE). Sistem akan mencarinya di Database Global.
        * **Monte Carlo Simulation:** Karena Kripto sangat fluktuatif, AI akan membuat 100 jalur kemungkinan harga 30 hari ke depan. Lihat garis tebal merah (Rata-rata). Jika menjulang naik, Hold koin Anda.
        """)
        
    tab_candle, tab_monte = st.tabs(["🕯️ DETEKSI POLA CANDLE", "🔮 PROYEKSI MONTE CARLO (AI)"])
    
    with tab_candle:
        with st.form("f_candle_cr"):
            c1, c2 = st.columns(2)
            tk_candle = c1.text_input("Ketik Simbol Koin (Contoh: BTC, DOGE)", value="BTC").upper().strip()
            tf_candle = c2.selectbox("Pilih Timeframe (Gambaran Besar)", ["Harian (Daily)", "Mingguan (Weekly)", "Bulanan (Monthly)"])
            btn_candle = st.form_submit_button("Deteksi Pola Sekarang", width="stretch")
            
        if btn_candle:
            with st.spinner("Mendeteksi anatomi grafik koin..."):
                try:
                    full_tk = f"{tk_candle}-USD"
                    tf_map = {"Harian (Daily)": "1d", "Mingguan (Weekly)": "1wk", "Bulanan (Monthly)": "1mo"}
                    p_map_c = {"Harian (Daily)": "2mo", "Mingguan (Weekly)": "6mo", "Bulanan (Monthly)": "2y"}
                    
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
                        if math.isnan(atr): atr = c_c * 0.05
                        
                        target_price = c_c + (2 * atr)
                        stop_loss = c_c - atr
                        
                        if is_bull_engulfing:
                            pola, warna, badge_c = "BULLISH ENGULFING TERDETEKSI", "#16A34A", "badge-green"
                            kesimpulan = "Luar Biasa! Pembeli koin masuk dalam jumlah besar menelan penjualan hari sebelumnya."
                        elif is_hammer:
                            pola, warna, badge_c = "HAMMER (PALU) TERDETEKSI", "#16A34A", "badge-green"
                            kesimpulan = "Bagus! Cukong menahan harga jatuh dan memborong di bawah (Ekor bawah panjang)."
                        elif is_bear_engulfing:
                            pola, warna, badge_c = "BEARISH ENGULFING TERDETEKSI", "#DC2626", "badge-red"
                            kesimpulan = "BAHAYA! Paus (Whales) mulai buang barang besar-besaran."
                        elif is_shooting_star:
                            pola, warna, badge_c = "SHOOTING STAR TERDETEKSI", "#DC2626", "badge-red"
                            kesimpulan = "Hati-hati! Kenaikan harga diguyur oleh penjualan masif di atas."
                        elif is_doji:
                            pola, warna, badge_c = "POLA DOJI TERDETEKSI", "#2563EB", "badge-blue"
                            kesimpulan = "Pasar sedang galau. Kekuatan bull dan bear seimbang."
                            
                        st.markdown(f"<div class='dash-box' style='border-top: 3px solid {warna}; text-align:center;'><br><span class='{badge_c}' style='font-size:1.2rem; padding:8px 16px;'>{pola}</span><p style='font-size:15px; margin-top:15px; color:#0F172A;'>{kesimpulan}</p></div>", unsafe_allow_html=True)
                        
                        if pola != "TIDAK ADA POLA SPESIFIK" and warna == "#16A34A":
                            st.info(f"🎯 **AI Smart Target:** Disarankan Jual Untung di **$ {target_price:,.4f}** dan Cut Loss jika harga turun ke **$ {stop_loss:,.4f}**.")
                        
                        df_chart = df_c_full.tail(20)
                        fig = go.Figure(data=[go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'], name='Candle', increasing_line_color='#16A34A', decreasing_line_color='#DC2626')])
                        
                        if pola != "TIDAK ADA POLA SPESIFIK" and warna == "#16A34A":
                            fig.add_hline(y=target_price, line_dash="dash", line_color="#16A34A", annotation_text="TARGET (TP)")
                            fig.add_hline(y=stop_loss, line_dash="dash", line_color="#DC2626", annotation_text="STOP LOSS")
                            
                        fig.update_layout(template="plotly_white", height=400, margin=dict(l=0,r=0,t=10,b=0), xaxis_rangeslider_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                        st.plotly_chart(fig, use_container_width=True)
                except: st.error("Data koin tidak ditemukan.")

    with tab_monte:
        with st.form("f_mc_cr"):
            tk_mc = st.text_input("Ketik Simbol Koin (Contoh: BTC, PEPE)", value="BTC").upper().strip()
            btn_mc = st.form_submit_button("Mulai Simulasi Proyeksi Kripto", width="stretch")
            
        if btn_mc:
            with st.spinner("Menghitung 100 skenario masa depan koin..."):
                try:
                    df_mc = yf.download(f"{tk_mc}-USD", period="1y", interval="1d", progress=False)['Close'].dropna()
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
                            
                        avg_path = np.mean(paths, axis=0)
                        fig_mc.add_trace(go.Scatter(y=avg_path, mode='lines', line=dict(color='#DC2626', width=3), name='Rata-Rata Proyeksi'))
                        
                        fig_mc.update_layout(title=f"Proyeksi Harga {tk_mc} (30 Hari ke Depan)", template="plotly_white", height=400, margin=dict(l=0,r=0,t=40,b=0))
                        st.plotly_chart(fig_mc, use_container_width=True)
                        
                        final_prices = [p[-1] for p in paths]
                        prob_up = sum([1 for p in final_prices if p > last_price]) / simulations * 100
                        st.info(f"💡 **Kesimpulan AI Kripto:** Berdasarkan perhitungan matematika probabilitas acak, ada **{prob_up:.0f}%** peluang harga koin {tk_mc} 30 Hari lagi akan lebih tinggi dari harga saat ini ($ {last_price:,.4f}).")
                    else: st.warning("Data koin terlalu sedikit untuk disimulasikan.")
                except Exception as e: st.error("Gagal melakukan simulasi kuantitatif kripto.")

def render_adu_kripto():
    st.markdown(f"<h2 class='gradient-text'>Adu Kekuatan Koin (Head-to-Head)</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Mencari Pemenang Duel Koin:**
        * Masukkan dua simbol koin (misal: BTC vs ETH).
        * Perhatikan baris **Tingkat Kenaikan (1 Bulan)**. Koin mana yang naiknya lebih cepat dan stabil?
        * Jika momentum harga koin A sedang hijau/meroket dan koin B memerah, ikut beli koin A.
        """)
    col_in1, col_in2 = st.columns(2)
    with col_in1: tk1 = st.text_input("Koin Pilihan 1 (Contoh: BTC)", value="BTC").upper().strip()
    with col_in2: tk2 = st.text_input("Koin Pilihan 2 (Contoh: ETH)", value="ETH").upper().strip()

    if st.button("Bandingkan Koin", width="stretch"):
        with st.spinner("Membandingkan performa pasar..."):
            try:
                indo_tickers = get_indodax_tickers()
                data1 = indo_tickers.get(f"{tk1.lower()}_idr", {})
                data2 = indo_tickers.get(f"{tk2.lower()}_idr", {})
                
                if data1 and data2:
                    st.markdown(f"<h2 style='text-align:center; color:#2563EB;'>{tk1} <span style='color:#DC2626;'>VS</span> {tk2}</h2>", unsafe_allow_html=True)
                    
                    last1, high1, low1 = float(data1.get('last',0)), float(data1.get('high',0)), float(data1.get('low',0))
                    last2, high2, low2 = float(data2.get('last',0)), float(data2.get('high',0)), float(data2.get('low',0))
                    
                    chg1 = ((last1 - low1) / low1 * 100) if low1 > 0 else 0
                    chg2 = ((last2 - low2) / low2 * 100) if low2 > 0 else 0
                    
                    df_compare = pd.DataFrame({
                        "METRIK ANALISIS": ["Harga Terakhir (Rp)", "Harga Tertinggi 24 Jam (Rp)", "Tingkat Kenaikan (24 Jam)", "Total Volume (Rp)"],
                        tk1: [format_rupiah_bersih(last1), format_rupiah_bersih(high1), f"{chg1:+.2f}%", f"Rp {float(data1.get('vol_idr',0))/1e9:,.1f} M"],
                        tk2: [format_rupiah_bersih(last2), format_rupiah_bersih(high2), f"{chg2:+.2f}%", f"Rp {float(data2.get('vol_idr',0))/1e9:,.1f} M"] 
                    })
                    st.table(df_compare.set_index("METRIK ANALISIS"))
                else: st.error("Salah satu koin tidak ditemukan di pasar Indodax.")
            except: st.error("Simbol koin tidak valid atau gagal terhubung ke satelit data.")

# --- FITUR BARU 3: KORELASI ALCOIN ---
def render_korelasi_kripto():
    st.markdown(f"<h2 class='gradient-text'>Matriks Korelasi Kripto</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Mengatur Diversifikasi:**
        * Sama seperti saham, jangan membeli koin yang pergerakannya 100% sama.
        * Jika angka **mendekati +1** (merah pekat), koin-koin tersebut akan jatuh bersamaan jika terjadi crash.
        * Cari koin dengan angka korelasi rendah (mendekati 0 atau negatif/biru) untuk mengamankan portofolio Anda saat Bitcoin sedang turun.
        """)
    input_tkrs = st.text_input("MASUKKAN KODE KOIN (DIPISAH KOMA)", value="BTC, ETH, SOL, DOGE, PEPE")
    if st.button("Kalkulasi Matriks Korelasi Kripto", width="stretch"):
        with st.spinner("Mengukur ikatan pergerakan antar koin..."):
            try:
                raw_list = [t.strip().upper() + "-USD" for t in input_tkrs.split(",")]
                data_corr = yf.download(raw_list, period="3mo", interval="1d", progress=False)['Close'].dropna()
                
                if not data_corr.empty:
                    if isinstance(data_corr.columns, pd.MultiIndex): data_corr.columns = data_corr.columns.get_level_values(0)
                    data_corr.columns = [c.replace("-USD", "") for c in data_corr.columns]
                    
                    fig_corr = px.imshow(data_corr.corr(), text_auto=True, color_continuous_scale="RdBu_r", zmin=-1, zmax=1)
                    fig_corr.update_layout(template="plotly_white", height=400, margin=dict(l=0,r=0,t=20,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_corr, use_container_width=True)
            except: st.error("Kalkulasi terhambat. Pastikan kode koin valid (Contoh: BTC, ETH).")

# --- FITUR BARU 4: ROTASI NARASI KRIPTO ---
def render_rotasi_narasi():
    st.markdown(f"<h2 class='gradient-text'>Peta Rotasi Narasi Kripto</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Mendeteksi Musim Kripto (Crypto Seasons):**
        * Kripto bergerak berdasarkan Tren/Narasi (contoh: Musim Koin Meme, Musim Koin AI, Musim Koin Layer-1).
        * Grafik ini merangkum rata-rata kenaikan/penurunan koin berdasarkan sektornya dalam seminggu terakhir.
        * Belilah koin di sektor yang barnya sedang panjang ke atas (Hijau), karena uang Paus (Whales) dunia sedang mengalir ke sektor tersebut!
        """)
        
    kategori_koin = {
        "Layer-1 (Fondasi)": ["BTC", "ETH", "SOL", "ADA", "AVAX"],
        "Meme Coins": ["DOGE", "SHIB", "PEPE", "FLOKI", "BONK"],
        "Kecerdasan Buatan (AI)": ["FET", "RNDR", "INJ", "NEAR", "GRT"],
        "DeFi & Pertukaran": ["UNI", "LINK", "LDO", "CRV", "MKR"]
    }
    
    if st.button("Pantau Tren Sektor Dunia", use_container_width=True):
        with st.spinner("Memetakan aliran dana institusi ke sektor narasi..."):
            hasil_narasi = []
            semua_ticker = []
            
            for koin_list in kategori_koin.values():
                semua_ticker.extend([f"{k}-USD" for k in koin_list])
                
            try:
                # Mengambil data performa 7 hari terakhir
                df_narasi = yf.download(semua_ticker, period="7d", interval="1d", progress=False)['Close']
                
                for nama_sektor, daftar_koin in kategori_koin.items():
                    total_chg = []
                    for k in daftar_koin:
                        tk = f"{k}-USD"
                        try:
                            s_data = df_narasi[tk].dropna() if isinstance(df_narasi, pd.DataFrame) else df_narasi.dropna()
                            if len(s_data) >= 2:
                                chg = ((float(s_data.iloc[-1]) - float(s_data.iloc[0])) / float(s_data.iloc[0])) * 100
                                total_chg.append(chg)
                        except: pass
                    
                    if total_chg:
                        rata_rata = sum(total_chg) / len(total_chg)
                        hasil_narasi.append({"Narasi": nama_sektor, "Performa 7 Hari (%)": round(rata_rata, 2)})
                        
                if hasil_narasi:
                    df_hasil = pd.DataFrame(hasil_narasi).sort_values(by="Performa 7 Hari (%)", ascending=False)
                    fig_narasi = px.bar(df_hasil, x="Narasi", y="Performa 7 Hari (%)", color="Performa 7 Hari (%)", color_continuous_scale=["#EF4444", "#1E293B", "#10B981"], text="Performa 7 Hari (%)")
                    fig_narasi.update_traces(texttemplate='%{text}%', textposition='outside')
                    fig_narasi.update_layout(template="plotly_white", height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_narasi, use_container_width=True)
                else:
                    st.warning("Gagal menyusun peta rotasi narasi saat ini.")
            except:
                st.error("Koneksi ke data pusat terputus.")

def render_peta_kripto():
    st.markdown(f"<h2 class='gradient-text'>Peta Dominasi Altcoin (Lokal)</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Membaca Radar Uang Lokal:**
        * Menunjukkan performa koin kripto utama di bursa lokal (Indodax).
        * Koin dengan batang tertinggi (hijau pekat) berarti sedang menerima aliran suntikan dana Paus (Whales) Indonesia.
        * Anda bisa menumpang (*riding the wave*) pada koin-koin yang baru mulai merangkak naik.
        """)
        
    if st.button("Pantau Pergerakan Kripto Terkini", use_container_width=True):
        with st.spinner("Memetakan arus Rupiah di Indodax..."):
            coin_data = []
            coins = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "PEPE", "SHIB", "AVAX"]
            indo_tickers = get_indodax_tickers()
            
            for c in coins:
                pair = f"{c.lower()}_idr"
                if pair in indo_tickers:
                    try:
                        data = indo_tickers[pair]
                        last_p = float(data.get('last', 0))
                        low_p = float(data.get('low', last_p)) 
                        if low_p > 0:
                            chg_pct = ((last_p - low_p) / low_p) * 100
                            coin_data.append({"Koin": c, "Perubahan (%)": round(chg_pct, 2)})
                    except: pass
            
            if coin_data:
                df_sec = pd.DataFrame(coin_data).sort_values(by="Perubahan (%)", ascending=False)
                fig_sec = px.bar(df_sec, x="Koin", y="Perubahan (%)", color="Perubahan (%)", color_continuous_scale=["#EF4444", "#1E293B", "#10B981"])
                fig_sec.update_layout(template="plotly_white", height=400, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_sec, use_container_width=True)
            else:
                st.warning("Gagal menarik data. Server Indodax mungkin sedang sibuk atau menolak koneksi.")

# --- FITUR BARU 5: BERITA KRIPTO ---
def render_kripto_news():
    st.markdown(f"<h2 class='gradient-text'>Crypto Intelligence Center</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Sistem Pelacak Sentimen FUD & FOMO:**
        * Mesin AI ini menyaring berita global khusus Kripto.
        * Perhatikan label di sebelah kiri. Jika banyak berita berlabel **NEGATIF** (FUD), jangan buru-buru membeli. Bandar mungkin sedang menyebar ketakutan.
        * Jika pasar penuh dengan berita **POSITIF** (FOMO) dan berlabel **🔥 HOT NEWS**, ikuti arusnya tapi tetap pasang batas Cut Loss!
        """)
        
    def analyze_sentiment(text):
        pos_words = ['naik', 'bullish', 'untung', 'lonjak', 'etf', 'investasi', 'meroket', 'cuan', 'diborong', 'rekor', 'adopsi', 'beli']
        neg_words = ['turun', 'bearish', 'anjlok', 'hack', 'kasus', 'gagal', 'merosot', 'jeblok', 'dijual', 'sec', 'denda', 'larang', 'scam']
        score = sum(1 for w in pos_words if w in text.lower()) - sum(1 for w in neg_words if w in text.lower())
        if score > 0: return "POSITIF", "badge-green"
        elif score < 0: return "NEGATIF", "badge-red"
        else: return "NETRAL", "badge-gray"

    def check_if_new(p_parsed):
        if p_parsed and (time.time() - mktime(p_parsed)) < (12 * 3600): return "🔥 HOT NEWS"
        return ""

    headers = {'User-Agent': 'Mozilla/5.0'}

    with st.spinner("Memindai radar sentimen kripto global..."):
        try:
            # Query difokuskan pada Kripto
            url_rss = "https://news.google.com/rss/search?q=kripto+OR+bitcoin+OR+altcoin+OR+crypto&hl=id&gl=ID&ceid=ID:id"
            feed = feedparser.parse(requests.get(url_rss, headers=headers, timeout=5).content)
            
            if not feed.entries:
                st.warning("Data berita kripto sedang tidak tersedia.")
                
            for entry in feed.entries[:12]: 
                sent_text, badge_c = analyze_sentiment(entry.title)
                fire_badge = check_if_new(entry.published_parsed if hasattr(entry, 'published_parsed') else None)
                pub_date = entry.published if hasattr(entry, 'published') else ""
                st.markdown(f"<div class='dash-box'><div style='display:flex; justify-content:space-between; margin-bottom:8px;'><span class='{badge_c}'>{sent_text}</span><span style='font-size:11px; color:#EF4444; font-weight:700;'>{fire_badge}</span></div><a href='{entry.link}' target='_blank' style='color:#0F172A; text-decoration:none; font-size:1rem; font-weight:600;'>{entry.title}</a><p class='text-muted' style='margin-top:8px; margin-bottom:0;'>⏰ {pub_date}</p></div>", unsafe_allow_html=True)
        except: 
            st.error("Malfungsi sambungan internet saat penarikan RSS Berita Kripto.")

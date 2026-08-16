# views_crypto.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf
import math
import random
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
        * Sistem ini akan membaca antrean jual-beli (Bid/Offer) secara langsung dari server. Fitur ini menyajikan kedalaman data yang setara atau bahkan lebih brutal dari antrean order yang biasa Anda gunakan di Stockbit, karena di sini Anda melihat pergerakan paus kripto.
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

def render_peta_kripto():
    st.markdown(f"<h2 class='gradient-text'>Peta Dominasi Altcoin</h2>", unsafe_allow_html=True)
    with st.expander("📖 PANDUAN CARA BACA & EKSEKUSI (WAJIB BACA)", expanded=False):
        st.markdown("""
        **Cara Membaca Radar Uang Global:**
        * Menunjukkan performa koin kripto utama selama 5 hari terakhir.
        * Koin dengan batang tertinggi (hijau pekat) berarti sedang menerima aliran suntikan dana Paus (Whales) dari seluruh dunia.
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

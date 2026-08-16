# views_crypto.py
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from core import get_indodax_data

def render_dasbor_indodax():
    st.markdown("<h2 class='gradient-text'>🪙 Dasbor Indodax Utama</h2>", unsafe_allow_html=True)
    st.write("Gambaran cepat kondisi pasar kripto Indonesia saat ini.")
    
    df = get_indodax_data()
    if df.empty:
        st.warning("Gagal mengambil data dari Indodax. Silakan coba lagi nanti.")
        return

    # Hitung metrik cepat
    total_market = len(df)
    koin_naik = len(df[df['%_Change'] > 0])
    koin_turun = len(df[df['%_Change'] < 0])
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Koin Aktif", f"{total_market} Koin")
    c2.metric("Market Sentiment", "BULLISH" if koin_naik > koin_turun else "BEARISH", f"{koin_naik} Naik, {koin_turun} Turun")
    
    # Koin dengan Volume Tertinggi (IDR)
    df_vol = df.sort_values(by='Vol_IDR', ascending=False).head(1)
    if not df_vol.empty:
        top_vol_coin = df_vol.iloc[0]
        c3.metric("Raja Volume (24h)", top_vol_coin['ID'], f"Rp {top_vol_coin['Vol_IDR']/1e9:.2f} Miliar")

    st.markdown("---")
    
    st.markdown("### 🏆 Top 5 Movers Hari Ini")
    col_gain, col_lose = st.columns(2)
    
    with col_gain:
        st.success("🚀 Top Gainers")
        top_gainers = df.sort_values(by='%_Change', ascending=False).head(5)
        st.dataframe(top_gainers[['ID', 'Last_Price', '%_Change']], hide_index=True, use_container_width=True)
        
    with col_lose:
        st.error("🩸 Top Losers")
        top_losers = df.sort_values(by='%_Change', ascending=True).head(5)
        st.dataframe(top_losers[['ID', 'Last_Price', '%_Change']], hide_index=True, use_container_width=True)

def render_radar_altcoin():
    st.markdown("<h2 class='gradient-text'>🚀 Radar Altcoin: Detektor Akumulasi Cukong</h2>", unsafe_allow_html=True)
    st.info("Algoritma Quant ini mencari anomali: Koin yang **volumenya masif** namun **harganya sedang ditahan/belum terbang**. Ini adalah ciri khas aktivitas akumulasi paus (Whale) sebelum harga didorong naik (PUMP).")
    
    df = get_indodax_data()
    if df.empty:
        st.warning("Sedang memuat data dari Indodax... Silakan klik Refresh.")
        return

    # Filter dasar untuk membuang koin gorengan dengan likuiditas sangat kecil
    # Minimal volume 100 Juta Rupiah per hari agar aman ditradingkan
    df_valid = df[df['Vol_IDR'] > 100_000_000].copy()
    
    # ---------------------------------------------------------------------
    # LOGIKA RADAR CUKONG (ANOMALY ACCUMULATION)
    # Kriteria 1: Harga tidak boleh sudah terbang (Maksimal naik 5%)
    # Kriteria 2: Harga tidak boleh sedang jatuh hancur (Maksimal turun 3%)
    # Kriteria 3: Volatilitas kecil (Low price action, High Volume)
    # ---------------------------------------------------------------------
    
    # Kriteria Harga: Sedang Sideways / Diakumulasi diam-diam
    df_sideways = df_valid[(df_valid['%_Change'] >= -3.0) & (df_valid['%_Change'] <= 5.0)].copy()
    
    if df_sideways.empty:
        st.warning("Belum ada koin yang memenuhi kriteria akumulasi saat ini.")
        return

    # Kriteria Volume: Kita buat rasio buatan karena API publik Indodax hanya memberikan Vol 24h
    # Asumsi: Jika Vol IDR sangat besar relatif terhadap harganya (rasio perpindahan uang), ada akumulasi.
    # Urutkan berdasarkan Volume Uang (IDR) terbesar di antara koin-koin yang harganya sideways
    df_accumulation = df_sideways.sort_values(by='Vol_IDR', ascending=False).head(15)

    st.markdown("### 🎯 Top 15 Koin Terindikasi Diakumulasi")
    st.caption("Semakin atas posisinya, semakin besar perputaran uang (IDR) yang terjadi sementara harganya sengaja ditahan.")
    
    # Formatting tampilan
    df_accumulation['Harga_Live'] = df_accumulation['Last_Price'].apply(lambda x: f"Rp {x:,.0f}" if x >= 100 else f"Rp {x:,.2f}")
    df_accumulation['Volume_Uang'] = df_accumulation['Vol_IDR'].apply(lambda x: f"Rp {x/1e9:,.2f} Miliar")
    df_accumulation['Pergerakan_Harga'] = df_accumulation['%_Change'].apply(lambda x: f"+{x}%" if x > 0 else f"{x}%")
    
    # Warna kolom untuk mempercantik tabel
    def highlight_accumulation(val):
        color = '#10B981' if '+' in str(val) else '#EF4444' if '-' in str(val) else '#64748B'
        return f'color: {color}; font-weight: bold'

    styled_df = df_accumulation[['ID', 'Harga_Live', 'Pergerakan_Harga', 'Volume_Uang']].style.applymap(highlight_accumulation, subset=['Pergerakan_Harga'])
    
    st.dataframe(styled_df, hide_index=True, use_container_width=True)

    with st.expander("🛠️ Trik Pro: Cara Eksekusi Sinyal Ini"):
        st.markdown("""
        **Strategi Masuk (Entry):**
        1. Jangan asal beli buta. Cek grafik *chart* koin tersebut (Timeframe 4H atau 1D).
        2. Pastikan grafiknya memang sedang mendatar (*Sideways*) setelah tren turun yang panjang, bukan sedang di pucuk lalu istirahat.
        3. Jika Anda melihat ada tiang volume hijau yang tinggi tetapi ukuran *candle* harganya kecil (Doji/Spinning Top), itu konfirmasi kuat cukong sedang menadah barang diam-diam.
        4. Masuklah dengan sistem cicil (DCA), karena cukong bisa mengakumulasi selama berhari-hari atau berminggu-minggu sebelum menerbangkan harganya.
        """)

def render_whale_tracker():
    st.markdown("<h2 class='gradient-text'>🐋 Whale Tracker Indodax</h2>", unsafe_allow_html=True)
    st.info("Memantau pergerakan koin dengan volume masif secara mendadak.")
    st.write("Fitur ini sedang dalam pengembangan untuk menarik data *Order Book* kedalaman level 2 dari Indodax.")

def render_arbitrase():
    st.markdown("<h2 class='gradient-text'>⚖️ Radar Arbitrase Kripto</h2>", unsafe_allow_html=True)
    st.info("Mencari selisih harga antara Indodax dan market global (Binance/KuCoin).")
    st.write("Fitur ini sedang sinkronisasi dengan WebSocket exchange eksternal.")

def render_dca():
    st.markdown("<h2 class='gradient-text'>⏳ Mesin Waktu DCA (Kripto)</h2>", unsafe_allow_html=True)
    st.info("Simulasi jika Anda rutin membeli kripto tertentu setiap bulan dari tahun-tahun lalu.")
    st.write("Modul kalkulator DCA kripto akan segera tersedia.")

def render_prediksi_kripto():
    st.markdown("<h2 class='gradient-text'>🔮 Prediksi Kripto (AI/ML)</h2>", unsafe_allow_html=True)
    st.info("Prediksi harga koin 7 hari ke depan menggunakan Machine Learning (ARIMA/Prophet).")
    st.write("Sistem ML sedang men-training model prediksi dari data historis.")

def render_adu_kripto():
    st.markdown("<h2 class='gradient-text'>⚔️ Adu Kripto (Pair Comparison)</h2>", unsafe_allow_html=True)
    st.info("Bandingkan momentum dan volume dua koin berbeda untuk memilih mana yang lebih potensial dibeli hari ini.")
    st.write("Modul visualisasi perbandingan koin akan segera hadir.")

def render_korelasi_kripto():
    st.markdown("<h2 class='gradient-text'>🧬 Korelasi Kripto</h2>", unsafe_allow_html=True)
    st.info("Deteksi hubungan pergerakan koin. (Misal: Jika BTC naik, koin apa yang ikut naik paling kencang?)")
    st.write("Sistem Matriks Korelasi (Heatmap) sedang dibangun.")

def render_rotasi_narasi():
    st.markdown("<h2 class='gradient-text'>🎡 Peta Rotasi Narasi Kripto</h2>", unsafe_allow_html=True)
    st.info("Mendeteksi kemana uang pintar berpindah (AI -> Meme -> L2 -> DeFi -> Gaming).")
    st.write("AI NLP Tracker sedang mengolah sentimen dari X (Twitter) dan berita global.")

def render_peta_kripto():
    st.markdown("<h2 class='gradient-text'>🌐 Peta Panas Kripto (Heatmap)</h2>", unsafe_allow_html=True)
    st.info("Visualisasi pergerakan seluruh market kripto dalam satu layar.")
    
    df = get_indodax_data()
    if df.empty:
        st.warning("Data tidak tersedia saat ini.")
        return
        
    df_valid = df[df['Vol_IDR'] > 0].copy()
    if df_valid.empty:
        return
        
    fig = px.treemap(df_valid.head(50), path=[px.Constant("Market Indodax (Top 50)"), 'ID'], values='Vol_IDR',
                     color='%_Change', hover_data=['Last_Price'],
                     color_continuous_scale=['#EF4444', '#1E293B', '#10B981'],
                     color_continuous_midpoint=0)
    fig.update_layout(margin=dict(t=30, l=0, r=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

def render_kripto_news():
    st.markdown("<h2 class='gradient-text'>📰 Berita & Sentimen Kripto Global</h2>", unsafe_allow_html=True)
    st.info("Berita yang menggerakkan pasar (Breaking News & Regulasi SEC/ETF).")
    st.write("Live RSS Feed dari CoinDesk & Cointelegraph akan ditampilkan di sini.")

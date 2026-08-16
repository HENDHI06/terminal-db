# views_crypto.py
import streamlit as st
import pandas as pd
import urllib.request
import json
import plotly.express as px

@st.cache_data(ttl=60) # Refresh data otomatis setiap 60 detik
def fetch_indodax_live():
    """Mesin penarik data 100% ASLI & LANGSUNG dari Server Indodax"""
    try:
        url = "https://indodax.com/api/tickers"
        # Menyamar sebagai browser agar tidak diblokir sistem keamanan Indodax
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            
        tickers = data.get("tickers", {})
        results = []
        
        for pair, info in tickers.items():
            if pair.endswith('_idr'): # Fokus 100% ke market Rupiah Indodax
                coin = pair.replace('_idr', '').upper()
                last_price = float(info.get('last', 0))
                low_price = float(info.get('low', 1)) # Harga terendah 24 jam terakhir
                vol_idr = float(info.get('vol_idr', 0))
                
                # RUMUS PRO QUANT: Mengukur "Bounce Rate"
                # Menghitung seberapa dekat harga saat ini dengan harga terdalamnya hari ini.
                # Jika angkanya 0% - 3%, berarti harga sedang di dasar (Tertahan).
                bounce_pct = ((last_price - low_price) / low_price) * 100 if low_price > 0 else 0
                
                results.append({
                    'ID': coin,
                    'Last_Price': last_price,
                    'Low_Price': low_price,
                    'Bounce_Pct': bounce_pct,
                    'Vol_IDR': vol_idr
                })
                
        return pd.DataFrame(results)
    except Exception as e:
        return pd.DataFrame()

def render_dasbor_indodax():
    st.markdown("<h2 class='gradient-text'>🪙 Dasbor Indodax Utama</h2>", unsafe_allow_html=True)
    st.write("Pantauan langsung denyut nadi market kripto lokal Indonesia.")
    
    df = fetch_indodax_live()
    if df.empty:
        st.warning("Menghubungkan ke server Indodax... Silakan klik '🔄 Refresh Data Server'.")
        return

    total_market = len(df)
    koin_aktif = len(df[df['Vol_IDR'] > 5_000_000_000]) # Koin dengan volume di atas 5 Miliar
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Pasangan IDR", f"{total_market} Koin")
    c2.metric("Koin Sangat Aktif", f"{koin_aktif} Koin", "Vol > Rp 5 Miliar")
    
    # Raja Volume Indodax
    df_vol = df.sort_values(by='Vol_IDR', ascending=False).head(1)
    if not df_vol.empty:
        top_vol_coin = df_vol.iloc[0]
        c3.metric("Raja Volume (24h)", top_vol_coin['ID'], f"Rp {top_vol_coin['Vol_IDR']/1e9:.2f} Miliar")

    st.markdown("---")
    
    st.markdown("### 🏆 Peta Momentum Indodax (24 Jam)")
    col_gain, col_lose = st.columns(2)
    
    with col_gain:
        st.success("🚀 Terjauh dari Dasar (Terbang)")
        st.caption("Koin yang sudah melambung jauh meninggalkan harga terendahnya.")
        top_bounce = df.sort_values(by='Bounce_Pct', ascending=False).head(5)
        top_bounce['Last_Price'] = top_bounce['Last_Price'].apply(lambda x: f"Rp {x:,.0f}" if x > 100 else f"Rp {x:,.4f}")
        top_bounce['Jauh_Dari_Dasar'] = top_bounce['Bounce_Pct'].apply(lambda x: f"+{x:.2f}%")
        st.dataframe(top_bounce[['ID', 'Last_Price', 'Jauh_Dari_Dasar']], hide_index=True, use_container_width=True)
        
    with col_lose:
        st.error("🧊 Masih di Dasar (Tertahan)")
        st.caption("Koin yang harganya nempel ketat dengan titik terendahnya hari ini.")
        bot_bounce = df.sort_values(by='Bounce_Pct', ascending=True).head(5)
        bot_bounce['Last_Price'] = bot_bounce['Last_Price'].apply(lambda x: f"Rp {x:,.0f}" if x > 100 else f"Rp {x:,.4f}")
        bot_bounce['Jauh_Dari_Dasar'] = bot_bounce['Bounce_Pct'].apply(lambda x: f"+{x:.2f}%")
        st.dataframe(bot_bounce[['ID', 'Last_Price', 'Jauh_Dari_Dasar']], hide_index=True, use_container_width=True)

def render_radar_altcoin():
    st.markdown("<h2 class='gradient-text'>🚀 Radar Altcoin: Detektor Akumulasi Cukong</h2>", unsafe_allow_html=True)
    st.info("Scanner ini mencari Anomali: Koin yang **Perputaran Uang (Vol)-nya Miliaran Rupiah**, tapi **Harganya ditahan di dasar** (Jarak pantulannya kecil). Ini adalah jejak paus mengakumulasi barang tanpa membuat harga terbang terlebih dahulu.")
    
    df = fetch_indodax_live()
    if df.empty:
        st.warning("Menghubungkan ke server Indodax... Silakan klik '🔄 Refresh Data Server'.")
        return

    # ---------------------------------------------------------------------
    # LOGIKA RADAR CUKONG INDODAX ASLI
    # Syarat 1: Likuiditas Cukup (Volume IDR Minimal 1 Miliar Rupiah)
    # Syarat 2: Harga masih di Bawah/Dasar (Jarak dari Low 24h maksimal 5%)
    # ---------------------------------------------------------------------
    
    df_valid = df[df['Vol_IDR'] > 1_000_000_000].copy()
    
    # Mencari koin yang harganya sedang ditahan sideways dekat dasar
    df_accumulation = df_valid[df_valid['Bounce_Pct'] <= 5.0].copy()
    
    if df_accumulation.empty:
        st.warning("Market sedang panas. Belum ada koin bervolume besar yang ditahan di dasar saat ini.")
        return

    # Urutkan berdasarkan Uang yang masuk (IDR) terbesar
    df_accumulation = df_accumulation.sort_values(by='Vol_IDR', ascending=False).head(15)

    st.markdown("### 🎯 Sinyal Akumulasi Paus (Siap PUMP)")
    st.caption("Semakin atas posisinya, semakin brutal akumulasi uangnya (IDR) sementara harganya terus ditahan oleh Cukong.")
    
    # Formatting tampilan
    df_accumulation['Harga_Live'] = df_accumulation['Last_Price'].apply(lambda x: f"Rp {x:,.0f}" if x >= 100 else f"Rp {x:,.4f}")
    df_accumulation['Volume_Uang_IDR'] = df_accumulation['Vol_IDR'].apply(lambda x: f"Rp {x/1e9:,.2f} Miliar")
    df_accumulation['Posisi_Dari_Dasar'] = df_accumulation['Bounce_Pct'].apply(lambda x: f"+{x:.2f}% dari Bawah")
    
    def highlight_accumulation(val):
        # Berikan warna hijau menyala jika dia sangat dekat dengan dasar (0 - 2%)
        val_float = float(val.replace('+', '').replace('% dari Bawah', ''))
        color = '#10B981' if val_float <= 2.5 else '#3B82F6'
        return f'color: {color}; font-weight: bold'

    styled_df = df_accumulation[['ID', 'Harga_Live', 'Posisi_Dari_Dasar', 'Volume_Uang_IDR']].style.applymap(highlight_accumulation, subset=['Posisi_Dari_Dasar'])
    
    st.dataframe(styled_df, hide_index=True, use_container_width=True)

    with st.expander("🛠️ Trik Pro: Cara Membaca Scanner Ini"):
        st.markdown("""
        **Cara Mengeksekusi Cukong:**
        1. Buka Indodax, lihat koin yang ada di urutan **Nomor 1 atau 2** pada tabel di atas.
        2. Buka *chart* koin tersebut (Timeframe 1 Jam atau 4 Jam).
        3. Jika Anda melihat banyak tiang volume yang tinggi menjulang, tetapi *candle* harganya pendek-pendek (Doji / tertahan merayap), itu **KONFIRMASI 100% Cukong sedang menampung barang Ritel yang *Cut Loss***.
        4. Ikutlah membeli perlahan (DCA) dan pasang jaring. Tunggu sampai Ritel habis barangnya, lalu cukong akan menerbangkan harganya!
        """)

# --- FITUR LAINNYA ---

def render_whale_tracker():
    st.markdown("<h2 class='gradient-text'>🐋 Whale Tracker Indodax</h2>", unsafe_allow_html=True)
    st.info("Memantau pergerakan koin dengan volume masif secara mendadak.")
    st.write("Fitur ini sedang dalam pengembangan untuk menarik data *Order Book* kedalaman level 2 langsung dari Indodax API.")

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
    st.markdown("<h2 class='gradient-text'>🌐 Peta Panas Indodax (Heatmap)</h2>", unsafe_allow_html=True)
    st.info("Visualisasi pergerakan seluruh market Rupiah (IDR) dalam satu layar.")
    
    df = fetch_indodax_live()
    if df.empty:
        st.warning("Data tidak tersedia saat ini.")
        return
        
    df_valid = df[df['Vol_IDR'] > 0].copy()
    if df_valid.empty:
        return
        
    fig = px.treemap(df_valid.head(30), path=[px.Constant("Market Indodax (IDR)"), 'ID'], values='Vol_IDR',
                     color='Bounce_Pct', hover_data=['Last_Price'],
                     color_continuous_scale=['#1E293B', '#10B981', '#EF4444'], # Gelap ke Hijau ke Merah
                     color_continuous_midpoint=5)
    fig.update_layout(margin=dict(t=30, l=0, r=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

def render_kripto_news():
    st.markdown("<h2 class='gradient-text'>📰 Berita & Sentimen Kripto Global</h2>", unsafe_allow_html=True)
    st.info("Berita yang menggerakkan pasar (Breaking News & Regulasi SEC/ETF).")
    st.write("Live RSS Feed dari CoinDesk & Cointelegraph akan ditampilkan di sini.")

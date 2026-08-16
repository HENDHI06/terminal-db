# views_crypto.py
import streamlit as st
import pandas as pd
import urllib.request
import json
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf

@st.cache_data(ttl=60)
def fetch_indodax_live():
    """Mesin penarik data 100% ASLI & LANGSUNG dari Server Indodax"""
    try:
        url = "https://indodax.com/api/tickers"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            
        tickers = data.get("tickers", {})
        results = []
        
        for pair, info in tickers.items():
            if pair.endswith('_idr'): 
                coin = pair.replace('_idr', '').upper()
                last_price = float(info.get('last', 0))
                low_price = float(info.get('low', 1))
                vol_idr = float(info.get('vol_idr', 0))
                
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

@st.cache_data(ttl=30)
def fetch_order_book(coin_id):
    """Menarik data kedalaman pasar (Order Book Level 2) dari Indodax"""
    try:
        url = f"https://indodax.com/api/depth/{coin_id.lower()}idr"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
        
        df_buy = pd.DataFrame(data.get('buy', []), columns=['Price', 'Amount']).astype(float)
        df_sell = pd.DataFrame(data.get('sell', []), columns=['Price', 'Amount']).astype(float)
        return df_buy, df_sell
    except:
        return pd.DataFrame(), pd.DataFrame()

def render_dasbor_indodax():
    st.markdown("<h2 class='gradient-text'>🪙 Dasbor Indodax Utama</h2>", unsafe_allow_html=True)
    st.write("Pantauan langsung denyut nadi market kripto lokal Indonesia.")
    
    df = fetch_indodax_live()
    if df.empty:
        st.warning("Menghubungkan ke server Indodax... Silakan klik '🔄 Refresh Data Server'.")
        return

    total_market = len(df)
    koin_aktif = len(df[df['Vol_IDR'] > 5_000_000_000])
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Pasangan IDR", f"{total_market} Koin")
    c2.metric("Koin Sangat Aktif", f"{koin_aktif} Koin", "Vol > Rp 5 Miliar")
    
    df_vol = df.sort_values(by='Vol_IDR', ascending=False).head(1)
    if not df_vol.empty:
        top_vol_coin = df_vol.iloc[0]
        c3.metric("Raja Volume (24h)", top_vol_coin['ID'], f"Rp {top_vol_coin['Vol_IDR']/1e9:.2f} Miliar")

    st.markdown("---")
    st.markdown("### 🏆 Peta Momentum Indodax (24 Jam)")
    col_gain, col_lose = st.columns(2)
    
    with col_gain:
        st.success("🚀 Terjauh dari Dasar (Terbang)")
        top_bounce = df.sort_values(by='Bounce_Pct', ascending=False).head(5)
        top_bounce['Last_Price'] = top_bounce['Last_Price'].apply(lambda x: f"Rp {x:,.0f}" if x > 100 else f"Rp {x:,.4f}")
        top_bounce['Jauh_Dari_Dasar'] = top_bounce['Bounce_Pct'].apply(lambda x: f"+{x:.2f}%")
        st.dataframe(top_bounce[['ID', 'Last_Price', 'Jauh_Dari_Dasar']], hide_index=True, use_container_width=True)
        
    with col_lose:
        st.error("🧊 Masih di Dasar (Tertahan)")
        bot_bounce = df.sort_values(by='Bounce_Pct', ascending=True).head(5)
        bot_bounce['Last_Price'] = bot_bounce['Last_Price'].apply(lambda x: f"Rp {x:,.0f}" if x > 100 else f"Rp {x:,.4f}")
        bot_bounce['Jauh_Dari_Dasar'] = bot_bounce['Bounce_Pct'].apply(lambda x: f"+{x:.2f}%")
        st.dataframe(bot_bounce[['ID', 'Last_Price', 'Jauh_Dari_Dasar']], hide_index=True, use_container_width=True)

def render_radar_altcoin():
    st.markdown("<h2 class='gradient-text'>🚀 Peringkat Akumulasi Cukong</h2>", unsafe_allow_html=True)
    st.info("Sistem mengecek **SELURUH KOIN** di Indodax dan memberikan **Skor (0-100)**. Semakin tinggi skornya, semakin valid tanda koin tersebut sedang diakumulasi diam-diam sebelum PUMP.")
    
    df = fetch_indodax_live()
    if df.empty: return

    df_valid = df[df['Vol_IDR'] > 50_000_000].copy()
    
    def hitung_skor(row):
        vol = row['Vol_IDR']
        bounce = row['Bounce_Pct']
        
        if vol >= 10_000_000_000: vol_pts = 50
        elif vol >= 5_000_000_000: vol_pts = 40
        elif vol >= 1_000_000_000: vol_pts = 30
        elif vol >= 500_000_000: vol_pts = 20
        else: vol_pts = 10
            
        if bounce <= 1.5: bounce_pts = 50
        elif bounce <= 3.0: bounce_pts = 40
        elif bounce <= 5.0: bounce_pts = 30
        elif bounce <= 10.0: bounce_pts = 10
        else: bounce_pts = 0
            
        return vol_pts + bounce_pts

    def kategori_skor(skor):
        if skor >= 90: return "💎 SANGAT BAGUS"
        elif skor >= 70: return "⭐ BAGUS"
        elif skor >= 50: return "⚠️ LUMAYAN (Risiko)"
        else: return "❌ BURUK / SUDAH TERBANG"

    df_valid['Skor_Akumulasi'] = df_valid.apply(hitung_skor, axis=1)
    df_valid['Status_Koin'] = df_valid['Skor_Akumulasi'].apply(kategori_skor)
    df_sorted = df_valid.sort_values(by=['Skor_Akumulasi', 'Vol_IDR'], ascending=[False, False])
    
    st.markdown(f"### 📊 Tabel Peringkat Scanner ({len(df_sorted)} Koin)")
    df_sorted['Harga_Live'] = df_sorted['Last_Price'].apply(lambda x: f"Rp {x:,.0f}" if x >= 100 else f"Rp {x:,.4f}")
    df_sorted['Volume_Uang_IDR'] = df_sorted['Vol_IDR'].apply(lambda x: f"Rp {x/1e9:,.2f} Miliar")
    df_sorted['Pantulan_Dari_Dasar'] = df_sorted['Bounce_Pct'].apply(lambda x: f"+{x:.2f}%")
    
    display_df = df_sorted[['ID', 'Status_Koin', 'Skor_Akumulasi', 'Harga_Live', 'Pantulan_Dari_Dasar', 'Volume_Uang_IDR']]
    st.dataframe(display_df.style.background_gradient(subset=['Skor_Akumulasi'], cmap='RdYlGn', vmin=0, vmax=100), hide_index=True, use_container_width=True, height=600)

def render_whale_tracker():
    st.markdown("<h2 class='gradient-text'>🐋 Detektor Tembok Cukong (Order Book)</h2>", unsafe_allow_html=True)
    st.info("Memindai uang nyata (Rupiah) yang sedang mengantre di pasar. Cari 'Tembok Hijau' yang tinggi menjulang, itu adalah *Support* buatan Cukong yang sangat kuat!")
    
    koin_pilihan = st.selectbox("Pilih Koin untuk di-X-Ray Temboknya:", ["BTC", "ETH", "SOL", "PEPE", "DOGE", "XRP", "ADA", "AVAX"])
    
    if st.button(f"🔍 Pindai Tembok {koin_pilihan} Sekarang", use_container_width=True):
        with st.spinner(f"Menyadap data antrean {koin_pilihan} di Indodax..."):
            df_buy, df_sell = fetch_order_book(koin_pilihan)
            
            if df_buy.empty or df_sell.empty:
                st.error("Gagal menarik data antrean. Server Indodax mungkin sedang sibuk.")
            else:
                # Kalkulasi akumulasi uang di antrean Beli (Bid)
                df_buy = df_buy.sort_values('Price', ascending=False).head(50) # Ambil 50 antrean terdekat
                df_buy['Total_IDR'] = df_buy['Price'] * df_buy['Amount']
                df_buy['Cumulative_IDR'] = df_buy['Total_IDR'].cumsum()
                
                # Kalkulasi akumulasi uang di antrean Jual (Ask)
                df_sell = df_sell.sort_values('Price', ascending=True).head(50)
                df_sell['Total_IDR'] = df_sell['Price'] * df_sell['Amount']
                df_sell['Cumulative_IDR'] = df_sell['Total_IDR'].cumsum()
                
                # Buat Grafik Gunung (Depth Chart)
                fig = go.Figure()
                # Tembok Beli (Hijau)
                fig.add_trace(go.Scatter(x=df_buy['Price'], y=df_buy['Cumulative_IDR'], fill='tozeroy', mode='lines', line_color='#10B981', name='Antrean Beli (Tembok Support)'))
                # Tembok Jual (Merah)
                fig.add_trace(go.Scatter(x=df_sell['Price'], y=df_sell['Cumulative_IDR'], fill='tozeroy', mode='lines', line_color='#EF4444', name='Antrean Jual (Tembok Resistance)'))
                
                fig.update_layout(
                    title=f"Peta Kekuatan Antrean Uang - {koin_pilihan}/IDR",
                    xaxis_title="Tingkat Harga (Rp)",
                    yaxis_title="Total Akumulasi Antrean Uang (Rp)",
                    template="plotly_white",
                    hovermode="x unified",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, use_container_width=True)
                
                total_beli_miliar = df_buy['Total_IDR'].sum() / 1e9
                total_jual_miliar = df_sell['Total_IDR'].sum() / 1e9
                
                st.markdown("---")
                c1, c2 = st.columns(2)
                c1.metric("Kekuatan Beli (Support)", f"Rp {total_beli_miliar:.2f} Miliar")
                c2.metric("Tekanan Jual (Resistance)", f"Rp {total_jual_miliar:.2f} Miliar")
                
                if total_beli_miliar > total_jual_miliar * 1.5:
                    st.success(f"💡 **Kesimpulan Sistem:** Tembok BELI sangat dominan! Cukong sedang menjaga harga {koin_pilihan} agar tidak jatuh.")
                elif total_jual_miliar > total_beli_miliar * 1.5:
                    st.error(f"⚠️ **Kesimpulan Sistem:** Tembok JUAL raksasa menghadang di atas. {koin_pilihan} akan sangat berat untuk naik saat ini.")
                else:
                    st.info(f"⚖️ **Kesimpulan Sistem:** Kekuatan Beli dan Jual saat ini seimbang. Pasar sedang *wait and see*.")

def render_arbitrase():
    st.markdown("<h2 class='gradient-text'>⚖️ Radar Arbitrase (Lokal vs Global)</h2>", unsafe_allow_html=True)
    st.info("Mendeteksi koin yang 'Salah Harga'. Membandingkan harga di Indodax dengan harga standar Global (Wall Street/Binance).")
    
    if st.button("⚖️ Mulai Pindai Perbedaan Harga", use_container_width=True):
        with st.spinner("Menyelaraskan data kurs USD dan harga kripto global..."):
            try:
                # Ambil kurs Rupiah dari Yahoo Finance (Atau gunakan fallback 16.000)
                try:
                    kurs_df = yf.download('IDR=X', period='1d', progress=False)['Close']
                    kurs_usd_idr = float(kurs_df.iloc[-1])
                except:
                    kurs_usd_idr = 16000
                
                st.write(f"💵 *Nilai Tukar Referensi: 1 USD = Rp {kurs_usd_idr:,.0f}*")
                
                df_indo = fetch_indodax_live()
                koin_target = ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE', 'ADA', 'LINK']
                
                tickers_yf = [f"{k}-USD" for k in koin_target]
                df_global = yf.download(tickers_yf, period='1d', progress=False)['Close']
                
                hasil_arbitrase = []
                
                for koin in koin_target:
                    indo_row = df_indo[df_indo['ID'] == koin]
                    if not indo_row.empty:
                        harga_indo = float(indo_row['Last_Price'].iloc[0])
                        harga_global_usd = float(df_global[f"{koin}-USD"].iloc[-1])
                        harga_global_idr = harga_global_usd * kurs_usd_idr
                        
                        # Hitung selisih
                        selisih_pct = ((harga_indo - harga_global_idr) / harga_global_idr) * 100
                        
                        hasil_arbitrase.append({
                            'Koin': koin,
                            'Harga Indodax': f"Rp {harga_indo:,.0f}",
                            'Harga Global': f"Rp {harga_global_idr:,.0f}",
                            'Status Harga': selisih_pct
                        })
                
                df_hasil = pd.DataFrame(hasil_arbitrase)
                
                def format_status(val):
                    if val < -1.0: return f"🟢 DISKON {-val:.2f}% (Indodax Lebih Murah)"
                    elif val > 1.0: return f"🔴 PREMIUM {val:.2f}% (Indodax Lebih Mahal)"
                    else: return f"⚪ NORMAL ({val:.2f}%)"
                    
                def warna_status(val):
                    if 'DISKON' in val: return 'color: #10B981; font-weight: bold;'
                    elif 'PREMIUM' in val: return 'color: #EF4444; font-weight: bold;'
                    return 'color: #64748B;'
                    
                df_hasil['Status Harga'] = df_hasil['Status Harga'].apply(format_status)
                st.dataframe(df_hasil.style.applymap(warna_status, subset=['Status Harga']), hide_index=True, use_container_width=True)
                
            except Exception as e:
                st.error("Terjadi kendala saat menyinkronkan data global. Coba lagi dalam beberapa detik.")

# --- FITUR PLACEHOLDER LAINNYA ---
def render_dca():
    st.markdown("<h2 class='gradient-text'>⏳ Mesin Waktu DCA (Kripto)</h2>", unsafe_allow_html=True)
    st.write("Modul kalkulator DCA kripto akan segera tersedia di pembaruan selanjutnya.")

def render_prediksi_kripto():
    st.markdown("<h2 class='gradient-text'>🔮 Prediksi Kripto (AI/ML)</h2>", unsafe_allow_html=True)
    st.write("Sistem ML sedang men-training model prediksi dari data historis.")

def render_adu_kripto():
    st.markdown("<h2 class='gradient-text'>⚔️ Adu Kripto (Pair Comparison)</h2>", unsafe_allow_html=True)
    st.write("Modul visualisasi perbandingan koin akan segera hadir.")

def render_korelasi_kripto():
    st.markdown("<h2 class='gradient-text'>🧬 Korelasi Kripto</h2>", unsafe_allow_html=True)
    st.write("Sistem Matriks Korelasi (Heatmap) sedang dibangun.")

def render_rotasi_narasi():
    st.markdown("<h2 class='gradient-text'>🎡 Peta Rotasi Narasi Kripto</h2>", unsafe_allow_html=True)
    st.write("AI NLP Tracker sedang mengolah sentimen dari X (Twitter) dan berita global.")

def render_peta_kripto():
    st.markdown("<h2 class='gradient-text'>🌐 Peta Panas Indodax (Heatmap)</h2>", unsafe_allow_html=True)
    st.info("Visualisasi pergerakan seluruh market Rupiah (IDR) dalam satu layar.")
    df = fetch_indodax_live()
    if df.empty: return
    df_valid = df[df['Vol_IDR'] > 0].copy()
    if df_valid.empty: return
    fig = px.treemap(df_valid.head(30), path=[px.Constant("Market Indodax (IDR)"), 'ID'], values='Vol_IDR', color='Bounce_Pct', hover_data=['Last_Price'], color_continuous_scale=['#1E293B', '#10B981', '#EF4444'], color_continuous_midpoint=5)
    fig.update_layout(margin=dict(t=30, l=0, r=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

def render_kripto_news():
    st.markdown("<h2 class='gradient-text'>📰 Berita & Sentimen Kripto Global</h2>", unsafe_allow_html=True)
    st.write("Live RSS Feed dari CoinDesk & Cointelegraph akan ditampilkan di sini.")

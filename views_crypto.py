# views_crypto.py
import streamlit as st
import pandas as pd
import urllib.request
import json
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta

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
                df_buy = df_buy.sort_values('Price', ascending=False).head(50)
                df_buy['Total_IDR'] = df_buy['Price'] * df_buy['Amount']
                df_buy['Cumulative_IDR'] = df_buy['Total_IDR'].cumsum()
                
                df_sell = df_sell.sort_values('Price', ascending=True).head(50)
                df_sell['Total_IDR'] = df_sell['Price'] * df_sell['Amount']
                df_sell['Cumulative_IDR'] = df_sell['Total_IDR'].cumsum()
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_buy['Price'], y=df_buy['Cumulative_IDR'], fill='tozeroy', mode='lines', line_color='#10B981', name='Antrean Beli (Tembok Support)'))
                fig.add_trace(go.Scatter(x=df_sell['Price'], y=df_sell['Cumulative_IDR'], fill='tozeroy', mode='lines', line_color='#EF4444', name='Antrean Jual (Tembok Resistance)'))
                
                fig.update_layout(title=f"Peta Kekuatan Antrean Uang - {koin_pilihan}/IDR", xaxis_title="Tingkat Harga (Rp)", yaxis_title="Total Akumulasi Antrean Uang (Rp)", template="plotly_white", hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                st.plotly_chart(fig, use_container_width=True)
                
                total_beli_miliar = df_buy['Total_IDR'].sum() / 1e9
                total_jual_miliar = df_sell['Total_IDR'].sum() / 1e9
                
                st.markdown("---")
                c1, c2 = st.columns(2)
                c1.metric("Kekuatan Beli (Support)", f"Rp {total_beli_miliar:.2f} Miliar")
                c2.metric("Tekanan Jual (Resistance)", f"Rp {total_jual_miliar:.2f} Miliar")
                
                if total_beli_miliar > total_jual_miliar * 1.5: st.success(f"💡 **Kesimpulan Sistem:** Tembok BELI dominan! Cukong menjaga harga {koin_pilihan}.")
                elif total_jual_miliar > total_beli_miliar * 1.5: st.error(f"⚠️ **Kesimpulan Sistem:** Tembok JUAL raksasa. {koin_pilihan} akan berat untuk naik.")
                else: st.info(f"⚖️ **Kesimpulan Sistem:** Kekuatan Beli dan Jual saat ini seimbang.")

def render_arbitrase():
    st.markdown("<h2 class='gradient-text'>⚖️ Radar Arbitrase (Lokal vs Global)</h2>", unsafe_allow_html=True)
    st.info("Mendeteksi koin yang 'Salah Harga'. Membandingkan harga di Indodax dengan harga standar Global (Wall Street/Binance).")
    
    if st.button("⚖️ Mulai Pindai Perbedaan Harga", use_container_width=True):
        with st.spinner("Menyelaraskan data kurs USD dan harga kripto global..."):
            try:
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
                        selisih_pct = ((harga_indo - harga_global_idr) / harga_global_idr) * 100
                        hasil_arbitrase.append({'Koin': koin, 'Harga Indodax': f"Rp {harga_indo:,.0f}", 'Harga Global': f"Rp {harga_global_idr:,.0f}", 'Status Harga': selisih_pct})
                
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

def render_dca():
    st.markdown("<h2 class='gradient-text'>⏳ Mesin Waktu DCA Kripto</h2>", unsafe_allow_html=True)
    st.info("Mengkalkulasi secara nyata keuntungan Anda jika rutin membeli kripto tertentu setiap bulan menggunakan data historis riil.")
    
    with st.form("dca_form"):
        c1, c2, c3 = st.columns(3)
        coin_pilihan = c1.selectbox("Pilih Aset", ["BTC", "ETH", "SOL", "DOGE", "XRP"])
        nabung_rutin = c2.number_input("Tabungan Rutin per Bulan (Rp)", min_value=100000, value=1000000, step=100000)
        durasi_bulan = c3.slider("Sejak Berapa Bulan Lalu?", 1, 48, 12)
        btn = st.form_submit_button("Hitung Profit DCA Saya", width="stretch")
        
    if btn:
        with st.spinner("Memutar waktu ke masa lalu..."):
            try:
                # Menggunakan yfinance bulanan
                df_hist = yf.download(f"{coin_pilihan}-USD", period=f"{durasi_bulan}mo", interval="1mo", progress=False)['Close']
                if not df_hist.empty:
                    df_hist = df_hist.dropna()
                    total_koin = 0
                    total_modal = 0
                    
                    # Simulasi pembelian setiap bulan (asumsi kurs 16.000)
                    for price_usd in df_hist.values:
                        price_idr = float(price_usd) * 16000
                        koin_didapat = nabung_rutin / price_idr
                        total_koin += koin_didapat
                        total_modal += nabung_rutin
                        
                    harga_sekarang_idr = float(df_hist.iloc[-1]) * 16000
                    nilai_sekarang = total_koin * harga_sekarang_idr
                    profit_loss = nilai_sekarang - total_modal
                    profit_pct = (profit_loss / total_modal) * 100
                    
                    st.markdown("---")
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Total Modal Dikeluarkan", f"Rp {total_modal:,.0f}")
                    m2.metric("Nilai Portofolio Sekarang", f"Rp {nilai_sekarang:,.0f}", f"{profit_pct:.2f}%")
                    m3.metric("Koin Terkumpul", f"{total_koin:.4f} {coin_pilihan}")
                    
                    if profit_loss > 0:
                        st.success(f"🎉 Strategi disiplin berhasil! Anda menghasilkan **keuntungan bersih Rp {profit_loss:,.0f}** dibandingkan menabung biasa di bank.")
                    else:
                        st.error(f"📉 Portofolio DCA Anda sedang merah Rp {profit_loss:,.0f}. Teruslah konsisten untuk menurunkan harga rata-rata (Average Down)!")
            except Exception as e:
                st.error("Gagal menarik data masa lalu. Silakan coba lagi.")

def render_prediksi_kripto():
    st.markdown("<h2 class='gradient-text'>🔮 Prediksi Tren Kripto (Kuantitatif)</h2>", unsafe_allow_html=True)
    st.info("Sistem menganalisis momentum rata-rata harga (Moving Average) 30 hari terakhir dan memproyeksikan arah tren 7 hari ke depan.")
    
    koin_prediksi = st.selectbox("Pilih Koin untuk Diproyeksikan:", ["BTC", "ETH", "SOL", "DOGE"])
    
    if st.button("🔮 Tarik Garis Prediksi Tren", use_container_width=True):
        with st.spinner("Mesin kuantitatif sedang mengkalkulasi..."):
            try:
                df_hist = yf.download(f"{koin_prediksi}-USD", period="30d", progress=False)['Close'].dropna()
                if not df_hist.empty:
                    df_hist = df_hist.to_frame(name='Price')
                    df_hist = df_hist.reset_index()
                    df_hist['Hari_Ke'] = range(len(df_hist))
                    
                    # Simple Linear Regression Line (Trend Line)
                    z = np.polyfit(df_hist['Hari_Ke'], df_hist['Price'], 1)
                    p = np.poly1d(z)
                    
                    fig = go.Figure()
                    # Garis harga asli
                    fig.add_trace(go.Scatter(x=df_hist['Date'], y=df_hist['Price'], mode='lines', name='Harga Aktual', line=dict(color='#2563EB', width=2)))
                    # Garis Tren/Prediksi
                    fig.add_trace(go.Scatter(x=df_hist['Date'], y=p(df_hist['Hari_Ke']), mode='lines', name='Garis Tren Model', line=dict(color='#EF4444', width=2, dash='dash')))
                    
                    fig.update_layout(title=f"Proyeksi Tren {koin_prediksi} (Berdasarkan Momentum 30 Hari)", template="plotly_white")
                    st.plotly_chart(fig, use_container_width=True)
                    
                    kemiringan = z[0] # Slope
                    if kemiringan > 0:
                        st.success(f"📈 **Sinyal Tren:** Algoritma membaca momentum {koin_prediksi} sedang **NAIK**. Jika tidak ada anomali pasar, arah 7 hari ke depan cenderung positif.")
                    else:
                        st.error(f"📉 **Sinyal Tren:** Algoritma membaca momentum {koin_prediksi} sedang **TURUN**. Waspada terhadap koreksi lebih lanjut.")
            except Exception as e:
                st.error("Gagal menarik data model.")

def render_adu_kripto():
    st.markdown("<h2 class='gradient-text'>⚔️ Adu Kripto (Pair Comparison)</h2>", unsafe_allow_html=True)
    st.info("Fitur untuk melihat koin mana yang tumbuh lebih cepat jika keduanya dimulai dari titik 0% di waktu yang sama (Normalisasi).")
    
    c1, c2 = st.columns(2)
    koin1 = c1.selectbox("Koin Penantang 1:", ["BTC", "ETH", "SOL", "ADA"], index=0)
    koin2 = c2.selectbox("Koin Penantang 2:", ["ETH", "SOL", "DOGE", "AVAX"], index=1)
    durasi = st.selectbox("Durasi Pertarungan:", ["1mo", "3mo", "6mo"], format_func=lambda x: f"{x.replace('mo', ' Bulan Terakhir')}")
    
    if st.button("⚔️ Mulai Pertarungan Chart", use_container_width=True):
        with st.spinner("Memproses grafik perbandingan..."):
            try:
                df1 = yf.download(f"{koin1}-USD", period=durasi, progress=False)['Close'].dropna()
                df2 = yf.download(f"{koin2}-USD", period=durasi, progress=False)['Close'].dropna()
                
                # Normalisasi persentase pertumbuhan dari hari pertama
                df1_norm = (df1 / df1.iloc[0]) * 100
                df2_norm = (df2 / df2.iloc[0]) * 100
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df1_norm.index, y=df1_norm.values, name=koin1, line=dict(width=3)))
                fig.add_trace(go.Scatter(x=df2_norm.index, y=df2_norm.values, name=koin2, line=dict(width=3)))
                
                fig.update_layout(title="Perbandingan Pertumbuhan (% Persentase)", yaxis_title="Pertumbuhan (Base 100)", template="plotly_white", hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)
                
                akhir1 = df1_norm.iloc[-1] - 100
                akhir2 = df2_norm.iloc[-1] - 100
                st.success(f"🏆 Pemenang dalam periode ini adalah **{koin1 if akhir1 > akhir2 else koin2}**.")
            except:
                st.error("Gagal menarik data grafik. Koin mungkin tidak tersedia.")

def render_korelasi_kripto():
    st.markdown("<h2 class='gradient-text'>🧬 Matriks Korelasi Kripto</h2>", unsafe_allow_html=True)
    st.info("Peta panas (Heatmap) ini mendeteksi seberapa kuat koin bergerak bersamaan. Skor mendekati 1 berarti mereka selalu naik/turun bareng. Skor negatif berarti saling bertolak belakang.")
    
    if st.button("🧬 Pindai DNA Market (Top Koin)", use_container_width=True):
        with st.spinner("Mengunduh data pergerakan..."):
            try:
                tickers = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'DOGE-USD', 'XRP-USD', 'LINK-USD']
                df = yf.download(tickers, period="3mo", progress=False)['Close'].dropna()
                
                # Rapikan nama kolom
                df.columns = [c.replace('-USD', '') for c in df.columns]
                
                # Hitung korelasi
                corr_matrix = df.corr()
                
                fig = px.imshow(corr_matrix, text_auto=True, color_continuous_scale='RdBu_r', aspect="auto")
                fig.update_layout(title="Heatmap Korelasi (3 Bulan Terakhir)", template="plotly_white")
                st.plotly_chart(fig, use_container_width=True)
                
                st.markdown("💡 **Tips Trading:** Jangan beli koin yang korelasinya 0.9 ke atas sekaligus (Misal BTC dan ETH) karena itu sama saja menaruh uang di keranjang yang persis sama. Carilah koin dengan korelasi rendah untuk lindung nilai (Diversifikasi).")
            except:
                st.error("Gagal memuat matriks.")

def render_rotasi_narasi():
    st.markdown("<h2 class='gradient-text'>🎡 Peta Rotasi Sektor Kripto</h2>", unsafe_allow_html=True)
    st.info("Menganalisis data live Indodax untuk melihat sektor mana (Meme, L1, DeFi) yang sedang ramai disuntik dana oleh Cukong hari ini.")
    
    df = fetch_indodax_live()
    if df.empty: return
    
    # Pengelompokan Narasi Manual (Sederhana)
    sektor_map = {
        'Layer-1': ['BTC', 'ETH', 'SOL', 'ADA', 'AVAX', 'DOT', 'NEAR', 'FTM'],
        'Meme': ['DOGE', 'SHIB', 'PEPE', 'FLOKI'],
        'DeFi': ['UNI', 'LINK', 'AAVE', 'MKR', 'COMP'],
        'Gaming/Web3': ['SAND', 'MANA', 'GALA', 'AXS', 'ENJ']
    }
    
    hasil_sektor = []
    for sektor, koin_list in sektor_map.items():
        # Cari koin sektor ini di data Indodax
        df_sektor = df[df['ID'].isin(koin_list)]
        if not df_sektor.empty:
            avg_bounce = df_sektor['Bounce_Pct'].mean()
            total_vol = df_sektor['Vol_IDR'].sum() / 1e9 # Miliar
            hasil_sektor.append({'Sektor/Narasi': sektor, 'Rata-rata Pantulan': avg_bounce, 'Total Uang Masuk (Miliar)': total_vol})
            
    if hasil_sektor:
        df_hasil = pd.DataFrame(hasil_sektor).sort_values(by='Total Uang Masuk (Miliar)', ascending=False)
        
        fig = px.bar(df_hasil, x='Sektor/Narasi', y='Total Uang Masuk (Miliar)', color='Rata-rata Pantulan', 
                     color_continuous_scale=['#1E293B', '#10B981', '#EF4444'], text_auto='.2s',
                     title="Aliran Dana Per Sektor (Narasi) Hari Ini")
        st.plotly_chart(fig, use_container_width=True)
        st.write("💡 Perhatikan sektor dengan **Volume tertinggi tetapi warnanya gelap (Pantulan kecil)**, itu tandanya sektor tersebut sedang diakumulasi dan bersiap meledak menyusul sektor lainnya.")

def render_peta_kripto():
    st.markdown("<h2 class='gradient-text'>🌐 Peta Panas Indodax (Heatmap)</h2>", unsafe_allow_html=True)
    st.info("Visualisasi pergerakan seluruh market Rupiah (IDR) dalam satu layar.")
    
    df = fetch_indodax_live()
    if df.empty: return
    df_valid = df[df['Vol_IDR'] > 0].copy()
    if df_valid.empty: return
    
    fig = px.treemap(df_valid.head(30), path=[px.Constant("Market Indodax (IDR)"), 'ID'], values='Vol_IDR', 
                     color='Bounce_Pct', hover_data=['Last_Price'], 
                     color_continuous_scale=['#1E293B', '#10B981', '#EF4444'], color_continuous_midpoint=5)
    fig.update_layout(margin=dict(t=30, l=0, r=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

def render_kripto_news():
    st.markdown("<h2 class='gradient-text'>📰 Radar Sentimen Global</h2>", unsafe_allow_html=True)
    st.info("Menarik liputan fundamental langsung dari Wall Street dan institusi finansial.")
    
    if st.button("📰 Tarik Berita Kripto Terkini", use_container_width=True):
        with st.spinner("Menghubungkan ke Feed Berita Global..."):
            try:
                # Menggunakan library YFinance bawaan untuk menarik berita terkait BTC
                crypto = yf.Ticker("BTC-USD")
                berita = crypto.news
                
                if berita:
                    for b in berita[:5]: # Ambil 5 berita terbaru
                        with st.expander(f"🔴 {b.get('title', 'Berita Tanpa Judul')}"):
                            st.write(f"**Publisher:** {b.get('publisher', 'Global Media')}")
                            st.write(f"🔗 [Baca Selengkapnya di Sini]({b.get('link', '#')})")
                else:
                    st.write("Belum ada berita terbaru saat ini.")
            except:
                st.error("Gagal menarik feed berita. Sistem media mungkin memblokir akses otomatis.")

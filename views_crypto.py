# views_crypto.py
import streamlit as st
import pandas as pd
import urllib.request
import urllib.parse
import json
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf
import numpy as np
import xml.etree.ElementTree as ET
import ssl
import re
from datetime import datetime, timedelta

# ==========================================
# ⚙️ MESIN DATA (DATA FETCHERS)
# ==========================================

@st.cache_data(ttl=60)
def fetch_indodax_live():
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
                    'ID': coin, 'Last_Price': last_price, 'Low_Price': low_price,
                    'Bounce_Pct': bounce_pct, 'Vol_IDR': vol_idr
                })
        return pd.DataFrame(results)
    except:
        return pd.DataFrame()

@st.cache_data(ttl=30)
def fetch_order_book(coin_id):
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

@st.cache_data(ttl=3600)
def fetch_fear_greed_index():
    try:
        req = urllib.request.Request("https://api.alternative.me/fng/?limit=1", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            return int(data['data'][0]['value']), data['data'][0]['value_classification']
    except:
        return 50, "Neutral"

# PERBAIKAN: Menyedot RATUSAN koin dari Binance, lalu memfilter khusus koin yang ada di Indodax
@st.cache_data(ttl=300)
def fetch_funding_rates():
    try:
        # Ambil daftar seluruh koin Indodax saat ini
        df_indo = fetch_indodax_live()
        koin_indodax_valid = df_indo['ID'].tolist() if not df_indo.empty else []
        
        url = "https://fapi.binance.com/fapi/v1/premiumIndex"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
        
        results = []
        for item in data:
            symbol = item.get('symbol', '')
            if symbol.endswith('USDT'):
                koin = symbol.replace('USDT', '')
                # Hanya masukkan ke daftar jika koin tersebut JUGA ADA di Indodax
                if (not koin_indodax_valid) or (koin in koin_indodax_valid):
                    fr = float(item.get('lastFundingRate', 0)) * 100 
                    results.append({'Koin': koin, 'Funding Rate (%)': fr})
        
        df_res = pd.DataFrame(results)
        if not df_res.empty:
            # Urutkan berdasarkan yang paling berbahaya (Paling Merah / Paling Hijau)
            df_res['Absolut'] = df_res['Funding Rate (%)'].abs()
            df_res = df_res.sort_values(by='Absolut', ascending=False).drop(columns=['Absolut'])
        return df_res
    except:
        return pd.DataFrame()

def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def clean_html_text(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.strip()

# ==========================================
# 🖥️ ROUTING MENU TAMPILAN UTAMA
# ==========================================

def render_dasbor_indodax():
    st.markdown("<h2 class='gradient-text'>🪙 Dasbor Indodax Utama</h2>", unsafe_allow_html=True)
    st.write("Pantauan langsung denyut nadi market kripto lokal Indonesia & Sentimen Global.")
    
    fgi_val, fgi_class = fetch_fear_greed_index()
    fig_gauge = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = fgi_val,
        title = {'text': f"Psikologi Massa: <b>{fgi_class.upper()}</b>", 'font': {'size': 18}},
        gauge = {
            'axis': {'range': [0, 100], 'tickwidth': 1},
            'bar': {'color': "#0F172A", 'thickness': 0.25},
            'steps': [
                {'range': [0, 25], 'color': "#EF4444"},   
                {'range': [25, 45], 'color': "#F97316"},  
                {'range': [45, 55], 'color': "#EAB308"},  
                {'range': [55, 75], 'color': "#84CC16"},  
                {'range': [75, 100], 'color': "#10B981"}  
            ]
        }
    ))
    fig_gauge.update_layout(height=250, margin=dict(l=10, r=10, t=40, b=10))
    
    col_g, col_m = st.columns([1, 1.5])
    with col_g:
        st.plotly_chart(fig_gauge, use_container_width=True)
    
    df = fetch_indodax_live()
    with col_m:
        if df.empty:
            st.warning("Menghubungkan ke server Indodax...")
        else:
            koin_aktif = len(df[df['Vol_IDR'] > 5_000_000_000])
            c1, c2 = st.columns(2)
            c1.metric("Total Pasangan IDR", f"{len(df)} Koin")
            c2.metric("Koin Bervolume Tinggi", f"{koin_aktif} Koin", "Vol > Rp 5 Miliar")
            
            df_vol = df.sort_values(by='Vol_IDR', ascending=False).head(1)
            if not df_vol.empty:
                st.metric("👑 Raja Volume (24h)", df_vol.iloc[0]['ID'], f"Rp {df_vol.iloc[0]['Vol_IDR']/1e9:.2f} Miliar")
                
            if fgi_val <= 25:
                st.success("💡 **Sinyal Institusi:** Market sedang *Extreme Fear* (Kepanikan Maksimal). Ini adalah momentum paling aman untuk serok koin fundamental!")
            elif fgi_val >= 75:
                st.error("⚠️ **Sinyal Institusi:** Market sedang *Extreme Greed* (Sangat Rakus). Waspada bantingan keras (Koreksi) oleh Cukong. Siap-siap Take Profit.")

    if not df.empty:
        st.markdown("---")
        st.markdown("### 🏆 Peta Momentum Indodax (24 Jam)")
        col_gain, col_lose = st.columns(2)
        
        with col_gain:
            st.success("🚀 Terjauh dari Dasar (Terbang)")
            top_bounce = df.sort_values(by='Bounce_Pct', ascending=False).head(5)
            top_bounce['Last_Price'] = top_bounce['Last_Price'].apply(lambda x: f"Rp {x:,.0f}" if x >= 1 else f"Rp {x:,.4f}")
            top_bounce['Jauh_Dari_Dasar'] = top_bounce['Bounce_Pct'].apply(lambda x: f"+{x:.2f}%")
            st.dataframe(top_bounce[['ID', 'Last_Price', 'Jauh_Dari_Dasar']], hide_index=True, use_container_width=True)
            
        with col_lose:
            st.error("🧊 Masih di Dasar (Tertahan)")
            bot_bounce = df.sort_values(by='Bounce_Pct', ascending=True).head(5)
            bot_bounce['Last_Price'] = bot_bounce['Last_Price'].apply(lambda x: f"Rp {x:,.0f}" if x >= 1 else f"Rp {x:,.4f}")
            bot_bounce['Jauh_Dari_Dasar'] = bot_bounce['Bounce_Pct'].apply(lambda x: f"+{x:.2f}%")
            st.dataframe(bot_bounce[['ID', 'Last_Price', 'Jauh_Dari_Dasar']], hide_index=True, use_container_width=True)

def render_radar_altcoin():
    st.markdown("<h2 class='gradient-text'>🚀 Peringkat Akumulasi Cukong</h2>", unsafe_allow_html=True)
    st.info("Sistem memblokir *Stablecoin* dan Koin Mati, lalu mengecek *Altcoin* berpotensi yang sedang ditahan cukong di harga dasar sebelum PUMP.")
    
    df = fetch_indodax_live()
    if df.empty: return

    stablecoins = ['USDT', 'USDC', 'DAI', 'BUSD', 'TUSD', 'FDUSD', 'PYUSD']
    df = df[~df['ID'].isin(stablecoins)]

    df_valid = df[df['Vol_IDR'] >= 1_000_000_000].copy()
    
    def hitung_skor(row):
        vol = row['Vol_IDR']
        bounce = row['Bounce_Pct']
        
        if vol >= 10_000_000_000: vol_pts = 50
        elif vol >= 5_000_000_000: vol_pts = 40
        elif vol >= 2_000_000_000: vol_pts = 30
        else: vol_pts = 20
            
        if bounce <= 1.5: bounce_pts = 50
        elif bounce <= 3.0: bounce_pts = 40
        elif bounce <= 5.0: bounce_pts = 30
        elif bounce <= 10.0: bounce_pts = 10
        else: bounce_pts = 0
            
        return vol_pts + bounce_pts

    def kategori_skor(skor):
        if skor >= 90: return "💎 SANGAT BAGUS"
        elif skor >= 70: return "⭐ BAGUS"
        elif skor >= 50: return "⚠️ LUMAYAN"
        else: return "❌ BURUK / TERBANG"
        
    def rekomendasi_aksi(skor):
        if skor >= 90: return "🎯 Pantau Entry & DCA"
        elif skor >= 70: return "👀 Masukkan Watchlist"
        elif skor >= 50: return "⏳ Wait & See"
        else: return "🚫 Hindari (Fomo)"

    df_valid['Skor_Akumulasi'] = df_valid.apply(hitung_skor, axis=1)
    df_valid['Status_Koin'] = df_valid['Skor_Akumulasi'].apply(kategori_skor)
    df_valid['Rekomendasi'] = df_valid['Skor_Akumulasi'].apply(rekomendasi_aksi)
    
    df_sorted = df_valid.sort_values(by=['Skor_Akumulasi', 'Vol_IDR'], ascending=[False, False])
    
    st.markdown(f"### 📊 Tabel Peringkat Scanner (Terfilter: {len(df_sorted)} Koin Valid)")
    
    df_sorted['Harga_Live'] = df_sorted['Last_Price'].apply(lambda x: f"Rp {x:,.0f}" if x >= 1 else f"Rp {x:,.4f}")
    df_sorted['Vol_Uang_IDR'] = df_sorted['Vol_IDR'].apply(lambda x: f"Rp {x/1e9:,.2f} M")
    df_sorted['Pantulan'] = df_sorted['Bounce_Pct'].apply(lambda x: f"+{x:.2f}%")
    
    display_df = df_sorted[['ID', 'Rekomendasi', 'Skor_Akumulasi', 'Harga_Live', 'Pantulan', 'Vol_Uang_IDR']]
    
    def warnai_skor_manual(val):
        if val >= 90: warna = '#10B981'
        elif val >= 70: warna = '#34D399'
        elif val >= 50: warna = '#FBBF24'
        else: warna = '#EF4444'
        return f'background-color: {warna}; color: white; font-weight: bold;'
    
    st.dataframe(display_df.style.applymap(warnai_skor_manual, subset=['Skor_Akumulasi']), hide_index=True, use_container_width=True, height=600)

def render_whale_tracker():
    st.markdown("<h2 class='gradient-text'>🐋 Whale Tracker & Likuidasi</h2>", unsafe_allow_html=True)
    tab_order, tab_liq = st.tabs(["🧱 TEMBOK CUKONG (SPOT)", "🩸 DETEKTOR LIKUIDASI (FUTURES)"])
    
    df_indo = fetch_indodax_live()
    semua_koin = sorted(df_indo['ID'].tolist()) if not df_indo.empty else ["BTC", "ETH", "SOL"]
    
    with tab_order:
        st.info("Memindai uang nyata (Rupiah) yang sedang mengantre di pasar. Cari 'Tembok Hijau' yang tinggi menjulang, itu adalah *Support* buatan Cukong yang sangat kuat!")
        koin_pilihan = st.selectbox("Pilih Koin untuk di-X-Ray Temboknya (Pilih dari 160+ Market Indodax):", semua_koin)
        
        if st.button(f"🔍 Pindai Tembok {koin_pilihan} Sekarang", use_container_width=True):
            with st.spinner(f"Menyadap data antrean {koin_pilihan} di Indodax..."):
                df_buy, df_sell = fetch_order_book(koin_pilihan)
                if not df_buy.empty and not df_sell.empty:
                    df_buy = df_buy.sort_values('Price', ascending=False).head(50)
                    df_buy['Total_IDR'] = df_buy['Price'] * df_buy['Amount']
                    df_buy['Cumulative_IDR'] = df_buy['Total_IDR'].cumsum()
                    
                    df_sell = df_sell.sort_values('Price', ascending=True).head(50)
                    df_sell['Total_IDR'] = df_sell['Price'] * df_sell['Amount']
                    df_sell['Cumulative_IDR'] = df_sell['Total_IDR'].cumsum()
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=df_buy['Price'], y=df_buy['Cumulative_IDR'], fill='tozeroy', mode='lines', line_color='#10B981', name='Antrean Beli (Tembok Support)'))
                    fig.add_trace(go.Scatter(x=df_sell['Price'], y=df_sell['Cumulative_IDR'], fill='tozeroy', mode='lines', line_color='#EF4444', name='Antrean Jual (Tembok Resistance)'))
                    fig.update_layout(title=f"Peta Kekuatan Antrean Uang - {koin_pilihan}/IDR", xaxis_title="Tingkat Harga (Rp)", yaxis_title="Akumulasi Uang (Rp)", template="plotly_white")
                    st.plotly_chart(fig, use_container_width=True)
                    
                    total_beli_miliar = df_buy['Total_IDR'].sum() / 1e9
                    total_jual_miliar = df_sell['Total_IDR'].sum() / 1e9
                    st.markdown("---")
                    c1, c2 = st.columns(2)
                    c1.metric("Kekuatan Beli (Support)", f"Rp {total_beli_miliar:.2f} Miliar")
                    c2.metric("Tekanan Jual (Resistance)", f"Rp {total_jual_miliar:.2f} Miliar")

    with tab_liq:
        st.info("Mendeteksi *Funding Rate* Binance Global khusus untuk koin yang ada di Indodax. Jika nilai sangat positif (merah), Cukong bersiap menjatuhkan harga untuk melikuidasi mereka!")
        
        if st.button("🔄 Tarik Data Likuidasi Seluruh Koin", use_container_width=True):
            st.cache_data.clear() 
            
        with st.spinner("Mengecek ratusan koin di API Binance Global..."):
            df_funding = fetch_funding_rates()
            
            if not df_funding.empty:
                st.success(f"Berhasil melacak data Likuidasi dari {len(df_funding)} koin yang tersedia di Indodax!")
                def format_funding(val):
                    if val >= 0.03: return f"🔴 RAWAN BANTINGAN ({val:.4f}%)"
                    elif val <= -0.03: return f"🟢 RAWAN PUMP NAIK ({val:.4f}%)"
                    else: return f"⚪ AMAN / NETRAL ({val:.4f}%)"
                    
                def color_funding(val):
                    if 'BANTINGAN' in val: return 'color: #EF4444; font-weight: bold;'
                    elif 'PUMP' in val: return 'color: #10B981; font-weight: bold;'
                    return 'color: #64748B;'
                    
                df_funding['Status Likuidasi (Squeeze)'] = df_funding['Funding Rate (%)'].apply(format_funding)
                st.dataframe(df_funding[['Koin', 'Status Likuidasi (Squeeze)']].style.applymap(color_funding, subset=['Status Likuidasi (Squeeze)']), hide_index=True, use_container_width=True, height=600)
            else:
                st.error("⚠️ **Gagal memuat data likuidasi.** Silakan klik tombol 'Tarik Data' lagi.")

def render_arbitrase():
    st.markdown("<h2 class='gradient-text'>⚖️ Radar Arbitrase (Lokal vs Global)</h2>", unsafe_allow_html=True)
    st.info("Mendeteksi koin yang 'Salah Harga'. Membandingkan harga di Indodax dengan harga standar Global (Wall Street/Binance).")
    
    df_indo = fetch_indodax_live()
    semua_koin = sorted(df_indo['ID'].tolist()) if not df_indo.empty else ["BTC", "ETH", "SOL", "XRP", "DOGE"]
    
    default_coins = [c for c in ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE', 'ADA'] if c in semua_koin]
    koin_target = st.multiselect("Pilih Koin yang Ingin Dicek Selisih Harganya (Pilih Semua Koin Indodax):", semua_koin, default=default_coins)
    
    if st.button("⚖️ Mulai Pindai Perbedaan Harga", use_container_width=True):
        if not koin_target:
            st.warning("Silakan pilih minimal 1 koin untuk dipindai.")
            return
            
        with st.spinner("Menyelaraskan data kurs USD dan harga kripto global..."):
            try:
                try:
                    kurs_df = yf.download('IDR=X', period='1d', progress=False)['Close']
                    kurs_usd_idr = float(kurs_df.iloc[-1])
                except:
                    kurs_usd_idr = 16000
                st.write(f"💵 *Nilai Tukar Referensi: 1 USD = Rp {kurs_usd_idr:,.0f}*")
                
                tickers_yf = [f"{k}-USD" for k in koin_target]
                df_global = yf.download(tickers_yf, period='1d', progress=False)['Close']
                
                hasil_arbitrase = []
                for koin in koin_target:
                    indo_row = df_indo[df_indo['ID'] == koin]
                    if not indo_row.empty:
                        harga_indo = float(indo_row['Last_Price'].iloc[0])
                        try:
                            if len(koin_target) == 1:
                                harga_global_usd = float(df_global.iloc[-1])
                            else:
                                harga_global_usd = float(df_global[f"{koin}-USD"].iloc[-1])
                                
                            harga_global_idr = harga_global_usd * kurs_usd_idr
                            selisih_pct = ((harga_indo - harga_global_idr) / harga_global_idr) * 100
                            
                            harga_indo_str = f"Rp {harga_indo:,.0f}" if harga_indo >= 1 else f"Rp {harga_indo:,.4f}"
                            harga_global_idr_str = f"Rp {harga_global_idr:,.0f}" if harga_global_idr >= 1 else f"Rp {harga_global_idr:,.4f}"
                            
                            hasil_arbitrase.append({'Koin': koin, 'Harga Indodax': harga_indo_str, 'Harga Global': harga_global_idr_str, 'Status Harga': selisih_pct})
                        except:
                            pass 
                
                if hasil_arbitrase:
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
                else:
                    st.warning("Tidak dapat membandingkan harga. Mungkin koin yang Anda pilih adalah koin lokal yang tidak terdaftar di bursa Global.")
            except:
                st.error("Terjadi kendala saat menyinkronkan data global.")

def render_dca():
    st.markdown("<h2 class='gradient-text'>⏳ Mesin DCA Institusi (Smart DCA)</h2>", unsafe_allow_html=True)
    st.info("Bandingkan menabung buta (DCA Klasik) vs Menabung menggunakan kecerdasan buatan (Smart DCA).")
    
    df_indo = fetch_indodax_live()
    semua_koin = sorted(df_indo['ID'].tolist()) if not df_indo.empty else ["BTC", "ETH", "SOL", "DOGE"]
    
    with st.form("dca_form"):
        c1, c2, c3 = st.columns(3)
        coin_pilihan = c1.selectbox("Pilih Aset Historis (Semua Koin Indodax)", semua_koin, index=semua_koin.index('BTC') if 'BTC' in semua_koin else 0)
        nabung_rutin = c2.number_input("Alokasi Mingguan (Rp)", min_value=100000, value=1000000, step=100000)
        durasi_bulan = c3.slider("Backtest Berapa Bulan Lalu?", 6, 48, 12)
        btn = st.form_submit_button("Simulasi Perang Algoritma", width="stretch")
        
    if btn:
        with st.spinner("Memutar waktu ke masa lalu dan mengeksekusi ratusan transaksi..."):
            try:
                df_hist = yf.download(f"{coin_pilihan}-USD", period=f"{durasi_bulan}mo", interval="1d", progress=False)['Close'].dropna()
                
                if df_hist.empty:
                    st.error(f"⚠️ Maaf, sejarah harga untuk koin '{coin_pilihan}' tidak tersedia di database Global (Hanya ada di Indodax).")
                    return
                    
                df_hist = df_hist.to_frame(name='Price')
                df_hist['RSI'] = calculate_rsi(df_hist['Price'], 14)
                df_weekly = df_hist.resample('W').last().dropna()
                
                total_koin_dumb, total_modal_dumb = 0, 0
                total_koin_smart, total_modal_smart = 0, 0
                
                for index, row in df_weekly.iterrows():
                    price_idr = float(row['Price']) * 16000
                    rsi = float(row['RSI'])
                    
                    total_koin_dumb += nabung_rutin / price_idr
                    total_modal_dumb += nabung_rutin
                    
                    if rsi < 40:
                        total_koin_smart += (nabung_rutin * 2) / price_idr
                        total_modal_smart += (nabung_rutin * 2)
                    elif rsi > 70:
                        pass
                    else:
                        total_koin_smart += nabung_rutin / price_idr
                        total_modal_smart += nabung_rutin
                        
                harga_sekarang_idr = float(df_weekly['Price'].iloc[-1]) * 16000
                nilai_dumb = total_koin_dumb * harga_sekarang_idr
                profit_dumb_pct = ((nilai_dumb - total_modal_dumb) / total_modal_dumb) * 100
                nilai_smart = total_koin_smart * harga_sekarang_idr
                profit_smart_pct = ((nilai_smart - total_modal_smart) / total_modal_smart) * 100 if total_modal_smart > 0 else 0
                
                st.markdown("### Hasil Tarung Strategi")
                col_d, col_s = st.columns(2)
                with col_d:
                    st.error("🤖 Klasik DCA (Nabung Buta)")
                    st.metric("Modal Keluar", f"Rp {total_modal_dumb:,.0f}")
                    st.metric("Nilai Portofolio", f"Rp {nilai_dumb:,.0f}", f"{profit_dumb_pct:.2f}%")
                with col_s:
                    st.success("🧠 Smart DCA (Logika RSI)")
                    st.metric("Modal Keluar (Fleksibel)", f"Rp {total_modal_smart:,.0f}")
                    st.metric("Nilai Portofolio", f"Rp {nilai_smart:,.0f}", f"{profit_smart_pct:.2f}%")
            except:
                st.error(f"Gagal melakukan simulasi. Data historis untuk {coin_pilihan} kemungkinan tidak tersedia.")

def render_prediksi_kripto():
    st.markdown("<h2 class='gradient-text'>🎯 Auto-Fibonacci & Pivot Target</h2>", unsafe_allow_html=True)
    st.info("Algoritma ini mengukur jarak titik tertinggi dan terendah 30 hari terakhir untuk mencetak garis Target Beli dan Jual menggunakan Rasio Emas Matematika.")
    
    df_indo = fetch_indodax_live()
    semua_koin = sorted(df_indo['ID'].tolist()) if not df_indo.empty else ["BTC", "ETH", "SOL", "PEPE", "DOGE"]
    koin_prediksi = st.selectbox("Pilih Koin untuk Diukur (Semua Koin Indodax):", semua_koin, index=semua_koin.index('BTC') if 'BTC' in semua_koin else 0)
    
    if st.button("📏 Pasang Jaring Fibonacci", use_container_width=True):
        with st.spinner("Menarik garis matematika presisi tinggi..."):
            try:
                df_hist = yf.download(f"{koin_prediksi}-USD", period="30d", progress=False)['Close'].dropna()
                
                if df_hist.empty:
                    st.error(f"⚠️ Maaf, grafik {koin_prediksi} tidak bisa diakses karena koin ini adalah koin lokal yang belum terdaftar di database Global.")
                    return
                    
                df_hist = df_hist.to_frame(name='Price')
                df_hist['Date'] = df_hist.index
                df_hist['Price'] = df_hist['Price'] * 16000 
                
                tinggi = df_hist['Price'].max()
                rendah = df_hist['Price'].min()
                selisih = tinggi - rendah
                harga_sekarang = df_hist['Price'].iloc[-1]
                
                level_fib = {
                    'Pucuk Tertinggi (0%)': tinggi,
                    'Target Jual 2 (23.6%)': tinggi - 0.236 * selisih,
                    'Target Jual 1 (38.2%)': tinggi - 0.382 * selisih,
                    'Garis Emas / Titik Tengah (50%)': tinggi - 0.5 * selisih,
                    'Support Pantulan (61.8%)': tinggi - 0.618 * selisih,
                    'Support Kuat (78.6%)': tinggi - 0.786 * selisih,
                    'Dasar Bawah (100%)': rendah
                }
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_hist['Date'], y=df_hist['Price'], mode='lines', name='Pergerakan Harga', line=dict(color='#2563EB', width=2)))
                
                colors = ['#EF4444', '#F97316', '#FBBF24', '#A3A3A3', '#34D399', '#10B981', '#1E293B']
                for (nama_level, nilai), warna in zip(level_fib.items(), colors):
                    nilai_str = f"Rp {nilai:,.0f}" if nilai >= 1 else f"Rp {nilai:,.4f}"
                    fig.add_hline(y=nilai, line_dash="dash", line_color=warna, annotation_text=f"{nama_level}: {nilai_str}", annotation_position="right")
                
                fig.update_layout(title=f"X-Ray Fibonacci 30 Hari: {koin_prediksi}/IDR", template="plotly_white", height=500)
                st.plotly_chart(fig, use_container_width=True)
            except:
                st.error("Gagal menarik data Fibonacci.")

def render_adu_kripto():
    st.markdown("<h2 class='gradient-text'>⚔️ Adu Kripto (Pair Comparison)</h2>", unsafe_allow_html=True)
    st.info("Melihat koin mana yang tumbuh lebih cepat jika keduanya dimulai dari titik 0% di waktu yang sama (Normalisasi).")
    
    df_indo = fetch_indodax_live()
    semua_koin = sorted(df_indo['ID'].tolist()) if not df_indo.empty else ["BTC", "ETH", "SOL", "ADA"]
    
    c1, c2 = st.columns(2)
    koin1 = c1.selectbox("Koin Penantang 1:", semua_koin, index=semua_koin.index('BTC') if 'BTC' in semua_koin else 0)
    koin2 = c2.selectbox("Koin Penantang 2:", semua_koin, index=semua_koin.index('ETH') if 'ETH' in semua_koin else 1)
    durasi = st.selectbox("Durasi Pertarungan:", ["1mo", "3mo", "6mo"], format_func=lambda x: f"{x.replace('mo', ' Bulan Terakhir')}")
    
    if st.button("⚔️ Mulai Pertarungan Chart", use_container_width=True):
        with st.spinner("Memproses grafik perbandingan..."):
            try:
                df1 = yf.download(f"{koin1}-USD", period=durasi, progress=False)['Close'].dropna()
                df2 = yf.download(f"{koin2}-USD", period=durasi, progress=False)['Close'].dropna()
                
                if df1.empty or df2.empty:
                    st.error("⚠️ Gagal: Salah satu koin yang Anda pilih tidak tersedia di database Global.")
                    return
                
                df1_norm = (df1 / df1.iloc[0]) * 100
                df2_norm = (df2 / df2.iloc[0]) * 100
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df1_norm.index, y=df1_norm.values, name=koin1, line=dict(width=3)))
                fig.add_trace(go.Scatter(x=df2_norm.index, y=df2_norm.values, name=koin2, line=dict(width=3)))
                fig.update_layout(title="Perbandingan Pertumbuhan (% Persentase)", yaxis_title="Pertumbuhan (Base 100)", template="plotly_white", hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)
            except:
                st.error("Gagal menarik data grafik. Koin mungkin tidak tersedia.")

def render_korelasi_kripto():
    st.markdown("<h2 class='gradient-text'>🧬 Matriks Korelasi Kripto</h2>", unsafe_allow_html=True)
    st.info("Peta panas (Heatmap) ini mendeteksi seberapa kuat koin bergerak bersamaan.")
    
    df_indo = fetch_indodax_live()
    semua_koin = sorted(df_indo['ID'].tolist()) if not df_indo.empty else ["BTC", "ETH", "SOL", "DOGE", "XRP"]
    default_coins = [c for c in ['BTC', 'ETH', 'SOL', 'DOGE', 'XRP', 'LINK'] if c in semua_koin]
    
    selected_coins = st.multiselect("Pilih Koin untuk di-Scan DNA-nya:", semua_koin, default=default_coins)
    
    if st.button("🧬 Pindai DNA Market", use_container_width=True):
        if len(selected_coins) < 2:
            st.warning("Pilih minimal 2 koin untuk melihat korelasinya.")
            return
            
        with st.spinner("Mengunduh data pergerakan..."):
            try:
                tickers = [f"{c}-USD" for c in selected_coins]
                df = yf.download(tickers, period="3mo", progress=False)['Close'].dropna()
                
                if df.empty:
                    st.error("Data tidak tersedia untuk koin yang dipilih.")
                    return
                    
                df.columns = [c.replace('-USD', '') for c in df.columns]
                corr_matrix = df.corr()
                fig = px.imshow(corr_matrix, text_auto=True, color_continuous_scale='RdBu_r', aspect="auto")
                fig.update_layout(title="Heatmap Korelasi (3 Bulan Terakhir)", template="plotly_white")
                st.plotly_chart(fig, use_container_width=True)
            except:
                st.error("Gagal memuat matriks. Kemungkinan ada koin lokal yang tidak punya data global.")

# PERBAIKAN: Memasukkan SELURUH Koin Indodax ke dalam Sektor Narasi
def render_rotasi_narasi():
    st.markdown("<h2 class='gradient-text'>🎡 Peta Rotasi Sektor Kripto</h2>", unsafe_allow_html=True)
    st.info("Menganalisis data live Indodax untuk melihat sektor mana yang sedang ramai disuntik dana.")
    
    df = fetch_indodax_live()
    if df.empty: return
    
    semua_koin_live = df['ID'].tolist()
    
    sektor_map = {
        'Layer-1 Utama': ['BTC', 'ETH', 'SOL', 'ADA', 'AVAX', 'DOT', 'NEAR', 'TRX', 'APT', 'FTM'],
        'Koin Meme': ['DOGE', 'SHIB', 'PEPE', 'FLOKI', 'BONK', 'MEME', 'WIF', 'BOME'],
        'Keuangan DeFi': ['UNI', 'LINK', 'AAVE', 'MKR', 'COMP', 'CRV', 'SNX', 'RNDR'],
        'Gaming & Metaverse': ['SAND', 'MANA', 'GALA', 'AXS', 'ENJ', 'IMX', 'ILV', 'ALICE']
    }
    
    # Mencari koin yang sudah terpetakan di atas
    koin_terkategori = []
    for k_list in sektor_map.values():
        koin_terkategori.extend(k_list)
        
    # Koin sisanya otomatis dimasukkan ke "Altcoin Lainnya" agar volume 100% terbaca
    koin_sisa = [c for c in semua_koin_live if c not in koin_terkategori]
    sektor_map['Altcoin Campuran (Lainnya)'] = koin_sisa
    
    hasil_sektor = []
    for sektor, koin_list in sektor_map.items():
        df_sektor = df[df['ID'].isin(koin_list)]
        if not df_sektor.empty:
            avg_bounce = df_sektor['Bounce_Pct'].mean()
            total_vol = df_sektor['Vol_IDR'].sum() / 1e9 
            hasil_sektor.append({'Sektor/Narasi': sektor, 'Rata-rata Pantulan': avg_bounce, 'Total Uang Masuk (Miliar)': total_vol})
            
    if hasil_sektor:
        df_hasil = pd.DataFrame(hasil_sektor).sort_values(by='Total Uang Masuk (Miliar)', ascending=False)
        fig = px.bar(df_hasil, x='Sektor/Narasi', y='Total Uang Masuk (Miliar)', color='Rata-rata Pantulan', 
                     color_continuous_scale=['#1E293B', '#10B981', '#EF4444'], text_auto='.2s',
                     title="Aliran Dana Keseluruhan Per Sektor Hari Ini")
        st.plotly_chart(fig, use_container_width=True)

def render_peta_kripto():
    st.markdown("<h2 class='gradient-text'>🌐 Peta Panas Indodax (Heatmap)</h2>", unsafe_allow_html=True)
    st.info("Visualisasi pergerakan seluruh market Rupiah (IDR) dalam satu layar.")
    df = fetch_indodax_live()
    if df.empty: return
    df_valid = df[df['Vol_IDR'] > 0].copy()
    if df_valid.empty: return
    
    fig = px.treemap(df_valid.head(50), path=[px.Constant("Market Indodax (IDR)"), 'ID'], values='Vol_IDR', 
                     color='Bounce_Pct', hover_data=['Last_Price'], 
                     color_continuous_scale=['#1E293B', '#10B981', '#EF4444'], color_continuous_midpoint=5)
    fig.update_layout(margin=dict(t=30, l=0, r=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

def render_kripto_news():
    st.markdown("<h2 class='gradient-text'>📰 Berita Fundamental Kripto</h2>", unsafe_allow_html=True)
    st.info("Membaca langsung dari portal berita kripto ternama di Indonesia untuk memberikan Anda rangkuman sentimen pasar secara otomatis.")
    
    if st.button("📰 Tarik Berita Kripto Terkini", use_container_width=True):
        with st.spinner("Menyadap artikel terbaru dari media kripto Indonesia..."):
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                
                url = "https://coinvestasi.com/feed" 
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                
                with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
                    raw_xml = response.read().decode('utf-8')
                    root = ET.fromstring(raw_xml)
                    
                    count = 0
                    for item in root.findall('./channel/item'):
                        title = item.find('title').text
                        link = item.find('link').text
                        pubDate = item.find('pubDate').text
                        
                        description = item.find('description')
                        desc_text = description.text if description is not None else "Tidak ada ringkasan yang tersedia."
                        desc_clean = clean_html_text(desc_text)
                        
                        if len(desc_clean) > 250:
                            desc_clean = desc_clean[:250] + "..."
                        
                        with st.expander(f"🔴 {title}"):
                            st.caption(f"📅 **Waktu Tayang:** {pubDate}")
                            st.markdown(f"**💡 Penjelasan Singkat:**")
                            st.info(desc_clean)
                            st.markdown(f"🔗 [Baca Artikel Lengkapnya di Sini]({link})")
                        
                        count += 1
                        if count >= 7: 
                            break
                            
                    if count == 0:
                        st.warning("Belum ada berita terbaru hari ini.")
                        
            except Exception as e:
                try:
                    url2 = "https://blockchainmedia.id/feed/"
                    req2 = urllib.request.Request(url2, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req2, context=ctx, timeout=15) as response:
                        raw_xml = response.read().decode('utf-8')
                        root = ET.fromstring(raw_xml)
                        
                        count = 0
                        for item in root.findall('./channel/item'):
                            title = item.find('title').text
                            link = item.find('link').text
                            pubDate = item.find('pubDate').text
                            description = item.find('description')
                            desc_text = description.text if description is not None else "Tidak ada ringkasan yang tersedia."
                            desc_clean = clean_html_text(desc_text)
                            
                            if len(desc_clean) > 250: desc_clean = desc_clean[:250] + "..."
                            
                            with st.expander(f"🔴 {title}"):
                                st.caption(f"📅 **Waktu Tayang:** {pubDate}")
                                st.markdown(f"**💡 Penjelasan Singkat:**")
                                st.info(desc_clean)
                                st.markdown(f"🔗 [Baca Artikel Lengkapnya di Sini]({link})")
                            
                            count += 1
                            if count >= 7: break
                except Exception as e2:
                    st.error(f"Gagal menarik berita berbahasa Indonesia. Semua server target sedang sibuk. (Detail: {e2})")

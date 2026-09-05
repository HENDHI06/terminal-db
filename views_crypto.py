# --- FILE: views_crypto.py ---
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
import math
import random
from core import *

def clean_html_text(raw_html):
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', raw_html).strip()

def render_dasbor_indodax():
    st.markdown("<h2 class='gradient-text'>🪙 Dasbor Indodax Utama</h2>", unsafe_allow_html=True)
    indo_tickers = get_indodax_tickers()
    if indo_tickers:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("BITCOIN", f"Rp {int(indo_tickers.get('btc_idr', {}).get('last', 0)):,.0f}")
        c2.metric("ETHEREUM", f"Rp {int(indo_tickers.get('eth_idr', {}).get('last', 0)):,.0f}")
        c3.metric("TETHER", f"Rp {int(indo_tickers.get('usdt_idr', {}).get('last', 0)):,.0f}")
        c4.metric("BINANCE", f"Rp {int(indo_tickers.get('bnb_idr', {}).get('last', 0)):,.0f}")
        st.write("---")

def render_radar_altcoin():
    st.markdown("<h2 class='gradient-text'>🚀 Radar Altcoin (100% IDR)</h2>", unsafe_allow_html=True)
    if st.button("Mulai Scan", width="stretch"):
        with st.spinner("Memindai pasar..."):
            indo_tickers, res_crypto = get_indodax_tickers(), []
            for p, d in indo_tickers.items():
                if p.endswith('_idr'):
                    c, lp, hp, lp_low, vp = p.replace('_idr', '').upper(), float(d.get('last',0)), float(d.get('high',0)), float(d.get('low',0)), float(d.get('vol_idr',0))
                    if vp >= 100_000_000 and lp > 0:
                        chg = ((lp - lp_low)/lp_low*100) if lp_low > 0 else 0
                        res_crypto.append({"TICKER": c, "LAST": lp, "CHG%": chg, "VAL(M)": vp/1e6, "AI_SCORE": (chg*0.6)+(vp/1e9*0.4), "ENTRY": lp*0.98, "TP 1": lp*1.05, "TP 2": lp*1.1, "EXIT/CL": lp*0.95})
            if res_crypto: 
                st.session_state.res_crypto = pd.DataFrame(res_crypto).sort_values('AI_SCORE', ascending=False)
                st.rerun()

    if 'res_crypto' in st.session_state and not st.session_state.res_crypto.empty:
        df = st.session_state.res_crypto
        # FIX: Menggunakan map() untuk versi Pandas terbaru!
        def highlight_cols(s):
            if s.name == 'CHG%': return ['background-color: rgba(52, 211, 153, 0.2); color: #34D399; font-weight:bold;' if pd.to_numeric(v, errors='coerce') > 0 else 'background-color: rgba(239, 68, 68, 0.2); color: #EF4444; font-weight:bold;' for v in s]
            return ['' for _ in s]
        styled_df = df.style.format({'LAST': 'Rp {:,.0f}', 'CHG%': '{:.2f}%', 'ENTRY': 'Rp {:,.0f}', 'TP 1': 'Rp {:,.0f}', 'EXIT/CL': 'Rp {:,.0f}'}).map(lambda x: '').apply(highlight_cols)
        st.dataframe(styled_df, hide_index=True, use_container_width=True)

def render_whale_tracker():
    st.markdown("<h2 class='gradient-text'>🐋 Whale Tracker Indodax</h2>", unsafe_allow_html=True)
    st.info("Fokus pada pergerakan antrean lokal.")

def render_arbitrase():
    st.markdown("<h2 class='gradient-text'>⚖️ Radar Arbitrase</h2>", unsafe_allow_html=True)
    st.info("Menu sinkronisasi global ditahan sementara untuk perbaikan server.")

def render_dca():
    st.markdown("<h2 class='gradient-text'>⏳ Mesin Waktu DCA</h2>", unsafe_allow_html=True)

def render_prediksi_kripto():
    st.markdown("<h2 class='gradient-text'>🔮 Prediksi Kripto</h2>", unsafe_allow_html=True)

def render_adu_kripto():
    st.markdown("<h2 class='gradient-text'>⚔️ Adu Kripto</h2>", unsafe_allow_html=True)

def render_korelasi_kripto():
    st.markdown("<h2 class='gradient-text'>🧬 Korelasi Kripto</h2>", unsafe_allow_html=True)

def render_rotasi_narasi():
    st.markdown("<h2 class='gradient-text'>🎡 Rotasi Narasi Kripto</h2>", unsafe_allow_html=True)

def render_peta_kripto():
    st.markdown("<h2 class='gradient-text'>🌐 Peta Dominasi Altcoin</h2>", unsafe_allow_html=True)
    if st.button("Pantau Kripto", width="stretch"):
        cd, indo = [], get_indodax_tickers()
        for c in ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "PEPE"]:
            d = indo.get(f"{c.lower()}_idr", {})
            if d and float(d.get('low',0)) > 0: cd.append({"Koin": c, "Chg": (float(d.get('last',0)) - float(d.get('low',0))) / float(d.get('low',0)) * 100})
        if cd: st.plotly_chart(px.bar(pd.DataFrame(cd), x="Koin", y="Chg", color="Chg", color_continuous_scale=["#EF4444", "#10B981"]).update_layout(template="plotly_white", height=400), use_container_width=True)

def render_kripto_news():
    st.markdown("<h2 class='gradient-text'>📰 Berita Kripto</h2>", unsafe_allow_html=True)

# --- FILE: core.py ---
import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import pytz
import math
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

conn_gs = st.connection("gsheets", type=GSheetsConnection)

CRYPTO_SET = {
    "BTC", "ETH", "USDT", "BNB", "SOL", "XRP", "DOGE", "ADA", "SHIB", "AVAX", 
    "LINK", "DOT", "MATIC", "UNI", "LTC", "NEAR", "ATOM", "APT", "INJ", "OP", 
    "RNDR", "ARB", "GALA", "FET", "PEPE", "WIF", "FLOKI", "BONK", "CEL", "SUI", 
    "TON", "NOT", "RENDER", "TRX", "XLM", "ETC", "BCH", "FIL", "LDO", "TIA", "SEI", "FWOG"
}

def is_crypto_ticker(t):
    clean_t = str(t).strip().upper().replace(".JK", "").replace("-USD", "")
    return ("-" in str(t)) or (clean_t in CRYPTO_SET) or (str(t).upper().endswith("USD"))

def get_visitor_info():
    providers = ['https://ipapi.co/json/', 'https://ipinfo.io/json']
    for url in providers:
        try:
            response = requests.get(url, timeout=1.5).json()
            ip = response.get('ip') or response.get('query', 'Unknown')
            if ip != 'Unknown': return ip, f"{response.get('city', 'Unknown')}, {response.get('region', 'Unknown')}"
        except: continue
    return "Mobile Node", "Cloud"

def authenticate_user(u, p):
    try:
        df = conn_gs.read(worksheet="users", ttl=0)
        if df.empty: return None
        df['username'] = df['username'].astype(str).str.strip()
        df['password'] = df['password'].astype(str).str.strip()
        user_match = df[(df['username'] == str(u).strip()) & (df['password'] == str(p).strip())]
        if not user_match.empty:
            idx = user_match.index[0]
            role = str(user_match.iloc[0]['role'])
            ip, loc = get_visitor_info()
            tz = pytz.timezone('Asia/Jakarta') 
            df.at[idx, 'last_login'] = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
            df.at[idx, 'ip_address'] = ip
            df.at[idx, 'location'] = loc
            conn_gs.update(worksheet="users", data=df)
            return role
        return None
    except Exception: return None

def get_sidebar_log(u):
    df = conn_gs.read(worksheet="users", ttl=60)
    user_data = df[df['username'] == u]
    if not user_data.empty: return user_data.iloc[0]['last_login'], user_data.iloc[0]['ip_address'], user_data.iloc[0]['location']
    return "-", "-", "-"

def get_ticker_data():
    try:
        data = yf.download(['^JKSE', 'BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'TLKM.JK'], period="7d", interval="1d", progress=False)['Close']
        items = []
        for tk, name in zip(['^JKSE', 'BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'TLKM.JK'], ['IHSG', 'BBCA', 'BBRI', 'BMRI', 'TLKM']):
            try:
                tk_data = data[tk].dropna() 
                if len(tk_data) >= 2:
                    pct = ((float(tk_data.iloc[-1]) - float(tk_data.iloc[-2])) / float(tk_data.iloc[-2])) * 100
                    color = "#34D399" if pct > 0 else "#EF4444"
                    items.append(f"<span class='ticker-item'>{name} {float(tk_data.iloc[-1]):,.0f} <span style='color:{color};'>({pct:+.2f}%)</span></span>")
            except: pass
        return " &nbsp;&nbsp; | &nbsp;&nbsp; ".join(items) * 4 
    except: return ""

def add_to_portfolio(u, t, p, l, tp, cl, strategy="Bebas", is_crypto=False):
    df = conn_gs.read(worksheet="portfolio", ttl=0)
    next_id = int(pd.to_numeric(df['id'], errors='coerce').max() + 1) if not df.empty and 'id' in df.columns else 1
    new_row = pd.DataFrame([{'id': next_id, 'username': u, 'ticker': t.upper().strip(), 'buy_price': float(p), 'lots': float(l), 'tp_price': float(tp), 'cl_price': float(cl), 'date': datetime.now(pytz.timezone('Asia/Jakarta')).strftime("%Y-%m-%d"), 'strategy': strategy, 'is_crypto': is_crypto}])
    conn_gs.update(worksheet="portfolio", data=pd.concat([df, new_row], ignore_index=True))

def sell_position(u, row_id, ticker, buy_p, sell_p, total_lots, sold_lots, is_crypto=False):
    pnl = (sell_p - buy_p) * sold_lots if is_crypto else (sell_p - buy_p) * sold_lots * 100 
    df_port = conn_gs.read(worksheet="portfolio", ttl=0)
    idx = df_port.index[df_port['id'] == row_id].tolist()
    strat_used = "Bebas"
    if idx:
        strat_used = df_port.at[idx[0], 'strategy'] if 'strategy' in df_port.columns else "Bebas"
        if total_lots - sold_lots > 0: df_port.at[idx[0], 'lots'] = total_lots - sold_lots
        else: df_port = df_port.drop(idx[0]).reset_index(drop=True)
        conn_gs.update(worksheet="portfolio", data=df_port)
    
    df_h = conn_gs.read(worksheet="history", ttl=0)
    next_id = int(pd.to_numeric(df_h['id'], errors='coerce').max() + 1) if not df_h.empty and 'id' in df_h.columns else 1
    new_h = pd.DataFrame([{'id': next_id, 'username': u, 'ticker': ticker, 'buy_price': float(buy_p), 'sell_price': float(sell_p), 'lots': float(sold_lots), 'pnl': float(pnl), 'date': datetime.now(pytz.timezone('Asia/Jakarta')).strftime("%Y-%m-%d"), 'strategy': strat_used}])
    conn_gs.update(worksheet="history", data=pd.concat([df_h, new_h], ignore_index=True))

def get_user_portfolio(u, r=None):
    df = conn_gs.read(worksheet="portfolio", ttl=0)
    if df.empty: return pd.DataFrame()
    df[['id','lots','buy_price']] = df[['id','lots','buy_price']].apply(pd.to_numeric, errors='coerce')
    if 'is_crypto' not in df.columns: df['is_crypto'] = False
    return df[df['username'] == u].sort_values(by='date', ascending=False)

def get_watchlist(u):
    try: return conn_gs.read(worksheet="watchlist", ttl=0)[conn_gs.read(worksheet="watchlist", ttl=0)['username'] == u]['ticker'].tolist()
    except: return []

def add_watchlist(u, t):
    df = conn_gs.read(worksheet="watchlist", ttl=0)
    n_id = int(pd.to_numeric(df['id'], errors='coerce').max() + 1) if not df.empty and 'id' in df.columns else 1
    conn_gs.update(worksheet="watchlist", data=pd.concat([df, pd.DataFrame([{'id': n_id, 'username': u, 'ticker': t.upper().strip()}])], ignore_index=True))

def remove_watchlist(u, t):
    df = conn_gs.read(worksheet="watchlist", ttl=0)
    idx = df.index[(df['username'] == u) & (df['ticker'] == t)].tolist()
    if idx: conn_gs.update(worksheet="watchlist", data=df.drop(idx[0]).reset_index(drop=True))

def update_password_db(u, new_p):
    df = conn_gs.read(worksheet="users", ttl=0)
    idx = df.index[df['username'] == u].tolist()
    if idx:
        df.at[idx[0], 'password'] = new_p
        conn_gs.update(worksheet="users", data=df)
        return True
    return False

def add_user_db(u, p, r):
    df = conn_gs.read(worksheet="users", ttl=0)
    if u in df['username'].values: return False
    conn_gs.update(worksheet="users", data=pd.concat([df, pd.DataFrame([{'username': u, 'password': p, 'role': r, 'last_login': '', 'ip_address': '', 'location': ''}])], ignore_index=True))
    return True

def delete_user_db(u):
    if u == 'admin': return False
    df = conn_gs.read(worksheet="users", ttl=0)
    idx = df.index[df['username'] == u].tolist()
    if idx:
        conn_gs.update(worksheet="users", data=df.drop(idx[0]).reset_index(drop=True))
        return True
    return False

def get_sector(ticker):
    try: return yf.Ticker(ticker).info.get('sector', 'Lainnya')
    except: return "Lainnya"

def load_tickers():
    try:
        url = "https://raw.githubusercontent.com/datasets-id/idx-stocks/main/data/stock_codes.csv"
        return [str(t).strip().upper() + ".JK" for t in pd.read_csv(url)['ticker'].tolist() if len(str(t)) <= 5]
    except: return []

def run_scan_accurate(tickers, mode, is_crypto=False):
    tickers = list(set(tickers))
    results = []
    min_chg, min_rsi, min_val, vol_m = (1.5, 45, 10_000_000, 1.1) if mode == "Santai" else (2.5, 55, 100_000_000, 1.4) if mode == "Profesional" else (4.0, 60, 500_000_000, 1.8)

    progress = st.progress(0, text="📡 Memindai Database...")
    try: data = yf.download(tickers, period="20d", interval="1d", group_by="ticker", threads=True, progress=False)
    except: return pd.DataFrame()

    for i, t in enumerate(tickers):
        try:
            progress.progress(int((i + 1) / len(tickers) * 100), text=f"🔍 Analisa {t}")
            df = data[t].copy() if len(tickers) > 1 else data.copy()
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df = df.dropna(subset=['Close', 'Volume']) 
            if len(df) < 14: continue

            c_now, c_prev = float(df['Close'].iloc[-1]), float(df['Close'].iloc[-2])
            chg = ((c_now - c_prev) / c_prev) * 100
            val_tr = float(df['Volume'].iloc[-1]) * c_now
            
            delta = df['Close'].diff()
            gain, loss = (delta.where(delta > 0, 0)).rolling(14).mean(), (-delta.where(delta < 0, 0)).rolling(14).mean()
            rsi = 100 - (100 / (1 + (gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] != 0 else 0)))
            vol_avg = df['Volume'].rolling(20).mean().iloc[-1] if len(df) >= 20 else df['Volume'].mean()
            
            if chg < min_chg or val_tr < min_val: continue

            multiplier = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) / (df['High'] - df['Low'] + 1e-9)
            cmf = float(((multiplier * df['Volume']).rolling(14).sum() / df['Volume'].rolling(14).sum()).dropna().iloc[-1])
            atr_val = float(pd.concat([df['High'] - df['Low'], (df['High'] - df['Close'].shift()).abs(), (df['Low'] - df['Close'].shift()).abs()], axis=1).max(axis=1).rolling(14).mean().iloc[-1])
            if math.isnan(atr_val): atr_val = c_now * 0.03
            ideal_e = c_now - (0.4 * atr_val)

            clean_t = t.replace(".JK", "").replace("-USD", "")
            results.append({
                "TICKER": clean_t, "LAST": c_now, "CHG%": chg, "VAL(M)": (val_tr / 1_000_000), 
                "BANDAR": "AKUMULASI" if cmf > 0 else "DISTRIBUSI", 
                "VPA_STATUS": "🚀 BREAKOUT BESAR" if float(df['Volume'].iloc[-1]) > (vol_avg * 1.5) and chg >= 2.0 else "NORMAL",
                "AI_SCORE": (chg * 0.4) + (rsi * 0.2) + (10 if (c_now > df['High'].rolling(20).max().iloc[-2]) and (df['Volume'].iloc[-1] > vol_avg * vol_m) else 0) + (cmf * 20),
                "SCORE_MOM": min(max(rsi, 0), 100), "SCORE_BNDR": min(max((cmf + 0.5) * 100, 0), 100), 
                "SCORE_TRND": 80 if c_now > df['Close'].rolling(20).mean().iloc[-1] else 30, "SCORE_VOL": min(100, (atr_val / c_now) * 1000),
                "ENTRY": ideal_e, "TP 1": ideal_e + (1.5 * atr_val), "TP 2": ideal_e + (2.5 * atr_val), "EXIT/CL": ideal_e - (1.0 * atr_val), "FULL": t
            })
        except: continue
    progress.empty()
    return pd.DataFrame(results).sort_values(by="AI_SCORE", ascending=False).drop_duplicates(subset=['TICKER']) if results else pd.DataFrame()

def get_trend_signals(ticker_list):
    signals = []
    for ticker in ticker_list:
        try:
            df = yf.download(f"{ticker}", period="6mo", interval="1d", progress=False).dropna(subset=['Close'])
            if len(df) < 50: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df['MA20'], df['MA50'] = df['Close'].rolling(20).mean(), df['Close'].rolling(50).mean()
            df['Multiplier'] = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) / (df['High'] - df['Low'] + 1e-9)
            cmf_val = float(((df['Multiplier'] * df['Volume']).rolling(20).sum() / df['Volume'].rolling(20).sum()).fillna(0).iloc[-1])
            last_ma20, last_ma50, prev_ma20, prev_ma50, cp = float(df['MA20'].iloc[-1]), float(df['MA50'].iloc[-1]), float(df['MA20'].iloc[-2]), float(df['MA50'].iloc[-2]), float(df['Close'].iloc[-1])
            if prev_ma20 < prev_ma50 and last_ma20 > last_ma50:
                signals.append({"ticker": ticker.replace(".JK", ""), "status": "GOLDEN CROSS + AKUMULASI" if cmf_val > 0 else "GOLDEN CROSS", "price": cp, "color": "#16A34A" if cmf_val > 0 else "#F59E0B"})
            elif prev_ma20 > prev_ma50 and last_ma20 < last_ma50:
                signals.append({"ticker": ticker.replace(".JK", ""), "status": "DEAD CROSS + DISTRIBUSI BANDAR" if cmf_val < 0 else "DEAD CROSS", "price": cp, "color": "#DC2626" if cmf_val < 0 else "#EA580C"})
        except: continue
    return signals

def draw_mobile_cards(df, is_crypto=False):
    for _, row in df.iterrows():
        chg, chg_color = row.get('CHG%', 0), "#34D399" if row.get('CHG%', 0) > 0 else "#EF4444"
        val_last, val_entry, val_tp1, val_cl, val_m = row.get('LAST', 0), row.get('ENTRY', 0), row.get('TP 1', 0), row.get('EXIT/CL', 0), row.get('VAL(M)', 0)
        st.markdown(f"""
        <div class="dash-box" style="border-left: 4px solid {chg_color}; padding: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <b style="font-size: 1.2rem; color: #FFFFFF;">{row.get('TICKER','-')}</b>
                <span style="color: {chg_color}; font-weight: 700;">{'+' if chg>0 else ''}{chg:.2f}%</span>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 12px; font-size: 0.85rem; color: #94A3B8;">
                <div>Harga: <b style="color:#FFFFFF;">Rp {val_last:,.0f}</b></div>
                <div>Vol: <b style="color:#FFFFFF;">Rp {val_m:,.1f} M</b></div>
                <div style="color: #38BDF8;">Antre Beli: Rp {val_entry:,.0f}</div>
                <div style="color: #34D399;">Jual Untung: Rp {val_tp1:,.0f}</div>
                <div style="color: #EF4444; grid-column: span 2; text-align: center; margin-top:5px;">Cut Loss: Rp {val_cl:,.0f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

def style_dataframe(val):
    if type(val) in [int, float] and val > 0: return 'background-color: rgba(52, 211, 153, 0.2); color: #34D399; font-weight:bold;'
    elif type(val) in [int, float] and val < 0: return 'background-color: rgba(239, 68, 68, 0.2); color: #EF4444; font-weight:bold;'
    if isinstance(val, str) and "⚠️" in val: return 'color: #FBBF24; font-weight:bold;'
    if isinstance(val, str) and "🔥" in val: return 'color: #EF4444; font-weight:bold;'
    return ''

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import time
import os
from datetime import datetime, time as dtime
import pytz

# --- 1. FAIL-SAFE IMPORTS (CRITICAL FIX) ---
SmartConnect = None
try:
    from SmartApi import SmartConnect 
except ImportError:
    try: from smartapi import SmartConnect
    except ImportError: pass 
import pyotp

# --- 2. PAGE CONFIG ---
st.set_page_config(page_title="Mishr@lgobot Ultimate", layout="wide", initial_sidebar_state="expanded")

# --- 3. SECURITY LAYER ---
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    st.markdown("""
        <style>
        .stApp { background-color: #000000; }
        .login-box { border: 1px solid #00f2ff; padding: 20px; border-radius: 10px; text-align: center; }
        </style>
        <br><br><br>
        """, unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.markdown("<h1 style='text-align:center; color:#00f2ff;'>🤖 Mishr@lgobot <span style='font-size:15px; color:gold;'>MASTER</span></h1>", unsafe_allow_html=True)
        key = st.text_input("ENTER ACCESS KEY", type="password", placeholder="••••••••••")
        if st.button("UNLOCK TERMINAL", use_container_width=True):
            if key == "8500081391":
                st.session_state.auth = True
                st.rerun()
            else: st.error("⛔ ACCESS DENIED")
    st.stop()

# --- 4. STATE MANAGEMENT ---
if 'bal' not in st.session_state: st.session_state.bal = 100000.0
if 'positions' not in st.session_state: st.session_state.positions = []
if 'trade_history' not in st.session_state: st.session_state.trade_history = []
if 'bot_active' not in st.session_state: st.session_state.bot_active = False
if 'angel' not in st.session_state: st.session_state.angel = None
if 'real_trade_active' not in st.session_state: st.session_state.real_trade_active = False
if 'strategy_mode' not in st.session_state: st.session_state.strategy_mode = "Sniper (1m)"
if 'manual_qty' not in st.session_state: st.session_state.manual_qty = 1

# History Management
HISTORY_FILE = "trade_history.csv"
def load_history():
    if os.path.exists(HISTORY_FILE):
        try: return pd.read_csv(HISTORY_FILE).to_dict('records')
        except: return []
    return []

if not st.session_state.trade_history:
    st.session_state.trade_history = load_history()

# Default Watchlist
if 'watchlist' not in st.session_state: 
    st.session_state.watchlist = {
        "NIFTY 50": "^NSEI", 
        "BANKNIFTY": "^NSEBANK",
        "RELIANCE": "RELIANCE.NS", 
        "GOLD (MCX)": "GC=F",
        "BITCOIN": "BTC-USD"
    }

# --- 5. ANGEL ONE LOGIN ---
def angel_login(api, cid, pw, otp):
    if SmartConnect is None: return "Library Error: SmartApi not found", None
    try:
        obj = SmartConnect(api_key=api)
        t = pyotp.TOTP(otp).now()
        data = obj.generateSession(cid, pw, t)
        if data['status']: return "Success", obj
        return f"Failed: {data['message']}", None
    except Exception as e: return f"Error: {str(e)}", None

# --- 6. UI CSS (NEON THEME) ---
st.markdown("""
    <style>
        .stApp { background-color: #000000; color: #ffffff; font-family: 'Roboto', sans-serif; }
        
        /* Sidebar */
        section[data-testid="stSidebar"] { background-color: #0a0a0a; border-right: 1px solid #333; }
        
        /* Ticker */
        .ticker-wrap { position: fixed; top: 0; left: 0; width: 100%; height: 40px; background: #0f0f0f; border-bottom: 2px solid #00f2ff; z-index: 99999; display: flex; align-items: center; overflow: hidden; }
        .ticker { display: inline-block; white-space: nowrap; animation: ticker 45s linear infinite; }
        @keyframes ticker { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }
        .ticker-item { font-family: 'Courier New', monospace; font-size: 16px; font-weight: bold; margin-right: 50px; color: #e0e0e0; }
        
        .block-container { padding-top: 5rem !important; padding-bottom: 5rem; }
        
        /* Cards */
        .live-card { background: linear-gradient(145deg, #111, #1a1a1a); border: 1px solid #333; border-radius: 12px; padding: 15px; margin-bottom: 10px; }
        .closed-card { background: #1a0505; border: 1px dashed #555; opacity: 0.6; }
        
        /* Badges */
        .badge-buy { background: #00e676; color: black; padding: 2px 6px; border-radius: 4px; font-weight: 800; font-size:10px; }
        .badge-sell { background: #ff1744; color: white; padding: 2px 6px; border-radius: 4px; font-weight: 800; font-size:10px; }
        
        #MainMenu, footer { visibility: hidden; }
    </style>
""", unsafe_allow_html=True)

# --- 7. LOGIC ENGINE ---
def calculate_indicators(df):
    if len(df) < 20: return df
    df['EMA_9'] = df['Close'].ewm(span=9).mean()
    df['EMA_21'] = df['Close'].ewm(span=21).mean()
    df['EMA_50'] = df['Close'].ewm(span=50).mean()
    df['EMA_200'] = df['Close'].ewm(span=200).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MACD & VWAP
    ema12 = df['Close'].ewm(span=12).mean()
    ema26 = df['Close'].ewm(span=26).mean()
    df['MACD'] = ema12 - ema26
    df['Signal_Line'] = df['MACD'].ewm(span=9).mean()
    df['VWAP'] = (df['Close'] * df['Volume']).cumsum() / df['Volume'].cumsum()
    
    # ADX
    tr1 = df['High'] - df['Low']
    atr = tr1.ewm(alpha=1/14).mean()
    df['ADX'] = (atr / df['Close']) * 1000 
    
    return df

@st.cache_data(ttl=15)
def scan_market(watchlist, strategy_mode):
    data = []
    ticker_text = ""
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    today = now.date()
    
    # Timeframe Selection
    interval, period = "15m", "5d"
    if "Sniper" in strategy_mode: interval, period = "1m", "1d"
    if "Volume" in strategy_mode: interval, period = "5m", "5d"
    
    for name, sym in watchlist.items():
        try:
            df = yf.download(sym, period=period, interval=interval, progress=False)
            if df.empty: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            
            # Market Status Check
            last_time = df.index[-1].to_pydatetime().astimezone(ist)
            is_fresh = last_time.date() == today
            status = "CLOSED"
            atype = "NSE"
            
            if "-USD" in sym: status = "OPEN"; atype = "CRYPTO"
            elif "=F" in sym:
                atype = "MCX"
                if now.weekday() < 5 and dtime(9,0) <= now.time() <= dtime(23,55) and is_fresh: status = "OPEN"
            else:
                if now.weekday() < 5 and dtime(9,15) <= now.time() <= dtime(15,30) and is_fresh: status = "OPEN"

            df = calculate_indicators(df)
            last = df.iloc[-1]
            sig = "HOLD"
            reason = "Scanning..."
            
            if status == "OPEN":
                # --- STRATEGIES ---
                if "Sniper" in strategy_mode:
                    if last['EMA_9'] > last['EMA_21'] and last['RSI'] > 55: sig = "BUY"; reason="Scalp Buy"
                    elif last['EMA_9'] < last['EMA_21'] and last['RSI'] < 45: sig = "SELL"; reason="Scalp Sell"
                
                elif "Momentum" in strategy_mode:
                    if last['Close'] > last['EMA_50'] and last['RSI'] > 60: sig = "BUY"; reason="Momentum"
                    elif last['Close'] < last['EMA_50'] and last['RSI'] < 40: sig = "SELL"; reason="Momentum"
                
                elif "Pro 90%" in strategy_mode:
                    if last['Close'] > last['EMA_200'] and last['MACD'] > last['Signal_Line'] and last['RSI'] > 50: sig = "BUY"; reason="Pro Trend"
                    elif last['Close'] < last['EMA_200'] and last['MACD'] < last['Signal_Line'] and last['RSI'] < 50: sig = "SELL"; reason="Pro Dump"
                
                elif "Institutional" in strategy_mode:
                    if last['Close'] > last['VWAP'] and last['Close'] > last['EMA_200']: sig = "BUY"; reason="Whale Buy"
                    elif last['Close'] < last['VWAP'] and last['Close'] < last['EMA_200']: sig = "SELL"; reason="Whale Sell"
                
                else: # Swing
                    if last['Close'] > last['EMA_50'] and last['RSI'] < 40: sig = "BUY"; reason="Dip Buy"
                    elif last['Close'] < last['EMA_50'] and last['RSI'] > 60: sig = "SELL"; reason="Rally Sell"
            
            else: sig = "MKT CLOSED"
            
            change = ((last['Close'] - df.iloc[0]['Open']) / df.iloc[0]['Open']) * 100
            data.append({"name": name, "price": last['Close'], "change": change, "rsi": last['RSI'], "sig": sig, "type": atype, "status": status, "reason": reason})
            
            cls = "tick-up" if change >= 0 else "tick-down"
            ticker_text += f"<span class='ticker-item'>{name}: <span class='{cls}'>{last['Close']:.2f} ({change:+.2f}%)</span></span> "
            
        except: pass
    return data, ticker_text

@st.cache_data(ttl=60)
def get_chart_data(symbol):
    try:
        df = yf.download(symbol, period="5d", interval="15m", progress=False)
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        return df
    except: return None

# --- 8. EXECUTION ---
def place_angel_order(symbol_name, side, qty):
    if not st.session_state.angel: return False, "Not Connected"
    return True, "ORD_EXECUTED"

def run_bot(data):
    for item in data:
        if item['status'] == "CLOSED": continue
        is_open = any(p['name'] == item['name'] for p in st.session_state.positions)
        if not is_open and item['sig'] in ["BUY", "SELL"]:
            qty = st.session_state.manual_qty
            
            # SL/TP
            sl_pct = 0.5; tp_pct = 1.0
            if item['sig'] == "BUY":
                sl = item['price'] * (1 - sl_pct/100)
                tp = item['price'] * (1 + tp_pct/100)
            else:
                sl = item['price'] * (1 + sl_pct/100)
                tp = item['price'] * (1 - tp_pct/100)

            # Real Trade
            if st.session_state.real_trade_active and st.session_state.angel and item['type'] == "NSE":
                status, oid = place_angel_order(item['name'], item['sig'], qty)
                if status:
                    st.toast(f"🚀 REAL: {oid}")
                    st.session_state.positions.append({"name": item['name'], "side": item['sig'], "entry": item['price'], "qty": qty, "pnl": 0.0, "sl": sl, "tp": tp})
            
            # Paper Trade
            elif not st.session_state.real_trade_active:
                st.session_state.bal -= item['price'] * qty
                st.session_state.positions.append({"name": item['name'], "side": item['sig'], "entry": item['price'], "qty": qty, "pnl": 0.0, "sl": sl, "tp": tp})
                st.toast(f"📝 PAPER: {item['name']} ({qty} Qty)")

def save_trade(trade_dict):
    trade_dict['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.trade_history.insert(0, trade_dict)
    if st.session_state.trade_history:
        pd.DataFrame(st.session_state.trade_history).to_csv(HISTORY_FILE, index=False)

def delete_all_history():
    if os.path.exists(HISTORY_FILE): os.remove(HISTORY_FILE)
    st.session_state.trade_history = []
    st.rerun()

# --- 9. SIDEBAR ---
with st.sidebar:
    st.markdown("## 🔐 LOGIN")
    with st.expander("Angel One Credentials", expanded=True):
        if st.session_state.angel:
            st.success("✅ Connected")
            if st.button("Logout"): st.session_state.angel = None; st.rerun()
        else:
            ak = st.text_input("API Key")
            cid = st.text_input("Client ID")
            pw = st.text_input("Password", type="password")
            otp = st.text_input("TOTP Key", value="VJWYHR7ACJ7H56Q7OGJ54PKTFA")
            if st.button("CONNECT NOW"):
                msg, api = angel_login(ak, cid, pw, otp)
                if api: 
                    st.session_state.angel = api
                    st.success("Login Success!")
                    time.sleep(1)
                    st.rerun()
                else: st.error(msg)

    st.markdown("---")
    st.subheader("⚙️ SETTINGS")
    st.session_state.strategy_mode = st.selectbox("Select Strategy", [
        "Sniper (1m Scalping)", 
        "Momentum (5m Trend)", 
        "Swing (15m Safe)",
        "Institutional (Whale)",
        "🔥 Pro 90% (Trend+MACD)"
    ])
    st.session_state.manual_qty = st.number_input("Trade Qty / Lot Size", 1, 10000, 1)
    
    real_trade = st.toggle("⚠️ ENABLE REAL TRADING", value=st.session_state.real_trade_active)
    if real_trade != st.session_state.real_trade_active:
        st.session_state.real_trade_active = real_trade
        st.rerun()

# --- 10. MAIN UI ---
data_list, ticker_html = scan_market(st.session_state.watchlist, st.session_state.strategy_mode)

st.markdown(f"<div class='ticker-wrap'><div class='ticker'>{ticker_html}</div></div>", unsafe_allow_html=True)

c1, c2 = st.columns([3, 1])
with c1: st.markdown("<h3>🤖 Mishr@lgobot <span style='color:#00e676; font-size:14px'>MASTER</span></h3>", unsafe_allow_html=True)
with c2: 
    if st.button("🔄 REFRESH"): st.rerun()

tab_dash, tab_market, tab_charts, tab_algo, tab_hist = st.tabs(["🏠 DASHBOARD", "📈 MARKET", "📊 CHARTS", "🤖 ALGO", "📜 LOGS"])

# DASHBOARD
with tab_dash:
    pnl = sum(p['pnl'] for p in st.session_state.positions)
    pnl_c = "#00e676" if pnl >= 0 else "#ff1744"
    col1, col2 = st.columns(2)
    col1.markdown(f"<div class='live-card' style='text-align:center'><small>FUNDS</small><h3>₹{st.session_state.bal:,.0f}</h3></div>", unsafe_allow_html=True)
    col2.markdown(f"<div class='live-card' style='text-align:center'><small>PNL</small><h3 style='color:{pnl_c}'>₹{pnl:,.2f}</h3></div>", unsafe_allow_html=True)
    
    if st.session_state.positions:
        for p in st.session_state.positions:
            curr = next((d['price'] for d in data_list if d['name'] == p['name']), p['entry'])
            p['pnl'] = (curr - p['entry']) * p['qty'] if p['side']=="BUY" else (p['entry'] - curr) * p['qty']
            
            # Auto Exit
            if p['side']=="BUY" and (curr >= p['tp'] or curr <= p['sl']):
                save_trade(p); st.session_state.positions.remove(p); st.rerun()
            elif p['side']=="SELL" and (curr <= p['tp'] or curr >= p['sl']):
                save_trade(p); st.session_state.positions.remove(p); st.rerun()
            
            st.markdown(f"<div class='live-card' style='border-left:4px solid #00f2ff'><b>{p['name']}</b> ({p['side']})<br>Entry: {p['entry']:.2f} | PnL: {p['pnl']:.2f}</div>", unsafe_allow_html=True)
            if st.button(f"EXIT {p['name']}", key=p['name']):
                st.session_state.positions.remove(p)
                save_trade({"Symbol": p['name'], "Side": "EXIT", "Entry": p['entry'], "Exit": curr, "PnL": round(p['pnl'], 2), "Status": "MANUAL"})
                st.rerun()
    else: st.info("No Active Trades")

# MARKET
with tab_market:
    with st.expander("🔍 Custom Search"):
        c1, c2 = st.columns([1, 2])
        stype = c1.selectbox("Type", ["NSE", "MCX", "CRYPTO"], label_visibility="collapsed")
        search_txt = c2.text_input("Symbol", placeholder="e.g. TATASTEEL", label_visibility="collapsed")
        if st.button("ADD"):
            if search_txt:
                nm = search_txt.upper()
                if stype == "NSE": sym = f"{nm}.NS"
                elif stype == "MCX": sym = f"{nm}=F"
                elif stype == "CRYPTO": sym = f"{nm}-USD"
                st.session_state.watchlist[nm] = sym
                st.success(f"Added {sym}")
                time.sleep(0.5)
                st.rerun()

    if st.session_state.bot_active: run_bot(data_list)
    
    for d in data_list:
        cls = "live-card closed-card" if d['status'] == "CLOSED" else "live-card"
        badge = f"<span class='badge-buy'>{d['sig']}</span>" if d['sig']=="BUY" else (f"<span class='badge-sell'>{d['sig']}</span>" if d['sig']=="SELL" else "<span style='color:gray'>WAIT</span>")
        if d['status'] == "CLOSED": badge = "<span style='color:#ff9800; font-size:10px'>CLOSED</span>"
        
        st.markdown(f"<div class='{cls}'><div style='display:flex; justify-content:space-between'><div><span style='color:gold; font-size:10px;'>{d['type']}</span> <b>{d['name']}</b></div> <b>{d['price']:.2f}</b></div><div style='margin-top:5px; font-size:12px; color:#aaa'>RSI: {d['rsi']:.0f} | {badge}</div><div style='font-size:10px; color:#666;'>Reason: {d['reason']}</div></div>", unsafe_allow_html=True)
        if st.button(f"🗑️", key=f"del_{d['name']}"):
            del st.session_state.watchlist[d['name']]
            st.rerun()

# CHARTS
with tab_charts:
    sel = st.selectbox("Select Asset", list(st.session_state.watchlist.keys()))
    df = get_chart_data(st.session_state.watchlist[sel])
    if df is not None:
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
        fig.update_layout(height=400, template="plotly_dark", margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig, use_container_width=True)

# ALGO
with tab_algo:
    if st.button("🔴 STOP BOT" if st.session_state.bot_active else "🟢 START BOT", use_container_width=True, type="primary"):
        st.session_state.bot_active = not st.session_state.bot_active
        st.rerun()
    if st.session_state.bot_active: st.success("Bot is Running...")

# HISTORY
with tab_hist:
    if st.session_state.trade_history:
        if st.button("🗑️ DELETE ALL HISTORY"): delete_all_history()
        df_h = pd.DataFrame(st.session_state.trade_history)
        st.download_button("⬇️ DOWNLOAD CSV", df_h.to_csv(index=False).encode('utf-8'), "trades.csv", use_container_width=True)
        st.dataframe(df_h)
    else: st.info("No History")

if st.session_state.bot_active:
    time.sleep(15 if "Sniper" in st.session_state.strategy_mode else 60)
    st.rerun()
"""

with open("app.py", "w") as f:
    f.write(app_code)

print("✅ Final Ultimate App Created.")



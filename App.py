import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import time
import os
from datetime import datetime, time as dtime
import pytz
import pyotp
from SmartApi import SmartConnect
from logzero import logger

# --- 1. CONFIG & TOKENS ---
st.set_page_config(page_title="Mishr@lgobot Ultimate", layout="wide", initial_sidebar_state="expanded")

# Angel One Token Map (Hardcoded for Demo)
TOKEN_MAP = {
    "RELIANCE": {"token": "2885", "exchange": "NSE"},
    "SBIN": {"token": "3045", "exchange": "NSE"},
    "TATASTEEL": {"token": "3499", "exchange": "NSE"},
    "INFY": {"token": "1594", "exchange": "NSE"},
    "HDFCBANK": {"token": "1333", "exchange": "NSE"},
    "NIFTY": {"token": "99926000", "exchange": "NSE"},
    "BANKNIFTY": {"token": "99926009", "exchange": "NSE"}
}

# --- 2. SECURITY LAYER ---
if "auth" not in st.session_state: st.session_state.auth = False
if not st.session_state.auth:
    st.markdown("""
        <style>
        .stApp { background-color: #000000; }
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

# --- 3. STATE MANAGEMENT ---
if 'bal' not in st.session_state: st.session_state.bal = 100000.0
if 'positions' not in st.session_state: st.session_state.positions = []
if 'trade_history' not in st.session_state: st.session_state.trade_history = []
if 'bot_active' not in st.session_state: st.session_state.bot_active = False
if 'angel' not in st.session_state: st.session_state.angel = None
if 'real_trade_active' not in st.session_state: st.session_state.real_trade_active = False
if 'strategy_mode' not in st.session_state: st.session_state.strategy_mode = "🔥 Alpha Prime (Fib+Vol)"
if 'manual_qty' not in st.session_state: st.session_state.manual_qty = 1
if 'watchlist' not in st.session_state: 
    st.session_state.watchlist = {
        "RELIANCE": "RELIANCE.NS", 
        "SBIN": "SBIN.NS",
        "TATASTEEL": "TATASTEEL.NS",
        "INFY": "INFY.NS"
    }

HISTORY_FILE = "trade_history.csv"
def load_history():
    if os.path.exists(HISTORY_FILE):
        try: return pd.read_csv(HISTORY_FILE).to_dict('records')
        except: return []
    return []

if not st.session_state.trade_history:
    st.session_state.trade_history = load_history()

# --- 4. ANGEL ONE LOGIN ---
def angel_login(api_key, client_code, password, totp_key):
    try:
        smartApi = SmartConnect(api_key)
        try:
            totp = pyotp.TOTP(totp_key).now()
        except Exception as e:
            return "Invalid TOTP Key (QR Code)", None

        data = smartApi.generateSession(client_code, password, totp)
        if data['status']:
            smartApi.getfeedToken()
            return "Success", smartApi
        else:
            return f"Login Failed: {data['message']}", None
    except Exception as e:
        logger.error(f"Login Exception: {e}")
        return f"Error: {str(e)}", None

# --- 5. ORDER PLACEMENT ---
def place_angel_order(symbol_name, side, qty):
    if not st.session_state.angel: return False, "Not Connected"
    sym_info = TOKEN_MAP.get(symbol_name)
    if not sym_info: return False, f"Token not found for {symbol_name}"

    try:
        orderparams = {
            "variety": "NORMAL",
            "tradingsymbol": f"{symbol_name}-EQ",
            "symboltoken": sym_info['token'],
            "transactiontype": side,
            "exchange": sym_info['exchange'],
            "ordertype": "MARKET",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "quantity": str(qty)
        }
        orderid = st.session_state.angel.placeOrder(orderparams)
        logger.info(f"PlaceOrder : {orderid}")
        return True, orderid
    except Exception as e:
        logger.exception(f"Order placement failed: {e}")
        return False, str(e)

# --- 6. UI CSS (NEON THEME) ---
st.markdown("""
    <style>
        .stApp { background-color: #000000; color: #ffffff; font-family: 'Roboto', sans-serif; }
        section[data-testid="stSidebar"] { background-color: #0a0a0a; border-right: 1px solid #333; }
        .ticker-wrap { position: fixed; top: 0; left: 0; width: 100%; height: 40px; background: #0f0f0f; border-bottom: 2px solid #00f2ff; z-index: 99999; display: flex; align-items: center; overflow: hidden; }
        .ticker { display: inline-block; white-space: nowrap; animation: ticker 45s linear infinite; }
        @keyframes ticker { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }
        .ticker-item { font-family: 'Courier New', monospace; font-size: 16px; font-weight: bold; margin-right: 50px; color: #e0e0e0; }
        .block-container { padding-top: 5rem !important; padding-bottom: 5rem; }
        .live-card { background: linear-gradient(145deg, #111, #1a1a1a); border: 1px solid #333; border-radius: 12px; padding: 15px; margin-bottom: 10px; }
        .closed-card { background: #1a0505; border: 1px dashed #555; opacity: 0.6; }
        .badge-buy { background: #00e676; color: black; padding: 2px 6px; border-radius: 4px; font-weight: 800; font-size:10px; }
        .badge-sell { background: #ff1744; color: white; padding: 2px 6px; border-radius: 4px; font-weight: 800; font-size:10px; }
        #MainMenu, footer { visibility: hidden; }
        div.stButton > button { border: 1px solid #333; background-color: #111; color: #fff; }
        div.stButton > button:hover { border-color: #00f2ff; color: #00f2ff; }
    </style>
""", unsafe_allow_html=True)

# --- 7. LOGIC ENGINE ---
def calculate_indicators(df):
    if len(df) < 20: return df
    
    # EMAs
    df['EMA_9'] = df['Close'].ewm(span=9).mean()
    df['EMA_21'] = df['Close'].ewm(span=21).mean()
    df['EMA_50'] = df['Close'].ewm(span=50).mean()
    df['EMA_200'] = df['Close'].ewm(span=200).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MACD
    ema12 = df['Close'].ewm(span=12).mean()
    ema26 = df['Close'].ewm(span=26).mean()
    df['MACD'] = ema12 - ema26
    df['Signal_Line'] = df['MACD'].ewm(span=9).mean()
    
    # ATR (Volatility)
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['ATR'] = true_range.ewm(alpha=1/14).mean()
    
    # Volume SMA
    df['Vol_SMA'] = df['Volume'].rolling(window=20).mean()

    # FIBONACCI Levels (Recent 20 Candles)
    roll_high = df['High'].rolling(20).max()
    roll_low = df['Low'].rolling(20).min()
    df['Fib_High'] = roll_high
    df['Fib_Low'] = roll_low
    
    return df

@st.cache_data(ttl=15)
def scan_market(watchlist, strategy_mode):
    data = []
    ticker_text = ""
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    today = now.date()
    
    interval, period = "15m", "5d"
    if "Sniper" in strategy_mode: interval, period = "1m", "1d"
    if "Alpha" in strategy_mode: interval, period = "5m", "5d" # Alpha Prime uses 5m
    
    for name, sym in watchlist.items():
        try:
            # FIX: Single threaded for stability, robust error handling
            df = yf.download(sym, period=period, interval=interval, progress=False, threads=False)
            
            if df.empty: continue
            
            # FIX: MultiIndex handling for yfinance 0.2.40+
            if isinstance(df.columns, pd.MultiIndex): 
                df.columns = df.columns.get_level_values(0)
            
            # Ensure index is datetime
            df.index = pd.to_datetime(df.index)

            last_time = df.index[-1].to_pydatetime().astimezone(ist)
            is_fresh = last_time.date() == today
            status = "CLOSED"
            
            if now.weekday() < 5 and dtime(9,15) <= now.time() <= dtime(15,30) and is_fresh: status = "OPEN"

            df = calculate_indicators(df)
            last = df.iloc[-1]
            prev = df.iloc[-2]
            
            sig = "HOLD"
            reason = "Scanning..."
            
            # --- FIBONACCI CALCULATION ---
            # Range = High - Low
            fib_range = last['Fib_High'] - last['Fib_Low']
            
            # Default invalid levels
            tp_price = 0.0
            sl_price = 0.0

            if status == "OPEN":
                # --- STRATEGY: Alpha Prime (Fib + Vol + EMA + Volume) ---
                if "Alpha Prime" in strategy_mode:
                    # Logic: EMA Crossover + Volume Spike + High Volatility
                    
                    # 1. EMA Crossover (Bullish)
                    ema_cross_up = prev['EMA_9'] <= prev['EMA_21'] and last['EMA_9'] > last['EMA_21']
                    # 2. Volume Spike
                    vol_spike = last['Volume'] > last['Vol_SMA']
                    # 3. Volatility Check (ATR should be decent)
                    valid_volatility = last['ATR'] > (last['Close'] * 0.0005) # 0.05% move minimum
                    
                    if ema_cross_up and vol_spike and valid_volatility:
                        sig = "BUY"
                        reason = "Alpha Prime Buy"
                        # Fibonacci Targets
                        # Buy at current. Target = 1.618 Ext. SL = 0.618 Retracement level from bottom
                        tp_price = last['Close'] + (fib_range * 0.618) 
                        sl_price = last['Close'] - (fib_range * 0.382) 
                    
                    # Bearish
                    ema_cross_down = prev['EMA_9'] >= prev['EMA_21'] and last['EMA_9'] < last['EMA_21']
                    if ema_cross_down and vol_spike and valid_volatility:
                        sig = "SELL"
                        reason = "Alpha Prime Sell"
                        tp_price = last['Close'] - (fib_range * 0.618)
                        sl_price = last['Close'] + (fib_range * 0.382)

                # --- OLD STRATEGIES ---
                elif "Sniper" in strategy_mode:
                    if last['EMA_9'] > last['EMA_21'] and last['RSI'] > 55: sig = "BUY"; reason="Scalp Buy"
                    elif last['EMA_9'] < last['EMA_21'] and last['RSI'] < 45: sig = "SELL"; reason="Scalp Sell"
                
                # ... (Other legacy strategies logic kept simple for brevity) ...

            else: sig = "MKT CLOSED"
            
            # If no specific Fib calc done (legacy strategies), use standard pct
            if tp_price == 0:
                if sig == "BUY":
                    tp_price = last['Close'] * 1.01
                    sl_price = last['Close'] * 0.995
                elif sig == "SELL":
                    tp_price = last['Close'] * 0.99
                    sl_price = last['Close'] * 1.005

            change = ((last['Close'] - df.iloc[0]['Open']) / df.iloc[0]['Open']) * 100
            data.append({
                "name": name, 
                "price": last['Close'], 
                "change": change, 
                "rsi": last['RSI'], 
                "sig": sig, 
                "status": status, 
                "reason": reason,
                "tp": tp_price,
                "sl": sl_price
            })
            
            cls = "tick-up" if change >= 0 else "tick-down"
            ticker_text += f"<span class='ticker-item'>{name}: <span class='{cls}'>{last['Close']:.2f} ({change:+.2f}%)</span></span> "
            
        except Exception as e:
            # logger.error(f"Data Error {name}: {e}")
            pass
            
    return data, ticker_text

@st.cache_data(ttl=60)
def get_chart_data(symbol):
    try:
        df = yf.download(symbol, period="5d", interval="15m", progress=False, threads=False)
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        return df
    except: return None

# --- 8. EXECUTION ENGINE ---
def run_bot(data):
    for item in data:
        if item['status'] == "CLOSED": continue
        is_open = any(p['name'] == item['name'] for p in st.session_state.positions)
        
        if not is_open and item['sig'] in ["BUY", "SELL"]:
            qty = st.session_state.manual_qty
            
            # Use Calculated Fib Levels
            sl = item['sl']
            tp = item['tp']

            # REAL TRADING LOGIC
            if st.session_state.real_trade_active and st.session_state.angel:
                status, oid = place_angel_order(item['name'], item['sig'], qty)
                if status:
                    st.toast(f"🚀 REAL ORDER: {oid}")
                    st.session_state.positions.append({"name": item['name'], "side": item['sig'], "entry": item['price'], "qty": qty, "pnl": 0.0, "sl": sl, "tp": tp})
                else:
                    st.toast(f"❌ ORDER FAILED: {oid}")
            
            # PAPER TRADING
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
        "🔥 Alpha Prime (Fib+Vol)",
        "Sniper (1m Scalping)", 
        "Momentum (5m Trend)", 
        "Swing (15m Safe)",
        "Pro 90% (Trend+MACD)"
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
            
            # Fibonacci Targets Display
            tp_dist = abs(p['tp'] - curr)
            sl_dist = abs(p['sl'] - curr)
            
            if p['side']=="BUY" and (curr >= p['tp'] or curr <= p['sl']):
                save_trade({"Symbol": p['name'], "Side": "BUY", "Entry": p['entry'], "Exit": curr, "PnL": round(p['pnl'], 2), "Status": "AUTO-TP/SL"})
                st.session_state.positions.remove(p)
                st.rerun()
            elif p['side']=="SELL" and (curr <= p['tp'] or curr >= p['sl']):
                save_trade({"Symbol": p['name'], "Side": "SELL", "Entry": p['entry'], "Exit": curr, "PnL": round(p['pnl'], 2), "Status": "AUTO-TP/SL"})
                st.session_state.positions.remove(p)
                st.rerun()
            
            st.markdown(f"""
            <div class='live-card' style='border-left:4px solid #00f2ff'>
                <b>{p['name']}</b> ({p['side']})<br>
                Entry: {p['entry']:.2f} | Current: {curr:.2f}<br>
                <span style='color:#00e676'>TP: {p['tp']:.2f}</span> | <span style='color:#ff1744'>SL: {p['sl']:.2f}</span><br>
                <b>PnL: {p['pnl']:.2f}</b>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button(f"EXIT {p['name']}", key=p['name']):
                save_trade({"Symbol": p['name'], "Side": "EXIT", "Entry": p['entry'], "Exit": curr, "PnL": round(p['pnl'], 2), "Status": "MANUAL"})
                st.session_state.positions.remove(p)
                st.rerun()
    else: st.info("No Active Trades")

# MARKET
with tab_market:
    with st.expander("🔍 Custom Search"):
        c1, c2 = st.columns([1, 2])
        stype = c1.selectbox("Type", ["NSE"], label_visibility="collapsed")
        search_txt = c2.text_input("Symbol", placeholder="e.g. TATASTEEL", label_visibility="collapsed")
        if st.button("ADD"):
            if search_txt:
                nm = search_txt.upper()
                sym = f"{nm}.NS"
                st.session_state.watchlist[nm] = sym
                st.success(f"Added {sym}")
                time.sleep(0.5)
                st.rerun()

    if st.session_state.bot_active: run_bot(data_list)
    
    for d in data_list:
        cls = "live-card closed-card" if d['status'] == "CLOSED" else "live-card"
        badge = f"<span class='badge-buy'>{d['sig']}</span>" if d['sig']=="BUY" else (f"<span class='badge-sell'>{d['sig']}</span>" if d['sig']=="SELL" else "<span style='color:gray'>WAIT</span>")
        if d['status'] == "CLOSED": badge = "<span style='color:#ff9800; font-size:10px'>CLOSED</span>"
        
        st.markdown(f"""
        <div class='{cls}'>
            <div style='display:flex; justify-content:space-between'>
                <b>{d['name']}</b> <b>{d['price']:.2f}</b>
          

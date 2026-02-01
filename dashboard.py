import time
from datetime import datetime
import pandas as pd
import streamlit as st
from binance.client import Client
from streamlit_autorefresh import st_autorefresh
import smtplib
from email.mime.text import MIMEText
import requests
import plotly.graph_objects as go
import subprocess
import os
import numpy as np
from binance.exceptions import BinanceAPIException, BinanceRequestException

# ================= CONFIG =================
BINANCE_API_KEY = st.secrets.get("BINANCE_API_KEY")
BINANCE_API_SECRET = st.secrets.get("BINANCE_API_SECRET")

EMAIL_FROM = st.secrets.get("EMAIL_FROM")
EMAIL_TO = EMAIL_FROM
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_PASSWORD = st.secrets.get("SMTP_PASSWORD")

CAPITAL_BASE = 1000
TAKE_PROFIT = 100
REBUY_AMOUNT = 100
SYMBOL = "BTCEUR"
CHECK_INTERVAL = 30
NGROK_PATH = r"C:\Users\alcar\OneDrive\Escritorio\ngok\ngrok.exe"

MODE = "BALANCED"
BASE_REBUY_AMOUNT = 100
MAX_DCA_LEVELS = 3
BASE_COOLDOWN = 1800
MAX_VOLATILITY = 0.04
KILL_SWITCH_DRAWDOWN = -0.12

# ===== BINANCE CLIENT SEGURO =====
client = None
if BINANCE_API_KEY and BINANCE_API_SECRET:
    try:
        client = Client(
            BINANCE_API_KEY,
            BINANCE_API_SECRET,
            requests_params={"timeout": 30}
        )
        server_time = client.get_server_time()
        client.timestamp_offset = server_time["serverTime"] - int(time.time() * 1000)
    except Exception as e:
        client = None
        st.error(f"❌ Binance no conectado: {e}")
else:
    st.error("❌ API Keys de Binance no configuradas")

# ===== EMAIL =====
def send_email(subject, body):
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_FROM
        msg["To"] = EMAIL_TO
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_FROM, SMTP_PASSWORD)
            server.send_message(msg)
    except:
        pass

# ===== AUTOREFRESH =====
st_autorefresh(interval=CHECK_INTERVAL * 1000, key="refresh")

# ===== DASHBOARD =====
st.set_page_config(page_title="BTC AutoGestión PRO", layout="wide")
st.title("👑 DASHBOARD BOT BTC-EUR – DARKPULSE-X")

if "events" not in st.session_state:
    st.session_state.events = []
if "last_rebuy_time" not in st.session_state:
    st.session_state.last_rebuy_time = 0
if "dca_level" not in st.session_state:
    st.session_state.dca_level = 0

# ===== FUNCIONES SEGURAS =====
def get_price():
    if not client:
        return 0
    try:
        return float(client.get_avg_price(symbol=SYMBOL)["price"])
    except:
        return 0

def get_balances():
    if not client:
        return 0, 0, CAPITAL_BASE
    try:
        btc = float(client.get_asset_balance(asset="BTC")["free"])
        eur = float(client.get_asset_balance(asset="EUR")["free"])
        price = get_price()
        total = eur + btc * price
        return btc, eur, total
    except:
        return 0, 0, CAPITAL_BASE

def get_klines():
    if not client:
        return None
    try:
        kl = client.get_klines(symbol=SYMBOL, interval="1h", limit=200)
        df = pd.DataFrame(
            kl,
            columns=["t","o","h","l","c","v","ct","q","n","tb","tq","i"]
        )
        df[["o","h","l","c"]] = df[["o","h","l","c"]].astype(float)
        return df
    except:
        return None

def indicators(df):
    if df is None or df.empty or "c" not in df.columns:
        return {"RSI": 50, "EMA200": 0}
    df["EMA200"] = df["c"].ewm(span=200).mean()
    delta = df["c"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    rs = gain.rolling(14).mean() / loss.rolling(14).mean()
    df["RSI"] = 100 - (100 / (1 + rs))
    last = df.iloc[-1]
    return {"RSI": last["RSI"], "EMA200": last["EMA200"]}

# ===== MAIN =====
price = get_price()
btc, cash, total = get_balances()
df = get_klines()
ind = indicators(df)

# ===== MÉTRICAS =====
col1, col2, col3, col4 = st.columns(4)
col1.metric("Precio BTC (€)", f"{price:,.2f}")
col2.metric("BTC", f"{btc:.6f}")
col3.metric("EUR", f"{cash:,.2f}")
col4.metric("Total (€)", f"{total:,.2f}")

# ===== GRÁFICO =====
if df is not None and not df.empty:
    fig = go.Figure(go.Candlestick(
        x=df.index,
        open=df["o"],
        high=df["h"],
        low=df["l"],
        close=df["c"]
    ))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("⏳ Esperando datos de Binance…")

# ===== FOOTER =====
st.markdown("---")
st.markdown(
    "👑 **Dashboard desarrollado por Alex Romera**  \n"
    "💬 Contacto: darkpulsex@protonmail.com"
)
















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
BINANCE_API_KEY = st.secrets["BINANCE_API_KEY"]
BINANCE_API_SECRET = st.secrets["BINANCE_API_SECRET"]


EMAIL_FROM = st.secrets["EMAIL_FROM"]
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_PASSWORD = st.secrets["SMTP_PASSWORD"]


CAPITAL_BASE = 1000
TAKE_PROFIT = 100
REBUY_AMOUNT = 100
SYMBOL = "BTCEUR"
CHECK_INTERVAL = 30
NGROK_PATH = r"C:\Users\alcar\OneDrive\Escritorio\ngok\ngrok.exe"

# ====== NIVEL DIOS CONFIG ======
MODE = "BALANCED"  # CONSERVATIVE | BALANCED | AGGRESSIVE
BASE_REBUY_AMOUNT = 100
MAX_DCA_LEVELS = 3
BASE_COOLDOWN = 1800
MAX_VOLATILITY = 0.04
KILL_SWITCH_DRAWDOWN = -0.12

# =========================================

# ===== BINANCE CLIENT SEGURO =====
try:
    client = Client(
        BINANCE_API_KEY,
        BINANCE_API_SECRET,
        requests_params={"timeout": 30}  # aumentar tiempo si la nube es lenta
    )
    print("Ping Binance:", client.ping())
    server_time = client.get_server_time()
    client.timestamp_offset = server_time["serverTime"] - int(time.time() * 1000)
    print("Conexión Binance OK. Tiempo sincronizado.")
except BinanceAPIException as e:
    print("Error de Binance API:", e)
    client = None
except BinanceRequestException as e:
    print("Error de conexión a Binance:", e)
    client = None
except Exception as e:
    print("Error general:", e)
    client = None

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
    except Exception as e:
        st.warning(f"No se pudo enviar email: {e}")

# ===== AUTOREFRESH =====
st_autorefresh(interval=CHECK_INTERVAL * 1000, key="refresh")

# ===== DASHBOARD CONFIG =====
st.set_page_config(page_title="BTC AutoGestión PRO", layout="wide")
st.title("👑DASHBOARD BOT BTC-EUR🤖>🧠DARKPULSE-X edition limit📈 – Gestión Automática PRO")
st.caption("Venta automática +100 € | Recompra automatica y manual opcional | RSI + EMA200 | TradingView | Fear & Greed")

if "events" not in st.session_state:
    st.session_state.events = []

if "ngrok_url" not in st.session_state:
    st.session_state.ngrok_url = None

if "last_rebuy_time" not in st.session_state:
    st.session_state.last_rebuy_time = 0
if "dca_level" not in st.session_state:
    st.session_state.dca_level = 0

# ===== FUNCIONES SEGURAS =====
def get_price():
    if client is None:
        st.error("Cliente de Binance no inicializado correctamente")
        return 0  # devuelve 0 si no hay conexión
    try:
        return float(client.get_avg_price(symbol=SYMBOL)["price"])
    except Exception as e:
        st.error(f"Error obteniendo precio de {SYMBOL}: {e}")
        return 0


def get_balances():
    if client is None:
        st.error("Cliente de Binance no inicializado correctamente")
        return 0, 0, 0  # devuelve ceros si no hay conexión


try:
    btc = float(client.get_asset_balance(asset="BTC")["free"])
except Exception as e:
    st.error(f"Error obteniendo balance de BTC: {e}")
    btc = 0  # valor por defecto si falla
       


def get_klines():
    if client is None:
        st.error("❌ Binance no conectado. No se pueden obtener velas.")
        return None

    try:
        kl = client.get_klines(symbol=SYMBOL, interval="1h", limit=200)
        df = pd.DataFrame(
            kl,
            columns=["t","o","h","l","c","v","ct","q","n","tb","tq","i"]
        )
        df[["o","h","l","c"]] = df[["o","h","l","c"]].astype(float)
        return df
    except Exception as e:
        st.error(f"Error obteniendo klines: {e}")
        return None



def indicators(df):
    df["EMA200"] = df["c"].ewm(span=200).mean()
    delta = df["c"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    rs = gain.rolling(14).mean() / loss.rolling(14).mean()
    df["RSI"] = 100 - (100 / (1 + rs))
    return df.iloc[-1]

def get_fear_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1").json()["data"][0]
        return int(r["value"]), r["value_classification"]
    except:
        return None, None

def draw_fear_greed_gauge(value):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value if value else 0,
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "orange"},
            "steps": [
                {"range": [0, 25], "color": "#8B0000"},
                {"range": [25, 50], "color": "#FF8C00"},
                {"range": [50, 75], "color": "#FFD700"},
                {"range": [75, 100], "color": "#006400"},
            ]
        }
    ))
    st.plotly_chart(fig, use_container_width=True)

# ===== FUNCIONES DE DASHBOARD =====
def display_metrics(price, btc, cash, total):
    beneficio = total - CAPITAL_BASE
    beneficio_pct = (beneficio / CAPITAL_BASE) * 100
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("💰 Precio BTC (€)", f"{price:,.2f}")
    col2.metric("💶 Saldo efectivo", f"{cash:,.2f}")
    col3.metric("₿ Saldo BTC", f"{btc:.6f}")
    col4.metric("📊 Valor total (€)", f"{total:,.2f}")
    col5.metric("📈 Ganancia / Pérdida (€)", f"{beneficio:,.2f}", delta=f"{beneficio_pct:.2f} %")
    col6.metric("🎯 Objetivo venta (€)", f"{CAPITAL_BASE + TAKE_PROFIT}")

def automatic_sell(price, total, ind):
    exceso = total - CAPITAL_BASE
    if exceso >= TAKE_PROFIT and ind["RSI"] > 55 and price > ind["EMA200"]:
        btc_to_sell = TAKE_PROFIT / price
        try:
            client.order_market_sell(symbol=SYMBOL, quantity=btc_to_sell)
            st.success(f"💰 Venta automática ejecutada: +{TAKE_PROFIT} €")
            send_email("💰 Venta automática",
                       f"Venta ejecutada\nPrecio: {price}\nCantidad BTC: {btc_to_sell:.6f}\nRSI: {ind['RSI']:.2f}\nFecha: {datetime.now()}")
            st.session_state.events.append({
                "Fecha": datetime.now(),
                "Evento": f"Venta automática +{TAKE_PROFIT}€",
                "Precio": price
            })
        except Exception as e:
            st.error(f"Error venta automática: {e}")

def manual_rebuy(price):
    st.warning("📉 Recompra manual opcional")
    if st.button("Ejecutar recompra manual", key="rebuy_button"):
        try:
            client.order_market_buy(symbol=SYMBOL, quoteOrderQty=REBUY_AMOUNT)
            st.session_state.events.append({
                "Fecha": datetime.now(),
                "Evento": "Recompra manual",
                "Precio": price
            })
            send_email("📉 Recompra ejecutada", f"Precio BTC: {price}")
        except Exception as e:
            st.error(f"Error recompra manual: {e}")

def display_tradingview():
    st.markdown("---")
    st.subheader("📈 TradingView")
    tv_html = f"""
    <div class="tradingview-widget-container">
      <div id="tv"></div>
      <script src="https://s3.tradingview.com/tv.js"></script>
      <script>
      new TradingView.widget({{
        "symbol": "BINANCE:{SYMBOL}",
        "interval": "1H",
        "theme": "dark",
        "container_id": "tv",
        "studies": ["RSI@tv-basicstudies","MAExp@tv-basicstudies","BollingerBands@tv-basicstudies","ADX@tv-basicstudies"]
      }});
      </script>
    </div>
    """
    st.components.v1.html(tv_html, height=700)

def display_fear_greed():
    st.markdown("---")
    st.subheader("🧭 Miedo / Codicia")
    value, label = get_fear_greed()
    colA, colB = st.columns([1,2])
    with colA:
        st.metric("Índice", value if value else "N/A", label if label else "")
    with colB:
        draw_fear_greed_gauge(value if value else 0)

def start_ngrok():
    st.markdown("---")
    st.subheader("🌐 URL pública (Ngrok)")
    if not st.session_state.ngrok_url:
        try:
            subprocess.Popen([NGROK_PATH, "http", "8501"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(5)
            ngrok_api = requests.get("http://127.0.0.1:4040/api/tunnels").json()
            public_url = ngrok_api["tunnels"][0]["public_url"]
            st.session_state.ngrok_url = public_url
        except Exception as e:
            st.error(f"No se pudo iniciar Ngrok: {e}")
    if st.session_state.ngrok_url:
        st.markdown(f"[Abrir Dashboard en móvil]({st.session_state.ngrok_url})", unsafe_allow_html=True)

# =========================================================
# ========== 🔥 NIVEL DIOS – RECOMPRA PRO 🔥 ==========
# =========================================================

def add_atr(df):
    high_low = df["h"] - df["l"]
    high_close = abs(df["h"] - df["c"].shift())
    low_close = abs(df["l"] - df["c"].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["ATR"] = tr.rolling(14).mean()
    return df

def trend_ok(df):
    ema50 = df["c"].ewm(span=50).mean().iloc[-1]
    ema200 = df["c"].ewm(span=200).mean().iloc[-1]
    return ema50 > ema200

def adaptive_rsi_floor():
    return {"CONSERVATIVE":35, "BALANCED":40, "AGGRESSIVE":45}[MODE]

def kill_switch(total):
    dd = (total - CAPITAL_BASE) / CAPITAL_BASE
    return dd < KILL_SWITCH_DRAWDOWN

def automatic_rebuy_pro(price, cash, total, df):
    if kill_switch(total):
        return

    now = time.time()
    cooldown = BASE_COOLDOWN
    if now - st.session_state.last_rebuy_time < cooldown:
        return

    df = add_atr(df)
    atr_pct = df["ATR"].iloc[-1] / df["c"].iloc[-1]
    if atr_pct > MAX_VOLATILITY:
        return

    ind = indicators(df)
    if not trend_ok(df):
        return

    if ind["RSI"] > adaptive_rsi_floor():
        return

    if st.session_state.dca_level >= MAX_DCA_LEVELS:
        return

# ===== COMPRA FIJA 100€ – FUNCIÓN SEGURA =====
def fixed_rebuy(price, cash):
    """
    Compra fija de 100€ si hay suficiente saldo y cliente conectado
    """
    amount = BASE_REBUY_AMOUNT  # siempre 100 €

    if cash < amount:
        return  # salir si hay menos de 100 €

    if client is None:
        st.error("Cliente de Binance no inicializado. No se puede ejecutar la recompra.")
        return  # salir si no hay cliente

    try:
        # Ejecutar orden de compra por mercado
        client.order_market_buy(symbol=SYMBOL, quoteOrderQty=amount)

        # Actualizar estado de la sesión
        now = datetime.now()
        st.session_state.last_rebuy_time = now
        st.session_state.dca_level += 1
        st.session_state.events.append({
            "Fecha": now,
            "Evento": f"Recompra PRO DCA {st.session_state.dca_level}",
            "Precio": price
        })

        # Notificación por email
        send_email(
            "🤖 Recompra PRO",
            f"Importe: {amount} €\nPrecio: {price}"
        )

        st.success(f"🤖 Recompra PRO ejecutada ({amount} €)")

    except BinanceAPIException as e:
        st.error(f"Error en Binance API: {e}")

    except Exception as e:
        st.error(f"Error general al ejecutar recompra: {e}")


# ===== RECOMPRA AUTOMÁTICA NIVEL DIOS =====
def automatic_rebuy_pro(price, cash, total, df):
    """
    Recompra automática avanzada con DCA, ATR, RSI y control de tendencia
    """
    if kill_switch(total):
        return  # detener si drawdown supera límite

    now_ts = time.time()
    cooldown = BASE_COOLDOWN
    if now_ts - st.session_state.last_rebuy_time < cooldown:
        return  # cooldown activo

    df = add_atr(df)
    atr_pct = df["ATR"].iloc[-1] / df["c"].iloc[-1]
    if atr_pct > MAX_VOLATILITY:
        return  # volatilidad muy alta

    ind = indicators(df)
    if not trend_ok(df):
        return  # tendencia no favorable

    if ind["RSI"] > adaptive_rsi_floor():
        return  # RSI demasiado alto

    if st.session_state.dca_level >= MAX_DCA_LEVELS:
        return  # máximo DCA alcanzado

    # ===== COMPRA FIJA 100€ =====
    fixed_rebuy(price, cash)



# ===== MAIN LIMPIO – DASHBOARD SUPREMO =====
price = get_price()
btc, cash, total = get_balances()
df = get_klines()
ind = indicators(df)

# ===== MÉTRICAS PRINCIPALES =====
display_metrics(price, btc, cash, total)

# ===== VENTAS Y RECOMPRA AUTOMÁTICA =====
automatic_sell(price, total, ind)
manual_rebuy(price)
automatic_rebuy_pro(price, cash, total, df)

# ===== FEAR & GREED =====
display_fear_greed()

# ===== NGROK URL =====
start_ngrok()

# ===== HISTORIAL =====
if st.session_state.events:
    st.markdown("---")
    st.subheader("🗂️ Historial")
    st.dataframe(pd.DataFrame(st.session_state.events), use_container_width=True)

# =========================================================
# ========== 📊 BTC/EUR – Gráfico Supremo (TradingView + Señales Bot) =========
# =========================================================

st.markdown("---")
st.subheader("📊 BTC/EUR Gráfico TradingView  ✅")

# ===== TRADINGVIEW – CONTEXTO COMPLETO =====
tv_html = """
<div class="tradingview-widget-container">
  <div id="tv_chart_supreme"></div>
  <script src="https://s3.tradingview.com/tv.js"></script>
  <script>
  new TradingView.widget({
    "symbol": "BINANCE:BTCEUR",
    "interval": "15",
    "timezone": "Europe/Madrid",
    "theme": "dark",
    "style": "1",
    "locale": "es",
    "toolbar_bg": "#1e1e1e",
    "enable_publishing": false,
    "hide_side_toolbar": false,
    "allow_symbol_change": false,
    "studies": [
      "MAExp@tv-basicstudies",  // EMA 20
      "MAExp@tv-basicstudies",  // EMA 50
      "MAExp@tv-basicstudies",  // EMA 100
      "MAExp@tv-basicstudies",  // EMA 200
      "RSI@tv-basicstudies",
      "MACD@tv-basicstudies",
      "ATR@tv-basicstudies",
      "Volume@tv-basicstudies",
      "ADX@tv-basicstudies",
      "BB@tv-basicstudies"
    ],
    "container_id": "tv_chart_supreme"
  });
  </script>
</div>
"""
st.components.v1.html(tv_html, height=800)

# =========================================================
# ========== 📈 BTC/EUR – Señales Reales del Bot (Plotly) =========
# =========================================================

st.markdown("---")
st.subheader("📈 BTC/EUR – Señales Reales del Bot (Plotly) ✅")

df_plot = df.copy()

# EMAs exactas
df_plot["EMA20"] = df_plot["c"].ewm(span=20).mean()
df_plot["EMA50"] = df_plot["c"].ewm(span=50).mean()
df_plot["EMA100"] = df_plot["c"].ewm(span=100).mean()
df_plot["EMA200"] = df_plot["c"].ewm(span=200).mean()

# Soportes / Resistencias recientes
df_plot["High_Recent"] = df_plot["h"].rolling(50).max()
df_plot["Low_Recent"] = df_plot["l"].rolling(50).min()

fig = go.Figure()

# Candlestick
fig.add_trace(go.Candlestick(
    x=df_plot.index,
    open=df_plot["o"],
    high=df_plot["h"],
    low=df_plot["l"],
    close=df_plot["c"],
    name="Precio BTC"
))

# EMAs
fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot["EMA20"], name="EMA 20", line=dict(color="yellow")))
fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot["EMA50"], name="EMA 50", line=dict(color="orange")))
fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot["EMA100"], name="EMA 100", line=dict(color="blue")))
fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot["EMA200"], name="EMA 200", line=dict(color="red")))

# Soportes / Resistencias
fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot["High_Recent"], name="Resistencia", line=dict(dash="dot", color="green")))
fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot["Low_Recent"], name="Soporte", line=dict(dash="dot", color="purple")))

# Señales BUY / SELL desde historial
if st.session_state.events:
    buys_x, buys_y, sells_x, sells_y = [], [], [], []
    for e in st.session_state.events:
        if "Recompra" in e["Evento"]:
            buys_x.append(e["Fecha"])
            buys_y.append(e["Precio"])
        if "Venta" in e["Evento"]:
            sells_x.append(e["Fecha"])
            sells_y.append(e["Precio"])
    fig.add_trace(go.Scatter(x=buys_x, y=buys_y, mode="markers",
                             marker=dict(symbol="triangle-up", size=12, color="green"), name="BUY"))
    fig.add_trace(go.Scatter(x=sells_x, y=sells_y, mode="markers",
                             marker=dict(symbol="triangle-down", size=12, color="red"), name="SELL"))

fig.update_layout(
    height=700,
    xaxis_rangeslider_visible=False,
    template="plotly_dark",
    title="BTC/EUR – Gráfico Supremo: Contexto + Señales Bot",
    legend=dict(orientation="h", y=1.05)
)

st.plotly_chart(fig, use_container_width=True)

# ===== FOOTER =====
st.markdown("---")
st.markdown(
    "👑 **Dashboard desarrollado por Alex Romera**  \n"
    "💬 Contacto: [darkpulsex@protonmail.com](mailto:darkpulsex@protonmail.com)",
    unsafe_allow_html=True
)
















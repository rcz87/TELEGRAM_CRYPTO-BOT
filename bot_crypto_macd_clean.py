
import requests
import nest_asyncio
import asyncio
import pandas as pd
import numpy as np
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

nest_asyncio.apply()

TELEGRAM_TOKEN = "7695838700:AAFoZve12b53RzL8pu_swAnFkjaqXz43zKU"

COIN_LIST = [
    "BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "DOGE-USDT",
    "ADA-USDT", "AVAX-USDT", "DOT-USDT", "SHIB-USDT", "LINK-USDT",
]

def get_candles(inst, bar="5m"):
    url = f"https://www.okx.com/api/v5/market/candles?instId={inst}&bar={bar}&limit=100"
    try:
        res = requests.get(url, timeout=5).json()
        if res["code"] != "0":
            return None
        raw = res["data"]
        df = pd.DataFrame(raw, columns=["ts", "o", "h", "l", "c", "vol", "volCcy", "volCcyQuote", "confirm", "chg"])
        df["close"] = df["c"].astype(float)
        df["high"] = df["h"].astype(float)
        df["low"] = df["l"].astype(float)
        return df[["close", "high", "low"]].iloc[::-1]
    except:
        return None

def calculate_indicators(df):
    df["EMA10"] = df["close"].ewm(span=10, adjust=False).mean()
    
    # RSI
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    # Stochastic RSI
    min_rsi = df["RSI"].rolling(14).min()
    max_rsi = df["RSI"].rolling(14).max()
    df["StochRSI"] = (df["RSI"] - min_rsi) / (max_rsi - min_rsi) * 100

    # MACD
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()

    return df

def detect_sr(df):
    recent_lows = df["low"].rolling(5).min().iloc[-10:]
    recent_highs = df["high"].rolling(5).max().iloc[-10:]
    support = recent_lows.min()
    resistance = recent_highs.max()
    return support, resistance

def analyze(df):
    signals = []
    price = df["close"].iloc[-1]

    if price > df["EMA10"].iloc[-1]:
        signals.append("✅ *Harga di atas EMA10* (tren naik)")
    else:
        signals.append("⚠️ *Harga di bawah EMA10* (tren turun)")

    rsi = df["RSI"].iloc[-1]
    if rsi < 30:
        signals.append("🟢 *RSI Oversold* — potensi naik")
    elif rsi > 70:
        signals.append("🔴 *RSI Overbought* — potensi turun")
    else:
        signals.append("📉 *RSI Normal*")

    stoch = df["StochRSI"].iloc[-1]
    if stoch < 20:
        signals.append("🟢 *Stoch RSI Oversold* — momentum naik")
    elif stoch > 80:
        signals.append("🔴 *Stoch RSI Overbought* — momentum turun")

    macd = df["MACD"].iloc[-1]
    macd_signal = df["MACD_signal"].iloc[-1]
    if macd > macd_signal:
        signals.append("🟢 *MACD Bullish Crossover* — tren naik")
    elif macd < macd_signal:
        signals.append("🔴 *MACD Bearish Crossover* — tren turun")

    support, resistance = detect_sr(df)
    if price < support * 1.02:
        signals.append(f"📍 *Dekat Support*: {support:.2f}")
    elif price > resistance * 0.98:
        signals.append(f"📍 *Dekat Resistance*: {resistance:.2f}")

    return signals, price

async def simple_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.strip().upper()
        words = text.split()
        pairs = []

        for word in words:
            if not word.endswith("-USDT"):
                word = word + "-USDT"
            if word in COIN_LIST:
                pairs.append(word)
            if len(pairs) >= 3:
                break

        if not pairs:
            await update.message.reply_text("⚠️ Coin tidak valid atau terlalu banyak.")
            return

        for coin in pairs:
            df = get_candles(coin)
            await asyncio.sleep(1)
            if df is None or df.empty:
                await update.message.reply_text(f"❌ Gagal ambil data {coin}")
                continue

            df = calculate_indicators(df)
            signals, latest_price = analyze(df)

            output_text = f"""━━━━━━━━━━━━━━
📊 *ANALISA {coin}*
💰 Harga: {latest_price:.2f}
{chr(10).join(signals)}
━━━━━━━━━━━━━━"""
            await update.message.reply_text(output_text, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Halo! Kirim nama coin, contoh: BTC atau ETH")

application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, simple_check))

async def main():
    await application.initialize()
    await application.start()
    await application.run_polling()

import nest_asyncio
nest_asyncio.apply()

asyncio.get_event_loop().run_until_complete(main())


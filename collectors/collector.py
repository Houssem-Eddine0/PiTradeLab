import ccxt
import sqlite3
import time

exchange = ccxt.binance()

conn = sqlite3.connect("data/market.db")
cursor = conn.cursor()

symbol = "BTC/USDT"
timeframe = "1m"

print("Collector started...")

while True:
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=1)
        candle = ohlcv[0]

        timestamp, open_p, high, low, close, volume = candle

        cursor.execute(
            "INSERT INTO prices VALUES (?, ?, ?, ?, ?, ?)",
            (timestamp, open_p, high, low, close, volume)
        )

        conn.commit()

        print("Saved:", close)

        time.sleep(60)

    except Exception as e:
        print("Error:", e)
        time.sleep(10)

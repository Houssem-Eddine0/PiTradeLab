import sqlite3
import time
from strategy.strategy_v1 import simple_strategy

conn = sqlite3.connect("data/market.db")
cursor = conn.cursor()

balance = 1000
btc_balance = 0

print("Paper trader started...")

while True:

    cursor.execute(
        "SELECT close FROM prices ORDER BY timestamp DESC LIMIT 2"
    )

    rows = cursor.fetchall()

    if len(rows) < 2:
        time.sleep(10)
        continue

    last_price = rows[0][0]
    prev_price = rows[1][0]

    signal = simple_strategy(last_price, prev_price)

    print("Signal:", signal)

    if signal == "BUY" and balance > 0:

        btc_balance = balance / last_price
        balance = 0

        cursor.execute(
            "INSERT INTO paper_trades VALUES (?, ?, ?, ?, ?)",
            (int(time.time()), "BUY", last_price, balance, btc_balance)
        )

    elif signal == "SELL" and btc_balance > 0:

        balance = btc_balance * last_price
        btc_balance = 0

        cursor.execute(
            "INSERT INTO paper_trades VALUES (?, ?, ?, ?, ?)",
            (int(time.time()), "SELL", last_price, balance, btc_balance)
        )

    conn.commit()

    time.sleep(60)

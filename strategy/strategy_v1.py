def simple_strategy(last_price, previous_price):

    if last_price > previous_price:
        return "BUY"

    elif last_price < previous_price:
        return "SELL"

    else:
        return "HOLD"

import oandapyV20
import oandapyV20.endpoints.accounts as accounts
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.instruments as instruments
import time
import logging
from datetime import datetime, timezone

from strategy import BreakoutStrategy

# --- Configuration ---
# PASTE YOUR OANDA DETAILS HERE
OANDA_API_KEY = "00af8e5fa652f65e10ebe7d97cec5dfc-83d28a2b4b0c129bd012e604153d5b93"
OANDA_ACCOUNT_ID = "101-004-35670796-001"

# --- Strategy & Instrument Configuration ---
# The bot will check ALL of these instruments every 30 minutes.
TRADE_setups = {
    # Instrument: { strategy params, fixed unit size }
    'US30_USD':   {'params': {'stop_loss_distance': 10, 'take_profit_distance': 30}, 'units': 10},
    'SPX500_USD': {'params': {'stop_loss_distance': 10, 'take_profit_distance': 30}, 'units': 1},
    'NAS100_USD': {'params': {'stop_loss_distance': 20, 'take_profit_distance': 60}, 'units': 5},
    'XAU_USD':    {'params': {'stop_loss_distance': 10, 'take_profit_distance': 30}, 'units': 1},
    'EUR_USD':    {'params': {'stop_loss_distance': 0.0005, 'take_profit_distance': 0.0015}, 'units': 100},
    'GBP_USD':    {'params': {'stop_loss_distance': 0.0005, 'take_profit_distance': 0.0015}, 'units': 100},
    
}

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_candle_data(api, instrument, count=30, granularity='M1'):
    """Fetches the last N candles from OANDA for a given instrument."""
    params = {'count': count, 'granularity': granularity, 'price': 'M'} # M = Midpoint candles
    try:
        r = instruments.InstrumentsCandles(instrument=instrument, params=params)
        api.request(r)
        
        bars = []
        for candle in r.response['candles']:
            if candle['complete']:
                bars.append({
                    'time': candle['time'],
                    'high': float(candle['mid']['h']),
                    'low': float(candle['mid']['l']),
                    'close': float(candle['mid']['c'])
                })
        return bars
    except oandapyV20.exceptions.V20Error as err:
        logging.error(f"Error fetching candle data for {instrument}: {err}")
        return []

def is_market_hours():
    """
    Checks if it's currently within general market hours (avoids weekends).
    Returns True if markets are likely open, False otherwise.
    Note: This is a general check and doesn't account for specific market holidays.
    """
    now_utc = datetime.now(timezone.utc)
    # 0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday, 5=Saturday, 6=Sunday
    weekday = now_utc.weekday()

    # Market is closed from Friday 22:00 UTC to Sunday 22:00 UTC
    if weekday == 4 and now_utc.hour >= 22: # After 10 PM UTC on Friday
        return False
    if weekday == 5: # All day Saturday
        return False
    if weekday == 6 and now_utc.hour < 22: # Before 10 PM UTC on Sunday
        return False
        
    return True

def run_bot():
    """Main trading loop."""
    try:
        api = oandapyV20.API(access_token=OANDA_API_KEY, environment="practice") # IMPORTANT: Using practice account
        acc_details = accounts.AccountDetails(OANDA_ACCOUNT_ID)
        api.request(acc_details)
        logging.info(f"Bot started. Connected to OANDA practice account: {acc_details.response['account']['id']}")
    except Exception as e:
        logging.error(f"FATAL: Failed to connect to OANDA. Check API Key and Account ID. Error: {e}")
        return

    strategy = BreakoutStrategy()
    
    last_checked_minute = -1 # Variable to ensure we only check once per 30-min block

    while True:
        if not is_market_hours():
            logging.info("Markets are closed. Sleeping for 1 hour.")
            time.sleep(3600) # Sleep for an hour
            continue # Go back to the start of the loop

        now_utc = datetime.now(timezone.utc)
        current_minute = now_utc.minute

        # Check at the 29th and 59th minute to capture the data for the half-hour/hour that just ended.
        if current_minute in [29, 59] and current_minute != last_checked_minute:
            logging.info(f"--- It's minute {current_minute}. Checking for trades on all instruments. ---")
            
            for instrument, setup in TRADE_setups.items():
                logging.info(f"-> Checking {instrument}...")
                params = setup['params']
                units = setup['units']

                # 1. Fetch live candle data for the last 30 minutes
                bars = get_candle_data(api, instrument)
                if not bars or len(bars) < 30:
                    logging.warning(f"Could not get enough bar data for {instrument}. Skipping.")
                    continue

                # 2. Check for a trade signal from the strategy
                trade_signal = strategy.check_trade(bars, params['stop_loss_distance'], params['take_profit_distance'])

                if trade_signal:
                    direction, entry, sl_price, tp_price = trade_signal
                    trade_type = "LONG" if direction == 1 else "SHORT"
                    logging.info(f"!!! TRADE SIGNAL FOUND for {instrument}: {trade_type} !!!")

                    # 3. Place the trade with fixed unit size
                    order_data = {
                        "order": {
                            "instrument": instrument,
                            "units": str(units * direction), # Positive for long, negative for short
                            "type": "MARKET",
                            "positionFill": "DEFAULT",
                            "takeProfitOnFill": {"price": str(round(tp_price, 5))},
                            "stopLossOnFill": {"price": str(round(sl_price, 5))}
                        }
                    }

                    r = orders.OrderCreate(OANDA_ACCOUNT_ID, data=order_data)
                    try:
                        api.request(r)
                        logging.info(f"+++ TRADE PLACED for {instrument}. {trade_type} {units} units. SL={sl_price:.5f}, TP={tp_price:.5f} +++")
                    except oandapyV20.exceptions.V20Error as err:
                        logging.error(f"XXX FAILED TO PLACE TRADE for {instrument}. Reason: {err} XXX")
            
            last_checked_minute = current_minute # Mark this minute block as checked
            logging.info("--- Trade check complete. ---")
        
        time.sleep(20) # Wait before checking the time again

if __name__ == "__main__":
    run_bot()

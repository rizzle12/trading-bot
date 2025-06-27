class BreakoutStrategy:
    """
    A stateless breakout strategy that checks for a trade signal.
    It takes historical data and returns a trade signal if conditions are met.
    """
    def check_trade(self, bars, stop_loss_distance, take_profit_distance):
        """
        Analyzes the last 30 bars and decides if a trade should be entered.
        
        Args:
            bars (list of dicts): A list of the last 30 one-minute bars.
                                  Each dict has 'high', 'low', 'close'.
            stop_loss_distance (float): The distance in points for the stop loss.
            take_profit_distance (float): The distance in points for the take profit.

        Returns:
            A tuple (trade_direction, entry_price, stop_loss, take_profit) or None.
        """
        if not bars or len(bars) < 30:
            return None

        # --- Strategy Logic ---
        # 1. Define the range from the first 28 bars
        range_bars = bars[:28]
        recent_high = max(b['high'] for b in range_bars)
        recent_low = min(b['low'] for b in range_bars)

        # 2. Check the 29th bar
        check_bar = bars[28]
        if check_bar['high'] > recent_high or check_bar['low'] < recent_low:
            return None  # 29th bar broke the range, no trade

        # 3. Check the 30th bar for entry
        entry_bar = bars[29]
        entry_price = entry_bar['close']

        # Check for long entry (breakout above high)
        if entry_bar['high'] >= recent_high and entry_bar['low'] > recent_low:
            sl = entry_price - stop_loss_distance
            tp = entry_price + take_profit_distance
            return (1, entry_price, sl, tp)  # 1 for long

        # Check for short entry (breakdown below low)
        if entry_bar['low'] <= recent_low and entry_bar['high'] < recent_high:
            sl = entry_price + stop_loss_distance
            tp = entry_price - take_profit_distance
            return (-1, entry_price, sl, tp)  # -1 for short

        return None

import os
import time
from flask import Flask, request, jsonify
from mt5linux import MetaTrader5

app = Flask(__name__)

# Keep it global but completely empty on startup
mt5 = None

def safe_lazy_init():
    """Initializes and logs into MT5 only when an endpoint is actively triggered"""
    global mt5
    
    # If already initialized, just return it
    if mt5 is not None:
        return True
        
    print("⏳ Lazy initializing MT5 internal Wine server...")
    try:
        mt5 = MetaTrader5()
        
        login = int(os.environ.get("EXNESS_LOGIN", 0))
        password = os.environ.get("EXNESS_PASSWORD", "")
        server = os.environ.get("EXNESS_SERVER", "")
        
        print("⚙️ Logging into Exness via Wine emulation...")
        if mt5.initialize(login=login, password=password, server=server):
            print("✅ Successfully connected to Exness MT5!")
            return True
        else:
            print(f"❌ Exness Auth Failed: {mt5.last_error()}")
            mt5 = None
            return False
            
    except Exception as e:
        print(f"❌ Internal Wine Bridge Exception: {e}")
        mt5 = None
        return False

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "bridge server online and idling safely"})

@app.route('/trade', methods=['POST'])
def place_trade():
    # Initialize dynamically on request
    if not safe_lazy_init():
        return jsonify({"error": "Failed to wake up and authorize MT5 engine"}), 500
        
    data = request.get_json() or {}
    symbol = data.get('symbol', 'EURUSD')
    action = data.get('action')
    
    order_type = mt5.ORDER_TYPE_BUY if action == 'BUY' else mt5.ORDER_TYPE_SELL
    tick = mt5.symbol_info_tick(symbol)
    
    if not tick:
        return jsonify({"error": f"Could not fetch live tick for {symbol}"}), 400

    price = tick.ask if action == 'BUY' else tick.bid

    request_payload = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": 0.01,
        "type": order_type,
        "price": price,
        "deviation": 20,
        "magic": 123456,
        "comment": "Railway Signal Input",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request_payload)
    
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        return jsonify({"status": "failed", "error": result.comment}), 400

    return jsonify({"status": "success", "ticket": result.order})

@app.route('/history', methods=['GET'])
def get_history():
    # Initialize dynamically on request
    if not safe_lazy_init():
        return jsonify({"error": "Failed to wake up and authorize MT5 engine"}), 500

    symbol = request.args.get('symbol', 'EURUSDm')
    timeframe_str = request.args.get('timeframe', 'M15')
    count = int(request.args.get('count', 500))
    
    # Map incoming timeframe string to MT5 timeframe constants safely
    timeframe = mt5.TIMEFRAME_M15
    if timeframe_str == "M1": timeframe = mt5.TIMEFRAME_M1
    elif timeframe_str == "M5": timeframe = mt5.TIMEFRAME_M5
    elif timeframe_str == "M30": timeframe = mt5.TIMEFRAME_M30
    elif timeframe_str == "H1": timeframe = mt5.TIMEFRAME_H1
    
    print(f"📈 Extracting {count} bars of {timeframe_str} data for {symbol}...")
    rates = mt5.copy_rates_from_now(symbol, timeframe, count)

    if rates is None or len(rates) == 0:
        return jsonify({"error": f"Broker returned empty historical arrays for {symbol}"}), 400

    output_records = []
    
    # Safely convert the structure whether it returns as an array of tuples or objects
    for candle in rates:
        try:
            # If rates come back as an array of named tuples / objects
            record = {
                "time": int(candle.time),
                "open": float(candle.open),
                "high": float(candle.high),
                "low": float(candle.low),
                "close": float(candle.close),
                "tick_volume": int(candle.tick_volume)
            }
        except AttributeError:
            # Fallback if rates come back as raw indexed tuples
            record = {
                "time": int(candle[0]),
                "open": float(candle[1]),
                "high": float(candle[2]),
                "low": float(candle[3]),
                "close": float(candle[4]),
                "tick_volume": int(candle[5])
            }
        output_records.append(record)

    return jsonify(output_records)

if __name__ == '__main__':
    # Flask boots up instantly with NO background MT5 calls. 
    # This prevents Railway from crashing during deployment!
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

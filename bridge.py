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
    global mt5
    
    # 1. Initialize and log into the MT5 Engine dynamically
    try:
        if not safe_lazy_init():
            return jsonify({
                "status": "error", 
                "error": "Failed to initialize or authorize the MT5 Wine client engine."
            }), 500
    except Exception as init_err:
        return jsonify({
            "status": "error", 
            "error": f"Exception during lazy initialization: {str(init_err)}"
        }), 500

    # 2. Extract query arguments with explicit fallbacks
    symbol = request.args.get('symbol', 'EURUSDm')
    timeframe_str = str(request.args.get('timeframe', 'M15')).upper()
    
    try:
        count = int(request.args.get('count', 500))
    except ValueError:
        count = 500

    # 3. Direct literal timeframes to ensure mt5linux handles them seamlessly
    # Using explicit mt5linux frame ID numbers directly
    if timeframe_str == "M1":
        timeframe = 1
    elif timeframe_str == "M5":
        timeframe = 5
    elif timeframe_str == "M15":
        timeframe = 15
    elif timeframe_str == "M30":
        timeframe = 30
    elif timeframe_str == "H1":
        timeframe = 16385
    elif timeframe_str == "H4":
        timeframe = 16388
    else:
        timeframe = 15 # Default safe fallback to M15

    print(f"⚙️ Engine call: Symbol={symbol}, Timeframe={timeframe_str}({timeframe}), Count={count}")

    # 4. Request historical arrays from the broker terminal safely
    try:
        rates = mt5.copy_rates_from_now(symbol, timeframe, count)
    except Exception as fetch_err:
        return jsonify({
            "status": "error", 
            "error": f"Exception thrown during copy_rates_from_now: {str(fetch_err)}"
        }), 500

    # 5. Check if the broker returned valid data
    if rates is None or len(rates) == 0:
        return jsonify({
            "status": "error",
            "error": f"Broker returned empty arrays for market asset symbol '{symbol}'. Ensure it is visible in MarketWatch."
        }), 400

    # 6. Parse out records safely across tuple and object formats
    output_records = []
    for candle in rates:
        try:
            # Try parsing as a standard dictionary/object structure
            record = {
                "time": int(candle.time),
                "open": float(candle.open),
                "high": float(candle.high),
                "low": float(candle.low),
                "close": float(candle.close),
                "tick_volume": int(candle.tick_volume)
            }
        except Exception:
            try:
                # Safe fallback to index notation for array tuples
                record = {
                    "time": int(candle[0]),
                    "open": float(candle[1]),
                    "high": float(candle[2]),
                    "low": float(candle[3]),
                    "close": float(candle[4]),
                    "tick_volume": int(candle[5])
                }
            except Exception as parse_err:
                return jsonify({
                    "status": "error", 
                    "error": f"Failed compiling structural candle indexes: {str(parse_err)}"
                }), 500
        
        output_records.append(record)

    

    return jsonify(output_records)
if __name__ == '__main__':
    # Flask boots up instantly with NO background MT5 calls. 
    # This prevents Railway from crashing during deployment!
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

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

    symbol = request.args.get('symbol', 'EURUSD')
    timeframe = mt5.TIMEFRAME_M15 
    
    print(f"📈 Extracting 1000 bars of M15 data for {symbol}...")
    rates = mt5.copy_rates_from_now(symbol, timeframe, 1000)

    if rates is None or len(rates) == 0:
        return jsonify({"error": "Broker returned empty historical arrays"}), 400

    try:
        close_prices = [float(candle[4]) for candle in rates] 
    except Exception:
        close_prices = [float(candle.close) for candle in rates]
    
    return jsonify({"symbol": symbol, "closes": close_prices})

if __name__ == '__main__':
    # Flask boots up instantly with NO background MT5 calls. 
    # This prevents Railway from crashing during deployment!
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

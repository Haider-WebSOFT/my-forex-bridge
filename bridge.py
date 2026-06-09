import os
import time
from flask import Flask, request, jsonify
from mt5linux import MetaTrader5

app = Flask(__name__)

# Declare mt5 as global, but don't initialize it yet
mt5 = None

def init_mt5_bridge():
    """Initializes the mt5linux server bridge defensively"""
    global mt5
    print("⏳ Starting background Wine MT5 server bridge...")
    
    # Try connecting to the internal bridge server up to 5 times
    for attempt in range(1, 6):
        try:
            # We explicitly pass the initialization flag to kickstart the wine daemon
            mt5 = MetaTrader5()
            print("🚀 Internal mt5linux RPC bridge connected successfully!")
            return True
        except Exception as e:
            print(f"⚠️ Bridge connection attempt {attempt} failed. Retrying in 4s... Error: {e}")
            time.sleep(4)
    return False

def connect_to_exness():
    """Authenticates the initialized bridge with Exness servers"""
    login = int(os.environ.get("EXNESS_LOGIN", 0))
    password = os.environ.get("EXNESS_PASSWORD", "")
    server = os.environ.get("EXNESS_SERVER", "")

    if mt5 is None:
        print("❌ Cannot authenticate: MT5 Bridge object was never built.")
        return False

    print("⚙️ Logging into Exness Terminal via Wine...")
    if mt5.initialize(login=login, password=password, server=server):
        print("✅ Successfully logged into Exness!")
        return True
    
    print(f"❌ Exness Login Failed. Code: {mt5.last_error()}")
    return False

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "online",
        "bridge_initialized": mt5 is not None
    })

@app.route('/trade', methods=['POST'])
def place_trade():
    if mt5 is None:
        return jsonify({"error": "Bridge server is offline"}), 500
        
    data = request.get_json() or {}
    symbol = data.get('symbol', 'EURUSD')
    action = data.get('action') # 'BUY' or 'SELL'
    
    if not connect_to_exness():
        return jsonify({"error": "Could not authenticate with Exness broker"}), 500

    order_type = mt5.ORDER_TYPE_BUY if action == 'BUY' else mt5.ORDER_TYPE_SELL
    tick = mt5.symbol_info_tick(symbol)
    
    if not tick:
        mt5.shutdown()
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
        "comment": "Hostinger Signal Stream",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request_payload)
    mt5.shutdown() # Safeguard RAM cycles on Railway

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        return jsonify({"status": "failed", "error": result.comment}), 400

    return jsonify({"status": "success", "ticket": result.order})

if __name__ == '__main__':
    # Initialize the bridge server right before launching the web endpoints
    if init_mt5_bridge():
        port = int(os.environ.get("PORT", 5000))
        app.run(host='0.0.0.0', port=port)
    else:
        print("🚨 CRITICAL: Bridge failed to initialize. Exiting container process.")

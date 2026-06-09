from flask import Flask, request, jsonify
import os
from mt5linux import MetaTrader5

app = Flask(__name__)

# Initialize connection inside the emulator container
mt5 = MetaTrader5()

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "bridge online"})

@app.route('/trade', methods=['POST'])
def place_trade():
    data = request.get_json()
    
    # Exness MT5 connection authorization
    login = int(os.environ.get("EXNESS_LOGIN"))
    password = os.environ.get("EXNESS_PASSWORD")
    server = os.environ.get("EXNESS_SERVER")
    
    if not mt5.initialize(login=login, password=password, server=server):
        return jsonify({"error": "MT5 Auth Initialization Failed", "details": mt5.last_error()}), 500

    symbol = data.get('symbol', 'EURUSD')
    action = data.get('action') # 'BUY' or 'SELL'
    
    order_type = mt5.ORDER_TYPE_BUY if action == 'BUY' else mt5.ORDER_TYPE_SELL
    price = mt5.symbol_info_tick(symbol).ask if action == 'BUY' else mt5.symbol_info_tick(symbol).bid

    # Exness 0.01 micro unit lot order footprint configuration block
    request_payload = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": 0.01, 
        "type": order_type,
        "price": price,
        "deviation": 20,
        "magic": 123456,
        "comment": "Railway Hostinger Signal",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request_payload)
    mt5.shutdown()

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        return jsonify({"status": "failed", "error": result.comment}), 400

    return jsonify({"status": "success", "ticket": result.order})

if __name__ == '__main__':
    # Railway passes port dynamically via variable injectors
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
nano requirements.txt # only flask + flask-cors git add . git 
commit -m "fix railway"from flask import Flask, jsonify, request 
from flask_cors import CORS import time import random import os
git push
app = Flask(__name__)
CORS(app)

@app.route('/health')
def health():
    return jsonify({"status": "ok"}), 200

@app.route('/candles')
def get_candles():
    asset = request.args.get('asset', 'USDBRL-OTC')
    count = int(request.args.get('count', 50))
    
    base_prices = {
        'USDBRL-OTC': 5.45,
        'USDCOP-OTC': 4200,
        'USDEGP-OTC': 50.5
    }
    
    price = base_prices.get(asset, 5.0)
    candles = []
    now = time.time()
    
    for i in range(count - 1, -1, -1):
        t = now - i * 60
        time_str = time.strftime('%H:%M', time.localtime(t))
        open_price = price
        change = (random.random() - 0.48) * 0.003 * price
        close_price = open_price + change
        high = max(open_price, close_price) + random.random() * 0.002 * price
        low = min(open_price, close_price) - random.random() * 0.002 * price
        
        candles.append({
            "time": time_str,
            "open": round(open_price, 5),
            "high": round(high, 5),
            "low": round(low, 5),
            "close": round(close_price, 5),
            "isBull": close_price >= open_price
        })
        
        price = close_price
    
    return jsonify({
        "success": True,
        "asset": asset,
        "candles": candles
    })

@app.route('/')
def home():
    return jsonify({
        "status": "Online",
        "pairs": ["USDBRL-OTC", "USDCOP-OTC", "USDEGP-OTC"],
        "endpoints": ["/candles?asset=USDBRL-OTC&count=50", "/health"]
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

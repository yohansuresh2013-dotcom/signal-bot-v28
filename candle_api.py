from flask import Flask, jsonify, request
from flask_cors import CORS
from QuotexAPI import QuotexAPI
import asyncio
import os

app = Flask(__name__)
CORS(app)

QUOTEX_EMAIL = "wasihar465@4nly.com"
QUOTEX_PASS = "VIKRANTH2009"

async def fetch_real_candles(asset, count=50):
    api = QuotexAPI(email=QUOTEX_EMAIL, password=QUOTEX_PASS)
    try:
        await api.connect()
        await api.change_balance("PRACTICE")
        candles = await api.get_candles(asset=asset, period=60)
        await api.disconnect()
        
        result = []
        for c in candles[-count:]:
            result.append({
                "time": str(c.get('time',''))[-8:-3] if c.get('time') else "--:--",
                "open": float(c.get('open',0)),
                "high": float(c.get('high',0)),
                "low": float(c.get('low',0)),
                "close": float(c.get('close',0)),
                "isBull": float(c.get('close',0)) >= float(c.get('open',0))
            })
        return result
    except Exception as e:
        print(f"Quotex error: {e}")
        return []
    finally:
        try: await api.disconnect()
        except: pass

@app.route('/health')
def health():
    return jsonify({"status": "ok"}), 200

@app.route('/candles')
def get_candles():
    asset = request.args.get('asset', 'USDBRL-OTC')
    count = int(request.args.get('count', 50))
    try:
        candles = asyncio.run(fetch_real_candles(asset, count))
        return jsonify({"success": True, "asset": asset, "candles": candles})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/')
def home():
    return jsonify({"status": "Online", "pairs": ["USDBRL-OTC","USDCOP-OTC","USDEGP-OTC"]})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

from flask import Flask, jsonify, request
from flask_cors import CORS
import asyncio
from QuotexAPI import QuotexAPI

app = Flask(__name__)
CORS(app)

QUOTEX_EMAIL = "wasihar465@4nly.com"
QUOTEX_PASS = "VIKRANTH2009"

async def fetch_candles(asset, period=60, count=50):
    """Fetch real candles from Quotex"""
    api = QuotexAPI(email=QUOTEX_EMAIL, password=QUOTEX_PASS)
    try:
        await api.connect()
        await api.change_balance("PRACTICE")
        candles = await api.get_candles(asset=asset, period=period)
        await api.disconnect()
        
        # Format for chart
        result = []
        for c in candles[-count:]:
            result.append({
                "time": str(c.get('time', ''))[-8:-3] if c.get('time') else "--:--",
                "open": float(c.get('open', 0)),
                "high": float(c.get('high', 0)),
                "low": float(c.get('low', 0)),
                "close": float(c.get('close', 0)),
                "isBull": float(c.get('close', 0)) >= float(c.get('open', 0))
            })
        return result
    except Exception as e:
        print(f"Error: {e}")
        return []
    finally:
        try:
            await api.disconnect()
        except:
            pass

@app.route('/candles')
def get_candles():
    asset = request.args.get('asset', 'USDBRL-OTC')
    period = int(request.args.get('period', 60))
    count = int(request.args.get('count', 50))
    
    try:
        candles = asyncio.run(fetch_candles(asset, period, count))
        return jsonify({"success": True, "candles": candles, "asset": asset})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/')
def home():
    return jsonify({"status": "Quotex Candle API", "endpoints": ["/candles?asset=USDBRL-OTC&period=60&count=50"]})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

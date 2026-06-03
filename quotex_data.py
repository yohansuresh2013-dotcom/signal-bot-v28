import asyncio
from QuotexAPI import QuotexAPI

async def get_candles(asset="USDBRL-OTC", period=60, count=10):
    """Fetch candles from Quotex"""
    api = QuotexAPI(
        email="wasihar465@4nly.com",
        password="VIKRANTH2009"
    )
    await api.connect()
    await api.change_balance("PRACTICE")
    candles = await api.get_candles(asset=asset, period=period)
    await api.disconnect()
    return candles[-count:] if candles else []

async def get_payout(asset="USDBRL-OTC"):
    """Get payout percentage"""
    api = QuotexAPI(
        email="wasihar465@4nly.com",
        password="VIKRANTH2009"
    )
    await api.connect()
    await api.change_balance("PRACTICE")
    payout = await api.get_payout(asset)
    await api.disconnect()
    return payout

async def get_all_assets():
    """Get available OTC assets"""
    api = QuotexAPI(
        email="wasihar465@4nly.com",
        password="VIKRANTH2009"
    )
    await api.connect()
    await api.change_balance("PRACTICE")
    assets = await api.get_assets()
    await api.disconnect()
    otc = [a for a in assets if 'OTC' in str(a.get('name',''))]
    return otc

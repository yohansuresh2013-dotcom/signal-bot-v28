import asyncio
import logging
from datetime import datetime, timedelta
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode
import re
import json
import os

# ==================== CONFIGURATION ====================
BOT_TOKEN = "8586468507:AAHy5MTwjTp-uGDW6UffwM6EiW62m69nxZg"
DEFAULT_CHANNEL = "@botsignal007"

# ==================== LOGGING ====================
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== FILES ====================
HISTORY_FILE = "signal_history.json"

# ==================== STORAGE ====================
user_data = {}
processed_results = {}

# ==================== TRACKER ====================
class WinLossTracker:
    def __init__(self):
        self.stats = {'total': 0, 'wins': 0, 'losses': 0, 'mtg_wins': 0, 'avoids': 0}
        self.history = []
    
    def add_result(self, signal_data, result, signal_id):
        if signal_id in processed_results: return
        processed_results[signal_id] = result
        if result == 'WIN': self.stats['wins'] += 1
        elif result == 'LOSS': self.stats['losses'] += 1
        elif result == 'MTG1_WIN': self.stats['mtg_wins'] += 1; self.stats['wins'] += 1
        elif result == 'AVOID': self.stats['avoids'] += 1
        self.stats['total'] += 1
        self.history.append({
            'asset': signal_data['asset'].replace('-OTC', ''),
            'time': signal_data['converted_time'],
            'direction': signal_data['direction'],
            'result': result,
            'date': datetime.now().strftime('%d/%m/%Y %I:%M %p')
        })
        if len(self.history) > 200: self.history = self.history[-200:]
        self.save()
    
    def get_rate(self):
        decided = self.stats.get('wins',0) + self.stats.get('losses',0)
        return (self.stats.get('wins',0) / decided * 100) if decided > 0 else 0
    
    def get_history_text(self, limit=30):
        if not self.history: return "📋 𝙉𝙤 𝙝𝙞𝙨𝙩𝙤𝙧𝙮 𝙮𝙚𝙩"
        recent = self.history[-limit:]
        text = "📊 𝙎𝙄𝙂𝙉𝘼𝙇 𝙃𝙄𝙎𝙏𝙊𝙍𝙔\n\n𝙋𝘼𝙄𝙍      𝙏𝙄𝙈𝙀   𝘿𝙄𝙍   𝙍𝙀𝙎𝙐𝙇𝙏\n" + "─"*40 + "\n"
        w = l = m = a = 0
        for sig in recent:
            pair = sig['asset'][:8]; time = sig['time']
            dir_short = 'CAL' if sig['direction'] == 'CALL' else 'PUT'
            if sig['result'] == 'WIN': res = '✅ 𝙒𝙄𝙉'; w += 1
            elif sig['result'] == 'LOSS': res = '❌ 𝙇𝙊𝙎'; l += 1
            elif sig['result'] == 'MTG1_WIN': res = '🔄 𝙈-𝙒𝙄𝙉'; m += 1
            else: res = '⚠️ 𝘼𝙑𝘿'; a += 1
            text += f"{pair:<8}  {time}  {dir_short}   {res}\n"
        text += "─"*40 + f"\n𝙏𝙊𝙏: {w+l+m+a} | 𝙒:{w} 𝙇:{l} 𝙈:{m} 𝘼:{a} | 𝙒𝙍:{self.get_rate():.1f}%\n" + "─"*40
        return text
    
    def get_mood_message(self):
        """Get mood message based on win rate"""
        wr = self.get_rate()
        total = self.stats['total']
        
        if total == 0:
            return ""
        
        if wr >= 100:
            return """╔══════════════════════════════════╗
║  🏆 𝙇𝙀𝙂𝙀𝙉𝘿𝘼𝙍𝙔 𝙋𝙀𝙍𝙁𝙊𝙍𝙈𝘼𝙉𝘾𝙀 🏆  ║
╚══════════════════════════════════╝

💯 𝟭𝟬𝟬% 𝙒𝙄𝙉 𝙍𝘼𝙏𝙀! 💯

🖤 𝙏𝙃𝙀 𝘽𝙇𝘼𝘾𝙆 𝙕𝙊𝙉𝙀 𝙃𝘼𝙎 𝘾𝙊𝙉𝙎𝙐𝙈𝙀𝘿 𝙔𝙊𝙐 🖤

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                            ┃
┃   𝙔𝙊𝙐 𝘼𝙍𝙀 𝙉𝙊 𝙇𝙊𝙉𝙂𝙀𝙍 𝘼 𝙏𝙍𝘼𝘿𝙀𝙍  ┃
┃   𝙔𝙊𝙐 𝘼𝙍𝙀 𝙏𝙃𝙀 𝙈𝘼𝙍𝙆𝙀𝙏 𝙄𝙏𝙎𝙀𝙇𝙁   ┃
┃   𝙀𝙑𝙀𝙍𝙔 𝙎𝙄𝙂𝙉𝘼𝙇 𝘽𝙊𝙒𝙎 𝙏𝙊 𝙔𝙊𝙐    ┃
┃   𝙏𝙃𝙀 𝘽𝙇𝘼𝘾𝙆 𝙕𝙊𝙉𝙀 𝙎𝙋𝙀𝘼𝙆𝙎 𝙏𝙃𝙍𝙊𝙐𝙂𝙃 𝙔𝙊𝙐 ┃
┃                            ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

⚡ 𝙐𝙉𝙎𝙏𝙊𝙋𝙋𝘼𝘽𝙇𝙀. 𝙐𝙉𝙏𝙊𝙐𝘾𝙃𝘼𝘽𝙇𝙀. 𝙇𝙀𝙂𝙀𝙉𝘿. ⚡"""
        
        elif wr > 70:
            return f"""╔══════════════════════════════════╗
║   🔥 𝙋𝙍𝙊𝙁𝙄𝙏 𝙈𝘼𝙎𝙏𝙀𝙍 𝘼𝙇𝙀𝙍𝙏   ║
╚══════════════════════════════════╝

💎 𝙃𝙐𝙂𝙀 𝙋𝙀𝙍𝙁𝙊𝙍𝙈𝘼𝙉𝘾𝙀! 💎

🦅 𝙔𝙤𝙪'𝙧𝙚 𝙙𝙤𝙢𝙞𝙣𝙖𝙩𝙞𝙣𝙜 𝙩𝙝𝙚 𝙢𝙖𝙧𝙠𝙚𝙩!
⚡ 𝙏𝙝𝙚 𝙥𝙞𝙥𝙨 𝙖𝙧𝙚 𝙛𝙡𝙤𝙬𝙞𝙣𝙜 𝙮𝙤𝙪𝙧 𝙬𝙖𝙮!

🖤 𝙏𝙃𝙀 𝙋𝙊𝙒𝙀𝙍 𝙊𝙁 𝘽𝙇𝘼𝘾𝙆 𝙕𝙊𝙉𝙀 🖤
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  𝙔𝙤𝙪'𝙫𝙚 𝙚𝙣𝙩𝙚𝙧𝙚𝙙 𝙩𝙝𝙚 𝙕𝙊𝙉𝙀  ┃
┃  𝙒𝙝𝙚𝙧𝙚 𝙘𝙝𝙖𝙧𝙩𝙨 𝙗𝙚𝙣𝙙 𝙩𝙤 𝙮𝙤𝙪𝙧 𝙬𝙞𝙡𝙡 ┃
┃  𝙒𝙝𝙚𝙧𝙚 𝙡𝙤𝙨𝙨𝙚𝙨 𝙛𝙚𝙖𝙧 𝙩𝙤 𝙚𝙣𝙩𝙚𝙧  ┃
┃  𝙒𝙝𝙚𝙧𝙚 𝙈𝙏𝙂𝟭 𝙗𝙚𝙘𝙤𝙢𝙚𝙨 𝙬𝙚𝙖𝙥𝙤𝙣   ┃
┃  𝙏𝙃𝙄𝙎 𝙄𝙎 𝙔𝙊𝙐𝙍 𝙏𝙀𝙍𝙍𝙄𝙏𝙊𝙍𝙔    ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

👑 𝙆𝙀𝙀𝙋 𝙍𝙐𝙇𝙄𝙉𝙂 𝙏𝙃𝙀 𝙈𝘼𝙍𝙆𝙀𝙏!
🔥 𝙏𝙃𝙀 𝙕𝙊𝙉𝙀 𝙄𝙎 𝙔𝙊𝙐𝙍𝙎!"""
        
        elif wr >= 50:
            return f"""╔══════════════════════════════════╗
║    ⚖️ 𝙋𝙀𝙍𝙁𝙊𝙍𝙈𝘼𝙉𝘾𝙀 𝙐𝙋𝘿𝘼𝙏𝙀    ║
╚══════════════════════════════════╝

📊 𝙎𝙩𝙚𝙖𝙙𝙮 𝙥𝙧𝙤𝙜𝙧𝙚𝙨𝙨... 𝙆𝙚𝙚𝙥 𝙜𝙤𝙞𝙣𝙜!

💡 𝙏𝙄𝙋𝙎:
├─ 🎯 𝙁𝙤𝙘𝙪𝙨 𝙤𝙣 𝙝𝙞𝙜𝙝-𝙘𝙤𝙣𝙛𝙞𝙙𝙚𝙣𝙘𝙚 𝙨𝙚𝙩𝙪𝙥𝙨
├─ 📈 𝙏𝙧𝙖𝙘𝙠 𝙮𝙤𝙪𝙧 𝙗𝙚𝙨𝙩 𝙥𝙖𝙞𝙧𝙨
└─ 💰 𝙆𝙚𝙚𝙥 𝙘𝙤𝙣𝙨𝙞𝙨𝙩𝙚𝙣𝙩 𝙡𝙤𝙩 𝙨𝙞𝙯𝙚

🏆 𝙆𝙀𝙀𝙋 𝙋𝙐𝙎𝙃𝙄𝙉𝙂!"""
        
        else:
            return f"""╔══════════════════════════════════╗
║     💔 𝙋𝙀𝙍𝙁𝙊𝙍𝙈𝘼𝙉𝘾𝙀 𝘼𝙇𝙀𝙍𝙏     ║
╚══════════════════════════════════╝

😢 𝙏𝙤𝙪𝙜𝙝 𝙙𝙖𝙮 𝙞𝙣 𝙩𝙝𝙚 𝙢𝙖𝙧𝙠𝙚𝙩...

📉 𝙇𝙤𝙨𝙨𝙚𝙨 𝙝𝙖𝙥𝙥𝙚𝙣 𝙩𝙤 𝙚𝙫𝙚𝙧𝙮 𝙩𝙧𝙖𝙙𝙚𝙧
💪 𝙏𝙝𝙞𝙨 𝙞𝙨 𝙣𝙤𝙩 𝙮𝙤𝙪𝙧 𝙚𝙣𝙙

🔄 𝙍𝙀𝘾𝙊𝙑𝙀𝙍𝙔 𝘼𝘿𝙑𝙄𝘾𝙀:
├─ 📏 𝙍𝙚𝙙𝙪𝙘𝙚 𝙡𝙤𝙩 𝙨𝙞𝙯𝙚 𝙗𝙮 𝟱𝟬%
├─ ⏸️ 𝙏𝙖𝙠𝙚 𝙖 𝟯𝟬-𝙢𝙞𝙣 𝙗𝙧𝙚𝙖𝙠
├─ 📊 𝙍𝙚𝙫𝙞𝙚𝙬 𝙮𝙤𝙪𝙧 𝙨𝙩𝙧𝙖𝙩𝙚𝙜𝙮
├─ 🎯 𝙎𝙩𝙞𝙘𝙠 𝙩𝙤 𝙈𝙏𝙂𝟭 𝙤𝙣𝙡𝙮
└─ 🧘 𝙎𝙩𝙖𝙮 𝙘𝙖𝙡𝙢, 𝙙𝙤𝙣'𝙩 𝙧𝙚𝙫𝙚𝙣𝙜𝙚 𝙩𝙧𝙖𝙙𝙚

⚠️ 𝙍𝙀𝙈𝙀𝙈𝘽𝙀𝙍:
"𝙀𝙫𝙚𝙧𝙮 𝙡𝙤𝙨𝙨 𝙞𝙨 𝙖 𝙡𝙚𝙨𝙨𝙤𝙣, 𝙣𝙤𝙩 𝙖 𝙛𝙖𝙞𝙡𝙪𝙧𝙚"

🌟 𝙏𝙤𝙢𝙤𝙧𝙧𝙤𝙬 𝙞𝙨 𝙖 𝙣𝙚𝙬 𝙙𝙖𝙮!"""
    
    def reset_stats(self):
        self.stats = {'total': 0, 'wins': 0, 'losses': 0, 'mtg_wins': 0, 'avoids': 0}
        self.history = []; processed_results.clear()
        self.save()
        if os.path.exists(HISTORY_FILE): os.remove(HISTORY_FILE)
    
    def save(self):
        try:
            with open(HISTORY_FILE, 'w') as f: 
                json.dump({'stats': self.stats, 'history': self.history, 'processed': processed_results}, f)
        except: pass
    
    def load(self):
        try:
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE, 'r') as f:
                    data = json.load(f)
                self.stats = data.get('stats', {'total': 0, 'wins': 0, 'losses': 0, 'mtg_wins': 0, 'avoids': 0})
                self.history = data.get('history', [])
                for k, v in data.get('processed', {}).items(): processed_results[k] = v
        except: pass

tracker = WinLossTracker()

# ==================== PER-USER DATA ====================
def get_ud(user_id):
    if user_id not in user_data:
        user_data[user_id] = {
            'scheduled_signals': {}, 'active_tasks': {}, 'pending_results': {},
            'channels': [DEFAULT_CHANNEL], 'current_channel': DEFAULT_CHANNEL,
            'countdown_active': True
        }
    return user_data[user_id]

# ==================== HELPERS ====================
def to_font(text):
    font_map = {
        'A':'𝘼','B':'𝘽','C':'𝘾','D':'𝘿','E':'𝙀','F':'𝙁','G':'𝙂','H':'𝙃','I':'𝙄','J':'𝙅','K':'𝙆','L':'𝙇','M':'𝙈',
        'N':'𝙉','O':'𝙊','P':'𝙋','Q':'𝙌','R':'𝙍','S':'𝙎','T':'𝙏','U':'𝙐','V':'𝙑','W':'𝙒','X':'𝙓','Y':'𝙔','Z':'𝙕',
        'a':'𝙖','b':'𝙗','c':'𝙘','d':'𝙙','e':'𝙚','f':'𝙛','g':'𝙜','h':'𝙝','i':'𝙞','j':'𝙟','k':'𝙠','l':'𝙡','m':'𝙢',
        'n':'𝙣','o':'𝙤','p':'𝙥','q':'𝙦','r':'𝙧','s':'𝙨','t':'𝙩','u':'𝙪','v':'𝙫','w':'𝙬','x':'𝙭','y':'𝙮','z':'𝙯',
        '0':'𝟬','1':'𝟭','2':'𝟮','3':'𝟯','4':'𝟰','5':'𝟱','6':'𝟲','7':'𝟳','8':'𝟴','9':'𝟵',
    }
    return ''.join(font_map.get(c, c) for c in str(text))

def parse_signals(text):
    signals = []
    lines = text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line: continue
        clean = line.replace('🧪', '').replace('🦅', '').replace('🐻', '').replace('🦁', '').strip()
        match = re.search(r'([A-Za-z0-9-]+(?:-OTC)?)\s*☞\s*(\d{1,2}:\d{2})\s*(CALL|PUT)', clean, re.IGNORECASE)
        if not match: match = re.search(r'([A-Za-z0-9-]+(?:-OTC)?)\s+(\d{1,2}:\d{2})\s+(CALL|PUT)', clean, re.IGNORECASE)
        if match: signals.append({'asset': match.group(1).strip(), 'time': match.group(2).strip(), 'direction': match.group(3).upper()})
    return signals

def convert_time(time_str):
    try:
        h, m = map(int, time_str.split(':')); total = h * 60 + m - 30
        if total < 0: total += 1440
        return f"{(total//60)%24:02d}:{total%60:02d}"
    except: return time_str

def get_conf(): return random.randint(82, 98)

# ==================== GLITCH EFFECT ====================
def glitch_text(text):
    style = random.randint(1, 4)
    if style == 1: return text
    elif style == 2:
        result = ""
        for c in text:
            if c in "0123456789:": result += c + "\u0337"
            else: result += c
        return result
    elif style == 3:
        result = ""
        for c in text:
            if c in "0123456789:": result += c + "\u0334"
            else: result += c
        return result
    else:
        zalgo = "\u0337\u033E\u0323\u0328"
        result = ""
        for c in text:
            if c in "0123456789:": result += c + random.choice(zalgo) + random.choice(zalgo)
            else: result += c
        return result

def fmt_countdown_glitch(minutes, seconds, last_10=False):
    text = f"{minutes:02d}:{seconds:02d}"
    if last_10: return glitch_text(text)
    elif seconds % random.randint(3, 5) == 0: return glitch_text(text)
    else: return text

# ==================== KEYBOARDS ====================
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 𝙇𝙤𝙖𝙙 𝙎𝙞𝙜𝙣𝙖𝙡𝙨", callback_data="load")],
        [InlineKeyboardButton("📊 𝙎𝙘𝙝𝙚𝙙𝙪𝙡𝙚𝙙", callback_data="signals"), InlineKeyboardButton("📈 𝙎𝙩𝙖𝙩𝙨", callback_data="stats")],
        [InlineKeyboardButton("📋 𝙃𝙞𝙨𝙩𝙤𝙧𝙮", callback_data="history"), InlineKeyboardButton("📝 𝙋𝙚𝙣𝙙𝙞𝙣𝙜", callback_data="pending")],
        [InlineKeyboardButton("📢 𝘾𝙝𝙖𝙣𝙣𝙚𝙡𝙨", callback_data="channels"), InlineKeyboardButton("🔄 𝙍𝙚𝙨𝙚𝙩", callback_data="reset")],
        [InlineKeyboardButton("🗑️ 𝘾𝙡𝙚𝙖𝙧", callback_data="clear")]
    ])

def ch_kb(user_id):
    ud = get_ud(user_id); cur = ud['current_channel']
    btns = []
    for ch in ud['channels'][:6]:
        m = "🟢 " if ch == cur else ""
        btns.append([InlineKeyboardButton(f"{m}{ch}", callback_data=f"ch_{ch}")])
    btns.append([InlineKeyboardButton("➕ 𝘼𝙙𝙙", callback_data="ch_new")])
    btns.append([InlineKeyboardButton("✅ 𝙐𝙨𝙚 𝘾𝙪𝙧𝙧𝙚𝙣𝙩", callback_data="ch_skip")])
    btns.append([InlineKeyboardButton("🔙 𝘽𝙖𝙘𝙠", callback_data="start")])
    return InlineKeyboardMarkup(btns)

def res_kb(sid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ 𝙒𝙄𝙉", callback_data=f"w_{sid}"), InlineKeyboardButton("❌ 𝙇𝙊𝙎𝙎", callback_data=f"l_{sid}")],
        [InlineKeyboardButton("🔄 𝙈𝙏𝙂𝟭 𝙒𝙄𝙉", callback_data=f"mw_{sid}"), InlineKeyboardButton("⚠️ 𝘼𝙑𝙊𝙄𝘿", callback_data=f"a_{sid}")]
    ])

def countdown_kb(user_id):
    ud = get_ud(user_id)
    if ud['countdown_active']:
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔴 𝙊𝙁𝙁 𝙏𝙄𝙈𝙀𝙍", callback_data="timer_off")]])
    else:
        return InlineKeyboardMarkup([[InlineKeyboardButton("🟢 𝙊𝙉 𝙏𝙄𝙈𝙀𝙍", callback_data="timer_on")]])

# ==================== FORMATTERS ====================
def fmt_signal(sig, sid, ch):
    a = sig['asset']; t = sig['converted_time']; d = sig['direction']
    if d == 'CALL': de = "🟢"; di = "📈"; dl = "𝘾𝘼𝙇𝙇 / 𝘽𝙐𝙔"
    else: de = "🔴"; di = "📉"; dl = "𝙋𝙐𝙏 / 𝙎𝙀𝙇𝙇"
    return f"""╔══════════════════════════════════╗
║     🎯 𝙏𝙍𝘼𝘿𝙄𝙉𝙂 𝙎𝙄𝙂𝙉𝘼𝙇     ║
╚══════════════════════════════════╝

💎 𝘼𝙎𝙎𝙀𝙏
   └─ {to_font(a)}

⏰ 𝙏𝙍𝘼𝘿𝙀 𝙏𝙄𝙈𝙀 (𝙐𝙏𝘾+5:30)
   └─ {to_font(t)}

📊 𝘿𝙄𝙍𝙀𝘾𝙏𝙄𝙊𝙉
   └─ {de} {dl} {di}

🔄 𝙈𝙏𝙂𝟭

╔══════════════════════════════════╗
║  ⚡ 𝙋𝙍𝙀𝙈𝙄𝙐𝙈 𝙎𝙄𝙂𝙉𝘼𝙇 • 𝘼𝘾𝙏𝙄𝙑𝙀 ⚡  ║
║  📱 {ch}              ║
╚══════════════════════════════════╝"""

def fmt_next_box():
    return """╔══════════════════════════════════╗
║        ⏭️ 𝙉𝙀𝙓𝙏 𝙎𝙄𝙂𝙉𝘼𝙇        ║
╚══════════════════════════════════╝

⏳ 𝙏𝙄𝙈𝙀 𝙍𝙀𝙈𝘼𝙄𝙉𝙄𝙉𝙂"""

def fmt_countdown_line(minutes, seconds, last_10=False):
    time_text = fmt_countdown_glitch(minutes, seconds, last_10)
    return f"   └─ {time_text}"

def fmt_result(sig, result, sid, ch):
    a = sig['asset']; t = sig['converted_time']; d = sig['direction']
    pair = a.replace('-OTC', '')
    if result == 'WIN': ri = "✅"; rt = "𝙒𝙄𝙉𝙉𝙀𝙍"
    elif result == 'LOSS': ri = "❌"; rt = "𝙇𝙊𝙎𝙎"
    elif result == 'MTG1_WIN': ri = "🔄"; rt = "𝙈𝙏𝙂𝟭 𝙒𝙄𝙉"
    else: ri = "⚠️"; rt = "𝘼𝙑𝙊𝙄𝘿"
    return f"""╔══════════════════════════════════╗
║     📊 𝙎𝙄𝙂𝙉𝘼𝙇 𝙍𝙀𝙎𝙐𝙇𝙏      ║
╚══════════════════════════════════╝

{ri} {rt}

💎 {to_font(pair)}
⏰ {t}
📊 {'🟢' if d == 'CALL' else '🔴'} {d}

📈 𝙒:{tracker.stats.get('wins',0)} 𝙇:{tracker.stats.get('losses',0)} | 𝙒𝙍:{tracker.get_rate():.1f}%

╔══════════════════════════════════╗
║  📱 {ch}              ║
╚══════════════════════════════════╝"""

# ==================== CALLBACK HANDLER ====================
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; d = q.data; uid = q.from_user.id
    await q.answer()
    ud = get_ud(uid)
    
    if d == 'timer_off':
        ud['countdown_active'] = False
        await q.edit_message_reply_markup(reply_markup=countdown_kb(uid))
        return
    if d == 'timer_on':
        ud['countdown_active'] = True
        await q.edit_message_reply_markup(reply_markup=countdown_kb(uid))
        return
    
    if d.startswith('w_') or d.startswith('l_') or d.startswith('mw_') or d.startswith('a_'):
        if d.startswith('mw_'): sid = d[3:]; result = 'MTG1_WIN'
        elif d.startswith('w_'): sid = d[2:]; result = 'WIN'
        elif d.startswith('l_'): sid = d[2:]; result = 'LOSS'
        else: sid = d[2:]; result = 'AVOID'
        if sid in processed_results: await q.edit_message_text("⚠️ 𝘼𝙡𝙧𝙚𝙖𝙙𝙮 𝙧𝙚𝙘𝙤𝙧𝙙𝙚𝙙!"); return
        if sid not in ud['pending_results']: await q.edit_message_text("⚠️ 𝙉𝙤𝙩 𝙛𝙤𝙪𝙣𝙙"); return
        info = ud['pending_results'][sid]; sd = info['signal']
        tracker.add_result(sd, result, sid)
        ch = ud['current_channel']
        try: await context.bot.send_message(chat_id=ch, text=fmt_result(sd, result, sid, ch))
        except: pass
        emap = {'WIN': '✅ 𝙒𝙄𝙉', 'LOSS': '❌ 𝙇𝙊𝙎𝙎', 'MTG1_WIN': '🔄 𝙈𝙏𝙂𝟭 𝙒𝙄𝙉', 'AVOID': '⚠️ 𝘼𝙑𝙊𝙄𝘿'}
        sh = sid[-4:] if len(sid) >= 4 else sid
        await q.edit_message_text(f"{emap[result]} #{sh}\n📊 {sd['asset']}\n⏰ {sd['converted_time']}\n📈 𝙒𝙍:{tracker.get_rate():.1f}%")
        if sid in ud['pending_results']: del ud['pending_results'][sid]
        return
    
    if d.startswith('ch_'):
        ch = d[3:]
        if ch == 'new': context.user_data['wait'] = True; await q.edit_message_text("📝 𝙎𝙚𝙣𝙙 𝙪𝙨𝙚𝙧𝙣𝙖𝙢𝙚:\n@my_channel"); return
        if ch == 'skip': sel = ud['current_channel']
        else: sel = ch; ud['current_channel'] = sel
        if sel not in ud['channels']: ud['channels'].insert(0, sel)
        act = context.user_data.get('pact', '')
        if act == 'history':
            hist = tracker.get_history_text(30)
            mood = tracker.get_mood_message()
            full_text = f"```\n{hist}\n```"
            try: await context.bot.send_message(chat_id=sel, text=full_text, parse_mode=ParseMode.MARKDOWN)
            except: await context.bot.send_message(chat_id=sel, text=hist)
            if mood:
                try: await context.bot.send_message(chat_id=sel, text=mood)
                except: pass
            await q.edit_message_text(f"✅ 𝙋𝙤𝙨𝙩𝙚𝙙 𝙩𝙤 {sel}", reply_markup=main_menu())
        else:
            await q.edit_message_text(f"✅ {sel}\n📝 𝙋𝙖𝙨𝙩𝙚 𝙨𝙞𝙜𝙣𝙖𝙡𝙨 𝙣𝙤𝙬...")
        context.user_data['pact'] = ''
        return
    
    if d == "start":
        ch = ud['current_channel']
        txt = f"""🤖 𝙎𝙄𝙂𝙉𝘼𝙇 𝘽𝙊𝙏 𝙫𝟮𝟴

👤 {uid} | 📢 {ch}
📊 𝘼𝙘𝙩𝙞𝙫𝙚: {len(ud['scheduled_signals'])} | 𝙋𝙚𝙣𝙙𝙞𝙣𝙜: {len(ud['pending_results'])}
📈 𝙒:{tracker.stats.get('wins',0)} 𝙇:{tracker.stats.get('losses',0)} 𝙈:{tracker.stats.get('mtg_wins',0)} 𝘼:{tracker.stats.get('avoids',0)} | 𝙒𝙍:{tracker.get_rate():.1f}%
⏱️ 𝙏𝙞𝙢𝙚𝙧: {'🟢 𝙊𝙉' if ud['countdown_active'] else '🔴 𝙊𝙁𝙁'}
👇 𝙎𝙚𝙡𝙚𝙘𝙩:"""
        await q.edit_message_text(txt, reply_markup=main_menu())
        return
    
    if d == "load": context.user_data['pact'] = 'load'; await q.edit_message_text("📢 𝙎𝙚𝙡𝙚𝙘𝙩 𝙘𝙝𝙖𝙣𝙣𝙚𝙡:", reply_markup=ch_kb(uid)); return
    if d == "signals":
        if not ud['scheduled_signals']: await q.edit_message_text("📋 𝙉𝙤𝙣𝙚", reply_markup=main_menu()); return
        ss = sorted(ud['scheduled_signals'].items(), key=lambda x: x[1]['scheduled_time'])
        now = datetime.utcnow() + timedelta(hours=5, minutes=30)
        txt = f"📊 𝙎𝘾𝙃𝙀𝘿𝙐𝙇𝙀𝘿 ({len(ss)})\n\n"
        for i, (sid, sd) in enumerate(ss[:10], 1):
            sig = sd['signal']; df = sd['scheduled_time'] - now
            if df.total_seconds() > 0:
                m = int(df.total_seconds() // 60)
                lf = f"{m//60}𝙝{m%60}𝙢" if m >= 60 else f"{m}𝙢"
            else: lf = "𝙉𝙤𝙬"
            em = "🟢" if sig['direction'] == 'CALL' else "🔴"; sh = sid[-4:] if len(sid) >= 4 else sid
            txt += f"{i}. #{sh} ⏰ {sig['converted_time']} | {em} {sig['direction']} | ⏳{lf}\n"
        if len(ss) > 10: txt += f"\n...{len(ss)-10} 𝙢𝙤𝙧𝙚"
        await q.edit_message_text(txt, reply_markup=main_menu())
        return
    if d == "stats":
        txt = f"📊 𝙎𝙏𝘼𝙏𝙎\n\n𝙒:{tracker.stats.get('wins',0)} 𝙇:{tracker.stats.get('losses',0)} 𝙈:{tracker.stats.get('mtg_wins',0)} 𝘼:{tracker.stats.get('avoids',0)}\n𝙒𝙍:{tracker.get_rate():.1f}%"
        await q.edit_message_text(txt, reply_markup=main_menu()); return
    if d == "history": context.user_data['pact'] = 'history'; await q.edit_message_text("📋 𝙎𝙚𝙡𝙚𝙘𝙩 𝙜𝙧𝙤𝙪𝙥:", reply_markup=ch_kb(uid)); return
    if d == "pending":
        if not ud['pending_results']: await q.edit_message_text("📋 𝙉𝙤𝙣𝙚", reply_markup=main_menu()); return
        for sid, info in list(ud['pending_results'].items())[:1]:
            sig = info['signal']; em = "🟢" if sig['direction'] == 'CALL' else "🔴"; sh = sid[-4:] if len(sid) >= 4 else sid
            await q.edit_message_text(f"📊 #{sh}\n💎 {sig['asset']}\n⏰ {sig['converted_time']}\n📈 {em} {sig['direction']}\n\n𝙍𝙚𝙘𝙤𝙧𝙙:", reply_markup=res_kb(sid))
        for sid, info in list(ud['pending_results'].items())[1:6]:
            sig = info['signal']; em = "🟢" if sig['direction'] == 'CALL' else "🔴"; sh = sid[-4:] if len(sid) >= 4 else sid
            await q.message.reply_text(f"📊 #{sh}\n💎 {sig['asset']}\n⏰ {sig['converted_time']}\n📈 {em} {sig['direction']}\n\n𝙍𝙚𝙘𝙤𝙧𝙙:", reply_markup=res_kb(sid))
        return
    if d == "channels":
        ch = ud['current_channel']; chs = ud['channels']
        txt = f"📢 𝘾𝙃𝘼𝙉𝙉𝙀𝙇𝙎\n\n🟢 {ch}\n\n"
        for i, c in enumerate(chs, 1): txt += f"{i}. {c}\n"
        await q.edit_message_text(txt, reply_markup=main_menu()); return
    if d == "reset": tracker.reset_stats(); await q.edit_message_text("✅ 𝙍𝙚𝙨𝙚𝙩!", reply_markup=main_menu()); return
    if d == "clear":
        for t in list(ud['active_tasks'].values()):
            if not t.done(): t.cancel()
        sc = len(ud['scheduled_signals']); pc = len(ud['pending_results'])
        ud['active_tasks'].clear(); ud['scheduled_signals'].clear(); ud['pending_results'].clear()
        await q.edit_message_text(f"✅ {sc} 𝙨𝙞𝙜𝙣𝙖𝙡𝙨 & {pc} 𝙥𝙚𝙣𝙙𝙞𝙣𝙜 𝙘𝙡𝙚𝙖𝙧𝙚𝙙", reply_markup=main_menu()); return

# ==================== MESSAGE HANDLER ====================
async def msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; ud = get_ud(uid)
    text = update.message.text.strip()
    
    if context.user_data.get('wait'):
        if not text.startswith('@'): text = '@' + text
        ud['current_channel'] = text
        if text not in ud['channels']: ud['channels'].insert(0, text)
        context.user_data['wait'] = False
        await update.message.reply_text(f"✅ {text}\n📝 𝙋𝙖𝙨𝙩𝙚 𝙨𝙞𝙜𝙣𝙖𝙡𝙨 𝙣𝙤𝙬...")
        return
    
    if 'OTC' in text.upper() or '☞' in text:
        parsed = parse_signals(text)
        if not parsed:
            await update.message.reply_text("❌ 𝙉𝙤 𝙫𝙖𝙡𝙞𝙙 𝙨𝙞𝙜𝙣𝙖𝙡𝙨!")
            return
        parsed.sort(key=lambda x: x['time'])
        ok = 0
        for sig in parsed:
            ct = convert_time(sig['time']); cf = get_conf()
            sd = {'asset': sig['asset'], 'time': sig['time'], 'original_time': sig['time'], 'converted_time': ct, 'direction': sig['direction'], 'confidence': cf}
            o, sid = await sched_signal(context.bot, uid, sd)
            if o: ok += 1
        await update.message.reply_text(f"✅ {ok} 𝙨𝙞𝙜𝙣𝙖𝙡𝙨 𝙨𝙘𝙝𝙚𝙙𝙪𝙡𝙚𝙙!\n📢 {ud['current_channel']}\n⏰ 𝙐𝙏𝘾+𝟱:𝟯𝟬\n🔄 𝙋𝙖𝙨𝙩→𝙏𝙤𝙢𝙤𝙧𝙧𝙤𝙬", reply_markup=main_menu())
        return
    
    ch = ud['current_channel']
    txt = f"""🤖 𝙎𝙄𝙂𝙉𝘼𝙇 𝘽𝙊𝙏 𝙫𝟮𝟴

👤 {uid} | 📢 {ch}
📊 𝘼𝙘𝙩𝙞𝙫𝙚: {len(ud['scheduled_signals'])} | 𝙋𝙚𝙣𝙙𝙞𝙣𝙜: {len(ud['pending_results'])}
📈 𝙒:{tracker.stats.get('wins',0)} 𝙇:{tracker.stats.get('losses',0)} 𝙈:{tracker.stats.get('mtg_wins',0)} 𝘼:{tracker.stats.get('avoids',0)} | 𝙒𝙍:{tracker.get_rate():.1f}%
⏱️ 𝙏𝙞𝙢𝙚𝙧: {'🟢 𝙊𝙉' if ud['countdown_active'] else '🔴 𝙊𝙁𝙁'}
👇 𝙎𝙚𝙡𝙚𝙘𝙩:"""
    await update.message.reply_text(txt, reply_markup=main_menu())

# ==================== SCHEDULING ====================
async def sched_signal(bot, uid, sd):
    ud = get_ud(uid)
    try:
        h, m = map(int, sd['converted_time'].split(':'))
        now = datetime.utcnow() + timedelta(hours=5, minutes=30)
        tgt = now.replace(hour=h, minute=m, second=0, microsecond=0)
        pt = tgt - timedelta(minutes=1)
        if pt <= now: pt += timedelta(days=1)
        delay = (pt - now).total_seconds()
        if delay < 0: return False, None
        sid = f"{sd['asset']}_{sd['converted_time']}_{random.randint(10000,99999)}"
        ud['scheduled_signals'][sid] = {'signal': sd, 'scheduled_time': pt}
        task = asyncio.create_task(post_signal(bot, uid, sid, sd, delay))
        ud['active_tasks'][sid] = task
        return True, sid
    except: return False, None

async def post_signal(bot, uid, sid, sd, delay):
    ud = get_ud(uid)
    try:
        await asyncio.sleep(delay)
        if sid not in ud['scheduled_signals']: return
        ch = ud['current_channel']
        
        next_sig = None
        sorted_sigs = sorted(ud['scheduled_signals'].items(), key=lambda x: x[1]['scheduled_time'])
        now = datetime.utcnow() + timedelta(hours=5, minutes=30)
        for nsid, nsdata in sorted_sigs:
            if nsid != sid and nsdata['scheduled_time'] > now:
                next_sig = nsdata['signal']
                break
        
        await bot.send_message(chat_id=ch, text=fmt_signal(sd, sid, ch))
        
        if next_sig and ud['countdown_active']:
            next_time = next_sig['converted_time']
            nh, nm = map(int, next_time.split(':'))
            next_dt = now.replace(hour=nh, minute=nm, second=0, microsecond=0)
            if next_dt <= now: next_dt += timedelta(days=1)
            total_seconds = int((next_dt - now).total_seconds())
            
            if total_seconds > 0:
                mins = total_seconds // 60
                secs = total_seconds % 60
                next_msg = await bot.send_message(chat_id=ch, text=f"{fmt_next_box()}\n{fmt_countdown_line(mins, secs)}")
                asyncio.create_task(run_countdown(bot, ch, next_msg.message_id, total_seconds, uid))
        
        ud['pending_results'][sid] = {'signal': sd}
        em = "🟢" if sd['direction'] == 'CALL' else "🔴"; sh = sid[-4:] if len(sid) >= 4 else sid
        await bot.send_message(chat_id=uid, text=f"✅ #{sh}\n📊 {sd['asset']}\n⏰ {sd['converted_time']}\n📈 {em} {sd['direction']}\n📢 {ch}\n\n𝙍𝙚𝙘𝙤𝙧𝙙:", reply_markup=res_kb(sid))
        
        if sid in ud['scheduled_signals']: del ud['scheduled_signals'][sid]
        if sid in ud['active_tasks']: del ud['active_tasks'][sid]
    except asyncio.CancelledError:
        if sid in ud['scheduled_signals']: del ud['scheduled_signals'][sid]
    except Exception as e:
        logger.error(f"Post error: {e}")

async def run_countdown(bot, ch, msg_id, total_seconds, uid):
    ud = get_ud(uid)
    for remaining in range(total_seconds, -1, -1):
        if not ud['countdown_active']:
            try: await bot.edit_message_text(chat_id=ch, message_id=msg_id, text=f"{fmt_next_box()}\n⏳ 𝙊𝙁𝙁")
            except: pass
            return
        mins = remaining // 60
        secs = remaining % 60
        last_10 = remaining <= 10
        try:
            await bot.edit_message_text(chat_id=ch, message_id=msg_id, text=f"{fmt_next_box()}\n{fmt_countdown_line(mins, secs, last_10)}")
        except: break
        await asyncio.sleep(1)

async def err(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")

# ==================== MAIN ====================
def main():
    tracker.load()
    print(f"""
╔══════════════════════════════════╗
║  🤖 𝙎𝙄𝙂𝙉𝘼𝙇 𝘽𝙊𝙏 𝙫𝟮𝟴 𝙁𝙄𝙉𝘼𝙇  ║
║  𝘼𝙇𝙇 𝙇𝙊𝙂𝙄𝘾 • 𝘽𝙇𝘼𝘾𝙆 𝙕𝙊𝙉𝙀  ║
╚══════════════════════════════════╝
✅ 𝙍𝙚𝙖𝙙𝙮!
""")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg))
    app.add_handler(CommandHandler("start", msg))
    app.add_error_handler(err)
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == '__main__':
    main()

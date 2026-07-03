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
BOT_TOKEN = "8586468507:AAEac6kwOoo-99H2rogtXImzhbUgReMlt_4"

# ==================== LOGGING ====================
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== FILES ====================
HISTORY_FILE = "signal_history.json"
BACKUP_FILE = "signal_backup.json"
CONFIG_FILE = "bot_config.json"

# ==================== STORAGE ====================
user_data = {}
processed_results = {}
signal_counters = {"BRL": 0, "COP": 0, "EGP": 0}
win_streak = 0
loss_streak = 0
posted_signals = set()
deleted_signals = []
paused_all = False

PAIRS = {
    "BRL": {"name": "USDBRL-OTC", "flag": "🇧🇷", "aliases": ["BRL", "brl", "USDBRL", "usdbrl", "usd/brl"]},
    "COP": {"name": "USDCOP-OTC", "flag": "🇨🇴", "aliases": ["COP", "cop", "USDCOP", "usdcop", "usd/cop"]},
    "EGP": {"name": "USDEGP-OTC", "flag": "🇪🇬", "aliases": ["EGP", "egp", "USDEGP", "usdegp", "usd/egp"]},
}

POST_TIMES = {"30s": 30, "1min": 60, "2min": 120}

# ==================== TRACKER ====================
class WinLossTracker:
    def __init__(self):
        self.stats = {'total': 0, 'wins': 0, 'losses': 0, 'mtg_wins': 0, 'avoids': 0, 'expired': 0}
        self.history = []
        self.daily_stats = {}
        self.last_result = None
        self.best_pair = None
        self.worst_pair = None
    
    def add_result(self, signal_data, result, signal_id):
        if signal_id in processed_results: return
        processed_results[signal_id] = result
        if result == 'WIN': self.stats['wins'] += 1; self.last_result = 'WIN'
        elif result == 'LOSS': self.stats['losses'] += 1; self.last_result = 'LOSS'
        elif result == 'MTG1_WIN': self.stats['mtg_wins'] += 1; self.stats['wins'] += 1; self.last_result = 'WIN'
        elif result == 'AVOID': self.stats['avoids'] += 1; self.last_result = 'AVOID'
        elif result == 'EXPIRED': self.stats['expired'] += 1
        self.stats['total'] += 1
        
        global win_streak, loss_streak
        if result in ['WIN', 'MTG1_WIN']: win_streak += 1; loss_streak = 0
        elif result == 'LOSS': loss_streak += 1; win_streak = 0
        
        today = datetime.now().strftime('%Y-%m-%d')
        if today not in self.daily_stats: self.daily_stats[today] = {'wins': 0, 'losses': 0, 'signals': 0}
        self.daily_stats[today]['signals'] += 1
        if result in ['WIN', 'MTG1_WIN']: self.daily_stats[today]['wins'] += 1
        elif result == 'LOSS': self.daily_stats[today]['losses'] += 1
        
        self.history.append({
            'asset': signal_data['asset'].replace('-OTC', ''),
            'time': signal_data['converted_time'],
            'direction': signal_data['direction'],
            'result': result,
            'pair': signal_data.get('pair', ''),
            'date': datetime.now().strftime('%d/%m/%Y %I:%M %p')
        })
        if len(self.history) > 500: self.history = self.history[-500:]
        self.save()
        self.backup()
    
    def get_rate(self):
        decided = self.stats.get('wins',0) + self.stats.get('losses',0)
        return (self.stats.get('wins',0) / decided * 100) if decided > 0 else 0
    
    def get_streak_text(self):
        global win_streak, loss_streak
        if win_streak >= 5: return f"🔥 {win_streak} WINS STREAK! UNSTOPPABLE!"
        elif win_streak >= 3: return f"🔥 {win_streak} Wins Streak!"
        elif loss_streak >= 3: return f"❄️ {loss_streak} Losses Streak - Reduce Lot!"
        return ""
    
    def get_best_pair(self):
        pair_stats = {}
        for h in self.history:
            p = h.get('pair', 'Unknown')
            if p not in pair_stats: pair_stats[p] = {'w': 0, 'l': 0}
            if h['result'] in ['WIN', 'MTG1_WIN']: pair_stats[p]['w'] += 1
            elif h['result'] == 'LOSS': pair_stats[p]['l'] += 1
        if not pair_stats: return None, None
        best = max(pair_stats.items(), key=lambda x: x[1]['w']/(x[1]['w']+x[1]['l']) if (x[1]['w']+x[1]['l'])>0 else 0)
        worst = min(pair_stats.items(), key=lambda x: x[1]['w']/(x[1]['w']+x[1]['l']) if (x[1]['w']+x[1]['l'])>0 else 1)
        return best, worst
    
    def get_daily_report(self):
        today = datetime.now().strftime('%Y-%m-%d')
        d = self.daily_stats.get(today, {'wins': 0, 'losses': 0, 'signals': 0})
        total = d['wins'] + d['losses']
        rate = (d['wins'] / total * 100) if total > 0 else 0
        return f"""📅 DAILY REPORT ({today})
├─ Signals: {d['signals']}
├─ Wins: {d['wins']} ✅
├─ Losses: {d['losses']} ❌
└─ Rate: {rate:.1f}%"""
    
    def get_history_text(self, limit=30):
        if not self.history: return "📋 No history yet"
        recent = self.history[-limit:]
        text = "📊 SIGNAL HISTORY\n\nPAIR      TIME   DIR   RESULT   #\n" + "─"*50 + "\n"
        w=l=m=a=e=0
        for i, sig in enumerate(recent):
            pair=sig['asset'][:8];time=sig['time']
            ds='CAL' if sig['direction']=='CALL' else 'PUT'
            if sig['result']=='WIN':res='✅ WIN';w+=1
            elif sig['result']=='LOSS':res='❌ LOS';l+=1
            elif sig['result']=='MTG1_WIN':res='🔄 M-WIN';m+=1
            elif sig['result']=='EXPIRED':res='⏰ EXP';e+=1
            else:res='⚠️ AVD';a+=1
            text+=f"{pair:<8} {time} {ds}  {res}\n"
        text+="─"*50+f"\nTOT: {w+l+m+a+e} | W:{w} L:{l} M:{m} A:{a} E:{e} | WR:{self.get_rate():.1f}%\n"+"─"*50
        streak=self.get_streak_text()
        if streak: text+=f"\n{streak}"
        return text
    
    def get_mood_message(self):
        wr=self.get_rate();total=self.stats['total']
        if total==0:return""
        if wr>=100:return"🏆 LEGENDARY! 100% WIN RATE!\n🖤 BLACK ZONE CONSUMED YOU!\n⚡ UNSTOPPABLE. UNTOUCHABLE. LEGEND."
        elif wr>70:return"🔥 PROFIT MASTER!\n🖤 THE ZONE IS YOURS!\n👑 KEEP RULING THE MARKET!"
        elif wr>=50:return"⚖️ STEADY PROGRESS...\n💡 FOCUS ON HIGH-CONFIDENCE SETUPS\n🏆 KEEP PUSHING!"
        else:return"💔 TOUGH DAY IN THE MARKET\n\n🔄 RECOVERY ADVICE:\n├─ 📏 REDUCE LOT SIZE BY 50%\n├─ ⏸️ TAKE A 30-MIN BREAK\n├─ 📊 REVIEW YOUR STRATEGY\n├─ 🎯 STICK TO MTG1 ONLY\n└─ 🧘 STAY CALM, NO REVENGE\n\n🌟 TOMORROW IS A NEW DAY!"
    
    def reset_stats(self):
        self.stats={'total':0,'wins':0,'losses':0,'mtg_wins':0,'avoids':0,'expired':0}
        self.history=[];processed_results.clear();self.daily_stats={}
        global win_streak,loss_streak;win_streak=0;loss_streak=0
        self.save()
        if os.path.exists(HISTORY_FILE):os.remove(HISTORY_FILE)
    
    def save(self):
        try:
            with open(HISTORY_FILE,'w') as f:json.dump({'stats':self.stats,'history':self.history,'daily':self.daily_stats,'processed':processed_results},f)
        except:pass
    
    def backup(self):
        try:
            with open(BACKUP_FILE,'w') as f:json.dump({'stats':self.stats,'history':self.history},f)
        except:pass
    
    def load(self):
        try:
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE,'r') as f:
                    data=json.load(f)
                self.stats=data.get('stats',{'total':0,'wins':0,'losses':0,'mtg_wins':0,'avoids':0,'expired':0})
                self.history=data.get('history',[])
                self.daily_stats=data.get('daily',{})
                for k,v in data.get('processed',{}).items():processed_results[k]=v
        except:pass

tracker = WinLossTracker()

# ==================== PER-USER DATA ====================
def get_ud(user_id):
    if user_id not in user_data:
        user_data[user_id] = {
            'scheduled_signals': {}, 'active_tasks': {}, 'pending_results': {},
            'pair_channels': {"BRL": None, "COP": None, "EGP": None},
            'countdown_active': True, 'selected_pair': None,
            'last_signal_preview': None, 'post_time': 60, 'expiry_minutes': 5,
            'dm_notify': True, 'auto_clean': True
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
    return ''.join(font_map.get(c,c) for c in str(text))

def detect_pair(text):
    text_upper = text.upper().replace('/','')
    for pair_code, cfg in PAIRS.items():
        for alias in cfg['aliases']:
            if alias.upper().replace('/','') in text_upper:
                return pair_code
    return None

def parse_signals(text):
    signals = []
    lines = text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line: continue
        clean = line.replace('🧪','').replace('🦅','').replace('🐻','').replace('🦁','').strip()
        match = re.search(r'([A-Za-z0-9-]+(?:-OTC)?)\s*☞\s*(\d{1,2}:\d{2})\s*(CALL|PUT)', clean, re.IGNORECASE)
        if not match: match = re.search(r'([A-Za-z0-9-]+(?:-OTC)?)\s+(\d{1,2}:\d{2})\s+(CALL|PUT)', clean, re.IGNORECASE)
        if match: signals.append({'asset':match.group(1).strip(),'time':match.group(2).strip(),'direction':match.group(3).upper()})
    return signals

def is_duplicate(signals, new_sig):
    for sig in signals:
        if sig['asset'] == new_sig['asset'] and sig['time'] == new_sig['time'] and sig['direction'] == new_sig['direction']:
            return True
    return False

def convert_time(time_str):
    try:
        h,m = map(int,time_str.split(':')); total = h*60+m-30
        if total<0: total+=1440
        return f"{(total//60)%24:02d}:{total%60:02d}"
    except: return time_str

def get_conf(): return random.randint(82,98)

# ==================== KEYBOARDS ====================
def main_menu(uid=None):
    global paused_all
    pause_btn = "▶️ Resume All" if paused_all else "⏸️ Pause All"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Load Signals", callback_data="load")],
        [InlineKeyboardButton("📊 Scheduled", callback_data="signals"), InlineKeyboardButton("📈 Stats", callback_data="stats")],
        [InlineKeyboardButton("📋 History", callback_data="history"), InlineKeyboardButton("📝 Pending", callback_data="pending")],
        [InlineKeyboardButton("📢 Channels", callback_data="channels"), InlineKeyboardButton("📅 Daily", callback_data="daily")],
        [InlineKeyboardButton("🔄 Reset", callback_data="reset"), InlineKeyboardButton("🗑️ Clear", callback_data="clear")],
        [InlineKeyboardButton(pause_btn, callback_data="pause_all"), InlineKeyboardButton("📢 Change Ch", callback_data="change_ch")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings")]
    ])

def pair_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇧🇷 USDBRL", callback_data="pair_BRL"),
         InlineKeyboardButton("🇨🇴 USDCOP", callback_data="pair_COP")],
        [InlineKeyboardButton("🇪🇬 USDEGP", callback_data="pair_EGP")],
        [InlineKeyboardButton("📢 Change Channel", callback_data="change_ch")],
        [InlineKeyboardButton("🔙 Back", callback_data="start")]
    ])

def change_ch_menu(uid):
    ud = get_ud(uid)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🇧🇷 BRL: {ud['pair_channels'].get('BRL','Not set')}", callback_data="chpair_BRL")],
        [InlineKeyboardButton(f"🇨🇴 COP: {ud['pair_channels'].get('COP','Not set')}", callback_data="chpair_COP")],
        [InlineKeyboardButton(f"🇪🇬 EGP: {ud['pair_channels'].get('EGP','Not set')}", callback_data="chpair_EGP")],
        [InlineKeyboardButton("🔙 Back", callback_data="start")]
    ])

def settings_menu(uid):
    ud = get_ud(uid)
    pt = "30s" if ud['post_time']==30 else "1min" if ud['post_time']==60 else "2min"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⏱️ Post Before: {pt}", callback_data="set_post")],
        [InlineKeyboardButton(f"⏰ Expiry: {ud['expiry_minutes']}min", callback_data="set_expiry")],
        [InlineKeyboardButton(f"📩 DM Notify: {'ON' if ud['dm_notify'] else 'OFF'}", callback_data="toggle_dm")],
        [InlineKeyboardButton(f"🧹 Auto-Clean: {'ON' if ud['auto_clean'] else 'OFF'}", callback_data="toggle_clean")],
        [InlineKeyboardButton("🔙 Back", callback_data="start")]
    ])

def res_kb(sid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ WIN", callback_data=f"w_{sid}"), InlineKeyboardButton("❌ LOSS", callback_data=f"l_{sid}")],
        [InlineKeyboardButton("🔄 MTG1 WIN", callback_data=f"mw_{sid}"), InlineKeyboardButton("⚠️ AVOID", callback_data=f"a_{sid}")]
    ])

def preview_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ POST", callback_data="confirm_post"), InlineKeyboardButton("❌ CANCEL", callback_data="cancel_post")],
        [InlineKeyboardButton("✏️ EDIT TIME", callback_data="edit_time")]
    ])

def confirm_kb(action):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ YES", callback_data=f"confirm_{action}"), InlineKeyboardButton("❌ NO", callback_data="start")]
    ])

def countdown_kb(user_id):
    ud = get_ud(user_id)
    if ud['countdown_active']:
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔴 OFF TIMER", callback_data="timer_off")]])
    else:
        return InlineKeyboardMarkup([[InlineKeyboardButton("🟢 ON TIMER", callback_data="timer_on")]])

# ==================== FORMATTERS ====================
def fmt_signal(sig, sid, ch, pair_code):
    a = sig['asset']; t = sig['converted_time']; d = sig['direction']
    flag = PAIRS.get(pair_code, {}).get('flag', '')
    if d == 'CALL': de = "🟢"; di = "📈"; dl = "CALL / BUY"
    else: de = "🔴"; di = "📉"; dl = "PUT / SELL"
    snum = signal_counters.get(pair_code, 0)
    return f"""╔══════════════════════════════════╗
║     🎯 TRADING SIGNAL     ║
╚══════════════════════════════════╝

💸 SIGNAL NO : {snum}

{flag} 💎 ASSET
   └─ {to_font(a)}

⏰ TRADE TIME (UTC+5:30)
   └─ {to_font(t)}

📊 DIRECTION
   └─ {de} {dl} {di}

🔄 MTG1

╔══════════════════════════════════╗
║  ⚡ PREMIUM SIGNAL • ACTIVE ⚡  ║
║  📱 {ch}              ║
╚══════════════════════════════════╝"""

def fmt_next_box():
    return """╔══════════════════════════════════╗
║        ⏭️ NEXT SIGNAL        ║
╚══════════════════════════════════╝

⏳ TIME REMAINING"""

def glitch_text(text):
    style = random.randint(1,4)
    if style==1: return text
    elif style==2:
        r=""
        for c in text:
            if c in "0123456789:": r+=c+"\u0337"
            else: r+=c
        return r
    elif style==3:
        r=""
        for c in text:
            if c in "0123456789:": r+=c+"\u0334"
            else: r+=c
        return r
    else:
        zalgo="\u0337\u033E\u0323\u0328"
        r=""
        for c in text:
            if c in "0123456789:": r+=c+random.choice(zalgo)+random.choice(zalgo)
            else: r+=c
        return r

def fmt_countdown_line(minutes, seconds, last_10=False):
    text = f"{minutes:02d}:{seconds:02d}"
    if last_10: return f"   └─ {glitch_text(text)}"
    elif seconds%random.randint(3,5)==0: return f"   └─ {glitch_text(text)}"
    else: return f"   └─ {text}"

def fmt_result(sig, result, sid, ch):
    a = sig['asset']; t = sig['converted_time']; d = sig['direction']
    pair = a.replace('-OTC','')
    if result=='WIN': ri="✅"; rt="WINNER 🏆"
    elif result=='LOSS': ri="❌"; rt="LOSS"
    elif result=='MTG1_WIN': ri="🔄"; rt="MTG1 WIN 🏆"
    else: ri="⚠️"; rt="AVOID"
    streak = tracker.get_streak_text()
    extra = f"\n{streak}" if streak else ""
    return f"""╔══════════════════════════════════╗
║     📊 SIGNAL RESULT      ║
╚══════════════════════════════════╝

{ri} {rt}

💎 {to_font(pair)}
⏰ {t}
📊 {'🟢' if d=='CALL' else '🔴'} {d}

📈 W:{tracker.stats.get('wins',0)} L:{tracker.stats.get('losses',0)} | WR:{tracker.get_rate():.1f}%{extra}

╔══════════════════════════════════╗
║  📱 {ch}              ║
╚══════════════════════════════════╝"""

# ==================== CALLBACK HANDLER ====================
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; d = q.data; uid = q.from_user.id
    await q.answer()
    ud = get_ud(uid)
    global paused_all
    
    # Timer toggle
    if d == 'timer_off': ud['countdown_active'] = False; await q.edit_message_reply_markup(reply_markup=countdown_kb(uid)); return
    if d == 'timer_on': ud['countdown_active'] = True; await q.edit_message_reply_markup(reply_markup=countdown_kb(uid)); return
    
    # Pause/Resume All
    if d == 'pause_all':
        paused_all = not paused_all
        if paused_all:
            for t in list(ud['active_tasks'].values()):
                if not t.done(): t.cancel()
            ud['active_tasks'].clear()
        await q.edit_message_text(f"{'⏸️ PAUSED' if paused_all else '▶️ RESUMED'} all signals!", reply_markup=main_menu())
        return
    
    # Confirm dialogs
    if d == 'clear': await q.edit_message_text("⚠️ Delete ALL signals?", reply_markup=confirm_kb('clear')); return
    if d == 'confirm_clear':
        for t in list(ud['active_tasks'].values()):
            if not t.done(): t.cancel()
        ud['active_tasks'].clear();ud['scheduled_signals'].clear();ud['pending_results'].clear()
        await q.edit_message_text("✅ All cleared!", reply_markup=main_menu()); return
    if d == 'reset': await q.edit_message_text("⚠️ Reset ALL stats?", reply_markup=confirm_kb('reset')); return
    if d == 'confirm_reset':
        tracker.reset_stats();signal_counters.update({"BRL":0,"COP":0,"EGP":0})
        await q.edit_message_text("✅ Stats reset!", reply_markup=main_menu()); return
    
    # Settings
    if d == 'settings': await q.edit_message_text("⚙️ Settings:", reply_markup=settings_menu(uid)); return
    if d == 'set_post':
        times = [30, 60, 120]
        current = ud['post_time']
        next_idx = (times.index(current) + 1) % len(times)
        ud['post_time'] = times[next_idx]
        pt = "30s" if ud['post_time']==30 else "1min" if ud['post_time']==60 else "2min"
        await q.edit_message_text(f"✅ Post before: {pt}", reply_markup=settings_menu(uid)); return
    if d == 'set_expiry':
        ud['expiry_minutes'] = ud['expiry_minutes'] + 5 if ud['expiry_minutes'] < 30 else 5
        await q.edit_message_text(f"✅ Expiry: {ud['expiry_minutes']}min", reply_markup=settings_menu(uid)); return
    if d == 'toggle_dm': ud['dm_notify'] = not ud['dm_notify']; await q.edit_message_text(f"✅ DM Notify: {'ON' if ud['dm_notify'] else 'OFF'}", reply_markup=settings_menu(uid)); return
    if d == 'toggle_clean': ud['auto_clean'] = not ud['auto_clean']; await q.edit_message_text(f"✅ Auto-Clean: {'ON' if ud['auto_clean'] else 'OFF'}", reply_markup=settings_menu(uid)); return
    
    # Result buttons
    if d.startswith('w_') or d.startswith('l_') or d.startswith('mw_') or d.startswith('a_'):
        if d.startswith('mw_'): sid=d[3:]; result='MTG1_WIN'
        elif d.startswith('w_'): sid=d[2:]; result='WIN'
        elif d.startswith('l_'): sid=d[2:]; result='LOSS'
        else: sid=d[2:]; result='AVOID'
        if sid in processed_results: await q.edit_message_text("⚠️ Already recorded!"); return
        if sid not in ud['pending_results']: await q.edit_message_text("⚠️ Not found"); return
        info = ud['pending_results'][sid]; sd = info['signal']
        tracker.add_result(sd, result, sid)
        ch = info.get('channel', '@botsignal007')
        try: await context.bot.send_message(chat_id=ch, text=fmt_result(sd, result, sid, ch))
        except: pass
        emap={'WIN':'✅ WIN','LOSS':'❌ LOSS','MTG1_WIN':'🔄 MTG1 WIN','AVOID':'⚠️ AVOID'}
        sh=sid[-4:] if len(sid)>=4 else sid
        await q.edit_message_text(f"{emap[result]} #{sh}\n📊 {sd['asset']}\n⏰ {sd['converted_time']}\n📈 WR:{tracker.get_rate():.1f}%")
        if sid in ud['pending_results']: del ud['pending_results'][sid]
        return
    
    # Pair selection
    if d.startswith('pair_'):
        pair = d[5:]
        ud['selected_pair'] = pair
        ch = ud['pair_channels'].get(pair)
        if ch:
            await q.edit_message_text(f"✅ {PAIRS[pair]['flag']} {PAIRS[pair]['name']}\n📢 Channel: {ch}\n📝 Paste signals now...", reply_markup=main_menu())
        else:
            context.user_data['waiting_for_channel'] = True
            context.user_data['pair'] = pair
            await q.edit_message_text(f"📢 Send channel for {PAIRS[pair]['flag']} {PAIRS[pair]['name']}:\nExample: @your_channel")
        return
    
    # Change channel
    if d == 'change_ch': await q.edit_message_text("📢 Select pair to change:", reply_markup=change_ch_menu(uid)); return
    if d.startswith('chpair_'):
        pair = d[7:]
        context.user_data['waiting_for_channel'] = True
        context.user_data['pair'] = pair
        await q.edit_message_text(f"📢 Send NEW channel for {PAIRS[pair]['flag']} {PAIRS[pair]['name']}:")
        return
    
    # Menu
    if d == "start":
        best, worst = tracker.get_best_pair()
        best_text = f"🏆 Best: {best[0]} ({best[1]['w']}W/{best[1]['l']}L)" if best else ""
        worst_text = f"💀 Worst: {worst[0]} ({worst[1]['w']}W/{worst[1]['l']}L)" if worst else ""
        txt = f"""🤖 SIGNAL BOT v31 ULTIMATE

👤 {uid}
📊 Active: {len(ud['scheduled_signals'])} | Pending: {len(ud['pending_results'])}
📈 W:{tracker.stats.get('wins',0)} L:{tracker.stats.get('losses',0)} M:{tracker.stats.get('mtg_wins',0)} A:{tracker.stats.get('avoids',0)} | WR:{tracker.get_rate():.1f}%
{tracker.get_streak_text()}
{best_text} {worst_text}

📢 Channels:
🇧🇷 BRL: {ud['pair_channels'].get('BRL','Not set')}
🇨🇴 COP: {ud['pair_channels'].get('COP','Not set')}
🇪🇬 EGP: {ud['pair_channels'].get('EGP','Not set')}

👇 Select:"""
        await q.edit_message_text(txt, reply_markup=main_menu())
        return
    
    if d == "load": await q.edit_message_text("📊 Select Pair:", reply_markup=pair_menu()); return
    if d == "signals":
        if not ud['scheduled_signals']: await q.edit_message_text("📋 None", reply_markup=main_menu()); return
        ss = sorted(ud['scheduled_signals'].items(), key=lambda x: x[1]['scheduled_time'])
        now = datetime.utcnow() + timedelta(hours=5, minutes=30)
        txt = f"📊 SCHEDULED ({len(ss)})\n\n"
        for i,(sid,sd) in enumerate(ss[:10],1):
            sig=sd['signal'];df=sd['scheduled_time']-now
            if df.total_seconds()>0:
                m=int(df.total_seconds()//60)
                lf=f"{m//60}h{m%60}m" if m>=60 else f"{m}m"
            else:lf="Now"
            em="🟢" if sig['direction']=='CALL' else "🔴";sh=sid[-4:] if len(sid)>=4 else sid
            p=sd.get('pair','')
            txt+=f"{i}. {PAIRS.get(p,{}).get('flag','')} #{sh} ⏰ {sig['converted_time']} | {em} | ⏳{lf}\n"
        if len(ss)>10: txt+=f"\n...{len(ss)-10} more"
        await q.edit_message_text(txt, reply_markup=main_menu())
        return
    if d == "stats":
        best, worst = tracker.get_best_pair()
        best_text = f"🏆 Best: {best[0]} ({best[1]['w']}W/{best[1]['l']}L)" if best else ""
        worst_text = f"💀 Worst: {worst[0]} ({worst[1]['w']}W/{worst[1]['l']}L)" if worst else ""
        txt=f"📊 STATS\n\nW:{tracker.stats.get('wins',0)} L:{tracker.stats.get('losses',0)} M:{tracker.stats.get('mtg_wins',0)} A:{tracker.stats.get('avoids',0)} E:{tracker.stats.get('expired',0)}\nWR:{tracker.get_rate():.1f}%\n{best_text}\n{worst_text}\n{tracker.get_streak_text()}"
        await q.edit_message_text(txt,reply_markup=main_menu());return
    if d == "history":
        hist = tracker.get_history_text(30); mood = tracker.get_mood_message()
        ch = ud['pair_channels'].get('BRL') or ud['pair_channels'].get('COP') or ud['pair_channels'].get('EGP')
        if ch:
            try: await context.bot.send_message(chat_id=ch, text=f"```\n{hist}\n```", parse_mode=ParseMode.MARKDOWN)
            except: await context.bot.send_message(chat_id=ch, text=hist)
            if mood:
                try: await context.bot.send_message(chat_id=ch, text=mood)
                except: pass
            await q.edit_message_text(f"✅ Posted to {ch}", reply_markup=main_menu())
        else:
            await q.edit_message_text("❌ No channel set!", reply_markup=main_menu())
        return
    if d == "daily":
        report = tracker.get_daily_report(); mood = tracker.get_mood_message()
        await q.edit_message_text(f"{report}\n\n{mood}", reply_markup=main_menu()); return
    if d == "pending":
        if not ud['pending_results']: await q.edit_message_text("📋 None",reply_markup=main_menu());return
        for sid,info in list(ud['pending_results'].items())[:1]:
            sig=info['signal'];em="🟢" if sig['direction']=='CALL' else "🔴";sh=sid[-4:] if len(sid)>=4 else sid
            await q.edit_message_text(f"📊 #{sh}\n💎 {sig['asset']}\n⏰ {sig['converted_time']}\n📈 {em} {sig['direction']}\n\nRecord:",reply_markup=res_kb(sid))
        for sid,info in list(ud['pending_results'].items())[1:6]:
            sig=info['signal'];em="🟢" if sig['direction']=='CALL' else "🔴";sh=sid[-4:] if len(sid)>=4 else sid
            await q.message.reply_text(f"📊 #{sh}\n💎 {sig['asset']}\n⏰ {sig['converted_time']}\n📈 {em} {sig['direction']}\n\nRecord:",reply_markup=res_kb(sid))
        return
    if d == "channels":
        txt="📢 PAIR CHANNELS\n\n"
        for p,cfg in PAIRS.items():
            ch=ud['pair_channels'].get(p,'Not set')
            txt+=f"{cfg['flag']} {cfg['name']}: {ch}\n"
        await q.edit_message_text(txt,reply_markup=main_menu());return

# ==================== MESSAGE HANDLER ====================
async def msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; ud = get_ud(uid)
    text = update.message.text.strip()
    
    if context.user_data.get('waiting_for_channel'):
        if not text.startswith('@'): text = '@' + text
        pair = context.user_data.get('pair', 'BRL')
        ud['pair_channels'][pair] = text
        ud['selected_pair'] = pair
        context.user_data['waiting_for_channel'] = False
        await update.message.reply_text(f"✅ {PAIRS[pair]['flag']} {PAIRS[pair]['name']} → {text}\n📝 Paste signals now...", reply_markup=main_menu())
        return
    
    if 'OTC' in text.upper() or '☞' in text:
        parsed = parse_signals(text)
        if not parsed: await update.message.reply_text("❌ No valid signals!"); return
        
        pair = ud.get('selected_pair') or detect_pair(text)
        if not pair: await update.message.reply_text("❌ Could not detect pair! Select pair first."); return
        
        ud['selected_pair'] = pair
        ch = ud['pair_channels'].get(pair)
        if not ch: await update.message.reply_text(f"❌ No channel set for {pair}!"); return
        
        parsed.sort(key=lambda x: x['time'])
        ok = 0; skipped = 0
        signal_counters[pair] = signal_counters.get(pair, 0) + len(parsed)
        
        for sig in parsed:
            if is_duplicate([s['signal'] for s in ud['scheduled_signals'].values()], sig):
                skipped += 1; continue
            
            ct = convert_time(sig['time']); cf = get_conf()
            sd = {'asset':sig['asset'],'time':sig['time'],'original_time':sig['time'],'converted_time':ct,'direction':sig['direction'],'confidence':cf,'pair':pair}
            o,sid = await sched_signal(context.bot, uid, sd, ch, pair, ud['post_time'])
            if o: ok += 1
        
        msg_text = f"✅ {ok} signals scheduled!\n{PAIRS[pair]['flag']} {PAIRS[pair]['name']}\n📢 {ch}\n⏰ UTC+5:30"
        if skipped: msg_text += f"\n⚠️ {skipped} duplicates skipped!"
        
        await update.message.reply_text(msg_text, reply_markup=main_menu())
        return
    
    txt = f"""🤖 SIGNAL BOT v31 ULTIMATE

👤 {uid}
📊 Active: {len(ud['scheduled_signals'])} | Pending: {len(ud['pending_results'])}
📈 W:{tracker.stats.get('wins',0)} L:{tracker.stats.get('losses',0)} | WR:{tracker.get_rate():.1f}%
{tracker.get_streak_text()}

📢 Channels:
🇧🇷 BRL: {ud['pair_channels'].get('BRL','Not set')}
🇨🇴 COP: {ud['pair_channels'].get('COP','Not set')}
🇪🇬 EGP: {ud['pair_channels'].get('EGP','Not set')}

👇 Select:"""
    await update.message.reply_text(txt, reply_markup=main_menu())

# ==================== SCHEDULING ====================
async def sched_signal(bot, uid, sd, ch, pair, post_before=60):
    ud = get_ud(uid)
    global paused_all
    if paused_all: return False, None
    try:
        h,m = map(int,sd['converted_time'].split(':'))
        now = datetime.utcnow() + timedelta(hours=5, minutes=30)
        tgt = now.replace(hour=h,minute=m,second=0,microsecond=0)
        pt = tgt - timedelta(seconds=post_before)
        if pt <= now: pt += timedelta(days=1)
        delay = (pt-now).total_seconds()
        if delay < 0: return False, None
        sid = f"{sd['asset']}_{sd['converted_time']}_{random.randint(10000,99999)}"
        ud['scheduled_signals'][sid] = {'signal':sd,'scheduled_time':pt,'channel':ch,'pair':pair}
        task = asyncio.create_task(post_signal(bot,uid,sid,sd,delay,ch,pair))
        ud['active_tasks'][sid] = task
        return True, sid
    except: return False, None

async def post_signal(bot, uid, sid, sd, delay, ch, pair):
    ud = get_ud(uid)
    try:
        await asyncio.sleep(delay)
        if sid not in ud['scheduled_signals']: return
        
        if ud['dm_notify']:
            await bot.send_message(chat_id=uid, text=f"⚠️ SIGNAL POSTING!\n{PAIRS[pair]['flag']} {sd['asset']}\n⏰ {sd['converted_time']}")
        
        next_sig = None
        sorted_sigs = sorted(ud['scheduled_signals'].items(), key=lambda x: x[1]['scheduled_time'])
        now = datetime.utcnow() + timedelta(hours=5, minutes=30)
        for nsid,nsdata in sorted_sigs:
            if nsid!=sid and nsdata['scheduled_time']>now and nsdata.get('channel')==ch:
                next_sig=nsdata['signal']; break
        
        for attempt in range(3):
            try:
                await bot.send_message(chat_id=ch, text=fmt_signal(sd,sid,ch,pair))
                break
            except: await asyncio.sleep(2)
        
        if next_sig and ud['countdown_active']:
            next_time=next_sig['converted_time']
            nh,nm=map(int,next_time.split(':'))
            next_dt=now.replace(hour=nh,minute=nm,second=0,microsecond=0)
            if next_dt<=now: next_dt+=timedelta(days=1)
            total_seconds=int((next_dt-now).total_seconds())
            if total_seconds>0:
                mins=total_seconds//60;secs=total_seconds%60
                next_msg=await bot.send_message(chat_id=ch,text=f"{fmt_next_box()}\n{fmt_countdown_line(mins,secs)}")
                asyncio.create_task(run_countdown(bot,ch,next_msg.message_id,total_seconds,uid))
        
        ud['pending_results'][sid]={'signal':sd,'channel':ch}
        em="🟢" if sd['direction']=='CALL' else "🔴";sh=sid[-4:] if len(sid)>=4 else sid
        await bot.send_message(chat_id=uid,text=f"✅ #{sh}\n📊 {sd['asset']}\n⏰ {sd['converted_time']}\n📈 {em} {sd['direction']}\n📢 {ch}\n\nRecord:",reply_markup=res_kb(sid))
        
        if ud['auto_clean']:
            asyncio.create_task(auto_expire(bot, uid, sid, ud['expiry_minutes'] * 60))
        
        if sid in ud['scheduled_signals']: del ud['scheduled_signals'][sid]
        if sid in ud['active_tasks']: del ud['active_tasks'][sid]
    except asyncio.CancelledError:
        if sid in ud['scheduled_signals']: del ud['scheduled_signals'][sid]
    except Exception as e:
        logger.error(f"Post error: {e}")

async def auto_expire(bot, uid, sid, delay):
    await asyncio.sleep(delay)
    ud = get_ud(uid)
    if sid in ud['pending_results']:
        info = ud['pending_results'][sid]
        tracker.add_result(info['signal'], 'EXPIRED', sid)
        del ud['pending_results'][sid]

async def run_countdown(bot, ch, msg_id, total_seconds, uid):
    ud = get_ud(uid)
    for remaining in range(total_seconds,-1,-1):
        if not ud['countdown_active']:
            try: await bot.edit_message_text(chat_id=ch,message_id=msg_id,text=f"{fmt_next_box()}\n⏳ OFF")
            except: pass
            return
        mins=remaining//60;secs=remaining%60;last_10=remaining<=10
        try:
            await bot.edit_message_text(chat_id=ch,message_id=msg_id,text=f"{fmt_next_box()}\n{fmt_countdown_line(mins,secs,last_10)}")
        except: break
        await asyncio.sleep(1)

async def err(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")

# ==================== MAIN ====================
def main():
    tracker.load()
    print(f"""
╔══════════════════════════════════╗
║  🤖 SIGNAL BOT v31 ULTIMATE ║
║  25+ LOGIC ADDED          ║
╚══════════════════════════════════╝
✅ Ready!
""")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg))
    app.add_handler(CommandHandler("start", msg))
    app.add_error_handler(err)
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == '__main__':
    main()

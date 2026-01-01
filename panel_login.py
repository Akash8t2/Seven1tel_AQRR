# -*- coding: utf-8 -*-

import os
import requests
import re
import datetime
import time
import telebot
from telebot import types
from bs4 import BeautifulSoup
from keep_alive import keep_alive

# ==========================================
# 🔥 CONFIGURATION
# ==========================================

# PANEL CONFIGURATION
BASE_IP = "94.23.120.156"
LOGIN_PAGE_URL = f"http://{BASE_IP}/ints/login"
LOGIN_POST_URL = f"http://{BASE_IP}/ints/signin"
API_URL = f"http://{BASE_IP}/ints/client/res/data_smscdr.php"
REFERER_URL = f"http://{BASE_IP}/ints/client/SMSCDRReports"

PANEL_USERNAME = os.environ.get("PANEL_USERNAME")
PANEL_PASSWORD = os.environ.get("PANEL_PASSWORD")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

GROUP_IDS_WITH_DOTS = [-1003405109562, -1003140739791]  # Groups that receive numbers with ••
GROUP_IDS_WITHOUT_DOTS = []  # Groups that receive full numbers (no ••)
PANEL_URL = "https://t.me/Aktrybot"
ALL_NUMBERS_URL = "https://t.me/+FzMuku4rLO1mYmY1"

# Initialize bot for callback handling
bot = telebot.TeleBot(BOT_TOKEN)

# Remove any existing webhook
try:
    bot.remove_webhook()
except:
    pass

# Callback handler for OTP copy button
@bot.callback_query_handler(func=lambda call: call.data.startswith('otp_'))
def handle_copy_callback(call):
    try:
        otp = call.data.replace('otp_', '')
        # Send OTP as separate message for easy copying
        bot.send_message(call.message.chat.id, f"`{otp}`", parse_mode='Markdown', reply_to_message_id=call.message.message_id)
        bot.answer_callback_query(call.id, text="✓ Copied!")
    except Exception as e:
        print(f"[!] Callback error: {e}")

# ==========================================
# 🔥 MAIN CLASS
# ==========================================
class PanelToGroupForwarder:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest'
        })
        self.logged_in = False
        self.sent_messages = set()  # Track sent messages to avoid duplicates
        self.first_run = True  # Flag to skip old messages on first run

    def solve_captcha(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text()
        match = re.search(r'What is\s*(-?\d+)\s*([\+\-\*xX\/])\s*(-?\d+)', text, re.IGNORECASE)
        if match:
            a, op, b = int(match.group(1)), match.group(2), int(match.group(3))
            result = 0
            if op == '+': result = a + b
            elif op == '-': result = a - b
            elif op in ['*', 'x', 'X']: result = a * b
            elif op == '/' and b != 0: result = a // b
            print(f"[CAPTCHA] Solved: {a} {op} {b} = {result}")
            return result
        return None

    def login(self):
        print("------------------------------------------------")
        print(f"[*] [{datetime.datetime.now().strftime('%H:%M:%S')}] Logging in...")
        try:
            resp = self.session.get(LOGIN_PAGE_URL, timeout=10)
            ans = self.solve_captcha(resp.text)
            if ans is None:
                print("[!] Failed to solve captcha.")
                return False
            
            payload = {'username': PANEL_USERNAME, 'password': PANEL_PASSWORD, 'capt': ans}
            soup = BeautifulSoup(resp.text, 'html.parser')
            for inp in soup.find_all('input', type='hidden'):
                name = inp.get('name')  # type: ignore
                if name and isinstance(name, str):
                    payload[name] = inp.get('value', '')  # type: ignore
            
            post_resp = self.session.post(LOGIN_POST_URL, data=payload, timeout=10)
            if post_resp.status_code in [200, 302] and ("Dashboard" in post_resp.text or "Logout" in post_resp.text):
                self.logged_in = True
                print("[SUCCESS] Login successful!")
                return True
            
            print("[FAIL] Login failed.")
            return False
        except Exception as e:
            print(f"[ERROR] {e}")
            return False

    def fetch_all_messages_and_forward(self):
        if not self.login():
            return
        
        try:
            today = datetime.datetime.now()
            yesterday = today - datetime.timedelta(days=1)
            
            params = {
                'fdate1': f"{yesterday.strftime('%Y-%m-%d')} 00:00:00",
                'fdate2': f"{today.strftime('%Y-%m-%d')} 23:59:59",
                'iDisplayLength': '100',
                'sSortDir_0': 'desc', 
            }
            
            resp = self.session.get(API_URL, params=params, headers={'Referer': REFERER_URL}, timeout=15)
            data = resp.json()
            
            if data and 'aaData' in data:
                print(f"[*] Found {len(data['aaData'])} messages")
                
                # On first run, mark all existing messages as sent without forwarding (except latest 5)
                if self.first_run:
                    print("[*] First run - marking existing messages as seen (keeping latest 5)...")
                    messages_to_mark = data['aaData'][5:] if len(data['aaData']) > 5 else []
                    for sms_data in messages_to_mark:
                        if str(sms_data[2]) == "0" or not str(sms_data[2]).isdigit() or len(str(sms_data[2])) < 8:
                            continue
                        number = str(sms_data[2])
                        sms_text = str(sms_data[4])
                        if sms_text and sms_text.strip():
                            message_id = f"{number}:{sms_text[:50]}"
                            self.sent_messages.add(message_id)
                    self.first_run = False
                    print(f"[✓] Marked {len(self.sent_messages)} old messages as seen, will send latest {min(5, len(data['aaData']))} messages")
                    # Continue to process the latest 5 messages
                
                for sms_data in data['aaData']:
                    if str(sms_data[2]) == "0" or not str(sms_data[2]).isdigit() or len(str(sms_data[2])) < 8:
                        continue
                    
                    number = str(sms_data[2])
                    service = str(sms_data[3])
                    sms_text = str(sms_data[4])
                    
                    # Skip empty messages
                    if not sms_text or sms_text.strip() == "":
                        continue
                    
                    # Create unique message ID to track duplicates
                    message_id = f"{number}:{sms_text[:50]}"  # Use number + first 50 chars of SMS
                    
                    # Skip if already sent
                    if message_id in self.sent_messages:
                        continue
                    
                    otp_match = re.search(r'\b\d{4,8}\b', sms_text) or re.search(r'\b\d{3}[-\s]\d{3}\b', sms_text)
                    otp = otp_match.group(0) if otp_match else "N/A"
                    
                    # Send to groups WITH dots
                    for group_id in GROUP_IDS_WITH_DOTS:
                        try:
                            message, keyboard = self.format_message_with_buttons(service, number, otp, sms_text, use_dots=True)
                            bot.send_message(group_id, message, parse_mode='Markdown', reply_markup=keyboard)
                            print(f"[✓] Sent to {group_id}: {number} - {service} (with ••)")
                            time.sleep(1)
                        except Exception as e:
                            if "429" in str(e) and "retry after" in str(e):
                                retry_match = re.search(r'retry after (\d+)', str(e))
                                if retry_match:
                                    retry_time = int(retry_match.group(1))
                                    print(f"[⏳] Rate limited, waiting {retry_time}s...")
                                    time.sleep(retry_time + 1)
                                    try:
                                        bot.send_message(group_id, message, parse_mode='Markdown', reply_markup=keyboard)
                                        print(f"[✓] Sent to {group_id}: {number} - {service} (with ••)")
                                    except:
                                        pass
                            else:
                                print(f"[!] Failed to send to {group_id}: {e}")
                    
                    # Send to groups WITHOUT dots
                    if GROUP_IDS_WITHOUT_DOTS:
                        for group_id in GROUP_IDS_WITHOUT_DOTS:
                            try:
                                message, keyboard = self.format_message_with_buttons(service, number, otp, sms_text, use_dots=False)
                                bot.send_message(group_id, message, parse_mode='Markdown', reply_markup=keyboard)
                                print(f"[✓] Sent to {group_id}: {number} - {service} (full number)")
                                time.sleep(1)
                            except Exception as e:
                                if "429" in str(e) and "retry after" in str(e):
                                    retry_match = re.search(r'retry after (\d+)', str(e))
                                    if retry_match:
                                        retry_time = int(retry_match.group(1))
                                        print(f"[⏳] Rate limited, waiting {retry_time}s...")
                                        time.sleep(retry_time + 1)
                                        try:
                                            bot.send_message(group_id, message, parse_mode='Markdown', reply_markup=keyboard)
                                            print(f"[✓] Sent to {group_id}: {number} - {service} (full number)")
                                        except:
                                            pass
                                else:
                                    print(f"[!] Failed to send to {group_id}: {e}")
                    
                    # Mark as sent
                    self.sent_messages.add(message_id)
        except Exception as e:
            print(f"[!] Error: {e}")

    def get_country_info(self, number):
        clean_number = number.replace('+', '').replace(' ', '').strip()
        country_map = {
    '93': ('🇦🇫', 'AF'), '355': ('🇦🇱', 'AL'), '213': ('🇩🇿', 'DZ'), '1684': ('🇦🇸', 'AS'),
    '376': ('🇦🇩', 'AD'), '244': ('🇦🇴', 'AO'), '1264': ('🇦🇮', 'AI'), '672': ('🇦🇶', 'AQ'),
    '1268': ('🇦🇬', 'AG'), '54': ('🇦🇷', 'AR'), '374': ('🇦🇲', 'AM'), '297': ('🇦🇼', 'AW'),
    '61': ('🇦🇺', 'AU'), '43': ('🇦🇹', 'AT'), '994': ('🇦🇿', 'AZ'), '1242': ('🇧🇸', 'BS'),
    '973': ('🇧🇭', 'BH'), '880': ('🇧🇩', 'BD'), '1246': ('🇧🇧', 'BB'), '375': ('🇧🇾', 'BY'),
    '32': ('🇧🇪', 'BE'), '501': ('🇧🇿', 'BZ'), '229': ('🇧🇯', 'BJ'), '1441': ('🇧🇲', 'BM'),
    '975': ('🇧🇹', 'BT'), '591': ('🇧🇴', 'BO'), '387': ('🇧🇦', 'BA'), '267': ('🇧🇼', 'BW'),
    '55': ('🇧🇷', 'BR'), '246': ('🇮🇴', 'IO'), '1284': ('🇻🇬', 'VG'), '673': ('🇧🇳', 'BN'),
    '359': ('🇧🇬', 'BG'), '226': ('🇧🇫', 'BF'), '257': ('🇧🇮', 'BI'), '855': ('🇰🇭', 'KH'),
    '237': ('🇨🇲', 'CM'), '1': ('🇨🇦', 'CA'), '238': ('🇨🇻', 'CV'), '599': ('🇧🇶', 'BQ'),
    '1345': ('🇰🇾', 'KY'), '236': ('🇨🇫', 'CF'), '235': ('🇹🇩', 'TD'), '56': ('🇨🇱', 'CL'),
    '86': ('🇨🇳', 'CN'), '61': ('🇨🇽', 'CX'), '61': ('🇨🇨', 'CC'), '57': ('🇨🇴', 'CO'),
    '269': ('🇰🇲', 'KM'), '243': ('🇨🇩', 'CD'), '242': ('🇨🇬', 'CG'), '682': ('🇨🇰', 'CK'),
    '506': ('🇨🇷', 'CR'), '385': ('🇭🇷', 'HR'), '53': ('🇨🇺', 'CU'), '599': ('🇨🇼', 'CW'),
    '357': ('🇨🇾', 'CY'), '420': ('🇨🇿', 'CZ'), '45': ('🇩🇰', 'DK'), '253': ('🇩🇯', 'DJ'),
    '1767': ('🇩🇲', 'DM'), '1809': ('🇩🇴', 'DO'), '593': ('🇪🇨', 'EC'), '20': ('🇪🇬', 'EG'),
    '503': ('🇸🇻', 'SV'), '240': ('🇬🇶', 'GQ'), '291': ('🇪🇷', 'ER'), '372': ('🇪🇪', 'EE'),
    '251': ('🇪🇹', 'ET'), '500': ('🇫🇰', 'FK'), '298': ('🇫🇴', 'FO'), '679': ('🇫🇯', 'FJ'),
    '358': ('🇫🇮', 'FI'), '33': ('🇫🇷', 'FR'), '594': ('🇬🇫', 'GF'), '689': ('🇵🇫', 'PF'),
    '241': ('🇬🇦', 'GA'), '220': ('🇬🇲', 'GM'), '995': ('🇬🇪', 'GE'), '49': ('🇩🇪', 'DE'),
    '233': ('🇬🇭', 'GH'), '350': ('🇬🇮', 'GI'), '30': ('🇬🇷', 'GR'), '299': ('🇬🇱', 'GL'),
    '1473': ('🇬🇩', 'GD'), '590': ('🇬🇵', 'GP'), '1671': ('🇬🇺', 'GU'), '502': ('🇬🇹', 'GT'),
    '44': ('🇬🇬', 'GG'), '224': ('🇬🇳', 'GN'), '245': ('🇬🇼', 'GW'), '592': ('🇬🇾', 'GY'),
    '509': ('🇭🇹', 'HT'), '504': ('🇭🇳', 'HN'), '852': ('🇭🇰', 'HK'), '36': ('🇭🇺', 'HU'),
    '354': ('🇮🇸', 'IS'), '91': ('🇮🇳', 'IN'), '62': ('🇮🇩', 'ID'), '98': ('🇮🇷', 'IR'),
    '964': ('🇮🇶', 'IQ'), '353': ('🇮🇪', 'IE'), '44': ('🇮🇲', 'IM'), '972': ('🇮🇱', 'IL'),
    '39': ('🇮🇹', 'IT'), '1876': ('🇯🇲', 'JM'), '81': ('🇯🇵', 'JP'), '441534': ('🇯🇪', 'JE'),
    '962': ('🇯🇴', 'JO'), '7': ('🇰🇿', 'KZ'), '254': ('🇰🇪', 'KE'), '686': ('🇰🇮', 'KI'),
    '850': ('🇰🇵', 'KP'), '82': ('🇰🇷', 'KR'), '965': ('🇰🇼', 'KW'), '996': ('🇰🇬', 'KG'),
    '856': ('🇱🇦', 'LA'), '371': ('🇱🇻', 'LV'), '961': ('🇱🇧', 'LB'), '266': ('🇱🇸', 'LS'),
    '231': ('🇱🇷', 'LR'), '218': ('🇱🇾', 'LY'), '423': ('🇱🇮', 'LI'), '370': ('🇱🇹', 'LT'),
    '352': ('🇱🇺', 'LU'), '853': ('🇲🇴', 'MO'), '389': ('🇲🇰', 'MK'), '261': ('🇲🇬', 'MG'),
    '265': ('🇲🇼', 'MW'), '60': ('🇲🇾', 'MY'), '960': ('🇲🇻', 'MV'), '223': ('🇲🇱', 'ML'),
    '356': ('🇲🇹', 'MT'), '692': ('🇲🇭', 'MH'), '596': ('🇲🇶', 'MQ'), '222': ('🇲🇷', 'MR'),
    '230': ('🇲🇺', 'MU'), '262': ('🇾🇹', 'YT'), '52': ('🇲🇽', 'MX'), '691': ('🇫🇲', 'FM'),
    '373': ('🇲🇩', 'MD'), '377': ('🇲🇨', 'MC'), '976': ('🇲🇳', 'MN'), '382': ('🇲🇪', 'ME'),
    '1664': ('🇲🇸', 'MS'), '212': ('🇲🇦', 'MA'), '258': ('🇲🇿', 'MZ'), '95': ('🇲🇲', 'MM'),
    '264': ('🇳🇦', 'NA'), '674': ('🇳🇷', 'NR'), '977': ('🇳🇵', 'NP'), '31': ('🇳🇱', 'NL'),
    '687': ('🇳🇨', 'NC'), '64': ('🇳🇿', 'NZ'), '505': ('🇳🇮', 'NI'), '227': ('🇳🇪', 'NE'),
    '234': ('🇳🇬', 'NG'), '683': ('🇳🇺', 'NU'), '672': ('🇳🇫', 'NF'), '1670': ('🇲🇵', 'MP'),
    '47': ('🇳🇴', 'NO'), '968': ('🇴🇲', 'OM'), '92': ('🇵🇰', 'PK'), '680': ('🇵🇼', 'PW'),
    '970': ('🇵🇸', 'PS'), '507': ('🇵🇦', 'PA'), '675': ('🇵🇬', 'PG'), '595': ('🇵🇾', 'PY'),
    '51': ('🇵🇪', 'PE'), '63': ('🇵🇭', 'PH'), '48': ('🇵🇱', 'PL'), '351': ('🇵🇹', 'PT'),
    '1787': ('🇵🇷', 'PR'), '974': ('🇶🇦', 'QA'), '262': ('🇷🇪', 'RE'), '40': ('🇷🇴', 'RO'),
    '7': ('🇷🇺', 'RU'), '250': ('🇷🇼', 'RW'), '590': ('🇧🇱', 'BL'), '290': ('🇸🇭', 'SH'),
    '1869': ('🇰🇳', 'KN'), '1758': ('🇱🇨', 'LC'), '590': ('🇲🇫', 'MF'), '508': ('🇵🇲', 'PM'),
    '1784': ('🇻🇨', 'VC'), '685': ('🇼🇸', 'WS'), '378': ('🇸🇲', 'SM'), '239': ('🇸🇹', 'ST'),
    '966': ('🇸🇦', 'SA'), '221': ('🇸🇳', 'SN'), '381': ('🇷🇸', 'RS'), '248': ('🇸🇨', 'SC'),
    '232': ('🇸🇱', 'SL'), '65': ('🇸🇬', 'SG'), '1721': ('🇸🇽', 'SX'), '421': ('🇸🇰', 'SK'),
    '386': ('🇸🇮', 'SI'), '677': ('🇸🇧', 'SB'), '252': ('🇸🇴', 'SO'), '27': ('🇿🇦', 'ZA'),
    '211': ('🇸🇸', 'SS'), '34': ('🇪🇸', 'ES'), '94': ('🇱🇰', 'LK'), '249': ('🇸🇩', 'SD'),
    '597': ('🇸🇷', 'SR'), '47': ('🇸🇯', 'SJ'), '268': ('🇸🇿', 'SZ'), '46': ('🇸🇪', 'SE'),
    '41': ('🇨🇭', 'CH'), '963': ('🇸🇾', 'SY'), '886': ('🇹🇼', 'TW'), '992': ('🇹🇯', 'TJ'),
    '255': ('🇹🇿', 'TZ'), '66': ('🇹🇭', 'TH'), '670': ('🇹🇱', 'TL'), '228': ('🇹🇬', 'TG'),
    '690': ('🇹🇰', 'TK'), '676': ('🇹🇴', 'TO'), '1868': ('🇹🇹', 'TT'), '216': ('🇹🇳', 'TN'),
    '90': ('🇹🇷', 'TR'), '993': ('🇹🇲', 'TM'), '688': ('🇹🇻', 'TV'), '256': ('🇺🇬', 'UG'),
    '380': ('🇺🇦', 'UA'), '971': ('🇦🇪', 'AE'), '44': ('🇬🇧', 'GB'), '1': ('🇺🇸', 'US'),
    '598': ('🇺🇾', 'UY'), '998': ('🇺🇿', 'UZ'), '678': ('🇻🇺', 'VU'), '379': ('🇻🇦', 'VA'),
    '58': ('🇻🇪', 'VE'), '84': ('🇻🇳', 'VN'), '681': ('🇼🇫', 'WF'), '967': ('🇾🇪', 'YE'),
    '260': ('🇿🇲', 'ZM'), '263': ('🇿🇼', 'ZW')
}
        for code, info in country_map.items():
            if clean_number.startswith(code):
                return info[0], info[1]
        return '🌍', 'XX'
    
    def format_message_with_buttons(self, service, number, otp, sms, use_dots=True):
        flag, country_code = self.get_country_info(number)
        clean_number = number.replace('+', '').replace(' ', '').strip()
        
        # Format number with •• hiding 2 middle digits (optional)
        if use_dots and len(clean_number) > 6:
            mid_point = len(clean_number) // 2
            formatted_number = clean_number[:mid_point-1] + '••' + clean_number[mid_point+1:]
        else:
            formatted_number = clean_number
        
        service_name = service if service else "Service"
        
        text = (
            f"*{flag} #{country_code} {service_name} {formatted_number}*\n\n"
            f"```\n{sms}\n```"
        )
        
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        if otp != "N/A":
            # Use native copy button if your local pyTelegramBotAPI supports it
            keyboard.row(types.InlineKeyboardButton(f"{otp}", copy_text=types.CopyTextButton(text=otp)))
        # For production, fallback to callback_data method:
        # keyboard.row(types.InlineKeyboardButton(f"{otp}", callback_data=f"otp_{otp}"))
        keyboard.row(
            types.InlineKeyboardButton("❗️ Panel", url=PANEL_URL),
            types.InlineKeyboardButton("♻️ All Number", url=ALL_NUMBERS_URL)
        )
        return text, keyboard


# ==========================================
# 🔥 MAIN LOOP - CONTINUOUS MONITORING
# ==========================================
def run_forwarder():
    """Continuously monitor panel and forward messages to group"""
    print("🚀 Panel to Group Forwarder Started!")
    print("=" * 50)
    
    forwarder = PanelToGroupForwarder()
    last_check_time = None
    
    while True:
        try:
            print(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] Checking panel...")
            
            forwarder.fetch_all_messages_and_forward()
            
            print(f"[*] Sleeping for 7 seconds...")
            time.sleep(7)  # Check every 7 seconds
            
        except KeyboardInterrupt:
            print("\n\n⚠️ Stopped by user")
            break
        except Exception as e:
            print(f"[ERROR] {e}")
            print("[*] Restarting in 10 seconds...")
            time.sleep(10)


# ==========================================
# 🔥 EXAMPLE USAGE
# ==========================================
if __name__ == "__main__":
    # Start Flask keep-alive server
    keep_alive()
    
    # Fill in credentials above first!
    print("=" * 50)
    print("🔥 PANEL TO TELEGRAM GROUP FORWARDER")
    print("=" * 50)
    print("\n⚙️  Configuration Check:\n")
    
    missing = []
    if not BOT_TOKEN: missing.append("BOT_TOKEN")
    if not GROUP_IDS_WITH_DOTS and not GROUP_IDS_WITHOUT_DOTS: missing.append("GROUP_IDS")
    if not PANEL_USERNAME: missing.append("PANEL_USERNAME")
    if not PANEL_PASSWORD: missing.append("PANEL_PASSWORD")
    
    if missing:
        print("❌ Missing configuration:")
        for item in missing:
            print(f"   - {item}")
        print("\n⚠️  Please fill in the values at the top of the file!\n")
        input("Press Enter to exit...")
    else:
        print("✅ All configuration values are set!")
        print("\n🚀 Starting forwarder...\n")
        run_forwarder()



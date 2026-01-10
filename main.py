import os
import logging
import json
import asyncio
import glob
import random
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

# Compatibility for Python 3.13+ (audioop removal)
import sys
try:
    import audioop
except ImportError:
    try:
        import audioop_copy as audioop
        sys.modules['audioop'] = audioop
    except ImportError:
        # Fallback to avoid crash on import
        class MockAudioop:
            def __getattr__(self, name):
                def mock_func(*args, **kwargs):
                    raise ImportError("audioop module is required for this action and is missing in Python 3.13+")
                return mock_func
        sys.modules['audioop'] = MockAudioop()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp
from shazamio import Shazam
from pydub import AudioSegment

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Config
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# Priority: .env file first, then environment secrets
try:
    with open(".env", "r") as f:
        for line in f:
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                val = line.split("=", 1)[1].strip()
                if val:
                    TELEGRAM_TOKEN = val
                break
except:
    pass

FOOTER_TEXT = {
    'ru': "\n\n⚡️ *Бот разработан Aglarus*",
    'uz': "\n\n⚡️ *Bot Aglarus tomonidan ishlab chiqilgan*",
    'en': "\n\n⚡️ *Bot developed by Aglarus*",
    'az': "\n\n⚡️ *Bot Aglarus tərəfindən hazırlanıb*"
}

# Persistent storage for user preferences
PREFS_FILE = "user_prefs.json"

def load_prefs():
    if os.path.exists(PREFS_FILE):
        try:
            with open(PREFS_FILE, 'r') as f:
                # Convert string keys back to int for user_id
                data = json.load(f)
                return {int(k): v for k, v in data.items()}
        except Exception as e:
            logger.error(f"Error loading prefs: {e}")
    return {}

def save_prefs():
    try:
        with open(PREFS_FILE, 'w') as f:
            json.dump(user_prefs, f)
    except Exception as e:
        logger.error(f"Error saving prefs: {e}")

user_prefs = load_prefs()
user_searches = {}

STRINGS = {
    'ru': {
        'start': "🎸 *Привет! Я твой личный музыкальный гуру.*\n\n1️⃣ *Поиск*: Просто напиши название или автора.\n2️⃣ *Распознавание*: Скинь аудио или голосовое — и я узнаю этот хит!\n\n📩 Попробуй: 'Лепс зараза'",
        'lang_select': "Выбери язык / Tilni tanlang / Select language / Dil seçin:",
        'searching': ["🎸 Настраиваю гитару...", "🎼 Ищу вдохновение в нотах...", "🎧 Прослушиваю мировые хиты..."],
        'found': ["✨ Эврика! Вот что удалось найти:", "🎵 Музыкальная находка специально для тебя:", "🔥 Это звучит круто! Выбирай:"],
        'not_found': "😢 Увы, тишина... Ничего не найдено.\nПопробуй другой запрос!",
        'error': "😵 Ой, струна лопнула! (Ошибка поиска)",
        'back': "◀️ Назад",
        'next': "▶️ Вперёд",
        'timeout': "🕰 Время вышло! Начни новый поиск.",
        'recognizing': "🎧 *Прислушиваюсь к ритму...*",
        'not_recognized': "🤷‍♂️ Не узнаю этот мотив... Может, споешь погромче?",
        'recognized': "🔥 *О, это же {subtitle} — {title}!* \nИщу лучшую запись для тебя...",
        'rec_error': "😵 Не удалось распознать. Кажется, кто-то фальшивит!",
        'sending': "🚀 *Летит к тебе:* {title}...",
        'dl_error': "❌ Загрузка сорвалась. Попробуй еще раз.",
        'track_error': "😿 Прости, не удалось достать этот трек.",
        'dev': "💎 Разработка: Aglarus"
    },
    'uz': {
        'start': "🎸 *Salom! Men sizning shaxsiy musiqa gurusingizman.*\n\n1️⃣ *Qidiruv*: Shunchaki nomini yoki muallifini yozing.\n2️⃣ *Tanish*: Audio yoki ovozli xabar yuboring — va men ushbu xitni taniyman!\n\n📩 Sinab ko'ring: 'Sherali Jo'rayev'",
        'lang_select': "Tilni tanlang:",
        'searching': ["🎸 Gitarani sozlayapman...", "🎼 Notalardan ilhom qidiryapman...", "🎧 Dunyo xitlarini tinglayapman..."],
        'found': ["✨ Evrika! Mana nimalar topildi:", "🎵 Maxsus siz uchun musiqiy topilma:", "🔥 Bu ajoyib eshitiladi! Tanlang:"],
        'not_found': "😢 Afsus, jimjitlik... Hech narsa topilmadi.\nBoshqa so'rovni sinab ko'ring!",
        'error': "😵 Voy, tor uzilib ketdi! (Qidiruv xatosi)",
        'back': "◀️ Orqaga",
        'next': "▶️ Oldinga",
        'timeout': "🕰 Vaqt tugadi! Yangi qidiruvni boshlang.",
        'recognizing': "🎧 *Ritmni tinglayapman...*",
        'not_recognized': "🤷‍♂️ Bu ohangni tani olmayapman... Balki balandroq kuylarsiz?",
        'recognized': "🔥 *O, bu {subtitle} — {title}!* \nSiz uchun eng yaxshi yozuvni qidiryapman...",
        'rec_error': "😵 Taniy olmadim. Kimdir noto'g'ri kuylayotganga o'xshaydi!",
        'sending': "🚀 *Sizga uchmoqda:* {title}...",
        'dl_error': "❌ Yuklab olish amalga oshmadi. Qayta urinib ko'ring.",
        'track_error': "😿 Kechirasiz, bu trekni olishning iloji bo'lmadi.",
        'dev': "💎 Ishlab chiquvchi: Aglarus"
    },
    'en': {
        'start': "🎸 *Hello! I'm your personal music guru.*\n\n1️⃣ *Search*: Just type the name or artist.\n2️⃣ *Recognition*: Send audio or voice — and I'll recognize this hit!\n\n📩 Try: 'Queen Bohemian Rhapsody'",
        'lang_select': "Select language:",
        'searching': ["🎸 Tuning the guitar...", "🎼 Looking for inspiration in notes...", "🎧 Listening to world hits..."],
        'found': ["✨ Eureka! Here's what I found:", "🎵 A musical find just for you:", "🔥 This sounds cool! Choose:"],
        'not_found': "😢 Alas, silence... Nothing found.\nTry another query!",
        'error': "😵 Oops, a string snapped! (Search error)",
        'back': "◀️ Back",
        'next': "▶️ Next",
        'timeout': "🕰 Time's up! Start a new search.",
        'recognizing': "🎧 *Listening to the rhythm...*",
        'not_recognized': "🤷‍♂️ I don't recognize this tune... Maybe sing louder?",
        'recognized': "🔥 *Oh, it's {subtitle} — {title}!* \nLooking for the best recording for you...",
        'rec_error': "😵 Could not recognize. Someone seems to be out of tune!",
        'sending': "🚀 *Flying to you:* {title}...",
        'dl_error': "❌ Download failed. Try again.",
        'track_error': "😿 Sorry, could not get this track.",
        'dev': "💎 Developer: Aglarus"
    },
    'az': {
        'start': "🎸 *Salam! Mən sənin şəxsi musiqi qurun bələdçisiyəm.*\n\n1️⃣ *Axtarış*: Sadəcə adı və ya müəllifi yaz.\n2️⃣ *Tanıma*: Audio və ya səsli mesaj göndər — mən bu hiti tanıyacam!\n\n📩 Sına: 'Rəşid Behbudov'",
        'lang_select': "Dil seçin:",
        'searching': ["🎸 Gitaranı kökləyirəm...", "🎼 Notlarda ilham axtarıram...", "🎧 Dünya hitlərini dinləyirəm..."],
        'found': ["✨ Evrika! Budur tapılanlar:", "🎵 Sənin üçün xüsusi musiqi tapıntısı:", "🔥 Bu əla səslənir! Seç:"],
        'not_found': "😢 Təəssüf ki, sükutdur... Heç nə tapılmadı.\nBaşqa sorğu yoxla!",
        'error': "😵 Oy, sim qırıldı! (Axtarış xətası)",
        'back': "◀️ Geri",
        'next': "▶️ İrəli",
        'timeout': "🕰 Vaxt bitdi! Yeni axtarışa başla.",
        'recognizing': "🎧 *Ritmi dinləyirəm...*",
        'not_recognized': "🤷‍♂️ Bu melodiyanı tanımıram... Bəlkə bir az bərkdən oxuyasan?",
        'recognized': "🔥 *O, bu axı {subtitle} — {title}!* \nSənin üçün ən yaxşı yazını axtarıram...",
        'rec_error': "😵 Tanımaq mümkün olmadı. Deyəsən kimsə yalan oxuyur!",
        'sending': "🚀 *Sənə tərəf uçur:* {title}...",
        'dl_error': "❌ Yükləmə uğursuz oldu. Yenidən cəhd et.",
        'track_error': "😿 Bağışlayın, bu treki əldə etmək mümkün olmadı.",
        'dev': "💎 Hazırladı: Aglarus"
    }
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    keyboard = [
        [
            InlineKeyboardButton("🇷🇺 Русский", callback_data="setlang_ru"),
            InlineKeyboardButton("🇺🇿 Uzbekcha", callback_data="setlang_uz")
        ],
        [
            InlineKeyboardButton("🇺🇸 English", callback_data="setlang_en"),
            InlineKeyboardButton("🇦🇿 Azərbaycan", callback_data="setlang_az")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.effective_message:
        await update.effective_message.reply_text(
            STRINGS['ru']['lang_select'],
            reply_markup=reply_markup
        )

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = query.data.split('_')[1]
    user_id = update.effective_user.id
    user_prefs[user_id] = lang
    save_prefs()
    
    await query.answer()
    await query.message.edit_text(
        STRINGS[lang]['start'] + FOOTER_TEXT[lang],
        parse_mode='Markdown'
    )

def get_lang(user_id):
    return user_prefs.get(user_id, 'ru')

async def search_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the user message and search for music."""
    if not update.effective_message or not update.effective_message.text:
        return
        
    query = update.effective_message.text
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    
    sent_message = await update.effective_message.reply_text(random.choice(STRINGS[lang]['searching']))
    await perform_search(update, context, query, sent_message)

async def perform_search(update, context, query, sent_message):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    try:
        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'default_search': 'ytsearch50',
            'nocheckcertificate': True,
            'cachedir': False,
            'youtube_include_dash_manifest': False,
            'youtube_include_hls_manifest': False,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web', 'tv'],
                    'skip': ['dash', 'hls']
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'en-US,en;q=0.9',
                'Sec-Fetch-Mode': 'navigate',
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch50:{query}", download=False)
            if not info or 'entries' not in info or not info['entries']:
                await sent_message.edit_text(STRINGS[lang]['not_found'])
                return
            
            results = info['entries']
            user_searches[user_id] = {
                'query': query,
                'results': results,
                'page': 0
            }
            
            await show_results(update, context, sent_message, user_id)
            
    except Exception as e:
        logger.error(f"Search error: {e}")
        await sent_message.edit_text(STRINGS[lang]['error'])

async def show_results(update, context, message, user_id):
    search_data = user_searches.get(user_id)
    if not search_data:
        return

    lang = get_lang(user_id)
    results = search_data['results']
    page = search_data['page']
    per_page = 10
    
    start_idx = page * per_page
    end_idx = min(start_idx + per_page, len(results))
    
    text = f"{random.choice(STRINGS[lang]['found'])}\n\n"
    keyboard = []
    
    row1, row2 = [], []
    
    for i in range(start_idx, end_idx):
        num = i - start_idx + 1
        title = results[i].get('title', 'Unknown')
        text += f"{num}. {title}\n"
        
        btn = InlineKeyboardButton(str(num), callback_data=f"select_{i}")
        if num <= 5: row1.append(btn)
        else: row2.append(btn)
            
    if row1: keyboard.append(row1)
    if row2: keyboard.append(row2)
        
    nav_row = []
    if page > 0: nav_row.append(InlineKeyboardButton(STRINGS[lang]['back'], callback_data="prev"))
    if len(results) > end_idx: nav_row.append(InlineKeyboardButton(STRINGS[lang]['next'], callback_data="next"))
    
    if nav_row: keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton(STRINGS[lang]['dev'], url="https://t.me/aglarus")])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        if message:
            await message.edit_text(text, reply_markup=reply_markup)
        else:
            await update.callback_query.message.edit_text(text, reply_markup=reply_markup)
    except: pass

async def recognize_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recognize music from voice or audio message."""
    message = update.effective_message
    if not message: return
    user_id = update.effective_user.id
    lang = get_lang(user_id)

    file = None
    if message.voice: file = await message.voice.get_file()
    elif message.audio: file = await message.audio.get_file()
    elif message.video: file = await message.video.get_file()
    elif message.document:
        mime = message.document.mime_type
        if mime and (mime.startswith('audio/') or mime.startswith('video/')):
            file = await message.document.get_file()
    
    if not file: return

    status_msg = await message.reply_text(STRINGS[lang]['recognizing'], parse_mode='Markdown')
    
    try:
        os.makedirs('temp', exist_ok=True)
        ogg_path = f"temp/{file.file_id}.ogg"
        mp3_path = f"temp/{file.file_id}.mp3"
        await file.download_to_drive(ogg_path)
        
        audio = AudioSegment.from_file(ogg_path)
        audio.export(mp3_path, format="mp3")
        
        shazam = Shazam()
        out = await shazam.recognize(mp3_path)
        
        if os.path.exists(ogg_path): os.remove(ogg_path)
        if os.path.exists(mp3_path): os.remove(mp3_path)
        
        if not out or not out.get('track'):
            await status_msg.edit_text(STRINGS[lang]['not_recognized'])
            return
            
        track = out['track']
        title = track.get('title', 'Unknown')
        subtitle = track.get('subtitle', 'Unknown')
        query = f"{subtitle} {title}"
        
        await status_msg.edit_text(STRINGS[lang]['recognized'].format(subtitle=subtitle, title=title), parse_mode='Markdown')
        await perform_search(update, context, query, status_msg)
        
    except Exception as e:
        logger.error(f"Recognition error: {e}")
        await status_msg.edit_text(STRINGS[lang]['rec_error'])

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    data = query.data
    
    if data.startswith("setlang_"):
        await set_language(update, context)
        return

    if user_id not in user_searches:
        await query.message.edit_text(STRINGS[lang]['timeout'])
        return
        
    search_data = user_searches[user_id]
    
    if data == "next":
        search_data['page'] += 1
        await show_results(update, context, None, user_id)
    elif data == "prev":
        search_data['page'] -= 1
        await show_results(update, context, None, user_id)
    elif data.startswith("select_"):
        idx = int(data.split("_")[1])
        track = search_data['results'][idx]
        await download_and_send(update, context, track)

async def download_and_send(update, context, track):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    url = track.get('url') or track.get('webpage_url')
    title = track.get('title', 'Song')
    
    status_msg = await context.bot.send_message(chat_id, STRINGS[lang]['sending'].format(title=title), parse_mode='Markdown')
    
    try:
        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'outtmpl': 'downloads/%(id)s.%(ext)s',
            'quiet': True,
            'nocheckcertificate': True,
            'cachedir': False,
            'buffersize': 1024*1024,
            'noplaylist': True,
            'external_downloader': 'ffmpeg',
            'external_downloader_args': ['-ss', '00:00:00', '-t', '00:10:00', '-preset', 'ultrafast'],
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web', 'tv'],
                    'skip': ['dash', 'hls']
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'en-US,en;q=0.9',
                'Sec-Fetch-Mode': 'navigate',
            }
        }
        
        os.makedirs('downloads', exist_ok=True)
            
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            files = glob.glob('downloads/*')
            if not files:
                await status_msg.edit_text(STRINGS[lang]['dl_error'])
                return
            
            filename = max(files, key=os.path.getctime)
            with open(filename, 'rb') as audio:
                await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=audio,
                    title=title,
                    caption=f"🎧 {title}{FOOTER_TEXT[lang]}",
                    parse_mode='Markdown',
                    read_timeout=180,
                    write_timeout=180,
                )
            
            os.remove(filename)
            await status_msg.delete()
            
    except Exception as e:
        logger.error(f"Download error: {e}")
        await status_msg.edit_text(STRINGS[lang]['track_error'])


async def main_async():
    if not TELEGRAM_TOKEN:
        print("❌ Ошибка: TELEGRAM_BOT_TOKEN не найден в .env или Secrets!")
        return
        
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Получаем информацию о боте для вывода названия
    bot_info = await application.bot.get_me()
    print(f"🚀 Бот @{bot_info.username} ({bot_info.first_name}) успешно запущен и готов к работе!")
    logger.info(f"Бот {bot_info.username} запущен")
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_music))
    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO | filters.VIDEO | filters.Document.ALL, recognize_audio))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    async with application:
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        # Keep the event loop running
        while True:
            await asyncio.sleep(1)

def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Fatal error: {e}")

if __name__ == "__main__":
    main()

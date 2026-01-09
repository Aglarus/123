import os
import logging
import json
import asyncio
import glob
import random
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
FOOTER_TEXT = "\n\n⚡️ *Бот разработан Aglarus*"

# In-memory storage for search results
user_searches = {}

CREATIVE_STATUS = [
    "🎸 Настраиваю гитару...",
    "🎼 Ищу вдохновение в нотах...",
    "🎧 Прослушиваю мировые хиты...",
    "🎹 Проверяю аккорды...",
    "🎤 Распеваюсь перед поиском...",
    "🎻 Протираю смычок...",
    "🥁 Ловлю ритм..."
]

CREATIVE_FOUND = [
    "✨ Эврика! Вот что удалось найти:",
    "🎵 Музыкальная находка специально для тебя:",
    "🌟 Твои уши будут в восторге:",
    "🎶 Посмотри, какие сокровища я нашел:",
    "🔥 Это звучит круто! Выбирай:"
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    if update.effective_message:
        await update.effective_message.reply_text(
            "🎸 *Привет! Я твой личный музыкальный гуру.*\n\n"
            "1️⃣ *Поиск*: Просто напиши название или автора.\n"
            "2️⃣ *Распознавание*: Скинь аудио или голосовое — и я узнаю этот хит!\n\n"
            "📩 Попробуй: 'Лепс зараза'"
            f"{FOOTER_TEXT}",
            parse_mode='Markdown'
        )

async def search_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the user message and search for music."""
    if not update.effective_message or not update.effective_message.text:
        return
        
    query = update.effective_message.text
    user_id = update.effective_user.id
    
    sent_message = await update.effective_message.reply_text(random.choice(CREATIVE_STATUS))
    await perform_search(update, context, query, sent_message)

async def perform_search(update, context, query, sent_message):
    user_id = update.effective_user.id
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
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch50:{query}", download=False)
            if not info or 'entries' not in info or not info['entries']:
                await sent_message.edit_text("😢 Увы, тишина... Ничего не найдено.\nПопробуй другой запрос!")
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
        await sent_message.edit_text(f"😵 Ой, струна лопнула! (Ошибка поиска)")

async def show_results(update, context, message, user_id):
    search_data = user_searches.get(user_id)
    if not search_data:
        return

    results = search_data['results']
    page = search_data['page']
    per_page = 10
    
    start_idx = page * per_page
    end_idx = min(start_idx + per_page, len(results))
    
    text = f"{random.choice(CREATIVE_FOUND)}\n\n"
    keyboard = []
    
    row1, row2 = [], []
    
    for i in range(start_idx, end_idx):
        num = i - start_idx + 1
        title = results[i].get('title', 'Unknown')
        text += f"{num}️⃣ {title}\n"
        
        btn = InlineKeyboardButton(str(num), callback_data=f"select_{i}")
        if num <= 5: row1.append(btn)
        else: row2.append(btn)
            
    if row1: keyboard.append(row1)
    if row2: keyboard.append(row2)
        
    nav_row = []
    if page > 0: nav_row.append(InlineKeyboardButton("◀️ Назад", callback_data="prev"))
    if len(results) > end_idx: nav_row.append(InlineKeyboardButton("▶️ Вперёд", callback_data="next"))
    
    if nav_row: keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton("💎 Разработка: Aglarus", url="https://t.me/aglarus")])
        
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

    file = None
    if message.voice: file = await message.voice.get_file()
    elif message.audio: file = await message.audio.get_file()
    elif message.video: file = await message.video.get_file()
    elif message.document:
        mime = message.document.mime_type
        if mime and (mime.startswith('audio/') or mime.startswith('video/')):
            file = await message.document.get_file()
    
    if not file: return

    status_msg = await message.reply_text("🎧 *Прислушиваюсь к ритму...*", parse_mode='Markdown')
    
    try:
        os.makedirs('temp', exist_ok=True)
        ogg_path = f"temp/{file.file_id}.ogg"
        mp3_path = f"temp/{file.file_id}.mp3"
        await file.download_to_drive(ogg_path)
        
        audio = AudioSegment.from_file(ogg_path)
        audio.export(mp3_path, format="mp3")
        
        shazam = Shazam()
        out = await shazam.recognize_song(mp3_path)
        
        if os.path.exists(ogg_path): os.remove(ogg_path)
        if os.path.exists(mp3_path): os.remove(mp3_path)
        
        if not out or not out.get('track'):
            await status_msg.edit_text("🤷‍♂️ Не узнаю этот мотив... Может, споешь погромче?")
            return
            
        track = out['track']
        title = track.get('title', 'Unknown')
        subtitle = track.get('subtitle', 'Unknown')
        query = f"{subtitle} {title}"
        
        await status_msg.edit_text(f"🔥 *О, это же {subtitle} — {title}!* \nИщу лучшую запись для тебя...", parse_mode='Markdown')
        await perform_search(update, context, query, status_msg)
        
    except Exception as e:
        logger.error(f"Recognition error: {e}")
        await status_msg.edit_text("😵 Не удалось распознать. Кажется, кто-то фальшивит!")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data
    
    if user_id not in user_searches:
        await query.message.edit_text("🕰 Время вышло! Начни новый поиск.")
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
    url = track.get('url') or track.get('webpage_url')
    title = track.get('title', 'Song')
    
    status_msg = await context.bot.send_message(chat_id, f"🚀 *Летит к тебе:* {title}...", parse_mode='Markdown')
    
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
        }
        
        os.makedirs('downloads', exist_ok=True)
            
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            files = glob.glob('downloads/*')
            if not files:
                await status_msg.edit_text("❌ Загрузка сорвалась. Попробуй еще раз.")
                return
            
            filename = max(files, key=os.path.getctime)
            with open(filename, 'rb') as audio:
                await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=audio,
                    title=title,
                    caption=f"🎧 {title}{FOOTER_TEXT}",
                    parse_mode='Markdown',
                    read_timeout=180,
                    write_timeout=180,
                )
            
            os.remove(filename)
            await status_msg.delete()
            
    except Exception as e:
        logger.error(f"Download error: {e}")
        await status_msg.edit_text(f"😿 Прости, не удалось достать этот трек.")

def main():
    if not TELEGRAM_TOKEN: return
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_music))
    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO | filters.VIDEO | filters.Document.ALL, recognize_audio))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.run_polling()

if __name__ == "__main__":
    main()

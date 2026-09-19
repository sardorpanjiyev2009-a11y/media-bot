import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import yt_dlp
from shazamio import Shazam
import subprocess

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    text = (
        f"Assalomu alaykum, **{user_name}**! 👋\n\n"
        "Men sizning shaxsiy yordamchi botingizman 🤖✨\n"
        "📥 **YouTube, Instagram yoki TikTok havolasini** yuboring — videoni va ostida qo'shiqni topish tugmasini beraman.\n"
        "🎵 **Ovozli xabar yoki musiqa** yuboring — Shazam orqali topib, MP3 faylini beraman.\n"
        "✍️ Yoki shunchaki **qo'shiq nomini** yozib yuboring — 10 ta variant va yuklash tugmalarini chiqarib beraman!"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# Matn yoki havolalarni qayta ishlash
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    # 1. Havola bo'lsa - Videoni yuklab berish va qo'shiqni topish tugmasini qo'shish
    if text.startswith("http"):
        sent_msg = await update.message.reply_text("⏳ Havola qabul qilindi, video yuklab olinmoqda. Biroz kuting...")

        try:
            ydl_opts = {
                'outtmpl': 'downloaded_video.%(ext)s',
                'format': 'best',
                'socket_timeout': 30,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(text, download=True)
                filename = ydl.prepare_filename(info)

            # Videodan audio ajratib Shazam orqali musiqani aniqlaymiz
            audio_temp = "video_audio.mp3"
            subprocess.run(['ffmpeg', '-y', '-i', filename, '-q:a', '0', '-map', 'a', audio_temp], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            song_query = "Musiqa"
            if os.path.exists(audio_temp):
                try:
                    shazam = Shazam()
                    out = await shazam.recognize(audio_temp)
                    if "track" in out:
                        track = out["track"]
                        title = track.get("title", "")
                        artist = track.get("subtitle", "")
                        song_query = f"{artist} - {title}"
                except:
                    pass
                os.remove(audio_temp)

            # Qidiruv so'rovini xotirada saqlaymiz
            context.user_data['reel_song_query'] = song_query

            # Videoni tagida tugma bilan yuboramiz
            keyboard = [[InlineKeyboardButton("🎵 Qo'shiqni yuklab olish", callback_data="get_reel_song")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_video(video=open(filename, 'rb'), reply_markup=reply_markup)
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=sent_msg.message_id)

            if os.path.exists(filename):
                os.remove(filename)

        except Exception as e:
            await update.message.reply_text(f"Kechirasiz, videoni yuklab olishda xatolik yuz berdi: {e}")

    # 2. Qo'shiq nomi bo'lsa - 10 ta variant va tugmalarni chiqarish
    else:
        sent_msg = await update.message.reply_text(f"🔍 '{text}' bo'yicha 10 ta variant qidirilmoqda...")

        try:
            ydl_opts = {
                'extract_flat': True,
                'quiet': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch10:{text}", download=False)
                entries = info.get('entries', [])

            if not entries:
                await update.message.reply_text("Hech qanday natija topilmadi.")
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=sent_msg.message_id)
                return

            context.user_data['search_results'] = entries

            result_lines = [f"🔍 **{text}** bo'yicha topilgan variantlar:\n"]
            
            keyboard = []
            row = []

            for i, entry in enumerate(entries, 1):
                title = entry.get('title', 'Noma\'lum')
                duration_sec = entry.get('duration', 0)
                
                if duration_sec:
                    mins = duration_sec // 60
                    secs = duration_sec % 60
                    duration_str = f"{mins}:{secs:02d}"
                else:
                    duration_str = ""
                
                result_lines.append(f"{i}. {title} **{duration_str}**")
                
                row.append(InlineKeyboardButton(str(i), callback_data=f"dl_{i-1}"))
                if len(row) == 5:
                    keyboard.append(row)
                    row = []

            if row:
                keyboard.append(row)

            reply_markup = InlineKeyboardMarkup(keyboard)
            response_text = "\n".join(result_lines)

            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=sent_msg.message_id)
            await update.message.reply_text(response_text, parse_mode="Markdown", reply_markup=reply_markup)

        except Exception as e:
            await update.message.reply_text(f"Qidirishda xatolik yuz berdi: {e}")

# Tugma bosilganda ishlaydigan qism
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    # Agar videodagi qo'shiqni yuklab olish tugmasi bosilsa
    if data == "get_reel_song":
        song_query = context.user_data.get('reel_song_query', 'popular music')
        sent_msg = await query.message.reply_text(f"🔍 '{song_query}' bo'yicha variantlar qidirilmoqda...")

        try:
            ydl_opts = {
                'extract_flat': True,
                'quiet': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch10:{song_query}", download=False)
                entries = info.get('entries', [])

            if not entries:
                await query.message.reply_text("Hech qanday qo'shiq topilmadi.")
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=sent_msg.message_id)
                return

            context.user_data['search_results'] = entries

            result_lines = [f"🎵 **{song_query}** bo'yicha topilgan variantlar:\n"]
            
            keyboard = []
            row = []

            for i, entry in enumerate(entries, 1):
                title = entry.get('title', 'Noma\'lum')
                duration_sec = entry.get('duration', 0)
                
                if duration_sec:
                    mins = duration_sec // 60
                    secs = duration_sec % 60
                    duration_str = f"{mins}:{secs:02d}"
                else:
                    duration_str = ""
                
                result_lines.append(f"{i}. {title} **{duration_str}**")
                
                row.append(InlineKeyboardButton(str(i), callback_data=f"dl_{i-1}"))
                if len(row) == 5:
                    keyboard.append(row)
                    row = []

            if row:
                keyboard.append(row)

            reply_markup = InlineKeyboardMarkup(keyboard)
            response_text = "\n".join(result_lines)

            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=sent_msg.message_id)
            await query.message.reply_text(response_text, parse_mode="Markdown", reply_markup=reply_markup)

        except Exception as e:
            await query.message.reply_text(f"Xatolik yuz berdi: {e}")

    # Agar 1 dan 10 gacha raqamli mp3 yuklash tugmasi bosilsa
    elif data.startswith("dl_"):
        index = int(data.split("_")[1])
        entries = context.user_data.get('search_results', [])

        if index >= len(entries):
            await query.message.reply_text("Kechirasiz, bu amalning vaqti o'tdi. Qaytadan urinib ko'ring.")
            return

        selected_entry = entries[index]
        video_url = selected_entry.get('url') or f"https://www.youtube.com/watch?v={selected_entry.get('id')}"
        title = selected_entry.get('title', 'Musiqa')

        await query.message.reply_text(f"📥 '{title}' yuklab olinmoqda, biroz kuting...")

        try:
            mp3_opts = {
                'format': 'bestaudio/best',
                'outtmpl': 'song.%(ext)s',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }

            with yt_dlp.YoutubeDL(mp3_opts) as ydl:
                ydl.extract_info(video_url, download=True)
                filename = "song.mp3"

            await query.message.reply_audio(audio=open(filename, 'rb'), title=title)

            if os.path.exists(filename):
                os.remove(filename)

        except Exception as e:
            await query.message.reply_text(f"Yuklab olishda xatolik yuz berdi: {e}")

# Shazam orqali musiqani aniqlash va MP3 formatda yuborish
async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    audio_file = msg.audio or msg.voice

    if not audio_file:
        await update.message.reply_text("Iltimos, musiqa fayli yoki ovozli xabar yuboring!")
        return

    await update.message.reply_text("🔍 Musiqa qidirilmoqda va MP3 fayl tayyorlanmoqda, ozgina sabr...")

    try:
        file = await context.bot.get_file(audio_file.file_id)
        file_path = "temp_music.mp3"
        await file.download_to_drive(file_path)

        shazam = Shazam()
        out = await shazam.recognize(file_path)

        if os.path.exists(file_path):
            os.remove(file_path)

        if "track" in out:
            track = out["track"]
            title = track.get("title", "Noma'lum")
            artist = track.get("subtitle", "Noma'lum artist")
            image = track.get("images", {}).get("coverart")
            
            result_text = f"🎵 **Topilgan qo'shiq:**\n\n🎤 **Artist:** {artist}\n🎧 **Nomi:** {title}"
            
            if image:
                await update.message.reply_photo(photo=image, caption=result_text, parse_mode="Markdown")
            else:
                await update.message.reply_text(result_text, parse_mode="Markdown")

            query_str = f"{artist} - {title}"
            await update.message.reply_text(f"📥 Qo'shiqning MP3 fayli yuklab olinmoqda...")

            mp3_opts = {
                'format': 'bestaudio/best',
                'outtmpl': 'song.%(ext)s',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }

            with yt_dlp.YoutubeDL(mp3_opts) as ydl:
                ydl.extract_info(f"ytsearch1:{query_str}", download=True)
                filename = "song.mp3"

            await update.message.reply_audio(audio=open(filename, 'rb'), title=title, performer=artist)

            if os.path.exists(filename):
                os.remove(filename)

        else:
            await update.message.reply_text("Kechirasiz, bu musiqani aniqlay olmadim. Boshqa parcha yuborib ko'ring.")

    except Exception as e:
        await update.message.reply_text(f"Xatolik yuz berdi: {e}")

if __name__ == '__main__':
    TOKEN = "8679524771:AAHxsBVZVPTUEF3ByXn1Q2ZQpJglGi-txyQ"
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, handle_audio))

    print("Bot ishga tushdi...")
    application.run_polling()
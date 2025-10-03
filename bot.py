import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import yt_dlp

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Token desde variables de entorno
TOKEN = os.environ.get('BOT_TOKEN')

# Verificar token
if not TOKEN:
    logger.error("❌ BOT_TOKEN no encontrado en variables de entorno")
    raise ValueError("BOT_TOKEN no configurado")

# Diccionario para almacenar info temporal
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 **Bot Descargador Avanzado**\n\n"
        "✨ **Características:**\n"
        "• ✅ Videos en diferentes calidades\n"
        "• 🎵 Audio MP3\n"
        "• 🚀 YouTube, TikTok, Instagram, etc.\n\n"
        "📥 **Envía un enlace para comenzar**"
    )

async def process_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    user_id = update.message.from_user.id
    
    try:
        # Verificar enlace
        domains = ['youtube', 'youtu.be', 'tiktok', 'instagram', 'twitter', 'x.com']
        if not any(domain in url.lower() for domain in domains):
            await update.message.reply_text("❌ Enlace no soportado.")
            return

        msg = await update.message.reply_text("🔍 Analizando video...")
        
        # Obtener info sin descargar
        ydl_info = yt_dlp.YoutubeDL({'quiet': True})
        info = ydl_info.extract_info(url, download=False)
        
        # Guardar info temporal
        user_data[user_id] = {'url': url, 'title': info.get('title', 'Video')}
        await msg.delete()
        
        # Crear teclado
        keyboard = [
            [InlineKeyboardButton("🎥 Alta Calidad (720p)", callback_data="quality_720")],
            [InlineKeyboardButton("🎥 Media Calidad (480p)", callback_data="quality_480")],
            [InlineKeyboardButton("🎵 Audio MP3", callback_data="audio_mp3")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🎬 **{info['title'][:50]}...**\n"
            f"⏱ Duración: {info.get('duration', 0)//60}:{info.get('duration', 0)%60:02d}\n\n"
            f"📥 **Selecciona formato:**",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("❌ Error analizando el video.")

async def handle_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if query.data == "cancel":
        await query.edit_message_text("❌ Cancelado.")
        return
    
    if user_id not in user_data:
        await query.edit_message_text("❌ Sesión expirada.")
        return
    
    url = user_data[user_id]['url']
    
    try:
        await query.edit_message_text("⏳ Procesando...")
        
        if query.data.startswith("quality_"):
            quality = query.data.split("_")[1]
            format_map = {'720': 'best[height<=720]', '480': 'best[height<=480]'}
            ydl_opts = {
                'format': format_map.get(quality, 'best[height<=720]'),
                'outtmpl': '/tmp/%(title)s.%(ext)s',
            }
        else:  # audio_mp3
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': '/tmp/%(title)s.%(ext)s',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                }],
            }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            if query.data == "audio_mp3":
                file_path = file_path.replace('.webm', '.mp3').replace('.m4a', '.mp3')
        
        # Enviar archivo
        if query.data == "audio_mp3":
            with open(file_path, 'rb') as f:
                await query.message.reply_audio(audio=f, title=info['title'][:30])
        else:
            with open(file_path, 'rb') as f:
                await query.message.reply_video(video=f, caption=info['title'])
        
        # Limpiar
        if user_id in user_data:
            del user_data[user_id]
            
    except Exception as e:
        logger.error(f"Error descarga: {e}")
        await query.edit_message_text(f"❌ Error: {str(e)}")

def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_url))
    application.add_handler(CallbackQueryHandler(handle_selection))
    
    logger.info("🤖 Bot iniciado en Render...")
    application.run_polling()

if __name__ == "__main__":
    main()

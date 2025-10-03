import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import yt_dlp
import asyncio

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Token desde variables de entorno
TOKEN = os.environ.get('BOT_TOKEN')

# Diccionario para almacenar info temporal de usuarios
user_data = {}

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 **Bot Descargador Avanzado**\n\n"
        "✨ **Características:**\n"
        "• ✅ Descarga videos en diferentes calidades\n"
        "• 🎵 Extrae audio en formato MP3\n"
        "• 🚀 Soporte para YouTube, TikTok, Instagram, etc.\n\n"
        "📥 **Envía el enlace del video para comenzar**"
    )

# Procesar enlace y mostrar opciones
async def process_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    user_id = update.message.from_user.id
    
    try:
        # Verificar si es un enlace válido
        if not any(domain in url for domain in ['youtube', 'youtu.be', 'tiktok', 'instagram', 'twitter', 'x.com']):
            await update.message.reply_text("❌ Enlace no soportado. Solo YouTube, TikTok, Instagram, Twitter.")
            return

        processing_msg = await update.message.reply_text("🔍 Analizando video...")
        
        # Obtener información del video
        ydl_info = yt_dlp.YoutubeDL({'quiet': True})
        info = ydl_info.extract_info(url, download=False)
        
        # Guardar info temporalmente
        user_data[user_id] = {
            'url': url,
            'title': info.get('title', 'Video'),
            'duration': info.get('duration', 0)
        }
        
        await processing_msg.delete()
        
        # Crear teclado de opciones
        keyboard = [
            [InlineKeyboardButton("🎥 Alta Calidad (720p)", callback_data="quality_720")],
            [InlineKeyboardButton("🎥 Media Calidad (480p)", callback_data="quality_480")],
            [InlineKeyboardButton("🎥 Baja Calidad (360p)", callback_data="quality_360")],
            [InlineKeyboardButton("🎵 Audio MP3 (Calidad Alta)", callback_data="audio_mp3")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Mostrar información del video y opciones
        duration = f"{info['duration']//60}:{info['duration']%60:02d}" if info.get('duration') else "Desconocida"
        
        await update.message.reply_text(
            f"🎬 **{info['title']}**\n"
            f"⏱ Duración: {duration}\n"
            f"👤 Canal: {info.get('uploader', 'N/A')}\n\n"
            f"📥 **Selecciona el formato deseado:**",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Error analizando video: {e}")
        await update.message.reply_text("❌ Error al analizar el video. Verifica el enlace.")

# Manejar selecciones del usuario
async def handle_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "cancel":
        await query.edit_message_text("❌ Descarga cancelada.")
        if user_id in user_data:
            del user_data[user_id]
        return
    
    if user_id not in user_data:
        await query.edit_message_text("❌ Sesión expirada. Envía el enlace nuevamente.")
        return
    
    url = user_data[user_id]['url']
    title = user_data[user_id]['title']
    
    try:
        await query.edit_message_text("⏳ Procesando tu solicitud...")
        
        if data.startswith("quality_"):
            # Descargar video
            quality = data.split("_")[1]
            await download_video(query, url, title, quality)
        
        elif data == "audio_mp3":
            # Descargar audio
            await download_audio(query, url, title)
        
        # Limpiar datos temporales
        if user_id in user_data:
            del user_data[user_id]
            
    except Exception as e:
        logger.error(f"Error en descarga: {e}")
        await query.edit_message_text(f"❌ Error durante la descarga: {str(e)}")

# Descargar video con calidad específica
async def download_video(query, url, title, quality):
    try:
        quality_map = {
            '720': 'best[height<=720]',
            '480': 'best[height<=480]', 
            '360': 'best[height<=360]'
        }
        
        ydl_opts = {
            'format': quality_map[quality],
            'outtmpl': '/tmp/%(title)s.%(ext)s',
            'writethumbnail': True,
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }]
        }
        
        processing_msg = await query.message.reply_text("📥 Descargando video...")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_path = ydl.prepare_filename(info)
        
        # Enviar video
        with open(video_path, 'rb') as video_file:
            await query.message.reply_video(
                video=video_file,
                caption=f"🎥 **{title}**\n"
                       f"📊 Calidad: {quality}p\n"
                       f"✅ Descarga completada!",
                supports_streaming=True
            )
        
        await processing_msg.delete()
        
        # Limpiar archivo temporal
        if os.path.exists(video_path):
            os.remove(video_path)
            
    except Exception as e:
        raise e

# Descargar audio MP3
async def download_audio(query, url, title):
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': '/tmp/%(title)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'writethumbnail': True,
            'postprocessor_args': [
                '-strict', '-2'
            ],
            'prefer_ffmpeg': True
        }
        
        processing_msg = await query.message.reply_text("🎵 Extrayendo audio...")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            audio_path = ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3')
        
        # Enviar audio
        with open(audio_path, 'rb') as audio_file:
            await query.message.reply_audio(
                audio=audio_file,
                caption=f"🎵 **{title}**\n"
                       f"🎧 Formato: MP3 (192kbps)\n"
                       f"✅ Audio extraído!",
                title=title[:30] + "..." if len(title) > 30 else title
            )
        
        await processing_msg.delete()
        
        # Limpiar archivo temporal
        if os.path.exists(audio_path):
            os.remove(audio_path)
            
    except Exception as e:
        raise e

# Comando de ayuda
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 **Guía de uso:**\n\n"
        "1. Envía el enlace del video\n"
        "2. Selecciona la calidad o formato\n"
        "3. Espera a que se procese\n\n"
        "✨ **Formatos soportados:**\n"
        "• 🎥 Video: 720p, 480p, 360p\n"
        "• 🎵 Audio: MP3 alta calidad\n\n"
        "🌐 **Plataformas:** YouTube, TikTok, Instagram, Twitter, etc.\n\n"
        "⏰ Los videos muy largos pueden tardar más."
    )

# Manejar errores
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")
    if update and update.message:
        await update.message.reply_text("❌ Ocurrió un error inesperado. Intenta nuevamente.")

# Función principal
def main():
    # Crear aplicación
    application = Application.builder().token(TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_url))
    application.add_handler(CallbackQueryHandler(handle_selection))
    application.add_error_handler(error_handler)
    
    # Iniciar bot con polling
    print("🤖 Bot avanzado iniciado...")
    application.run_polling()

if __name__ == "__main__":
    main()
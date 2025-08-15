import logging
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler as TelegramCommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)
import asyncio

from config import TELEGRAM_BOT_TOKEN, SUPPORTED_AUDIO_FORMATS
from database import DatabaseManager
from voice_service import VoiceService
from conversation import ConversationManager
from commands import CommandHandler

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

db = DatabaseManager()
voice_service = VoiceService()
conversation_manager = ConversationManager(db)
command_handler = CommandHandler(db, conversation_manager)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    response = await command_handler.handle_command(user.id, 'start')
    await update.message.reply_text(response)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    response = await command_handler.handle_command(user_id, 'help')
    await update.message.reply_text(response, parse_mode='Markdown')

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    response = await command_handler.handle_command(user_id, 'clear')
    await update.message.reply_text(response)

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = ' '.join(context.args) if context.args else None
    response = await command_handler.handle_command(user_id, 'search', query)
    await update.message.reply_text(response)

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    response = await command_handler.handle_command(user_id, 'history')
    await update.message.reply_text(response, parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    response = await command_handler.handle_command(user_id, 'stats')
    await update.message.reply_text(response)

async def rec_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    response = await command_handler.handle_command(user_id, 'rec')
    await update.message.reply_text(response, parse_mode='Markdown')

async def agent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    response = await command_handler.handle_command(user_id, 'agent')
    await update.message.reply_text(response, parse_mode='Markdown')

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    # Send typing indicator instead of text message
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    
    try:
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        
        file_name = f"{user.id}_{update.message.message_id}.ogg"
        
        transcribed_text = await voice_service.download_and_transcribe(
            file, 
            file_name
        )
        
        if transcribed_text:
            # Get user mode
            user_mode = db.get_user_mode(user.id)
            
            if user_mode == 'rec':
                # Recognition mode - only send transcribed text
                await update.message.reply_text(transcribed_text)
            else:
                # Agent mode - send transcribed text and AI response
                await update.message.reply_text(f"📝 Transcribed: {transcribed_text}")
                
                db.add_message(user.id, "user", transcribed_text, "voice")
                
                command, args = command_handler.parse_command(transcribed_text)
                
                if command:
                    response = await command_handler.handle_command(user.id, command, args)
                else:
                    # Send typing indicator while generating response
                    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                    response = await conversation_manager.get_response(user.id, transcribed_text)
                
                await update.message.reply_text(response, parse_mode='Markdown')
        else:
            await update.message.reply_text(
                "❌ Sorry, I couldn't transcribe your voice message. Please try again."
            )
    
    except Exception as e:
        logger.error(f"Error handling voice message: {str(e)}")
        await update.message.reply_text(
            "❌ An error occurred processing your voice message. Please try again."
        )

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    # Send typing indicator instead of text message
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    
    try:
        audio = update.message.audio
        file_name = audio.file_name or f"{user.id}_{update.message.message_id}.mp3"
        
        if not any(file_name.lower().endswith(fmt) for fmt in SUPPORTED_AUDIO_FORMATS):
            await update.message.reply_text(
                f"❌ Unsupported audio format. Supported formats: {', '.join(SUPPORTED_AUDIO_FORMATS)}"
            )
            return
        
        file = await context.bot.get_file(audio.file_id)
        
        transcribed_text = await voice_service.download_and_transcribe(
            file,
            file_name
        )
        
        if transcribed_text:
            # Get user mode
            user_mode = db.get_user_mode(user.id)
            
            if user_mode == 'rec':
                # Recognition mode - only send transcribed text
                await update.message.reply_text(transcribed_text)
            else:
                # Agent mode - send transcribed text and AI response
                await update.message.reply_text(f"📝 Transcribed: {transcribed_text}")
                
                db.add_message(user.id, "user", transcribed_text, "voice")
                
                command, args = command_handler.parse_command(transcribed_text)
                
                if command:
                    response = await command_handler.handle_command(user.id, command, args)
                else:
                    # Send typing indicator while generating response
                    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                    response = await conversation_manager.get_response(user.id, transcribed_text)
                
                await update.message.reply_text(response, parse_mode='Markdown')
        else:
            await update.message.reply_text(
                "❌ Sorry, I couldn't transcribe your audio file. Please try again."
            )
    
    except Exception as e:
        logger.error(f"Error handling audio file: {str(e)}")
        await update.message.reply_text(
            "❌ An error occurred processing your audio file. Please try again."
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    text = update.message.text
    
    command, args = command_handler.parse_command(text)
    
    if command:
        response = await command_handler.handle_command(user.id, command, args)
    else:
        # Get user mode
        user_mode = db.get_user_mode(user.id)
        
        if user_mode == 'agent':
            # Agent mode - process text with AI
            search_keywords = ['search for', 'look up', 'find information about', 'google']
            needs_search = any(keyword in text.lower() for keyword in search_keywords)
            
            # Send typing indicator while generating response
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
            
            if needs_search:
                response = await conversation_manager.search_and_respond(user.id, text)
            else:
                response = await conversation_manager.get_response(user.id, text)
        else:
            # Recognition mode - inform user that text processing needs agent mode
            response = (
                "🎤 I'm currently in recognition-only mode.\n"
                "Use /agent to enable AI responses for text messages,\n"
                "or send me a voice message to transcribe."
            )
    
    await update.message.reply_text(response, parse_mode='Markdown')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An error occurred. Please try again later."
        )

def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(TelegramCommandHandler("start", start))
    application.add_handler(TelegramCommandHandler("help", help_command))
    application.add_handler(TelegramCommandHandler("clear", clear_command))
    application.add_handler(TelegramCommandHandler("search", search_command))
    application.add_handler(TelegramCommandHandler("history", history_command))
    application.add_handler(TelegramCommandHandler("stats", stats_command))
    application.add_handler(TelegramCommandHandler("rec", rec_command))
    application.add_handler(TelegramCommandHandler("agent", agent_command))
    
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.AUDIO, handle_audio))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    application.add_error_handler(error_handler)
    
    logger.info("Bot is starting...")
    
    try:
        voice_service.cleanup_temp_files()
    except Exception as e:
        logger.warning(f"Could not clean temp files on startup: {e}")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
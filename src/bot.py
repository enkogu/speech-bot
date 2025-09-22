import logging
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatAction
import asyncio

from config import TELEGRAM_BOT_TOKEN, API_ID, API_HASH, SUPPORTED_AUDIO_FORMATS
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

# Initialize Pyrogram client
app = Client(
    "speech_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=TELEGRAM_BOT_TOKEN
)

async def send_split_messages(message: Message, text: str, parse_mode: str = None):
    """Send text in chunks if it exceeds Telegram's message limit."""
    chunks = voice_service.split_text(text)
    for i, chunk in enumerate(chunks):
        if len(chunks) > 1:
            chunk_text = f"[Part {i+1}/{len(chunks)}]\n{chunk}"
        else:
            chunk_text = chunk
        await message.reply_text(chunk_text)

@app.on_message(filters.command("start") & filters.private)
async def start(client: Client, message: Message):
    user = message.from_user
    db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )

    response = await command_handler.handle_command(user.id, 'start')
    await message.reply_text(response)

@app.on_message(filters.command("help") & filters.private)
async def help_command(client: Client, message: Message):
    user_id = message.from_user.id
    response = await command_handler.handle_command(user_id, 'help')
    await message.reply_text(response)

@app.on_message(filters.command("clear") & filters.private)
async def clear_command(client: Client, message: Message):
    user_id = message.from_user.id
    response = await command_handler.handle_command(user_id, 'clear')
    await message.reply_text(response)

@app.on_message(filters.command("search") & filters.private)
async def search_command(client: Client, message: Message):
    user_id = message.from_user.id
    # Get the search query from the message text
    text_parts = message.text.split(maxsplit=1)
    query = text_parts[1] if len(text_parts) > 1 else None
    response = await command_handler.handle_command(user_id, 'search', query)
    await message.reply_text(response)

@app.on_message(filters.command("history") & filters.private)
async def history_command(client: Client, message: Message):
    user_id = message.from_user.id
    response = await command_handler.handle_command(user_id, 'history')
    await message.reply_text(response)

@app.on_message(filters.command("stats") & filters.private)
async def stats_command(client: Client, message: Message):
    user_id = message.from_user.id
    response = await command_handler.handle_command(user_id, 'stats')
    await message.reply_text(response)

@app.on_message(filters.command("rec") & filters.private)
async def rec_command(client: Client, message: Message):
    user_id = message.from_user.id
    response = await command_handler.handle_command(user_id, 'rec')
    await message.reply_text(response)

@app.on_message(filters.command("agent") & filters.private)
async def agent_command(client: Client, message: Message):
    user_id = message.from_user.id
    response = await command_handler.handle_command(user_id, 'agent')
    await message.reply_text(response)

@app.on_message(filters.voice & filters.private)
async def handle_voice(client: Client, message: Message):
    user = message.from_user
    db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )

    # Send typing indicator
    await client.send_chat_action(message.chat.id, ChatAction.TYPING)

    try:
        voice = message.voice

        # Log file size
        file_size_mb = voice.file_size / (1024 * 1024) if voice.file_size else 0
        logger.info(f"Receiving voice message: {file_size_mb:.2f}MB")

        # Download the voice message - Pyrogram handles any size up to 2GB
        file_name = f"{user.id}_{message.id}.ogg"
        file_path = await message.download(file_name=f"{voice_service.TEMP_DIR}/{file_name}")

        # Transcribe the audio
        transcribed_text = await voice_service.transcribe_audio(file_path)

        if transcribed_text:
            # Get user mode
            user_mode = db.get_user_mode(user.id)

            if user_mode == 'rec':
                # Recognition mode - only send transcribed text
                await send_split_messages(message, transcribed_text)
            else:
                # Agent mode - send transcribed text and AI response
                await send_split_messages(message, f"📝 Transcribed: {transcribed_text}")

                db.add_message(user.id, "user", transcribed_text, "voice")

                command, args = command_handler.parse_command(transcribed_text)

                if command:
                    response = await command_handler.handle_command(user.id, command, args)
                else:
                    # Send typing indicator while generating response
                    await client.send_chat_action(message.chat.id, ChatAction.TYPING)
                    response = await conversation_manager.get_response(user.id, transcribed_text)

                await message.reply_text(response)
        else:
            # Silently log the failure
            logger.warning("Transcription failed, no text returned")

        # Clean up the downloaded file
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.warning(f"Could not delete temp file {file_path}: {e}")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error handling voice message: {error_msg}")

@app.on_message(filters.audio & filters.private)
async def handle_audio(client: Client, message: Message):
    user = message.from_user
    db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )

    # Send typing indicator
    await client.send_chat_action(message.chat.id, ChatAction.TYPING)

    try:
        audio = message.audio
        file_name = audio.file_name if audio.file_name else f"{user.id}_{message.id}.mp3"

        # Check if format is supported
        if not any(file_name.lower().endswith(fmt) for fmt in SUPPORTED_AUDIO_FORMATS):
            logger.warning(f"Unsupported audio format: {file_name}")
            return

        # Log file size
        file_size_mb = audio.file_size / (1024 * 1024) if audio.file_size else 0
        logger.info(f"Receiving audio file: {file_size_mb:.2f}MB")

        # Download the audio file - Pyrogram handles any size up to 2GB
        file_path = await message.download(file_name=f"{voice_service.TEMP_DIR}/{file_name}")

        # Transcribe the audio
        transcribed_text = await voice_service.transcribe_audio(file_path)

        if transcribed_text:
            # Get user mode
            user_mode = db.get_user_mode(user.id)

            if user_mode == 'rec':
                # Recognition mode - only send transcribed text
                await send_split_messages(message, transcribed_text)
            else:
                # Agent mode - send transcribed text and AI response
                await send_split_messages(message, f"📝 Transcribed: {transcribed_text}")

                db.add_message(user.id, "user", transcribed_text, "voice")

                command, args = command_handler.parse_command(transcribed_text)

                if command:
                    response = await command_handler.handle_command(user.id, command, args)
                else:
                    # Send typing indicator while generating response
                    await client.send_chat_action(message.chat.id, ChatAction.TYPING)
                    response = await conversation_manager.get_response(user.id, transcribed_text)

                await message.reply_text(response)
        else:
            # Silently log the failure
            logger.warning("Audio transcription failed, no text returned")

        # Clean up the downloaded file
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.warning(f"Could not delete temp file {file_path}: {e}")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error handling audio file: {error_msg}")

@app.on_message(filters.text & filters.private & ~filters.command(["start", "help", "clear", "search", "history", "stats", "rec", "agent"]))
async def handle_text(client: Client, message: Message):
    user = message.from_user
    db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )

    text = message.text

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
            await client.send_chat_action(message.chat.id, ChatAction.TYPING)

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

    await message.reply_text(response)

def main():
    logger.info("Bot is starting...")

    # Clean up temp files on startup
    try:
        voice_service.cleanup_temp_files()
    except Exception as e:
        logger.warning(f"Could not clean temp files on startup: {e}")

    # Run the bot
    app.run()

if __name__ == '__main__':
    main()
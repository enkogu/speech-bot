import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")

DATABASE_PATH = "data/bot.db"
TEMP_DIR = "temp"

WHISPER_MODEL = "whisper-large-v3-turbo"
CONVERSATION_MODEL = "openai/gpt-oss-120b"

MAX_CONTEXT_MESSAGES = 10
MAX_AUDIO_SIZE_MB = 25
SUPPORTED_AUDIO_FORMATS = [".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm", ".ogg", ".flac"]

COMMANDS = {
    "help": "Show available commands",
    "clear": "Clear your conversation history",
    "search": "Search the web for information",
    "history": "Show recent conversation",
    "stats": "Show your usage statistics",
    "start": "Start the bot",
    "rec": "Switch to recognition-only mode (default)",
    "agent": "Switch to agent mode (AI responses)"
}

BOT_MODES = {
    "rec": "Recognition mode - only transcribe voice messages",
    "agent": "Agent mode - transcribe and respond with AI"
}

DEFAULT_MODE = "rec"
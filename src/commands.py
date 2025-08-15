import re
from typing import Optional, Tuple
from database import DatabaseManager
from conversation import ConversationManager
from config import COMMANDS, BOT_MODES
import logging

logger = logging.getLogger(__name__)

class CommandHandler:
    def __init__(self, db: DatabaseManager, conversation: ConversationManager):
        self.db = db
        self.conversation = conversation
    
    def parse_command(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        text = text.strip()
        
        if text.startswith('/'):
            parts = text.split(maxsplit=1)
            command = parts[0][1:].lower()
            args = parts[1] if len(parts) > 1 else None
            return command, args
        
        text_lower = text.lower()
        
        command_patterns = {
            'help': r'^(help|what can you do|show commands?|how to use)',
            'clear': r'^(clear|reset|start over|new conversation)',
            'search': r'^(search|find|look up|google)',
            'history': r'^(show history|recent messages|what did we talk)',
            'stats': r'^(stats|statistics|my usage)',
        }
        
        for cmd, pattern in command_patterns.items():
            if re.match(pattern, text_lower):
                remaining_text = re.sub(pattern, '', text_lower).strip()
                return cmd, remaining_text if remaining_text else None
        
        return None, None
    
    async def handle_command(self, user_id: int, command: str, args: str = None) -> str:
        self.db.add_command(user_id, command, args)
        
        if command == 'start':
            return await self.handle_start(user_id)
        elif command == 'help':
            return await self.handle_help(user_id)
        elif command == 'clear':
            return await self.handle_clear(user_id)
        elif command == 'search':
            return await self.handle_search(user_id, args)
        elif command == 'history':
            return await self.handle_history(user_id)
        elif command == 'stats':
            return await self.handle_stats(user_id)
        elif command == 'rec':
            return await self.handle_rec_mode(user_id)
        elif command == 'agent':
            return await self.handle_agent_mode(user_id)
        else:
            return f"Unknown command: {command}. Type /help for available commands."
    
    async def handle_start(self, user_id: int) -> str:
        current_mode = self.db.get_user_mode(user_id)
        mode_desc = BOT_MODES.get(current_mode, BOT_MODES['rec'])
        
        return (
            "🤖 Welcome to the Voice Recognition Bot!\n\n"
            "I can:\n"
            "• Understand voice messages\n"
            "• Have conversations\n"
            "• Search the web for information\n"
            "• Remember our conversation history\n\n"
            f"Current mode: **{current_mode.upper()}** - {mode_desc}\n\n"
            "Send me a voice message or text, or use /help to see commands."
        )
    
    async def handle_help(self, user_id: int) -> str:
        current_mode = self.db.get_user_mode(user_id)
        
        help_text = "📋 **Available Commands:**\n\n"
        for cmd, description in COMMANDS.items():
            help_text += f"/{cmd} - {description}\n"
        
        help_text += (
            f"\n🔧 **Current Mode:** {current_mode.upper()}\n"
            "\n💡 **Tips:**\n"
            "• Send voice messages for speech-to-text\n"
            "• I understand natural language commands\n"
            "• Ask me to search for current information\n"
            "• Your conversation history is saved per user"
        )
        
        return help_text
    
    async def handle_clear(self, user_id: int) -> str:
        self.conversation.clear_context(user_id)
        return "✨ Conversation history cleared. Starting fresh!"
    
    async def handle_search(self, user_id: int, query: str) -> str:
        if not query:
            return "Please provide a search query. Example: /search latest AI news"
        
        return await self.conversation.search_and_respond(user_id, query)
    
    async def handle_history(self, user_id: int) -> str:
        history = self.db.get_conversation_history(user_id, limit=10)
        
        if not history:
            return "No conversation history found."
        
        response = "📜 **Recent Conversation:**\n\n"
        for msg in history[-5:]:
            role_emoji = "👤" if msg['role'] == 'user' else "🤖"
            content = msg['content'][:100] + "..." if len(msg['content']) > 100 else msg['content']
            response += f"{role_emoji} {content}\n\n"
        
        return response
    
    async def handle_stats(self, user_id: int) -> str:
        stats = self.db.get_user_stats(user_id)
        
        response = "📊 **Your Statistics:**\n\n"
        response += f"💬 Total messages: {stats['message_count']}\n"
        response += f"🎤 Voice messages: {stats['voice_count']}\n"
        response += f"⚡ Commands used: {stats['command_count']}\n"
        
        if stats['member_since']:
            response += f"📅 Member since: {stats['member_since']}\n"
        
        current_mode = self.db.get_user_mode(user_id)
        response += f"\n🔧 Current mode: {current_mode.upper()}"
        
        return response
    
    async def handle_rec_mode(self, user_id: int) -> str:
        self.db.set_user_mode(user_id, 'rec')
        return (
            "🎤 **Recognition Mode Activated**\n\n"
            "I will now only transcribe voice messages without AI responses.\n"
            "Use /agent to switch back to AI response mode."
        )
    
    async def handle_agent_mode(self, user_id: int) -> str:
        self.db.set_user_mode(user_id, 'agent')
        return (
            "🤖 **Agent Mode Activated**\n\n"
            "I will now transcribe voice messages and provide AI responses.\n"
            "Use /rec to switch back to recognition-only mode."
        )
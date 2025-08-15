from openai import OpenAI
from typing import List, Dict, Optional
import logging
from config import GROQ_API_KEY, CONVERSATION_MODEL, MAX_CONTEXT_MESSAGES
from database import DatabaseManager

logger = logging.getLogger(__name__)

class ConversationManager:
    def __init__(self, db: DatabaseManager):
        self.client = OpenAI(
            api_key=GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1"
        )
        self.db = db
    
    async def get_response(self, user_id: int, message: str, 
                          use_browser_search: bool = False) -> str:
        try:
            self.db.add_message(user_id, "user", message)
            
            conversation_history = self.db.get_conversation_history(
                user_id, 
                limit=MAX_CONTEXT_MESSAGES
            )
            
            messages = []
            for msg in conversation_history:
                if msg['role'] in ['user', 'assistant']:
                    messages.append({
                        "role": msg['role'],
                        "content": msg['content']
                    })
            
            if not messages or messages[-1]['role'] != 'user':
                messages.append({"role": "user", "content": message})
            
            system_message = {
                "role": "system",
                "content": (
                    "You are a helpful AI assistant. Respond concisely and clearly. "
                    "If asked about recent events or needing current information, "
                    "indicate that you'll search for it."
                )
            }
            messages.insert(0, system_message)
            
            kwargs = {
                "model": CONVERSATION_MODEL,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 1000
            }
            
            if use_browser_search:
                kwargs["tool_choice"] = "required"
                kwargs["tools"] = [{"type": "browser_search"}]
            
            response = self.client.chat.completions.create(**kwargs)
            
            assistant_message = response.choices[0].message.content
            
            self.db.add_message(user_id, "assistant", assistant_message)
            
            return assistant_message
        
        except Exception as e:
            logger.error(f"Error getting response: {str(e)}")
            return "I apologize, but I encountered an error processing your request. Please try again."
    
    async def search_and_respond(self, user_id: int, query: str) -> str:
        try:
            self.db.add_message(user_id, "user", f"Search: {query}")
            
            response = self.client.chat.completions.create(
                model=CONVERSATION_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant with web search capabilities."
                    },
                    {
                        "role": "user",
                        "content": query
                    }
                ],
                temperature=0.5,
                max_tokens=1500,
                tool_choice="required",
                tools=[{"type": "browser_search"}]
            )
            
            result = response.choices[0].message.content
            
            self.db.add_message(user_id, "assistant", result)
            
            return result
        
        except Exception as e:
            logger.error(f"Error in search: {str(e)}")
            return "I couldn't complete the search. Please try again."
    
    def clear_context(self, user_id: int):
        self.db.clear_conversation(user_id)
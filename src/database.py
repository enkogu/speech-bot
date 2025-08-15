import sqlite3
from datetime import datetime
from typing import List, Tuple, Optional
import os
from config import DATABASE_PATH

class DatabaseManager:
    def __init__(self):
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        self.conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
    
    def _create_tables(self):
        cursor = self.conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                mode TEXT DEFAULT 'rec',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                message_role TEXT NOT NULL,
                message_content TEXT NOT NULL,
                message_type TEXT DEFAULT 'text',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS command_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                command TEXT NOT NULL,
                response TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_conversations_user_id 
            ON conversations(user_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_conversations_timestamp 
            ON conversations(timestamp)
        ''')
        
        # Add mode column to existing users table if it doesn't exist
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'mode' not in columns:
            cursor.execute('''
                ALTER TABLE users ADD COLUMN mode TEXT DEFAULT 'rec'
            ''')
        
        self.conn.commit()
    
    def add_user(self, user_id: int, username: str = None, 
                 first_name: str = None, last_name: str = None):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name))
        self.conn.commit()
    
    def add_message(self, user_id: int, role: str, content: str, 
                   message_type: str = 'text'):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO conversations (user_id, message_role, message_content, message_type)
            VALUES (?, ?, ?, ?)
        ''', (user_id, role, content, message_type))
        self.conn.commit()
    
    def get_conversation_history(self, user_id: int, limit: int = 10) -> List[dict]:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT message_role, message_content, message_type, timestamp
            FROM conversations
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (user_id, limit))
        
        rows = cursor.fetchall()
        messages = []
        for row in reversed(rows):
            messages.append({
                'role': row['message_role'],
                'content': row['message_content'],
                'type': row['message_type'],
                'timestamp': row['timestamp']
            })
        return messages
    
    def clear_conversation(self, user_id: int):
        cursor = self.conn.cursor()
        cursor.execute('''
            DELETE FROM conversations WHERE user_id = ?
        ''', (user_id,))
        self.conn.commit()
    
    def add_command(self, user_id: int, command: str, response: str = None):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO command_history (user_id, command, response)
            VALUES (?, ?, ?)
        ''', (user_id, command, response))
        self.conn.commit()
    
    def get_user_stats(self, user_id: int) -> dict:
        cursor = self.conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) as message_count
            FROM conversations
            WHERE user_id = ?
        ''', (user_id,))
        message_count = cursor.fetchone()['message_count']
        
        cursor.execute('''
            SELECT COUNT(*) as command_count
            FROM command_history
            WHERE user_id = ?
        ''', (user_id,))
        command_count = cursor.fetchone()['command_count']
        
        cursor.execute('''
            SELECT created_at
            FROM users
            WHERE user_id = ?
        ''', (user_id,))
        user_data = cursor.fetchone()
        
        cursor.execute('''
            SELECT COUNT(*) as voice_count
            FROM conversations
            WHERE user_id = ? AND message_type = 'voice'
        ''', (user_id,))
        voice_count = cursor.fetchone()['voice_count']
        
        return {
            'message_count': message_count,
            'command_count': command_count,
            'voice_count': voice_count,
            'member_since': user_data['created_at'] if user_data else None
        }
    
    def get_user_mode(self, user_id: int) -> str:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT mode FROM users WHERE user_id = ?
        ''', (user_id,))
        result = cursor.fetchone()
        return result['mode'] if result else 'rec'
    
    def set_user_mode(self, user_id: int, mode: str):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE users SET mode = ? WHERE user_id = ?
        ''', (mode, user_id))
        self.conn.commit()
    
    def close(self):
        self.conn.close()
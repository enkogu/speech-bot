import os
import tempfile
from groq import Groq
from typing import Optional
import logging
from config import GROQ_API_KEY, WHISPER_MODEL, TEMP_DIR, MAX_AUDIO_SIZE_MB

logger = logging.getLogger(__name__)

class VoiceService:
    def __init__(self):
        self.client = Groq(api_key=GROQ_API_KEY)
        os.makedirs(TEMP_DIR, exist_ok=True)
    
    async def transcribe_audio(self, audio_file_path: str, language: str = None) -> Optional[str]:
        try:
            file_size_mb = os.path.getsize(audio_file_path) / (1024 * 1024)
            if file_size_mb > MAX_AUDIO_SIZE_MB:
                logger.error(f"Audio file too large: {file_size_mb:.2f}MB (max: {MAX_AUDIO_SIZE_MB}MB)")
                return None
            
            with open(audio_file_path, "rb") as audio_file:
                transcription = self.client.audio.transcriptions.create(
                    file=audio_file,
                    model=WHISPER_MODEL,
                    language=language,
                    temperature=0.0,
                    response_format="json"
                )
            
            return transcription.text
        
        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            return None
    
    async def download_and_transcribe(self, file, file_name: str, language: str = None) -> Optional[str]:
        temp_path = None
        try:
            temp_path = os.path.join(TEMP_DIR, f"{file_name}")
            
            await file.download_to_drive(temp_path)
            
            transcribed_text = await self.transcribe_audio(temp_path, language)
            
            return transcribed_text
        
        except Exception as e:
            logger.error(f"Error in download_and_transcribe: {str(e)}")
            return None
        
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as e:
                    logger.warning(f"Could not delete temp file {temp_path}: {str(e)}")
    
    def cleanup_temp_files(self):
        try:
            for filename in os.listdir(TEMP_DIR):
                file_path = os.path.join(TEMP_DIR, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    logger.info(f"Cleaned up temp file: {filename}")
        except Exception as e:
            logger.error(f"Error cleaning temp files: {str(e)}")
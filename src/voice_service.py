import os
import tempfile
from groq import Groq
from typing import Optional
import logging
from pydub import AudioSegment
import re
from config import GROQ_API_KEY, WHISPER_MODEL, TEMP_DIR, MAX_AUDIO_SIZE_MB

logger = logging.getLogger(__name__)

class VoiceService:
    def __init__(self):
        self.client = Groq(api_key=GROQ_API_KEY)
        os.makedirs(TEMP_DIR, exist_ok=True)
        # Text truncation settings
        self.max_text_length = 4000
    
    def preprocess_audio(self, input_path: str, output_path: str) -> bool:
        """Preprocess audio: 2x speed, reduced quality for smaller file size."""
        try:
            # Load audio file
            audio = AudioSegment.from_file(input_path)

            # Speed up audio by 2x (halve the duration)
            audio_fast = audio._spawn(audio.raw_data, overrides={
                "frame_rate": int(audio.frame_rate * 2.0)
            }).set_frame_rate(audio.frame_rate)

            # Reduce quality: lower bitrate and sample rate for smaller file size
            # Convert to mono, reduce sample rate to 16kHz (good for speech)
            audio_processed = audio_fast.set_channels(1).set_frame_rate(16000)

            # Export with lower bitrate (32k is sufficient for speech)
            audio_processed.export(
                output_path,
                format="mp3",
                bitrate="32k"
            )
            return True
        except Exception as e:
            logger.error(f"Error preprocessing audio: {str(e)}")
            return False

    def split_text(self, text: str) -> list:
        """Split text into chunks of max 4000 characters, preferably at sentence boundaries."""
        if len(text) <= self.max_text_length:
            return [text]

        chunks = []
        remaining_text = text

        while remaining_text:
            if len(remaining_text) <= self.max_text_length:
                chunks.append(remaining_text)
                break

            # Try to find a good breaking point near the limit
            chunk_text = remaining_text[:self.max_text_length]

            # Look for the last sentence ending (. ! ?)
            sentence_endings = ['.', '!', '?']
            last_sentence_end = -1

            for ending in sentence_endings:
                pos = chunk_text.rfind(ending)
                if pos > last_sentence_end:
                    last_sentence_end = pos

            # If we found a sentence ending in the latter half of the chunk, use it
            if last_sentence_end > self.max_text_length // 2:
                split_point = last_sentence_end + 1
            else:
                # Otherwise, try to break at a space to avoid cutting words
                last_space = chunk_text.rfind(' ')
                if last_space > self.max_text_length - 200:
                    split_point = last_space
                else:
                    # Fallback: just split at the limit
                    split_point = self.max_text_length

            chunks.append(remaining_text[:split_point].strip())
            remaining_text = remaining_text[split_point:].strip()

        return chunks

    async def transcribe_audio(self, audio_file_path: str, language: str = None) -> Optional[str]:
        processed_path = None
        try:
            # Preprocess audio file
            processed_path = os.path.join(TEMP_DIR, f"processed_{os.path.basename(audio_file_path)}")
            if not self.preprocess_audio(audio_file_path, processed_path):
                logger.warning("Audio preprocessing failed, using original file")
                processed_path = audio_file_path

            file_size_mb = os.path.getsize(processed_path) / (1024 * 1024)
            if file_size_mb > MAX_AUDIO_SIZE_MB:
                logger.error(f"Audio file too large: {file_size_mb:.2f}MB (max: {MAX_AUDIO_SIZE_MB}MB)")
                return None

            with open(processed_path, "rb") as audio_file:
                transcription = self.client.audio.transcriptions.create(
                    file=audio_file,
                    model=WHISPER_MODEL,
                    language=language,
                    temperature=0.0,
                    response_format="json"
                )

            # Return the full transcribed text (splitting will be handled in bot.py)
            return transcription.text
        
        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            return None
        finally:
            # Clean up processed file if it exists and is different from input
            if processed_path and processed_path != audio_file_path and os.path.exists(processed_path):
                try:
                    os.remove(processed_path)
                except Exception as e:
                    logger.warning(f"Could not delete processed file {processed_path}: {str(e)}")
    
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
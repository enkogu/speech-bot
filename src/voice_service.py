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
        self.TEMP_DIR = TEMP_DIR
        os.makedirs(TEMP_DIR, exist_ok=True)
        # Text truncation settings
        self.max_text_length = 4000
    
    def preprocess_audio(self, input_path: str, output_path: str, aggressive_compress: bool = False) -> bool:
        """Preprocess audio: speed up and reduce quality for smaller file size."""
        try:
            # Load audio file
            audio = AudioSegment.from_file(input_path)

            # Log original file info
            duration_seconds = len(audio) / 1000
            logger.info(f"Original audio: {duration_seconds:.1f}s, {audio.frame_rate}Hz, {audio.channels} channels")

            if aggressive_compress:
                # For very large files, use more aggressive compression
                # Speed up by 3x
                audio_fast = audio._spawn(audio.raw_data, overrides={
                    "frame_rate": int(audio.frame_rate * 3.0)
                }).set_frame_rate(audio.frame_rate)

                # Very low quality for maximum compression
                audio_processed = audio_fast.set_channels(1).set_frame_rate(8000)

                # Export with minimum bitrate
                audio_processed.export(
                    output_path,
                    format="mp3",
                    bitrate="16k"
                )
            else:
                # Normal compression - Speed up audio by 2x
                audio_fast = audio._spawn(audio.raw_data, overrides={
                    "frame_rate": int(audio.frame_rate * 2.0)
                }).set_frame_rate(audio.frame_rate)

                # Convert to mono, reduce sample rate to 16kHz (good for speech)
                audio_processed = audio_fast.set_channels(1).set_frame_rate(16000)

                # Export with lower bitrate (32k is sufficient for speech)
                audio_processed.export(
                    output_path,
                    format="mp3",
                    bitrate="32k"
                )

            # Log processed file size
            processed_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            logger.info(f"Processed audio: {processed_size_mb:.2f}MB")

            # If still too large, try even more aggressive compression
            if processed_size_mb > 18 and not aggressive_compress:
                logger.info(f"File still too large ({processed_size_mb:.2f}MB), applying aggressive compression...")
                return self.preprocess_audio(input_path, output_path, aggressive_compress=True)

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

    def split_audio_into_chunks(self, audio_path: str, chunk_duration_ms: int = 300000) -> list:
        """Split audio file into smaller chunks (default 5 minutes each)."""
        try:
            audio = AudioSegment.from_file(audio_path)
            chunks = []

            # Split audio into chunks
            for i in range(0, len(audio), chunk_duration_ms):
                chunk = audio[i:i + chunk_duration_ms]
                chunk_path = os.path.join(TEMP_DIR, f"chunk_{i//chunk_duration_ms}_{os.path.basename(audio_path)}")
                chunk.export(chunk_path, format="mp3")
                chunks.append(chunk_path)

            logger.info(f"Split audio into {len(chunks)} chunks")
            return chunks
        except Exception as e:
            logger.error(f"Error splitting audio: {str(e)}")
            return []

    async def transcribe_audio(self, audio_file_path: str, language: str = None) -> Optional[str]:
        processed_path = None
        chunk_files = []
        try:
            # Check original file size first
            original_size_mb = os.path.getsize(audio_file_path) / (1024 * 1024)
            logger.info(f"Original file size: {original_size_mb:.2f}MB")

            # Preprocess audio file
            processed_path = os.path.join(TEMP_DIR, f"processed_{os.path.basename(audio_file_path)}")
            aggressive = original_size_mb > 50  # Use aggressive compression for very large files
            if not self.preprocess_audio(audio_file_path, processed_path, aggressive_compress=aggressive):
                logger.warning("Audio preprocessing failed, using original file")
                processed_path = audio_file_path

            file_size_mb = os.path.getsize(processed_path) / (1024 * 1024)

            # For Groq API, we still need to respect the 25MB limit, so split if needed
            if file_size_mb > MAX_AUDIO_SIZE_MB:
                logger.info(f"Audio file is {file_size_mb:.2f}MB, splitting into chunks...")
                chunk_files = self.split_audio_into_chunks(processed_path)

                if not chunk_files:
                    logger.error(f"Failed to split large audio file")
                    return None

                # Transcribe each chunk and combine results
                transcriptions = []
                for i, chunk_path in enumerate(chunk_files):
                    logger.info(f"Transcribing chunk {i+1}/{len(chunk_files)}")

                    chunk_size_mb = os.path.getsize(chunk_path) / (1024 * 1024)
                    if chunk_size_mb > MAX_AUDIO_SIZE_MB:
                        logger.warning(f"Chunk {i+1} still too large ({chunk_size_mb:.2f}MB), skipping")
                        continue

                    with open(chunk_path, "rb") as audio_file:
                        transcription = self.client.audio.transcriptions.create(
                            file=audio_file,
                            model=WHISPER_MODEL,
                            language=language,
                            temperature=0.0,
                            response_format="json"
                        )
                        transcriptions.append(transcription.text)

                # Combine all transcriptions
                return " ".join(transcriptions) if transcriptions else None

            else:
                # File is small enough, transcribe normally
                with open(processed_path, "rb") as audio_file:
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
        finally:
            # Clean up chunk files
            for chunk_path in chunk_files:
                if os.path.exists(chunk_path):
                    try:
                        os.remove(chunk_path)
                    except Exception as e:
                        logger.warning(f"Could not delete chunk file {chunk_path}: {str(e)}")

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
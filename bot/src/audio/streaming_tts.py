import asyncio
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


class StreamingTTS:
    """Stream TTS audio chunks for lower latency."""
    
    def __init__(self, tts_engine):
        self.tts = tts_engine
    
    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Stream audio chunks as they're generated.
        Yields PCM chunks for immediate playback.
        """
        # Split text into sentences for streaming
        sentences = self._split_sentences(text)
        
        for sentence in sentences:
            if sentence.strip():
                pcm = await self.tts.synthesize(sentence)
                # Yield in small chunks for streaming
                chunk_size = 640  # 20ms at 16kHz
                for i in range(0, len(pcm), chunk_size):
                    chunk = pcm[i:i + chunk_size]
                    if len(chunk) < chunk_size:
                        chunk += b"\x00" * (chunk_size - len(chunk))
                    yield chunk
    
    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences for streaming."""
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s for s in sentences if s.strip()]

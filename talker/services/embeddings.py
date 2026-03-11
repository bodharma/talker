"""Embedding generation and markdown chunking for the RAG knowledge base."""

import re
from dataclasses import dataclass, field

from talker.config import Settings


@dataclass
class TextChunk:
    text: str
    heading: str = ""
    source_file: str = ""
    metadata: dict = field(default_factory=dict)


def chunk_markdown(
    text: str,
    max_size: int = 512,
    overlap: int = 64,
) -> list[TextChunk]:
    """Split markdown by headers, then by size if needed."""
    sections = re.split(r"^(#{1,3}\s+.+)$", text, flags=re.MULTILINE)
    chunks: list[TextChunk] = []
    current_heading = ""

    i = 0
    while i < len(sections):
        section = sections[i].strip()
        if not section:
            i += 1
            continue

        if re.match(r"^#{1,3}\s+", section):
            current_heading = re.sub(r"^#{1,3}\s+", "", section).strip()
            i += 1
            continue

        if len(section) <= max_size:
            chunks.append(TextChunk(text=section, heading=current_heading))
        else:
            paragraphs = section.split("\n\n")
            buffer = ""
            for para in paragraphs:
                # Split very long paragraphs by sentences
                if len(para) > max_size:
                    if buffer:
                        chunks.append(
                            TextChunk(text=buffer.strip(), heading=current_heading)
                        )
                        buffer = ""
                    # Try splitting by sentences first
                    parts = re.split(r"(?<=[.!?])\s+", para)
                    # Fall back to word-level splitting if no sentences
                    if len(parts) == 1 and len(parts[0]) > max_size:
                        words = para.split()
                        parts = []
                        word_buf = ""
                        for w in words:
                            if len(word_buf) + len(w) + 1 > max_size:
                                if word_buf:
                                    parts.append(word_buf)
                                word_buf = w
                            else:
                                word_buf = word_buf + " " + w if word_buf else w
                        if word_buf:
                            parts.append(word_buf)
                    sent_buf = ""
                    for part in parts:
                        if len(sent_buf) + len(part) + 1 > max_size:
                            if sent_buf:
                                chunks.append(
                                    TextChunk(
                                        text=sent_buf.strip(),
                                        heading=current_heading,
                                    )
                                )
                            sent_buf = part
                        else:
                            sent_buf = sent_buf + " " + part if sent_buf else part
                    if sent_buf:
                        buffer = sent_buf
                elif len(buffer) + len(para) + 2 > max_size:
                    if buffer:
                        chunks.append(
                            TextChunk(text=buffer.strip(), heading=current_heading)
                        )
                    buffer = para
                else:
                    buffer = buffer + "\n\n" + para if buffer else para
            if buffer:
                chunks.append(
                    TextChunk(text=buffer.strip(), heading=current_heading)
                )

        i += 1

    return chunks


class EmbeddingService:
    """Generates embeddings via OpenAI API or Ollama."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.provider = settings.embedding_provider

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if self.provider == "openai":
            return await self._embed_openai(texts)
        return await self._embed_ollama(texts)

    async def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        import openai

        client = openai.AsyncOpenAI(api_key=self.settings.openai_api_key)
        response = await client.embeddings.create(
            input=texts,
            model=self.settings.embedding_model,
        )
        return [item.embedding for item in response.data]

    async def _embed_ollama(self, texts: list[str]) -> list[list[float]]:
        import httpx

        embeddings = []
        async with httpx.AsyncClient() as client:
            for text in texts:
                response = await client.post(
                    f"{self.settings.ollama_base_url}/api/embeddings",
                    json={
                        "model": self.settings.ollama_embedding_model,
                        "prompt": text,
                    },
                )
                response.raise_for_status()
                embeddings.append(response.json()["embedding"])
        return embeddings

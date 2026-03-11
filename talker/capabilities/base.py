"""Base class for pluggable pipeline capabilities."""

from abc import ABC, abstractmethod
from typing import Any

import numpy as np


class BaseCapability(ABC):
    """A capability processes audio/text and provides context to the agent.

    Capabilities are NOT tools. They run automatically on every turn
    and inject enriched context. They may optionally expose tools
    for the LLM to query their accumulated results.
    """

    def __init__(self, room_name: str = "") -> None:
        self.room_name = room_name

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier, e.g. 'voice_analysis', 'sentiment'."""

    @abstractmethod
    async def process_audio(
        self,
        audio: np.ndarray,
        sample_rate: int,
        transcript: str | None = None,
    ) -> dict[str, Any]:
        """Process a single audio turn. Returns enrichment data.

        This runs on every voice turn BEFORE the LLM sees the transcript.
        The returned dict is merged into the agent's context.
        """

    def get_context_prompt(self, results: dict[str, Any]) -> str:
        """Format results into a string injected into the LLM context.

        Override this to control how the LLM sees your capability's output.
        """
        return ""

    def get_tools(self) -> list:
        """Return any @function_tool functions this capability exposes.

        These are added to the agent's tool list so the LLM can query
        accumulated results on demand.
        """
        return []

"""Pluggable capabilities for persona pipelines.

A capability is a processing module that hooks into the voice pipeline
to enrich the agent's context. Unlike tools (which the LLM calls on demand),
capabilities run automatically on every audio turn and inject their results
into the agent's context for the LLM to use.

Pattern:
    1. Create a capability class that extends BaseCapability
    2. Implement process_audio() and/or process_transcript()
    3. Optionally provide a tool via get_tools() for LLM to query results
    4. Register the capability in the persona's capabilities list
"""

from talker.capabilities.base import BaseCapability

__all__ = ["BaseCapability"]

import os
import uuid

import pytest

from glyph import AgentOptions
from glyph import AgentText
from glyph import GlyphClient


async def _stream_text(client: GlyphClient, prompt: str, session_id: str) -> str:
    chunks: list[str] = []
    async for event in client.query_streamed(prompt, session_id=session_id):
        if isinstance(event, AgentText):
            chunks.append(event.text)
    return "".join(chunks)


@pytest.mark.asyncio
async def test_session_remembers_within_session_id() -> None:
    options = AgentOptions(model=os.environ.get("GLYPH_MODEL"))
    session_a = str(uuid.uuid4())
    session_b = str(uuid.uuid4())

    async with GlyphClient(options) as client:
        await _stream_text(client, "Remember the secret word is teapot.", session_id=session_a)
        recalled = await _stream_text(
            client,
            "What is the secret word? Reply with that single word only.",
            session_id=session_a,
        )
        other = await _stream_text(
            client,
            "What is the secret word ?'.",
            session_id=session_b,
        )

    assert "teapot" in recalled.lower()
    assert "teapot" not in other.lower()

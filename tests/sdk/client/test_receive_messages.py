import os

import pytest

from glyph import AgentOptions
from glyph import AgentQueryCompleted
from glyph import AgentText
from glyph import GlyphClient


@pytest.mark.asyncio
async def test_receive_messages_two_turns() -> None:
    options = AgentOptions(model=os.environ.get("GLYPH_MODEL"))
    events = []

    async with GlyphClient(options) as client:
        await client.query("Say 'first turn done'.")
        await client.query("Say 'second turn done'.")
        completed_turns = 0
        async for event in client.receive_messages():
            events.append(event)
            if isinstance(event, AgentQueryCompleted):
                completed_turns += 1
                if completed_turns == 2:
                    break

    texts = [event.text for event in events if type(event) == AgentText]
    merged = "".join(texts).lower()
    assert "first turn done" in merged
    assert "second turn done" in merged
    assert events[-1].stop_reason == "completed" or events[-1].stop_reason == "end_turn"

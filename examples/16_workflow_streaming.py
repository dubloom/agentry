import asyncio
import os

from glyph import AgentOptions
from glyph import AgentQueryCompleted
from glyph import AgentText
from glyph import GlyphWorkflow
from glyph import step


class MyWorkflow(GlyphWorkflow):
    """LLM step with ``is_streaming=True`` uses ``query_streamed``; events arrive one by one."""

    options = AgentOptions(
        model=os.getenv("GLYPH_MODEL", "gpt-5.4-mini"),
        reasoning_effort="medium",
        allowed_tools=("Read", "Grep", "Glob"),
    )

    @step(
        prompt="What is this file about ?",
        is_streaming=True,
    )
    async def stream_response(self) -> None:
        # The first `yield` suspends until the run starts; each `asend` from the runtime
        # delivers the next `AgentEvent` (text chunks, then `AgentQueryCompleted`).
        event = None
        while not isinstance(event, AgentQueryCompleted):
            event = yield
            print(type(event))

        completion: AgentQueryCompleted = event
        print()
        print("Turn finished — error:" if completion.is_error else "Turn finished — ok:", end=" ")
        print(completion.message)


async def main() -> None:
    await MyWorkflow.run()


if __name__ == "__main__":
    asyncio.run(main())

import asyncio

from glyph import AgentOptions
from glyph import AgentQueryCompleted
from glyph import GlyphWorkflow
from glyph import step


class MyWorkflow(GlyphWorkflow):
    options = AgentOptions(model="gpt-5.4-nano")

    @step(prompt="Say a sentence")
    async def say_sentence(self) -> None:
        query: AgentQueryCompleted = yield
        print(query.message)

    @step(prompt="Repeat exactly what you just said", model="gpt-5.4-mini")
    async def finish(self) -> None:
        query: AgentQueryCompleted = yield
        print(query.message)



async def main() -> None:
    await MyWorkflow.run()


if __name__ == "__main__":
    asyncio.run(main())

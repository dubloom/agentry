import asyncio

from glyph import AgentOptions
from glyph import AgentQueryCompleted
from glyph import GlyphWorkflow
from glyph import step


class MyWorkflow(GlyphWorkflow):
    options = AgentOptions(model="gpt-5.4-nano")

    @step(prompt="Say a short sentence about {a}.")
    async def first_turn(self, topic: str) -> None:
        self.fill_prompt(a=topic)
        query: AgentQueryCompleted = yield
        print(query.message)


async def main() -> None:
    # Override class-level defaults and provide first-step input at run time.
    await MyWorkflow.run(
        options=AgentOptions(model="gpt-5.4-mini"),
        initial_input="sea turtles",
    )


if __name__ == "__main__":
    asyncio.run(main())

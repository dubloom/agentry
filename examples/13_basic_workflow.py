import asyncio
import os

from glyph import AgentOptions
from glyph import AgentQueryCompleted
from glyph import GlyphWorkflow
from glyph import step


class MyWorkflow(GlyphWorkflow):
    options = AgentOptions(model=os.getenv("GLYPH_MODEL", "gpt-4.1-mini"))

    @step
    async def fetch_variable(self):
        return ["rainy weather", "a walk in paris"]

    @step(prompt="Based on {variable_1}, and {variable_2}, write one short sentence.")
    async def call_llm(self, prev: tuple[str, str]) -> None:
        # Pre-processing: render the template just before the LLM call.
        self.fill_prompt(variable_1=prev[0], variable_2=prev[1])
        yield
        print("after agent run")

    @step
    async def finish(self, previous_step_result: AgentQueryCompleted) -> None:
        print(previous_step_result.message)



async def main() -> None:
    await MyWorkflow.run()


if __name__ == "__main__":
    asyncio.run(main())

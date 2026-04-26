from pathlib import Path

from glyph import AgentQueryCompleted


async def load_trip_context(previous_result=None):
    del previous_result
    return {
        "city": "Lisbon",
        "mood": "warm and nostalgic",
        "memory": "the yellow tram climbing the hill at sunset",
    }


async def save_postcard(previous_result: AgentQueryCompleted):
    output_path = Path(__file__).with_name("postcard.txt")
    output_path.write_text(previous_result.message, encoding="utf-8")
    return {"file_path": str(output_path)}

async def main(previous_result: AgentQueryCompleted):
    return await save_postcard(previous_result)


import os
from dotenv import load_dotenv
from typing import Dict, List
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser, OutputFixingParser

from schema import DayItinerary
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
llm = ChatOpenAI(openai_api_key=OPENAI_API_KEY, model_name="gpt-4-turbo", temperature=0.5)
parser = PydanticOutputParser(pydantic_object=DayItinerary)
fallback_parser = OutputFixingParser.from_llm(llm=llm, parser=parser)
# === Prompt Template ===
itinerary_prompt = PromptTemplate(
    template="""
You are a helpful travel planner. The user is visiting {destination} for {travel_days} days.

They have selected the following landmarks:
{selected_landmarks}

Please create a complete and realistic itinerary for each day.

You must:
- Start with the selected landmarks provided by the user
- Add 1–2 additional landmarks per day as needed to fill the time reasonably
- Use realistic average time spent at each landmark (e.g., 30 minutes at a viewpoint, 1-3 hours at a museum, 3-7 hours at a theme park) based on its type and size.
, and account for travel time between them
- If only one landmark is selected for a day, consider adding more popular landmarks to fill the full day unless it's a theme park or similar
- Add a lunch and dinner restaurant recommendation at appropriate times between landmarks. 
- Restaurants do not need to be near a landmark but should be realistically located along or between travel routes.
- Restaurants should appear as separate entries in the itinerary, clearly marked with their mealtime.


Also:
- Add 1-2 recommended nearby restaurants for lunch and dinner, or the restaurants on the travel route.

Traveler profile:
- with_kids: {with_kids}
- with_elderly: {with_elderly}

Instructions:
- Restaurants should be kid-friendly or elderly-accessible if needed according to Traveler Profile.
- Output must strictly follow the JSON schema below.

{format_instructions}
""",
    input_variables=["destination", "travel_days", "selected_landmarks", "with_kids", "with_elderly"],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)


# === Main function ===
def complete_itinerary_from_landmarks(
    destination: str,
    travel_days: int,
    with_kids: bool,
    with_elderly: bool,
    selected_landmarks: Dict[str, List[str]]
) -> Dict:

    chain = itinerary_prompt | llm | fallback_parser

    print("🧠 Generating enriched itinerary with descriptions and restaurants...")
    try:
        result = chain.invoke({
            "destination": destination,
            "travel_days": travel_days,
            "with_kids": with_kids,
            "with_elderly": with_elderly,
            "selected_landmarks": selected_landmarks
        })
        return result.root  # ✅ correct for RootModel in Pydantic v2
  # Return the parsed day-to-landmarks dict
    except Exception as e:
        print("❌ Parsing failed:", e)
        return {"error": "Failed to parse itinerary"}
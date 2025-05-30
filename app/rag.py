import os
import time
import json
from typing import Dict, Optional
from functools import lru_cache
from dotenv import load_dotenv
from pydantic import BaseModel
import re
from datetime import datetime

from openai import OpenAI
from pinecone import Pinecone

from langchain_openai import ChatOpenAI
from langchain.output_parsers import PydanticOutputParser, OutputFixingParser
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnableSequence

# --- Load environment ---
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = os.getenv("INDEX_NAME")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set")
if not PINECONE_API_KEY:
    raise ValueError("PINECONE_API_KEY environment variable is not set")
if not INDEX_NAME:
    raise ValueError("INDEX_NAME environment variable is not set")

# --- Clients ---
try:
    client = OpenAI(
        api_key=OPENAI_API_KEY,
        timeout=30.0,  # 30 second timeout
        max_retries=2  # Only retry twice
    )
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(INDEX_NAME)
    llm = ChatOpenAI(
        openai_api_key=OPENAI_API_KEY,
        model_name="gpt-4-turbo",
        temperature=0.5,
        request_timeout=30  # 30 second timeout
    )
    print("✅ Successfully initialized all API clients")
except Exception as e:
    print(f"❌ Error initializing API clients: {str(e)}")
    raise

# --- Embeddings & RAG ---
@lru_cache(maxsize=1000)
def cached_embedding_call(text: str):
    try:
        start_time = time.time()
        result = client.embeddings.create(
            model="text-embedding-ada-002",
            input=[text]
        )
        print(f"📊 Embedding generated in {time.time() - start_time:.2f}s")
        return tuple(result.data[0].embedding)
    except Exception as e:
        print(f"❌ Error generating embedding: {str(e)}")
        raise

def get_cached_embedding(text: str):
    return list(cached_embedding_call(text))

def normalize_destination(input_str: str) -> str:
    """
    Normalize destination to match Pinecone metadata format.
    Converts: "Dallas TX" or "dallas,tx" => "Dallas, TX"
    """
    if not input_str:
        return ""

    # Remove extra whitespace and fix common separators
    cleaned = input_str.strip().lower()
    cleaned = re.sub(r"[\s,]+", " ", cleaned)  # normalize whitespace and commas
    parts = cleaned.split()

    if len(parts) >= 2:
        city = " ".join(parts[:-1])
        state = parts[-1].upper()
        return f"{city.title()}, {state}"
    else:
        return input_str.title()

def retrieve_relevant_transcripts(query, destination=None, with_kids=None, with_elderly=None, top_k=10, token_limit=1500):
    try:
        start_time = time.time()
        query_embedding = get_cached_embedding(query)

        # === Build metadata filter ===
        filters = {}
        filters["destination"] = destination.lower()
        filters["with_kids"] = with_kids
        filters["with_elderly"] = with_elderly

        print(f"🔍 Querying Pinecone with filters: {filters}")
        search_results = index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True,
            filter=filters  # Use Pinecone filtering!
        )
        matches = search_results.get("matches", [])
        if not matches:
            print("⚠️ No relevant transcripts found.")
            return ""

        retrieved_texts, total_tokens = [], 0
        for match in matches:
            text = match["metadata"].get("text", "")
            token_count = len(text.split())
            if total_tokens + token_count <= token_limit:
                retrieved_texts.append(text)
                total_tokens += token_count
            else:
                break

        print(f"🧲 Retrieval took {time.time() - start_time:.2f}s with filter {filters}")
        return " ".join(retrieved_texts)
    except Exception as e:
        print(f"❌ Error in retrieve_relevant_transcripts: {str(e)}")
        raise


# --- Output Schema ---
class SuggestedItem(BaseModel):
    description: str
    badge: Optional[str] = None  # e.g., "trending"

class StructuredItineraryResponse(BaseModel):
    Suggested_Things_to_Do: Dict[str, SuggestedItem]

parser = PydanticOutputParser(pydantic_object=StructuredItineraryResponse)
retry_parser = OutputFixingParser.from_llm(llm=llm, parser=parser)

# --- Prompt Template ---
prompt_template = PromptTemplate(
    template="""
You are a helpful travel planner for {destination}.

Recommend at least {min_count} landmarks or events for a visitor staying {travel_days} days.

Use the retrieved context below, supplementing with your own knowledge.

Traveler Info:
{traveler_notes}

Instructions:
- Start with high-view-count or latest places in context, that are suitable to traveler.
- Prioritize **popular**, **recently opened**, or **upcoming** events.
- Only include places that are realistically reachable by car or transit within 3 hours of {destination}. 
- Do NOT include places that require long highway trips, flights, or inter-city trains.
- EXCLUDE bars, lounges, restaurants, cafes, and food-only destinations.
- You can include places that offer food only if it's part of a larger family or cultural experience (e.g., a fair or theme park).
- List specific museums if possible, rather than umbrella terms like "Smithsonian Museums"
- Consider any seasonal events or weather-related factors mentioned in the traveler notes
- Pay attention to any special requests or preferences in the traveler notes

Examples of GOOD entries for Dallas TX if with kids aged 3:
- "Peppa Pig Theme Park": An recently opened toddler park themed around Peppa Pig.
- "Dallas Arboretum": Botanical garden with a dedicated children garden.
- "Crayola Experience Plano": Hands-on creative experience for young children.
- "State Fair of Texas": Latest cultural and family-friendly event with rides, food, and activities.

Examples of BAD entries:
- "Pecan Lodge Barbecue", "Vinyl Lounge", "Galveston Day Trip" (too far)

Output Format (STRICT):
Return this exact structure in JSON format using the landmark name as the key, and a dictionary with:
  - "description": short phrase
  - "badge": optional (only include if landmark is trending or new)

{{
  "Suggested_Things_to_Do": {{
    "Landmark Name A": {{
      "description": "Short phrase",
      "badge": "trending"
    }},
    "Landmark Name B": {{
      "description": "Short phrase"
    }}
  }}
}}

Context:
{retrieved_context}

{format_instructions}
""",
    input_variables=["destination", "travel_days", "min_count", "retrieved_context", "traveler_notes"],
    partial_variables={"format_instructions": parser.get_format_instructions()},
)

# --- Main Function ---
def generate_structured_itinerary(
    destination: str,
    travel_days: int,
    with_kids=False,
    kids_age=None,
    with_elderly=False,
    special_requests=None,
    start_date=None,
    end_date=None
):
    try:
        print("🚀 Generating itinerary...")
        total_start = time.time()

        # Handle backward compatibility - convert single age to list
        if kids_age is not None and not isinstance(kids_age, list):
            kids_age = [kids_age]
        
        # Build modifier string for search query
        modifiers = []
        if with_kids and kids_age:
            avg_age = sum(kids_age) / len(kids_age)
            modifiers.append(f"with {int(avg_age)}-year-old kid")
        elif with_kids:
            modifiers.append("with kids")
        
        if with_elderly:
            modifiers.append("elderly-friendly")
            
        if special_requests:
            modifiers.append(special_requests)
            
        modifier = " " + " and ".join(modifiers) if modifiers else ""
            
        destination_normalized = normalize_destination(destination)
        print(f"🌍 Normalized destination: {destination_normalized}")

        try:
            context = retrieve_relevant_transcripts(
                f"{destination} things to do{modifier}",
                destination=destination_normalized,
                with_kids=with_kids,
                with_elderly=with_elderly
            )
        except Exception as e:
            print(f"⚠️ Error retrieving transcripts: {str(e)}")
            context = ""  # Fallback to LLM-only generation

        if not context.strip():
            print("⚠️ No relevant transcripts found. Proceeding without context.")
            context = ""

        min_required = max(4 * travel_days, 12)
        print(f"📌 Enforcing minimum of {min_required} items")

        # Build traveler notes with age range considerations
        traveler_notes = []
        
        # Add date-specific notes if provided
        if start_date and end_date:
            traveler_notes.append(f"Trip dates: {start_date} to {end_date}.")
            
            # Parse dates to check for seasonal considerations
            start = datetime.strptime(start_date, '%Y-%m-%d')
            month = start.month
            
            # Add seasonal notes
            if month in [12, 1, 2]:  # Winter
                traveler_notes.append("Consider indoor activities and winter events.")
            elif month in [3, 4, 5]:  # Spring
                traveler_notes.append("Include spring festivals and outdoor activities.")
            elif month in [6, 7, 8]:  # Summer
                traveler_notes.append("Prioritize early morning or indoor activities to avoid peak heat.")
            else:  # Fall
                traveler_notes.append("Consider fall festivals and outdoor activities.")
        
        if special_requests:
            traveler_notes.append(f"Special requests: {special_requests}")
            
        if with_kids and kids_age:
            min_age = min(kids_age)
            max_age = max(kids_age)
            
            if min_age < 6:
                traveler_notes.append("Include toddler-friendly attractions with minimal walking.")
            if any(age >= 3 and age <= 12 for age in kids_age):
                traveler_notes.append("Prioritize interactive museums, theme parks, and hands-on activities.")
            if max_age > 10:
                traveler_notes.append("Include more adventurous activities suitable for pre-teens.")
                
            if len(kids_age) == 1:
                traveler_notes.append(f"Prioritize activities suitable for {kids_age[0]}-year-old children.")
            else:
                ages_str = ", ".join(str(age) for age in kids_age)
                traveler_notes.append(f"Prioritize activities suitable for children aged {ages_str}.")
        elif with_kids:
            traveler_notes.append("Prioritize child-friendly landmarks and activities.")
            
        if with_elderly:
            traveler_notes.append("Include comfortable, low-exertion activities.")
            
        traveler_notes = " ".join(traveler_notes)

        print("🤖 Calling LLM for recommendations...")
        chain: RunnableSequence = prompt_template | llm | retry_parser
        llm_start = time.time()

        try:
            result = chain.invoke({
                "destination": destination,
                "travel_days": travel_days,
                "min_count": min_required,
                "retrieved_context": context,
                "traveler_notes": traveler_notes
            })
            print(f"💬 LLM response in {time.time() - llm_start:.2f}s")
        except Exception as e:
            print(f"❌ Error from LLM chain: {str(e)}")
            raise

        try:
            actual_count = len(result.Suggested_Things_to_Do)
            if actual_count < min_required:
                return {"error": f"Only {actual_count} valid items after filtering."}
            print(f"✅ Success in {time.time() - total_start:.2f}s")
            return result.model_dump()
        except Exception as e:
            print(f"❌ Error validating result: {str(e)}")
            raise

    except Exception as e:
        error_msg = f"Failed to generate itinerary: {str(e)}"
        print(f"❌ {error_msg}")
        return {"error": error_msg}



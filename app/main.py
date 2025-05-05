from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from rag import generate_structured_itinerary
from schema import LandmarkSelection, DayItinerary
from complete_itinerary import complete_itinerary_from_landmarks

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # ✅ must be false when using allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

class ItineraryRequest(BaseModel):
    destination: str
    travel_days: int
    with_kids: bool = False
    kids_age: int = None
    with_elderly: bool = False

@app.post("/generate")
def generate(request: ItineraryRequest):
    result = generate_structured_itinerary(
        destination=request.destination,
        travel_days=request.travel_days,
        with_kids=request.with_kids,
        kids_age=request.kids_age,
        with_elderly=request.with_elderly
    )
    return {"itinerary": result}

@app.post("/complete-itinerary", response_model=DayItinerary)
def complete_itinerary(data: LandmarkSelection):
    result = complete_itinerary_from_landmarks(
        destination=data.destination,
        travel_days=data.travel_days,
        with_kids=data.with_kids,
        with_elderly=data.with_elderly,
        selected_landmarks=data.selected_landmarks
    )
    return DayItinerary(root=result)

@app.get("/")
def home():
    return {"message": "🎒 Welcome to Plan Your Trip RAG API! Use /generate to get recommendations."}

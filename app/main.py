from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Union, List, Optional
from .rag import generate_structured_itinerary
from .schema import LandmarkSelection, DayItinerary
from .complete_itinerary import complete_itinerary_from_landmarks

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
    kids_age: Optional[Union[int, List[int]]] = None
    with_elderly: bool = False

@app.post("/generate")
async def generate(request: ItineraryRequest):
    try:
        result = generate_structured_itinerary(
            destination=request.destination,
            travel_days=request.travel_days,
            with_kids=request.with_kids,
            kids_age=request.kids_age,
            with_elderly=request.with_elderly
        )
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
            
        return {"itinerary": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/complete-itinerary", response_model=DayItinerary)
async def complete_itinerary(data: LandmarkSelection):
    try:
        result = complete_itinerary_from_landmarks(
            destination=data.destination,
            travel_days=data.travel_days,
            with_kids=data.with_kids,
            with_elderly=data.with_elderly,
            selected_landmarks=data.selected_landmarks
        )
        return DayItinerary(root=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def home():
    return {"message": "🎒 Welcome to Plan Your Trip RAG API! Use /generate to get recommendations."}

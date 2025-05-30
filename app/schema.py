from typing import List, Dict, Optional
from pydantic import BaseModel, RootModel

class LandmarkSelection(BaseModel):
    destination: str
    travel_days: int
    with_kids: bool = False
    with_elderly: bool = False
    selected_landmarks: List[str]

class ItineraryBlock(BaseModel):
    type: str  # "landmark" or "meal"
    name: str
    description: str
    mealtime: str | None = None  # Only filled if it's a meal

class DayPlan(BaseModel):
    morning: Optional[str] = None
    afternoon: Optional[str] = None
    evening: Optional[str] = None
    notes: Optional[str] = None

class DayItinerary(BaseModel):
    root: Dict[str, DayPlan]



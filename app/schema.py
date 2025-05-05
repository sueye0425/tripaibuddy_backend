from typing import List, Dict
from pydantic import BaseModel, RootModel

class LandmarkSelection(BaseModel):
    destination: str
    travel_days: int
    with_kids: bool
    with_elderly: bool
    selected_landmarks: Dict[str, List[str]]  # e.g., {"Day 1": ["Landmark A", "Landmark B"]}

class ItineraryBlock(BaseModel):
    type: str  # "landmark" or "meal"
    name: str
    description: str
    mealtime: str | None = None  # Only filled if it's a meal

class DayItinerary(RootModel):
    root: Dict[str, List[ItineraryBlock]]



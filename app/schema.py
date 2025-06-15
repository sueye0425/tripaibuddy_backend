from typing import List, Dict, Optional, Any
from pydantic import BaseModel, RootModel

class TripDetails(BaseModel):
    destination: str
    travelDays: int
    startDate: str
    endDate: str
    withKids: bool = False
    withElders: bool = False
    kidsAge: Optional[List[int]] = None
    specialRequests: Optional[str] = None

class Location(BaseModel):
    lat: float
    lng: float

class Attraction(BaseModel):
    name: str
    description: str
    location: Location
    type: str  # "restaurant" or "landmark"

class DayAttraction(BaseModel):
    day: int
    attractions: List[Attraction]

class LandmarkSelection(BaseModel):
    details: TripDetails
    wishlist: List[Any] = []  # Currently empty but keeping for future use
    itinerary: List[DayAttraction]

# New structured itinerary output models
class ItineraryBlock(BaseModel):
    type: str  # "landmark" or "restaurant"
    name: str
    description: Optional[str] = None  # Only used for landmarks, not restaurants
    start_time: str  # e.g., "9:00 AM"
    duration: str  # e.g., "2 hours"
    mealtime: Optional[str] = None  # "lunch" or "dinner" - only for restaurants
    place_id: Optional[str] = None  # Google Places ID if available
    rating: Optional[float] = None  # Google Places rating if available
    location: Optional[Location] = None  # Coordinates for internal use
    address: Optional[str] = None  # Human-readable address for display
    photo_url: Optional[str] = None  # Proxy URL for photo if available
    website: Optional[str] = None  # Official website URL for clickable cards - primary info source for restaurants
    notes: Optional[str] = None  # Additional context or recommendations

class StructuredDayPlan(BaseModel):
    day: int
    blocks: List[ItineraryBlock]

class StructuredItinerary(BaseModel):
    itinerary: List[StructuredDayPlan]

class CompleteItineraryResponse(BaseModel):
    itinerary: List[StructuredDayPlan]  # Direct list instead of nested StructuredItinerary
    performance_metrics: Optional[Dict] = None

# Keep the old models for backward compatibility
class DayPlan(BaseModel):
    morning: Optional[str] = None
    afternoon: Optional[str] = None
    evening: Optional[str] = None
    notes: Optional[str] = None

class DayItinerary(RootModel[Dict[str, Any]]):
    """Root model for day itinerary that can handle flexible day structures"""
    pass



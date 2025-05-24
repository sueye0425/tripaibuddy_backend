# Backend API Update: Multiple Kids Ages Support

## Overview
The `/generate` endpoint has been updated to support families with multiple children of different ages. The `kids_age` parameter now accepts both single numbers and arrays.

## Changes Made

### 1. Request Model Update
The `ItineraryRequest` model in `app/main.py` now accepts:
```python
kids_age: Optional[Union[int, List[int]]] = None
```

### 2. Backward Compatibility
- Single number format: `"kids_age": 5` → Converted internally to `[5]`
- Array format: `"kids_age": [5, 8, 12]` → Used as-is

### 3. Enhanced Recommendation Logic
The system now provides age-appropriate recommendations based on age ranges:

- **Ages < 6**: Focuses on toddler-friendly attractions with minimal walking
- **Ages 3-12**: Prioritizes interactive museums, theme parks, and hands-on activities
- **Ages > 10**: Includes more adventurous activities suitable for pre-teens

## API Usage Examples

### Single Child (Array Format)
```json
{
  "destination": "Paris",
  "travel_days": 3,
  "with_kids": true,
  "kids_age": [5],
  "with_elderly": false
}
```

### Multiple Children (Same Age)
```json
{
  "destination": "Paris",
  "travel_days": 3,
  "with_kids": true,
  "kids_age": [7, 7],
  "with_elderly": false
}
```

### Multiple Children (Different Ages)
```json
{
  "destination": "Paris",
  "travel_days": 3,
  "with_kids": true,
  "kids_age": [3, 8, 14],
  "with_elderly": false
}
```

### Backward Compatible (Single Number)
```json
{
  "destination": "Paris",
  "travel_days": 3,
  "with_kids": true,
  "kids_age": 5,
  "with_elderly": false
}
```

## Implementation Details

1. **Search Query Optimization**: Uses average age for database queries to find relevant content
2. **Personalized Recommendations**: Traveler notes are customized based on the age range of all children
3. **Flexible Input**: Automatically detects and handles both single numbers and arrays

## Testing

Run the included test script to verify functionality:
```bash
python test_kids_age.py
```

This will test all scenarios including backward compatibility. 
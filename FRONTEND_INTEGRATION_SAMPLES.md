# Frontend Integration Samples

## 📋 Sample Inputs & Outputs for Both Endpoints

### 🚀 `/generate` Endpoint (Fast Recommendations)

#### Sample Input
```json
{
  "destination": "San Francisco, CA",
  "travel_days": 3,
  "with_kids": true,
  "kids_age": "8-12",
  "special_requests": "Family-friendly activities, avoid too much walking"
}
```

#### Sample Output
```json
{
  "recommendations": {
    "landmarks": [
      {
        "name": "Golden Gate Bridge",
        "type": "landmark",
        "description": "Iconic suspension bridge with stunning views and photo opportunities",
        "location": {"lat": 37.8199, "lng": -122.4783},
        "rating": 4.7,
        "estimated_duration": "1.5h",
        "kid_friendly": true,
        "photo_url": "https://api.tripaibuddy.com/photo-proxy/golden-gate-bridge.jpg"
      },
      {
        "name": "Fisherman's Wharf",
        "type": "landmark", 
        "description": "Waterfront area with sea lions, street performers, and family attractions",
        "location": {"lat": 37.8080, "lng": -122.4177},
        "rating": 4.3,
        "estimated_duration": "2h",
        "kid_friendly": true,
        "photo_url": "https://api.tripaibuddy.com/photo-proxy/fishermans-wharf.jpg"
      },
      {
        "name": "Alcatraz Island",
        "type": "landmark",
        "description": "Historic former prison with audio tours and ferry ride",
        "location": {"lat": 37.8267, "lng": -122.4230},
        "rating": 4.6,
        "estimated_duration": "3h",
        "kid_friendly": true,
        "photo_url": "https://api.tripaibuddy.com/photo-proxy/alcatraz.jpg"
      }
    ],
    "restaurants": [
      {
        "name": "Pier Market Seafood Restaurant",
        "type": "restaurant",
        "description": "Family-friendly seafood restaurant with harbor views",
        "location": {"lat": 37.8085, "lng": -122.4100},
        "rating": 4.4,
        "cuisine": "Seafood",
        "price_level": 2,
        "kid_friendly": true,
        "photo_url": "https://api.tripaibuddy.com/photo-proxy/pier-market.jpg"
      },
      {
        "name": "Boudin Bakery Cafe",
        "type": "restaurant", 
        "description": "Famous sourdough bread bakery with kid-friendly menu",
        "location": {"lat": 37.8078, "lng": -122.4155},
        "rating": 4.2,
        "cuisine": "American",
        "price_level": 1,
        "kid_friendly": true,
        "photo_url": "https://api.tripaibuddy.com/photo-proxy/boudin-bakery.jpg"
      }
    ]
  },
  "performance_metrics": {
    "response_time": 0.49,
    "api_calls_used": 18,
    "estimated_cost": "$0.378"
  }
}
```

### 🎯 `/complete-itinerary` Endpoint (Detailed Scheduling)

#### Sample Input
```json
{
  "details": {
    "destination": "San Francisco, CA",
    "travelDays": 3,
    "withKids": true,
    "kidsAge": "8-12",
    "specialRequests": "Family-friendly activities, avoid too much walking"
  },
  "itinerary": [
    {
      "day": 1,
      "attractions": [
        {
          "name": "Golden Gate Bridge",
          "type": "landmark",
          "selected": true
        },
        {
          "name": "Fisherman's Wharf", 
          "type": "landmark",
          "selected": true
        }
      ]
    },
    {
      "day": 2,
      "attractions": [
        {
          "name": "Alcatraz Island",
          "type": "landmark", 
          "selected": true
        }
      ]
    },
    {
      "day": 3,
      "attractions": [
        {
          "name": "California Academy of Sciences",
          "type": "landmark",
          "selected": true
        }
      ]
    }
  ],
  "wishlist": [
    {"name": "Lombard Street", "type": "landmark"},
    {"name": "Chinatown", "type": "landmark"}
  ]
}
```

#### Sample Output (First Day Only - Full Response Would Include All 3 Days)
```json
{
  "itinerary": {
    "itinerary": [
      {
        "day": 1,
        "blocks": [
          {
            "type": "restaurant",
            "name": "Mama's on Washington Square",
            "description": "Famous breakfast spot known for family-friendly atmosphere and generous portions",
            "start_time": "08:00",
            "duration": "45m",
            "mealtime": "breakfast",
            "location": {"lat": 37.8006, "lng": -122.4103},
            "rating": 4.5,
            "address": "1701 Stockton St, San Francisco, CA",
            "photo_url": "https://api.tripaibuddy.com/photo-proxy/mamas-breakfast.jpg",
            "place_id": "ChIJXYZ123",
            "website": "https://mamas-sf.com"
          },
          {
            "type": "landmark",
            "name": "Golden Gate Bridge",
            "description": "Iconic suspension bridge offering breathtaking views and perfect photo opportunities for families",
            "start_time": "09:30",
            "duration": "1.5h",
            "location": {"lat": 37.8199, "lng": -122.4783},
            "rating": 4.7,
            "address": "Golden Gate Bridge, San Francisco, CA",
            "photo_url": "https://api.tripaibuddy.com/photo-proxy/golden-gate-bridge.jpg",
            "place_id": "ChIJABC456",
            "website": "https://www.goldengate.org"
          },
          {
            "type": "restaurant",
            "name": "The Warming Hut",
            "description": "Casual cafe near Golden Gate Bridge with kid-friendly snacks and warm drinks",
            "start_time": "12:00",
            "duration": "1h",
            "mealtime": "lunch",
            "location": {"lat": 37.8055, "lng": -122.4662},
            "rating": 4.1,
            "address": "983 Marine Dr, San Francisco, CA",
            "photo_url": "https://api.tripaibuddy.com/photo-proxy/warming-hut.jpg",
            "place_id": "ChIJDEF789",
            "website": null
          },
          {
            "type": "landmark",
            "name": "Fisherman's Wharf",
            "description": "Bustling waterfront destination with sea lions, street performers, and family-friendly attractions",
            "start_time": "14:00",
            "duration": "2.5h",
            "location": {"lat": 37.8080, "lng": -122.4177},
            "rating": 4.3,
            "address": "Fisherman's Wharf, San Francisco, CA",
            "photo_url": "https://api.tripaibuddy.com/photo-proxy/fishermans-wharf.jpg",
            "place_id": "ChIJGHI012",
            "website": "https://www.fishermanswharf.org"
          },
          {
            "type": "restaurant",
            "name": "Pier Market Seafood Restaurant",
            "description": "Family-friendly seafood restaurant with harbor views and fresh catches",
            "start_time": "18:00",
            "duration": "1.5h",
            "mealtime": "dinner",
            "location": {"lat": 37.8085, "lng": -122.4100},
            "rating": 4.4,
            "address": "Pier 39, San Francisco, CA",
            "photo_url": "https://api.tripaibuddy.com/photo-proxy/pier-market.jpg",
            "place_id": "ChIJJKL345",
            "website": "https://piermarket.com"
          }
        ]
      }
    ]
  },
  "performance_metrics": {
    "timings": {
      "llm_generation": 8.2,
      "restaurant_and_enhancement": 7.8,
      "duplicate_removal": 1.9,
      "total_generation": 18.1
    },
    "costs": {
      "google_places": {
        "restaurant_api_calls": 5,
        "enhancement_api_calls": 8,
        "total_cost_estimate": "$0.653"
      },
      "openai": {
        "llm_calls": 2,
        "total_cost_estimate": "$0.017"
      }
    },
    "optimization": "Significant reduction through parallel processing and smart grouping"
  }
}
```

## 🔧 Frontend Implementation Guidelines

### 1. **Loading States**

#### For `/generate` (Fast)
```javascript
// Show spinner for ~0.5 seconds
const [loading, setLoading] = useState(false);

const fetchRecommendations = async () => {
  setLoading(true);
  try {
    const response = await fetch('/api/generate', {
      method: 'POST',
      body: JSON.stringify(requestData)
    });
    const data = await response.json();
    // Handle success
  } catch (error) {
    // Handle error
  } finally {
    setLoading(false); // Usually completes in < 1 second
  }
};
```

#### For `/complete-itinerary` (Detailed)
```javascript
// Show progress indicator for ~15-20 seconds
const [loading, setLoading] = useState(false);
const [progress, setProgress] = useState(0);

const generateItinerary = async () => {
  setLoading(true);
  setProgress(0);
  
  // Simulate progress (since we can't get real-time updates)
  const progressInterval = setInterval(() => {
    setProgress(prev => Math.min(prev + 5, 90));
  }, 1000);
  
  try {
    const response = await fetch('/api/complete-itinerary', {
      method: 'POST',
      body: JSON.stringify(requestData)
    });
    const data = await response.json();
    setProgress(100);
    // Handle success
  } catch (error) {
    // Handle error
  } finally {
    clearInterval(progressInterval);
    setLoading(false);
  }
};
```

### 2. **Error Handling**

```javascript
const handleApiError = (error, response) => {
  if (response?.error) {
    // Backend returned structured error
    switch (response.error) {
      case 'Invalid destination':
        showError('Please enter a valid destination');
        break;
      case 'Rate limit exceeded':
        showError('Too many requests. Please try again in a minute.');
        break;
      default:
        showError(`Error: ${response.error}`);
    }
  } else if (error.name === 'AbortError') {
    showError('Request timed out. Please try again.');
  } else {
    showError('Something went wrong. Please try again.');
  }
};
```

### 3. **Performance Monitoring**

```javascript
// Track API performance
const trackApiPerformance = (endpoint, startTime, success) => {
  const duration = Date.now() - startTime;
  
  // Send to analytics
  analytics.track('api_call', {
    endpoint,
    duration,
    success,
    timestamp: new Date().toISOString()
  });
  
  // Log slow requests
  if (duration > 30000) { // 30 seconds
    console.warn(`Slow API call: ${endpoint} took ${duration}ms`);
  }
};
```

---

*Last updated: December 2024*
*For integration support, contact the backend team* 
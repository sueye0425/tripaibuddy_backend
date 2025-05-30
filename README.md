# Travel Planning Backend

A smart travel planning backend that combines Google Places API with RAG (Retrieval-Augmented Generation) to provide personalized travel recommendations.

## Features

- Smart landmark and restaurant recommendations using Google Places API
- Preference-based filtering and ranking
- Support for families with kids and elderly travelers
- Date-aware recommendations considering seasonal activities
- Redis caching for improved performance
- RAG fallback system for comprehensive coverage
- Rate limiting for API quota management

## Architecture

### Core Components
- **Google Places Integration**: Primary source for location data
- **OpenAI GPT-3.5**: For processing special requests and preferences (requires openai==1.12.0)
- **Redis Cache**: For storing geocoding and place details
- **Pinecone**: Vector database for RAG fallback system
- **FastAPI**: REST API framework

### API Response Structures

#### /generate Endpoint
```json
{
  "landmarks": {
    "place_name": {
      "description": "string",
      "place_id": "string",
      "rating": "float",
      "location": {
        "lat": "float",
        "lng": "float"
      },
      "photos": ["string"],
      "opening_hours": {}
    }
  },
  "restaurants": {
    // Same structure as landmarks
  }
}
```

### Example API Usage

#### Generate Travel Recommendations
```bash
curl -X POST https://tripaibuddy-backend-850428903067.us-central1.run.app/generate \
  -H "Content-Type: application/json" \
  -d '{
    "destination": "Orlando, Florida",
    "travel_days": 4,
    "with_kids": true,
    "kids_age": [5, 8],
    "with_elderly": false,
    "special_requests": "Looking for theme parks, family-friendly activities, and good restaurants"
  }'
```

This example:
- Requests recommendations for Orlando, Florida
- Plans for a 4-day trip
- Includes preferences for children aged 5 and 8
- Looks for theme parks and family-friendly activities
- Returns both landmarks and restaurant recommendations

#### /complete-itinerary Endpoint
```json
{
  "root": {
    "Day 1": {
      "morning": "string",
      "afternoon": "string",
      "evening": "string",
      "notes": "string"
    }
    // More days...
  }
}
```

## Setup

### Prerequisites
- Python 3.11+
- Redis
- Google Cloud SDK (for GCP deployment)
- Docker (optional)

### Dependencies
Key package versions:
```
openai>=1.12.0
pinecone-client>=2.2.2
redis>=4.5.0
fastapi>=0.100.0
uvicorn>=0.22.0
```

### Important Notes

#### OpenAI Client Version
- The project requires OpenAI Python SDK version 1.12.0 or higher.
- If you encounter errors like `TypeError: Client.__init__() got an unexpected keyword argument 'proxies'`, run:
  ```bash
  pip install --upgrade openai
  ```
- This ensures you have the latest compatible OpenAI client and avoids issues with deprecated arguments.

#### OpenAI Client Changes
The project uses the new OpenAI Python SDK (>=1.0.0) which has significant changes:
- The client initialization is now instance-based instead of global configuration
- Proxy configuration is no longer supported via the client constructor
- Use environment variables for proxy configuration if needed

Example client initialization:
```python
from openai import OpenAI

# Correct way:
client = OpenAI(api_key="your_api_key")

# ❌ Don't use proxies in constructor:
# client = OpenAI(api_key="your_api_key", proxies={"http": ..., "https": ...})
```

### Local Development Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/tripaibuddy_backend.git
cd tripaibuddy_backend
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Set up environment variables:
- Copy `.env.example` to `.env`
- Fill in your API keys and configuration:
  ```
  OPENAI_API_KEY=your_openai_api_key
  GOOGLE_PLACES_API_KEY=your_google_places_api_key
  REDIS_URL=redis://localhost:6379
  PINECONE_API_KEY=your_pinecone_api_key
  PINECONE_ENVIRONMENT=your_pinecone_environment
  ```

Note: The project uses OpenAI API client version 1.12.0. If you encounter initialization errors, ensure you have the correct version:
```bash
pip install openai
```

4. Start Redis:
```bash
docker run -d -p 6379:6379 redis
```

5. Run the application:
```bash
uvicorn app.main:app --reload --port 8080
```
or 
```bash
lsof -i :8000 | grep LISTEN | awk '{print $2}' | xargs kill -9 && uvicorn app.main:app --reload --port 8000
```

## Testing

### 1. API Connection Tests
Test all external API connections using:
```bash
python scripts/test_setup.py
```

This tests connections to:
- Redis
- OpenAI API
- Google Places API
- Pinecone

### 2. Endpoint Tests
Test all endpoints and response structures:
```bash
python scripts/test_endpoints.py
```

This includes:
- Health check endpoint
- Basic recommendations
- Date-based recommendations
- Complete itinerary generation
- Response structure validation

### 3. Environment-specific Testing

#### Local Testing
```bash
# Default configuration uses localhost:8080
python scripts/test_endpoints.py
```

#### GCP Testing
```bash
export API_BASE_URL="https://your-cloud-run-url.run.app"
python scripts/test_endpoints.py
```

## GCP Deployment

### 1. Initial Setup
```bash
# Install and initialize Google Cloud SDK
gcloud init
gcloud config set project YOUR_PROJECT_ID

# Enable required services
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  containerregistry.googleapis.com
```

### 2. Secret Management
```bash
# Create secrets in Secret Manager
python scripts/migrate_secrets.py
```

### 3. Deployment Commands

#### Initial Deployment
```bash
# Submit build and deploy to Cloud Run
gcloud builds submit --config cloudbuild.yaml
```

#### Redeployment (for code updates like CORS changes)
##### Note: The v3 prefix is now in place. If you make further significant backend changes in the future that require cache invalidation, you would increment CACHE_VERSION to "v4", then "v5", and so on. The v2 data would then eventually expire due to its TTL.
```bash
# Method 1: Using Cloud Build (Recommended)
gcloud builds submit --config cloudbuild.yaml

# Method 2: Direct deployment from local source
gcloud run deploy tripaibuddy-backend \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --concurrency 80 \
  --max-instances 10

# Method 3: Deploy specific image (if you have a pre-built image)
gcloud run deploy tripaibuddy-backend \
  --image gcr.io/YOUR_PROJECT_ID/tripaibuddy-backend:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

#### Quick Redeployment for Code Changes
```bash
# For quick updates (like CORS changes), use this one-liner:
gcloud builds submit --config cloudbuild.yaml --substitutions=_SERVICE_NAME=tripaibuddy-backend
```

#### Check Deployment Status
```bash
# View service details
gcloud run services describe tripaibuddy-backend --region us-central1

# View recent deployments
gcloud run revisions list --service tripaibuddy-backend --region us-central1

# View logs
gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=tripaibuddy-backend" --limit 50
```

#### Environment Variables and Secrets
```bash
# Update environment variables (if needed)
gcloud run services update tripaibuddy-backend \
  --region us-central1 \
  --set-env-vars "ALLOWED_ORIGINS=https://your-frontend-domain.com,http://localhost:5173"

# Update secrets (if API keys change)
gcloud secrets versions add OPENAI_API_KEY --data-file=-
gcloud secrets versions add GOOGLE_PLACES_API_KEY --data-file=-
```

### 4. Networking Configuration

#### VPC Connector Setup (for Redis access)
```bash
# Create VPC connector (if not already created)
gcloud compute networks vpc-access connectors create redis-connector \
  --region us-central1 \
  --subnet default \
  --subnet-project YOUR_PROJECT_ID \
  --min-instances 2 \
  --max-instances 3

# Update Cloud Run service to use VPC connector
gcloud run services update tripaibuddy-backend \
  --region us-central1 \
  --vpc-connector redis-connector \
  --vpc-egress private-ranges-only
```

### Infrastructure
- **Cloud Run**: Main service hosting
- **Cloud Build**: CI/CD pipeline
- **Secret Manager**: API key management
- **VPC Connector**: For Redis access
- **Redis**: Memorystore instance

## Rate Limits

The system respects Google Places API quotas:
- SearchNearbyRequest: 600/minute, 75,000/day
- GetPlaceRequest: 600/minute, 125,000/day
- GetPhotoMediaRequest: 600/minute, 175,000/day

Redis caching helps minimize API calls.

## Error Handling

The system includes:
- Graceful fallback to RAG system
- Comprehensive error logging
- Rate limit monitoring
- Cache management
- Input validation

## API Documentation

Full API documentation is available at:
- Swagger UI: `/docs`
- OpenAPI spec: `/openapi.json`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
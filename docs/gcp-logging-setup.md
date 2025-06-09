# GCP Logging Setup Guide

## Overview

The application now includes structured logging that integrates seamlessly with Google Cloud Platform logging systems. This provides much better visibility than simple print statements.

## What You Get

### Before (Print Statements)
```
🚀 Starting complete itinerary generation...
🧠 LLM processing: 2 days, 3 attractions
✅ Itinerary generated successfully in 3.2s total
```

### After (Structured GCP Logs)
```json
{
  "timestamp": "2025-06-01T21:48:04.792Z",
  "severity": "INFO",
  "message": "Itinerary generation completed successfully",
  "event": "itinerary_generation_complete",
  "destination": "Washington DC",
  "travel_days": 2,
  "success": true,
  "total_duration": 3.2,
  "llm_duration": 2.1,
  "llm_percentage": 65.6,
  "violation_count": 0,
  "with_kids": true,
  "kids_count": 2,
  "total_selected_attractions": 3
}
```

## Setup Instructions

### 1. Install Dependencies
```bash
pip install google-cloud-logging>=3.8.0
```

### 2. Set Up Authentication
Either:
- **Service Account**: Set `GOOGLE_APPLICATION_CREDENTIALS` environment variable
- **Default Credentials**: Use Application Default Credentials on GCP services

### 3. Deploy to GCP
The logging will automatically work on:
- **Cloud Run** ✅
- **App Engine** ✅  
- **GKE** ✅
- **Compute Engine** (with Logging Agent)

## Log Queries in GCP Console

### Find All Itinerary Generations
```
resource.type="cloud_run_revision"
jsonPayload.event="itinerary_generation_complete"
```

### Find Failed Requests
```
resource.type="cloud_run_revision"
jsonPayload.success=false
```

### Find Slow Requests (>5 seconds)
```
resource.type="cloud_run_revision"
jsonPayload.total_duration>5
```

### Find Requests with Violations
```
resource.type="cloud_run_revision"
jsonPayload.violation_count>0
```

### Monitor by Destination
```
resource.type="cloud_run_revision"
jsonPayload.destination="Washington DC"
```

## Available Log Events

### 1. Request Start
- **Event**: `itinerary_generation_start`
- **Fields**: destination, travel_days, with_kids, kids_count, total_selected_attractions

### 2. Cache Hit
- **Event**: `cache_hit`
- **Fields**: cache_key, response_time

### 3. LLM Interaction
- **Event**: `llm_interaction`
- **Fields**: model_name, result_metrics, violations, input_metrics

### 4. Completion
- **Event**: `itinerary_generation_complete`
- **Fields**: success, total_duration, llm_duration, violation_count

### 5. Errors
- **Event**: `itinerary_generation_error` or `itinerary_generation_timeout`
- **Fields**: error_type, error_message, total_duration

## Monitoring & Alerting

### Create Alerts for:
1. **High error rate**: `jsonPayload.success=false`
2. **Slow responses**: `jsonPayload.total_duration>10`
3. **High violation rate**: `jsonPayload.violation_count>2`
4. **Model fallbacks**: `jsonPayload.used_backup_model=true` (when GPT-4-turbo fails and falls back to GPT-3.5-turbo)

### Metrics to Track:
- Average response time by destination
- Success rate by travel days
- Violation patterns by group composition
- Cache hit rate
- LLM model usage distribution

## Development vs Production

### Development
- Print statements show in console for immediate debugging
- Standard logging format for local development

### Production (GCP)
- Structured JSON logs in Cloud Logging
- Queryable and filterable
- Automatic log retention and archiving
- Integration with monitoring and alerting

## Benefits

✅ **Searchable**: Query by any field (destination, duration, etc.)
✅ **Filterable**: Find specific issues quickly
✅ **Alertable**: Set up proactive monitoring
✅ **Analyzable**: Export to BigQuery for analysis
✅ **Traceable**: Follow request flow end-to-end
✅ **Debuggable**: Rich context for troubleshooting 
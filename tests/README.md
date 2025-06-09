# Agentic Itinerary Testing Suite

This directory contains comprehensive tests for the agentic itinerary system, broken down into modular pytest files for efficient testing and cost management.

## Test Structure

### 🤖 LLM Tests (Cost-Incurring)
- **`test_llm_generation.py`** - Real LLM calls to validate generation quality
  - No duplicate landmarks across days
  - Theme park detection and handling  
  - JSON format compliance
  - Mandatory attraction inclusion

### 🔧 Rule-Based Tests (No Cost)
- **`test_restaurant_logic.py`** - Restaurant addition logic using mocks
- **`test_performance.py`** - Performance requirements using mocked responses
- **`test_duplicate_detection.py`** - Duplicate prevention using known test data

### 📁 Test Configuration
- **`conftest.py`** - Shared fixtures, mocks, and test data
- **`pytest.ini`** - Pytest configuration and markers

## Running Tests

### Run All Tests (Includes LLM Costs)
```bash
pytest tests/
```

### Run Only Rule-Based Tests (No LLM Costs)
```bash
pytest tests/ -m "not llm_cost"
```

### Run Only LLM Tests (For Validation)
```bash
pytest tests/ -m "llm_cost"
```

### Run Specific Test Files
```bash
# Restaurant logic only
pytest tests/test_restaurant_logic.py

# Performance tests only  
pytest tests/test_performance.py

# Duplicate detection only
pytest tests/test_duplicate_detection.py
```

### Run with Coverage
```bash
pytest tests/ --cov=app.agentic_itinerary --cov-report=html
```

## Test Markers

- `@pytest.mark.llm_cost` - Tests that make real LLM calls (expensive)
- `@pytest.mark.slow` - Tests that take longer to run
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.unit` - Fast unit tests

## Key Testing Strategy

### 1. **One LLM Test for Quality Validation**
The `test_llm_generation.py` file contains the expensive tests that make real LLM calls to validate:
- No duplicate landmarks are generated
- Theme park logic works correctly
- Mandatory attractions are included
- JSON format is followed

### 2. **Rule-Based Tests for Logic Validation**
All other tests use mocked LLM responses to validate:
- Restaurant addition logic
- Performance requirements  
- Duplicate prevention
- Error handling
- Edge cases

### 3. **Cost Management**
- Most tests use mocks to avoid LLM costs
- Only critical validation tests make real API calls
- Use `-m "not llm_cost"` for development testing
- Use `-m "llm_cost"` sparingly for validation

## Test Data

### Mock Responses
- **Good landmarks response** - Diverse landmarks, no duplicates
- **Duplicate landmarks response** - Known duplicates for testing detection
- **Restaurant data** - Various Google Places restaurant responses

### Sample Trips
- **Orlando 3-day trip** - Universal Studios (theme park) + regular attractions
- **Mixed attraction types** - Theme parks, museums, parks

## Expected Test Results

### ✅ Passing Tests Should Show:
- No duplicate landmarks across days
- Exactly 3 restaurants per day
- Theme park lunch at 12:30
- Performance under 15 seconds (mocked)
- 100% Google Places integration (mocked)

### ❌ LLM Tests May Occasionally Fail Due to:
- LLM generating unexpected duplicates
- Theme park logic variations
- JSON format issues
- API timeouts

## Adding New Tests

1. **Add to appropriate file** based on whether it needs real LLM calls
2. **Use existing fixtures** from `conftest.py`
3. **Add appropriate markers** (`@pytest.mark.llm_cost` if expensive)
4. **Mock LLM responses** for rule-based tests
5. **Update this README** if adding new test categories 
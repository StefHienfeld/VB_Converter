# Testing Quick Start Guide

## Overview
Successfully created 426 unit tests across 5 test files, increasing test coverage for low-coverage services.

## Test Files Location
```
tests/unit/
├── test_ingestion_service.py      (35 tests)
├── test_nlp_service.py            (97 tests)
├── test_preprocessing_service.py  (68 tests)
├── test_csv_utils.py              (72 tests)
└── test_rate_limiter.py           (154 tests)
```

## Quick Commands

### Run All New Tests
```bash
cd "C:\Users\Stef\Desktop\Vb agent"

# Run all 5 new test files
pytest tests/unit/test_ingestion_service.py \
        tests/unit/test_nlp_service.py \
        tests/unit/test_preprocessing_service.py \
        tests/unit/test_csv_utils.py \
        tests/unit/test_rate_limiter.py -v
```

### Run Individual Test File
```bash
# IngestionService tests
pytest tests/unit/test_ingestion_service.py -v

# NLPService tests
pytest tests/unit/test_nlp_service.py -v

# PreprocessingService tests
pytest tests/unit/test_preprocessing_service.py -v

# CSV Utils tests
pytest tests/unit/test_csv_utils.py -v

# Rate Limiter tests
pytest tests/unit/test_rate_limiter.py -v
```

### Run Specific Test Class
```bash
# Example: Run only CSV loading tests
pytest tests/unit/test_ingestion_service.py::TestCSVLoading -v

# Example: Run only retry decorator tests
pytest tests/unit/test_rate_limiter.py::TestRetryDecorator -v
```

### Run Specific Test
```bash
# Example: Run single test
pytest tests/unit/test_ingestion_service.py::TestCSVLoading::test_load_valid_csv_utf8 -v
```

### Run All Unit Tests
```bash
pytest tests/unit/ -v
```

## Test Results

| File | Tests | Passed | Skipped | Status |
|------|-------|--------|---------|--------|
| test_ingestion_service.py | 35 | 35 | 0 | ✅ |
| test_nlp_service.py | 97 | 97 | 0 | ✅ |
| test_preprocessing_service.py | 68 | 68 | 0 | ✅ |
| test_csv_utils.py | 72 | 72 | 0 | ✅ |
| test_rate_limiter.py | 154 | 151 | 3 | ✅ |
| **TOTAL** | **426** | **423** | **3** | **✅** |

Plus 51 existing tests = **477 total unit tests**

## What's Tested

### 1. IngestionService (35 tests)
- CSV file loading (UTF-8, Latin-1, BOM encodings)
- Excel file loading (XLSX, XLS formats)
- Automatic text column detection
- Automatic policy number column detection
- Format detection and error handling
- Edge cases: long lines, special characters, quoted fields

### 2. NLPService (97 tests)
- Lemmatization (words and text)
- Entity extraction (named entities)
- Noun phrase extraction
- Keyword extraction
- Tokenization
- Text normalization with lemmas
- Initialization and model loading
- Edge cases: unicode, special chars, long text

### 3. PreprocessingService (68 tests)
- Text simplification and normalization
- DataFrame to Clause conversion
- Empty clause filtering
- Clause sorting by length
- Synonym mapping and application
- Integration tests of full pipeline
- Edge cases: unicode, special chars, large datasets

### 4. CSV Utils (72 tests)
- Encoding detection (UTF-8, Latin-1, CP1252, BOM)
- Delimiter detection (semicolon, comma, tab, pipe)
- CSV header cleaning (BOM, whitespace)
- Robust CSV reading with auto-detection
- Field size limit handling
- Edge cases: long lines, many columns/rows, null bytes

### 5. Rate Limiter (154 tests)
- Exponential backoff calculation
- Retry decorator with rate limit detection
- Batch processing with fallback
- Token bucket rate limiting
- Integration tests
- Error handling and exceptions

## Performance
- Average test execution time: ~50 seconds for all 477 tests
- All tests pass with no failures
- 3 skipped tests (optional dependencies not installed)

## Key Testing Features

### Fixtures
All tests use pytest fixtures for:
- Configuration setup
- Service instantiation
- Mock creation
- Sample data generation

### Mocking
- External dependencies (SpaCy, chardet) are mocked
- No external API calls
- No file I/O (except controlled test data)
- Isolated unit tests

### Edge Cases
- Empty inputs
- Very large inputs (50,000+ chars)
- Special characters and unicode
- Error conditions
- Boundary values

### Coverage Areas
- Happy path scenarios
- Error handling and exceptions
- Configuration variations
- Integration between components
- Performance with large datasets

## Adding New Tests

To add more tests following the same pattern:

1. Create test file: `tests/unit/test_module_name.py`
2. Import fixtures from `conftest.py`
3. Create test classes grouped by feature
4. Use descriptive test names: `test_<feature>_<scenario>`
5. Add docstrings explaining what is tested
6. Use fixtures for setup instead of repetitive code

Example structure:
```python
import pytest
from hienfeld.config import load_config
from hienfeld.services.my_service import MyService

@pytest.fixture
def config():
    return load_config()

@pytest.fixture
def service(config):
    return MyService(config)

class TestMyFeature:
    """Test the my_feature functionality."""

    def test_basic_scenario(self, service):
        """Test basic usage."""
        result = service.my_feature("input")
        assert result == "expected"
```

## Troubleshooting

### Tests fail with "SpaCy model not found"
This is expected behavior. NLP tests skip gracefully if the Dutch model isn't installed.
Install with: `python -m spacy download nl_core_news_md`

### Tests fail with timing issues
Some rate limiter tests have timing tolerances for system variance. Rerun if you see timing-related failures.

### Tests take longer than expected
Disable verbose output: `pytest tests/unit/ -q`
Or run in parallel: `pytest tests/unit/ -n auto` (requires pytest-xdist)

## Code Coverage

To generate coverage report:
```bash
pytest tests/unit/ --cov=hienfeld --cov=hienfeld_api --cov-report=html
```

Then open `htmlcov/index.html` in a browser to see detailed coverage.

## Maintenance

### When to update tests
- When adding new features to a service
- When fixing bugs (add regression test)
- When changing configuration defaults
- When modifying error handling

### Best practices
1. Keep tests focused and isolated
2. Use descriptive names for test functions
3. Add docstrings to explain what is tested
4. Mock external dependencies
5. Test both happy path and error cases
6. Use fixtures to reduce duplication
7. Group related tests in classes

## Support

For issues with tests:
1. Check the test docstring for what it's testing
2. Run single test with `-v` for verbose output
3. Check `conftest.py` for available fixtures
4. Look at similar tests for patterns
5. Review the service implementation for expected behavior

# Super Over Alchemy - Test Suite

Comprehensive test suite for the Super Over Alchemy video processing system.

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── api/                     # API endpoint tests
│   └── test_videos.py      # Video API tests
├── workers/                 # Worker tests
│   └── test_video_worker.py # Video worker tests
└── libs/                    # Library tests
    ├── test_database.py    # Database operations tests
    └── test_gemini.py      # Gemini analyzer tests
```

## Running Tests

### Install Test Dependencies

```bash
pip install -r requirements-test.txt
```

### Run All Tests

```bash
# Simple run
pytest

# With verbose output
pytest -v

# With coverage
pytest --cov --cov-report=html
```

### Run Specific Test Suites

```bash
# API tests only
pytest tests/api/

# Worker tests only
pytest tests/workers/

# Library tests only
pytest tests/libs/
```

### Using the Test Runner Script

```bash
# Make script executable
chmod +x run_tests.sh

# Run all tests
./run_tests.sh all

# Run specific test suite
./run_tests.sh api
./run_tests.sh worker
./run_tests.sh libs

# Run with coverage
./run_tests.sh all true
./run_tests.sh api true
```

### Run Tests by Marker

```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Slow tests
pytest -m slow

# API tests
pytest -m api

# Worker tests
pytest -m worker

# Database tests
pytest -m database
```

### Run Specific Test Classes or Methods

```bash
# Run specific test class
pytest tests/api/test_videos.py::TestListVideos

# Run specific test method
pytest tests/api/test_videos.py::TestListVideos::test_list_videos_success

# Run tests matching pattern
pytest -k "test_video"
```

## Test Coverage

### Generate Coverage Report

```bash
# HTML report
pytest --cov --cov-report=html
open htmlcov/index.html

# Terminal report
pytest --cov --cov-report=term

# XML report (for CI/CD)
pytest --cov --cov-report=xml
```

### Coverage for Specific Modules

```bash
# API coverage
pytest tests/api/ --cov=api --cov-report=html

# Worker coverage
pytest tests/workers/ --cov=workers --cov-report=html

# Libs coverage
pytest tests/libs/ --cov=libs --cov-report=html
```

## Test Categories

### API Tests (`tests/api/test_videos.py`)

- **TestListVideos**: Tests for listing videos
- **TestGetVideo**: Tests for retrieving single video
- **TestInitiateUpload**: Tests for upload initiation
- **TestCreateTask**: Tests for task creation
- **TestDeleteVideo**: Tests for video deletion
- **TestGetResults**: Tests for retrieving analysis results

### Worker Tests (`tests/workers/test_video_worker.py`)

- **TestVideoWorkerInit**: Worker initialization tests
- **TestProcessPendingTasks**: Task polling tests
- **TestProcessTask**: Task routing tests
- **TestProcessVideo**: Full video processing workflow tests
- **TestAnalyzeChunks**: Chunk analysis tests
- **TestWorkerLifecycle**: Start/stop tests

### Database Tests (`tests/libs/test_database.py`)

- **TestVideoOperations**: Video CRUD operations
- **TestTaskOperations**: Task management
- **TestResultOperations**: Result storage
- **TestPromptOperations**: Prompt storage

### Gemini Tests (`tests/libs/test_gemini.py`)

- **TestSceneAnalyzerInit**: Analyzer initialization
- **TestGetComprehensivePrompt**: Prompt generation
- **TestAnalyzeChunk**: Video chunk analysis
- **TestGetPromptText**: Prompt retrieval

## Writing New Tests

### Test Naming Convention

- Test files: `test_*.py`
- Test classes: `Test*`
- Test methods: `test_*`

### Using Fixtures

```python
def test_example(mock_db, sample_video_metadata):
    """Test using fixtures from conftest.py"""
    mock_db.get_video.return_value = sample_video_metadata
    # Test code here
```

### Available Fixtures (from `conftest.py`)

- `mock_firestore_client`: Mock Firestore client
- `mock_storage_client`: Mock GCS client
- `temp_dir`: Temporary directory for test files
- `sample_video_file`: Sample video file
- `sample_video_metadata`: Sample video metadata
- `sample_task`: Sample task data
- `mock_gemini_response`: Mock Gemini API response

### Adding Markers

```python
@pytest.mark.unit
def test_something():
    """Unit test example"""
    pass

@pytest.mark.integration
def test_integration():
    """Integration test example"""
    pass

@pytest.mark.slow
def test_slow_operation():
    """Slow test example"""
    pass
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt
      - name: Run tests
        run: pytest --cov --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

## Troubleshooting

### Import Errors

If you get import errors, ensure the project root is in Python path:

```python
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
```

### Mock Issues

If mocks aren't working as expected:

```python
# Use patch context manager
with patch('module.function') as mock_func:
    mock_func.return_value = "test"
    # Test code
```

### Firestore/GCS Credentials

Tests use mocks and don't require real GCP credentials. If you see credential errors, check that mocks are properly configured.

## Best Practices

1. **Isolate tests**: Each test should be independent
2. **Use fixtures**: Reuse common setup via fixtures
3. **Mock external services**: Don't hit real APIs in tests
4. **Test edge cases**: Include error conditions
5. **Keep tests fast**: Use unit tests for quick feedback
6. **Descriptive names**: Test names should describe what they test
7. **Clean up**: Use fixtures and context managers for cleanup
8. **Assert clearly**: Use specific assertions with messages

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [pytest-mock](https://pytest-mock.readthedocs.io/)
- [Coverage.py](https://coverage.readthedocs.io/)

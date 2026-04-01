# Lottery Analysis Project - Agent Guidelines

## Project Overview

This project collects and analyzes Korean Pension Lottery 720+ data from the official DHL Lottery website (https://www.dhlottery.co.kr). The project focuses on building a robust data collection pipeline while respecting the target website rate limits.

Target: Pension Lottery 720+ (연금복권720+) - NOT Lotto 6/45
Data Source: https://dhlottery.co.kr/gameResult.do?method=win720 (POST)
First Draw Date: 2020-05-07 (Round 1)

## Project Structure

lottery_analysis/
├── src/
│   ├── collector/          # Data collection modules
│   │   ├── __init__.py
│   │   ├── fetcher.py      # HTTP requests with rate limiting
│   │   └── parser.py       # HTML parsing (BeautifulSoup)
│   ├── storage/            # Data persistence
│   │   ├── __init__.py
│   │   └── database.py     # SQLite/JSON storage
│   ├── models/             # Data models
│   │   ├── __init__.py
│   │   └── lottery.py      # Pension lottery data classes
│   └── utils/              # Utilities
│       ├── __init__.py
│       └── logging_config.py
├── tests/
├── data/                   # Raw and processed data
├── pyproject.toml
└── AGENTS.md

## Build / Lint / Test Commands

### Installation
pip install -e .

### Testing
Run all tests: pytest
Run single test file: pytest tests/test_collector/test_fetcher.py
Run single test function: pytest tests/test_collector/test_fetcher.py::test_fetch_latest_round
Verbose output: pytest -v
With coverage: pytest --cov=src --cov-report=html

### Linting and Formatting
Format code: black src/ tests/
Lint code: ruff check src/ tests/
Type checking: mypy src/

## Code Style Guidelines

### Import Organization
1. Standard library
2. Third-party libraries
3. Local modules (relative imports)

### Naming Conventions
- Variables/functions: snake_case
- Classes: PascalCase
- Constants: UPPER_SNAKE_CASE
- Private methods: prefix with underscore
- Type hints: Always use for function signatures

### Error Handling
- Use specific exceptions with context
- Log errors with appropriate level
- NEVER use empty catch blocks

### Type Hints
Always use for function signatures.

### Documentation
All public functions require docstrings (Google style preferred).

### File Organization
- Maximum 300 lines per file
- Single responsibility principle
- Test files mirror src structure

## Rate Limiting Strategy (Critical)

### Why Rate Limiting Matters
The DHL Lottery website implements IP-based blocking. The site shows service access waiting message or blocks the IP entirely.

### Implementation Requirements

### 1. Request Delay (Required)
Minimum delay between requests: 2.0 seconds
Use exponential backoff on errors.

### 2. Session Management
- Reuse HTTP session for connection pooling
- Set appropriate headers (User-Agent, Accept)
- Implement circuit breaker pattern

### 3. Error Recovery
Detect rate limit errors and wait before retry.

### 4. Collection Strategy
- Collect data incrementally
- Save progress frequently
- Resume from last successful round on restart

### Recommended Settings
Normal: 2.0s delay, 3 retries, 2^n backoff
Historical bulk: 3.0s delay, 5 retries, 5^n backoff
Resume from error: 5.0s delay, 3 retries, fixed 30s backoff


## Data Collection Flow

### 1. Get Latest Round
From main page: https://dhlottery.co.kr/common.do?method=main
Parse: strong id=drwNo720 -> latest round number

### 2. Fetch Round Data (POST)
Endpoint: https://dhlottery.co.kr/gameResult.do?method=win720
POST data: Round=round_number
Returns: HTML with winning numbers

### 3. Parse Response
Extract:
- Round number (from strong tag)
- Draw date (from p class=desc)
- 1등 번호: 1조 + 6 digits
- 보너스 번호: 6 digits

### 4. Store Data
Save to SQLite/JSON after each successful fetch.
Schema: round_number, draw_date, group, numbers[], bonus_numbers[]

### 5. Progress Tracking
Track last successful round in separate file.
On restart: load last round, continue from next.

## Key Endpoints (Reference)

Purpose: Latest round
URL: https://dhlottery.co.kr/common.do?method=main
Method: GET

Purpose: Round results
URL: https://dhlottery.co.kr/gameResult.do?method=win720
Method: POST

## Common Issues and Solutions

Issue: IP blocked
Solution: Wait 1-2 hours, increase delay to 5s

Issue: 403 Forbidden
Solution: Check User-Agent header

Issue: HTML parse error
Solution: Site may have changed structure

## Testing Guidelines

### Unit Tests
- Mock HTTP responses
- Test parsing logic independently
- Test error handling paths

### Integration Tests (Slow)
- Mark slow tests with pytest.mark.slow
- Run separately: pytest -m not slow

## Performance Notes
- Single-threaded collection is sufficient
- Process ~400 rounds/hour with 2s delay
- Monitor IP status periodically

---
Generated for AI agent use. Update when project structure changes.

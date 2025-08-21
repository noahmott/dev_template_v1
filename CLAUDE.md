# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

### Development
```bash
# Run the application
python -m uvicorn app.main:app --reload

# Run all tests
python -m pytest tests/ -v

# Run tests with coverage
python -m pytest --cov=app --cov-report=term-missing --cov-fail-under=85

# Run specific test file
python -m pytest tests/test_healthz.py -v

# Run policy tests only
python -m pytest tests/policy/ -v
```

### Code Quality
```bash
# Lint code
ruff check .

# Format code
ruff format .

# Type checking
mypy app

# Security scan
bandit -r app
pip-audit -r requirements.txt --strict

# Pre-commit hooks (after setup)
pre-commit run --all-files
```

## Architecture Overview

This is a FastAPI-based Python 3.11 application following strict development rails and a hat-based development workflow.

### Core Structure
- **app/main.py**: FastAPI application entry point with `/healthz` endpoint
- **app/telemetry/logger.py**: JSON logging with ASCII-only output (no emojis)
- **tests/**: All test files including policy tests that enforce coding standards
- **docs/adr/ADR-000-rails.md**: Non-negotiable architecture constraints

### Development Workflow (Hat-Based Process)
When implementing features, follow this sequential process with ONE commit per hat:
1. **PLANNER** → Design and document the feature in docs/plan/
2. **TESTER** → Write tests first (TDD approach)
3. **SCAFFOLDER** → Create file structure
4. **IMPLEMENTER** → Write the implementation
5. **SECURITY** → Security review and hardening
6. **TELEMETRY** → Add logging and observability
7. **DOCS** → Complete documentation

### Critical Rails (Non-negotiables)
- **Logging**: JSON format, ASCII only (no emojis), with request_id/call_id
- **Testing**: Minimum 85% coverage, tests-first approach
- **Security**: No raw environment secrets (use Azure Key Vault)
- **Code Quality**: All code must pass ruff and mypy checks
- **Dependencies**: No new dependencies without justification
- **Observability**: OpenTelemetry ready for traces and metrics

### Restrictions
- DO NOT modify: `.github/`, `infra/`, `app/security/`
- Stop work if tests fail twice or if new dependencies are needed

### Testing Strategy
- Policy tests in `tests/policy/` enforce:
  - ASCII-only logging (no emojis)
  - No empty stub files
- All new features require tests written BEFORE implementation
- Coverage must remain ≥ 85%

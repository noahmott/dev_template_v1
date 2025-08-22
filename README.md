# FastAPI Development Template v1

[![Use this template](https://img.shields.io/badge/Use%20this-template-blue?style=for-the-badge)](https://github.com/noahmott/dev_template_v1/generate)

A production-ready FastAPI template with built-in best practices, testing infrastructure, and development workflow.

## Features

### Core Stack
- **Python 3.11** - Modern Python with latest features
- **FastAPI** - High-performance async web framework
- **Uvicorn** - Lightning-fast ASGI server
- **JSON Logging** - Structured logging with ASCII-only output (no emojis)
- **OpenTelemetry Ready** - Observability infrastructure

### Development Tools
- **Pre-commit Hooks** - Comprehensive automatic code quality checks
- **Ruff** - Fast Python linter and formatter
- **MyPy** - Strict static type checking
- **Pytest** - Comprehensive testing framework with coverage
- **Vulture** - Dead code detection
- **GitHub Actions** - CI/CD pipeline ready

### Security & Quality
- **Bandit** - Security vulnerability scanning
- **Pip-audit** - Dependency vulnerability scanning
- **85% Test Coverage Requirement** - Enforced in CI and pre-commit
- **Policy Tests** - Enforce coding standards (ASCII logs, no empty stubs)

## Project Structure

```
dev_template_v1/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry point
│   └── telemetry/
│       ├── __init__.py
│       └── logger.py        # JSON logging configuration
├── tests/
│   ├── policy/
│   │   ├── test_logs_ascii.py      # Enforce ASCII-only logging
│   │   └── test_no_empty_stubs.py  # Prevent empty stub files
│   ├── test_healthz.py              # Health endpoint tests
│   └── test_logger.py               # Logger tests
├── docs/
│   ├── adr/
│   │   └── ADR-000-rails.md        # Architecture decisions & constraints
│   ├── plan/                        # Feature planning documents
│   └── security/                    # Security reviews
├── scripts/
│   └── claude_kickoff.txt          # Development workflow guide
├── .claude/
│   ├── agents/
│   │   ├── docs.md                 # Documentation agent
│   │   ├── implementer.md          # Implementation agent
│   │   ├── orchestrator.md         # Pipeline orchestrator
│   │   ├── planner.md              # Planning agent
│   │   ├── scaffolder.md           # Scaffolding agent
│   │   ├── security.md             # Security agent
│   │   ├── telemetry.md            # Telemetry agent
│   │   └── tester.md               # Testing agent
│   └── settings.json                # Claude-specific settings
├── .github/
│   └── workflows/
│       └── ci.yml                   # GitHub Actions CI pipeline
├── .pre-commit-config.yaml          # Pre-commit hooks configuration
├── pyproject.toml                   # Python project configuration
├── requirements.txt                 # Production dependencies
└── requirements-dev.txt            # Development dependencies
```

## Quick Start

### Prerequisites
- Python 3.11+
- Git

### Setup

1. **Clone the template**
   ```bash
   git clone https://github.com/noahmott/dev_template_v1.git my-new-project
   cd my-new-project
   ```

2. **Remove template origin and set your own**
   ```bash
   git remote remove origin
   git remote add origin https://github.com/yourusername/your-new-repo.git
   ```

3. **Create virtual environment**
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # Linux/Mac
   source .venv/bin/activate
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

5. **Setup pre-commit hooks**
   ```bash
   pre-commit install
   ```

6. **Run the application**
   ```bash
   python -m uvicorn app.main:app --reload
   ```

7. **Run tests**
   ```bash
   python -m pytest tests/ -v
   ```

## Development Workflow

This template includes a structured development workflow with AI agents and orchestration:

### AI-Powered Development Agents
The `.claude/agents/` directory contains specialized agents for each development phase:
- **orchestrator.md** - Coordinates the entire development pipeline with quality gates
- **planner.md** - Designs features and creates planning documents
- **tester.md** - Writes comprehensive test suites following TDD
- **scaffolder.md** - Creates file structure and interfaces
- **implementer.md** - Writes production code
- **security.md** - Performs security analysis and hardening
- **telemetry.md** - Adds observability and monitoring
- **docs.md** - Creates architecture decision records (ADRs)

### Hat-Based Development Process
Work through features using sequential "hats" with one commit per hat:

1. **PLANNER** → Design and document the feature
2. **TESTER** → Write tests first (TDD approach)
3. **SCAFFOLDER** → Create file structure
4. **IMPLEMENTER** → Write the implementation
5. **SECURITY** → Security review and hardening
6. **TELEMETRY** → Add logging and observability
7. **DOCS** → Complete documentation

### Rails (Non-negotiables)
See `docs/adr/ADR-000-rails.md` for architecture constraints:
- JSON logging with ASCII only (no emojis)
- Minimum 85% test coverage
- No raw environment secrets (use Azure Key Vault or similar)
- All code must pass ruff, mypy, bandit, and vulture checks
- Tests first approach (TDD)
- No dead code allowed

## API Endpoints

### Health Check
- **GET** `/healthz` - Returns `{"status": "ok"}` when service is healthy

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_healthz.py -v

# Run policy tests only
pytest tests/policy/ -v
```

## Configuration

### Linting & Formatting (pyproject.toml)
```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
python_version = "3.11"
strict = true
```

### Pre-commit Hooks
The template includes comprehensive pre-commit hooks that run automatically:
- **Ruff** - Python linting and auto-formatting
- **MyPy** - Strict type checking with FastAPI support
- **Bandit** - Security vulnerability scanning (skips test assertions)
- **Vulture** - Dead code detection (80% confidence threshold)
- **Pytest** - Runs tests on Python file changes
- **File validators** - YAML, JSON, TOML syntax checking
- **Code hygiene** - EOL fixer, trailing whitespace, merge conflicts
- **Security** - Detect private keys, large files

## CI/CD

GitHub Actions workflow (`.github/workflows/ci.yml`) runs on every push and PR:
- Dependency installation
- Linting (ruff)
- Type checking (mypy)
- Security scanning (bandit, pip-audit)
- Test execution with coverage reporting
- Coverage threshold enforcement (85%)

## Customization Guide

### Adding New Features
1. Create a feature branch: `git checkout -b feat/feature-name`
2. Follow the hat-based workflow in `scripts/claude_kickoff.txt`
3. Ensure all tests pass
4. Create a pull request

### Modifying the Template
- **Dependencies**: Update `requirements.txt` and document why
- **Configuration**: Adjust `pyproject.toml` for linting rules
- **CI/CD**: Modify `.github/workflows/ci.yml`
- **Logging**: Extend `app/telemetry/logger.py`

### Extending the API
1. Add new routers in `app/routers/`
2. Register in `app/main.py`
3. Write tests in `tests/`
4. Document endpoints in README

## Environment Variables

Create a `.env` file for local development (never commit this):
```env
# Example environment variables
LOG_LEVEL=INFO
```

## Production Deployment

### Recommendations
- Use environment-specific configuration
- Implement proper secret management (Azure Key Vault, AWS Secrets Manager, etc.)
- Set up monitoring and alerting
- Configure rate limiting and CORS
- Add authentication/authorization as needed
- Set up database connections with connection pooling

### Docker Support (Optional)
Create a `Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Follow the development workflow
4. Ensure all tests pass
5. Submit a pull request

## License

[Your License Here]

## Support

For issues with the template, please open an issue on GitHub.

---

Built with discipline and best practices in mind. Ready for production use.

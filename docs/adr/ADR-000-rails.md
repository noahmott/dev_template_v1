# ADR-000 Rails (non-negotiables)
- Stack: Python 3.11, FastAPI
- Secrets: Azure Key Vault (no raw env secrets)
- Logging: JSON, ASCII only (no emoji), request_id/call_id
- Observability: OpenTelemetry traces + key metrics
- Security: SAST, dep scan, secret scan on every PR
- Contracts: tests first; coverage ≥ 85%; no new deps without justification

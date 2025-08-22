# Orchestrator Agent

Execute development cycle with feedback loops and quality gates.
Coordinates all agents in deterministic sequence with rollback capability.

## Execution Pipeline

### 1. PLANNING PHASE
- Run planner.md → outputs docs/plan/<TICKET>.md
- Validate: plan includes config vs code decisions, public interfaces defined
- Gate: mini threat table exists with ≥1 entry per asset
- Rollback point: git commit

### 2. TEST DEFINITION PHASE
- Run tester.md → outputs tests/
- Validate: tests cover all ACs from ticket, policy tests exist
- Gate: pytest --collect-only succeeds
- Rollback point: git commit

### 3. SCAFFOLDING PHASE
- Run scaffolder.md → creates minimal stubs
- Validate: all files from plan exist, no empty files
- Gate: ruff check && mypy app/ --ignore-missing-imports
- Rollback point: git commit

### 4. IMPLEMENTATION PHASE
- Run implementer.md → implements business logic
- Validate: all tests pass, no new deps without justification
- Gate: pytest && ruff format --check && mypy app/ && vulture app/
- Coverage gate: pytest --cov=app --cov-report=term --cov-fail-under=85
- Rollback: if tests fail after 2 attempts, flag plan for revision

### 5. SECURITY PHASE
- Run security.md → updates threat model
- Validate: SAST config exists, secret scanning enabled
- Gate: bandit -r app/ && pip-audit
- Gate: no PII in logs (grep -r 'email\|ssn\|password' app/logs/)
- Gate: no secrets in code (no raw env secrets per ADR-000)

### 6. TELEMETRY PHASE
- Run telemetry.md → adds observability
- Validate: spans exist for all public interfaces
- Validate: request_id/call_id in all logs (per ADR-000)
- Gate: metrics defined for SLI (latency p99 < 100ms)
- Gate: JSON logging format, ASCII only (no emoji)

### 7. DOCUMENTATION PHASE
- Run docs.md → writes ADR
- Validate: ADR is 350-450 words, upgrade path documented
- Gate: docs/adr/ADR-*.md exists with latency targets
- Gate: justification for any new dependencies

## Feedback Mechanisms

### Implementation Failures (Step 4)
- After 2 failed attempts, create docs/feedback/<TICKET>-impl.md
- Contains: failed tests, missing interfaces, suggested plan changes
- Restart from Step 1 with feedback file as additional input

### Performance Regression (Step 6)
- If p99 > 100ms, create performance report
- Choose: optimize implementation OR update ADR with justified targets
- Max 3 optimization cycles before escalation

### Security Findings (Step 5)
- Critical findings halt pipeline
- Generate docs/security/<TICKET>-block.md with remediation required
- Resume only after security approval signature

## Integration Points

**Input**: ticket.md with acceptance criteria
**Output**: merged PR with all artifacts

**Config Override** (optional):
```yaml
# .claude/pipeline.yaml
orchestrator:
  max_retries: 2
  latency_target_ms: 100
  security_block_on_critical: true
  rollback_on_test_failure: true
  require_integration_tests: false
  coverage_threshold: 85
```

## State Management

Track progress in .claude/state/<TICKET>.json:
```json
{
  "ticket": "PROJ-123",
  "current_phase": "implementation",
  "attempt": 1,
  "gates_passed": ["planning", "test_definition", "scaffolding"],
  "rollback_points": {
    "planning": "git:abc123",
    "test_definition": "git:bcd234",
    "scaffolding": "git:cde345",
    "pre_implementation": "git:def456"
  },
  "metrics": {
    "total_duration_seconds": 234,
    "test_count": 47,
    "coverage_percent": 92,
    "vulture_dead_code_count": 0
  }
}
```

## Failure Recovery

On any gate failure:
1. Save current state to .claude/state/<TICKET>.json
2. Generate failure report with specific remediation
3. If retriable: increment attempt counter and retry
4. If not retriable: create manual intervention ticket
5. Preserve git commits at each phase for rollback

## Success Criteria

Pipeline succeeds when:
- All 7 phases complete without rollback
- Zero critical security findings (bandit high severity)
- Test coverage ≥ 85% (per ADR-000)
- No dead code detected by vulture
- p99 latency < configured target
- ADR approved (if manual review configured)
- No non-ASCII in log literals
- All public interfaces have telemetry with request_id/call_id
- Azure Key Vault integration for secrets (no raw env)
- Python 3.11 + FastAPI stack compliance

## Manual Intervention Triggers

Stop and await human input when:
- New dependency requires architectural review (per ADR-000)
- Security critical finding detected (bandit high/critical)
- Performance regression > 50% from baseline
- Test coverage drops below 85%
- Implementation fails 3x with different approaches
- Dead code detected that cannot be auto-removed
- Raw environment secrets detected (violates ADR-000)

## Monitoring

Emit metrics for pipeline optimization:
- Phase duration (histogram per phase)
- Failure rate (counter per phase)
- Rollback frequency (counter)
- Time to successful merge (histogram)
- Agent retry attempts (counter per agent)
- Dead code detection rate (gauge)
- Coverage percentage (gauge)
- Security finding severity distribution (counter by level)

## Quality Gates Summary

Each phase must pass these checks:
- **ruff check**: code style and linting
- **ruff format --check**: formatting compliance
- **mypy app/ --strict**: type checking
- **pytest**: all tests pass
- **pytest --cov-fail-under=85**: coverage threshold
- **vulture app/**: no dead code
- **bandit -r app/**: security scanning
- **pip-audit**: dependency vulnerabilities
- **JSON logs with ASCII only**: observability compliance
- **OpenTelemetry traces**: telemetry compliance
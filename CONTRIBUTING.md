# Contributing to django-tenant-authx

Thank you for your interest in contributing to `django-tenant-authx`! We welcome contributions from everyone.

## Getting Started

1. **Fork the repository** on GitHub.
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/kkrajid/django-tenant-authx.git
   cd django-tenant-authx
   ```
3. **Set up a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
4. **Install dependencies**:
   ```bash
   pip install -e ".[dev,drf]"
   ```

## Running Tests

We use `tox` to run tests across multiple environments.

```bash
# Run all tests
tox

# Run only unit tests
pytest tests/

# Run security audit
python tests/security_audit.py
```

## Development Standards

- **Code Style**: We use `black` and `isort`. Run `tox -e lint` to check.
- **Type Hints**: All new code must be fully typed. Run `tox -e typecheck` to verify.
- **Tests**: New features must include tests. We encourage property-based testing with Hypothesis.

## Pull Request Process

1. Create a new branch for your feature or fix.
2. Write tests covering your changes.
3. Ensure all tests pass matching the project standards.
4. Update the documentation if necessary.
5. Submit a Pull Request with a clear description of the changes.

## Code of Conduct

Please note that this project is released with a [Code of Conduct](CODE_OF_CONDUCT.md). By participating in this project you agree to abide by its terms.

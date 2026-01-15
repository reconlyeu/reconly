"""E2E tests for Reconly.

These tests require network access and external services.
They are marked with @pytest.mark.e2e and @pytest.mark.slow.

To run only E2E tests:
    pytest tests/e2e/ -v -s

To skip E2E tests in CI:
    pytest -m "not e2e"
"""

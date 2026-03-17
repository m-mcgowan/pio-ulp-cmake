"""PlatformIO custom test runner — uses pio-test-runner for orchestration.

Requires pio-test-runner: pip install -e <path-to-pio-test-runner>
"""

try:
    from pio_test_runner import EmbeddedTestRunner

    class CustomTestRunner(EmbeddedTestRunner):
        pass

except ImportError:
    # Fallback for compile-only builds where pio-test-runner is not installed.
    from platformio.test.runners.doctest import DoctestTestRunner as CustomTestRunner  # noqa: F401

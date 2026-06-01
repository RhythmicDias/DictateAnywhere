# Contributing to DictateAnywhere

Thank you for your interest in contributing to DictateAnywhere! We welcome contributions from everyone.

## Reporting Bugs

Before submitting a bug report, please check the [ISSUES.md](ISSUES.md) tracker to make sure it hasn't been resolved recently.

If the bug is new, please open an issue on GitHub with:
- A clear, descriptive title.
- Steps to reproduce the issue.
- Expected behavior vs. what actually happened.
- Your OS version and configuration (e.g. engine mode, device, compute type).

## Suggesting Features

If you have an idea for a feature or enhancement:
- Open a GitHub issue outlining your suggestion.
- Explain the use case and how it benefits the application.
- Use the `enhancement` label.

## Pull Requests

1. Fork the repository and create your feature branch: `git checkout -b feature/your-feature-name`
2. Implement your changes. Make sure to adhere to type hints and include docstrings.
3. Run the test suite using `scripts\test.bat` (or `pytest`) to verify no regressions.
4. Keep your changes focused. Open a pull request describing the changes and why they are necessary.

## Code Style

- Follow Python's PEP 8 guidelines.
- Always add type signatures to new functions and methods.
- Document any public APIs with descriptive docstrings.
- Avoid using `print()` statements; use the built-in `logger` for telemetry.

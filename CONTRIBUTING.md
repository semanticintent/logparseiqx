# Contributing to LogParseIQX

Thank you for your interest in contributing to LogParseIQX! This document provides guidelines and information for contributors.

## Getting Started

### Development Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/logparseiqx.git
   cd logparseiqx
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install in development mode**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Install Ollama and pull a model**
   ```bash
   ollama pull qwen2.5:3b
   ollama serve
   ```

### Running Tests

```bash
pytest tests/ -v
```

### Code Style

We use standard Python conventions:
- Line length: 100 characters
- Use type hints where practical
- Docstrings for public functions

Run linting:
```bash
ruff check src/
black --check src/
```

Format code:
```bash
black src/
ruff check --fix src/
```

## How to Contribute

### Reporting Bugs

1. Check if the issue already exists in [GitHub Issues](https://github.com/semanticintent/logparseiqx/issues)
2. If not, create a new issue with:
   - Clear description of the problem
   - Steps to reproduce
   - Expected vs actual behavior
   - Your environment (OS, Python version, Ollama version)

### Suggesting Features

Open an issue with:
- Clear description of the feature
- Use case / why it would be useful
- Any implementation ideas (optional)

### Pull Requests

1. **Create a branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write clear commit messages
   - Add tests for new functionality
   - Update documentation if needed

3. **Test your changes**
   ```bash
   pytest tests/ -v
   ```

4. **Submit a PR**
   - Reference any related issues
   - Describe what your PR does
   - Keep PRs focused on a single change

## Adding New Log Parsers

We welcome new log format parsers! Here's how to add one:

### 1. Create the parser module

Create `src/logparseiqx/parsers/your_format.py`:

```python
"""
Your Format log parsing utilities for LogParseIQX
"""

from typing import Dict, Any, List, Callable

def parse_line(line: str) -> Dict[str, Any]:
    """Parse a single log line"""
    # Your parsing logic here
    pass

def filter_logs(filepath: str, tail: int, filter_func: Callable) -> List[Dict]:
    """Read and filter logs"""
    # Your filtering logic here
    pass

def format_compact(log: Dict[str, Any]) -> str:
    """Format log entry compactly for LLM context"""
    # Reduce fields to essentials
    pass

# Add filter functions
def filter_errors(log: Dict[str, Any]) -> bool:
    """Filter for error entries"""
    pass
```

### 2. Add CLI commands

In `src/logparseiqx/cli.py`, add a new command group:

```python
@cli.group()
def yourformat():
    """Your Format log commands"""
    pass

@yourformat.command('errors')
@click.argument('logfile', type=click.Path(exists=True))
@click.pass_context
def yourformat_errors(ctx, logfile):
    """Find errors in Your Format logs"""
    # Implementation
    pass
```

### 3. Add tests

Create `tests/test_your_format.py`:

```python
import pytest
from logparseiqx.parsers.your_format import parse_line, filter_errors

class TestYourFormat:
    def test_parse_valid_line(self):
        # Test parsing
        pass

    def test_filter_errors(self):
        # Test filtering
        pass
```

### 4. Update documentation

- Add examples to README.md
- Document any new environment variables or configuration

## Code Organization

```
src/logparseiqx/
├── __init__.py          # Version and constants
├── __main__.py          # Entry point for python -m
├── cli.py               # All CLI commands
├── parsers/
│   ├── __init__.py      # Generic utilities (read_log_file, etc.)
│   ├── cloudflare.py    # Cloudflare-specific parsing
│   └── your_format.py   # Your new parser
└── utils/
    └── __init__.py      # Ollama integration
```

## Guidelines

### Do
- Keep the CLI user-friendly
- Pre-filter logs before sending to LLM (reduce tokens)
- Write compact formatters (fewer fields = faster inference)
- Add helpful error messages
- Test on Windows, macOS, and Linux if possible

### Don't
- Add features that require cloud APIs
- Break existing CLI commands
- Add heavy dependencies
- Commit sensitive data or API keys

## Questions?

- Open an issue for questions
- Tag it with `question` label

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

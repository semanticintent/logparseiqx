# LogParseIQX

[![Tests](https://github.com/semanticintent/logparseiqx/actions/workflows/test.yml/badge.svg)](https://github.com/semanticintent/logparseiqx/actions/workflows/test.yml)
[![Coverage](https://img.shields.io/badge/coverage-91%25-brightgreen)](https://github.com/semanticintent/logparseiqx)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **"Like cloud AI log parsing but $0"**
>
> *grep with intelligence*

A local CLI log parser powered by [Ollama](https://ollama.com). Runs entirely on your machine. No tokens. No API costs. Just results.

Part of [Millpond AI](https://millpond.ai).

---

## Features

- **Generic log parsing** - Works with any log format
- **Cloudflare-specific commands** - Pre-filtered for efficiency
- **Local LLM powered** - Uses Ollama (Qwen, Mistral, Phi-3, etc.)
- **$0 cost** - No API fees, no token limits
- **Smart pre-filtering** - Reduces context before sending to LLM
- **Beautiful CLI** - Rich terminal output

---

## Installation

### Prerequisites

1. **Install Ollama**
   ```bash
   # Windows
   winget install Ollama.Ollama

   # macOS
   brew install ollama

   # Linux
   curl -fsSL https://ollama.com/install.sh | sh
   ```

2. **Pull a model**
   ```bash
   # Lightweight (recommended for 8GB RAM)
   ollama pull qwen2.5:3b

   # Better quality (needs more RAM)
   ollama pull mistral:7b
   ```

3. **Start Ollama**
   ```bash
   ollama serve
   ```

### Install LogParseIQX

```bash
# Clone the repo
git clone https://github.com/semanticintent/logparseiqx.git
cd logparseiqx

# Install in editable mode
pip install -e .

# Verify installation
logparseiqx --version
```

Or install directly from GitHub:

```bash
pip install git+https://github.com/semanticintent/logparseiqx.git
```

---

## Usage

### Quick Start

```bash
# Parse any log file
logparseiqx parse application.log

# Find errors
logparseiqx errors server.log

# Ask a specific question
logparseiqx parse app.log -q "Why did it crash?"

# Use short alias
lpx parse app.log
```

### Generic Commands

```bash
# Parse and explain a log file
logparseiqx parse <logfile>
logparseiqx parse <logfile> --question "What happened at 3pm?"
logparseiqx parse <logfile> --tail 500  # Last 500 lines only

# Summarize a log file
logparseiqx summarize <logfile>

# Find and explain errors
logparseiqx errors <logfile>

# Deep analysis (patterns, anomalies, timeline)
logparseiqx analyze <logfile>

# Ask anything
logparseiqx ask "What does a 502 error mean?"
```

### Cloudflare Commands

Specialized commands for Cloudflare JSON logs with smart pre-filtering:

```bash
# Find HTTP errors (4xx, 5xx)
logparseiqx cf errors cloudflare.log
logparseiqx cf errors cloudflare.log --status 502  # Only 502s

# Find slow requests
logparseiqx cf slow cloudflare.log
logparseiqx cf slow cloudflare.log --threshold 2000  # >2 seconds

# Security events (WAF, threats, blocks)
logparseiqx cf security cloudflare.log
logparseiqx cf security cloudflare.log --threat-score 20

# Top requesting IPs (find bots/abuse)
logparseiqx cf top-ips cloudflare.log --limit 30

# Quick traffic summary
logparseiqx cf summary cloudflare.log
```

### Other Commands

```bash
# List available models
logparseiqx models

# See cost comparison
logparseiqx cost

# Use a different model
logparseiqx --model mistral:7b parse app.log
lpx -m phi3:mini errors server.log
```

---

## Cost Comparison

| Service | Cost/1M tokens | 500MB log file |
|---------|----------------|----------------|
| Cloud AI APIs | $15-90 | $437-$2,625 |
| **LogParseIQX (local)** | $0 | **$0** |

The savings add up quickly when parsing logs regularly.

---

## How Cloudflare Filtering Works

The key to efficient log parsing is reducing context before sending to the LLM:

```
Raw Cloudflare Log (50+ fields, 1000s of lines)
                    |
                    v
        PRE-FILTER (Python) - No LLM needed
        * Only 4xx/5xx errors
        * Only slow requests
        * Only security events
                    |
                    v
        COMPACT FORMAT (50 fields -> 6 fields)
        timestamp|method|uri|status|IP|ray_id
                    |
                    v
        Local LLM (small context, fast)
                    |
                    v
        Actionable insights
```

---

## Recommended Models

For **8GB RAM** (CPU inference):

| Model | Size | Speed | Quality | Command |
|-------|------|-------|---------|---------|
| **Qwen 2.5 3B** | ~2GB | Fast | Good | `ollama pull qwen2.5:3b` |
| Phi-3 Mini | ~2.3GB | Fast | Good | `ollama pull phi3:mini` |
| Mistral 7B Q4 | ~4GB | Medium | Better | `ollama pull mistral:7b-instruct-q4_K_M` |

For **16GB+ RAM**:

| Model | Size | Quality | Command |
|-------|------|---------|---------|
| Qwen 2.5 7B | ~4.5GB | Great | `ollama pull qwen2.5:7b` |
| DeepSeek R1 8B | ~5GB | Excellent | `ollama pull deepseek-r1:8b` |
| Mistral 7B | ~4GB | Excellent | `ollama pull mistral:7b` |

---

## Project Structure

```
logparseiqx/
├── pyproject.toml           # Package configuration
├── README.md
├── LICENSE
├── src/
│   └── logparseiqx/
│       ├── __init__.py      # Version, banner
│       ├── __main__.py      # python -m entry point
│       ├── cli.py           # Main CLI commands
│       ├── parsers/
│       │   ├── __init__.py  # Generic log utilities
│       │   └── cloudflare.py # Cloudflare-specific
│       └── utils/
│           └── __init__.py  # Ollama integration
└── tests/
```

---

## Configuration

### Change default model

```bash
# Per-command
logparseiqx --model mistral:7b parse app.log

# Or set environment variable
export LOGPARSEIQX_MODEL=mistral:7b
```

### Store models on external SSD

```bash
# Set Ollama model storage location
export OLLAMA_MODELS=/path/to/external/ssd/ollama/models
```

---

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Ideas for future parsers:

- [ ] Nginx access logs
- [ ] Apache logs
- [ ] AWS CloudWatch
- [ ] Docker/Kubernetes logs
- [ ] Application-specific (Rails, Django, Express)

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Credits

- [Ollama](https://ollama.com) - Local LLM runtime
- [Click](https://click.palletsprojects.com/) - CLI framework
- [Rich](https://rich.readthedocs.io/) - Beautiful terminal output

---

## Links

- **Website**: [millpond.ai](https://millpond.ai)
- **GitHub**: [github.com/semanticintent/logparseiqx](https://github.com/semanticintent/logparseiqx)
- **Issues**: [Report bugs or request features](https://github.com/semanticintent/logparseiqx/issues)

---

<p align="center">
  <b>Part of Millpond AI</b>
</p>

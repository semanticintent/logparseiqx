# Changelog

All notable changes to LogParseIQX will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-01-03

### Added
- Initial release of LogParseIQX
- Core CLI commands: `parse`, `summarize`, `errors`, `analyze`, `ask`
- Cloudflare-specific commands: `cf errors`, `cf slow`, `cf security`, `cf top-ips`, `cf summary`
- Smart pre-filtering to minimize token usage
- Support for custom Ollama models via `--model` flag
- Rich terminal output with tables and colored text
- 91% test coverage with mocked Ollama tests

### Features
- Parse any log file with natural language questions
- Cloudflare JSON log parsing with automatic field extraction
- Aggregation by status code, IP, country, URI, and WAF action
- Performance analysis for slow requests
- Security event detection (WAF blocks, high threat scores)

[0.1.0]: https://github.com/semanticintent/logparseiqx/releases/tag/v0.1.0

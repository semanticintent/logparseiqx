"""
Basic tests for LogParseIQX
"""

import pytest
from click.testing import CliRunner

from logparseiqx import __version__
from logparseiqx.cli import cli
from logparseiqx.parsers import chunk_text, filter_lines
from logparseiqx.parsers.cloudflare import (
    parse_cloudflare_line,
    filter_errors,
    filter_slow_requests,
    aggregate_by_status,
)


class TestVersion:
    """Test version info"""
    
    def test_version_exists(self):
        assert __version__ is not None
        assert len(__version__) > 0
    
    def test_version_format(self):
        parts = __version__.split('.')
        assert len(parts) >= 2


class TestCLI:
    """Test CLI commands"""
    
    def test_cli_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert 'LogParseIQX' in result.output
    
    def test_cli_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ['--version'])
        assert result.exit_code == 0
        assert __version__ in result.output
    
    def test_cost_command(self):
        runner = CliRunner()
        result = runner.invoke(cli, ['cost'])
        assert result.exit_code == 0
        assert '$0' in result.output
        assert 'Opus' in result.output


class TestParsers:
    """Test parsing utilities"""
    
    def test_chunk_text_small(self):
        text = "line1\nline2\nline3"
        chunks = chunk_text(text, size=100)
        assert len(chunks) == 1
        assert chunks[0] == text
    
    def test_chunk_text_large(self):
        text = "a" * 100 + "\n" + "b" * 100
        chunks = chunk_text(text, size=50)
        assert len(chunks) > 1
    
    def test_filter_lines_basic(self):
        content = "INFO: all good\nERROR: something failed\nWARN: be careful"
        matches = filter_lines(content, ['error', 'fail'])
        assert len(matches) == 1
        assert 'ERROR' in matches[0]
    
    def test_filter_lines_case_insensitive(self):
        content = "Error: test\nERROR: test2\nerror: test3"
        matches = filter_lines(content, ['error'], case_sensitive=False)
        assert len(matches) == 3


class TestCloudflare:
    """Test Cloudflare-specific parsing"""
    
    def test_parse_valid_line(self):
        line = '{"EdgeResponseStatus": 200, "ClientIP": "1.2.3.4"}'
        result = parse_cloudflare_line(line)
        assert result is not None
        assert result['EdgeResponseStatus'] == 200
    
    def test_parse_invalid_line(self):
        result = parse_cloudflare_line("not json")
        assert result is None
    
    def test_filter_errors_500(self):
        log = {'EdgeResponseStatus': 500}
        assert filter_errors(log) is True
    
    def test_filter_errors_200(self):
        log = {'EdgeResponseStatus': 200}
        assert filter_errors(log) is False
    
    def test_filter_errors_404(self):
        log = {'EdgeResponseStatus': 404}
        assert filter_errors(log) is True
    
    def test_filter_slow_requests(self):
        filter_func = filter_slow_requests(1000)
        assert filter_func({'OriginResponseTime': 2000}) is True
        assert filter_func({'OriginResponseTime': 500}) is False
    
    def test_aggregate_by_status(self):
        logs = [
            {'EdgeResponseStatus': 200},
            {'EdgeResponseStatus': 200},
            {'EdgeResponseStatus': 404},
            {'EdgeResponseStatus': 500},
        ]
        result = aggregate_by_status(logs)
        assert result[200] == 2
        assert result[404] == 1
        assert result[500] == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

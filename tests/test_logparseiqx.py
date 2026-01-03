"""
Comprehensive tests for LogParseIQX with mocked Ollama
"""

import os
import sys
import json
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from logparseiqx import __version__, BANNER, TAGLINE


# Helper for Windows temp file cleanup
def safe_unlink(filepath):
    """Safely delete a file, ignoring permission errors on Windows"""
    try:
        os.unlink(filepath)
    except PermissionError:
        pass  # Windows file locking - file will be cleaned up later
from logparseiqx.cli import cli
from logparseiqx.parsers import (
    chunk_text,
    filter_lines,
    read_log_file,
    get_file_stats,
    CHUNK_SIZE
)
from logparseiqx.parsers.cloudflare import (
    parse_cloudflare_line,
    filter_cloudflare_logs,
    filter_errors,
    filter_server_errors,
    filter_client_errors,
    filter_by_status,
    filter_slow_requests,
    filter_security_events,
    filter_by_country,
    filter_by_ip,
    aggregate_by_status,
    aggregate_by_country,
    aggregate_by_ip,
    aggregate_by_uri,
    aggregate_by_waf_action,
    calculate_stats,
    format_cf_log_compact,
    format_cf_security_compact,
    format_cf_performance_compact,
)
from logparseiqx.utils import (
    check_ollama,
    get_available_models,
    ensure_ollama_running,
    query_ollama,
    model_info,
    DEFAULT_MODEL,
    OLLAMA_BASE_URL,
)


# =============================================================================
# VERSION AND PACKAGE TESTS
# =============================================================================

class TestVersion:
    """Test version info"""

    def test_version_exists(self):
        assert __version__ is not None
        assert len(__version__) > 0

    def test_version_format(self):
        parts = __version__.split('.')
        assert len(parts) >= 2
        # Each part should be numeric
        for part in parts:
            assert part.isdigit()

    def test_banner_exists(self):
        assert BANNER is not None
        assert len(BANNER) > 0  # Banner is non-empty
        assert 'IQX' in BANNER or 'Parse' in BANNER or '___' in BANNER  # Has ASCII art

    def test_tagline_exists(self):
        assert TAGLINE is not None
        assert '$0' in TAGLINE


# =============================================================================
# OLLAMA UTILS TESTS (MOCKED)
# =============================================================================

class TestOllamaUtils:
    """Test Ollama integration with mocked requests"""

    @patch('logparseiqx.utils.requests.get')
    def test_check_ollama_running(self, mock_get):
        """Test check_ollama when Ollama is running"""
        mock_get.return_value.status_code = 200
        assert check_ollama() is True
        mock_get.assert_called_once()

    @patch('logparseiqx.utils.requests.get')
    def test_check_ollama_not_running(self, mock_get):
        """Test check_ollama when Ollama is not running"""
        from requests.exceptions import ConnectionError
        mock_get.side_effect = ConnectionError()
        assert check_ollama() is False

    @patch('logparseiqx.utils.requests.get')
    def test_check_ollama_error(self, mock_get):
        """Test check_ollama with unexpected error"""
        mock_get.side_effect = Exception("Unexpected error")
        assert check_ollama() is False

    @patch('logparseiqx.utils.requests.get')
    def test_get_available_models_success(self, mock_get):
        """Test getting available models"""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "models": [
                {"name": "qwen2.5:3b"},
                {"name": "mistral:7b"},
                {"name": "phi3:mini"}
            ]
        }
        models = get_available_models()
        assert len(models) == 3
        assert "qwen2.5:3b" in models
        assert "mistral:7b" in models

    @patch('logparseiqx.utils.requests.get')
    def test_get_available_models_empty(self, mock_get):
        """Test getting models when none installed"""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": []}
        models = get_available_models()
        assert models == []

    @patch('logparseiqx.utils.requests.get')
    def test_get_available_models_connection_error(self, mock_get):
        """Test getting models when Ollama not running"""
        from requests.exceptions import ConnectionError
        mock_get.side_effect = ConnectionError()
        models = get_available_models()
        assert models == []

    @patch('logparseiqx.utils.check_ollama')
    def test_ensure_ollama_running_success(self, mock_check):
        """Test ensure_ollama_running when running"""
        mock_check.return_value = True
        # Should not raise or exit
        ensure_ollama_running()

    @patch('logparseiqx.utils.check_ollama')
    def test_ensure_ollama_running_failure(self, mock_check):
        """Test ensure_ollama_running when not running"""
        mock_check.return_value = False
        with pytest.raises(SystemExit) as exc_info:
            ensure_ollama_running()
        assert exc_info.value.code == 1

    @patch('logparseiqx.utils.requests.post')
    def test_query_ollama_stream(self, mock_post):
        """Test query_ollama with streaming response"""
        # Mock streaming response
        mock_response = MagicMock()
        mock_response.iter_lines.return_value = [
            json.dumps({"response": "Hello ", "done": False}).encode(),
            json.dumps({"response": "World!", "done": True}).encode(),
        ]
        mock_post.return_value = mock_response

        result = query_ollama("Test prompt", stream=True)
        assert "Hello " in result
        assert "World!" in result

    @patch('logparseiqx.utils.requests.post')
    def test_query_ollama_no_stream(self, mock_post):
        """Test query_ollama without streaming"""
        mock_post.return_value.json.return_value = {
            "response": "This is a test response"
        }

        result = query_ollama("Test prompt", stream=False)
        assert result == "This is a test response"

    @patch('logparseiqx.utils.requests.post')
    def test_query_ollama_connection_error(self, mock_post):
        """Test query_ollama when connection fails"""
        from requests.exceptions import ConnectionError
        mock_post.side_effect = ConnectionError()

        with pytest.raises(SystemExit) as exc_info:
            query_ollama("Test prompt")
        assert exc_info.value.code == 1

    @patch('logparseiqx.utils.requests.post')
    def test_query_ollama_timeout(self, mock_post):
        """Test query_ollama when request times out"""
        from requests.exceptions import Timeout
        mock_post.side_effect = Timeout()

        with pytest.raises(SystemExit) as exc_info:
            query_ollama("Test prompt")
        assert exc_info.value.code == 1

    @patch('logparseiqx.utils.requests.post')
    def test_model_info_success(self, mock_post):
        """Test getting model info"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "modelfile": "FROM mistral",
            "parameters": "num_ctx 4096"
        }

        info = model_info("mistral:7b")
        assert "modelfile" in info

    @patch('logparseiqx.utils.requests.post')
    def test_model_info_failure(self, mock_post):
        """Test model_info when request fails"""
        mock_post.side_effect = Exception("Error")
        info = model_info("invalid:model")
        assert info == {}


# =============================================================================
# PARSER TESTS WITH TEMP FILES
# =============================================================================

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

    def test_chunk_text_no_newlines(self):
        """Test chunking text without newlines"""
        text = "a" * 200
        chunks = chunk_text(text, size=50)
        assert len(chunks) == 4
        for chunk in chunks:
            assert len(chunk) <= 50

    def test_chunk_text_empty(self):
        """Test chunking empty text"""
        chunks = chunk_text("")
        assert chunks == []

    def test_filter_lines_basic(self):
        content = "INFO: all good\nERROR: something failed\nWARN: be careful"
        matches = filter_lines(content, ['error', 'fail'])
        assert len(matches) == 1
        assert 'ERROR' in matches[0]

    def test_filter_lines_case_insensitive(self):
        content = "Error: test\nERROR: test2\nerror: test3"
        matches = filter_lines(content, ['error'], case_sensitive=False)
        assert len(matches) == 3

    def test_filter_lines_case_sensitive(self):
        content = "Error: test\nERROR: test2\nerror: test3"
        matches = filter_lines(content, ['ERROR'], case_sensitive=True)
        assert len(matches) == 1
        assert 'ERROR: test2' in matches[0]

    def test_filter_lines_multiple_keywords(self):
        content = "ERROR: failed\nWARN: warning\nFATAL: crash\nINFO: ok"
        matches = filter_lines(content, ['error', 'fatal', 'crash'])
        assert len(matches) == 2

    def test_filter_lines_no_matches(self):
        content = "INFO: all good\nDEBUG: trace info"
        matches = filter_lines(content, ['error', 'fail'])
        assert len(matches) == 0


class TestFileOperations:
    """Test file reading operations with temp files"""

    def test_read_log_file_full(self):
        """Test reading entire log file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            filepath = f.name
            f.write("line1\nline2\nline3\nline4\nline5\n")

        try:
            content = read_log_file(filepath)
            assert "line1" in content
            assert "line5" in content
        finally:
            safe_unlink(filepath)

    def test_read_log_file_tail(self):
        """Test reading last N lines"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            filepath = f.name
            for i in range(100):
                f.write(f"line{i}\n")

        try:
            content = read_log_file(filepath, tail=5)
            assert "line95" in content
            assert "line99" in content
            assert "line0" not in content
        finally:
            safe_unlink(filepath)

    def test_read_log_file_not_found(self):
        """Test reading non-existent file"""
        with pytest.raises(SystemExit):
            read_log_file("/nonexistent/path/to/file.log")

    def test_get_file_stats(self):
        """Test getting file statistics"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            filepath = f.name
            f.write("line1\nline2\nline3\n")

        try:
            stats = get_file_stats(filepath)
            assert stats['line_count'] == 3
            assert stats['size_bytes'] > 0
            assert 'size_mb' in stats
        finally:
            safe_unlink(filepath)

    def test_get_file_stats_not_found(self):
        """Test stats for non-existent file"""
        stats = get_file_stats("/nonexistent/file.log")
        assert stats == {}


# =============================================================================
# CLOUDFLARE PARSER TESTS
# =============================================================================

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

    def test_parse_empty_line(self):
        result = parse_cloudflare_line("")
        assert result is None

    def test_parse_whitespace_line(self):
        result = parse_cloudflare_line("   \n  ")
        assert result is None


class TestCloudflareFilters:
    """Test Cloudflare filter functions"""

    def test_filter_errors_500(self):
        log = {'EdgeResponseStatus': 500}
        assert filter_errors(log) is True

    def test_filter_errors_200(self):
        log = {'EdgeResponseStatus': 200}
        assert filter_errors(log) is False

    def test_filter_errors_404(self):
        log = {'EdgeResponseStatus': 404}
        assert filter_errors(log) is True

    def test_filter_errors_301(self):
        log = {'EdgeResponseStatus': 301}
        assert filter_errors(log) is False

    def test_filter_server_errors(self):
        assert filter_server_errors({'EdgeResponseStatus': 500}) is True
        assert filter_server_errors({'EdgeResponseStatus': 502}) is True
        assert filter_server_errors({'EdgeResponseStatus': 404}) is False
        assert filter_server_errors({'EdgeResponseStatus': 200}) is False

    def test_filter_client_errors(self):
        assert filter_client_errors({'EdgeResponseStatus': 400}) is True
        assert filter_client_errors({'EdgeResponseStatus': 404}) is True
        assert filter_client_errors({'EdgeResponseStatus': 499}) is True
        assert filter_client_errors({'EdgeResponseStatus': 500}) is False
        assert filter_client_errors({'EdgeResponseStatus': 200}) is False

    def test_filter_by_status(self):
        filter_502 = filter_by_status("502")
        assert filter_502({'EdgeResponseStatus': 502}) is True
        assert filter_502({'EdgeResponseStatus': 500}) is False

        filter_5xx = filter_by_status("5")
        assert filter_5xx({'EdgeResponseStatus': 500}) is True
        assert filter_5xx({'EdgeResponseStatus': 502}) is True
        assert filter_5xx({'EdgeResponseStatus': 404}) is False

    def test_filter_slow_requests(self):
        filter_func = filter_slow_requests(1000)
        assert filter_func({'OriginResponseTime': 2000}) is True
        assert filter_func({'OriginResponseTime': 1000}) is True
        assert filter_func({'OriginResponseTime': 500}) is False
        assert filter_func({'OriginResponseTime': 0}) is False

    def test_filter_slow_requests_missing_field(self):
        filter_func = filter_slow_requests(1000)
        assert filter_func({}) is False

    def test_filter_security_events_waf(self):
        filter_func = filter_security_events(10)
        assert filter_func({'WAFAction': 'block'}) is True
        assert filter_func({'WAFAction': 'challenge'}) is True
        assert filter_func({'WAFAction': 'allow'}) is False

    def test_filter_security_events_threat_score(self):
        filter_func = filter_security_events(10)
        assert filter_func({'ClientThreatScore': 50}) is True
        assert filter_func({'ClientThreatScore': 10}) is True
        assert filter_func({'ClientThreatScore': 5}) is False

    def test_filter_security_events_blocked(self):
        filter_func = filter_security_events(10)
        assert filter_func({'EdgeResponseStatus': 403}) is True

    def test_filter_by_country(self):
        filter_us = filter_by_country("US")
        assert filter_us({'ClientCountry': 'US'}) is True
        assert filter_us({'ClientCountry': 'us'}) is True
        assert filter_us({'ClientCountry': 'GB'}) is False

    def test_filter_by_ip(self):
        filter_ip = filter_by_ip("1.2.3.4")
        assert filter_ip({'ClientIP': '1.2.3.4'}) is True
        assert filter_ip({'ClientIP': '5.6.7.8'}) is False


class TestCloudflareAggregation:
    """Test Cloudflare aggregation functions"""

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

    def test_aggregate_by_country(self):
        logs = [
            {'ClientCountry': 'US'},
            {'ClientCountry': 'US'},
            {'ClientCountry': 'GB'},
            {'ClientCountry': 'DE'},
        ]
        result = aggregate_by_country(logs)
        assert result['US'] == 2
        assert result['GB'] == 1
        # Should be sorted by count descending
        countries = list(result.keys())
        assert countries[0] == 'US'

    def test_aggregate_by_ip(self):
        logs = [
            {'ClientIP': '1.1.1.1', 'ClientCountry': 'US', 'EdgeResponseStatus': 200, 'ClientRequestURI': '/api'},
            {'ClientIP': '1.1.1.1', 'ClientCountry': 'US', 'EdgeResponseStatus': 404, 'ClientRequestURI': '/other'},
            {'ClientIP': '2.2.2.2', 'ClientCountry': 'GB', 'EdgeResponseStatus': 200, 'ClientRequestURI': '/'},
        ]
        result = aggregate_by_ip(logs)
        assert result['1.1.1.1']['count'] == 2
        assert result['1.1.1.1']['country'] == 'US'
        assert result['2.2.2.2']['count'] == 1

    def test_aggregate_by_uri(self):
        logs = [
            {'ClientRequestURI': '/api/users'},
            {'ClientRequestURI': '/api/users?page=1'},
            {'ClientRequestURI': '/api/posts'},
            {'ClientRequestURI': '/'},
        ]
        result = aggregate_by_uri(logs)
        assert result['/api/users'] == 2  # Query string stripped
        assert result['/api/posts'] == 1
        assert result['/'] == 1

    def test_aggregate_by_waf_action(self):
        logs = [
            {'WAFAction': 'block'},
            {'WAFAction': 'block'},
            {'WAFAction': 'challenge'},
            {'WAFAction': None},
            {},
        ]
        result = aggregate_by_waf_action(logs)
        assert result['block'] == 2
        assert result['challenge'] == 1
        assert result['none'] == 2


class TestCloudflareStats:
    """Test calculate_stats function"""

    def test_calculate_stats_basic(self):
        logs = [
            {'EdgeResponseStatus': 200, 'ClientIP': '1.1.1.1', 'ClientRequestURI': '/a', 'OriginResponseTime': 100, 'EdgeResponseBytes': 1000},
            {'EdgeResponseStatus': 200, 'ClientIP': '1.1.1.1', 'ClientRequestURI': '/b', 'OriginResponseTime': 200, 'EdgeResponseBytes': 2000},
            {'EdgeResponseStatus': 500, 'ClientIP': '2.2.2.2', 'ClientRequestURI': '/c', 'OriginResponseTime': 300, 'EdgeResponseBytes': 500},
        ]
        stats = calculate_stats(logs)

        assert stats['total_requests'] == 3
        assert stats['unique_ips'] == 2
        assert stats['unique_uris'] == 3
        assert stats['error_count'] == 1
        assert stats['error_rate'] == pytest.approx(33.33, rel=0.1)
        assert stats['avg_response_time'] == 200
        assert stats['max_response_time'] == 300
        assert stats['total_bytes'] == 3500

    def test_calculate_stats_empty(self):
        stats = calculate_stats([])
        assert stats == {}

    def test_calculate_stats_no_response_times(self):
        logs = [
            {'EdgeResponseStatus': 200, 'ClientIP': '1.1.1.1'},
        ]
        stats = calculate_stats(logs)
        assert stats['avg_response_time'] == 0
        assert stats['max_response_time'] == 0


class TestCloudflareFormatters:
    """Test compact format functions"""

    def test_format_cf_log_compact(self):
        log = {
            'EdgeStartTimestamp': '2024-01-01T12:00:00Z',
            'ClientRequestMethod': 'GET',
            'ClientRequestURI': '/api/test',
            'EdgeResponseStatus': 200,
            'ClientIP': '1.2.3.4',
            'OriginResponseTime': 150,
            'RayID': 'abc123def456'
        }
        result = format_cf_log_compact(log)
        assert '2024-01-01' in result
        assert 'GET' in result
        assert '/api/test' in result
        assert '200' in result
        assert '1.2.3.4' in result
        assert '150ms' in result

    def test_format_cf_security_compact(self):
        log = {
            'EdgeStartTimestamp': '2024-01-01T12:00:00Z',
            'ClientIP': '1.2.3.4',
            'ClientRequestMethod': 'POST',
            'ClientRequestURI': '/admin',
            'WAFAction': 'block',
            'ClientThreatScore': 50,
            'ClientCountry': 'CN'
        }
        result = format_cf_security_compact(log)
        assert '1.2.3.4' in result
        assert 'block' in result
        assert '50' in result
        assert 'CN' in result

    def test_format_cf_performance_compact(self):
        log = {
            'EdgeStartTimestamp': '2024-01-01T12:00:00Z',
            'ClientRequestURI': '/slow-endpoint',
            'EdgeResponseStatus': 200,
            'OriginResponseTime': 5000,
            'EdgeTimeToFirstByteMs': 5100,
            'CacheCacheStatus': 'MISS'
        }
        result = format_cf_performance_compact(log)
        assert '/slow-endpoint' in result
        assert '5000ms' in result
        assert 'MISS' in result


class TestCloudflareFileOperations:
    """Test Cloudflare log file operations"""

    def test_filter_cloudflare_logs(self):
        """Test filtering Cloudflare logs from file"""
        logs = [
            '{"EdgeResponseStatus": 200, "ClientIP": "1.1.1.1"}',
            '{"EdgeResponseStatus": 500, "ClientIP": "2.2.2.2"}',
            '{"EdgeResponseStatus": 404, "ClientIP": "3.3.3.3"}',
            'invalid json line',
            '{"EdgeResponseStatus": 200, "ClientIP": "4.4.4.4"}',
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            filepath = f.name
            f.write('\n'.join(logs))

        try:
            # Filter for errors
            errors = filter_cloudflare_logs(filepath, 1000, filter_errors)
            assert len(errors) == 2
        finally:
            safe_unlink(filepath)

    def test_filter_cloudflare_logs_tail(self):
        """Test filtering with tail limit"""
        logs = [f'{{"EdgeResponseStatus": {200 if i % 2 == 0 else 500}}}' for i in range(100)]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            filepath = f.name
            f.write('\n'.join(logs))

        try:
            # Only last 10 lines
            errors = filter_cloudflare_logs(filepath, 10, filter_errors)
            assert len(errors) <= 10
        finally:
            safe_unlink(filepath)


# =============================================================================
# CLI TESTS WITH MOCKED OLLAMA
# =============================================================================

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

    def test_cli_no_command_shows_banner(self):
        runner = CliRunner()
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        # Should show help with banner


class TestCLIWithMockedOllama:
    """Test CLI commands that require Ollama"""

    @patch('logparseiqx.cli.ensure_ollama_running')
    @patch('logparseiqx.cli.query_ollama')
    def test_parse_command(self, mock_query, mock_ensure):
        """Test parse command with mocked Ollama"""
        mock_query.return_value = "Analysis: This is a test log file"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            filepath = f.name
            f.write("INFO: Application started\nERROR: Something failed\n")

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ['parse', filepath])

            assert result.exit_code == 0
            mock_ensure.assert_called_once()
            mock_query.assert_called_once()
        finally:
            safe_unlink(filepath)

    @patch('logparseiqx.cli.ensure_ollama_running')
    @patch('logparseiqx.cli.query_ollama')
    def test_parse_with_question(self, mock_query, mock_ensure):
        """Test parse command with specific question"""
        mock_query.return_value = "The crash was caused by memory leak"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            filepath = f.name
            f.write("ERROR: Out of memory\n")

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ['parse', filepath, '-q', 'Why did it crash?'])

            assert result.exit_code == 0
            # Check that the question was passed to the prompt
            call_args = mock_query.call_args[0][0]
            assert 'Why did it crash?' in call_args
        finally:
            safe_unlink(filepath)

    @patch('logparseiqx.cli.ensure_ollama_running')
    @patch('logparseiqx.cli.query_ollama')
    def test_summarize_command(self, mock_query, mock_ensure):
        """Test summarize command"""
        mock_query.return_value = "Summary: All systems operational"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            filepath = f.name
            f.write("INFO: OK\n" * 100)

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ['summarize', filepath])

            assert result.exit_code == 0
            mock_query.assert_called_once()
        finally:
            safe_unlink(filepath)

    @patch('logparseiqx.cli.ensure_ollama_running')
    @patch('logparseiqx.cli.query_ollama')
    def test_errors_command_with_errors(self, mock_query, mock_ensure):
        """Test errors command when errors exist"""
        mock_query.return_value = "Found database connection errors"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            filepath = f.name
            f.write("INFO: Starting\nERROR: Database connection failed\nFATAL: Crash\n")

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ['errors', filepath])

            assert result.exit_code == 0
            mock_query.assert_called_once()
        finally:
            safe_unlink(filepath)

    @patch('logparseiqx.cli.ensure_ollama_running')
    @patch('logparseiqx.cli.query_ollama')
    def test_errors_command_no_errors(self, mock_query, mock_ensure):
        """Test errors command when no errors exist"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            filepath = f.name
            f.write("INFO: All good\nDEBUG: Trace\n")

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ['errors', filepath])

            assert result.exit_code == 0
            assert 'No obvious errors found' in result.output
            mock_query.assert_not_called()
        finally:
            safe_unlink(filepath)

    @patch('logparseiqx.cli.ensure_ollama_running')
    @patch('logparseiqx.cli.query_ollama')
    def test_analyze_command(self, mock_query, mock_ensure):
        """Test analyze command"""
        mock_query.return_value = "Deep analysis: No issues found"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            filepath = f.name
            f.write("INFO: Event 1\nWARN: Event 2\n")

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ['analyze', filepath])

            assert result.exit_code == 0
            mock_query.assert_called_once()
        finally:
            safe_unlink(filepath)

    @patch('logparseiqx.cli.ensure_ollama_running')
    @patch('logparseiqx.cli.query_ollama')
    def test_ask_command(self, mock_query, mock_ensure):
        """Test ask command"""
        mock_query.return_value = "A 502 error means Bad Gateway"

        runner = CliRunner()
        result = runner.invoke(cli, ['ask', 'What is a 502 error?'])

        assert result.exit_code == 0
        mock_query.assert_called_once()
        call_args = mock_query.call_args[0][0]
        assert '502' in call_args


class TestCLIModelsCommand:
    """Test models command"""

    @patch('logparseiqx.cli.get_available_models')
    def test_models_command_with_models(self, mock_get_models):
        """Test models command when models are available"""
        mock_get_models.return_value = ['qwen2.5:3b', 'mistral:7b']

        runner = CliRunner()
        result = runner.invoke(cli, ['models'])

        assert result.exit_code == 0
        assert 'qwen2.5:3b' in result.output
        assert 'mistral:7b' in result.output

    @patch('logparseiqx.cli.get_available_models')
    def test_models_command_no_models(self, mock_get_models):
        """Test models command when no models installed"""
        mock_get_models.return_value = []

        runner = CliRunner()
        result = runner.invoke(cli, ['models'])

        assert result.exit_code == 0
        assert 'No models found' in result.output


class TestCloudflareCommands:
    """Test Cloudflare subcommands with mocked Ollama"""

    @patch('logparseiqx.cli.ensure_ollama_running')
    @patch('logparseiqx.cli.query_ollama')
    def test_cf_errors_command(self, mock_query, mock_ensure):
        """Test cf errors command"""
        mock_query.return_value = "Analysis of errors"

        logs = [
            '{"EdgeResponseStatus": 200, "ClientIP": "1.1.1.1"}',
            '{"EdgeResponseStatus": 500, "ClientIP": "2.2.2.2", "RayID": "abc123"}',
            '{"EdgeResponseStatus": 502, "ClientIP": "3.3.3.3", "RayID": "def456"}',
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            filepath = f.name
            f.write('\n'.join(logs))

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ['cf', 'errors', filepath])

            assert result.exit_code == 0
            assert 'Found 2 error' in result.output
            mock_query.assert_called_once()
        finally:
            safe_unlink(filepath)

    @patch('logparseiqx.cli.ensure_ollama_running')
    @patch('logparseiqx.cli.query_ollama')
    def test_cf_errors_no_errors(self, mock_query, mock_ensure):
        """Test cf errors when no errors"""
        logs = ['{"EdgeResponseStatus": 200, "ClientIP": "1.1.1.1"}']

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            filepath = f.name
            f.write('\n'.join(logs))

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ['cf', 'errors', filepath])

            assert result.exit_code == 0
            assert 'No HTTP errors found' in result.output
            mock_query.assert_not_called()
        finally:
            safe_unlink(filepath)

    @patch('logparseiqx.cli.ensure_ollama_running')
    @patch('logparseiqx.cli.query_ollama')
    def test_cf_slow_command(self, mock_query, mock_ensure):
        """Test cf slow command"""
        mock_query.return_value = "Slow requests analysis"

        logs = [
            '{"EdgeResponseStatus": 200, "OriginResponseTime": 100}',
            '{"EdgeResponseStatus": 200, "OriginResponseTime": 5000}',
            '{"EdgeResponseStatus": 200, "OriginResponseTime": 3000}',
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            filepath = f.name
            f.write('\n'.join(logs))

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ['cf', 'slow', filepath, '--threshold', '1000'])

            assert result.exit_code == 0
            assert 'Found 2 slow request' in result.output
        finally:
            safe_unlink(filepath)

    @patch('logparseiqx.cli.ensure_ollama_running')
    @patch('logparseiqx.cli.query_ollama')
    def test_cf_security_command(self, mock_query, mock_ensure):
        """Test cf security command"""
        mock_query.return_value = "Security analysis"

        logs = [
            '{"EdgeResponseStatus": 200, "WAFAction": "allow", "ClientThreatScore": 0}',
            '{"EdgeResponseStatus": 403, "WAFAction": "block", "ClientThreatScore": 50, "ClientCountry": "CN"}',
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            filepath = f.name
            f.write('\n'.join(logs))

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ['cf', 'security', filepath])

            assert result.exit_code == 0
            assert 'Found 1 security event' in result.output
        finally:
            safe_unlink(filepath)

    @patch('logparseiqx.cli.ensure_ollama_running')
    @patch('logparseiqx.cli.query_ollama')
    def test_cf_top_ips_command(self, mock_query, mock_ensure):
        """Test cf top-ips command"""
        mock_query.return_value = "IP analysis"

        logs = [
            '{"EdgeResponseStatus": 200, "ClientIP": "1.1.1.1", "ClientCountry": "US", "ClientThreatScore": 0}',
            '{"EdgeResponseStatus": 200, "ClientIP": "1.1.1.1", "ClientCountry": "US", "ClientThreatScore": 0}',
            '{"EdgeResponseStatus": 200, "ClientIP": "2.2.2.2", "ClientCountry": "GB", "ClientThreatScore": 0}',
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            filepath = f.name
            f.write('\n'.join(logs))

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ['cf', 'top-ips', filepath])

            assert result.exit_code == 0
            assert '3 requests' in result.output
            assert '2 unique IPs' in result.output
        finally:
            safe_unlink(filepath)

    @patch('logparseiqx.cli.ensure_ollama_running')
    @patch('logparseiqx.cli.query_ollama')
    def test_cf_summary_command(self, mock_query, mock_ensure):
        """Test cf summary command"""
        mock_query.return_value = "Traffic summary"

        logs = [
            '{"EdgeResponseStatus": 200, "ClientIP": "1.1.1.1", "ClientCountry": "US", "OriginResponseTime": 100, "EdgeResponseBytes": 1000}',
            '{"EdgeResponseStatus": 500, "ClientIP": "2.2.2.2", "ClientCountry": "US", "OriginResponseTime": 200, "EdgeResponseBytes": 500}',
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            filepath = f.name
            f.write('\n'.join(logs))

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ['cf', 'summary', filepath])

            assert result.exit_code == 0
            # Should show statistics table
            assert 'Traffic Statistics' in result.output
        finally:
            safe_unlink(filepath)


class TestCLIModelOption:
    """Test --model option across commands"""

    @patch('logparseiqx.cli.ensure_ollama_running')
    @patch('logparseiqx.cli.query_ollama')
    def test_custom_model(self, mock_query, mock_ensure):
        """Test using custom model"""
        mock_query.return_value = "Response"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            filepath = f.name
            f.write("INFO: test\n")

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ['--model', 'mistral:7b', 'parse', filepath])

            assert result.exit_code == 0
            # Check model was passed correctly
            call_args = mock_query.call_args
            assert call_args[0][1] == 'mistral:7b'
        finally:
            safe_unlink(filepath)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

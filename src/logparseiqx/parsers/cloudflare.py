"""
Cloudflare log parsing utilities for LogParseIQX

Handles Cloudflare JSON logs with smart pre-filtering
to minimize token usage while maximizing insights.
"""

import sys
import json
from pathlib import Path
from typing import Optional, List, Callable, Dict, Any
import click
from rich.console import Console
from rich.table import Table

console = Console()


def parse_cloudflare_line(line: str) -> Optional[Dict[str, Any]]:
    """
    Parse a single Cloudflare JSON log line.
    
    Args:
        line: A single line from the log file
    
    Returns:
        Parsed JSON dict or None if parsing fails
    """
    try:
        return json.loads(line.strip())
    except json.JSONDecodeError:
        return None
    except Exception:
        return None


def filter_cloudflare_logs(
    filepath: str,
    tail: int,
    filter_func: Callable[[Dict], bool]
) -> List[Dict[str, Any]]:
    """
    Read and filter Cloudflare logs.
    
    Args:
        filepath: Path to the log file
        tail: Number of lines to read from end
        filter_func: Function that returns True for logs to keep
    
    Returns:
        List of filtered log entries
    """
    path = Path(filepath)
    if not path.exists():
        console.print(f"[red][X] File not found: {filepath}[/red]")
        sys.exit(1)
    
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            if tail:
                lines = lines[-tail:]
    except Exception as e:
        console.print(f"[red][X] Error reading file: {e}[/red]")
        sys.exit(1)
    
    filtered = []
    for line in lines:
        parsed = parse_cloudflare_line(line)
        if parsed and filter_func(parsed):
            filtered.append(parsed)
    
    return filtered


def format_cf_log_compact(log: Dict[str, Any]) -> str:
    """
    Format a Cloudflare log entry compactly for LLM context.
    
    Reduces 50+ fields to 6 key fields to save tokens.
    
    Format: timestamp | method uri | status | IP | origin_time | ray_id
    """
    return (
        f"{log.get('EdgeStartTimestamp', 'N/A')} | "
        f"{log.get('ClientRequestMethod', '?')} {log.get('ClientRequestURI', '/')[:50]} | "
        f"{log.get('EdgeResponseStatus', '?')} | "
        f"{log.get('ClientIP', '?.?.?.?')} | "
        f"{log.get('OriginResponseTime', 0)}ms | "
        f"Ray:{log.get('RayID', 'N/A')[:8]}"
    )


def format_cf_security_compact(log: Dict[str, Any]) -> str:
    """
    Format a Cloudflare security event compactly.
    
    Format: timestamp | IP | method uri | WAF action | threat score | country
    """
    return (
        f"{log.get('EdgeStartTimestamp', 'N/A')} | "
        f"{log.get('ClientIP', '?.?.?.?')} | "
        f"{log.get('ClientRequestMethod', '?')} {log.get('ClientRequestURI', '/')[:40]} | "
        f"WAF:{log.get('WAFAction', 'none')} | "
        f"Threat:{log.get('ClientThreatScore', 0)} | "
        f"{log.get('ClientCountry', '??')}"
    )


def format_cf_performance_compact(log: Dict[str, Any]) -> str:
    """
    Format a Cloudflare log for performance analysis.
    
    Format: timestamp | uri | status | origin_time | edge_time | cache_status
    """
    return (
        f"{log.get('EdgeStartTimestamp', 'N/A')} | "
        f"{log.get('ClientRequestURI', '/')[:40]} | "
        f"{log.get('EdgeResponseStatus', '?')} | "
        f"Origin:{log.get('OriginResponseTime', 0)}ms | "
        f"Edge:{log.get('EdgeTimeToFirstByteMs', 0)}ms | "
        f"Cache:{log.get('CacheCacheStatus', 'unknown')}"
    )


# =============================================================================
# FILTER FUNCTIONS
# =============================================================================

def filter_errors(log: Dict[str, Any]) -> bool:
    """Filter for HTTP errors (4xx and 5xx)"""
    status = log.get('EdgeResponseStatus', 200)
    return isinstance(status, int) and status >= 400


def filter_server_errors(log: Dict[str, Any]) -> bool:
    """Filter for server errors only (5xx)"""
    status = log.get('EdgeResponseStatus', 200)
    return isinstance(status, int) and status >= 500


def filter_client_errors(log: Dict[str, Any]) -> bool:
    """Filter for client errors only (4xx)"""
    status = log.get('EdgeResponseStatus', 200)
    return isinstance(status, int) and 400 <= status < 500


def filter_by_status(status_code: str) -> Callable[[Dict], bool]:
    """Create a filter for a specific status code or prefix"""
    def _filter(log: Dict[str, Any]) -> bool:
        status = str(log.get('EdgeResponseStatus', ''))
        return status.startswith(status_code) or status == status_code
    return _filter


def filter_slow_requests(threshold_ms: int) -> Callable[[Dict], bool]:
    """Create a filter for slow requests"""
    def _filter(log: Dict[str, Any]) -> bool:
        origin_time = log.get('OriginResponseTime', 0)
        return isinstance(origin_time, (int, float)) and origin_time >= threshold_ms
    return _filter


def filter_security_events(threat_score: int = 10) -> Callable[[Dict], bool]:
    """Create a filter for security events"""
    def _filter(log: Dict[str, Any]) -> bool:
        waf_action = log.get('WAFAction', 'allow')
        threat = log.get('ClientThreatScore', 0)
        blocked = log.get('EdgeResponseStatus', 200) == 403
        
        has_waf_action = waf_action not in ['allow', 'unknown', None, '']
        has_high_threat = isinstance(threat, (int, float)) and threat >= threat_score
        
        return has_waf_action or has_high_threat or blocked
    return _filter


def filter_by_country(country_code: str) -> Callable[[Dict], bool]:
    """Create a filter for a specific country"""
    def _filter(log: Dict[str, Any]) -> bool:
        return log.get('ClientCountry', '').upper() == country_code.upper()
    return _filter


def filter_by_ip(ip_address: str) -> Callable[[Dict], bool]:
    """Create a filter for a specific IP"""
    def _filter(log: Dict[str, Any]) -> bool:
        return log.get('ClientIP', '') == ip_address
    return _filter


# =============================================================================
# AGGREGATION FUNCTIONS
# =============================================================================

def aggregate_by_status(logs: List[Dict[str, Any]]) -> Dict[int, int]:
    """Group logs by HTTP status code"""
    by_status = {}
    for log in logs:
        status = log.get('EdgeResponseStatus', 0)
        by_status[status] = by_status.get(status, 0) + 1
    return dict(sorted(by_status.items()))


def aggregate_by_country(logs: List[Dict[str, Any]]) -> Dict[str, int]:
    """Group logs by country"""
    by_country = {}
    for log in logs:
        country = log.get('ClientCountry', 'unknown')
        by_country[country] = by_country.get(country, 0) + 1
    return dict(sorted(by_country.items(), key=lambda x: -x[1]))


def aggregate_by_ip(logs: List[Dict[str, Any]]) -> Dict[str, Dict]:
    """Group logs by IP with details"""
    by_ip = {}
    for log in logs:
        ip = log.get('ClientIP', 'unknown')
        if ip not in by_ip:
            by_ip[ip] = {
                'count': 0,
                'country': log.get('ClientCountry', '??'),
                'user_agent': log.get('ClientRequestUserAgent', 'unknown')[:50],
                'threat_score': log.get('ClientThreatScore', 0),
                'statuses': set(),
                'uris': set()
            }
        by_ip[ip]['count'] += 1
        by_ip[ip]['statuses'].add(log.get('EdgeResponseStatus', 0))
        by_ip[ip]['uris'].add(log.get('ClientRequestURI', '/')[:30])
    
    return dict(sorted(by_ip.items(), key=lambda x: -x[1]['count']))


def aggregate_by_uri(logs: List[Dict[str, Any]]) -> Dict[str, int]:
    """Group logs by URI path"""
    by_uri = {}
    for log in logs:
        uri = log.get('ClientRequestURI', '/').split('?')[0]  # Remove query string
        by_uri[uri] = by_uri.get(uri, 0) + 1
    return dict(sorted(by_uri.items(), key=lambda x: -x[1]))


def aggregate_by_waf_action(logs: List[Dict[str, Any]]) -> Dict[str, int]:
    """Group logs by WAF action"""
    by_action = {}
    for log in logs:
        action = log.get('WAFAction', 'none') or 'none'
        by_action[action] = by_action.get(action, 0) + 1
    return dict(sorted(by_action.items(), key=lambda x: -x[1]))


def calculate_stats(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate summary statistics for a set of logs"""
    if not logs:
        return {}
    
    total = len(logs)
    
    # Status codes
    statuses = aggregate_by_status(logs)
    error_count = sum(v for k, v in statuses.items() if k >= 400)
    
    # Response times
    response_times = [
        log.get('OriginResponseTime', 0)
        for log in logs
        if isinstance(log.get('OriginResponseTime'), (int, float))
    ]
    
    # Bytes
    total_bytes = sum(
        log.get('EdgeResponseBytes', 0)
        for log in logs
        if isinstance(log.get('EdgeResponseBytes'), (int, float))
    )
    
    return {
        'total_requests': total,
        'unique_ips': len(set(log.get('ClientIP', '') for log in logs)),
        'unique_uris': len(set(log.get('ClientRequestURI', '') for log in logs)),
        'error_count': error_count,
        'error_rate': (error_count / total * 100) if total > 0 else 0,
        'total_bytes': total_bytes,
        'total_mb': total_bytes / (1024 * 1024),
        'avg_response_time': sum(response_times) / len(response_times) if response_times else 0,
        'max_response_time': max(response_times) if response_times else 0,
        'statuses': statuses,
    }


# =============================================================================
# DISPLAY HELPERS
# =============================================================================

def print_stats_table(stats: Dict[str, Any]):
    """Print a nice stats table using Rich"""
    table = Table(title="Traffic Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Total Requests", f"{stats.get('total_requests', 0):,}")
    table.add_row("Unique IPs", f"{stats.get('unique_ips', 0):,}")
    table.add_row("Unique URIs", f"{stats.get('unique_uris', 0):,}")
    table.add_row("Error Rate", f"{stats.get('error_rate', 0):.1f}%")
    table.add_row("Total Data", f"{stats.get('total_mb', 0):.2f} MB")
    table.add_row("Avg Response Time", f"{stats.get('avg_response_time', 0):.0f} ms")
    table.add_row("Max Response Time", f"{stats.get('max_response_time', 0):.0f} ms")
    
    console.print(table)


def print_status_breakdown(statuses: Dict[int, int]):
    """Print HTTP status code breakdown"""
    table = Table(title="HTTP Status Codes")
    table.add_column("Status", style="cyan")
    table.add_column("Count", style="green")
    table.add_column("Type", style="yellow")
    
    for status, count in statuses.items():
        if status < 300:
            status_type = "[OK] Success"
        elif status < 400:
            status_type = "[->] Redirect"
        elif status < 500:
            status_type = "[!] Client Error"
        else:
            status_type = "[X] Server Error"
        
        table.add_row(str(status), f"{count:,}", status_type)
    
    console.print(table)

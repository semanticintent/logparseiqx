"""
Generic log parsing utilities for LogParseIQX
"""

import sys
from pathlib import Path
from typing import Optional, List, Callable
import click
from rich.console import Console

console = Console()

# Default chunk size for LLM context
CHUNK_SIZE = 4000


def read_log_file(filepath: str, tail: Optional[int] = None) -> str:
    """
    Read a log file, optionally just the tail.
    
    Args:
        filepath: Path to the log file
        tail: If set, only return the last N lines
    
    Returns:
        The file contents as a string
    """
    path = Path(filepath)
    if not path.exists():
        console.print(f"[red][X] File not found: {filepath}[/red]")
        sys.exit(1)
    
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            if tail:
                lines = f.readlines()
                return ''.join(lines[-tail:])
            return f.read()
    except PermissionError:
        console.print(f"[red][X] Permission denied: {filepath}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red][X] Error reading file: {e}[/red]")
        sys.exit(1)


def chunk_text(text: str, size: int = CHUNK_SIZE) -> List[str]:
    """
    Split text into chunks, trying to break at newlines.
    
    Args:
        text: The text to split
        size: Maximum size of each chunk
    
    Returns:
        List of text chunks
    """
    chunks = []
    while text:
        if len(text) <= size:
            chunks.append(text)
            break
        # Find last newline within chunk size
        split_point = text.rfind('\n', 0, size)
        if split_point == -1:
            split_point = size
        chunks.append(text[:split_point])
        text = text[split_point:].lstrip('\n')
    return chunks


def filter_lines(content: str, keywords: List[str], case_sensitive: bool = False) -> List[str]:
    """
    Filter log lines by keywords.
    
    Args:
        content: Log file content
        keywords: List of keywords to search for
        case_sensitive: Whether to match case
    
    Returns:
        List of matching lines
    """
    lines = content.split('\n')
    
    if case_sensitive:
        return [l for l in lines if any(k in l for k in keywords)]
    else:
        return [l for l in lines if any(k in l.lower() for k in [kw.lower() for kw in keywords])]


def get_file_stats(filepath: str) -> dict:
    """Get basic stats about a log file"""
    path = Path(filepath)
    if not path.exists():
        return {}
    
    stats = path.stat()
    
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        line_count = sum(1 for _ in f)
    
    return {
        'size_bytes': stats.st_size,
        'size_mb': stats.st_size / (1024 * 1024),
        'line_count': line_count,
        'modified': stats.st_mtime,
    }

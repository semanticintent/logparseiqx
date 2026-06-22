"""
Generic log parsing utilities for LogParseIQX
"""

import sys
import time
from pathlib import Path
from typing import Optional, List, Iterator, Tuple
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
        return [line for line in lines if any(k in line for k in keywords)]
    else:
        return [line for line in lines if any(k in line.lower() for k in [kw.lower() for kw in keywords])]


def needs_chunking(content: str, max_size: int = CHUNK_SIZE * 3) -> bool:
    """Return True if content exceeds the single-pass context limit"""
    return len(content) > max_size


def tail_file(filepath: str, interval: int, batch_size: int) -> Iterator[Tuple[str, int]]:
    """
    Watch a file for new lines, yielding batches as they arrive.

    Seeks to the end of the file on first call so only new content is returned.
    Handles file rotation by detecting when the file shrinks.

    Yields:
        (new_content, line_count) tuples whenever new lines appear
    """
    path = Path(filepath)
    position = path.stat().st_size  # start at end — only watch new content

    while True:
        time.sleep(interval)

        try:
            current_size = path.stat().st_size
        except FileNotFoundError:
            console.print(f"[red][X] File disappeared: {filepath}[/red]")
            return

        # File was rotated or truncated
        if current_size < position:
            console.print("[yellow][!] File rotated or truncated — resetting position[/yellow]")
            position = 0

        if current_size == position:
            yield ("", 0)
            continue

        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            f.seek(position)
            new_lines = f.readlines()
            position = f.tell()

        if not new_lines:
            yield ("", 0)
            continue

        # Cap batch size — take the most recent lines if over limit
        batch = new_lines[-batch_size:] if len(new_lines) > batch_size else new_lines
        yield (''.join(batch), len(new_lines))


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

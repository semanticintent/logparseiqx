"""
Ollama integration utilities for LogParseIQX
"""

import os
import sys
import json
import requests
import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# Configuration — all overridable via environment variables
OLLAMA_BASE_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_GENERATE_URL = f"{OLLAMA_BASE_URL}/api/generate"
OLLAMA_TAGS_URL = f"{OLLAMA_BASE_URL}/api/tags"
DEFAULT_MODEL = os.environ.get("LOGPARSEIQX_MODEL", "llama3:8b")
DEFAULT_TIMEOUT = 300


def check_ollama() -> bool:
    """Check if Ollama is running"""
    try:
        r = requests.get(OLLAMA_TAGS_URL, timeout=5)
        return r.status_code == 200
    except requests.exceptions.ConnectionError:
        return False
    except Exception:
        return False


def get_available_models() -> list:
    """Get list of installed Ollama models"""
    try:
        r = requests.get(OLLAMA_TAGS_URL, timeout=5)
        if r.status_code == 200:
            return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        pass
    return []


def ensure_ollama_running():
    """Check Ollama is running, exit with helpful message if not"""
    if not check_ollama():
        console.print("[red][X] Ollama is not running![/red]")
        console.print("[yellow]   Start it with: ollama serve[/yellow]")
        console.print("[yellow]   Or install from: https://ollama.com[/yellow]")
        sys.exit(1)


def query_ollama(
    prompt: str,
    model: str = DEFAULT_MODEL,
    stream: bool = True,
    timeout: int = DEFAULT_TIMEOUT
) -> str:
    """
    Send query to Ollama and get response.
    
    Args:
        prompt: The prompt to send
        model: Ollama model to use
        stream: Whether to stream the response
        timeout: Request timeout in seconds
    
    Returns:
        The model's response text
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": stream
    }
    
    try:
        if stream:
            response = requests.post(
                OLLAMA_GENERATE_URL,
                json=payload,
                stream=True,
                timeout=timeout
            )
            full_response = ""
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    chunk = data.get("response", "")
                    console.print(chunk, end="", highlight=False, markup=False)
                    full_response += chunk
                    if data.get("done", False):
                        break
            console.print()  # Newline at end
            return full_response
        else:
            response = requests.post(
                OLLAMA_GENERATE_URL,
                json=payload,
                timeout=timeout
            )
            return response.json().get("response", "")
            
    except requests.exceptions.ConnectionError:
        console.print("[red][X] Error: Cannot connect to Ollama. Is it running?[/red]")
        console.print("[yellow]   Start it with: ollama serve[/yellow]")
        sys.exit(1)
    except requests.exceptions.Timeout:
        console.print("[red][X] Error: Request timed out. Try a smaller log file.[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red][X] Error: {e}[/red]")
        sys.exit(1)


def model_info(model: str) -> dict:
    """Get info about a specific model"""
    try:
        r = requests.post(
            f"{OLLAMA_BASE_URL}/api/show",
            json={"name": model},
            timeout=10
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}

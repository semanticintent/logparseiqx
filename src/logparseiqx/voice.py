"""
Voice input support for LogParseIQX.

Optional feature — requires: pip install logparseiqx[voice]
Records from microphone, transcribes locally via faster-whisper.
Nothing leaves your machine.
"""

import sys
import threading
from typing import Optional
from rich.console import Console

console = Console()

WHISPER_MODELS = ["tiny", "base", "small"]
DEFAULT_WHISPER_MODEL = "base"
SAMPLE_RATE = 16000  # Hz — required by Whisper


def check_voice_deps() -> bool:
    """Return True if voice dependencies are installed."""
    try:
        import sounddevice  # noqa: F401
        import numpy  # noqa: F401
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def require_voice_deps():
    """Exit with a helpful message if voice deps are missing."""
    if not check_voice_deps():
        console.print("[red][X] Voice dependencies not installed.[/red]")
        console.print()
        console.print("Install them with:")
        console.print("[bold cyan]   pip install logparseiqx\\[voice][/bold cyan]")
        console.print()
        console.print("[dim]   Installs: sounddevice, numpy, faster-whisper[/dim]")
        console.print("[dim]   First run downloads the Whisper model (~150MB)[/dim]")
        sys.exit(1)


def record_audio(sample_rate: int = SAMPLE_RATE) -> Optional["numpy.ndarray"]:
    """
    Record audio from the microphone until the user presses Enter.

    Returns a float32 numpy array at the given sample rate,
    or None if no audio was captured.
    """
    import numpy as np
    import sounddevice as sd

    chunks = []
    stop_event = threading.Event()

    def audio_callback(indata, frames, time_info, status):
        if not stop_event.is_set():
            chunks.append(indata.copy())

    console.print("\n[bold red]● REC[/bold red] Recording... press [bold]Enter[/bold] to stop\n")

    try:
        stream = sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            callback=audio_callback,
        )
        with stream:
            sys.stdin.readline()
            stop_event.set()
    except Exception as e:
        console.print(f"[red][X] Microphone error: {e}[/red]")
        console.print("[dim]   Make sure your mic is connected and permissions are granted.[/dim]")
        return None

    if not chunks:
        return None

    audio = np.concatenate(chunks).flatten()

    # Minimum 0.5 seconds of audio to bother transcribing
    if len(audio) < sample_rate * 0.5:
        console.print("[yellow][!] Recording too short — try again.[/yellow]")
        return None

    duration = len(audio) / sample_rate
    console.print(f"[dim]   Captured {duration:.1f}s of audio[/dim]")

    return audio


def transcribe_audio(
    audio: "numpy.ndarray",
    whisper_model: str = DEFAULT_WHISPER_MODEL,
    language: Optional[str] = None,
) -> Optional[str]:
    """
    Transcribe a numpy audio array using faster-whisper (runs locally).

    On first call, downloads the Whisper model (~150MB for 'base').
    Subsequent calls reuse the cached model.

    Returns the transcribed text, or None on failure.
    """
    from faster_whisper import WhisperModel

    console.print(f"[dim]   Transcribing with whisper/{whisper_model}...[/dim]")

    try:
        model = WhisperModel(whisper_model, device="cpu", compute_type="int8")
        segments, info = model.transcribe(
            audio,
            beam_size=5,
            language=language,
            vad_filter=True,  # skip silent regions
            vad_parameters={"min_silence_duration_ms": 500},
        )
        text = "".join(s.text for s in segments).strip()
        return text if text else None

    except Exception as e:
        console.print(f"[red][X] Transcription error: {e}[/red]")
        return None


def voice_input(
    whisper_model: str = DEFAULT_WHISPER_MODEL,
    language: Optional[str] = None,
) -> Optional[str]:
    """
    Full pipeline: check deps → record → transcribe → return text.

    Returns the transcribed question string, or None if anything failed.
    """
    require_voice_deps()

    console.print("[cyan][MIC] Voice input — speak your question[/cyan]")
    console.print("[dim]   Press Enter to start recording[/dim]")
    sys.stdin.readline()

    audio = record_audio()
    if audio is None:
        return None

    text = transcribe_audio(audio, whisper_model=whisper_model, language=language)
    if not text:
        console.print("[yellow][!] Could not transcribe audio — try speaking more clearly.[/yellow]")
        return None

    console.print(f"\n[bold][You]:[/bold] {text}\n")
    return text

"""Generate docs/lpx-help.svg from current CLI --help output."""
import sys, pathlib, subprocess

# Run lpx --help using the same python that's running this script
out = subprocess.run(
    [sys.executable, "-m", "logparseiqx", "--help"],
    capture_output=True, text=True
)
help_text = out.stdout.strip() or out.stderr.strip()

from rich.console import Console

svg_path = pathlib.Path(__file__).parent / "lpx-help.svg"

console = Console(record=True, width=88, force_terminal=True, color_system="truecolor")
console.print(
    f"[bold green](.venv)[/bold green] [cyan]dev@Mac logparseiqx[/cyan] "
    f"[white]%[/white] [bold white]lpx --help[/bold white]"
)
console.print()
for line in help_text.splitlines():
    # Colour the command names in the Commands section
    if line.startswith("  ") and not line.startswith("   ") and "  " in line.strip():
        parts = line.split(None, 1)
        if len(parts) == 2:
            console.print(f"  [bold cyan]{parts[0]:<11}[/bold cyan]{parts[1]}")
            continue
    console.print(line)
console.print()
console.print(
    f"[bold green](.venv)[/bold green] [cyan]dev@Mac logparseiqx[/cyan] "
    f"[white]%[/white] [dim]▌[/dim]"
)

svg = console.export_svg(title="LogParseIQX — lpx --help")
svg_path.write_text(svg)
print(f"Saved: {svg_path}")

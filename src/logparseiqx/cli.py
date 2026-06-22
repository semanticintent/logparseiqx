#!/usr/bin/env python3
"""
LogParseIQX - Local log parser powered by Ollama
"Like cloud AI log analysis but $0"

Part of Millpond AI.
https://millpond.ai
"""

import click
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from logparseiqx import __version__, BANNER, TAGLINE
from logparseiqx.utils import (
    check_ollama,
    ensure_ollama_running,
    get_available_models,
    query_ollama,
    DEFAULT_MODEL,
)
from logparseiqx.parsers import read_log_file, filter_lines, chunk_text, needs_chunking, CHUNK_SIZE
from logparseiqx.parsers.cloudflare import (
    filter_cloudflare_logs,
    format_cf_log_compact,
    format_cf_security_compact,
    format_cf_performance_compact,
    filter_errors,
    filter_slow_requests,
    filter_security_events,
    filter_by_status_class,
    aggregate_by_status,
    aggregate_by_country,
    aggregate_by_ip,
    aggregate_by_waf_action,
    calculate_stats,
    print_stats_table,
)

console = Console()


# =============================================================================
# MAIN CLI GROUP
# =============================================================================

@click.group(invoke_without_command=True)
@click.option('--model', '-m', default=DEFAULT_MODEL, 
              help=f'Ollama model to use (default: {DEFAULT_MODEL})')
@click.option('--version', '-v', is_flag=True, help='Show version')
@click.pass_context
def cli(ctx, model, version):
    """
    LogParseIQX - Local log parser powered by Ollama

    "Like Opus 4.5 Thinking Mode but $0"
    
    \b
    USAGE:
        logparseiqx parse <logfile>
        logparseiqx errors <logfile>
        logparseiqx cf errors <cloudflare.log>
        lpx cf security <cloudflare.log>
    
    \b
    Part of Millpond AI.
    https://millpond.ai
    """
    ctx.ensure_object(dict)
    ctx.obj['model'] = model
    
    if version:
        console.print(f"[bold cyan]LogParseIQX[/bold cyan] v{__version__}")
        console.print(f"[dim]{TAGLINE}[/dim]")
        ctx.exit(0)
    
    if ctx.invoked_subcommand is None:
        # Show help with banner
        console.print(Panel(
            Text(BANNER, style="cyan") + Text(f"\n{TAGLINE}\n\nv{__version__}", style="dim"),
            title="LogParseIQX",
            subtitle="Part of Millpond AI"
        ))
        console.print()
        console.print(ctx.get_help())


# =============================================================================
# GENERIC LOG COMMANDS
# =============================================================================

@cli.command()
@click.argument('logfile', type=click.Path(exists=True))
@click.option('--question', '-q', default=None, help='Specific question to answer')
@click.option('--tail', '-n', default=None, type=int, help='Only parse last N lines')
@click.pass_context
def parse(ctx, logfile, question, tail):
    """Parse a log file and explain what's happening"""
    ensure_ollama_running()
    model = ctx.obj['model']
    
    console.print(f"[cyan][*] Parsing {logfile} with {model}...[/cyan]")
    console.print()
    
    content = read_log_file(logfile, tail)

    if needs_chunking(content):
        chunks = chunk_text(content)
        console.print(f"[dim]   Large file: processing {len(chunks)} chunks...[/dim]")
        chunk_summaries = []
        for i, chunk in enumerate(chunks, 1):
            console.print(f"[dim]   Chunk {i}/{len(chunks)}...[/dim]")
            chunk_prompt = f"""Briefly summarize the key events, errors, and patterns in this log excerpt (chunk {i} of {len(chunks)}):
```
{chunk}
```
Keep the summary under 150 words."""
            summary = query_ollama(chunk_prompt, model, stream=False)
            chunk_summaries.append(f"[Chunk {i}]: {summary}")
        combined = "\n\n".join(chunk_summaries)
        if question:
            final_prompt = f"""Based on these log summaries, answer the question: {question}

{combined}

Provide a clear, concise answer."""
        else:
            final_prompt = f"""Based on these log summaries, provide a final analysis:
1. What application/service is this from?
2. What is the general state? (healthy, errors, warnings?)
3. Any notable events or issues?
4. Key timestamps and patterns

Summaries:
{combined}

Be concise and focus on actionable insights."""
        query_ollama(final_prompt, model)
    elif question:
        prompt = f"""Analyze this log file and answer the question.

Question: {question}

Log content:
```
{content}
```

Provide a clear, concise answer based on the log content."""
        query_ollama(prompt, model)
    else:
        prompt = f"""Analyze this log file and explain:
1. What application/service is this from?
2. What is the general state? (healthy, errors, warnings?)
3. Any notable events or issues?
4. Key timestamps and patterns

Log content:
```
{content}
```

Be concise and focus on actionable insights."""
        query_ollama(prompt, model)


@cli.command()
@click.argument('logfile', type=click.Path(exists=True))
@click.option('--tail', '-n', default=500, type=int, help='Lines to summarize (default: 500)')
@click.pass_context
def summarize(ctx, logfile, tail):
    """Summarize a log file"""
    ensure_ollama_running()
    model = ctx.obj['model']
    
    console.print(f"[cyan][*] Summarizing last {tail} lines of {logfile}...[/cyan]")
    console.print()
    
    content = read_log_file(logfile, tail)

    if needs_chunking(content):
        chunks = chunk_text(content)
        console.print(f"[dim]   Large file: processing {len(chunks)} chunks...[/dim]")
        chunk_summaries = []
        for i, chunk in enumerate(chunks, 1):
            console.print(f"[dim]   Chunk {i}/{len(chunks)}...[/dim]")
            chunk_prompt = f"""One-paragraph summary of key events in this log excerpt (chunk {i} of {len(chunks)}):
```
{chunk}
```"""
            summary = query_ollama(chunk_prompt, model, stream=False)
            chunk_summaries.append(f"[Chunk {i}]: {summary}")
        combined = "\n\n".join(chunk_summaries)
        final_prompt = f"""Synthesize these log chunk summaries into a single executive summary:
- Overall status (1 line)
- Key events (bullet points)
- Any errors or warnings
- Recommendation (1 line)

Summaries:
{combined}

Keep under 200 words."""
        query_ollama(final_prompt, model)
    else:
        prompt = f"""Summarize this log file in a brief, executive-style summary:
- Overall status (1 line)
- Key events (bullet points)
- Any errors or warnings (if present)
- Recommendation (1 line)

Log content:
```
{content}
```

Keep the summary under 200 words."""
        query_ollama(prompt, model)


@cli.command()
@click.argument('logfile', type=click.Path(exists=True))
@click.option('--tail', '-n', default=1000, type=int, help='Lines to analyze (default: 1000)')
@click.pass_context  
def errors(ctx, logfile, tail):
    """Find and explain errors in a log file"""
    ensure_ollama_running()
    model = ctx.obj['model']
    
    console.print(f"[cyan][!] Finding errors in {logfile}...[/cyan]")
    console.print()
    
    content = read_log_file(logfile, tail)
    
    # Pre-filter for error-like lines
    error_keywords = ['error', 'fail', 'exception', 'critical', 'fatal', 'panic', 'crash']
    error_lines = filter_lines(content, error_keywords)
    
    if not error_lines:
        console.print("[green][OK] No obvious errors found in the log![/green]")
        console.print("[dim]   (Searched for: error, fail, exception, critical, fatal, panic, crash)[/dim]")
        return
    
    error_content = '\n'.join(error_lines[:100])
    
    prompt = f"""Analyze these error log lines and provide:
1. A list of unique error types found
2. Root cause analysis (best guess)
3. Suggested fixes or next steps

Error lines found:
```
{error_content}
```

Be specific and actionable."""

    query_ollama(prompt, model)


@cli.command()
@click.argument('logfile', type=click.Path(exists=True))
@click.option('--tail', '-n', default=1000, type=int, help='Lines to analyze (default: 1000)')
@click.pass_context
def analyze(ctx, logfile, tail):
    """Deep analysis - find patterns, anomalies, and insights"""
    ensure_ollama_running()
    model = ctx.obj['model']
    
    console.print(f"[cyan][*] Deep analysis of {logfile}...[/cyan]")
    console.print()
    
    content = read_log_file(logfile, tail)

    if needs_chunking(content):
        chunks = chunk_text(content)
        console.print(f"[dim]   Large file: processing {len(chunks)} chunks...[/dim]")
        chunk_summaries = []
        for i, chunk in enumerate(chunks, 1):
            console.print(f"[dim]   Chunk {i}/{len(chunks)}...[/dim]")
            chunk_prompt = f"""Analyze this log excerpt (chunk {i} of {len(chunks)}) for patterns, anomalies, errors, and security events. Be brief:
```
{chunk}
```"""
            summary = query_ollama(chunk_prompt, model, stream=False)
            chunk_summaries.append(f"[Chunk {i}]: {summary}")
        combined = "\n\n".join(chunk_summaries)
        final_prompt = f"""Synthesize these log chunk analyses into a full deep analysis:

1. **Patterns**: What recurring patterns appear across chunks?
2. **Anomalies**: Anything unusual or out of place?
3. **Timeline**: Key events in chronological order
4. **Performance**: Any performance indicators or concerns?
5. **Security**: Any security-related events?
6. **Recommendations**: Top 3 things to investigate

Chunk analyses:
{combined}

Think step by step and be thorough."""
        query_ollama(final_prompt, model)
    else:
        prompt = f"""Perform a deep analysis of this log file:

1. **Patterns**: What recurring patterns do you see?
2. **Anomalies**: Anything unusual or out of place?
3. **Timeline**: Key events in chronological order
4. **Performance**: Any performance indicators or concerns?
5. **Security**: Any security-related events?
6. **Recommendations**: Top 3 things to investigate

Log content:
```
{content}
```

Think step by step and be thorough."""
        query_ollama(prompt, model)


@cli.command()
@click.pass_context
def models(ctx):
    """List available Ollama models"""
    available = get_available_models()
    
    if not available:
        console.print("[red][X] No models found. Install one with:[/red]")
        console.print("[yellow]   ollama pull qwen2.5:3b     # Lightweight, fast[/yellow]")
        console.print("[yellow]   ollama pull phi3:mini      # Good reasoning[/yellow]")
        console.print("[yellow]   ollama pull mistral:7b     # Best quality[/yellow]")
        return
    
    console.print("[cyan][+] Available models:[/cyan]")
    for m in available:
        marker = " [green]<- current[/green]" if m == ctx.obj.get('model', DEFAULT_MODEL) else ""
        console.print(f"   * {m}{marker}")


@cli.command()
def cost():
    """Show how much you're saving vs cloud APIs"""
    console.print("""
[bold cyan][$] Cost Comparison for 500MB log file (~125M tokens):[/bold cyan]

  Service                   Cost/1M      Total
  -------------------------+------------+-------------
  Claude Opus (API)         $75          [red]$2,187[/red]
  Claude Sonnet (API)       $15          [red]$437[/red]
  GPT-4o (API)              $10          [red]$291[/red]
  Gemini 1.5 Pro (API)      $7           [red]$204[/red]
  -------------------------+------------+-------------
  LogParseIQX (local)       $0           [green]$0[/green]

[green]Your savings: up to $2,187+ per log file[/green]
[bold green]Your cost: $0[/bold green]

[dim]grep "error" logs.txt | head: Still $0, but less insightful :)[/dim]
""")


@cli.command()
@click.argument('text')
@click.pass_context
def ask(ctx, text):
    """Ask a quick question (no log file needed)"""
    ensure_ollama_running()
    model = ctx.obj['model']
    query_ollama(text, model)


# =============================================================================
# CLOUDFLARE COMMANDS
# =============================================================================

@cli.group()
def cf():
    """Cloudflare log commands (pre-filtered for efficiency)"""
    pass


@cf.command('errors')
@click.argument('logfile', type=click.Path(exists=True))
@click.option('--tail', '-n', default=1000, type=int, help='Lines to scan (default: 1000)')
@click.option('--status', '-s', default=None, help='Specific status code (e.g., 502, 404)')
@click.pass_context
def cf_errors(ctx, logfile, tail, status):
    """Find HTTP errors (4xx, 5xx) in Cloudflare logs"""
    ensure_ollama_running()
    model = ctx.obj['model']
    
    console.print("[orange3][CF] Scanning Cloudflare logs for errors...[/orange3]")
    
    if status:
        filter_func = filter_by_status_class(status)
    else:
        filter_func = filter_errors
    
    errors_list = filter_cloudflare_logs(logfile, tail, filter_func)
    
    if not errors_list:
        console.print("[green][OK] No HTTP errors found![/green]")
        return
    
    console.print(f"[yellow][#] Found {len(errors_list)} error(s). Analyzing...[/yellow]")
    console.print()
    
    by_status = aggregate_by_status(errors_list)
    
    summary = "Error Summary:\n"
    for code, count in by_status.items():
        summary += f"  {code}: {count} occurrences\n"
    
    sample_logs = "\n".join([format_cf_log_compact(e) for e in errors_list[:50]])
    
    prompt = f"""Analyze these Cloudflare HTTP errors:

{summary}

Sample error logs (compact format: timestamp | method uri | status | IP | origin_time | ray_id):
```
{sample_logs}
```

Provide:
1. What's causing these errors?
2. Are they client errors (4xx) or server errors (5xx)?
3. Any patterns in IPs, URIs, or timing?
4. Recommended actions to fix

Be specific and actionable."""

    query_ollama(prompt, model)


@cf.command('slow')
@click.argument('logfile', type=click.Path(exists=True))
@click.option('--tail', '-n', default=1000, type=int, help='Lines to scan (default: 1000)')
@click.option('--threshold', '-t', default=1000, type=int, help='Slow threshold in ms (default: 1000)')
@click.pass_context
def cf_slow(ctx, logfile, tail, threshold):
    """Find slow requests in Cloudflare logs"""
    ensure_ollama_running()
    model = ctx.obj['model']
    
    console.print(f"[orange3][CF] Finding requests slower than {threshold}ms...[/orange3]")
    
    slow = filter_cloudflare_logs(logfile, tail, filter_slow_requests(threshold))
    
    if not slow:
        console.print(f"[green][OK] No requests slower than {threshold}ms found![/green]")
        return
    
    slow.sort(key=lambda x: x.get('OriginResponseTime', 0), reverse=True)
    
    console.print(f"[yellow][#] Found {len(slow)} slow request(s). Analyzing...[/yellow]")
    console.print()
    
    sample_logs = "\n".join([format_cf_log_compact(e) for e in slow[:30]])
    
    times = [s.get('OriginResponseTime', 0) for s in slow]
    avg_time = sum(times) / len(times) if times else 0
    max_time = max(times) if times else 0
    
    prompt = f"""Analyze these slow Cloudflare requests:

Stats:
- Total slow requests: {len(slow)}
- Average response time: {avg_time:.0f}ms
- Slowest request: {max_time}ms
- Threshold: {threshold}ms

Sample slow requests (compact format: timestamp | method uri | status | IP | origin_time | ray_id):
```
{sample_logs}
```

Provide:
1. What endpoints/URIs are slowest?
2. Any patterns (time of day, specific IPs, etc.)?
3. Is this a backend issue or Cloudflare edge issue?
4. Performance optimization recommendations

Be specific and actionable."""

    query_ollama(prompt, model)


@cf.command('performance')
@click.argument('logfile', type=click.Path(exists=True))
@click.option('--tail', '-n', default=1000, type=int, help='Lines to scan (default: 1000)')
@click.option('--threshold', '-t', default=500, type=int, help='Slow threshold in ms (default: 500)')
@click.pass_context
def cf_performance(ctx, logfile, tail, threshold):
    """Analyze cache efficiency and edge vs origin latency in Cloudflare logs"""
    ensure_ollama_running()
    model = ctx.obj['model']

    console.print(f"[orange3][CF] Analyzing performance (threshold: {threshold}ms)...[/orange3]")

    all_logs = filter_cloudflare_logs(logfile, tail, lambda x: True)

    if not all_logs:
        console.print("[red][X] No logs found![/red]")
        return

    slow = [l for l in all_logs if l.get('OriginResponseTime', 0) >= threshold]
    slow.sort(key=lambda x: x.get('OriginResponseTime', 0), reverse=True)

    console.print(f"[yellow][#] {len(slow)}/{len(all_logs)} requests above {threshold}ms threshold[/yellow]")
    console.print()

    sample_logs = "\n".join([format_cf_performance_compact(l) for l in slow[:30]])

    times = [l.get('OriginResponseTime', 0) for l in all_logs if isinstance(l.get('OriginResponseTime'), (int, float))]
    avg_time = sum(times) / len(times) if times else 0
    max_time = max(times) if times else 0

    from logparseiqx.parsers.cloudflare import aggregate_by_uri
    top_uris = list(aggregate_by_uri(slow).items())[:10]
    uri_summary = "\n".join([f"  {uri}: {count}" for uri, count in top_uris])

    prompt = f"""Analyze this Cloudflare performance data:

Stats:
- Total requests: {len(all_logs)}
- Slow requests (>{threshold}ms): {len(slow)} ({len(slow)/len(all_logs)*100:.1f}%)
- Average origin time: {avg_time:.0f}ms
- Max origin time: {max_time}ms

Slowest endpoints:
{uri_summary}

Sample slow requests (format: timestamp | uri | status | origin_time | edge_time | cache_status):
```
{sample_logs}
```

Provide:
1. Which endpoints have the worst performance?
2. Is this a cache miss problem (MISS/EXPIRED cache status)?
3. Origin vs edge latency — where is time being lost?
4. Specific optimization recommendations (caching rules, origin improvements)

Be specific and actionable."""

    query_ollama(prompt, model)


@cf.command('security')
@click.argument('logfile', type=click.Path(exists=True))
@click.option('--tail', '-n', default=1000, type=int, help='Lines to scan (default: 1000)')
@click.option('--threat-score', '-t', default=10, type=int, help='Min threat score (default: 10)')
@click.pass_context
def cf_security(ctx, logfile, tail, threat_score):
    """Find security events (WAF, threats, blocks) in Cloudflare logs"""
    ensure_ollama_running()
    model = ctx.obj['model']
    
    console.print(f"[orange3][CF] Scanning for security events (threat score >= {threat_score})...[/orange3]")
    
    events = filter_cloudflare_logs(logfile, tail, filter_security_events(threat_score))
    
    if not events:
        console.print("[green][OK] No security events found![/green]")
        return
    
    console.print(f"[red][!!] Found {len(events)} security event(s). Analyzing...[/red]")
    console.print()
    
    by_action = aggregate_by_waf_action(events)
    by_country = aggregate_by_country(events)
    
    summary = "Security Event Summary:\n"
    summary += "By WAF Action:\n"
    for action, count in by_action.items():
        summary += f"  {action}: {count}\n"
    summary += "\nTop Countries:\n"
    for country, count in list(by_country.items())[:10]:
        summary += f"  {country}: {count}\n"
    
    sample_logs = "\n".join([format_cf_security_compact(e) for e in events[:40]])
    
    prompt = f"""Analyze these Cloudflare security events:

{summary}

Sample events (compact format: timestamp | IP | method uri | WAF action | threat score | country):
```
{sample_logs}
```

Provide:
1. What type of attack/threat is this? (DDoS, bot, scanner, etc.)
2. Are there attack patterns (IPs, countries, URIs)?
3. Is Cloudflare blocking effectively?
4. Recommended security actions

Be specific about the threat and actionable in recommendations."""

    query_ollama(prompt, model)


@cf.command('top-ips')
@click.argument('logfile', type=click.Path(exists=True))
@click.option('--tail', '-n', default=5000, type=int, help='Lines to scan (default: 5000)')
@click.option('--limit', '-l', default=20, type=int, help='Top N IPs (default: 20)')
@click.pass_context
def cf_top_ips(ctx, logfile, tail, limit):
    """Find top requesting IPs (potential abuse/bots)"""
    ensure_ollama_running()
    model = ctx.obj['model']
    
    console.print(f"[orange3][CF] Finding top {limit} IPs...[/orange3]")
    
    all_logs = filter_cloudflare_logs(logfile, tail, lambda x: True)
    
    if not all_logs:
        console.print("[red][X] No logs found![/red]")
        return
    
    ip_data = aggregate_by_ip(all_logs)
    top_ips = list(ip_data.items())[:limit]
    
    console.print(f"[yellow][#] Analyzed {len(all_logs)} requests from {len(ip_data)} unique IPs[/yellow]")
    console.print()
    
    summary = "Top IPs by Request Count:\n"
    for ip, details in top_ips:
        pct = (details['count'] / len(all_logs)) * 100
        summary += f"  {ip}: {details['count']} reqs ({pct:.1f}%) | {details['country']} | threat:{details['threat_score']}\n"
    
    prompt = f"""Analyze these top requesting IPs from Cloudflare logs:

Total requests analyzed: {len(all_logs)}
Unique IPs: {len(ip_data)}

{summary}

Provide:
1. Are any of these IPs suspicious? (high volume, high threat score)
2. Do these look like bots, scrapers, or legitimate traffic?
3. Any IPs that should be rate-limited or blocked?
4. Recommendations for IP-based security rules

Focus on identifying abuse vs legitimate traffic."""

    query_ollama(prompt, model)


@cf.command('summary')
@click.argument('logfile', type=click.Path(exists=True))
@click.option('--tail', '-n', default=1000, type=int, help='Lines to summarize (default: 1000)')
@click.pass_context
def cf_summary(ctx, logfile, tail):
    """Quick summary of Cloudflare traffic"""
    ensure_ollama_running()
    model = ctx.obj['model']
    
    console.print("[orange3][CF] Summarizing Cloudflare traffic...[/orange3]")
    
    all_logs = filter_cloudflare_logs(logfile, tail, lambda x: True)
    
    if not all_logs:
        console.print("[red][X] No logs found![/red]")
        return
    
    stats = calculate_stats(all_logs)
    by_country = aggregate_by_country(all_logs)
    
    # Print nice table
    print_stats_table(stats)
    
    # Build summary for LLM
    summary = f"""Traffic Summary ({stats['total_requests']} requests):

Status Codes:
{chr(10).join([f'  {s}: {c} ({c/stats["total_requests"]*100:.1f}%)' for s, c in stats['statuses'].items()])}

Top Countries:
{chr(10).join([f'  {c}: {n}' for c, n in list(by_country.items())[:5]])}

Totals:
  Total Bytes: {stats['total_mb']:.2f} MB
  Error Rate: {stats['error_rate']:.1f}%
  Avg Response Time: {stats['avg_response_time']:.0f}ms
"""
    
    console.print()
    console.print("[cyan][AI] Analysis:[/cyan]")
    console.print()
    
    prompt = f"""Analyze this Cloudflare traffic summary and provide a brief health assessment:

{summary}

In 3-5 bullet points:
- Is this traffic healthy or concerning?
- Any red flags?
- Quick recommendations?

Be concise."""

    query_ollama(prompt, model)


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == '__main__':
    cli()

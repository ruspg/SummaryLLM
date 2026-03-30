import typer
import sys
import subprocess
from pathlib import Path
from digest_core.diagnostics import export_diagnostics
from digest_core.run import run_digest, run_digest_dry_run
from digest_core.observability.logs import setup_logging

app = typer.Typer(add_completion=False)


@app.command()
def run(
    from_date: str = typer.Option(
        "today", "--from-date", help="Date to process (YYYY-MM-DD or 'today')"
    ),
    sources: str = typer.Option(
        "ews", "--sources", help="Comma-separated source types (e.g., 'ews')"
    ),
    out: str = typer.Option("./out", "--out", help="Output directory path"),
    model: str = typer.Option("qwen3.5-397b", "--model", help="LLM model identifier"),
    window: str = typer.Option(
        "calendar_day", "--window", help="Time window: calendar_day or rolling_24h"
    ),
    state: str = typer.Option(
        None, "--state", help="State directory path (overrides config for SyncState)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Run ingest+normalize only, skip LLM/assemble"
    ),
    force: bool = typer.Option(
        False, "--force", help="Bypass the T-48h idempotency check"
    ),
    dump_ingest: str = typer.Option(
        None, "--dump-ingest", help="Write normalized ingest snapshot to JSON"
    ),
    replay_ingest: str = typer.Option(
        None,
        "--replay-ingest",
        help="Replay a normalized ingest snapshot instead of EWS",
    ),
    validate_citations: bool = typer.Option(
        False,
        "--validate-citations",
        help="Enforce citation validation; exit with code 2 on failures",
    ),
    collect_logs: bool = typer.Option(
        False, "--collect-logs", help="Automatically collect diagnostics after run"
    ),
    log_file: str = typer.Option(None, "--log-file", help="Specify log file path"),
    log_level: str = typer.Option(
        "INFO", "--log-level", help="Log level (DEBUG, INFO, WARNING, ERROR)"
    ),
):
    """Run daily digest job."""
    try:
        # Setup logging
        setup_logging(log_level=log_level, log_file=log_file)

        if dry_run:
            typer.echo("Dry-run mode: ingest+normalize only")
            run_digest_dry_run(
                from_date,
                sources.split(","),
                out,
                model,
                window,
                state,
                validate_citations,
                force=force,
                dump_ingest=dump_ingest,
                replay_ingest=replay_ingest,
            )
            exit_code = 2  # Partial success code
        else:
            citation_validation_passed = run_digest(
                from_date,
                sources.split(","),
                out,
                model,
                window,
                state,
                validate_citations,
                force=force,
                dump_ingest=dump_ingest,
                replay_ingest=replay_ingest,
            )

            # Exit with code 2 if citation validation failed
            if validate_citations and not citation_validation_passed:
                typer.echo("⚠ Citation validation failed", err=True)
                exit_code = 2
            else:
                exit_code = 0  # Success

        # Collect diagnostics if requested
        if collect_logs:
            typer.echo("Collecting diagnostics...")
            try:
                script_dir = Path(__file__).parent.parent.parent / "scripts"
                collect_script = script_dir / "collect_diagnostics.sh"
                if collect_script.exists():
                    subprocess.run([str(collect_script)], check=True)
                    typer.echo("✓ Diagnostics collected successfully")
                else:
                    typer.echo("⚠ Diagnostics script not found", err=True)
            except Exception as e:
                typer.echo(f"⚠ Failed to collect diagnostics: {e}", err=True)

        sys.exit(exit_code)
    except KeyboardInterrupt:
        typer.echo("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)  # Error


@app.command()
def diagnose():
    """Run comprehensive diagnostics and collect system information."""
    try:
        typer.echo("Running ActionPulse diagnostics...")

        # Find scripts directory
        script_dir = Path(__file__).parent.parent.parent / "scripts"

        # Run environment diagnostics
        env_script = script_dir / "print_env.sh"
        if env_script.exists():
            typer.echo("Running environment diagnostics...")
            result = subprocess.run([str(env_script)], capture_output=True, text=True)
            typer.echo(result.stdout)
            if result.stderr:
                typer.echo(result.stderr, err=True)
        else:
            typer.echo("⚠ Environment diagnostics script not found", err=True)

        # Collect comprehensive diagnostics
        collect_script = script_dir / "collect_diagnostics.sh"
        if collect_script.exists():
            typer.echo("Collecting comprehensive diagnostics...")
            result = subprocess.run(
                [str(collect_script)], capture_output=True, text=True
            )
            typer.echo(result.stdout)
            if result.stderr:
                typer.echo(result.stderr, err=True)
        else:
            typer.echo("⚠ Diagnostics collection script not found", err=True)

        typer.echo("✓ Diagnostics completed")

    except Exception as e:
        typer.echo(f"Error running diagnostics: {e}", err=True)
        sys.exit(1)


@app.command("export-diagnostics")
def export_diagnostics_command(
    trace_id: str = typer.Option(
        None, "--trace-id", help="Trace ID of the run to export"
    ),
    out: str = typer.Option(
        ..., "--out", help="Directory where the diagnostic bundle will be written"
    ),
    date: str = typer.Option(
        None, "--date", help="Digest date to export if trace ID is unknown"
    ),
    send_mm: bool = typer.Option(
        False, "--send-mm", help="Send a Mattermost notification for the bundle"
    ),
):
    """Export a redacted diagnostic bundle."""
    try:
        if not trace_id and not date:
            raise typer.BadParameter("Either --trace-id or --date is required")
        archive_path = export_diagnostics(
            trace_id=trace_id,
            out_dir=Path(out),
            date=date,
            send_mm=send_mm,
        )
        typer.echo(str(archive_path))
    except Exception as e:
        typer.echo(f"Error exporting diagnostics: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    app()

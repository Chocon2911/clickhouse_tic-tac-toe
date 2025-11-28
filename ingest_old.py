import os
import sys
import glob
import pathlib
import subprocess
import urllib.parse
from typing import Optional, List, Tuple

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn
from dotenv import load_dotenv
import requests

import clickhouse_connect

app = typer.Typer(add_completion=False)
console = Console()


def find_pairs(base_dir: pathlib.Path) -> List[Tuple[pathlib.Path, pathlib.Path]]:
	"""
	Pair CSV files in data/ with matching SQL files in schema/ by stem.
	Returns list of (csv_path, sql_path)
	"""
	data_dir = base_dir / "data"
	schema_dir = base_dir / "schema"
	csv_files = {pathlib.Path(p).stem: pathlib.Path(p) for p in glob.glob(str(data_dir / "*.csv"))}
	sql_files = {pathlib.Path(p).stem: pathlib.Path(p) for p in glob.glob(str(schema_dir / "*.sql"))}

	pairs: List[Tuple[pathlib.Path, pathlib.Path]] = []
	for stem, csv_path in csv_files.items():
		sql_path = sql_files.get(stem)
		if sql_path and sql_path.exists():
			pairs.append((csv_path, sql_path))
		else:
			console.print(f"[yellow]Warning:[/yellow] Missing schema for CSV '{csv_path.name}'")
	return sorted(pairs, key=lambda t: t[0].name)


def table_name_from_sql(sql_text: str, default_name: str) -> str:
	"""
	Extract table name from a CREATE TABLE statement (simple heuristic).
	Falls back to default_name if not found.
	"""
	text = " ".join(sql_text.strip().split())
	text_upper = text.upper()
	if "CREATE TABLE" in text_upper:
		try:
			after = text_upper.split("CREATE TABLE", 1)[1].strip()
			# Remove IF NOT EXISTS
			if after.startswith("IF NOT EXISTS"):
				after = after[len("IF NOT EXISTS") :].strip()
			# Take until first space or '('
			raw = after.split("(")[0].strip()
			# Recover original casing by matching segment in original text
			orig_after = text.split("CREATE TABLE", 1)[1].strip()
			if orig_after.startswith("IF NOT EXISTS"):
				orig_after = orig_after[len("IF NOT EXISTS") :].strip()
			orig_raw = orig_after.split("(")[0].strip()
			# Remove backticks or quotes
			return orig_raw.strip("`\"")
		except Exception:
			return default_name
	return default_name


def normalize_sql(raw_sql: str) -> str:
	"""
	Some schema files may contain literal '\\n' sequences instead of real newlines.
	Normalize those to actual newlines and tidy whitespace.
	"""
	text = raw_sql
	# Replace escaped newlines/tabs if present
	if "\\n" in text or "\\t" in text or "\\r" in text:
		text = text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\n")
	# Ensure consistent newlines
	text = text.replace("\r\n", "\n").replace("\r", "\n")
	return text.strip()


def get_client(
	host: str,
	port: int,
	username: str,
	password: str,
	database: str,
	compress: bool = True,
	timeout: int = 300,
):
	client = clickhouse_connect.get_client(
		host=host,
		port=port,
		username=username,
		password=password,
		database=database,
		send_receive_timeout=timeout,
		compress=compress,
	)
	# Fast/robust insert settings
	client.set_client_setting("max_insert_block_size", 1_000_000)  # server-side block size
	client.set_client_setting("async_insert", 1)
	client.set_client_setting("wait_for_async_insert", 0)
	return client


def human_size(num_bytes: int) -> str:
	units = ["B", "KB", "MB", "GB", "TB"]
	size = float(num_bytes)
	for unit in units:
		if size < 1024:
			return f"{size:.1f} {unit}"
		size /= 1024
	return f"{size:.1f} PB"


@app.command()
def ingest(
	host: str = typer.Option(..., help="ClickHouse host"),
	port: int = typer.Option(8123, help="ClickHouse HTTP port"),
	username: str = typer.Option("default", help="ClickHouse username"),
	password: str = typer.Option("", help="ClickHouse password", prompt=False, hide_input=True),
	database: str = typer.Option("default", help="Target database"),
	cwd: str = typer.Option(".", help="Project base directory containing data/ and schema/"),
	concurrency: int = typer.Option(1, help="Number of files to load in parallel (1-4 recommended)"),
	dry_run: bool = typer.Option(False, help="Only show plan; do not execute"),
) -> None:
	"""
	Stream large CSV files from data/ into ClickHouse using schema/*.sql.
	Optimized for speed and low memory footprint.
	"""
	base_dir = pathlib.Path(cwd).resolve()
	if not (base_dir / "data").exists() or not (base_dir / "schema").exists():
		console.print("[red]Error:[/red] Expected 'data/' and 'schema/' directories under the base path.")
		typer.Exit(code=2)

	pairs = find_pairs(base_dir)
	if not pairs:
		console.print("[red]No CSV/SQL pairs found.[/red]")
		raise typer.Exit(code=1)

	table = Table(title="Planned Ingestion")
	table.add_column("CSV", style="cyan")
	table.add_column("Schema", style="magenta")
	table.add_column("Size", style="green")
	for csv_path, sql_path in pairs:
		try:
			size = csv_path.stat().st_size
		except Exception:
			size = 0
		table.add_row(csv_path.name, sql_path.name, human_size(size))
	console.print(table)

	if dry_run:
		console.print("[yellow]Dry run complete. No changes made.[/yellow]")
		return

	client = get_client(
		host=host,
		port=port,
		username=username,
		password=password,
		database=database,
	)

	# Create tables and insert data (avoid fancy progress to prevent Windows console unicode issues)
	console.print(f"[cyan]Ingesting {len(pairs)} file(s)...[/cyan]")
	for csv_path, sql_path in pairs:
		console.print(f"- [magenta]{csv_path.name}[/magenta] → [magenta]{sql_path.name}[/magenta]")
		# 1) Ensure table exists
		raw_sql = sql_path.read_text(encoding="utf-8")
		sql_text = normalize_sql(raw_sql)
		target_table = table_name_from_sql(sql_text, default_name=csv_path.stem).strip()
		# Create database if statement references db.table
		if "." in target_table:
			db_name = target_table.split(".", 1)[0].strip("`\" ")
			if db_name:
				client.command(f"CREATE DATABASE IF NOT EXISTS {db_name}")

		# Try to create table, ignore if it already exists
		try:
			client.command(sql_text)
		except Exception as e:
			if "TABLE_ALREADY_EXISTS" not in str(e):
				raise

		# 2) Stream insert CSV using Python requests for proper file streaming
		# This avoids memory issues with large files by streaming data in chunks
		insert_query = f"INSERT INTO {target_table} FORMAT CSV"

		url = f"http://{host}:{port}/"
		auth = (username, password) if password else None

		# Stream file in chunks to avoid loading entire file into memory
		try:
			with open(csv_path, 'rb') as f:
				response = requests.post(
					url,
					data=f,
					headers={'X-ClickHouse-Query': insert_query},
					auth=auth,
					timeout=3600  # 1 hour timeout for large files
				)

				if response.status_code != 200:
					console.print(f"[red]Error inserting {csv_path.name}: HTTP {response.status_code} - {response.text}[/red]")
					raise Exception(f"Failed to insert {csv_path.name}")
		except Exception as e:
			console.print(f"[red]Error inserting {csv_path.name}: {str(e)}[/red]")
			raise

	console.print("[bold green]Ingestion complete.[/bold green]")


@app.command()
def env_example() -> None:
	"""
	Print example environment variables.
	"""
	console.print(
		"\n".join(
			[
				"CLICKHOUSE_HOST=localhost",
				"CLICKHOUSE_PORT=8123",
				"CLICKHOUSE_USER=default",
				"CLICKHOUSE_PASSWORD=",
				"CLICKHOUSE_DATABASE=default",
			]
		)
	)


@app.command()
def run(
	cwd: str = typer.Option(".", help="Project base directory containing data/ and schema/"),
	use_env: bool = typer.Option(True, help="Load .env file if present"),
) -> None:
	"""
	Convenience wrapper that reads connection info from env/.env then runs ingest.
	"""
	base_dir = pathlib.Path(cwd).resolve()
	if use_env:
		env_path = base_dir / ".env"
		if env_path.exists():
			load_dotenv(env_path)
		else:
			load_dotenv()  # load from process or parent if any

	host = os.getenv("CLICKHOUSE_HOST", "localhost")
	port = int(os.getenv("CLICKHOUSE_PORT", "8123"))
	user = os.getenv("CLICKHOUSE_USER", "default")
	password = os.getenv("CLICKHOUSE_PASSWORD", "")
	database = os.getenv("CLICKHOUSE_DATABASE", "default")

	ingest(
		host=host,
		port=port,
		username=user,
		password=password,
		database=database,
		cwd=str(base_dir),
	)


if __name__ == "__main__":
	try:
		app()
	except KeyboardInterrupt:
		console.print("[red]Interrupted[/red]")
		sys.exit(130)


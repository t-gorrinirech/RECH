import json
import random
import sys
from pathlib import Path
from typing import Optional

import typer
import typer.rich_utils

typer.rich_utils.STYLE_TYPES = "bold white"

from core import personalities
from core.assembler import stream_candidates
from core.sanity_checks import run_checks
from core.tokenizer import tokenize
from output.writer import run_generation

DATA_TEMPLATE_NOTE = (
    "You can find the json data template in the config folder, use it there or copy it "
    "and use it wherever. Note that this script only works with the given data fields, "
    "so please don't remove or add any"
)

EXAMPLES = "\n\n".join(
    [
        "Examples:",
        "",
        "1) Basic gamer run, uppercase on:",
        "RECH.py -p gamer --input config/input_template.json -s small -Uc",
        "",
        "2) Paranoid, large size, custom symbols capped at 3 per password, seeded, custom output:",
        "RECH.py -p paranoid --input in.json -s large -sc !,@,$,% -lc 3 --seed 42 -o out.txt",
        "",
        "3) Corporate, length range, numbers up front, spaces allowed, debug + relax:",
        "RECH.py -p corporate --input in.json -r 8,16 -nf -sP --debug --allow-relax",
        "",
        "4) Lazy, numbers up front, max 2 symbols per password, uppercase, length window:",
        "RECH.py -p lazy --input in.json -s 50000 -r 8,16 -nf -lc 2 -Uc -sc .,!,@",
        "",
        "5) Technical, custom size, deeper token combos, seeded and reproducible:",
        "RECH.py -p technical --input in.json -s 200000 --depth 4 -sc _,-,. --seed 7",
        "",
        DATA_TEMPLATE_NOTE,
    ]
)

app = typer.Typer(
    add_completion=False,
    help="RECH - Ruthless Exposure of Credential Habits",
    context_settings={"help_option_names": ["-h", "--help"]},
)

ROOT = Path(__file__).resolve().parent
DEFAULT_FIELD_TYPES = ROOT / "config" / "field_types.json"
DEFAULT_FIELD_TIERS = ROOT / "config" / "field_tiers.json"
DEFAULT_SYMBOL_POOL = ["_", ".", "-", "!", "@", "*", "$", "?", "&", "%"]
SIZE_PRESETS = {"small": 300_000, "medium": 700_000, "large": 1_000_000}

SC_FLAGS = {"-sc", "--special-chars"}
SC_SENTINEL = "__RECH_DEFAULT_SC__"
SC_ERROR = (
    "Invalid format for '-sc' option. "
    "Correct format example !,@,$,% or leave blank for default set"
)
KNOWN_FLAGS = {
    "-p",
    "--personality",
    "-lp",
    "--list",
    "--input",
    "-r",
    "--range",
    "-sc",
    "--special-chars",
    "-sP",
    "--spaces",
    "-Uc",
    "--upper-case",
    "-nf",
    "--num-first",
    "-lc",
    "--limit-characters",
    "-s",
    "--size",
    "-o",
    "--output",
    "--depth",
    "--debug",
    "--allow-relax",
    "--seed",
    "--help",
}


def _parse_size(value: str) -> int:
    if value in SIZE_PRESETS:
        return SIZE_PRESETS[value]
    try:
        parsed = int(value)
    except ValueError:
        raise typer.BadParameter(
            f"--size must be one of {list(SIZE_PRESETS)} or an integer"
        )
    if parsed <= 0:
        raise typer.BadParameter("--size must be > 0")
    return parsed


def _parse_range(value: str):
    parts = value.split(",")
    if len(parts) != 2:
        raise typer.BadParameter("--range must be 'min,max' (example: 8,20)")
    try:
        minimum, maximum = int(parts[0]), int(parts[1])
    except ValueError:
        raise typer.BadParameter("--range values must be integers")
    return minimum, maximum


def _resolve_special_chars(value: Optional[str]):
    if value is None:
        return False, []
    if value == SC_SENTINEL:
        return True, list(DEFAULT_SYMBOL_POOL)
    pool = []
    for part in value.split(","):
        if len(part) != 1 or part.isspace() or part.isalnum() or not part.isprintable():
            raise typer.BadParameter(SC_ERROR)
        if part not in pool:
            pool.append(part)
    if not pool:
        raise typer.BadParameter(SC_ERROR)
    return True, pool


def _normalize_sc_argv(argv=None):
    argv = sys.argv if argv is None else argv
    index = 1
    while index < len(argv):
        token = argv[index]
        if token in SC_FLAGS:
            following = argv[index + 1] if index + 1 < len(argv) else None
            bare = (
                following is None
                or following in KNOWN_FLAGS
                or following.startswith("--")
            )
            if bare:
                argv[index] = f"--special-chars={SC_SENTINEL}"
        index += 1
    return argv


def run():
    _normalize_sc_argv()
    app()


def _list_personalities(value: bool):
    if not value:
        return
    typer.echo("\n--- Available Personalities ---\n")
    for personality_id in personalities.available_personalities():
        profile = personalities.load_personality(personality_id)
        typer.echo(f"{personality_id}  ({profile.display_name})")
    typer.echo("\n")
    raise typer.Exit()


def _load_json(path: Path):
    if not path.exists():
        raise typer.BadParameter(f"file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _emit_warnings(warnings):
    if not warnings:
        return
    label = typer.style("warning:", fg=typer.colors.YELLOW, bold=True)
    for warning in warnings:
        typer.echo(f"{label} {warning}", err=True)
    typer.echo("", err=True)


def _emit_errors(errors):
    label = typer.style("error:", fg=typer.colors.RED, bold=True)
    for error in errors:
        typer.echo(f"{label} {error}", err=True)


def _metric_row(label: str, value: str, accent=typer.colors.CYAN):
    marker = typer.style("›", fg=accent, bold=True)
    name = typer.style(label, fg=typer.colors.BRIGHT_BLACK)
    typer.echo(f"  {marker} {name}  {typer.style(value, bold=True)}", err=True)


RELAX_MESSAGE = "It's not stuck, it just needs its time to think..."


def _make_progress():
    is_tty = sys.stderr.isatty()
    bar_width = 20
    relax_line = (
        "  "
        + typer.style("Relax:", fg=typer.colors.GREEN, bold=True)
        + f" {RELAX_MESSAGE}"
    )
    state = {"relax_shown": False}

    def progress(done, total, relax=False):
        pct = int(done / total * 100) if total else 100
        pct = min(pct, 100)
        if is_tty:
            filled = pct * bar_width // 100
            bar = typer.style("█" * filled, fg=typer.colors.CYAN) + "░" * (
                bar_width - filled
            )
            bar_line = f"\r\033[K  generating [{bar}] {pct:3d}%  ({done}/{total})"
            if relax:
                typer.echo(bar_line, nl=False, err=True)
                typer.echo(f"\n\033[K{relax_line}\033[A", nl=False, err=True)
                state["relax_shown"] = True
            elif state["relax_shown"]:
                typer.echo(bar_line, nl=False, err=True)
                typer.echo("\n\033[K\033[A", nl=False, err=True)
                state["relax_shown"] = False
            else:
                typer.echo(bar_line, nl=False, err=True)
        else:
            if relax and not state["relax_shown"]:
                typer.echo(relax_line, err=True)
                state["relax_shown"] = True
            elif not relax:
                state["relax_shown"] = False
            typer.echo(f"generating... {pct}% ({done}/{total})", err=True)

    return progress, is_tty


def _emit_metrics(profile, metrics, debug_path):
    typer.echo("", err=True)
    header = typer.style(
        "── run metrics ──────────────────────", fg=typer.colors.CYAN, bold=True
    )
    typer.echo(header, err=True)
    _metric_row("personality ", f"{profile.personality_id} ({profile.display_name})")
    generated = typer.style(str(metrics["generated"]), fg=typer.colors.GREEN, bold=True)
    _metric_row("generated   ", f"{generated} / {metrics['requested']}")
    if metrics["exhausted"]:
        note = typer.style(
            "! combinatorial space exhausted before reaching --size",
            fg=typer.colors.YELLOW,
        )
        typer.echo(f"  {note}", err=True)
    _metric_row(
        "length      ",
        f"min {metrics['min_length']} · avg {metrics['average_length']} · max {metrics['max_length']}",
    )
    _metric_row("with symbol ", f"{metrics['percent_with_symbol']}%")
    _metric_row("uppercase   ", f"{metrics['percent_with_uppercase']}%")
    _metric_row("top fields  ", str(metrics["top_fields"]))
    _metric_row("elapsed     ", f"{metrics['elapsed_seconds']}s")
    _metric_row("wordlist    ", metrics["output_path"], accent=typer.colors.GREEN)
    if debug_path:
        _metric_row("debug       ", debug_path, accent=typer.colors.GREEN)
    typer.echo(
        typer.style("─────────────────────────────────────", fg=typer.colors.CYAN),
        err=True,
    )


@app.command(
    epilog=EXAMPLES,
    options_metavar="-p <personality> -s <size> --input <path> [OPTIONS]",
)
def main(
    personality: str = typer.Option(
        ...,
        "-p",
        "--personality",
        help="one of the defined personalities. Use -lp to list them",
    ),
    list_personalities: bool = typer.Option(
        False,
        "-lp",
        "--list",
        help="list available personalities",
        is_eager=True,
        callback=_list_personalities,
    ),
    input_path: str = typer.Option(
        ..., "--input", help="path to the completed data file"
    ),
    length_range: str = typer.Option(
        "6,20", "-r", "--range", help="password length range, example: 8,20"
    ),
    special_chars: Optional[str] = typer.Option(
        None,
        "-sc",
        "--special-chars",
        help="comma-separated symbols (example !,@,$,%), or -sc alone for the default pool",
    ),
    spaces: bool = typer.Option(
        False, "-sP", "--spaces", help="allow spaces inside passwords (off by default)"
    ),
    uppercase: bool = typer.Option(
        False,
        "-Uc",
        "--upper-case",
        help="apply uppercase letters (mainly the first char of each word), off by default",
    ),
    num_first: bool = typer.Option(
        False,
        "-nf",
        "--num-first",
        help="allow numbers to appear at the start of passwords (e.g. 1600tomilanus), off by default",
    ),
    limit_characters: Optional[int] = typer.Option(
        None,
        "-lc",
        "--limit-characters",
        help="max number of special symbols allowed per password (e.g. -lc 2)",
    ),
    size: str = typer.Option(..., "-s", "--size", help="small|medium|large|N"),
    output_path: str = typer.Option(
        "wordlist.txt", "-o", "--output", help="output file path"
    ),
    depth: int = typer.Option(
        3, "--depth", help="max data fields combined per password"
    ),
    debug: bool = typer.Option(
        False, "--debug", help="write metadata jsonl alongside the wordlist"
    ),
    allow_relax: bool = typer.Option(
        False, "--allow-relax", help="relax restrictions if size exceeds real space"
    ),
    seed: Optional[int] = typer.Option(
        None,
        "--seed",
        help="seed for reproducibility. Use the SAME OPTIONS if you want the same RESULT!!!",
    ),
):
    available = personalities.available_personalities()
    if personality not in available:
        raise typer.BadParameter(
            f"unknown personality '{personality}'. available: {', '.join(available)}"
        )

    size_value = _parse_size(size)
    range_value = _parse_range(length_range)
    special_present, forced_pool = _resolve_special_chars(special_chars)
    if limit_characters is not None and limit_characters < 0:
        raise typer.BadParameter("--limit-characters must be >= 0")

    input_file = Path(input_path)
    if not input_file.exists():
        raise typer.BadParameter(
            f"--input path not found: {input_path}\n\n{DATA_TEMPLATE_NOTE}"
        )
    input_data = _load_json(input_file)
    field_types = _load_json(DEFAULT_FIELD_TYPES)
    field_tiers = _load_json(DEFAULT_FIELD_TIERS)
    profile = personalities.load_personality(personality)
    tokens = tokenize(
        input_data,
        field_types,
        allow_spaces=spaces,
        allow_symbols=special_present,
        field_tiers=field_tiers,
        priority_fields=profile.priority_fields,
    )

    if not tokens:
        _emit_errors(["no usable fields in input (all empty or 'WRITE HERE')"])
        raise typer.Exit(code=1)

    checks = run_checks(
        tokens,
        profile,
        special_present,
        range_value,
        size_value,
        depth,
        allow_relax,
        output_path,
        debug,
        forced_pool=forced_pool,
        uppercase=uppercase,
    )
    _emit_warnings(checks.warnings)
    if not checks.ok():
        _emit_errors(checks.errors)
        raise typer.Exit(code=1)

    if seed is None:
        seed = random.randrange(2**32)
    typer.echo(
        typer.style("seed:", fg=typer.colors.CYAN, bold=True) + f" {seed}", err=True
    )
    rng = random.Random(seed)

    candidates = stream_candidates(
        tokens,
        profile,
        forced_pool,
        special_present,
        rng,
        depth_max=depth,
        uppercase=uppercase,
        num_first=num_first,
    )
    debug_path = str(Path(output_path).with_suffix(".debug.jsonl")) if debug else None
    progress, is_tty = _make_progress()
    metrics = run_generation(
        candidates,
        size_value,
        range_value,
        output_path,
        debug_path,
        progress=progress,
        symbol_limit=limit_characters,
    )
    if is_tty:
        typer.echo("", err=True)
    _emit_metrics(profile, metrics, debug_path)


if __name__ == "__main__":
    run()

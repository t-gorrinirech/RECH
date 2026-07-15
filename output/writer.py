import json
import time
from collections import Counter
from pathlib import Path
from typing import Iterator, Optional, Tuple

WRITE_CHUNK = 10000
STALL_FLOOR = 2000
STALL_FACTOR = 3
STALL_CEILING = 2000000


def _stall_limit(generated: int) -> int:
    return min(max(STALL_FLOOR, generated * STALL_FACTOR), STALL_CEILING)


def _has_symbol(text: str) -> bool:
    return any(not char.isalnum() for char in text)


def _has_upper(text: str) -> bool:
    return any(char.isupper() for char in text)


def run_generation(candidates: Iterator[dict], size: int, length_range: Tuple[int, int],
                   output_path: str, debug_path: Optional[str] = None, progress=None) -> dict:
    minimum, maximum = length_range
    progress_step = max(1, size // 20)
    next_mark = progress_step
    last_reported = 0
    seen = set()
    lengths = Counter()
    token_usage = Counter()
    symbol_count = 0
    upper_count = 0
    generated = 0
    consecutive_non_new = 0
    exhausted = False
    start = time.perf_counter()

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    out_file = open(output_path, "w", encoding="utf-8")
    debug_file = open(debug_path, "w", encoding="utf-8") if debug_path else None
    buffer = []
    debug_buffer = []

    try:
        for candidate in candidates:
            if generated >= size:
                break
            password = candidate["password"]
            if not password or not (minimum <= len(password) <= maximum):
                consecutive_non_new += 1
                if consecutive_non_new >= _stall_limit(generated):
                    exhausted = True
                    break
                continue
            if password in seen:
                consecutive_non_new += 1
                if consecutive_non_new >= _stall_limit(generated):
                    exhausted = True
                    break
                continue
            seen.add(password)
            consecutive_non_new = 0
            generated += 1
            if progress is not None and generated >= next_mark:
                progress(generated, size)
                last_reported = generated
                next_mark += progress_step
            buffer.append(password)
            lengths[len(password)] += 1
            token_usage.update(candidate["tokens"])
            if _has_symbol(password):
                symbol_count += 1
            if _has_upper(password):
                upper_count += 1
            if len(buffer) >= WRITE_CHUNK:
                out_file.write("\n".join(buffer) + "\n")
                buffer.clear()
            if debug_file is not None:
                debug_buffer.append(json.dumps({
                    "password": password,
                    "personality": candidate["personality"],
                    "mode": candidate["mode"],
                    "tokens": candidate["tokens"],
                }))
                if len(debug_buffer) >= WRITE_CHUNK:
                    debug_file.write("\n".join(debug_buffer) + "\n")
                    debug_buffer.clear()
        if buffer:
            out_file.write("\n".join(buffer) + "\n")
        if debug_file is not None and debug_buffer:
            debug_file.write("\n".join(debug_buffer) + "\n")
    finally:
        out_file.close()
        if debug_file is not None:
            debug_file.close()

    if progress is not None and generated != last_reported:
        progress(generated, size)

    elapsed = time.perf_counter() - start
    total_length = sum(length * count for length, count in lengths.items())
    return {
        "requested": size,
        "generated": generated,
        "exhausted": exhausted,
        "elapsed_seconds": round(elapsed, 3),
        "average_length": round(total_length / generated, 2) if generated else 0,
        "min_length": min(lengths) if lengths else 0,
        "max_length": max(lengths) if lengths else 0,
        "percent_with_symbol": round(symbol_count / generated * 100, 2) if generated else 0,
        "percent_with_uppercase": round(upper_count / generated * 100, 2) if generated else 0,
        "top_fields": token_usage.most_common(10),
        "output_path": output_path,
        "debug_path": debug_path,
    }

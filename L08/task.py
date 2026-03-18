#!/usr/bin/env python3
from pathlib import Path
import sys

from failure_fetch import (
    build_token_limited_failure_log,
    download_failure_log,
    get_api_key,
    render_summary_text,
    summarize_compact_log,
    summarize_failure_log,
    run_verification_cycle,
)


if __name__ == "__main__":
    try:
        log_path = download_failure_log()
        compact_info = build_token_limited_failure_log(log_path)
        compact_path = compact_info["path"]
        raw_summary = summarize_failure_log(log_path)
        compact_summary = summarize_compact_log(compact_path)
        verification = run_verification_cycle(get_api_key(), source_path=log_path, target_path=compact_path)
        print("Pobrano failure.log")
        print(render_summary_text(raw_summary, label="failure.log"))
        print()
        print("Utworzono failure_compact.log")
        print(render_summary_text(compact_summary, label="failure_compact.log"))
        print(f"Tokeny failure_compact.log: {compact_info['token_count']} / {compact_info['max_tokens']}")
        print()
        print("Weryfikacja:")
        print(verification)
    except Exception as error:
        print(f"ERROR: {error}")
        sys.exit(1)

from pathlib import Path

from sattlint.app_analysis import force_refresh_ast
from sattlint.config_io import load_config

trace_path = Path("/home/sqhj/projects/SattLint/artifacts/tmp/refresh_then_report_kahaxdilute.trace")
trace_path.write_text("started\n")

cfg, _ = load_config(Path("/home/sqhj/.config/sattlint/config.toml"))
trace_path.write_text(trace_path.read_text() + "config-loaded\n")
force_refresh_ast(cfg)
trace_path.write_text(trace_path.read_text() + "refreshed\n")
print("done")

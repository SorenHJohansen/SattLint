from pathlib import Path

from sattlint import engine
from sattlint._app_analysis_loading import load_project
from sattlint.analyzers.variables import IssueKind, analyze_variables
from sattlint.app_analysis import target_is_library
from sattlint.app_support import TargetLoadError, require_analyzed_targets
from sattlint.cache import ASTCache, compute_cache_key, get_cache_dir
from sattlint.config_io import load_config

trace_path = Path("/home/sqhj/projects/SattLint/artifacts/tmp/check_kahaxdilute_menu_path.trace")
trace_path.write_text("started\n")

cfg, _ = load_config(Path("/home/sqhj/.config/sattlint/config.toml"))
trace_path.write_text(trace_path.read_text() + "config-loaded\n")

for use_cache in (True, False):
    project_bp, graph = load_project(
        cfg,
        target_name="KaHAXDiluteLib",
        use_cache=use_cache,
        use_file_ast_cache=True,
        require_analyzed_targets_fn=require_analyzed_targets,
        cache_key_for_target_fn=lambda current_cfg, target_name: compute_cache_key(
            {**current_cfg, "analysis_target": target_name}
        ),
        target_load_error_factory=TargetLoadError,
        get_cache_dir_fn=get_cache_dir,
        ast_cache_cls=ASTCache,
        engine_module=engine,
        status_update_fn=None,
    )
    trace_path.write_text(trace_path.read_text() + f"loaded use_cache={use_cache}\n")
    report = analyze_variables(
        project_bp,
        unavailable_libraries=graph.unavailable_libraries,
        analyzed_target_is_library=target_is_library(cfg, project_bp, graph),
        config=cfg,
    )
    trace_path.write_text(trace_path.read_text() + f"analyzed use_cache={use_cache} issues={len(report.issues)}\n")
    dtype_rows = sorted(
        (issue.datatype_name, issue.field_path)
        for issue in report.issues
        if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD
    )
    out_path = Path(f"/home/sqhj/projects/SattLint/artifacts/tmp/check_kahaxdilute_menu_path_{use_cache}.txt")
    out_path.write_text("\n".join(f"{dtype}:{field}" for dtype, field in dtype_rows))
    trace_path.write_text(trace_path.read_text() + f"wrote use_cache={use_cache} rows={len(dtype_rows)}\n")

print("done")

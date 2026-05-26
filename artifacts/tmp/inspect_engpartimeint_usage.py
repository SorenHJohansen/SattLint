from pathlib import Path

from sattlint import engine
from sattlint._app_analysis_loading import load_project
from sattlint.analyzers.variables import VariablesAnalyzer
from sattlint.app_analysis import target_is_library
from sattlint.app_support import TargetLoadError, require_analyzed_targets
from sattlint.cache import ASTCache, compute_cache_key, get_cache_dir
from sattlint.config_io import load_config

cfg, _ = load_config(Path("/home/sqhj/.config/sattlint/config.toml"))
project_bp, graph = load_project(
    cfg,
    target_name="KaHAXDiluteLib",
    use_cache=True,
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
analyzer = VariablesAnalyzer(
    project_bp,
    unavailable_libraries=graph.unavailable_libraries,
    analyzed_target_is_library=target_is_library(cfg, project_bp, graph),
    config=cfg,
)
analyzer.run()
lines: list[str] = []
for mt in project_bp.moduletype_defs or []:
    if mt.name.casefold() != "engpartimeint":
        continue
    lines.append(f"typedef {mt.name} origin={mt.origin_lib}/{mt.origin_file}")
    for param in mt.moduleparameters or []:
        usage = analyzer.get_usage(param)
        lines.append(
            f"  {param.name} read={usage.read} written={usage.written} display_only={usage.is_display_only} field_reads={sorted((usage.field_reads or {}).keys())} usage_locations={usage.usage_locations[:6]}"
        )
Path("/home/sqhj/projects/SattLint/artifacts/tmp/inspect_engpartimeint_usage.txt").write_text("\n".join(lines))
print("done")

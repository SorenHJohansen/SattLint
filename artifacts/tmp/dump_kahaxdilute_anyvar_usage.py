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
interesting_names = ["steptext", "pt", "partext", "mm", "minmax", "optext", "warningtext"]
lines: list[str] = []
for name in interesting_names:
    matches = analyzer.any_var_index.get(name, [])
    lines.append(f"NAME {name} count={len(matches)}")
    for variable in matches:
        usage = analyzer.get_usage(variable)
        lines.append(
            f"  {variable.name}:{variable.datatype_text} origin={getattr(variable, 'origin_file', None)} reads={sorted((usage.field_reads or {}).keys())[:40]}"
        )
Path("/home/sqhj/projects/SattLint/artifacts/tmp/dump_kahaxdilute_anyvar_usage.txt").write_text("\n".join(lines))
print("done")

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
interesting_datatypes = {"MMType", "PTType", "StepTextType", "OpTextType", "DiluteWarningTextTyp"}
lines: list[str] = []
for path, context in sorted(analyzer.contexts_by_module_path.items()):
    hits = [
        f"{var.name}:{var.datatype_text}"
        for var in context.env.values()
        if getattr(var, "datatype_text", None) in interesting_datatypes
    ]
    if hits:
        lines.append(f"{' -> '.join(path)} :: {sorted(set(hits))}")
Path("/home/sqhj/projects/SattLint/artifacts/tmp/dump_kahaxdilute_contexts.txt").write_text("\n".join(lines))
print("done")

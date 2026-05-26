from pathlib import Path

from sattlint import engine
from sattlint._app_analysis_loading import load_project
from sattlint.app_support import TargetLoadError, require_analyzed_targets
from sattlint.cache import ASTCache, compute_cache_key, get_cache_dir
from sattlint.config_io import load_config

trace_path = Path("/home/sqhj/projects/SattLint/artifacts/tmp/dump_kahaxdilute_root_typedef_names.trace")
trace_path.write_text("started\n")

cfg, _ = load_config(Path("/home/sqhj/.config/sattlint/config.toml"))
project_bp, _graph = load_project(
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
trace_path.write_text(trace_path.read_text() + "loaded\n")
root_names = [
    mt.name
    for mt in (project_bp.moduletype_defs or [])
    if (getattr(mt, "origin_lib", None) or "").casefold() == "kahaxdilutelib"
]
Path("/home/sqhj/projects/SattLint/artifacts/tmp/dump_kahaxdilute_root_typedef_names.txt").write_text(
    "\n".join(sorted(root_names))
)
trace_path.write_text(trace_path.read_text() + f"wrote count={len(root_names)}\n")
print("done")

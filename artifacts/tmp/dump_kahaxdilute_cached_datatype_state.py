from pathlib import Path

from sattline_parser.models.ast_model import Simple_DataType
from sattlint import engine
from sattlint._app_analysis_loading import load_project
from sattlint.analyzers.variable_issue_collection import _iter_variables_for_datatype_field_analysis
from sattlint.analyzers.variables import VariablesAnalyzer
from sattlint.app_analysis import target_is_library
from sattlint.app_support import TargetLoadError, require_analyzed_targets
from sattlint.cache import ASTCache, compute_cache_key, get_cache_dir
from sattlint.config_io import load_config

trace_path = Path("/home/sqhj/projects/SattLint/artifacts/tmp/dump_kahaxdilute_cached_datatype_state.trace")
trace_path.write_text("started\n")

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
trace_path.write_text(trace_path.read_text() + "loaded\n")
analyzer = VariablesAnalyzer(
    project_bp,
    unavailable_libraries=graph.unavailable_libraries,
    analyzed_target_is_library=target_is_library(cfg, project_bp, graph),
    config=cfg,
)
analyzer.run()
trace_path.write_text(trace_path.read_text() + "analyzed\n")
interesting = {"MMType", "PTType", "StepTextType", "OpTextType", "DiluteWarningTextTyp"}
lines: list[str] = []
for path, variable, role, root_owned_decl in _iter_variables_for_datatype_field_analysis(analyzer):
    if isinstance(variable.datatype, Simple_DataType):
        continue
    if variable.datatype_text not in interesting:
        continue
    usage = analyzer.get_usage(variable)
    lines.append(
        f"path={' -> '.join(path)} | role={role} | root_owned={root_owned_decl} | {variable.name}:{variable.datatype_text}"
    )
    lines.append(f"  whole={bool(usage.usage_locations)}")
    lines.append(f"  reads={sorted((usage.field_reads or {}).keys())[:60]}")
    lines.append(f"  writes={sorted((usage.field_writes or {}).keys())[:40]}")
Path("/home/sqhj/projects/SattLint/artifacts/tmp/dump_kahaxdilute_cached_datatype_state.txt").write_text(
    "\n".join(lines)
)
trace_path.write_text(trace_path.read_text() + "wrote\n")
print("done")

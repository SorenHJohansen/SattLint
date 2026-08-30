"""Path lookup, cache, and prefetch helpers for the project loader."""

from __future__ import annotations

import importlib
from pathlib import Path
from time import perf_counter

from sattline_parser.models.ast_model import BasePicture

from ._engine_loader_base import (
    CodeMode,
    PrefetchedDependencyCandidate,
    PrefetchedLoadResult,
    SattLineProjectLoaderBase,
    code_ext,
    deps_ext,
    ensure_local_validation,
    mark_local_validation,
)


class SattLineProjectLoaderLookupMixin(SattLineProjectLoaderBase):
    def _engine_module(self):
        return importlib.import_module("sattlint.engine")

    def _is_ignored_base(self, base: Path) -> bool:
        try:
            base_r = base.resolve()
        except OSError:
            base_r = base
        return any(base_r == ign for ign in self._ignored_dirs)

    def _is_allowed_base(self, base: Path) -> bool:
        allowed = [self.program_dir, *self.other_lib_dirs, self.abb_lib_dir]
        try:
            base_r = base.resolve()
        except OSError:
            base_r = base
        for candidate in allowed:
            try:
                cand_r = candidate.resolve()
            except OSError:
                cand_r = candidate
            if base_r == cand_r:
                return True
        return False

    def _resolved_lookup_path(self, path: Path | None) -> Path | None:
        if path is None:
            return None
        try:
            return path.resolve()
        except OSError:
            return path

    def _lookup_path_key(self, path: Path) -> str:
        return str(self._resolved_lookup_path(path)).casefold()

    def _lookup_source_dirs(self) -> tuple[Path, ...]:
        return (self.program_dir, *self.other_lib_dirs, self.abb_lib_dir)

    def _is_lookup_relative_to(self, path: Path | None, root: Path | None) -> bool:
        resolved_path = self._resolved_lookup_path(path)
        resolved_root = self._resolved_lookup_path(root)
        if resolved_path is None or resolved_root is None:
            return False
        try:
            resolved_path.relative_to(resolved_root)
        except ValueError:
            return False
        return True

    def _first_lookup_branch_under(self, root: Path, path: Path) -> str | None:
        resolved_root = self._resolved_lookup_path(root)
        resolved_path = self._resolved_lookup_path(path)
        if resolved_root is None or resolved_path is None:
            return None
        try:
            relative_parts = resolved_path.relative_to(resolved_root).parts
        except ValueError:
            return None
        return relative_parts[0] if relative_parts else None

    def _shared_lookup_root_for(self, requester_dir: Path | None) -> Path | None:
        requester = self._resolved_lookup_path(requester_dir)
        if requester is None:
            return None

        candidate_dirs = [
            resolved
            for source_dir in self._lookup_source_dirs()
            if (resolved := self._resolved_lookup_path(source_dir)) is not None and resolved != requester
        ]
        current = requester
        while True:
            branches: set[str] = set()
            for source_dir in candidate_dirs:
                if not self._is_lookup_relative_to(source_dir, current):
                    continue
                branch = self._first_lookup_branch_under(current, source_dir)
                if branch is None:
                    continue
                branches.add(branch)
                if len(branches) > 1:
                    return current
            parent = current.parent
            if parent == current:
                break
            current = parent

        return None

    def _ordered_lookup_bases(self, requester_dir: Path | None) -> tuple[Path, ...]:
        requester = self._resolved_lookup_path(requester_dir)
        abb_dir = self._resolved_lookup_path(self.abb_lib_dir)
        ordered: list[Path] = []
        seen: set[str] = set()

        def add(path: Path | None) -> None:
            resolved = self._resolved_lookup_path(path)
            if resolved is None or self._is_ignored_base(resolved):
                return
            key = self._lookup_path_key(resolved)
            if key in seen:
                return
            seen.add(key)
            ordered.append(resolved)

        if requester is not None and self._is_allowed_base(requester):
            add(requester)

        cluster_root = self._shared_lookup_root_for(requester)
        if cluster_root is not None and requester is not None:
            requester_branch = self._first_lookup_branch_under(cluster_root, requester)
            same_branch: list[Path] = []
            sibling_branch: list[Path] = []
            for source_dir in self._lookup_source_dirs():
                resolved = self._resolved_lookup_path(source_dir)
                if resolved is None or resolved in (requester, abb_dir):
                    continue
                if not self._is_lookup_relative_to(resolved, cluster_root):
                    continue
                branch = self._first_lookup_branch_under(cluster_root, resolved)
                if requester_branch is not None and branch == requester_branch:
                    same_branch.append(resolved)
                else:
                    sibling_branch.append(resolved)
            for source_dir in sorted(same_branch, key=self._lookup_path_key):
                add(source_dir)
            for source_dir in sorted(sibling_branch, key=self._lookup_path_key):
                add(source_dir)

        for source_dir in self._lookup_source_dirs():
            resolved = self._resolved_lookup_path(source_dir)
            if resolved == abb_dir:
                continue
            add(resolved)

        add(abb_dir)
        return tuple(ordered)

    def _find_in_ordered_bases_without_cache(
        self,
        name: str,
        extensions: list[str],
        *,
        requester_dir: Path | None,
        kind: str,
    ) -> Path | None:
        for base in self._ordered_lookup_bases(requester_dir):
            indexed = self._find_in_index(base=base, name=name, extensions=extensions)
            if indexed is not None:
                self.dbg(f"Using ordered lookup file: {indexed}")
                set_cache = getattr(self._lookup_cache, "set", None)
                if callable(set_cache):
                    set_cache(kind, name, self.mode.value, base, indexed.suffix.lower())
                return indexed

            for ext in extensions:
                candidate = base / f"{name}{ext}"
                self.dbg(f"Checking ordered lookup file: {candidate} (exists={candidate.exists()})")
                if candidate.exists():
                    self.dbg(f"Using ordered lookup file: {candidate}")
                    set_cache = getattr(self._lookup_cache, "set", None)
                    if callable(set_cache):
                        set_cache(kind, name, self.mode.value, base, ext)
                    self._add_to_index(base, name, candidate)
                    return candidate

        return None

    def _get_base_index(self, base: Path) -> dict[str, dict[str, Path]]:
        if base in self._base_indexes:
            return self._base_indexes[base]
        index: dict[str, dict[str, Path]] = {}
        if not base.exists() or not base.is_dir():
            self._base_indexes[base] = index
            return index

        for entry in base.iterdir():
            if not entry.is_file():
                continue
            ext = entry.suffix.lower()
            if ext not in {".s", ".x", ".l", ".z"}:
                continue
            stem = entry.stem.casefold()
            index.setdefault(stem, {})[ext] = entry

        self._base_indexes[base] = index
        return index

    def _find_in_index(
        self,
        *,
        base: Path,
        name: str,
        extensions: list[str],
    ) -> Path | None:
        index = self._get_base_index(base)
        entries = index.get(name.casefold())
        if not entries:
            return None
        for ext in extensions:
            path = entries.get(ext)
            if path is not None:
                return path
        return None

    def _add_to_index(self, base: Path, name: str, path: Path) -> None:
        index = self._get_base_index(base)
        index.setdefault(name.casefold(), {})[path.suffix.lower()] = path

    def _find_in_cached_base(
        self,
        *,
        kind: str,
        name: str,
        extensions: list[str],
    ) -> Path | None:
        cached = self._lookup_cache.get(kind, name, self.mode.value)
        if not cached:
            return None

        base = Path(cached.get("base_dir", ""))
        if not base or self._is_ignored_base(base):
            return None
        if not self._is_allowed_base(base):
            self._lookup_cache.forget(kind, name, self.mode.value)
            return None

        cached_ext = cached.get("ext")
        ordered_exts = [cached_ext] if cached_ext in extensions else []
        ordered_exts.extend(ext for ext in extensions if ext != cached_ext)

        for ext in ordered_exts:
            path = base / f"{name}{ext}"
            self.dbg(f"Checking cached {kind} file: {path} (exists={path.exists()})")
            if path.exists():
                self.dbg(f"Using cached {kind} file: {path}")
                return path

        self._lookup_cache.forget(kind, name, self.mode.value)
        return None

    def _find_code(self, name: str) -> Path | None:
        return self._find_code_with_context(name, requester_dir=None)

    def _find_code_with_context(
        self,
        name: str,
        *,
        requester_dir: Path | None,
    ) -> Path | None:
        prefetched = self._prefetched_dependency_candidates.get(self._prefetched_dependency_key(name, requester_dir))
        if prefetched is not None and prefetched.code_path is not None:
            return prefetched.code_path

        extensions = [code_ext(self.mode), ".x"] if self.mode == CodeMode.DRAFT else [code_ext(self.mode)]

        if self.contextual_lookup is not None:
            resolved = self.contextual_lookup(name, extensions, requester_dir, "code")
            if resolved is not None:
                self.dbg(f"Using contextual code file: {resolved} (requested by {requester_dir or self.program_dir})")
                return resolved

        ordered = self._find_in_ordered_bases_without_cache(
            name,
            extensions,
            requester_dir=requester_dir,
            kind="code",
        )
        if ordered is not None:
            return ordered

        cached = self._find_in_cached_base(
            kind="code",
            name=name,
            extensions=extensions,
        )
        if cached is not None:
            return cached

        for base in [self.program_dir, *self.other_lib_dirs, self.abb_lib_dir]:
            if self._is_ignored_base(base):
                continue

            indexed = self._find_in_index(
                base=base,
                name=name,
                extensions=extensions,
            )
            if indexed is not None:
                self.dbg(f"Using code file: {indexed}")
                self._lookup_cache.set("code", name, self.mode.value, base, indexed.suffix.lower())
                return indexed

            for ext in extensions:
                path = base / f"{name}{ext}"
                self.dbg(f"Checking code file: {path} (exists={path.exists()})")
                if path.exists():
                    self.dbg(f"Using code file: {path}")
                    self._lookup_cache.set("code", name, self.mode.value, base, ext)
                    self._add_to_index(base, name, path)
                    return path

        self.dbg(f"No code file found for '{name}' in mode={self.mode.value}")
        return None

    def _find_deps_with_context(
        self,
        name: str,
        *,
        requester_dir: Path | None,
    ) -> Path | None:
        prefetched = self._prefetched_dependency_candidates.get(self._prefetched_dependency_key(name, requester_dir))
        if prefetched is not None and prefetched.deps_path is not None:
            return prefetched.deps_path

        extensions = [deps_ext(self.mode), ".z"] if self.mode == CodeMode.DRAFT else [deps_ext(self.mode)]

        if self.contextual_lookup is not None:
            resolved = self.contextual_lookup(name, extensions, requester_dir, "deps")
            if resolved is not None:
                self.dbg(f"Using contextual deps file: {resolved} (requested by {requester_dir or self.program_dir})")
                return resolved

        ordered = self._find_in_ordered_bases_without_cache(
            name,
            extensions,
            requester_dir=requester_dir,
            kind="deps",
        )
        if ordered is not None:
            return ordered

        cached = self._find_in_cached_base(
            kind="deps",
            name=name,
            extensions=extensions,
        )
        if cached is not None:
            return cached

        for base in [self.program_dir, *self.other_lib_dirs, self.abb_lib_dir]:
            if self._is_ignored_base(base):
                continue

            indexed = self._find_in_index(
                base=base,
                name=name,
                extensions=extensions,
            )
            if indexed is not None:
                self.dbg(f"Using deps file: {indexed}")
                self._lookup_cache.set("deps", name, self.mode.value, base, indexed.suffix.lower())
                return indexed

            for ext in extensions:
                path = base / f"{name}{ext}"
                self.dbg(f"Checking deps file: {path} (exists={path.exists()})")
                if path.exists():
                    self.dbg(f"Using deps file: {path}")
                    self._lookup_cache.set("deps", name, self.mode.value, base, ext)
                    self._add_to_index(base, name, path)
                    return path

        self.dbg(f"No deps file found for '{name}' in mode={self.mode.value}")
        return None

    def find_dependency_path(
        self,
        name: str,
        *,
        requester_dir: Path | None,
    ) -> Path | None:
        return self._find_deps_with_context(name, requester_dir=requester_dir)

    def _find_vendor_code(self, name: str) -> Path | None:
        extensions = [code_ext(self.mode), ".x"] if self.mode == CodeMode.DRAFT else [code_ext(self.mode)]
        for ignored_dir in self._ignored_dirs:
            for ext in extensions:
                path = ignored_dir / f"{name}{ext}"
                if path.exists():
                    return path
        return None

    def _find_vendor_deps(self, name: str) -> Path | None:
        extensions = [deps_ext(self.mode), ".z"] if self.mode == CodeMode.DRAFT else [deps_ext(self.mode)]
        for ignored_dir in self._ignored_dirs:
            for ext in extensions:
                path = ignored_dir / f"{name}{ext}"
                if path.exists():
                    return path
        return None

    def _read_deps(self, deps_path: Path) -> list[str]:
        engine_module = self._engine_module()
        text = engine_module.read_text_with_fallback(deps_path)
        lines = text.splitlines()
        names = [line.strip() for line in lines if line.strip()]
        self.dbg(f"Deps from {deps_path.name}: {names}")
        return names

    def read_dependency_names(self, deps_path: Path) -> list[str]:
        return self._read_deps(deps_path)

    def _library_name_for_path(self, code_path: Path) -> str:
        resolved_path = code_path.resolve()
        try:
            program_root = self.program_dir.resolve()
        except OSError:
            program_root = self.program_dir
        if resolved_path.is_relative_to(program_root):
            return program_root.name
        for library_dir in self.other_lib_dirs:
            try:
                resolved_library_dir = library_dir.resolve()
            except OSError:
                resolved_library_dir = library_dir
            if resolved_path.is_relative_to(resolved_library_dir):
                return resolved_library_dir.name
        try:
            resolved_abb_root = self.abb_lib_dir.resolve()
        except OSError:
            resolved_abb_root = self.abb_lib_dir
        if resolved_path.is_relative_to(resolved_abb_root):
            return resolved_abb_root.name
        return resolved_path.parent.name

    def _record_library_name(self, name: str, code_path: Path) -> str:
        library_name = self._library_name_for_path(code_path)
        self._lib_by_name[name.casefold()] = library_name
        return library_name

    def _dependency_library_name(
        self,
        graph: object,
        dependency_name: str,
        dep_bp: BasePicture | None,
    ) -> str | None:
        root_library_name_for_name = getattr(graph, "root_library_name_for_name", None)
        if callable(root_library_name_for_name):
            graph_library_name = root_library_name_for_name(dependency_name)
            if isinstance(graph_library_name, str) and graph_library_name:
                return graph_library_name

        cached_lib = self._lib_by_name.get(dependency_name.casefold())
        if cached_lib:
            return cached_lib

        origin_lib = getattr(dep_bp, "origin_lib", None) if dep_bp is not None else None
        return origin_lib if isinstance(origin_lib, str) and origin_lib else None

    def _parse_one(self, code_path: Path) -> BasePicture:
        engine_module = self._engine_module()
        return engine_module.parser_core_parse_source_file(
            code_path,
            parser=self.parser,
            transformer=self.transformer,
            debug=self.dbg,
        )

    def _load_or_parse(self, code_path: Path, *, owner_name: str | None = None) -> BasePicture | None:
        resolved_owner_name = owner_name or code_path.stem
        started_at = perf_counter()
        prefetched_result = self._prefetched_load_results_by_path.pop(code_path, None)
        if prefetched_result is not None:
            if prefetched_result.ast_cache_save_required:
                cache_save_started_at = perf_counter()
                self._ast_cache.save(code_path, self.mode.value, prefetched_result.basepicture)
                self._record_stage_timing(resolved_owner_name, "ast_cache_save", cache_save_started_at)
            self._record_stage_duration(
                resolved_owner_name,
                "load_or_parse",
                prefetched_result.load_or_parse_duration_s,
            )
            return prefetched_result.basepicture
        if self.use_file_ast_cache:
            cached = self._ast_cache.load(code_path, self.mode.value)
            if isinstance(cached, BasePicture):
                upgraded_cache_entry = ensure_local_validation(cached)
                if upgraded_cache_entry:
                    cache_save_started_at = perf_counter()
                    self._ast_cache.save(code_path, self.mode.value, cached)
                    self._record_stage_timing(resolved_owner_name, "ast_cache_save", cache_save_started_at)
                self._update_status(f"Loading {code_path.stem}: using cached AST from {code_path.name}")
                self.dbg(f"Using cached AST for: {code_path}")
                self._record_stage_timing(resolved_owner_name, "load_or_parse", started_at)
                return cached

        self._update_status(f"Loading {code_path.stem}: parsing {code_path.name}")
        basepicture = self._parse_one(code_path)
        mark_local_validation(basepicture)
        cache_save_started_at = perf_counter()
        self._ast_cache.save(code_path, self.mode.value, basepicture)
        self._record_stage_timing(resolved_owner_name, "ast_cache_save", cache_save_started_at)
        self._record_stage_timing(resolved_owner_name, "load_or_parse", started_at)
        return basepicture

    def _prefetched_dependency_key(self, name: str, requester_dir: Path | None) -> tuple[str, str | None]:
        requester_key = None if requester_dir is None else str(requester_dir)
        return name.casefold(), requester_key.casefold() if requester_key is not None else None

    def _prime_base_indexes(self) -> None:
        for base in [self.program_dir, *self.other_lib_dirs, self.abb_lib_dir]:
            self._get_base_index(base)

    def _prefetch_ast_candidates(self, code_paths: list[Path]) -> dict[Path, PrefetchedLoadResult]:
        if not self.use_file_ast_cache or len(code_paths) < 2:
            return {}

        prefetched: dict[Path, PrefetchedLoadResult] = {}
        for code_path in code_paths:
            started_at = perf_counter()
            cached = self._ast_cache.load(code_path, self.mode.value)
            if not isinstance(cached, BasePicture):
                continue
            save_required = ensure_local_validation(cached)
            prefetched[code_path] = PrefetchedLoadResult(
                basepicture=cached,
                load_or_parse_duration_s=perf_counter() - started_at,
                ast_cache_save_required=save_required,
            )
        return prefetched

    def _prefetch_dependency_candidates(self, dep_names: list[str], *, requester_dir: Path | None) -> None:
        if self.contextual_lookup is not None or len(dep_names) < 2:
            return

        unique_dep_names: list[str] = []
        seen: set[str] = set()
        for dep_name in dep_names:
            dep_key = dep_name.casefold()
            if dep_key in seen:
                continue
            seen.add(dep_key)
            unique_dep_names.append(dep_name)

        if len(unique_dep_names) < 2:
            return

        self._prime_base_indexes()
        code_extensions = [code_ext(self.mode), ".x"] if self.mode == CodeMode.DRAFT else [code_ext(self.mode)]
        deps_extensions = [deps_ext(self.mode), ".z"] if self.mode == CodeMode.DRAFT else [deps_ext(self.mode)]
        code_paths_to_prefetch: list[Path] = []
        for dep_name in unique_dep_names:
            code_path = self._find_in_ordered_bases_without_cache(
                dep_name,
                code_extensions,
                requester_dir=requester_dir,
                kind="code",
            )
            deps_path = self._find_in_ordered_bases_without_cache(
                dep_name,
                deps_extensions,
                requester_dir=requester_dir,
                kind="deps",
            )
            candidate = PrefetchedDependencyCandidate(
                name=dep_name,
                requester_dir=requester_dir,
                code_path=code_path,
                deps_path=deps_path,
            )
            self._prefetched_dependency_candidates[
                self._prefetched_dependency_key(candidate.name, candidate.requester_dir)
            ] = candidate
            if code_path is not None:
                code_paths_to_prefetch.append(code_path)

        cached_prefetch_results = self._prefetch_ast_candidates(code_paths_to_prefetch)
        self._prefetched_load_results_by_path.update(cached_prefetch_results)

    def _load_or_parse_for_owner(self, code_path: Path, *, owner_name: str) -> BasePicture | None:
        return self._load_or_parse(code_path, owner_name=owner_name)

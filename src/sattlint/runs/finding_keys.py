"""Stable identities for findings acknowledged inside one stored run.

Acknowledgement is recorded per run, so the key only has to stay stable for
that run's findings. It is still a digest rather than the finding text: the
sidecar then holds no source paths, module names, or finding messages.
"""

from __future__ import annotations

import hashlib
import json

from ..application.findings import AnalysisFinding, finding_data_key


def finding_acknowledgement_key(
    *,
    target_name: str,
    analyzer_key: str,
    finding: AnalysisFinding,
    declaration_role: str | None = None,
) -> str:
    """A stable digest for the finding group shown in the Results pane.

    The grouping fields mirror the results report: same kind, declaration
    role, message, and site are one displayed row. The target and analyzer
    keep identical findings from different targets or analyzers apart.
    """
    site = finding.data.get("site")
    payload = {
        "target": target_name,
        "analyzer": analyzer_key,
        "kind": finding.kind,
        "declaration_role": declaration_role or "",
        "message": finding.message,
        "module_path": list(finding.module_path),
        "site": "" if site is None else str(site),
        "data": finding_data_key(finding),
    }
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


__all__ = ["finding_acknowledgement_key"]

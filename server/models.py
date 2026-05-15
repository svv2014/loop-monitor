from typing import Any, Optional

from pydantic import BaseModel, model_validator


class ReportPayload(BaseModel):
    """Bounty event payload — accepts both legacy and v1.0 (loop) field names.

    Legacy (asdlc-era):  event_type, issue_number, pr_number, project, role
    v1.0 (loop core):    event,      issue_num,    pr_num,    api, core_version, timestamp

    Server normalizes to legacy field names internally. Either schema works.
    """
    # Bounty event API version (v1.0 spec) — optional; absent = legacy
    api: Optional[str] = None
    core_version: Optional[str] = None
    timestamp: Optional[str] = None

    project: str
    role: str
    model: Optional[str] = None
    event_type: Optional[str] = None
    event: Optional[str] = None        # alias for event_type (v1.0 schema)
    payload: Optional[Any] = None
    issue_number: Optional[int] = None
    issue_num: Optional[int] = None     # alias for issue_number (v1.0 schema)
    pr_number: Optional[int] = None
    pr_num: Optional[int] = None        # alias for pr_number (v1.0 schema)
    agent: Optional[str] = None
    detail: Optional[str] = None
    duration_seconds: Optional[int] = None
    rework_count: Optional[int] = None
    loop_id: Optional[str] = None

    class Config:
        extra = "ignore"

    @model_validator(mode="after")
    def _backfill_legacy_aliases(self):
        # v1.0 schema uses 'event' / 'issue_num' / 'pr_num'; legacy uses
        # 'event_type' / 'issue_number' / 'pr_number'. Internal code reads
        # legacy names — backfill from v1.0 when only v1.0 names provided.
        if not self.event_type and self.event:
            self.event_type = self.event
        if self.issue_number is None and self.issue_num is not None:
            self.issue_number = self.issue_num
        if self.pr_number is None and self.pr_num is not None:
            self.pr_number = self.pr_num
        if not self.event_type:
            self.event_type = "unknown"
        return self

    @model_validator(mode="after")
    def _validate_typed_payload(self):
        if self.event_type == "label_transition":
            p = self.payload if isinstance(self.payload, dict) else {}
            if not isinstance(self.payload, dict):
                raise ValueError("label_transition payload must be a JSON object")
            required = ("target_kind", "number", "before_labels", "after_labels", "op", "source")
            missing = [f for f in required if f not in p]
            if missing:
                raise ValueError(f"label_transition payload missing required fields: {missing}")
            if p.get("target_kind") not in ("issue", "pr"):
                raise ValueError("label_transition payload.target_kind must be 'issue' or 'pr'")
            if p.get("op") not in ("add", "remove", "swap"):
                raise ValueError("label_transition payload.op must be 'add', 'remove', or 'swap'")
        elif self.event_type == "reconcile_check":
            p = self.payload if isinstance(self.payload, dict) else {}
            if not isinstance(self.payload, dict):
                raise ValueError("reconcile_check payload must be a JSON object")
            required = ("target_kind", "target_num", "check_name", "decision")
            missing = [f for f in required if f not in p]
            if missing:
                raise ValueError(f"reconcile_check payload missing required fields: {missing}")
            if p.get("target_kind") not in ("issue", "pr"):
                raise ValueError("reconcile_check payload.target_kind must be 'issue' or 'pr'")
            if p.get("decision") not in ("skip", "mutate", "log", "notify"):
                raise ValueError("reconcile_check payload.decision must be 'skip', 'mutate', 'log', or 'notify'")
        return self


class VerdictPayload(BaseModel):
    project: str
    role: str
    model: Optional[str] = None
    points: int
    reason: Optional[str] = None

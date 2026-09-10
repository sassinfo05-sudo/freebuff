"""FailureFingerprintService + LoopDetector — the anti-loop engine.

`fingerprint()` is pure and dependency-free (unit-tested without DB/network). The rest of this
module persists FailureRecord counts and exposes the deterministic signals the Supervisor uses to
decide when to change strategy, switch specialist/model, or give up and mark BLOCKED.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import List, Optional

from ...db import get_db, utc_now_iso
from ..models import FailureRecord

ORCHESTRATION_BUDGETS = {"FAST": 4, "BALANCED": 8, "DEEP": 15}
MAX_SAME_STRATEGY_ATTEMPTS = 2

# --- Normalization ------------------------------------------------------------------------

_TIMESTAMP_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b"
)
_UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
_HEX_ID_RE = re.compile(r"\b[0-9a-f]{16,64}\b", re.IGNORECASE)
_TMP_PATH_RE = re.compile(r"/(?:tmp|var/folders)/\S+")
_ABS_PATH_RE = re.compile(r"(/[A-Za-z0-9_\-.]+){3,}")
_PORT_RE = re.compile(r":\d{4,5}\b")
_LINE_NO_RE = re.compile(r":\d+:\d+\b")
_MEMADDR_RE = re.compile(r"0x[0-9a-fA-F]{6,}")
_NUM_RE = re.compile(r"\b\d+\b")


def normalize_error(raw: str) -> str:
    """Strip timestamps/uuids/temp paths/random ids/line noise so the SAME underlying failure
    fingerprints identically even when superficial details differ between runs."""
    s = raw or ""
    s = _TIMESTAMP_RE.sub("<ts>", s)
    s = _UUID_RE.sub("<uuid>", s)
    s = _TMP_PATH_RE.sub("<tmp>", s)
    s = _MEMADDR_RE.sub("<addr>", s)
    s = _HEX_ID_RE.sub("<hex>", s)
    s = _ABS_PATH_RE.sub("<path>", s)
    s = _PORT_RE.sub(":<port>", s)
    s = _LINE_NO_RE.sub(":<line>", s)
    s = _NUM_RE.sub("<n>", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:4000]


def classify_failure(raw: str) -> str:
    low = (raw or "").lower()
    if "timeout" in low or "timed out" in low:
        return "timeout"
    if "assertionerror" in low or "expect(" in low or "assert " in low:
        return "assertion"
    if "syntaxerror" in low or "unexpected token" in low:
        return "syntax"
    if "modulenotfounderror" in low or "cannot find module" in low or "importerror" in low:
        return "missing_dependency"
    if "typeerror" in low:
        return "type_error"
    if "connection" in low and ("refused" in low or "reset" in low):
        return "connection"
    if "econnrefused" in low or "network" in low:
        return "network"
    if "permission denied" in low or "eacces" in low:
        return "permission"
    return "other"


def fingerprint(*, command: Optional[str], failure_class: str, normalized_error: str,
                 subsystem: Optional[str] = None) -> str:
    basis = "|".join([command or "", failure_class, normalized_error[:1000], subsystem or ""])
    return hashlib.sha256(basis.encode()).hexdigest()[:20]


def build_fingerprint(raw_output: str, command: Optional[str] = None,
                       subsystem: Optional[str] = None) -> dict:
    normalized = normalize_error(raw_output)
    failure_class = classify_failure(raw_output)
    fp = fingerprint(command=command, failure_class=failure_class, normalized_error=normalized,
                      subsystem=subsystem)
    return {"fingerprint": fp, "failure_class": failure_class, "normalized_error": normalized,
             "command": command, "subsystem": subsystem}


# --- Persistence / signals -----------------------------------------------------------------

@dataclass
class LoopSignal:
    should_change_strategy: bool
    should_block: bool
    reason: str
    occurrences: int


async def record_failure(task_id: str, raw_output: str, command: Optional[str] = None,
                          subsystem: Optional[str] = None, plan_item_id: Optional[str] = None) -> LoopSignal:
    info = build_fingerprint(raw_output, command=command, subsystem=subsystem)
    db = get_db()
    now = utc_now_iso()
    existing = await db.ds_failure_records.find_one({"task_id": task_id, "fingerprint": info["fingerprint"]})
    if existing:
        occurrences = existing.get("occurrences", 1) + 1
        await db.ds_failure_records.update_one(
            {"_id": existing["_id"]},
            {"$set": {"occurrences": occurrences, "last_seen_at": now, "updated_at": now}},
        )
    else:
        occurrences = 1
        rec = FailureRecord(task_id=task_id, plan_item_id=plan_item_id, fingerprint=info["fingerprint"],
                             command=command, failure_class=info["failure_class"],
                             normalized_error=info["normalized_error"], subsystem=subsystem,
                             occurrences=1, first_seen_at=now, last_seen_at=now)
        await db.ds_failure_records.insert_one(rec.to_mongo())

    if occurrences >= MAX_SAME_STRATEGY_ATTEMPTS + 1:
        return LoopSignal(True, True, "Same failure fingerprint repeated 3+ times — mark BLOCKED", occurrences)
    if occurrences > MAX_SAME_STRATEGY_ATTEMPTS:
        return LoopSignal(True, False, "Same failure repeated — switch strategy/specialist/model", occurrences)
    return LoopSignal(False, False, "First occurrence of this failure", occurrences)


async def failure_history(task_id: str, limit: int = 20) -> List[dict]:
    docs = get_db().ds_failure_records.find({"task_id": task_id}).sort("last_seen_at", -1).limit(limit)
    out = []
    async for d in docs:
        out.append({k: d.get(k) for k in
                     ("fingerprint", "command", "failure_class", "normalized_error",
                       "subsystem", "occurrences", "first_seen_at", "last_seen_at")})
    return out


def budget_for_preset(preset: str) -> int:
    if preset in ORCHESTRATION_BUDGETS:
        return ORCHESTRATION_BUDGETS[preset]
    return ORCHESTRATION_BUDGETS["BALANCED"]


def budget_exhausted(iterations_used: int, iteration_budget: int) -> bool:
    return iterations_used >= iteration_budget


# --- LoopDetector: patterns beyond raw failure repetition -----------------------------------

class LoopDetector:
    """Tracks per-task signals that a single FailureRecord repeat count can't see: the same patch
    being applied/reverted/reapplied, the same command run back-to-back with no diff progress, the
    same file re-requested repeatedly, and circular agent handoffs (A->B->A->B)."""

    def __init__(self):
        self._diff_hashes: List[str] = []
        self._commands: List[str] = []
        self._file_requests: List[str] = []
        self._handoff_chain: List[str] = []

    def record_diff(self, diff_text: str) -> bool:
        """Returns True if this diff is identical to the previous one (no progress this turn)."""
        h = hashlib.sha256((diff_text or "").encode()).hexdigest()[:16]
        no_progress = bool(self._diff_hashes) and self._diff_hashes[-1] == h
        self._diff_hashes.append(h)
        return no_progress

    def record_command(self, command: str) -> int:
        """Returns how many times this exact command has now run consecutively."""
        self._commands.append(command)
        streak = 0
        for c in reversed(self._commands):
            if c == command:
                streak += 1
            else:
                break
        return streak

    def record_file_request(self, path: str) -> int:
        self._file_requests.append(path)
        return self._file_requests.count(path)

    def record_handoff(self, role: str) -> bool:
        """Returns True if the last 4 handoffs form an A->B->A->B circular pattern."""
        self._handoff_chain.append(role)
        chain = self._handoff_chain[-4:]
        return len(chain) == 4 and chain[0] == chain[2] and chain[1] == chain[3] and chain[0] != chain[1]

    def snapshot(self) -> dict:
        return {
            "distinct_diffs": len(set(self._diff_hashes)),
            "total_diffs": len(self._diff_hashes),
            "command_repeats": {c: self._commands.count(c) for c in set(self._commands)},
            "handoff_chain": list(self._handoff_chain[-10:]),
        }

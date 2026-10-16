"""Data quality log: a record of every check and fix the pipeline applies.

It is loaded into the warehouse alongside the data, so analysts can see what was changed and why.
"""

from dataclasses import asdict, dataclass, field


class DataQualityError(Exception):
    """Raised when the raw data breaks an assumption the pipeline can't safely work around."""


@dataclass(frozen=True)
class Check:
    step: str
    status: str  # "passed", "fixed" or "warning"
    rows_affected: int
    detail: str


@dataclass
class QualityLog:
    checks: list[Check] = field(default_factory=list)

    def add(self, step: str, status: str, rows_affected: int, detail: str) -> None:
        self.checks.append(Check(step, status, int(rows_affected), detail))

    def to_records(self) -> list[dict]:
        return [asdict(c) for c in self.checks]

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Judge(Base):
    """A human judge. Judges are first-class so judgment provenance is kept
    separate from the judgment-set version they contributed to."""

    __tablename__ = "judges"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Query(Base):
    __tablename__ = "queries"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    text: Mapped[str] = mapped_column(Text)


class JudgmentSet(Base):
    """An immutable, versioned snapshot of relevance judgments."""

    __tablename__ = "judgment_sets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    judgments: Mapped[list["Judgment"]] = relationship(
        back_populates="judgment_set", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("name", "version", name="uq_jset_name_version"),)


class Judgment(Base):
    __tablename__ = "judgments"

    id: Mapped[int] = mapped_column(primary_key=True)
    judgment_set_id: Mapped[int] = mapped_column(
        ForeignKey("judgment_sets.id", ondelete="CASCADE")
    )
    query_id: Mapped[str] = mapped_column(ForeignKey("queries.id"))
    doc_id: Mapped[str] = mapped_column(String(60))
    grade: Mapped[int] = mapped_column(Integer)  # 0..3
    judge_id: Mapped[int] = mapped_column(ForeignKey("judges.id"))

    judgment_set: Mapped[JudgmentSet] = relationship(back_populates="judgments")
    judge: Mapped[Judge] = relationship()

    __table_args__ = (
        UniqueConstraint("judgment_set_id", "query_id", "doc_id", name="uq_judgment"),
    )


class Experiment(Base):
    """An experiment compares two ranking configurations against one frozen
    judgment set. Runs are bound to a concrete index and query config so a
    completed run is reproducible."""

    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    judgment_set_id: Mapped[int] = mapped_column(ForeignKey("judgment_sets.id"))
    index_name: Mapped[str] = mapped_column(String(120))
    baseline_config: Mapped[dict] = mapped_column(JSON)
    treatment_config: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    judgment_set: Mapped[JudgmentSet] = relationship()
    runs: Mapped[list["Run"]] = relationship(
        back_populates="experiment", cascade="all, delete-orphan"
    )


class Run(Base):
    """One executed retrieval+scoring pass. At most one run per role per
    experiment; re-running replaces the previous artifact."""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(20))  # 'baseline' | 'treatment'
    index_name: Mapped[str] = mapped_column(String(120))
    query_config: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    experiment: Mapped[Experiment] = relationship(back_populates="runs")
    results: Mapped[list["RunResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    query_metrics: Mapped[list["QueryMetricRow"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("experiment_id", "role", name="uq_run_role"),)


class RunResult(Base):
    """One retrieved row. ``kept=False`` rows (duplicates, beyond-cutoff)
    are stored for transparency but never scored."""

    __tablename__ = "run_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))
    query_id: Mapped[str] = mapped_column(ForeignKey("queries.id"))
    rank: Mapped[int] = mapped_column(Integer)  # rank in the raw retrieval
    doc_id: Mapped[str] = mapped_column(String(60))
    score: Mapped[float] = mapped_column(Float)
    kept: Mapped[bool] = mapped_column(default=True)
    drop_reason: Mapped[str | None] = mapped_column(String(20), nullable=True)

    run: Mapped[Run] = relationship(back_populates="results")

    __table_args__ = (UniqueConstraint("run_id", "query_id", "rank", name="uq_run_rank"),)


class QueryMetricRow(Base):
    __tablename__ = "query_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))
    query_id: Mapped[str] = mapped_column(ForeignKey("queries.id"))
    ndcg: Mapped[float] = mapped_column(Float)
    mrr: Mapped[float] = mapped_column(Float)
    recall: Mapped[float | None] = mapped_column(Float, nullable=True)
    num_rel: Mapped[int] = mapped_column(Integer)

    run: Mapped[Run] = relationship(back_populates="query_metrics")

    __table_args__ = (UniqueConstraint("run_id", "query_id", name="uq_qmetric"),)

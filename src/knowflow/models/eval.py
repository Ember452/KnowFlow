"""评测模型. EvalDataset / EvalRun / EvalResult."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from knowflow.models.base import Base, IDMixin, JSONBType, TimestampMixin


class EvalDataset(Base, IDMixin, TimestampMixin):
    """评测数据集. 如 retrieval_eval / knowledge_qa_eval."""

    __tablename__ = "eval_datasets"

    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")


class EvalRun(Base, IDMixin, TimestampMixin):
    """评测运行. 一次评测集执行的记录."""

    __tablename__ = "eval_runs"

    dataset_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("eval_datasets.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    config: Mapped[dict | None] = mapped_column(JSONBType, nullable=True, comment="评测参数")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[dict | None] = mapped_column(JSONBType, nullable=True, comment="汇总指标")

    __table_args__ = (Index("idx_eval_runs_dataset", "dataset_id"),)


class EvalResult(Base, IDMixin, TimestampMixin):
    """单条评测结果. 对应评测集中的一条 query."""

    __tablename__ = "eval_results"

    run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    expected: Mapped[dict | None] = mapped_column(
        JSONBType, nullable=True, comment="标注答案/相关 id"
    )
    actual: Mapped[dict | None] = mapped_column(JSONBType, nullable=True, comment="实际输出")
    metrics: Mapped[dict | None] = mapped_column(
        JSONBType, nullable=True, comment="Recall@K/MRR/..."
    )

    __table_args__ = (Index("idx_eval_results_run", "run_id"),)

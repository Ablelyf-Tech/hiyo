from sqlalchemy import (
    create_engine,
    String,
    Text,
    Integer,
    BigInteger,
    Boolean,
    Float,
    Index,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool
import time


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created: Mapped[float] = mapped_column(Float, default=time.time)


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    public_key: Mapped[str] = mapped_column(String(100))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen: Mapped[float] = mapped_column(Float, default=time.time)
    capabilities: Mapped[str] = mapped_column(Text, default="[]")


class Nonce(Base):
    __tablename__ = "device_nonces"
    device_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    value: Mapped[str] = mapped_column(String(80), primary_key=True)
    expires: Mapped[float] = mapped_column(Float, index=True)


class Usage(Base):
    __tablename__ = "monthly_usage"
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), primary_key=True)
    month: Mapped[str] = mapped_column(String(7), primary_key=True)
    jobs: Mapped[int] = mapped_column(Integer, default=0)
    requests: Mapped[int] = mapped_column(Integer, default=0)
    bytes_used: Mapped[int] = mapped_column(BigInteger, default=0)
    reserved_microusd: Mapped[int] = mapped_column(BigInteger, default=250000)


class CloudWorkflow(Base):
    __tablename__ = "cloud_workflows"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    definition: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    next_run: Mapped[float] = mapped_column(Float, default=0)
    created: Mapped[float] = mapped_column(Float, default=time.time)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    workflow_id: Mapped[str] = mapped_column(ForeignKey("cloud_workflows.id"))
    idempotency_key: Mapped[str] = mapped_column(String(100))
    payload: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="queued")
    device_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String(80), nullable=True)
    lease_until: Mapped[float] = mapped_column(Float, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_proof: Mapped[str] = mapped_column(Text, default="{}")
    approved: Mapped[str] = mapped_column(Text, default="[]")
    created: Mapped[float] = mapped_column(Float, default=time.time)
    updated: Mapped[float] = mapped_column(Float, default=time.time)
    __table_args__ = (
        UniqueConstraint("account_id", "idempotency_key", name="job_idempotency"),
        Index("jobs_account_status_created", "account_id", "status", "created"),
        Index("jobs_retention", "created"),
    )


def database(url):
    options = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        options.update(connect_args={"check_same_thread": False})
        if ":memory:" in url:
            options["poolclass"] = StaticPool
    else:
        options.update(pool_size=5, max_overflow=0, pool_recycle=1800)
    engine = create_engine(url, **options)
    return engine, sessionmaker(engine, expire_on_commit=False)


class EnrollmentTicket(Base):
    __tablename__ = "enrollment_tickets"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    expires: Mapped[float] = mapped_column(Float)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)


class ApprovalAudit(Base):
    __tablename__ = "approval_audit"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    step_id: Mapped[str] = mapped_column(String(60))
    approved: Mapped[bool] = mapped_column(Boolean)
    note: Mapped[str] = mapped_column(Text)
    created: Mapped[float] = mapped_column(Float, default=time.time)

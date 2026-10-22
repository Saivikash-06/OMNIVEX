import datetime
import uuid
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Index,
)
from sqlalchemy.orm import relationship
from backend.app.database.connection import Base


def utc_now() -> datetime.datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.datetime.now(datetime.timezone.utc)


class DatasetModel(Base):
    __tablename__ = "datasets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    filename = Column(String(100), nullable=False)
    file_path = Column(String(500), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False)
    row_count = Column(Integer, nullable=False)
    column_count = Column(Integer, nullable=False)
    schema_json = Column(JSON, nullable=False)
    role = Column(String(20), nullable=False, default="reference")  # reference or incoming
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    __table_args__ = (
        Index("ix_datasets_role_created_at", "role", "created_at"),
    )


class TrainedModel(Base):
    __tablename__ = "models"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    algorithm = Column(String(50), nullable=False)
    hyperparameters = Column(JSON, nullable=False)
    feature_names = Column(JSON, nullable=False)
    feature_dtypes = Column(JSON, nullable=False)
    target_column = Column(String(100), nullable=False)
    class_labels = Column(JSON, nullable=False)
    training_dataset_id = Column(String(36), ForeignKey("datasets.id"), nullable=False, index=True)
    training_dataset_hash = Column(String(64), nullable=False)
    random_seed = Column(Integer, nullable=False)
    library_versions = Column(JSON, nullable=False)
    baseline_metrics = Column(JSON, nullable=False)
    artifact_filename = Column(String(100), nullable=False)
    artifact_path = Column(String(500), nullable=False)
    artifact_sha256 = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    training_dataset = relationship("DatasetModel", foreign_keys=[training_dataset_id])


class ExperimentModel(Base):
    __tablename__ = "experiments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    scenario = Column(String(50), nullable=False, default="baseline")
    is_simulation = Column(Boolean, nullable=False, default=False)
    simulation_parameters = Column(JSON, nullable=True)
    reference_dataset_id = Column(String(36), ForeignKey("datasets.id"), nullable=False, index=True)
    incoming_dataset_id = Column(String(36), ForeignKey("datasets.id"), nullable=False, index=True)
    model_id = Column(String(36), ForeignKey("models.id"), nullable=True, index=True)
    settings_snapshot = Column(JSON, nullable=False)
    random_seed = Column(Integer, nullable=False)
    library_versions = Column(JSON, nullable=False)
    status = Column(String(30), nullable=False, default="completed")
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    reference_dataset = relationship("DatasetModel", foreign_keys=[reference_dataset_id])
    incoming_dataset = relationship("DatasetModel", foreign_keys=[incoming_dataset_id])
    model = relationship("TrainedModel", foreign_keys=[model_id])


class MonitoringRunModel(Base):
    __tablename__ = "monitoring_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    experiment_id = Column(String(36), ForeignKey("experiments.id"), nullable=True, index=True)
    reference_dataset_id = Column(String(36), ForeignKey("datasets.id"), nullable=False, index=True)
    incoming_dataset_id = Column(String(36), ForeignKey("datasets.id"), nullable=False, index=True)
    model_id = Column(String(36), ForeignKey("models.id"), nullable=True, index=True)
    reliability_state = Column(String(50), nullable=False, index=True)
    reasons = Column(JSON, nullable=False)
    drift_detected = Column(Boolean, nullable=False)
    performance_status = Column(String(50), nullable=False)
    execution_time_ms = Column(Float, nullable=False)
    settings_snapshot = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    experiment = relationship("ExperimentModel", foreign_keys=[experiment_id])
    reference_dataset = relationship("DatasetModel", foreign_keys=[reference_dataset_id])
    incoming_dataset = relationship("DatasetModel", foreign_keys=[incoming_dataset_id])
    model = relationship("TrainedModel", foreign_keys=[model_id])
    drift_results = relationship("DriftResultModel", back_populates="run", cascade="all, delete-orphan")
    performance_metrics = relationship("PerformanceMetricModel", back_populates="run", uselist=False, cascade="all, delete-orphan")
    alerts = relationship("AlertModel", back_populates="run")


class DriftResultModel(Base):
    __tablename__ = "drift_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("monitoring_runs.id"), nullable=False, index=True)
    feature = Column(String(100), nullable=False)
    feature_type = Column(String(20), nullable=False)
    test_name = Column(String(50), nullable=False)
    statistic = Column(Float, nullable=False)
    p_value = Column(Float, nullable=True)
    adjusted_p_value = Column(Float, nullable=True)
    threshold = Column(Float, nullable=False)
    status = Column(String(50), nullable=False)
    reference_n = Column(Integer, nullable=False)
    incoming_n = Column(Integer, nullable=False)
    note = Column(Text, nullable=True)

    run = relationship("MonitoringRunModel", back_populates="drift_results")


class PerformanceMetricModel(Base):
    __tablename__ = "performance_metrics"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("monitoring_runs.id"), nullable=False, index=True)
    accuracy = Column(Float, nullable=True)
    precision = Column(Float, nullable=True)
    recall = Column(Float, nullable=True)
    f1 = Column(Float, nullable=True)
    f1_average = Column(String(20), nullable=False, default="macro")
    confusion_matrix = Column(JSON, nullable=True)
    class_labels = Column(JSON, nullable=True)
    baseline_metrics = Column(JSON, nullable=True)
    accuracy_ci = Column(JSON, nullable=True)
    f1_ci = Column(JSON, nullable=True)
    sample_size = Column(Integer, nullable=False)
    degradation_flagged = Column(Boolean, nullable=False, default=False)

    run = relationship("MonitoringRunModel", back_populates="performance_metrics")


class AlertModel(Base):
    __tablename__ = "alerts"

    alert_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("monitoring_runs.id"), nullable=True, index=True)
    timestamp = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    alert_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)  # info, warning, critical
    affected_feature_or_metric = Column(String(100), nullable=False)
    explanation = Column(Text, nullable=False)
    evidence = Column(JSON, nullable=False)
    suggested_steps = Column(JSON, nullable=False)
    acknowledged = Column(Boolean, nullable=False, default=False, index=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(String(100), nullable=True)

    run = relationship("MonitoringRunModel", back_populates="alerts")

    __table_args__ = (
        Index("ix_alerts_acknowledged_severity", "acknowledged", "severity"),
    )

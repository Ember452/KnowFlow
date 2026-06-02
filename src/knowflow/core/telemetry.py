"""OpenTelemetry 初始化. P10 前仅初始化 TracerProvider, 不接入 collector."""

from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult

from knowflow.core.config import get_settings
from knowflow.core.logging import get_logger

logger = get_logger(__name__)


class _NullExporter(SpanExporter):
    """空 Span 导出器. P10 接入 OTLP collector 前占位, span 仅在内存中."""

    def export(self, spans: Any) -> SpanExportResult:
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def setup_telemetry() -> None:
    """初始化 OpenTelemetry trace provider.

    P10 阶段会替换 _NullExporter 为 OTLPExporter, 挂到 collector.
    """
    settings = get_settings()
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": settings.app_name,
                "service.version": "0.1.0",
                "deployment.environment": settings.env,
            }
        )
    )
    provider.add_span_processor(BatchSpanProcessor(_NullExporter()))
    trace.set_tracer_provider(provider)
    logger.info("telemetry.initialized", env=settings.env)


def get_tracer(name: str | None = None) -> trace.Tracer:
    """获取 tracer, 用于创建 span."""
    return trace.get_tracer(name or "knowflow")

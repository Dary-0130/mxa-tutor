"""Connectivity-stub service for MATLAB bridge diagnostics."""

from __future__ import annotations

from time import perf_counter

from loguru import logger

from core.domain.bridge_diagnostic import BridgeDiagnostic, BridgeDiagnosticReceipt

BRIDGE_RECEIPT_MESSAGE = "连接成功。本版本仅验证诊断信息传输,不提供报错解释。"


class DiagnosticService:
    """Consume one diagnostic payload and return the fixed connectivity receipt."""

    def consume(self, diagnostic: BridgeDiagnostic) -> BridgeDiagnosticReceipt:
        started = perf_counter()
        receipt = BridgeDiagnosticReceipt(
            request_id=diagnostic.request_id,
            status="received",
            mode="connectivity_stub",
            message=BRIDGE_RECEIPT_MESSAGE,
        )
        latency_ms = int((perf_counter() - started) * 1000)
        logger.info(
            (
                "MATLAB bridge diagnostic: request_id={} matlab_release={} "
                "client_version={} payload_chars={} status={} latency_ms={}"
            ),
            str(diagnostic.request_id),
            diagnostic.matlab_release,
            diagnostic.client_version,
            len(diagnostic.error_text),
            receipt.status,
            latency_ms,
        )
        return receipt

"""Construct the configured malware scanner without exposing its credentials."""

from app.core.config import Settings
from app.services.security_scanning.base_malware_scanner import (
    BaseMalwareScanner,
    MalwareScannerFailPolicy,
)
from app.services.security_scanning.clamav_malware_scanner import (
    ClamAvMalwareScanner,
)
from app.services.security_scanning.no_op_malware_scanner import (
    NoOpMalwareScanner,
)


def create_malware_scanner(settings: Settings) -> BaseMalwareScanner:
    if not settings.malware_scanning_enabled:
        return NoOpMalwareScanner()
    if settings.malware_scanner != "clamav":
        raise ValueError("Configured malware scanner is unsupported.")
    return ClamAvMalwareScanner(
        host=settings.clamav_host,
        port=settings.clamav_port,
        timeout_seconds=settings.malware_scan_timeout_seconds,
        fail_policy=MalwareScannerFailPolicy(settings.malware_scanner_failure_policy),
    )

"""Malware-scanning providers used by the upload quarantine flow."""

from app.services.security_scanning.base_malware_scanner import (
    BaseMalwareScanner,
    MalwareScannerFailPolicy,
    MalwareScanResult,
    MalwareScanStatus,
)
from app.services.security_scanning.clamav_malware_scanner import (
    ClamAvMalwareScanner,
)
from app.services.security_scanning.factory import create_malware_scanner
from app.services.security_scanning.no_op_malware_scanner import (
    NoOpMalwareScanner,
)

__all__ = [
    "BaseMalwareScanner",
    "ClamAvMalwareScanner",
    "MalwareScanResult",
    "MalwareScanStatus",
    "MalwareScannerFailPolicy",
    "NoOpMalwareScanner",
    "create_malware_scanner",
]

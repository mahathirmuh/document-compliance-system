"""Safe Graph path construction helpers."""

from urllib.parse import quote


def encode_identifier(value: str) -> str:
    normalized = value.strip()
    if not normalized or "/" in normalized or "\\" in normalized:
        raise ValueError("Graph identifier is invalid.")
    return quote(normalized, safe="")


def normalize_remote_path(value: str, *, allow_root: bool = True) -> str:
    raw = value.strip().replace("\\", "/").strip("/")
    if not raw and allow_root:
        return ""
    parts = raw.split("/")
    if not raw or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("SharePoint path must remain beneath the configured root.")
    if any("\x00" in part for part in parts):
        raise ValueError("SharePoint path contains an invalid character.")
    return "/".join(parts)


def encode_remote_path(value: str) -> str:
    normalized = normalize_remote_path(value)
    return "/".join(quote(part, safe="") for part in normalized.split("/"))


def join_remote_path(*parts: str) -> str:
    normalized = [
        normalize_remote_path(part)
        for part in parts
        if part is not None and part.strip().strip("/\\")
    ]
    return "/".join(part for part in normalized if part)

"""ERP REST API connector for Acme Finance Portal."""
from __future__ import annotations

from typing import Any, Dict, Optional
import httpx

from connectors.base import BaseConnector, ToolResult


class ERPConnector(BaseConnector):
    """Provides read-only lookup and state verification against the portal API."""

    @staticmethod
    def lookup_vendor(portal_url: str, name: str) -> ToolResult:
        """Calls GET /api/lookup_vendor?name=... to check if vendor is already registered."""
        url = f"{portal_url.rstrip('/')}/api/lookup_vendor"
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url, params={"name": name})
                if resp.status_code == 200:
                    data = resp.json()
                    return ToolResult(
                        success=True,
                        data={
                            "found": data.get("found", False),
                            "vendor": data.get("vendor"),
                            "vendor_id": data.get("vendor", {}).get("vendor_id")
                            if data.get("vendor")
                            else None,
                        },
                    )
                return ToolResult(
                    success=False,
                    error=f"Portal returned HTTP {resp.status_code}: {resp.text}",
                    error_code=f"HTTP_{resp.status_code}",
                )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"Failed to connect to ERP lookup API at {url}: {str(exc)}",
                error_code="CONNECTION_ERROR",
            )

    @staticmethod
    def fetch_system_state(portal_url: str) -> ToolResult:
        """Calls GET /api/verify/state for independent post-condition verification."""
        url = f"{portal_url.rstrip('/')}/api/verify/state"
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    return ToolResult(
                        success=True,
                        data=resp.json(),
                    )
                return ToolResult(
                    success=False,
                    error=f"Portal state API returned HTTP {resp.status_code}",
                    error_code=f"HTTP_{resp.status_code}",
                )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"Failed to fetch system state from {url}: {str(exc)}",
                error_code="CONNECTION_ERROR",
            )

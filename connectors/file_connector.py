"""File system connector for invoice ingestion and archival."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from connectors.base import BaseConnector, ToolResult


class FileConnector(BaseConnector):
    """Handles workspace filesystem operations for invoices."""

    @staticmethod
    def read_next_invoice(
        inbox_dir: str, target_filename: Optional[str] = None
    ) -> ToolResult:
        """Reads target or earliest .json invoice in inbox_dir."""
        inbox_path = Path(inbox_dir)
        if not inbox_path.exists():
            return ToolResult(
                success=False,
                error=f"Inbox directory '{inbox_dir}' does not exist.",
                error_code="INBOX_NOT_FOUND",
            )

        target_file: Optional[Path] = None
        if target_filename:
            candidate = inbox_path / target_filename
            if candidate.exists() and candidate.is_file():
                target_file = candidate
            else:
                return ToolResult(
                    success=False,
                    error=f"Target invoice file '{target_filename}' not found in '{inbox_dir}'.",
                    error_code="FILE_NOT_FOUND",
                )
        else:
            json_files = sorted(list(inbox_path.glob("*.json")))
            if not json_files:
                return ToolResult(
                    success=False,
                    error=f"No pending invoice JSON files found in '{inbox_dir}'.",
                    error_code="NO_INVOICES",
                )
            target_file = json_files[0]

        try:
            with open(target_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["file_path"] = str(target_file.resolve())
            return ToolResult(
                success=True,
                data={"invoice": data},
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"Failed to read/parse invoice '{target_file.name}': {str(exc)}",
                error_code="JSON_PARSE_ERROR",
            )

    @staticmethod
    def archive_invoice(file_path: str, archive_dir: str) -> ToolResult:
        """Moves processed invoice file from inbox to processed archive."""
        src = Path(file_path)
        dest_dir = Path(archive_dir)
        if not src.exists():
            return ToolResult(
                success=False,
                error=f"Source invoice file '{file_path}' does not exist.",
                error_code="FILE_NOT_FOUND",
            )

        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / src.name
            shutil.move(str(src), str(dest))
            return ToolResult(
                success=True,
                data={
                    "original_path": str(src),
                    "archived_path": str(dest.resolve()),
                },
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"Failed to archive file '{file_path}' to '{archive_dir}': {str(exc)}",
                error_code="ARCHIVE_ERROR",
            )

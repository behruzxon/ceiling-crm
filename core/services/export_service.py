"""
ExportService — exports CRM data to Google Sheets / Excel / PDF.
"""

from __future__ import annotations

from datetime import date

from shared.logging import get_logger

log = get_logger(__name__)


class ExportService:
    """
    Generates and delivers CRM data exports.
    Supports: Google Sheets sync, Excel download, PDF report.
    """

    async def export_to_sheets(self, leads: list, sheet_id: str) -> str:
        """Sync leads to Google Sheets. Returns sheet URL. TODO: implement."""
        raise NotImplementedError

    async def export_to_excel(self, leads: list, date_range: tuple[date, date]) -> bytes:
        """Generate Excel workbook bytes. TODO: implement with openpyxl."""
        raise NotImplementedError

    async def export_to_pdf(self, report_data: dict) -> bytes:
        """Generate PDF report bytes. TODO: implement with reportlab."""
        raise NotImplementedError

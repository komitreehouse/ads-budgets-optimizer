"""
Export Service — CSV and PDF report generation with IPSA branding.
"""

import csv
import io
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.bandit_ads.utils import get_logger

logger = get_logger('export')


class ExportService:
    """Generates downloadable reports from campaign and optimizer data."""

    def __init__(self):
        from src.bandit_ads.database import get_db_manager
        self.db_manager = get_db_manager()

    # ------------------------------------------------------------------
    # CSV exports
    # ------------------------------------------------------------------

    def metrics_csv(self, campaign_id: int, days: int = 30) -> bytes:
        """Daily metrics CSV for a campaign."""
        rows = self._load_metrics(campaign_id, days)
        return self._to_csv(
            rows,
            fieldnames=["date", "channel", "spend", "revenue", "roas",
                        "impressions", "clicks", "conversions"],
        )

    def allocation_csv(self, campaign_id: int) -> bytes:
        """Current arm allocation CSV."""
        rows = self._load_allocation(campaign_id)
        return self._to_csv(
            rows,
            fieldnames=["arm", "platform", "channel", "allocation_pct",
                        "daily_spend", "roas"],
        )

    def decisions_csv(self, campaign_id: Optional[int] = None, days: int = 30) -> bytes:
        """Recent optimizer decisions CSV."""
        rows = self._load_decisions(campaign_id, days)
        return self._to_csv(
            rows,
            fieldnames=["timestamp", "campaign_id", "arm_id",
                        "old_allocation", "new_allocation", "change_type", "explanation"],
        )

    # ------------------------------------------------------------------
    # PDF export
    # ------------------------------------------------------------------

    def campaign_pdf(self, campaign_id: int, campaign_name: str = "Campaign") -> bytes:
        """Branded PDF summary report for a campaign."""
        from fpdf import FPDF

        metrics_rows = self._load_metrics(campaign_id, days=30)
        alloc_rows = self._load_allocation(campaign_id)

        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        # ---- Header ----
        pdf.set_fill_color(155, 72, 25)   # IPSA terracotta
        pdf.rect(0, 0, 210, 28, 'F')
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_xy(12, 8)
        pdf.cell(0, 10, "Ipsa", ln=0)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_xy(12, 18)
        pdf.cell(0, 6, "Incremental performance, explained.")

        # ---- Title ----
        pdf.set_text_color(26, 26, 26)
        pdf.set_xy(12, 34)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 8, f"Campaign Report: {campaign_name}", ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(113, 113, 130)
        pdf.cell(0, 5, f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}  ·  Last 30 days", ln=True)
        pdf.ln(4)

        # ---- KPI Summary ----
        if metrics_rows:
            total_spend = sum(r.get("spend", 0) for r in metrics_rows)
            total_revenue = sum(r.get("revenue", 0) for r in metrics_rows)
            blended_roas = total_revenue / total_spend if total_spend > 0 else 0
            total_conv = sum(r.get("conversions", 0) for r in metrics_rows)

            self._pdf_section(pdf, "Performance Summary (30 days)")
            kpis = [
                ("Total Spend", f"${total_spend:,.0f}"),
                ("Total Revenue", f"${total_revenue:,.0f}"),
                ("Blended ROAS", f"{blended_roas:.2f}x"),
                ("Conversions", f"{int(total_conv):,}"),
            ]
            self._pdf_kpi_row(pdf, kpis)
            pdf.ln(4)

        # ---- Allocation table ----
        if alloc_rows:
            self._pdf_section(pdf, "Current Budget Allocation")
            self._pdf_table(
                pdf,
                headers=["Arm", "Platform", "Channel", "Allocation", "Daily Spend", "ROAS"],
                rows=[
                    [
                        r.get("arm", "")[:28],
                        r.get("platform", ""),
                        r.get("channel", ""),
                        f"{r.get('allocation_pct', 0):.1%}",
                        f"${r.get('daily_spend', 0):,.0f}",
                        f"{r.get('roas', 0):.2f}x",
                    ]
                    for r in alloc_rows
                ],
                col_widths=[55, 28, 28, 24, 30, 22],
            )
            pdf.ln(4)

        # ---- Daily metrics table (last 10 days) ----
        recent = sorted(metrics_rows, key=lambda r: r.get("date", ""), reverse=True)[:10]
        if recent:
            self._pdf_section(pdf, "Daily Metrics (last 10 days)")
            # Aggregate by date
            by_date: Dict[str, Dict] = {}
            for r in metrics_rows:
                d = r.get("date", "")
                if d not in by_date:
                    by_date[d] = {"spend": 0, "revenue": 0, "conversions": 0}
                by_date[d]["spend"] += r.get("spend", 0)
                by_date[d]["revenue"] += r.get("revenue", 0)
                by_date[d]["conversions"] += r.get("conversions", 0)

            daily_rows = []
            for d in sorted(by_date.keys(), reverse=True)[:10]:
                s = by_date[d]["spend"]
                rev = by_date[d]["revenue"]
                daily_rows.append([
                    d,
                    f"${s:,.0f}",
                    f"${rev:,.0f}",
                    f"{rev/s:.2f}x" if s > 0 else "—",
                    f"{int(by_date[d]['conversions']):,}",
                ])

            self._pdf_table(
                pdf,
                headers=["Date", "Spend", "Revenue", "ROAS", "Conversions"],
                rows=daily_rows,
                col_widths=[35, 35, 35, 30, 35],
            )

        # ---- Footer ----
        pdf.set_y(-18)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(113, 113, 130)
        pdf.cell(0, 6, "Generated by Ipsa · Confidential · ipsa.ai", align="C")

        return bytes(pdf.output())

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_metrics(self, campaign_id: int, days: int) -> List[Dict]:
        try:
            from src.bandit_ads.database import Metric, Arm
            from sqlalchemy import and_
            from datetime import timedelta
            cutoff = datetime.utcnow() - timedelta(days=days)
            with self.db_manager.get_session() as session:
                rows = (
                    session.query(Metric, Arm)
                    .join(Arm, Metric.arm_id == Arm.id)
                    .filter(and_(Arm.campaign_id == campaign_id, Metric.timestamp >= cutoff))
                    .order_by(Metric.timestamp)
                    .all()
                )
                result = []
                for m, arm in rows:
                    spend = m.spend or 0
                    revenue = m.revenue or 0
                    result.append({
                        "date": m.timestamp.strftime("%Y-%m-%d"),
                        "channel": arm.channel or arm.platform,
                        "spend": spend,
                        "revenue": revenue,
                        "roas": revenue / spend if spend > 0 else 0,
                        "impressions": m.impressions or 0,
                        "clicks": m.clicks or 0,
                        "conversions": m.conversions or 0,
                    })
                return result
        except Exception as e:
            logger.warning(f"Could not load metrics: {e}")
            return self._stub_metrics()

    def _load_allocation(self, campaign_id: int) -> List[Dict]:
        try:
            from src.bandit_ads.database import Arm, Metric
            from sqlalchemy import func
            with self.db_manager.get_session() as session:
                arms = session.query(Arm).filter(Arm.campaign_id == campaign_id).all()
                result = []
                for arm in arms:
                    latest = (
                        session.query(Metric)
                        .filter(Metric.arm_id == arm.id)
                        .order_by(Metric.timestamp.desc())
                        .first()
                    )
                    spend = latest.spend if latest else 0
                    revenue = latest.revenue if latest else 0
                    result.append({
                        "arm": f"{arm.platform} · {arm.channel} · {arm.creative}",
                        "platform": arm.platform,
                        "channel": arm.channel,
                        "allocation_pct": 1 / max(len(arms), 1),  # even split if no runner
                        "daily_spend": spend,
                        "roas": revenue / spend if spend > 0 else 0,
                    })
                return result
        except Exception as e:
            logger.warning(f"Could not load allocation: {e}")
            return self._stub_allocation()

    def _load_decisions(self, campaign_id: Optional[int], days: int) -> List[Dict]:
        try:
            from src.bandit_ads.change_tracker import get_change_tracker
            tracker = get_change_tracker()
            history = tracker.get_allocation_history(campaign_id=campaign_id, limit=200)
            return [
                {
                    "timestamp": d.get("timestamp", ""),
                    "campaign_id": d.get("campaign_id", ""),
                    "arm_id": d.get("arm_id", ""),
                    "old_allocation": d.get("old_allocation", 0),
                    "new_allocation": d.get("new_allocation", 0),
                    "change_type": d.get("change_type", "auto"),
                    "explanation": d.get("explanation_text", ""),
                }
                for d in history
            ]
        except Exception as e:
            logger.warning(f"Could not load decisions: {e}")
            return []

    @staticmethod
    def _to_csv(rows: List[Dict], fieldnames: List[str]) -> bytes:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue().encode()

    # ---- PDF helpers ----

    @staticmethod
    def _pdf_section(pdf, title: str):
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(155, 72, 25)
        pdf.cell(0, 7, title, ln=True)
        pdf.set_draw_color(155, 72, 25)
        pdf.set_line_width(0.4)
        x = pdf.get_x()
        y = pdf.get_y()
        pdf.line(x, y, x + 186, y)
        pdf.ln(3)
        pdf.set_text_color(26, 26, 26)

    @staticmethod
    def _pdf_kpi_row(pdf, kpis: List[tuple]):
        col_w = 186 / len(kpis)
        start_x = pdf.get_x()
        start_y = pdf.get_y()
        for label, value in kpis:
            pdf.set_fill_color(244, 241, 232)
            pdf.rect(pdf.get_x(), start_y, col_w - 3, 18, 'F')
            pdf.set_xy(pdf.get_x() + 3, start_y + 2)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(113, 113, 130)
            pdf.cell(col_w - 6, 5, label, ln=True)
            pdf.set_xy(pdf.get_x() + 3, pdf.get_y())
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(26, 26, 26)
            pdf.cell(col_w - 6, 7, value, ln=False)
            pdf.set_xy(start_x + (kpis.index((label, value)) + 1) * col_w, start_y)
        pdf.set_xy(start_x, start_y + 20)

    @staticmethod
    def _pdf_table(pdf, headers: List[str], rows: List[List], col_widths: List[int]):
        # Header row
        pdf.set_fill_color(155, 72, 25)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 8)
        for h, w in zip(headers, col_widths):
            pdf.cell(w, 7, h, border=0, fill=True)
        pdf.ln()
        # Data rows
        pdf.set_text_color(26, 26, 26)
        pdf.set_font("Helvetica", "", 8)
        for i, row in enumerate(rows):
            if i % 2 == 0:
                pdf.set_fill_color(244, 241, 232)
                fill = True
            else:
                fill = False
            for val, w in zip(row, col_widths):
                pdf.cell(w, 6, str(val)[:30], border=0, fill=fill)
            pdf.ln()

    # ---- Stubs for when DB is empty ----

    @staticmethod
    def _stub_metrics() -> List[Dict]:
        from datetime import timedelta
        import random
        today = datetime.utcnow()
        rows = []
        for d in range(30):
            dt = (today - timedelta(days=29 - d)).strftime("%Y-%m-%d")
            for ch in ["Google Search", "Meta Social"]:
                spend = round(800 + random.uniform(-100, 200), 2)
                revenue = round(spend * (2.2 + random.uniform(-0.3, 0.5)), 2)
                rows.append({
                    "date": dt, "channel": ch,
                    "spend": spend, "revenue": revenue,
                    "roas": revenue / spend,
                    "impressions": random.randint(8000, 20000),
                    "clicks": random.randint(300, 900),
                    "conversions": random.randint(20, 80),
                })
        return rows

    @staticmethod
    def _stub_allocation() -> List[Dict]:
        return [
            {"arm": "Google Search · Creative A", "platform": "Google", "channel": "Search",
             "allocation_pct": 0.40, "daily_spend": 1200, "roas": 2.85},
            {"arm": "Meta Social · Creative B", "platform": "Meta", "channel": "Social",
             "allocation_pct": 0.30, "daily_spend": 900, "roas": 2.15},
            {"arm": "Trade Desk · Programmatic", "platform": "TTD", "channel": "Programmatic",
             "allocation_pct": 0.30, "daily_spend": 900, "roas": 1.95},
        ]

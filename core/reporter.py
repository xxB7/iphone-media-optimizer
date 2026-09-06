import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, Any, List

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

console = Console(force_terminal=True)

def format_bytes(size_bytes: int) -> str:
    """Formats bytes into human readable string (KB, MB, GB)."""
    if size_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    val = float(size_bytes)
    while val >= 1024.0 and i < len(units) - 1:
        val /= 1024.0
        i += 1
    return f"{val:.2f} {units[i]}"

class ExecutionReporter:
    """Generates comprehensive terminal summaries and exportable reports."""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir

    def display_terminal_summary(self, stats: Dict[str, Any], elapsed_seconds: float):
        """Displays a clean, executive summary table in the terminal."""
        orig_bytes = stats.get("total_original_bytes", 0)
        comp_bytes = stats.get("total_compressed_bytes", 0)
        saved_bytes = stats.get("total_saved_bytes", 0)
        
        ratio = (saved_bytes / orig_bytes * 100.0) if orig_bytes > 0 else 0.0

        table = Table(title="iPhone DCIM Optimization Summary Report", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan", width=30)
        table.add_column("Value", style="bold green", width=22)

        table.add_row("Total Files Processed", str(stats.get("total_count", 0)))
        table.add_row("Compressed Successfully", str(stats.get("success_count", 0)))
        table.add_row("Kept Original (Size Safe)", str(stats.get("skipped_larger_count", 0)))
        table.add_row("Copied Sidecars (.AAE)", str(stats.get("copied_count", 0)))
        table.add_row("Failed Files", str(stats.get("failed_count", 0)))
        table.add_section()
        table.add_row("Original Size", format_bytes(orig_bytes))
        table.add_row("New Size", format_bytes(comp_bytes))
        table.add_row("Total Space Saved", f"[bold yellow]{format_bytes(saved_bytes)}[/bold yellow]")
        table.add_row("Reduction Ratio", f"[bold green]{ratio:.1f}%[/bold green]")
        table.add_section()
        mins, secs = divmod(int(elapsed_seconds), 60)
        table.add_row("Total Elapsed Time", f"{mins}m {secs}s")

        console.print()
        console.print(table)
        console.print()

    def export_reports(self, stats: Dict[str, Any], elapsed_seconds: float, scan_meta: Dict[str, Any]):
        """Saves persistent JSON and Markdown reports in the output directory."""
        os.makedirs(self.output_dir, exist_ok=True)
        report_data = {
            "generated_at": datetime.now().isoformat(),
            "elapsed_seconds": round(elapsed_seconds, 2),
            "statistics": stats,
            "scan_meta": scan_meta,
            "human_readable": {
                "original_size": format_bytes(stats.get("total_original_bytes", 0)),
                "compressed_size": format_bytes(stats.get("total_compressed_bytes", 0)),
                "saved_size": format_bytes(stats.get("total_saved_bytes", 0)),
                "saving_percentage": f"{(stats.get('total_saved_bytes', 0) / max(1, stats.get('total_original_bytes', 1)) * 100):.2f}%"
            }
        }

        # Save JSON
        json_path = os.path.join(self.output_dir, "optimization_report.json")
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            console.print(f"[red]Error saving JSON report: {e}[/red]")

        # Save Markdown
        md_path = os.path.join(self.output_dir, "optimization_report.md")
        try:
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(f"# تقرير تخفيف مكتبة الآيفون (iPhone Media Optimization Report)\n\n")
                f.write(f"- **تاريخ العملية:** {report_data['generated_at']}\n")
                f.write(f"- **مدة التشغيل:** {int(elapsed_seconds // 60)} دقيقة و {int(elapsed_seconds % 60)} ثانية\n\n")
                f.write(f"## النتائج الرقمية\n")
                f.write(f"| المعيار | القيمة |\n| :--- | :--- |\n")
                f.write(f"| إجمالي الملفات | {stats.get('total_count', 0)} |\n")
                f.write(f"| تم ضغطها بنجاح | {stats.get('success_count', 0)} |\n")
                f.write(f"| أخطاء | {stats.get('failed_count', 0)} |\n")
                f.write(f"| الحجم الأصلي | {report_data['human_readable']['original_size']} |\n")
                f.write(f"| الحجم بعد الضغط | {report_data['human_readable']['compressed_size']} |\n")
                f.write(f"| **المساحة الموفرة** | **{report_data['human_readable']['saved_size']} ({report_data['human_readable']['saving_percentage']})** |\n")
        except Exception as e:
            console.print(f"[red]Error saving Markdown report: {e}[/red]")

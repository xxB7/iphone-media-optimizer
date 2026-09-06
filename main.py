import argparse
import concurrent.futures
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Dict, Any, List

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from core.db import StateDatabase
from core.image_engine import ImageEngine
from core.metadata_engine import MetadataEngine
from core.mtp_reader import MTPReader
from core.reporter import ExecutionReporter, format_bytes
from core.scanner import DirectoryScanner, MediaItem, ScanResult
from core.video_engine import VideoEngine
from utils.hardware import inspect_hardware
from utils.logger import setup_logger, get_logger

console = Console(force_terminal=True)

def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Loads configuration with robust fallback defaults."""
    defaults = {
        "video": {
            "cq": 28,
            "preset": "p5",
            "tune": "hq",
            "rate_control": "vbr",
            "copy_audio": True,
            "keep_framerate": True,
            "enable_hdr_10bit": True,
            "apple_compatibility_tag": "hvc1"
        },
        "photo": {
            "heic_quality": 72,
            "jpeg_quality": 78,
            "max_dimension": 0,
            "optimize_encoding": True
        },
        "metadata": {
            "strict_copy": True,
            "quicktime_utc": True,
            "sync_filesystem_timestamps": True,
            "preserve_live_photos": True,
            "copy_apple_sidecars": True
        },
        "hardware": {
            "gpu_video_workers": 2,
            "cpu_photo_workers": 6
        },
        "safety": {
            "keep_original_if_larger": True,
            "verify_file_integrity": True,
            "atomic_writes": True,
            "enable_resume_db": True
        }
    }
    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_conf = yaml.safe_load(f) or {}
                for section, values in user_conf.items():
                    if section in defaults and isinstance(values, dict):
                        defaults[section].update(values)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not read {config_path} ({e}). Using defaults.[/yellow]")
    return defaults


def print_banner():
    banner_text = """
[bold cyan]╔════════════════════════════════════════════════════════════════════╗[/bold cyan]
[bold cyan]║[/bold cyan]   [bold white]📱 iPhone DCIM Media Optimizer - Enterprise Production Grade[/bold white]   [bold cyan]║[/bold cyan]
[bold cyan]║[/bold cyan]   [yellow]100% EXIF & Metadata Integrity • NVENC GPU Video • Live Photos[/yellow]   [bold cyan]║[/bold cyan]
[bold cyan]╚════════════════════════════════════════════════════════════════════╝[/bold cyan]
"""
    console.print(banner_text)


def process_single_item(
    item: MediaItem,
    input_dir: str,
    output_dir: str,
    video_engine: VideoEngine,
    image_engine: ImageEngine,
    metadata_engine: MetadataEngine,
    db: StateDatabase,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """Processes a single media item with isolation and resume checks."""
    rel_path = item.rel_path
    dest_path = os.path.join(output_dir, rel_path)
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    # 1. Check if already processed in SQLite
    if config["safety"]["enable_resume_db"]:
        if db.is_already_processed(rel_path, item.file_size, item.mtime) and os.path.isfile(dest_path):
            return {
                "rel_path": rel_path,
                "status": "RESUMED_SKIPPED",
                "original_size": item.file_size,
                "compressed_size": os.path.getsize(dest_path),
                "duration_sec": 0.0
            }

    # 2. Sidecar files (.AAE, .XMP) -> Copy directly
    if item.category == "sidecar":
        start_t = time.time()
        shutil.copy2(item.full_path, dest_path)
        dur = time.time() - start_t
        db.record_result(
            rel_path=rel_path,
            source_path=item.full_path,
            output_path=dest_path,
            media_type="sidecar",
            source_mtime=item.mtime,
            original_size=item.file_size,
            compressed_size=item.file_size,
            status="COPIED",
            duration_sec=dur
        )
        return {
            "rel_path": rel_path,
            "status": "COPIED",
            "original_size": item.file_size,
            "compressed_size": item.file_size,
            "duration_sec": dur
        }

    # 3. Video Processing (NVENC)
    elif item.category == "video":
        res = video_engine.process_video(item.full_path, dest_path)
        db.record_result(
            rel_path=rel_path,
            source_path=item.full_path,
            output_path=dest_path,
            media_type="video",
            source_mtime=item.mtime,
            original_size=res.original_size,
            compressed_size=res.compressed_size,
            status=res.status,
            error_message=res.error_message,
            duration_sec=res.duration_sec
        )
        return {
            "rel_path": rel_path,
            "status": res.status,
            "original_size": res.original_size,
            "compressed_size": res.compressed_size,
            "duration_sec": res.duration_sec
        }

    # 4. Image Processing (Pillow-Heif)
    elif item.category == "image":
        res = image_engine.process_image(item.full_path, dest_path)
        db.record_result(
            rel_path=rel_path,
            source_path=item.full_path,
            output_path=dest_path,
            media_type="image",
            source_mtime=item.mtime,
            original_size=res.original_size,
            compressed_size=res.compressed_size,
            status=res.status,
            error_message=res.error_message,
            duration_sec=res.duration_sec
        )
        return {
            "rel_path": rel_path,
            "status": res.status,
            "original_size": res.original_size,
            "compressed_size": res.compressed_size,
            "duration_sec": res.duration_sec
        }

    # 5. Other files -> Copy directly
    else:
        start_t = time.time()
        shutil.copy2(item.full_path, dest_path)
        dur = time.time() - start_t
        db.record_result(
            rel_path=rel_path,
            source_path=item.full_path,
            output_path=dest_path,
            media_type="other",
            source_mtime=item.mtime,
            original_size=item.file_size,
            compressed_size=item.file_size,
            status="COPIED",
            duration_sec=dur
        )
        return {
            "rel_path": rel_path,
            "status": "COPIED",
            "original_size": item.file_size,
            "compressed_size": item.file_size,
            "duration_sec": dur
        }


def main():
    print_banner()

    parser = argparse.ArgumentParser(description="iPhone DCIM Media Optimizer - GPU Accelerated & Full Metadata Preservation")
    parser.add_argument("-i", "--input", help="Path to input DCIM directory")
    parser.add_argument("-o", "--output", help="Path to output directory on PC")
    parser.add_argument("-c", "--config", default="config.yaml", help="Path to custom config.yaml")
    parser.add_argument("--cq", type=int, help="Override NVENC Constant Quality value (e.g. 28)")
    parser.add_argument("--photo-quality", type=int, help="Override HEIC compression quality (e.g. 72)")
    parser.add_argument("--workers-gpu", type=int, help="Max concurrent GPU video encoding sessions")
    parser.add_argument("--workers-cpu", type=int, help="Max concurrent CPU photo compression threads")
    parser.add_argument("--dry-run", action="store_true", help="Scan and display plan without executing compression")
    parser.add_argument("--reset-db", action="store_true", help="Reset SQLite resume database and start fresh")
    args = parser.parse_args()

    # Hardware Inspection
    profile = inspect_hardware()
    console.print(Panel(
        f"[bold]GPU:[/bold] {profile.gpu_name} (VRAM: {profile.vram_total_mb} MB) | NVENC HEVC: {'[green]Available[/green]' if profile.has_nvenc_hevc else '[red]Missing[/red]'}\n"
        f"[bold]CPU Threads:[/bold] {profile.cpu_count} | [bold]FFmpeg:[/bold] {profile.ffmpeg_path or 'Not Found'}\n"
        f"[bold]ExifTool:[/bold] {profile.exiftool_path or 'Not Found'}",
        title="🖥️ Hardware & Software Profile",
        border_style="cyan"
    ))

    if not profile.system_ready:
        for msg in profile.warning_messages:
            console.print(f"[bold red]❌ {msg}[/bold red]")
        sys.exit(1)

    # Check for connected iPhone via MTP
    detected_iphone = MTPReader.detect_iphone()
    is_direct_iphone_mode = False
    temp_staging_dir = None

    if detected_iphone:
        console.print(Panel(
            f"[bold green]📱 Connected iPhone USB Device Detected![/bold green]\n"
            f"[bold]Device:[/bold] {detected_iphone['device_name']}\n"
            f"[bold]Library:[/bold] {detected_iphone['total_files']} files across {detected_iphone['folders_count']} DCIM folders",
            title="✨ Direct iPhone USB Connection Ready",
            border_style="green"
        ))

    # Ask for inputs interactively if not provided via CLI
    input_dir = args.input
    output_dir = args.output

    if not input_dir:
        if detected_iphone:
            console.print("\n[bold cyan]Select Input Source:[/bold cyan]")
            console.print("[bold green][1][/bold green] [bold white]Direct USB Auto-Sync from connected iPhone[/bold white] (Recommended - Zero manual copying)")
            console.print("[bold yellow][2][/bold yellow] [white]Enter local PC folder path manually[/white]")
            choice = console.input("\n[bold yellow]Enter choice [1 or 2] (Default 1): [/bold yellow]").strip()
            if choice in ("", "1", "iphone", "apple"):
                is_direct_iphone_mode = True
            else:
                input_dir = console.input("\n[bold yellow]📂 Enter input folder path (e.g. E:\\MyFolder): [/bold yellow]").strip().strip('"').strip("'")
        else:
            input_dir = console.input("\n[bold yellow]📂 Enter input folder path: [/bold yellow]").strip().strip('"').strip("'")

    if any(w in (input_dir or "") for w in ("This PC", "Apple iPhone", "Internal Storage", "Computer")):
        is_direct_iphone_mode = True

    if not output_dir:
        output_dir = console.input("[bold yellow]💾 Enter output folder path (e.g. E:\\iphone 8): [/bold yellow]").strip().strip('"').strip("'")

    # If direct iPhone mode is selected, extract files automatically from MTP
    if is_direct_iphone_mode:
        temp_staging_dir = os.path.join(output_dir, "_temp_raw_dcim")
        console.print(f"\n[bold green]📥 Extracting DCIM library directly from iPhone via USB...[/bold green]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as mtp_prog:
            total_folders = detected_iphone['folders_count'] if detected_iphone else 19
            task = mtp_prog.add_task("[cyan]Extracting iPhone DCIM folders...", total=total_folders)
            
            def on_folder_done(fname):
                mtp_prog.advance(task)
                mtp_prog.update(task, description=f"[cyan]Extracted folder: {fname}")

            success = MTPReader.extract_iphone_dcim(temp_staging_dir, progress_callback=on_folder_done)
            if not success or not os.path.isdir(temp_staging_dir):
                console.print("[bold red]❌ Failed to read from iPhone. Please unlock your iPhone screen and tap 'Trust This Computer'.[/bold red]")
                sys.exit(1)
        
        input_dir = temp_staging_dir
        console.print("[bold green]✅ Media extracted successfully! Starting GPU NVENC compression...[/bold green]\n")

    elif not os.path.isdir(input_dir):
        console.print(f"[bold red]❌ Error: Input directory does not exist or is invalid: {input_dir}[/bold red]")
        sys.exit(1)

    # Initialize Logger
    os.makedirs(output_dir, exist_ok=True)
    setup_logger(log_dir=os.path.join(output_dir, "logs"))
    logger = get_logger()

    # Load configuration
    config = load_config(args.config)
    if args.cq: config["video"]["cq"] = args.cq
    if args.photo_quality: config["photo"]["heic_quality"] = args.photo_quality
    if args.workers_gpu: config["hardware"]["gpu_video_workers"] = args.workers_gpu
    if args.workers_cpu: config["hardware"]["cpu_photo_workers"] = args.workers_cpu

    # Initialize Engines
    metadata_engine = MetadataEngine(exiftool_path=profile.exiftool_path)
    video_engine = VideoEngine(
        metadata_engine=metadata_engine,
        cq=config["video"]["cq"],
        preset=config["video"]["preset"],
        tune=config["video"]["tune"],
        enable_hdr=config["video"]["enable_hdr_10bit"],
        keep_if_larger=config["safety"]["keep_original_if_larger"],
        ffmpeg_path=profile.ffmpeg_path,
        ffprobe_path=profile.ffprobe_path
    )
    image_engine = ImageEngine(
        metadata_engine=metadata_engine,
        heic_quality=config["photo"]["heic_quality"],
        jpeg_quality=config["photo"]["jpeg_quality"],
        max_dimension=config["photo"]["max_dimension"],
        keep_if_larger=config["safety"]["keep_original_if_larger"]
    )

    # SQLite Database for Resuming
    db_path = os.path.join(output_dir, "optimizer_state.db")
    if args.reset_db and os.path.isfile(db_path):
        os.remove(db_path)
        logger.info("Resume database reset upon user request.")
    db = StateDatabase(db_path)

    # Scan Directory
    scanner = DirectoryScanner(input_dir)
    scan_result = scanner.scan()

    if not scan_result.items:
        console.print("[yellow]No media items found in the specified directory.[/yellow]")
        return

    if args.dry_run:
        console.print("\n[bold cyan]🔍 Dry Run Mode: Found files without modifying anything:[/bold cyan]")
        console.print(f"- Photos: {len(scan_result.images)}")
        console.print(f"- Videos: {len(scan_result.videos)} (including {scan_result.live_photo_pairs_count} Live Photo pairs)")
        console.print(f"- Sidecars: {len(scan_result.sidecars)}")
        console.print(f"- Total Size: {format_bytes(scan_result.total_bytes)}")
        return

    # Execution plan
    gpu_workers = max(1, config["hardware"]["gpu_video_workers"])
    cpu_workers = max(2, config["hardware"]["cpu_photo_workers"])

    console.print(f"\n[bold green]🚀 Processing Started:[/bold green] {len(scan_result.items)} files | GPU Video Workers: {gpu_workers} | CPU Photo Workers: {cpu_workers}")

    start_exec_time = time.time()
    reporter = ExecutionReporter(output_dir)

    # Rich Progress Bar Configuration
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console
    )

    with progress:
        overall_task = progress.add_task("[white]Overall Progress", total=len(scan_result.items))
        video_task = progress.add_task("[magenta]Compressing Videos (NVENC GPU)", total=len(scan_result.videos)) if scan_result.videos else None
        photo_task = progress.add_task("[cyan]Compressing Photos (Pillow-Heif CPU)", total=len(scan_result.images)) if scan_result.images else None

        # 1. Process Videos with bounded GPU concurrency
        if scan_result.videos:
            with concurrent.futures.ThreadPoolExecutor(max_workers=gpu_workers) as executor:
                futures = {
                    executor.submit(
                        process_single_item,
                        vid, input_dir, output_dir, video_engine, image_engine, metadata_engine, db, config
                    ): vid for vid in scan_result.videos
                }
                for fut in concurrent.futures.as_completed(futures):
                    res = fut.result()
                    progress.advance(video_task)
                    progress.advance(overall_task)

        # 2. Process Photos with multicore CPU concurrency
        if scan_result.images:
            with concurrent.futures.ThreadPoolExecutor(max_workers=cpu_workers) as executor:
                futures = {
                    executor.submit(
                        process_single_item,
                        img, input_dir, output_dir, video_engine, image_engine, metadata_engine, db, config
                    ): img for img in scan_result.images
                }
                for fut in concurrent.futures.as_completed(futures):
                    res = fut.result()
                    progress.advance(photo_task)
                    progress.advance(overall_task)

        # 3. Process Sidecars and other files
        other_items = scan_result.sidecars + [it for it in scan_result.items if it.category == "other"]
        for it in other_items:
            process_single_item(it, input_dir, output_dir, video_engine, image_engine, metadata_engine, db, config)
            progress.advance(overall_task)

    elapsed_time = time.time() - start_exec_time

    # Retrieve final statistics from SQLite
    final_stats = db.get_summary_stats()

    # Display Terminal Summary
    reporter.display_terminal_summary(final_stats, elapsed_time)

    # Export Reports
    scan_meta = {
        "input_directory": input_dir,
        "output_directory": output_dir,
        "total_scanned_items": len(scan_result.items),
        "total_scanned_bytes": scan_result.total_bytes,
        "live_photo_pairs": scan_result.live_photo_pairs_count
    }
    reporter.export_reports(final_stats, elapsed_time, scan_meta)

    # Clean up temporary staging if direct iPhone mode was used
    if temp_staging_dir and os.path.isdir(temp_staging_dir):
        try:
            shutil.rmtree(temp_staging_dir)
            console.print("[dim green]🧹 Temporary staging cache cleaned up successfully.[/dim green]")
        except Exception as e:
            logger.debug(f"Could not remove temp staging dir: {e}")

    console.print(f"[bold green]✨ All tasks completed successfully! Output saved to:[/bold green] {output_dir}\n")


if __name__ == "__main__":
    main()

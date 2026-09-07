import os
import sys
import shutil
import argparse
from pathlib import Path
from typing import Set, Tuple
from rich.console import Console
from rich.panel import Panel

# Ensure UTF-8 I/O in Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console()


def get_album_signatures(albums_dir: str) -> Set[Tuple[str, int]]:
    """
    Scans all files in albums directory and creates signatures (filename_lower, file_size).
    """
    signatures = set()
    for root, _, files in os.walk(albums_dir):
        for f in files:
            if f.startswith(".") or f.lower() in ("thumbs.db", "desktop.ini"):
                continue
            full_p = os.path.join(root, f)
            try:
                size = os.path.getsize(full_p)
                signatures.add((f.lower(), size))
            except Exception:
                pass
    return signatures


def separate_unclassified_photos(albums_dir: str, library_dir: str, output_general_dir: str):
    albums_path = Path(albums_dir).resolve()
    library_path = Path(library_dir).resolve()
    output_general_path = Path(output_general_dir).resolve()

    if not albums_path.exists():
        console.print(f"[bold red]❌ Error: Albums directory does not exist:[/bold red] {albums_path}")
        return

    if not library_path.exists():
        console.print(f"[bold red]❌ Error: Library directory does not exist:[/bold red] {library_path}")
        return

    output_general_path.mkdir(parents=True, exist_ok=True)

    console.print(Panel("[bold cyan]🔍 Scanning and indexing album signatures...[/bold cyan]", border_style="cyan"))
    album_signatures = get_album_signatures(str(albums_path))
    console.print(f"✅ Found [bold green]{len(album_signatures)}[/bold green] files inside categorized albums.\n")

    console.print(Panel("[bold cyan]📂 Comparing Library against albums and isolating unclassified items...[/bold cyan]", border_style="cyan"))

    duplicates_count = 0
    unclassified_count = 0
    total_library_files = 0

    # Temporary isolation directory for duplicate files in Library
    duplicates_trash_dir = library_path.parent / "_duplicates_temp_backup"

    for root, _, files in os.walk(str(library_path)):
        for f in files:
            if f.startswith(".") or f.lower() in ("thumbs.db", "desktop.ini"):
                continue

            total_library_files += 1
            src_file = Path(root) / f
            try:
                size = src_file.stat().st_size
            except Exception:
                continue

            signature = (f.lower(), size)

            if signature in album_signatures:
                # File already exists in one of the albums (duplicate copy in Library)
                duplicates_count += 1
                duplicates_trash_dir.mkdir(parents=True, exist_ok=True)
                target_dup = duplicates_trash_dir / f
                if target_dup.exists():
                    target_dup = duplicates_trash_dir / f"{src_file.stem}_{duplicates_count}{src_file.suffix}"
                shutil.move(str(src_file), str(target_dup))
            else:
                # File does not exist in any album (true unclassified photo)
                unclassified_count += 1
                target_gen = output_general_path / f
                if target_gen.exists():
                    target_gen = output_general_path / f"{src_file.stem}_{unclassified_count}{src_file.suffix}"
                shutil.move(str(src_file), str(target_gen))

    report_text = f"""[bold green]🎉 Deduplication & Album Separation Completed Successfully![/bold green]

• [bold white]Total Library Files Scanned:[/bold white] {total_library_files}
• [bold yellow]Duplicates Removed from Library:[/bold yellow] {duplicates_count} [dim](Already preserved in your Albums)[/dim]
• [bold cyan]Unclassified / General Photos:[/bold cyan] {unclassified_count} [bold green](Isolated safely)[/bold green]

📁 [bold white]Output Folder (General Photos):[/bold white] {output_general_path}
📁 [bold white]Backup Folder (Duplicate Copies):[/bold white] {duplicates_trash_dir}
"""
    console.print(Panel(report_text, title="Smart Sorting Report", border_style="green"))


def main():
    parser = argparse.ArgumentParser(description="Smart Album Filter & Deduplicator for iPhone Media Optimizer")
    parser.add_argument("-a", "--albums", help="Path to categorized Albums folder")
    parser.add_argument("-l", "--library", help="Path to full Library export folder")
    parser.add_argument("-o", "--output", help="Path to save unclassified general photos")
    args = parser.parse_args()

    console.print("[bold yellow]====================================================[/bold yellow]")
    console.print("[bold cyan]   📱 iPhone Album Sorter & Deduplicator Tool[/bold cyan]")
    console.print("[bold yellow]====================================================[/bold yellow]\n")

    albums_input = args.albums
    library_input = args.library
    output_dir = args.output

    if not albums_input:
        albums_input = input("1. Enter Albums folder path (مجلد الألبومات): ").strip(' "\'')
    if not library_input:
        library_input = input("2. Enter Full Library folder path (مجلد الاستديو الكامل): ").strip(' "\'')

    if not albums_input or not library_input:
        console.print("[bold red]❌ Both Albums and Library folder paths are required.[/bold red]")
        sys.exit(1)

    if not output_dir:
        default_output = str(Path(albums_input).parent / "الصور_العامة_بدون_ألبوم")
        custom_out = input(f"3. Output folder for general photos [Press Enter for default: {default_output}]: ").strip(' "\'')
        output_dir = custom_out if custom_out else default_output

    separate_unclassified_photos(albums_input, library_input, output_dir)


if __name__ == "__main__":
    main()

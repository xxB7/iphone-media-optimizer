import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class HardwareProfile:
    gpu_name: str
    vram_total_mb: int
    has_nvenc_hevc: bool
    ffmpeg_path: Optional[str]
    ffprobe_path: Optional[str]
    exiftool_path: Optional[str]
    cpu_count: int
    system_ready: bool
    warning_messages: list

def find_exiftool_path() -> Optional[str]:
    """Finds ExifTool executable in PATH or standard Windows locations."""
    which_path = shutil.which("exiftool") or shutil.which("ExifTool")
    if which_path and os.path.isfile(which_path):
        return which_path

    # Check Windows local AppData & Program Files
    user_appdata = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")

    candidates = [
        os.path.join(user_appdata, "Programs", "ExifTool", "ExifTool.exe"),
        os.path.join(user_appdata, "Programs", "ExifTool", "exiftool.exe"),
        os.path.join(program_files, "ExifTool", "exiftool.exe"),
        os.path.join(program_files, "ExifTool", "ExifTool.exe"),
        os.path.join(program_files_x86, "ExifTool", "exiftool.exe"),
        r"C:\Users\XB7\AppData\Local\Programs\ExifTool\ExifTool.exe",
    ]

    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate
    return None

def find_ffmpeg_paths() -> tuple[Optional[str], Optional[str]]:
    """Finds ffmpeg and ffprobe executables."""
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")

    if not ffmpeg or not ffprobe:
        user_local = os.environ.get("LOCALAPPDATA", "")
        winget_links = os.path.join(user_local, "Microsoft", "WinGet", "Links")
        if not ffmpeg and os.path.isfile(os.path.join(winget_links, "ffmpeg.exe")):
            ffmpeg = os.path.join(winget_links, "ffmpeg.exe")
        if not ffprobe and os.path.isfile(os.path.join(winget_links, "ffprobe.exe")):
            ffprobe = os.path.join(winget_links, "ffprobe.exe")

    return ffmpeg, ffprobe

def check_nvenc_support(ffmpeg_path: Optional[str]) -> bool:
    """Checks if FFmpeg supports hevc_nvenc."""
    if not ffmpeg_path:
        return False
    try:
        res = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-encoders"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        return "hevc_nvenc" in res.stdout
    except Exception:
        return False

def get_gpu_info() -> tuple[str, int]:
    """Retrieves NVIDIA GPU model and VRAM in MB via nvidia-smi."""
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        if res.returncode == 0 and res.stdout.strip():
            line = res.stdout.strip().split("\n")[0]
            parts = [p.strip() for p in line.split(",")]
            name = parts[0]
            vram = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            return name, vram
    except Exception:
        pass
    return "Unknown / Not Detected", 0

def inspect_hardware() -> HardwareProfile:
    warnings = []
    gpu_name, vram_mb = get_gpu_info()
    ffmpeg, ffprobe = find_ffmpeg_paths()
    exiftool = find_exiftool_path()
    cpu_count = os.cpu_count() or 4
    has_nvenc = check_nvenc_support(ffmpeg)

    if not ffmpeg:
        warnings.append("FFmpeg executable was not found. Video compression will fail.")
    if not ffprobe:
        warnings.append("FFprobe executable was not found. Video probing/validation will fail.")
    if not exiftool:
        warnings.append("ExifTool was not found. Metadata preservation requires ExifTool.")
    if not has_nvenc:
        warnings.append("FFmpeg was found, but hevc_nvenc hardware encoder is unavailable.")

    ready = (ffmpeg is not None) and (exiftool is not None) and has_nvenc

    return HardwareProfile(
        gpu_name=gpu_name,
        vram_total_mb=vram_mb,
        has_nvenc_hevc=has_nvenc,
        ffmpeg_path=ffmpeg,
        ffprobe_path=ffprobe,
        exiftool_path=exiftool,
        cpu_count=cpu_count,
        system_ready=ready,
        warning_messages=warnings
    )

import os
import sys
import ctypes
from ctypes import wintypes
import subprocess
import tempfile
from datetime import datetime
from typing import Optional, Dict, Any, List
from utils.hardware import find_exiftool_path
from utils.logger import get_logger

logger = get_logger()

# Windows Win32 constants for SetFileTime
FILE_WRITE_ATTRIBUTES = 0x0100
OPEN_EXISTING = 3
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
EPOCH_DIFF = 116444736000000000  # 100-ns between 1601 and 1970

def _to_filetime(epoch_seconds: float) -> wintypes.FILETIME:
    val = int(epoch_seconds * 10000000) + EPOCH_DIFF
    return wintypes.FILETIME(val & 0xFFFFFFFF, val >> 32)

def set_windows_file_times(file_path: str, creation_time: float, modify_time: float):
    """Sets Windows creation time and last write time accurately."""
    try:
        if os.name != 'nt':
            os.utime(file_path, (modify_time, modify_time))
            return

        c_ft = _to_filetime(creation_time)
        m_ft = _to_filetime(modify_time)

        handle = ctypes.windll.kernel32.CreateFileW(
            os.path.abspath(file_path),
            FILE_WRITE_ATTRIBUTES,
            0,
            None,
            OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS,
            None
        )
        if handle == -1 or handle == 0xFFFFFFFF:
            os.utime(file_path, (modify_time, modify_time))
            return

        ctypes.windll.kernel32.SetFileTime(
            handle,
            ctypes.byref(c_ft),
            ctypes.byref(m_ft),
            ctypes.byref(m_ft)
        )
        ctypes.windll.kernel32.CloseHandle(handle)
    except Exception as e:
        logger.debug(f"Failed to set Windows file times on {file_path}: {e}")
        try:
            os.utime(file_path, (modify_time, modify_time))
        except Exception:
            pass


class MetadataEngine:
    """
    Manages metadata cloning, Apple QuickTime/EXIF preservation, and filesystem timestamp syncing.
    Uses UTF-8 temp argfiles on Windows to completely avoid ANSI codepage issues and wildcard errors.
    """

    def __init__(self, exiftool_path: Optional[str] = None):
        self.exiftool_path = exiftool_path or find_exiftool_path()
        if not self.exiftool_path or not os.path.isfile(self.exiftool_path):
            raise FileNotFoundError("ExifTool executable not found. Please install ExifTool or check PATH.")

    def _run_exiftool(self, args: List[str], timeout: int = 60) -> subprocess.CompletedProcess:
        """
        Executes ExifTool safely across all operating systems.
        On Windows, writes arguments to a UTF-8 encoded temporary file in %TEMP%
        and passes '-charset filename=utf8 -@ argfile' to eliminate Windows ANSI codepage
        limitations and 'Wildcards don't work' errors on non-ASCII/Arabic paths.
        """
        # Create temp argfile in standard %TEMP% directory
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, suffix=".txt") as tf:
            for arg in args:
                tf.write(arg + "\n")
            temp_argfile = tf.name

        try:
            cmd = [
                self.exiftool_path,
                "-charset", "filename=utf8",
                "-@", temp_argfile
            ]
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout
            )
            return res
        finally:
            if os.path.isfile(temp_argfile):
                try: os.remove(temp_argfile)
                except Exception: pass

    def copy_metadata(
        self,
        source_path: str,
        dest_path: str,
        is_video: bool = False,
        sync_os_timestamps: bool = True
    ) -> bool:
        """
        Copies 100% of metadata from source to destination file using ExifTool.
        Ensures Apple Live Photo pairing tags and QuickTime UTC tags are strictly retained.
        """
        abs_source = os.path.abspath(source_path)
        abs_dest = os.path.abspath(dest_path)

        args = [
            "-tagsFromFile", abs_source,
            "-all:all",
            "-unsafe",
            "-icc_profile",
        ]

        if is_video:
            # Check if source video has valid internal creation date
            src_summary = self.extract_metadata_summary(abs_source)
            src_create_date = str(src_summary.get("CreateDate", "") or src_summary.get("QuickTime:CreationDate", ""))
            has_internal_date = bool(src_create_date and not src_create_date.startswith("0000"))

            args.extend([
                "-QuickTime:all",
                "-api", "QuickTimeUTC=1",
                # Preserve Apple Live Photo content identifier
                "-Keys:ContentIdentifier",
                "-QuickTime:ContentIdentifier",
                "-UserData:ContentIdentifier",
            ])

            if has_internal_date:
                # Sync track and media headers to internal date
                args.extend([
                    "-TrackCreateDate<CreateDate",
                    "-TrackModifyDate<ModifyDate",
                    "-MediaCreateDate<CreateDate",
                    "-MediaModifyDate<ModifyDate",
                ])
            else:
                # Fallback for PC/DVR/WhatsApp videos that lack internal headers (0000:00:00)
                # Populate QuickTime dates from the original filesystem timestamps
                args.extend([
                    "-CreateDate<FileModifyDate",
                    "-ModifyDate<FileModifyDate",
                    "-QuickTime:CreationDate<FileModifyDate",
                    "-TrackCreateDate<FileModifyDate",
                    "-MediaCreateDate<FileModifyDate",
                ])

        else:
            # Check if source photo has internal EXIF date
            src_summary = self.extract_metadata_summary(abs_source)
            has_photo_date = bool(src_summary.get("DateTimeOriginal") or src_summary.get("CreateDate"))
            if not has_photo_date:
                # Check if parent DCIM folder is in YYYY__MM format (e.g. 2022__10)
                parent_name = os.path.basename(os.path.dirname(abs_source))
                if "__" in parent_name and len(parent_name) == 8 and parent_name[:4].isdigit() and parent_name[6:8].isdigit():
                    ey, em = parent_name[:4], parent_name[6:8]
                    if 2000 <= int(ey) <= 2030 and 1 <= int(em) <= 12:
                        fallback_date = f"{ey}:{em}:15 12:00:00"
                        args.extend([
                            f"-DateTimeOriginal={fallback_date}",
                            f"-CreateDate={fallback_date}",
                        ])
                if not any(a.startswith("-DateTimeOriginal=") for a in args):
                    # Generic fallback to original filesystem timestamps
                    args.extend([
                        "-DateTimeOriginal<FileModifyDate",
                        "-CreateDate<FileModifyDate",
                    ])

        # Overwrite original target directly without keeping a '_original' backup copy
        args.extend([
            "-overwrite_original",
            abs_dest
        ])

        try:
            result = self._run_exiftool(args, timeout=60)

            if result.returncode != 0 and "1 image files updated" not in result.stdout:
                logger.warning(f"ExifTool warning on {os.path.basename(dest_path)}: {result.stderr.strip() or result.stdout.strip()}")

            # Sync OS timestamps to match original shoot date
            if sync_os_timestamps:
                src_stat = os.stat(abs_source)
                m_time = src_stat.st_mtime
                # Set creation time to match shoot/modification time to prevent Windows/iCloud today-drift
                set_windows_file_times(abs_dest, m_time, m_time)

            return True

        except subprocess.TimeoutExpired:
            logger.error(f"ExifTool timed out while processing: {source_path}")
            return False
        except Exception as e:
            logger.error(f"Failed to copy metadata from {source_path} to {dest_path}: {e}")
            return False

    def extract_metadata_summary(self, file_path: str) -> Dict[str, Any]:
        """Extracts key date, GPS, and camera metadata for logging and verification."""
        args = [
            "-json",
            "-DateTimeOriginal",
            "-CreateDate",
            "-QuickTime:CreationDate",
            "-GPSPosition",
            "-Make",
            "-Model",
            "-ContentIdentifier",
            os.path.abspath(file_path)
        ]
        try:
            res = self._run_exiftool(args, timeout=15)
            if res.returncode == 0 and res.stdout.strip():
                import json
                data = json.loads(res.stdout)
                if data and isinstance(data, list):
                    return data[0]
        except Exception as e:
            logger.debug(f"Could not extract metadata summary: {e}")
        return {}

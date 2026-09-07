import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple
from core.metadata_engine import MetadataEngine
from utils.hardware import find_ffmpeg_paths
from utils.logger import get_logger

logger = get_logger()

@dataclass
class VideoStreamInfo:
    width: int
    height: int
    pix_fmt: str
    is_10bit: bool
    is_hdr: bool
    color_primaries: str
    color_trc: str
    colorspace: str
    duration: float
    has_audio: bool
    bitrate: int = 0

@dataclass
class VideoProcessResult:
    status: str  # 'SUCCESS', 'SKIPPED_LARGER', 'FAILED'
    original_size: int
    compressed_size: int
    duration_sec: float
    error_message: str = ""

class VideoEngine:
    """High-performance GPU-accelerated video compression engine using FFmpeg & NVENC."""

    def __init__(
        self,
        metadata_engine: MetadataEngine,
        cq: int = 28,
        preset: str = "p5",
        tune: str = "hq",
        enable_hdr: bool = True,
        keep_if_larger: bool = True,
        ffmpeg_path: Optional[str] = None,
        ffprobe_path: Optional[str] = None
    ):
        self.metadata_engine = metadata_engine
        self.cq = cq
        self.preset = preset
        self.tune = tune
        self.enable_hdr = enable_hdr
        self.keep_if_larger = keep_if_larger

        f_path, p_path = find_ffmpeg_paths()
        self.ffmpeg_path = ffmpeg_path or f_path
        self.ffprobe_path = ffprobe_path or p_path

        if not self.ffmpeg_path or not os.path.isfile(self.ffmpeg_path):
            raise FileNotFoundError("FFmpeg executable was not found.")
        if not self.ffprobe_path or not os.path.isfile(self.ffprobe_path):
            raise FileNotFoundError("FFprobe executable was not found.")

    def probe_video(self, file_path: str) -> Optional[VideoStreamInfo]:
        """Probes video metadata using ffprobe."""
        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-show_format",
            file_path
        ]
        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30
            )
            if res.returncode != 0:
                logger.error(f"FFprobe failed on {file_path}: {res.stderr}")
                return None

            data = json.loads(res.stdout)
            streams = data.get("streams", [])
            vid_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
            has_audio = any(s.get("codec_type") == "audio" for s in streams)

            if not vid_stream:
                return None

            pix_fmt = vid_stream.get("pix_fmt", "yuv420p")
            color_primaries = vid_stream.get("color_primaries", "")
            color_trc = vid_stream.get("color_trc", "")
            colorspace = vid_stream.get("colorspace", "")

            # Detect 10-bit and HDR
            is_10bit = "10" in pix_fmt or "p010" in pix_fmt
            is_hdr = is_10bit or (color_trc in ("smpte2084", "arib-std-b67") or color_primaries == "bt2020")

            duration = float(data.get("format", {}).get("duration", 0.0))
            if duration <= 0:
                duration = float(vid_stream.get("duration", 0.0))

            bitrate = int(data.get("format", {}).get("bit_rate", 0) or vid_stream.get("bit_rate", 0) or 0)

            return VideoStreamInfo(
                width=int(vid_stream.get("width", 0)),
                height=int(vid_stream.get("height", 0)),
                pix_fmt=pix_fmt,
                is_10bit=is_10bit,
                is_hdr=is_hdr,
                color_primaries=color_primaries,
                color_trc=color_trc,
                colorspace=colorspace,
                duration=duration,
                has_audio=has_audio,
                bitrate=bitrate
            )
        except Exception as e:
            logger.error(f"Exception probing {file_path}: {e}")
            return None

    def verify_integrity(self, file_path: str) -> bool:
        """Validates that the output video is healthy and decodable."""
        cmd = [
            self.ffprobe_path,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15
            )
            return res.returncode == 0 and float(res.stdout.strip() or 0) > 0
        except Exception:
            return False

    def process_video(
        self,
        source_path: str,
        dest_path: str,
        custom_cq: Optional[int] = None
    ) -> VideoProcessResult:
        """
        Compresses a video file using hevc_nvenc, injects metadata, and verifies size/integrity.
        """
        start_time = time.time()
        orig_size = os.path.getsize(source_path)
        cq_val = custom_cq if custom_cq is not None else self.cq

        dest_dir = os.path.dirname(os.path.abspath(dest_path))
        if dest_dir:
            os.makedirs(dest_dir, exist_ok=True)
        tmp_output = dest_path + ".tmp.mp4"

        try:
            info = self.probe_video(source_path)
            if not info:
                # If probing fails, fallback to safe copy
                logger.warning(f"Could not probe video {source_path}, copying original.")
                shutil.copy2(source_path, dest_path)
                return VideoProcessResult(
                    status="SKIPPED_LARGER",
                    original_size=orig_size,
                    compressed_size=orig_size,
                    duration_sec=time.time() - start_time
                )

            # Check if already ultra-low bitrate (e.g. TikTok / web clips under 1.2 Mbps)
            if info.bitrate > 0 and info.bitrate < 1200000 and orig_size < 20 * 1024 * 1024:
                logger.info(f"Video {source_path} already highly compressed ({info.bitrate // 1000} kbps). Retaining original.")
                shutil.copy2(source_path, dest_path)
                if self.metadata_engine:
                    self.metadata_engine.copy_metadata(source_path, dest_path, is_video=True)
                return VideoProcessResult(
                    status="SKIPPED_LARGER",
                    original_size=orig_size,
                    compressed_size=orig_size,
                    duration_sec=time.time() - start_time
                )

            # Build NVENC FFmpeg command
            cmd = [
                self.ffmpeg_path,
                "-hide_banner",
                "-nostdin",
                "-y",
                "-i", source_path,
                "-c:v", "hevc_nvenc",
                "-preset", self.preset,
                "-tune", self.tune,
                "-rc", "vbr",
                "-cq", str(cq_val),
                "-b:v", "0",
                "-spatial-aq", "1",
                "-temporal-aq", "1",
            ]

            # Handle 10-bit HDR / Dolby Vision
            if info.is_hdr and self.enable_hdr:
                cmd.extend([
                    "-pix_fmt", "p010le",
                    "-profile:v", "main10"
                ])
                if info.color_primaries:
                    cmd.extend(["-color_primaries", info.color_primaries])
                if info.color_trc:
                    cmd.extend(["-color_trc", info.color_trc])
                if info.colorspace:
                    cmd.extend(["-colorspace", info.colorspace])
            else:
                cmd.extend(["-pix_fmt", "yuv420p"])

            # Audio passthrough
            if info.has_audio:
                cmd.extend(["-c:a", "copy"])
            else:
                cmd.extend(["-an"])

            # Apple compatibility tag and faststart
            cmd.extend([
                "-tag:v", "hvc1",
                "-movflags", "+faststart",
                tmp_output
            ])

            # Run FFmpeg with dynamic timeout (max 4x video duration or 90s minimum)
            timeout_sec = max(90, int(info.duration * 4))
            try:
                res = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout_sec
                )
            except subprocess.TimeoutExpired:
                logger.warning(f"FFmpeg timed out after {timeout_sec}s on {source_path}. Retaining original.")
                if os.path.isfile(tmp_output):
                    try: os.remove(tmp_output)
                    except Exception: pass
                shutil.copy2(source_path, dest_path)
                if self.metadata_engine:
                    self.metadata_engine.copy_metadata(source_path, dest_path, is_video=True)
                return VideoProcessResult(
                    status="SKIPPED_LARGER",
                    original_size=orig_size,
                    compressed_size=orig_size,
                    duration_sec=time.time() - start_time
                )

            if res.returncode != 0:
                err_msg = res.stderr[-500:] if res.stderr else "Unknown FFmpeg error"
                logger.error(f"FFmpeg encoding failed for {source_path}: {err_msg}. Retaining original.")
                if os.path.isfile(tmp_output):
                    try: os.remove(tmp_output)
                    except Exception: pass
                shutil.copy2(source_path, dest_path)
                if self.metadata_engine:
                    self.metadata_engine.copy_metadata(source_path, dest_path, is_video=True)
                return VideoProcessResult(
                    status="SKIPPED_LARGER",
                    original_size=orig_size,
                    compressed_size=orig_size,
                    duration_sec=time.time() - start_time,
                    error_message=err_msg
                )

            # Integrity check
            if not self.verify_integrity(tmp_output):
                logger.error(f"Verification failed on compressed file: {tmp_output}")
                if os.path.isfile(tmp_output):
                    os.remove(tmp_output)
                return VideoProcessResult(
                    status="FAILED",
                    original_size=orig_size,
                    compressed_size=0,
                    duration_sec=time.time() - start_time,
                    error_message="Output video failed decode validation"
                )

            # Metadata copy
            self.metadata_engine.copy_metadata(source_path, tmp_output, is_video=True)

            compressed_size = os.path.getsize(tmp_output)

            # Size check: if compressed file is larger or equal to original, keep original
            if self.keep_if_larger and compressed_size >= orig_size:
                logger.info(f"Compressed video was larger than original ({compressed_size} >= {orig_size}). Retaining original.")
                if os.path.isfile(tmp_output):
                    os.remove(tmp_output)
                shutil.copy2(source_path, dest_path)
                return VideoProcessResult(
                    status="SKIPPED_LARGER",
                    original_size=orig_size,
                    compressed_size=orig_size,
                    duration_sec=time.time() - start_time
                )

            # Atomic move
            if os.path.isfile(dest_path):
                os.remove(dest_path)
            shutil.move(tmp_output, dest_path)

            return VideoProcessResult(
                status="SUCCESS",
                original_size=orig_size,
                compressed_size=compressed_size,
                duration_sec=time.time() - start_time
            )

        except Exception as e:
            logger.error(f"Unexpected error processing video {source_path}: {e}")
            if os.path.isfile(tmp_output):
                try: os.remove(tmp_output)
                except Exception: pass
            return VideoProcessResult(
                status="FAILED",
                original_size=orig_size,
                compressed_size=0,
                duration_sec=time.time() - start_time,
                error_message=str(e)
            )

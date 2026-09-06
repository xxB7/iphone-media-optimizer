import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Tuple, Set
from utils.logger import get_logger

logger = get_logger()

VIDEO_EXTENSIONS = {".mov", ".mp4", ".m4v"}
IMAGE_EXTENSIONS = {".heic", ".heif", ".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".dng"}
SIDECAR_EXTENSIONS = {".aae", ".xmp"}

@dataclass
class MediaItem:
    full_path: str
    rel_path: str
    stem: str
    extension: str
    category: str  # 'video', 'image', 'sidecar', 'other'
    file_size: int
    mtime: float
    is_live_photo: bool = False
    companion_path: str = ""

@dataclass
class ScanResult:
    items: List[MediaItem] = field(default_factory=list)
    videos: List[MediaItem] = field(default_factory=list)
    images: List[MediaItem] = field(default_factory=list)
    sidecars: List[MediaItem] = field(default_factory=list)
    total_bytes: int = 0
    live_photo_pairs_count: int = 0

class DirectoryScanner:
    """Recursively scans and classifies iPhone DCIM directories with Live Photo pairing."""

    def __init__(self, input_dir: str):
        self.input_dir = os.path.abspath(input_dir)
        if not os.path.isdir(self.input_dir):
            raise ValueError(f"Input path does not exist or is not a directory: {self.input_dir}")

    def scan(self) -> ScanResult:
        logger.info(f"Scanning directory: {self.input_dir} ...")
        result = ScanResult()
        
        # Group by folder to detect Live Photos (IMG_xxxx.HEIC + IMG_xxxx.MOV in same folder)
        folder_stems: Dict[str, Dict[str, List[MediaItem]]] = {}

        for root, dirs, files in os.walk(self.input_dir):
            # Sort for deterministic processing
            dirs.sort()
            files.sort()
            
            rel_folder = os.path.relpath(root, self.input_dir)
            if rel_folder not in folder_stems:
                folder_stems[rel_folder] = {}

            for filename in files:
                # Ignore system hidden / temp files
                if filename.startswith(".") or filename.lower() in ("thumbs.db", "desktop.ini"):
                    continue

                full_path = os.path.join(root, filename)
                try:
                    stat = os.stat(full_path)
                    file_size = stat.st_size
                    mtime = stat.st_mtime
                except Exception as e:
                    logger.warning(f"Could not stat file: {full_path} ({e})")
                    continue

                rel_path = os.path.relpath(full_path, self.input_dir)
                stem = Path(filename).stem
                ext = Path(filename).suffix.lower()

                if ext in VIDEO_EXTENSIONS:
                    cat = "video"
                elif ext in IMAGE_EXTENSIONS:
                    cat = "image"
                elif ext in SIDECAR_EXTENSIONS:
                    cat = "sidecar"
                else:
                    cat = "other"

                item = MediaItem(
                    full_path=full_path,
                    rel_path=rel_path,
                    stem=stem,
                    extension=ext,
                    category=cat,
                    file_size=file_size,
                    mtime=mtime
                )

                if stem not in folder_stems[rel_folder]:
                    folder_stems[rel_folder][stem] = []
                folder_stems[rel_folder][stem].append(item)

        # Detect Live Photo pairs and assemble result lists
        for rel_folder, stems in folder_stems.items():
            for stem, group in stems.items():
                has_image = any(it.category == "image" for it in group)
                has_video = any(it.category == "video" for it in group)

                is_live = has_image and has_video
                if is_live:
                    result.live_photo_pairs_count += 1
                    img_item = next(it for it in group if it.category == "image")
                    vid_item = next(it for it in group if it.category == "video")
                    img_item.is_live_photo = True
                    img_item.companion_path = vid_item.full_path
                    vid_item.is_live_photo = True
                    vid_item.companion_path = img_item.full_path

                for item in group:
                    result.items.append(item)
                    result.total_bytes += item.file_size
                    if item.category == "video":
                        result.videos.append(item)
                    elif item.category == "image":
                        result.images.append(item)
                    elif item.category == "sidecar":
                        result.sidecars.append(item)

        logger.info(
            f"Scan completed: Found {len(result.items)} items "
            f"({len(result.images)} images, {len(result.videos)} videos [including {result.live_photo_pairs_count} Live Photo pairs], "
            f"{len(result.sidecars)} sidecars). Total size: {result.total_bytes / (1024*1024*1024):.2f} GB."
        )
        return result

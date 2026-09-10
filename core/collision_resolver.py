import os
from collections import defaultdict
from typing import List, Dict, Tuple
from pathlib import Path
from utils.logger import get_logger

logger = get_logger()

class CollisionResolver:
    """
    Detects and resolves filename stem collisions in media directories.
    Prevents 3uTools and Apple PhotoKit import errors caused by non-pair media
    sharing identical base stems (e.g., IMG_0001.JPG and IMG_0001.MOV/MP4).
    """

    def __init__(self, directory: str):
        self.directory = os.path.abspath(directory)
        if not os.path.isdir(self.directory):
            raise ValueError(f"Directory does not exist: {self.directory}")

    def find_collisions(self) -> Dict[str, List[str]]:
        """Scans directory and returns all stems mapped to multiple filenames."""
        files = [f for f in os.listdir(self.directory) if os.path.isfile(os.path.join(self.directory, f))]
        stems = defaultdict(list)
        for f in files:
            stem, ext = os.path.splitext(f)
            stems[stem.lower()].append(f)
        
        return {stem: flist for stem, flist in stems.items() if len(flist) > 1}

    def resolve_collisions(self) -> Tuple[int, int]:
        """
        Systematically resolves all collisions by appending deterministic suffixes
        to conflicting stems, leaving the primary file unchanged.
        Returns: (resolved_stems_count, renamed_files_count)
        """
        collisions = self.find_collisions()
        if not collisions:
            logger.info("No stem collisions detected.")
            return 0, 0

        logger.info(f"Found {len(collisions)} collision stems to resolve...")
        renamed_count = 0

        for stem, flist in collisions.items():
            # Sort: prioritize .jpg/.heic as primary file, videos/alternate formats get renamed
            flist.sort(key=lambda x: (os.path.splitext(x)[1].lower() not in ('.jpg', '.heic'), x))
            
            # flist[0] remains untouched
            for idx, fname in enumerate(flist[1:], start=1):
                old_stem, ext = os.path.splitext(fname)
                new_name = f"{old_stem}_g{idx}{ext}"
                old_path = os.path.join(self.directory, fname)
                new_path = os.path.join(self.directory, new_name)
                
                while os.path.exists(new_path):
                    idx += 1
                    new_name = f"{old_stem}_g{idx}{ext}"
                    new_path = os.path.join(self.directory, new_name)
                
                try:
                    os.rename(old_path, new_path)
                    renamed_count += 1
                except Exception as e:
                    logger.error(f"Failed to rename {fname} -> {new_name}: {e}")

        remaining = len(self.find_collisions())
        logger.info(f"Resolved {len(collisions)} collision stems ({renamed_count} files renamed). Remaining collisions: {remaining}")
        return len(collisions), renamed_count

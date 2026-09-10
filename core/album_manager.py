import os
import shutil
from typing import Dict, List, Tuple
from pathlib import Path
from core.collision_resolver import CollisionResolver
from core.metadata_engine import MetadataEngine
from utils.logger import get_logger

logger = get_logger()

class AlbumManager:
    """
    Manages final media packaging, album organization, stem collision elimination,
    and metadata verification before iPhone import.
    """

    def __init__(self, output_base_dir: str, metadata_engine: MetadataEngine):
        self.output_base = os.path.abspath(output_base_dir)
        self.metadata_engine = metadata_engine
        if not os.path.isdir(self.output_base):
            raise ValueError(f"Output directory does not exist: {self.output_base}")

    def package_and_verify_all(self) -> Dict[str, Dict[str, int]]:
        """
        Processes each album directory and the general folder:
        1. Quarantines 0-byte files.
        2. Resolves stem collisions.
        3. Ensures chronological EXIF/QuickTime dates on all files.
        Returns detailed statistics per folder.
        """
        stats = {}
        folders = [f for f in os.listdir(self.output_base) if os.path.isdir(os.path.join(self.output_base, f))]

        for folder_name in sorted(folders):
            if folder_name.startswith((".", "_")):
                continue

            folder_path = os.path.join(self.output_base, folder_name)
            logger.info(f"=== Packaging & Verifying: {folder_name} ===")

            # 1. Quarantine 0-byte corrupt files
            corrupt = self.metadata_engine.quarantine_corrupt_files(folder_path)

            # 2. Resolve stem collisions (unless it's verified Live Photos)
            if "Live_Photos" not in folder_name and "صور_حية" not in folder_name:
                resolver = CollisionResolver(folder_path)
                stems_resolved, files_renamed = resolver.resolve_collisions()
            else:
                stems_resolved, files_renamed = 0, 0

            # 3. Ensure chronological EXIF metadata
            injected_count = self.metadata_engine.batch_ensure_chronological_metadata(folder_path)

            file_count = len([f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))])

            stats[folder_name] = {
                "total_files": file_count,
                "corrupt_quarantined": len(corrupt),
                "collisions_resolved": stems_resolved,
                "files_renamed": files_renamed,
                "metadata_injected": injected_count
            }

        self.generate_import_guide()
        return stats

    def generate_import_guide(self) -> str:
        """Generates a clear markdown guide for importing into iPhone with 3uTools."""
        guide_path = os.path.join(self.output_base, "دليل_الاستيراد_إلى_الآيفون.md")
        content = """# دليل استيراد الاستوديو المخفف إلى الآيفون 📱
تم إعداد وفحص كامل وسائط الاستوديو للتأكد من خلوها من أي تعارضات في الأسماء أو نقص في التواريخ.

---

## الخطوات بالترتيب الصحيح عبر 3uTools (مجاني 100%):

### 1. استيراد ألبومات التطبيقات المخصصة (سناب، واتساب، انستقرام)
1. افتح **3uTools** وصل الآيفون بكيبل الـ USB.
2. ادخل على **Photos** ثم **User Album** (ألبومات المستخدم).
3. اضغط **New Album** وأنشئ الألبوم بالاسم المناسب (مثلاً: `Snapchat`, `WhatsApp`, `Instagram`).
4. داخل الألبوم اضغط **Import** -> **Import Folder** واختر مجلد الألبوم من هذا المسار.
> 💡 **ملاحظة مهمة للفرز الزمني داخل ألبوم الآيفون:**
> الألبومات المخصصة في iOS تكون افتراضياً على خيار "ترتيب مخصص". لجعلها مرتبة زمنياً:
> ادخل الألبوم في الآيفون -> اضغط النقاط الثلاث `•••` بالأعلى -> اختر **فرز (Sort)** -> ثم **من الأقدم إلى الأحدث (Oldest to Newest)**.

---

### 2. استيراد الصور الحية (Live Photos)
1. من 3uTools ادخل على **Photos** ثم **Camera Roll**.
2. في الشريط العلوي، اضغط على السهم بجانب **Import** واختر **Import Live Photo**.
3. حدد مجلد الصور الحية.
4. سيتم دمج كل صورة وفيديو كصورة حية رسمية تتحرك باللمس والصوت في الآيفون.

---

### 3. استيراد الصور العامة (المكتبة الرئيسية)
1. من 3uTools ادخل على **Photos** ثم **Camera Roll**.
2. اضغط **Import** -> **Import Folder**.
3. اختر مجلد **الصور العامة بدون ألبوم**.
4. ستنزل كافة الصور والفيديوهات مباشرة في مكتبة الآيفون، وسيتولى نظام iOS ترتيب كل صورة وفيديو في سنتها وشهرها ويومها الحقيقي تلقائياً!
"""
        with open(guide_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"Generated iPhone import guide at: {guide_path}")
        return guide_path

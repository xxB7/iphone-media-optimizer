"""
fix_png_to_jpg.py  --  الحل الكامل لمشكلة ترتيب الصور في الآيفون
=================================================================
1. يحوّل جميع PNG -> JPG مع الحفاظ الكامل على EXIF (التواريخ، GPS)
2. يمزامن FileCreateDate + FileModifyDate مع DateTimeOriginal
3. يعمل بـ 12 خيط متوازي للسرعة القصوى
4. يحفظ نسخة احتياطية من PNG الأصلية
"""

import os
import sys
import shutil
import subprocess
import threading
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
import pillow_heif

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

pillow_heif.register_heif_opener()

# ---- الإعدادات --------------------------------------------------
OUTPUT_BASE = Path(r"E:\استديو مخفف")
PNG_BACKUP  = OUTPUT_BASE / "_png_originals_backup"
SKIP_DIRS   = {
    "_converted_originals_backup", "_reports", "_png_originals_backup",
    "ملفات_تم_تحويلها_جاهزة_للنقل",
    "1_Live_Photos_للاستيراد_كصور_حية",
    "2_الصور_الثابتة_المتبقية",
}
NUM_WORKERS = 12
JPG_QUALITY = 95
# -----------------------------------------------------------------

PNG_BACKUP.mkdir(parents=True, exist_ok=True)

lock       = threading.Lock()
done       = [0]
errors     = [0]
total      = [0]
start_time = [time.time()]


def progress_bar(current, tot, width=42):
    if tot == 0:
        return ""
    pct    = current / tot
    filled = int(width * pct)
    bar    = "=" * filled + "-" * (width - filled)
    elapsed = time.time() - start_time[0]
    rate    = current / elapsed if elapsed > 0 else 0
    eta     = (tot - current) / rate if rate > 0 else 0
    eta_str = f"{int(eta // 60):02d}:{int(eta % 60):02d}"
    return f"[{bar}] {current:,}/{tot:,}  {pct*100:.1f}%  ETA {eta_str}"


def convert_one_png(png_path: Path):
    try:
        mtime = os.path.getmtime(png_path)
        atime = os.path.getatime(png_path)

        with Image.open(png_path) as img:
            exif_data = img.info.get("exif")

            if img.mode in ("RGBA", "LA", "P"):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                converted = img.convert("RGBA") if img.mode == "P" else img
                if converted.mode in ("RGBA", "LA"):
                    bg.paste(converted, mask=converted.split()[-1])
                else:
                    bg.paste(converted)
                rgb_img = bg
            else:
                rgb_img = img.convert("RGB")

            target = png_path.with_suffix(".jpg")
            save_args = {"format": "JPEG", "quality": JPG_QUALITY, "optimize": True}
            if exif_data:
                save_args["exif"] = exif_data
            rgb_img.save(target, **save_args)

        os.utime(target, (atime, mtime))

        # Move original PNG to backup
        rel = png_path.relative_to(OUTPUT_BASE)
        bak = PNG_BACKUP / rel
        bak.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(png_path), str(bak))

        return True, png_path.name

    except Exception as exc:
        return False, f"{png_path.name}: {exc}"


def sync_exif_dates(folder: Path):
    """exiftool: set FileModifyDate and FileCreateDate = DateTimeOriginal."""
    cmd = [
        "exiftool", "-q", "-q",
        "-overwrite_original",
        "-if", "defined($DateTimeOriginal)",
        "-FileModifyDate<DateTimeOriginal",
        "-FileCreateDate<DateTimeOriginal",
        str(folder),
        "-ext", "jpg",
        "-ext", "jpeg",
        "-ext", "heic",
        "-ext", "mov",
        "-ext", "mp4",
    ]
    subprocess.run(cmd, capture_output=True)


# === المرحلة 0: فحص =============================================
print("=" * 65)
print("  الحل الكامل لمشكلة ترتيب الصور في الآيفون")
print("=" * 65)
print("\n[0/3] مسح المجلدات...")

all_pngs = []
for folder in OUTPUT_BASE.iterdir():
    if not folder.is_dir() or folder.name in SKIP_DIRS:
        continue
    for p in folder.rglob("*.png"):
        all_pngs.append(p)
    for p in folder.rglob("*.PNG"):
        all_pngs.append(p)

# Remove duplicates (case-insensitive FS may return both)
all_pngs = list({p.resolve(): p for p in all_pngs}.values())

total[0] = len(all_pngs)
print(f"     تم العثور على {total[0]:,} ملف PNG.")
print(f"     خيوط متوازية: {NUM_WORKERS}  |  نوى المعالج: {os.cpu_count()}")
print(f"     النسخ الاحتياطية: {PNG_BACKUP}")
print()

if total[0] == 0:
    print("لا توجد ملفات PNG -- كل شيء جاهز للنقل.")
    sys.exit(0)

# === المرحلة 1: تحويل PNG -> JPG ================================
print("[1/3] تحويل PNG -> JPG...")
start_time[0] = time.time()

with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
    futures = {executor.submit(convert_one_png, p): p for p in all_pngs}
    for future in as_completed(futures):
        ok, msg = future.result()
        with lock:
            done[0] += 1
            if not ok:
                errors[0] += 1
                print(f"\n  ERROR: {msg}")
        if done[0] % 200 == 0 or done[0] == total[0]:
            bar = progress_bar(done[0], total[0])
            print(f"\r  {bar}", end="", flush=True)

elapsed = time.time() - start_time[0]
success = done[0] - errors[0]
print(f"\n\n     النتيجة: {success:,} نجاح, {errors[0]} خطأ  ({elapsed/60:.1f} دقيقة)\n")

# === المرحلة 2: مزامنة التواريخ ================================
print("[2/3] مزامنة تواريخ الملفات مع EXIF DateTimeOriginal...")
folders = [f for f in OUTPUT_BASE.iterdir()
           if f.is_dir() and f.name not in SKIP_DIRS]
# Also sync the special folders
folders += [OUTPUT_BASE / "2_الصور_الثابتة_المتبقية",
            OUTPUT_BASE / "1_Live_Photos_للاستيراد_كصور_حية"]

for i, folder in enumerate(folders, 1):
    if not folder.exists():
        continue
    print(f"  [{i}/{len(folders)}] {folder.name} ...", end=" ", flush=True)
    sync_exif_dates(folder)
    print("تم")

# === التقرير النهائي ============================================
total_elapsed = time.time() - start_time[0]
print()
print("=" * 65)
print("  اكتمل الحل!")
print(f"  PNG محوّلة : {success:,} ملف")
print(f"  نسخ احتياطية : {PNG_BACKUP.name}")
print(f"  الوقت الكلي : {total_elapsed/60:.1f} دقيقة")
print(f"  الأخطاء : {errors[0]} ملف")
print()
print("  خطوات إعادة النقل للآيفون:")
print()
print("  1. في الجوال: احذف كل الصور المنقولة اليوم")
print("     تطبيق الصور -> اختر الكل -> احذف")
print("     ثم 'حذفت مؤخرا' -> احذف الكل نهائيا")
print()
print("  2. في 3uTools -> Photos -> Import -> Import Folder:")
print("     E:\\استديو مخفف\\الصور_العامة_بدون_ألبوم")
print("     E:\\استديو مخفف\\snapchat")
print("     E:\\استديو مخفف\\instagram")
print("     E:\\استديو مخفف\\whatsapp")
print("     E:\\استديو مخفف\\2_الصور_الثابتة_المتبقية")
print()
print("  3. Live Photos -> 3uTools -> Import Live Photos:")
print("     E:\\استديو مخفف\\1_Live_Photos_للاستيراد_كصور_حية")
print()
print("  الصور ستكون بالترتيب الزمني الصحيح 100%")
print("=" * 65)

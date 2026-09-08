import os
import sys
import shutil
from pathlib import Path
from PIL import Image
import pillow_heif

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

pillow_heif.register_heif_opener()

base_dir = Path(r"E:\استديو مخفف")
gen_dir = base_dir / "الصور_العامة_بدون_ألبوم"

live_dir = base_dir / "1_Live_Photos_للاستيراد_كصور_حية"
still_dir = base_dir / "2_الصور_الثابتة_المتبقية"

live_dir.mkdir(exist_ok=True)
still_dir.mkdir(exist_ok=True)

print("=" * 60)
print("🚀 جاري تحضير خيار Live Photos والصور الثابتة المتبقية...")
print("=" * 60)

# Step 1: Scan and map all files in general folder
files_by_stem = {}
for p in gen_dir.iterdir():
    if not p.is_file():
        continue
    stem = p.stem.upper()
    ext = p.suffix.lower()
    if stem not in files_by_stem:
        files_by_stem[stem] = {}
    files_by_stem[stem][ext] = p

live_pairs = []
standalone_heic = []
standalone_dng = []
standalone_jpeg = []

for stem, exts in files_by_stem.items():
    has_mov = ".mov" in exts
    has_heic = ".heic" in exts
    has_jpg = ".jpg" in exts
    has_jpeg = ".jpeg" in exts
    has_dng = ".dng" in exts
    
    # Priority for Live Photo image component
    img_p = exts.get(".heic") or exts.get(".jpg") or exts.get(".jpeg") or exts.get(".dng")
    
    if has_mov and img_p:
        live_pairs.append((img_p, exts[".mov"]))
    else:
        if has_heic:
            standalone_heic.append(exts[".heic"])
        if has_dng:
            standalone_dng.append(exts[".dng"])
        if has_jpeg:
            standalone_jpeg.append(exts[".jpeg"])

print(f"📊 تم حصر الملفات:")
print(f"  - أزواج Live Photos: {len(live_pairs)} زوج (صورة + فيديو)")
print(f"  - صور HEIC ثابتة (بدون فيديو): {len(standalone_heic)} صورة")
print(f"  - صور ProRAW DNG: {len(standalone_dng)} صورة")
print(f"  - صور JPEG (.jpeg): {len(standalone_jpeg)} صورة")
print("-" * 60)

# -------------------------------------------------------------
# Part 1: Copy Live Photo pairs to 1_Live_Photos_للاستيراد_كصور_حية
# -------------------------------------------------------------
print("\n📁 [1/4] جاري نسخ صور Live Photos إلى مجلدها المستقل...")
live_copied = 0
for img_p, mov_p in live_pairs:
    dst_img = live_dir / img_p.name
    dst_mov = live_dir / mov_p.name
    
    if not dst_img.exists():
        shutil.copy2(img_p, dst_img)
    if not dst_mov.exists():
        shutil.copy2(mov_p, dst_mov)
    
    live_copied += 1
    if live_copied % 200 == 0 or live_copied == len(live_pairs):
        print(f"  نسخ Live Photos: {live_copied}/{len(live_pairs)}")

print(f"✅ اكتمل تجهيز مجلد Live Photos بإجمالي {live_copied} زوج ({live_copied * 2} ملف).")

# -------------------------------------------------------------
# Part 2: Convert Standalone HEIC to JPG in 2_الصور_الثابتة_المتبقية
# -------------------------------------------------------------
print("\n🖼️ [2/4] جاري تحويل صور HEIC الثابتة إلى JPG عالية الجودة...")
heic_converted = 0
for p in standalone_heic:
    target = still_dir / f"{p.stem}.jpg"
    mtime = os.path.getmtime(p)
    atime = os.path.getatime(p)
    
    try:
        with Image.open(p) as img:
            exif = img.info.get("exif")
            rgb_img = img.convert("RGB")
            if exif:
                rgb_img.save(target, format="JPEG", quality=95, optimize=True, exif=exif)
            else:
                rgb_img.save(target, format="JPEG", quality=95, optimize=True)
        
        os.utime(target, (atime, mtime))
        heic_converted += 1
        if heic_converted % 100 == 0 or heic_converted == len(standalone_heic):
            print(f"  تحويل HEIC -> JPG: {heic_converted}/{len(standalone_heic)}")
    except Exception as e:
        print(f"  ❌ خطأ في {p.name}: {e}")

print(f"✅ تم تحويل {heic_converted} صورة HEIC ثابتة بنجاح مع حفظ التواريخ وبيانات EXIF كاملة.")

# -------------------------------------------------------------
# Part 3: Convert ProRAW DNG to JPG in 2_الصور_الثابتة_المتبقية
# -------------------------------------------------------------
print("\n📸 [3/4] جاري تحويل صور Apple ProRAW DNG إلى JPG...")
dng_converted = 0
for p in standalone_dng:
    target = still_dir / f"{p.stem}.jpg"
    mtime = os.path.getmtime(p)
    atime = os.path.getatime(p)
    
    try:
        with Image.open(p) as img:
            rgb_img = img.convert("RGB")
            rgb_img.save(target, format="JPEG", quality=95, optimize=True)
        
        os.utime(target, (atime, mtime))
        dng_converted += 1
        if dng_converted % 50 == 0 or dng_converted == len(standalone_dng):
            print(f"  تحويل DNG -> JPG: {dng_converted}/{len(standalone_dng)}")
    except Exception as e:
        print(f"  ❌ خطأ في {p.name}: {e}")

print(f"✅ تم تحويل {dng_converted} صورة ProRAW DNG بنجاح.")

# -------------------------------------------------------------
# Part 4: Handle JPEG (.jpeg) files in 2_الصور_الثابتة_المتبقية
# -------------------------------------------------------------
print("\n📝 [4/4] جاري حفظ صور JPEG القياسية...")
jpeg_saved = 0
for p in standalone_jpeg:
    target = still_dir / f"{p.stem}.jpg"
    mtime = os.path.getmtime(p)
    atime = os.path.getatime(p)
    
    try:
        shutil.copy2(p, target)
        jpeg_saved += 1
    except Exception as e:
        print(f"  ❌ خطأ في {p.name}: {e}")

print(f"✅ تم تجهيز {jpeg_saved} صورة JPEG بامتداد .jpg القياسي.")

# Also add any files from ملفات_تم_تحويلها_جاهزة_للنقل to still_dir if not already there
quick_dir = base_dir / "ملفات_تم_تحويلها_جاهزة_للنقل"
if quick_dir.exists():
    for f in quick_dir.glob("*"):
        if f.is_file() and not (still_dir / f.name).exists() and not (live_dir / f.name).exists():
            shutil.copy2(f, still_dir / f.name)

total_still = len(list(still_dir.glob("*")))
total_live_items = len(list(live_dir.glob("*")))

print("\n" + "=" * 60)
print(f"🎉 تم الانتهاء بنجاح تام!")
print(f"📂 المجلد الأول: {live_dir.name}")
print(f"   - يحتوي على {total_live_items // 2} صورة Live Photo (إجمالي {total_live_items} ملف: صور وفيديوهات متطابقة)")
print(f"   - الطريقة: في 3uTools اضغط Import ➡️ Import Live Photos واختر هذا المجلد.")
print(f"📂 المجلد الثاني: {still_dir.name}")
print(f"   - يحتوي على {total_still} صورة ثابتة قياسية بصيغة JPG عالية الجودة")
print(f"   - الطريقة: في 3uTools اضغط Import ➡️ Import Folder واختر هذا المجلد.")
print("=" * 60)

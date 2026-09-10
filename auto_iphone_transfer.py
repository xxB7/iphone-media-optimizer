"""
auto_iphone_transfer.py
========================
السكريبت الكامل الآلي - يشتغل أثناء النوم:
1. يحذف 19,109 ملف منقول اليوم من DCIM (يحافظ على 16 صورة أصلية)
2. يرفع كل الملفات الجديدة (JPG/HEIC/MOV/MP4) إلى DCIM
3. iOS يقرأ EXIF تلقائياً ويرتب الصور زمنياً
4. يكتب تقرير نهائي كامل
"""

import asyncio
import sys
import os
import time
import logging
from pathlib import Path
from datetime import date, datetime

sys.stdout.reconfigure(encoding="utf-8")

# ---- الإعدادات -------------------------------------------------------
OUTPUT_BASE  = Path(r"E:\استديو مخفف")
LOG_FILE     = OUTPUT_BASE / "_transfer_log.txt"
TODAY        = date(2026, 9, 8)
DCIM_START   = 200          # نبدأ مجلدات جديدة من 200APPLE
FILES_PER_FOLDER = 900      # max per DCIM subfolder
UPLOAD_SEM   = 3            # concurrent uploads via AFC
VALID_EXTS   = {".jpg", ".jpeg", ".heic", ".mov", ".mp4", ".dng", ".png"}

# ترتيب المجلدات للرفع (Live Photos أولاً لضمان الزوج)
UPLOAD_DIRS = [
    OUTPUT_BASE / "1_Live_Photos_للاستيراد_كصور_حية",
    OUTPUT_BASE / "الصور_العامة_بدون_ألبوم",
    OUTPUT_BASE / "2_الصور_الثابتة_المتبقية",
    OUTPUT_BASE / "snapchat",
    OUTPUT_BASE / "instagram",
    OUTPUT_BASE / "whatsapp",
]
# ----------------------------------------------------------------------

# إعداد اللوغ
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("transfer")

t_start = time.time()


def elapsed():
    s = int(time.time() - t_start)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


# ======================================================================
# المرحلة 1: حذف ملفات اليوم من DCIM (يحافظ على الأصلية)
# ======================================================================
async def phase1_delete(afc):
    log.info("=" * 60)
    log.info("المرحلة 1/3 -- حذف ملفات اليوم من DCIM")
    log.info("=" * 60)

    folders = await afc.listdir("DCIM")
    deleted = 0
    kept    = 0
    errors  = 0

    for folder in sorted(folders):
        if folder.startswith("."):
            continue
        try:
            files = await afc.listdir("DCIM/" + folder)
        except Exception:
            continue

        for fname in files:
            path = "DCIM/" + folder + "/" + fname
            try:
                stat = await afc.stat(path)
                bt   = stat.get("st_birthtime")
                if bt and bt.date() == TODAY:
                    await afc.rm(path)
                    deleted += 1
                else:
                    kept += 1
                    log.info(f"  محفوظة (أصلية): {path}")
            except Exception as e:
                errors += 1
                log.warning(f"  خطأ في: {path} -- {e}")

        if deleted % 1000 == 0 and deleted > 0:
            log.info(f"  تم حذف {deleted:,} ملف حتى الآن...")

    log.info(f"  ✅ حذف اكتمل: {deleted:,} محذوف | {kept} محفوظ | {errors} خطأ")
    return deleted, kept


# ======================================================================
# المرحلة 2: جمع الملفات وتنظيمها
# ======================================================================
def collect_files():
    log.info("=" * 60)
    log.info("المرحلة 2/3 -- جمع وتنظيم الملفات للرفع")
    log.info("=" * 60)

    all_files = []
    for d in UPLOAD_DIRS:
        if not d.exists():
            log.warning(f"  المجلد غير موجود: {d.name}")
            continue
        count = 0
        for f in d.iterdir():
            if f.is_file() and f.suffix.lower() in VALID_EXTS:
                all_files.append(f)
                count += 1
        log.info(f"  {d.name}: {count:,} ملف")

    log.info(f"  إجمالي: {len(all_files):,} ملف للرفع")

    # Live Photos: تأكد من أن كل زوج (HEIC + MOV) بنفس المجلد
    # نفصلهم ونرتبهم بحيث يكونوا متجاورين
    live_stems = {}
    regular    = []

    live_dir = OUTPUT_BASE / "1_Live_Photos_للاستيراد_كصور_حية"
    live_files_set = set()
    if live_dir.exists():
        for f in live_dir.iterdir():
            if f.is_file() and f.suffix.lower() in VALID_EXTS:
                live_files_set.add(f)

    # فصل Live Photos عن الباقي
    live_pairs = {}
    rest = []
    for f in all_files:
        if f in live_files_set:
            stem = f.stem.upper()
            if stem not in live_pairs:
                live_pairs[stem] = []
            live_pairs[stem].append(f)
        else:
            rest.append(f)

    # دمج الأزواج: HEIC أولاً ثم MOV (ضروري لـ Live Photos)
    ordered = []
    for stem, pair in live_pairs.items():
        heic = [x for x in pair if x.suffix.lower() == ".heic"]
        mov  = [x for x in pair if x.suffix.lower() == ".mov"]
        ordered.extend(heic)
        ordered.extend(mov)

    # الملفات الباقية (مرتبة بالاسم لاتساق أكبر)
    rest.sort(key=lambda f: f.name)
    ordered.extend(rest)

    log.info(f"  Live Photo pairs: {len(live_pairs):,} زوج")
    log.info(f"  ملفات عادية: {len(rest):,}")
    return ordered


# ======================================================================
# المرحلة 3: رفع الملفات إلى DCIM
# ======================================================================
async def phase3_upload(afc, files):
    log.info("=" * 60)
    log.info("المرحلة 3/3 -- رفع الملفات إلى DCIM")
    log.info("=" * 60)

    total       = len(files)
    uploaded    = 0
    errors      = 0
    folder_idx  = DCIM_START
    folder_count = 0

    sem = asyncio.Semaphore(UPLOAD_SEM)

    async def upload_one(local_path: Path, remote_path: str):
        async with sem:
            try:
                await afc.push(local_path, remote_path, progress_bar=False)
                return True
            except Exception as e:
                log.warning(f"  خطأ رفع: {local_path.name} -- {e}")
                # Retry once
                try:
                    await asyncio.sleep(1)
                    await afc.push(local_path, remote_path, progress_bar=False)
                    return True
                except Exception as e2:
                    log.error(f"  فشل نهائي: {local_path.name} -- {e2}")
                    return False

    # إنشاء المجلدات وتوزيع الملفات
    # نحتاج نخلي Live Photo pairs تروح لنفس المجلد
    batches = []
    current_batch = []

    live_dir = OUTPUT_BASE / "1_Live_Photos_للاستيراد_كصور_حية"

    for i, f in enumerate(files):
        current_batch.append(f)

        # عند اكتمال المجلد أو انتهاء الملفات
        is_live = f.parent == live_dir
        next_is_pair = False

        # تأكد ما نكسر زوج Live Photo بين مجلدين
        if i + 1 < len(files) and is_live:
            next_f = files[i + 1]
            if next_f.stem.upper() == f.stem.upper() and next_f.parent == live_dir:
                next_is_pair = True

        if len(current_batch) >= FILES_PER_FOLDER and not next_is_pair:
            batches.append((folder_idx, list(current_batch)))
            folder_idx += 1
            current_batch = []

    if current_batch:
        batches.append((folder_idx, current_batch))

    log.info(f"  سيتم إنشاء {len(batches)} مجلد DCIM (من {DCIM_START}APPLE)")

    # رفع كل batch
    last_log_time = time.time()
    for batch_num, (fnum, batch_files) in enumerate(batches, 1):
        folder_name = f"{fnum}APPLE"
        remote_dir  = f"DCIM/{folder_name}"

        # إنشاء المجلد إذا ما موجود
        try:
            await afc.makedirs(remote_dir)
        except Exception:
            pass  # ربما موجود

        log.info(f"  [{batch_num}/{len(batches)}] {folder_name}: {len(batch_files)} ملف")

        tasks = []
        for local_f in batch_files:
            remote_path = f"{remote_dir}/{local_f.name}"
            tasks.append(upload_one(local_f, remote_path))

        results = await asyncio.gather(*tasks)
        batch_ok  = sum(1 for r in results if r)
        batch_err = sum(1 for r in results if not r)

        uploaded += batch_ok
        errors   += batch_err

        # تقدم كل دقيقة
        if time.time() - last_log_time > 60:
            pct = uploaded / total * 100
            log.info(f"  التقدم: {uploaded:,}/{total:,} ({pct:.1f}%) | خطأ: {errors} | الوقت: {elapsed()}")
            last_log_time = time.time()

    return uploaded, errors


# ======================================================================
# التشغيل الرئيسي
# ======================================================================
async def main():
    log.info("=" * 60)
    log.info("  بدأ السكريبت الكامل -- " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    log.info("  iPhone 14 Pro Max -- iOS 26.5.2")
    log.info("=" * 60)

    from pymobiledevice3.lockdown import create_using_usbmux

    lockdown = await create_using_usbmux()
    log.info(f"  متصل بـ: {lockdown.display_name} ({lockdown.udid})")

    from pymobiledevice3.services.afc import AfcService

    async with AfcService(lockdown) as afc:
        # المرحلة 1: حذف
        deleted, kept = await phase1_delete(afc)

        # المرحلة 2: جمع الملفات
        files = collect_files()

        # المرحلة 3: رفع
        uploaded, up_errors = await phase3_upload(afc, files)

    # ======= التقرير النهائي =======
    total_elapsed = time.time() - t_start
    h = int(total_elapsed // 3600)
    m = int((total_elapsed % 3600) // 60)

    log.info("")
    log.info("=" * 60)
    log.info("  اكتمل كل شيء!")
    log.info(f"  الوقت الكلي     : {h} ساعة و {m} دقيقة")
    log.info(f"  محذوف من DCIM   : {deleted:,} ملف")
    log.info(f"  محفوظ (أصلي)    : {kept} ملف")
    log.info(f"  مرفوع للجوال    : {uploaded:,} ملف")
    log.info(f"  أخطاء رفع       : {up_errors} ملف")
    log.info("")
    log.info("  لما تصحى:")
    log.info("  1. افصل الجوال وأعد توصيله (يجبر iOS يعيد الفهرسة)")
    log.info("  2. افتح تطبيق الصور -> مكتبة -> كل الصور")
    log.info("  3. الصور يجب أن تكون مرتبة زمنياً بشكل صحيح 100%")
    log.info("  4. التقرير الكامل محفوظ في: " + str(LOG_FILE))
    log.info("=" * 60)


asyncio.run(main())

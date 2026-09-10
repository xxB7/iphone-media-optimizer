"""
clean_dcim_ghost_files.py
==========================
أداة سريعة لحذف المجلدات الشبحية (200APPLE فما فوق)
التي تم رفعها بالأمس إلى DCIM واستهلكت مساحة الآيفون بدون أن تظهر في تطبيق الصور.
تحافظ 100% على مجلدات وصور الآيفون الأصلية (100APPLE وغيرها).
"""

import asyncio
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

async def clean_dcim():
    print("=" * 60)
    print("🔍 جاري الاتصال بالآيفون عبر USB...")
    print("=" * 60)

    try:
        from pymobiledevice3.lockdown import create_using_usbmux
        from pymobiledevice3.services.afc import AfcService
    except ImportError:
        print("❌ مكتبة pymobiledevice3 غير مثبتة.")
        return

    try:
        lockdown = await create_using_usbmux()
        print(f"✅ متصل بنجاح: {lockdown.display_name} ({lockdown.product_type})")
    except Exception as e:
        print(f"❌ لم يتم العثور على آيفون متصل عبر الكيبل: {e}")
        print("💡 الرجاء توصيل الآيفون بالكمبيوتر وإلغاء قفل الشاشة والضغط على 'وثوق' (Trust).")
        return

    async with AfcService(lockdown) as afc:
        folders = await afc.listdir("DCIM")
        target_folders = []
        for f in folders:
            # نستهدف فقط المجلدات التي تبدأ برقم 200 فأعلى مثل 200APPLE, 201APPLE ...
            if f.endswith("APPLE") and f[:3].isdigit() and int(f[:3]) >= 200:
                target_folders.append(f)

        if not target_folders:
            print("✅ لا توجد أي مجلدات شبحية منقولة (200APPLE+). الذاكرة نظيفة.")
            return

        print(f"\n⚠️ تم العثور على {len(target_folders)} مجلد شبحي تم رفعها سابقاً وتستهلك مساحة:")
        for f in target_folders[:5]:
            print(f"   - DCIM/{f}")
        if len(target_folders) > 5:
            print(f"   ... و {len(target_folders) - 5} مجلد آخر.")

        print("\n🗑️ جاري حذف الملفات والمجلدات الشبحية لتحرير مساحة الآيفون...")
        total_deleted = 0
        for f in sorted(target_folders):
            remote_dir = f"DCIM/{f}"
            try:
                files = await afc.listdir(remote_dir)
                for fname in files:
                    await afc.rm(f"{remote_dir}/{fname}")
                    total_deleted += 1
                await afc.rm(remote_dir)
                print(f"  ✓ تم حذف {remote_dir} ({len(files)} ملف)")
            except Exception as e:
                print(f"  ❌ خطأ في {remote_dir}: {e}")

        print("\n" + "=" * 60)
        print(f"🎉 تم بنجاح حذف {total_deleted:,} ملف وتحرير كامل المساحة في الآيفون!")
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(clean_dcim())

import os
import sys
import shutil
import sqlite3
import subprocess
from pathlib import Path
from PIL import Image
import pillow_heif

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

output_base = Path(r"E:\استديو مخفف")
backup_dir = output_base / "_converted_originals_backup"
backup_dir.mkdir(exist_ok=True)
db_path = output_base / "_reports" / "optimizer_state.db"

pillow_heif.register_heif_opener()

conn = None
if db_path.exists():
    conn = sqlite3.connect(db_path)

def update_db(orig_rel, new_path, new_size):
    if not conn:
        return
    try:
        c = conn.cursor()
        c.execute("""
            UPDATE processed_records
            SET output_path = ?, compressed_size = ?, status = 'CONVERTED_STANDARD'
            WHERE rel_path = ? OR output_path LIKE ?
        """, (str(new_path), new_size, str(orig_rel), f"%{Path(orig_rel).name}"))
        conn.commit()
    except Exception as e:
        print(f"DB update error for {orig_rel}: {e}")

converted_count = 0
errors = []

# 1. Convert 10 misnamed HEIC (.WEBP) files
print("--- Converting Misnamed HEIC (.WEBP) files ---")
for p in sorted(output_base.rglob("*.WEBP")):
    if "_converted_originals_backup" in p.parts or "_reports" in p.parts:
        continue
    try:
        mtime = os.path.getmtime(p)
        atime = os.path.getatime(p)
        target = p.with_suffix(".jpg")
        
        with Image.open(p) as img:
            rgb_img = img.convert("RGB")
            rgb_img.save(target, format="JPEG", quality=95, optimize=True)
        
        os.utime(target, (atime, mtime))
        
        # Move original to backup
        rel = p.relative_to(output_base)
        bak_target = backup_dir / rel
        bak_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(p), str(bak_target))
        
        update_db(rel, target, target.stat().st_size)
        converted_count += 1
        print(f"✅ Converted HEIC/WebP -> JPG: {p.name} -> {target.name} ({target.stat().st_size / 1024:.1f} KB)")
    except Exception as e:
        errors.append((p.name, str(e)))
        print(f"❌ Error converting {p.name}: {e}")

# 2. Convert PSD file
print("\n--- Converting PSD file ---")
for p in sorted(output_base.rglob("*.PSD")):
    if "_converted_originals_backup" in p.parts or "_reports" in p.parts:
        continue
    try:
        mtime = os.path.getmtime(p)
        atime = os.path.getatime(p)
        target = p.with_suffix(".jpg")
        
        with Image.open(p) as img:
            rgb_img = img.convert("RGB")
            rgb_img.save(target, format="JPEG", quality=95, optimize=True)
        
        os.utime(target, (atime, mtime))
        
        rel = p.relative_to(output_base)
        bak_target = backup_dir / rel
        bak_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(p), str(bak_target))
        
        update_db(rel, target, target.stat().st_size)
        converted_count += 1
        print(f"✅ Converted PSD -> JPG: {p.name} -> {target.name} ({target.stat().st_size / 1024:.1f} KB)")
    except Exception as e:
        errors.append((p.name, str(e)))
        print(f"❌ Error converting {p.name}: {e}")

# 3. Remux M4V video
print("\n--- Remuxing M4V video ---")
for p in sorted(output_base.rglob("*.M4V")):
    if "_converted_originals_backup" in p.parts or "_reports" in p.parts:
        continue
    try:
        mtime = os.path.getmtime(p)
        atime = os.path.getatime(p)
        target = p.with_suffix(".mp4")
        
        cmd = [
            "ffmpeg", "-nostdin", "-y", "-i", str(p),
            "-c", "copy", "-movflags", "+faststart",
            str(target)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {res.stderr[:200]}")
        
        os.utime(target, (atime, mtime))
        
        rel = p.relative_to(output_base)
        bak_target = backup_dir / rel
        bak_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(p), str(bak_target))
        
        update_db(rel, target, target.stat().st_size)
        converted_count += 1
        print(f"✅ Remuxed M4V -> MP4: {p.name} -> {target.name} ({target.stat().st_size / (1024*1024):.2f} MB)")
    except Exception as e:
        errors.append((p.name, str(e)))
        print(f"❌ Error remuxing {p.name}: {e}")

# 4. Convert animated GIF files
print("\n--- Converting animated GIF files ---")
for p in sorted(output_base.rglob("*.GIF")):
    if "_converted_originals_backup" in p.parts or "_reports" in p.parts:
        continue
    try:
        mtime = os.path.getmtime(p)
        atime = os.path.getatime(p)
        target = p.with_suffix(".mp4")
        
        cmd = [
            "ffmpeg", "-nostdin", "-y", "-i", str(p),
            "-movflags", "+faststart", "-pix_fmt", "yuv420p",
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            str(target)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {res.stderr[:200]}")
        
        os.utime(target, (atime, mtime))
        
        rel = p.relative_to(output_base)
        bak_target = backup_dir / rel
        bak_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(p), str(bak_target))
        
        update_db(rel, target, target.stat().st_size)
        converted_count += 1
        print(f"✅ Converted GIF -> MP4: {p.name} -> {target.name} ({target.stat().st_size / 1024:.1f} KB)")
    except Exception as e:
        errors.append((p.name, str(e)))
        print(f"❌ Error converting {p.name}: {e}")

if conn:
    conn.close()

print(f"\n==========================================")
print(f"🎉 Summary: Successfully converted {converted_count} files.")
if errors:
    print(f"⚠️ {len(errors)} errors occurred:")
    for name, err in errors:
        print(f"  - {name}: {err}")
else:
    print("✨ All 17 non-standard files converted with 0 errors!")
print(f"==========================================")

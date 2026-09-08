import os
import sys
from pathlib import Path
from PIL import Image
import shutil

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

output_base = r"E:\استديو مخفف"
backup_dir = os.path.join(output_base, "_converted_originals_backup")
os.makedirs(backup_dir, exist_ok=True)

converted_count = 0
converted_psd = 0

for root, _, files in os.walk(output_base):
    if "_converted_originals_backup" in root or "_reports" in root:
        continue
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        full_p = os.path.join(root, f)

        if ext == ".webp":
            try:
                mtime = os.path.getmtime(full_p)
                ctime = os.path.getctime(full_p)

                with Image.open(full_p) as img:
                    stem = Path(f).stem
                    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                        new_ext = ".png"
                        target_p = os.path.join(root, f"{stem}{new_ext}")
                        img.save(target_p, format="PNG")
                    else:
                        new_ext = ".jpg"
                        target_p = os.path.join(root, f"{stem}{new_ext}")
                        rgb_img = img.convert("RGB")
                        rgb_img.save(target_p, format="JPEG", quality=95)

                # Preserve timestamps
                os.utime(target_p, (mtime, mtime))

                # Move original webp to backup
                rel = os.path.relpath(full_p, output_base)
                bak_path = os.path.join(backup_dir, rel)
                os.makedirs(os.path.dirname(bak_path), exist_ok=True)
                shutil.move(full_p, bak_path)

                converted_count += 1
                print(f"Converted WebP -> {new_ext}: {f}")
            except Exception as e:
                print(f"Error converting WebP {f}: {e}")

        elif ext == ".psd":
            try:
                mtime = os.path.getmtime(full_p)
                with Image.open(full_p) as img:
                    stem = Path(f).stem
                    target_p = os.path.join(root, f"{stem}.png")
                    img.save(target_p, format="PNG")
                os.utime(target_p, (mtime, mtime))

                rel = os.path.relpath(full_p, output_base)
                bak_path = os.path.join(backup_dir, rel)
                os.makedirs(os.path.dirname(bak_path), exist_ok=True)
                shutil.move(full_p, bak_path)

                converted_psd += 1
                print(f"Converted PSD -> .png: {f}")
            except Exception as e:
                print(f"Error converting PSD {f}: {e}")

# Move report and db files to _reports folder so 3uTools doesn't parse them as photos
reports_dir = os.path.join(output_base, "_reports")
os.makedirs(reports_dir, exist_ok=True)

for fname in os.listdir(output_base):
    if fname in ("optimization_report.md", "optimization_report.json", "optimizer_state.db", "optimizer_state.db-shm", "optimizer_state.db-wal"):
        src = os.path.join(output_base, fname)
        dst = os.path.join(reports_dir, fname)
        if os.path.exists(dst):
            os.remove(dst)
        shutil.move(src, dst)
        print(f"Moved non-media report file: {fname} -> _reports/")

print(f"\n✅ All done! Successfully converted {converted_count} WebP files and {converted_psd} PSD files to standard formats.")

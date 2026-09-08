import subprocess
import pathlib
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

p = pathlib.Path(r"E:\استديو مخفف\الصور_العامة_بدون_ألبوم\IMG_0015.HEIC")
mov = pathlib.Path(r"E:\استديو مخفف\الصور_العامة_بدون_ألبوم\IMG_0015.mov")

cmd = ["exiftool", "-charset", "filename=utf8", "-s", str(p)]
res = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="ignore")
print("=== HEIC TAGS ===")
for l in res.stdout.splitlines():
    if any(k in l.lower() for k in ["date", "model", "live", "contentidentifier", "apple"]):
        print(l)

cmd2 = ["exiftool", "-charset", "filename=utf8", "-s", str(mov)]
res2 = subprocess.run(cmd2, capture_output=True, encoding="utf-8", errors="ignore")
print("\n=== MOV TAGS ===")
for l in res2.stdout.splitlines():
    if any(k in l.lower() for k in ["date", "model", "live", "contentidentifier", "apple"]):
        print(l)

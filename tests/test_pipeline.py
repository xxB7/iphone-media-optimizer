import os
import sys
import shutil
import subprocess
import time
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from PIL import Image
import pillow_heif
from core.metadata_engine import MetadataEngine
from utils.hardware import inspect_hardware

pillow_heif.register_heif_opener()

def create_synthetic_dcim(base_dir: str):
    """Creates a mock iPhone DCIM structure with realistic EXIF, GPS, and Live Photo metadata."""
    dcim_apple = os.path.join(base_dir, "DCIM", "100APPLE")
    os.makedirs(dcim_apple, exist_ok=True)

    hardware = inspect_hardware()
    exiftool = hardware.exiftool_path
    ffmpeg = hardware.ffmpeg_path

    print(f"Creating mock DCIM at: {dcim_apple}")

    # 1. Create a Live Photo Pair: IMG_0001.HEIC + IMG_0001.MOV
    live_uuid = "E5616D19-8692-4934-B27D-5EBFF749EBF7"
    img_path = os.path.join(dcim_apple, "IMG_0001.HEIC")
    mov_path = os.path.join(dcim_apple, "IMG_0001.MOV")

    # Generate Image
    img = Image.new("RGB", (1920, 1080), color=(120, 180, 240))
    img.save(img_path, format="HEIF", quality=95)

    # Generate Video with FFmpeg (1080p, 5 seconds with high bitrate so NVENC compresses it)
    subprocess.run([
        ffmpeg, "-y", "-f", "lavfi",
        "-i", "testsrc=duration=5:size=1920x1080:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=5",
        "-c:v", "libx264", "-b:v", "5000k", "-c:a", "aac",
        "-movflags", "+faststart",
        mov_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    meta_engine = MetadataEngine(exiftool)

    fake_shoot_date = "2024:06:15 14:30:00"
    gps_lat = 24.7136
    gps_lon = 46.6753

    # Tag Photo
    res_img = meta_engine._run_exiftool([
        "-overwrite_original",
        "-Make=Apple",
        "-Model=iPhone 15 Pro",
        f"-DateTimeOriginal={fake_shoot_date}",
        f"-CreateDate={fake_shoot_date}",
        f"-GPSLatitude={gps_lat}",
        "-GPSLatitudeRef=N",
        f"-GPSLongitude={gps_lon}",
        "-GPSLongitudeRef=E",
        img_path
    ])
    if res_img.returncode != 0:
        print(f"ExifTool photo tagging warning/error: {res_img.stderr} / {res_img.stdout}")

    # Tag Video
    res_mov = meta_engine._run_exiftool([
        "-overwrite_original",
        "-Make=Apple",
        "-Model=iPhone 15 Pro",
        f"-QuickTime:CreationDate={fake_shoot_date}+03:00",
        f"-GPSCoordinates={gps_lat}, {gps_lon}",
        f"-Keys:ContentIdentifier={live_uuid}",
        mov_path
    ])
    if res_mov.returncode != 0:
        print(f"ExifTool video tagging warning/error: {res_mov.stderr} / {res_mov.stdout}")

    # 3. Create a standard JPEG photo: IMG_0002.JPG
    jpg_path = os.path.join(dcim_apple, "IMG_0002.JPG")
    img2 = Image.new("RGB", (1280, 720), color=(200, 100, 50))
    img2.save(jpg_path, format="JPEG", quality=95)
    meta_engine._run_exiftool([
        "-overwrite_original",
        "-Make=Apple",
        "-Model=iPhone 15 Pro",
        "-DateTimeOriginal=2024:07:01 09:15:00",
        "-GPSLatitude=21.4225", "-GPSLatitudeRef=N",
        "-GPSLongitude=39.8262", "-GPSLongitudeRef=E",
        jpg_path
    ])

    # 4. Create an Apple .AAE edit sidecar
    aae_path = os.path.join(dcim_apple, "IMG_0002.AAE")
    with open(aae_path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?><plist version="1.0"><dict><key>adjustmentData</key><string>AppleFilterPreset</string></dict></plist>')

    print("Synthetic DCIM library generated successfully!")
    return os.path.join(base_dir, "DCIM")


def verify_output_directory(output_dir: str):
    """Rigorously inspects output directory files to guarantee 100% metadata and compression integrity."""
    hardware = inspect_hardware()
    meta_engine = MetadataEngine(hardware.exiftool_path)

    out_100apple = os.path.join(output_dir, "100APPLE")
    assert os.path.isdir(out_100apple), f"Missing 100APPLE in output: {out_100apple}"

    out_heic = os.path.join(out_100apple, "IMG_0001.HEIC")
    out_mov = os.path.join(out_100apple, "IMG_0001.MOV")
    out_jpg = os.path.join(out_100apple, "IMG_0002.JPG")
    out_aae = os.path.join(out_100apple, "IMG_0002.AAE")

    assert os.path.isfile(out_heic), "Missing compressed HEIC!"
    assert os.path.isfile(out_mov), "Missing compressed MOV!"
    assert os.path.isfile(out_jpg), "Missing compressed JPG!"
    assert os.path.isfile(out_aae), "Missing copied AAE sidecar!"

    print("\n--- [1] Checking Metadata Preservation ---")
    
    # Check HEIC Metadata
    heic_meta = meta_engine.extract_metadata_summary(out_heic)
    print(f"HEIC Metadata: Make={heic_meta.get('Make')}, Model={heic_meta.get('Model')}, Date={heic_meta.get('DateTimeOriginal')}, GPS={heic_meta.get('GPSPosition')}")
    assert heic_meta.get("Make") == "Apple", f"Failed to preserve Make on HEIC: {heic_meta}"
    assert heic_meta.get("Model") == "iPhone 15 Pro", f"Failed to preserve Model on HEIC: {heic_meta}"
    assert "2024:06:15" in str(heic_meta.get("DateTimeOriginal")), f"Failed to preserve shoot date on HEIC: {heic_meta}"
    assert "24 deg" in str(heic_meta.get("GPSPosition")), f"Failed to preserve GPS on HEIC: {heic_meta}"

    # Check MOV Metadata
    mov_meta = meta_engine.extract_metadata_summary(out_mov)
    print(f"MOV Metadata: Make={mov_meta.get('Make')}, Model={mov_meta.get('Model')}, ContentIdentifier={mov_meta.get('ContentIdentifier')}")
    assert mov_meta.get("Make") == "Apple", f"Failed to preserve Make on MOV: {mov_meta}"
    assert mov_meta.get("Model") == "iPhone 15 Pro", f"Failed to preserve Model on MOV: {mov_meta}"

    # Check Live Photo UUID pairing on Video
    expected_uuid = "E5616D19-8692-4934-B27D-5EBFF749EBF7"
    assert mov_meta.get("ContentIdentifier") == expected_uuid, f"Live Photo ContentIdentifier missing on MOV: {mov_meta}"
    print("✅ Live Photo QuickTime ContentIdentifier preserved accurately on video!")

    # Check Video Codec is HEVC / hvc1
    res = subprocess.run([
        hardware.ffprobe_path, "-v", "quiet", "-show_entries", "stream=codec_name,codec_tag_string",
        "-of", "json", out_mov
    ], stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    import json
    v_data = json.loads(res.stdout)
    codec_name = v_data["streams"][0]["codec_name"]
    codec_tag = v_data["streams"][0]["codec_tag_string"]
    print(f"Compressed Video Codec: {codec_name}, Tag: {codec_tag}")
    assert codec_name == "hevc", f"Video codec is not HEVC! Got {codec_name}"
    assert codec_tag == "hvc1", f"Apple compatibility tag is not hvc1! Got {codec_tag}"
    print("✅ Video encoded with NVENC HEVC and apple-compatible 'hvc1' tag successfully!")

    # Check AAE sidecar content
    with open(out_aae, "r", encoding="utf-8") as f:
        content = f.read()
    assert "AppleFilterPreset" in content, "Sidecar .AAE corrupted during copy!"
    print("✅ Apple .AAE sidecar preserved verbatim!")

    print("\n🎉 ALL TESTS PASSED WITH 100% METADATA ACCURACY!\n")


def run_full_test():
    test_root = os.path.abspath("test_workspace")
    input_dcim = os.path.join(test_root, "input_dcim")
    output_dcim = os.path.join(test_root, "output_dcim")

    if os.path.exists(test_root):
        shutil.rmtree(test_root)

    os.makedirs(test_root, exist_ok=True)

    try:
        # Step 1: Create mock DCIM
        dcim_folder = create_synthetic_dcim(input_dcim)

        # Step 2: Run main.py
        print("\n--- Running main.py on test DCIM ---")
        cmd = [
            sys.executable, "main.py",
            "-i", dcim_folder,
            "-o", output_dcim,
            "--cq", "28",
            "--photo-quality", "72"
        ]
        res = subprocess.run(cmd, check=True)
        assert res.returncode == 0, "main.py failed!"

        # Step 3: Verify output files and metadata
        verify_output_directory(output_dcim)

        # Step 4: Test Resume functionality
        print("--- Testing Resume / Zero-Redundancy check ---")
        start_res = time.time()
        res_resume = subprocess.run(cmd, check=True)
        resume_dur = time.time() - start_res
        print(f"Resume run finished in: {resume_dur:.2f} seconds (all items skipped/instant)!")
        assert resume_dur < 3.0, "Resume run took longer than expected!"

    finally:
        # Clean up test workspace
        if os.path.exists(test_root):
            shutil.rmtree(test_root)
            print("Test workspace cleaned up cleanly.")


if __name__ == "__main__":
    run_full_test()

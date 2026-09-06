import json
import os
import subprocess
import sys
import time
from typing import Optional, Dict, Any, List
from utils.logger import get_logger

logger = get_logger()

class MTPReader:
    """Automates direct discovery and file extraction from connected iPhone MTP devices via Windows Shell COM."""

    @staticmethod
    def detect_iphone() -> Optional[Dict[str, Any]]:
        """
        Detects if an Apple iPhone is currently connected via USB with an accessible DCIM folder.
        Returns device info dictionary or None.
        """
        ps_code = """
        $shell = New-Object -ComObject Shell.Application
        $thisPc = $shell.NameSpace(17)
        $iphone = $thisPc.Items() | Where-Object { $_.Name -like '*iPhone*' } | Select-Object -First 1
        if (-not $iphone) {
            Write-Output '{"connected": false}'
            exit 0
        }
        $storage = $iphone.GetFolder.Items() | Where-Object { $_.Name -like '*Internal Storage*' } | Select-Object -First 1
        if (-not $storage) {
            Write-Output '{"connected": false, "reason": "locked"}'
            exit 0
        }
        $dcim = $storage.GetFolder.Items() | Where-Object { $_.Name -eq 'DCIM' } | Select-Object -First 1
        if (-not $dcim) {
            Write-Output '{"connected": false, "reason": "no_dcim"}'
            exit 0
        }
        $folders = $dcim.GetFolder.Items()
        $totalFiles = 0
        foreach ($f in $folders) {
            $totalFiles += $f.GetFolder.Items().Count
        }
        $out = @{
            connected = $true
            device_name = $iphone.Name
            folders_count = $folders.Count
            total_files = $totalFiles
        }
        $out | ConvertTo-Json -Compress
        """
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_code],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20
            )
            if res.returncode == 0 and res.stdout.strip():
                for line in res.stdout.strip().splitlines():
                    if line.startswith("{"):
                        data = json.loads(line)
                        if data.get("connected"):
                            return data
        except Exception as e:
            logger.debug(f"MTP detection error: {e}")
        return None

    @staticmethod
    def extract_iphone_dcim(
        target_dir: str,
        progress_callback = None
    ) -> bool:
        """
        Extracts all folders and media from iPhone's Internal Storage\\DCIM directly into target_dir.
        """
        abs_target = os.path.abspath(target_dir)
        os.makedirs(abs_target, exist_ok=True)

        ps_script = f"""
        $shell = New-Object -ComObject Shell.Application
        $thisPc = $shell.NameSpace(17)
        $iphone = $thisPc.Items() | Where-Object {{ $_.Name -like '*iPhone*' }} | Select-Object -First 1
        if (-not $iphone) {{ exit 1 }}
        $storage = $iphone.GetFolder.Items() | Where-Object {{ $_.Name -like '*Internal Storage*' }} | Select-Object -First 1
        $dcim = $storage.GetFolder.Items() | Where-Object {{ $_.Name -eq 'DCIM' }} | Select-Object -First 1
        $folders = $dcim.GetFolder.Items()

        $targetPath = '{abs_target}'
        $targetCOM = $shell.NameSpace($targetPath)

        foreach ($f in $folders) {{
            Write-Output ("START_FOLDER:" + $f.Name)
            $targetCOM.CopyHere($f, 20)
            Write-Output ("DONE_FOLDER:" + $f.Name)
        }}
        """

        try:
            proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-Command", ps_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace"
            )

            for line in proc.stdout:
                line = line.strip()
                if line.startswith("DONE_FOLDER:") and progress_callback:
                    folder_name = line.split(":", 1)[1]
                    progress_callback(folder_name)

            proc.wait()
            return proc.returncode == 0
        except Exception as e:
            logger.error(f"Failed to extract files from iPhone MTP: {e}")
            return False

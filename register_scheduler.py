"""
Registers Windows Task Scheduler tasks for autonomous daily YouTube uploads:
1. Hourly catch-up task: runs automation.py --auto every hour.
2. Daily 6:00 AM fallback run.
"""
import os
import sys
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
python_exe = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
automation_py = os.path.join(ROOT, "automation.py")
bat_file = os.path.join(ROOT, "run_auto_catchup.bat")

print(f"Project directory : {ROOT}")
print(f"Python executable : {python_exe}")
print(f"Runner batch file : {bat_file}")

# schtasks /tr syntax when path contains spaces:
# Using cmd.exe /c \"path_to_bat\" or \"path\"
task_tr = f'"{bat_file}"'

# 1. Register Hourly Catchup (standard user privilege, no admin needed)
cmd1 = [
    "schtasks", "/create",
    "/tn", "YAAS_Hourly_YouTube_Catchup",
    "/tr", task_tr,
    "/sc", "hourly",
    "/mo", "1",
    "/f"
]
print("\nRegistering YAAS_Hourly_YouTube_Catchup...")
res1 = subprocess.run(cmd1, capture_output=True, text=True)
print("Output:", res1.stdout.strip())
if res1.stderr:
    print("Error:", res1.stderr.strip())

# 2. Register Daily 6 AM Fallback
cmd2 = [
    "schtasks", "/create",
    "/tn", "YAAS_Daily_YouTube_Studio",
    "/tr", task_tr,
    "/sc", "daily",
    "/st", "06:00",
    "/f"
]
print("\nRegistering YAAS_Daily_YouTube_Studio...")
res2 = subprocess.run(cmd2, capture_output=True, text=True)
print("Output:", res2.stdout.strip())
if res2.stderr:
    print("Error:", res2.stderr.strip())

if res1.returncode == 0 or res2.returncode == 0:
    print("\n[SUCCESS] Windows Task Scheduler configuration successful!")
else:
    print("\n[NOTICE] Task scheduler registration returned code", res1.returncode)

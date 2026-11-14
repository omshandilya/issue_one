#!/usr/bin/env python3
"""Packaging script for Orbit Portal (Ticket T7).
Produces a standalone, zero-installation package in `package/Orbit Portal/` under 300 MB.
Works on clean Windows 10/11 machines without admin rights, Python, or Node installed.
"""
import os
import shutil
import subprocess
import sys


def get_base_python_dir():
    # If running in venv, base_prefix points to the underlying Python installation
    prefix = getattr(sys, "base_prefix", sys.prefix)
    if os.path.exists(os.path.join(prefix, "python.exe")):
        return prefix
    # Fallback to local appdata python
    local_appdata = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python315")
    if os.path.exists(local_appdata):
        return local_appdata
    return prefix


def ignore_pycache(src, names):
    return [n for n in names if n in ("__pycache__", ".pytest_cache") or n.endswith(".pyc")]


def build_package():
    proj_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    out_dir = os.path.join(proj_dir, "package", "Orbit Portal")
    print(f"Building Orbit Portal package in: {out_dir}")

    if os.path.exists(out_dir):
        print("Cleaning previous package build...")
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    # 1. Build Frontend
    print("Building frontend assets (npm run build)...")
    web_dir = os.path.join(proj_dir, "web")
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    subprocess.run([npm_cmd, "run", "build"], cwd=web_dir, check=True)

    dest_web = os.path.join(out_dir, "web", "dist")
    os.makedirs(os.path.dirname(dest_web), exist_ok=True)
    shutil.copytree(os.path.join(web_dir, "dist"), dest_web)

    # 2. Copy Orbit Backend Code
    print("Copying backend source code...")
    shutil.copytree(
        os.path.join(proj_dir, "orbit"),
        os.path.join(out_dir, "orbit"),
        ignore=ignore_pycache
    )

    # 3. Assemble Portable Python Runtime
    base_py = get_base_python_dir()
    dest_py = os.path.join(out_dir, "python")
    print(f"Bundling portable Python runtime from {base_py}...")
    os.makedirs(dest_py, exist_ok=True)

    # Copy Python executables and root DLLs
    for fn in os.listdir(base_py):
        src_path = os.path.join(base_py, fn)
        if os.path.isfile(src_path) and (fn.endswith(".exe") or fn.endswith(".dll")):
            shutil.copy2(src_path, os.path.join(dest_py, fn))

    # Copy DLLs directory
    src_dlls = os.path.join(base_py, "DLLs")
    if os.path.exists(src_dlls):
        shutil.copytree(src_dlls, os.path.join(dest_py, "DLLs"), ignore=ignore_pycache)

    # Copy Lib directory (standard library, excluding bulky non-essential modules)
    src_lib = os.path.join(base_py, "Lib")
    dest_lib = os.path.join(dest_py, "Lib")
    os.makedirs(dest_lib, exist_ok=True)

    def lib_ignore(src, names):
        ignored = [n for n in names if n in ("__pycache__", "site-packages", "test", "idlelib", "tkinter", "turtledemo") or n.endswith(".pyc")]
        return ignored

    for item in os.listdir(src_lib):
        if item in ("site-packages", "test", "idlelib", "tkinter", "turtledemo", "__pycache__"):
            continue
        s = os.path.join(src_lib, item)
        d = os.path.join(dest_lib, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, ignore=ignore_pycache)
        else:
            shutil.copy2(s, d)

    # Copy site-packages from .venv
    venv_site = os.path.join(proj_dir, ".venv", "Lib", "site-packages")
    dest_site = os.path.join(dest_lib, "site-packages")
    os.makedirs(dest_site, exist_ok=True)

    if os.path.exists(venv_site):
        print("Copying installed site-packages from virtual environment...")
        for item in os.listdir(venv_site):
            # Skip pytest, pip, setuptools, dist-info to save space
            if any(item.startswith(prefix) for prefix in ("pytest", "pip", "_pytest")):
                continue
            s = os.path.join(venv_site, item)
            d = os.path.join(dest_site, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, ignore=ignore_pycache)
            else:
                shutil.copy2(s, d)

    # 4. Seed Demo Data
    print("Preparing demo data and catalog...")
    dest_data = os.path.join(out_dir, "data")
    os.makedirs(os.path.join(dest_data, "files"), exist_ok=True)

    # Copy seed catalog and small demo files
    src_data = os.path.join(proj_dir, "data")
    if os.path.exists(os.path.join(src_data, "catalog.db")):
        shutil.copy2(os.path.join(src_data, "catalog.db"), os.path.join(dest_data, "catalog.db"))
    else:
        # Run seeder if catalog not present
        from orbit.catalog import seed
        seed.seed(os.path.join(dest_data, "catalog.db"), os.path.join(dest_data, "files"))

    # Copy demo scene files (keep under 300MB by copying small scenes and seed files)
    src_files = os.path.join(src_data, "files")
    if os.path.exists(src_files):
        for fn in os.listdir(src_files):
            # Copy small scenes
            if "small" in fn or fn.endswith(".bin"):
                s_fp = os.path.join(src_files, fn)
                # If file is under 50 MB, copy it
                if os.path.getsize(s_fp) < 50 * 1024 * 1024:
                    shutil.copy2(s_fp, os.path.join(dest_data, "files", fn))

    # 5. Create start.bat
    print("Writing start.bat...")
    start_bat_content = """@echo off
setlocal
cd /d "%~dp0"
title Orbit Portal
echo ===================================================
echo             Orbit Portal (Field Edition)
echo ===================================================
echo Starting Orbit Portal services... Please wait.
echo.
python\\python.exe launch.py
if errorlevel 1 (
    echo.
    echo An error occurred while running Orbit Portal.
    pause
)
"""
    with open(os.path.join(out_dir, "start.bat"), "w", newline="\r\n") as f:
        f.write(start_bat_content)

    # 6. Create launch.py
    print("Writing launch.py orchestrator...")
    launch_py_content = '''"""Orchestrator for standalone Orbit Portal package.
Handles:
- Dynamic port detection if default ports are busy.
- Process lifecycle management (Job Object ensures closing console stops all services).
- Automatic browser launch.
- Clean stop via Ctrl+C or console close.
"""
import ctypes
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from ctypes import wintypes


def setup_windows_job():
    """Binds all child processes to a Windows Job Object so they terminate automatically on exit."""
    if sys.platform != "win32":
        return None
    try:
        kernel32 = ctypes.windll.kernel32
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return None

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [("ReadOperationCount", ctypes.c_uint64),
                        ("WriteOperationCount", ctypes.c_uint64),
                        ("OtherOperationCount", ctypes.c_uint64),
                        ("ReadTransferCount", ctypes.c_uint64),
                        ("WriteTransferCount", ctypes.c_uint64),
                        ("OtherTransferCount", ctypes.c_uint64)]

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                        ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t),
                        ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                        ("IoInfo", IO_COUNTERS),
                        ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryLimit", ctypes.c_size_t),
                        ("PeakJobMemoryLimit", ctypes.c_size_t)]

        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        kernel32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))
        kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess())
        return job
    except Exception:
        return None


def find_free_port(preferred):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]


def main():
    setup_windows_job()

    root_dir = os.path.abspath(os.path.dirname(__file__))
    python_exe = os.path.join(root_dir, "python", "python.exe")
    if not os.path.exists(python_exe):
        python_exe = sys.executable

    gateway_port = find_free_port(8000)
    catalog_port = find_free_port(8001 if gateway_port != 8001 else 8005)
    tiles_port = find_free_port(8002 if gateway_port != 8002 and catalog_port != 8002 else 8006)

    env = os.environ.copy()
    env["PYTHONPATH"] = root_dir
    env["ORBIT_DATA_DIR"] = os.path.join(root_dir, "data")
    env["ORBIT_WEB_DIR"] = os.path.join(root_dir, "web", "dist")
    env["ORBIT_GATEWAY_PORT"] = str(gateway_port)
    env["ORBIT_CATALOG_PORT"] = str(catalog_port)
    env["ORBIT_TILES_PORT"] = str(tiles_port)
    env["ORBIT_CATALOG_URL"] = f"http://127.0.0.1:{catalog_port}"
    env["ORBIT_TILES_URL"] = f"http://127.0.0.1:{tiles_port}"

    processes = []

    def cleanup():
        print("\\nStopping all Orbit Portal services...")
        for p in processes:
            try:
                p.terminate()
                p.wait(timeout=2)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        print("All services stopped.")

    try:
        # 1. Start Catalog service
        p_catalog = subprocess.Popen(
            [python_exe, "-m", "uvicorn", "orbit.catalog.app:app", "--port", str(catalog_port), "--host", "127.0.0.1"],
            cwd=root_dir, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        processes.append(p_catalog)

        # 2. Start Tiles service
        p_tiles = subprocess.Popen(
            [python_exe, "-m", "uvicorn", "orbit.tiles.app:app", "--port", str(tiles_port), "--host", "127.0.0.1"],
            cwd=root_dir, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        processes.append(p_tiles)

        # 3. Start Gateway service
        p_gateway = subprocess.Popen(
            [python_exe, "-m", "uvicorn", "orbit.gateway.app:app", "--port", str(gateway_port), "--host", "127.0.0.1"],
            cwd=root_dir, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        processes.append(p_gateway)

        # Wait for Gateway to be ready
        gateway_url = f"http://127.0.0.1:{gateway_port}"
        ready = False
        for _ in range(30):
            try:
                with urllib.request.urlopen(f"{gateway_url}/health", timeout=1) as resp:
                    if resp.status == 200:
                        ready = True
                        break
            except Exception:
                time.sleep(0.5)

        if not ready:
            print("Error: Services took too long to start.")
            cleanup()
            sys.exit(1)

        print("---------------------------------------------------")
        print(f" Orbit Portal is running at: {gateway_url}")
        print("---------------------------------------------------")
        print(" Opening web portal in your default browser...")
        print(" Close this window or press Ctrl+C to STOP the portal.")
        print("---------------------------------------------------")

        webbrowser.open(gateway_url)

        # Keep running until interrupted
        while True:
            time.sleep(1)
            for p in processes:
                if p.poll() is not None:
                    print("Notice: A background service terminated unexpectedly.")
                    cleanup()
                    return

    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        cleanup()


if __name__ == "__main__":
    main()
'''
    with open(os.path.join(out_dir, "launch.py"), "w", newline="\r\n") as f:
        f.write(launch_py_content)

    # 7. Create README.txt
    print("Writing README.txt...")
    readme_content = """Orbit Portal - Field Edition
===========================

HOW TO START:
1. Double-click "start.bat" in this folder.
2. A command window will open, and Orbit Portal will launch in your default web browser.
3. If Windows shows an "Unrecognised app" warning, click "More info" and then "Run anyway" (this only happens once).

HOW TO STOP:
- Simply close the command window, or press Ctrl+C inside the command window.
- All background services stop automatically when the window is closed.

OFFLINE USAGE:
- The portal works completely offline. If there is no internet connection, the background world map tiles may not appear, but searching, viewing scenes, drawing search boxes/polygons, and downloading scene files will work normally.

TROUBLESHOOTING:
- If the browser does not open automatically, look at the command window for the address (e.g. http://127.0.0.1:8000) and open it manually in Chrome, Edge, or Firefox.
- If port 8000 is used by another application, Orbit Portal will automatically pick an alternative free port.
"""
    with open(os.path.join(out_dir, "README.txt"), "w", newline="\r\n") as f:
        f.write(readme_content)

    # 8. Measure Package Size
    total_bytes = 0
    for root, dirs, files in os.walk(out_dir):
        for f in files:
            fp = os.path.join(root, f)
            total_bytes += os.path.getsize(fp)

    mb = total_bytes / (1024 * 1024)
    print(f"\nPackage build complete!")
    print(f"Location: {out_dir}")
    print(f"Total package size: {mb:.1f} MB (Limit: 300 MB)")
    assert mb < 300, f"Package exceeded 300 MB limit: {mb:.1f} MB"


if __name__ == "__main__":
    build_package()


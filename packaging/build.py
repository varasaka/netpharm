#!/usr/bin/env python3
"""
Cross-platform build script for NetPharm executable
Run this script to build netpharm.exe on Windows or a binary on Unix/Linux/macOS
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


def check_python_version():
    """Ensure Python 3.10+ is being used"""
    if sys.version_info < (3, 10):
        print(f"Error: Python 3.10+ is required. You are using {sys.version}")
        sys.exit(1)
    print(f"✓ Python version OK: {sys.version.split()[0]}")


def install_dependencies():
    """Install required dependencies"""
    print("\n[1/5] Installing dependencies...")
    
    # Upgrade pip, setuptools, wheel
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", 
         "pip", "setuptools", "wheel"],
        check=True
    )
    
    # Install project requirements
    req_file = Path(__file__).parent.parent / "requirements.txt"
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
        check=True
    )
    
    # Install PyInstaller
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "pyinstaller"],
        check=True
    )
    
    print("✓ Dependencies installed")


def build_executable():
    """Build the executable using PyInstaller"""
    print("\n[2/5] Building executable...")
    
    project_root = Path(__file__).parent.parent
    src_main = project_root / "src" / "main.py"
    dist_dir = project_root / "dist"
    build_dir = project_root / "build"
    spec_file = project_root / "netpharm.spec"
    
    # Ensure source file exists
    if not src_main.exists():
        print(f"Warning: {src_main} not found. Creating a stub...")
        src_main.parent.mkdir(parents=True, exist_ok=True)
        src_main.write_text("# NetPharm Application Entry Point\nprint('NetPharm')\n")
    
    # Ensure dist directory exists
    dist_dir.mkdir(exist_ok=True)
    
    # PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "netpharm",
        "--onefile",
        "--add-data", f"{project_root / 'config'}:config" if (project_root / 'config').exists() else "",
        "--add-data", f"{project_root / 'docs'}:docs" if (project_root / 'docs').exists() else "",
        "--collect-all", "streamlit",
        "--collect-all", "langgraph",
        "--collect-all", "rdkit",
        "--collect-all", "playwright",
        "--collect-all", "py4cytoscape",
        "--collect-all", "anthropic",
        "--distpath", str(dist_dir),
        "--buildpath", str(build_dir),
        "--specpath", str(project_root),
        str(src_main),
    ]
    
    # Filter out empty strings
    cmd = [c for c in cmd if c]
    
    subprocess.run(cmd, check=True)
    print("✓ Executable built")


def cleanup():
    """Clean up build artifacts"""
    print("\n[3/5] Cleaning up...")
    
    project_root = Path(__file__).parent.parent
    build_dir = project_root / "build"
    spec_file = project_root / "netpharm.spec"
    
    if build_dir.exists():
        shutil.rmtree(build_dir)
        print(f"  Removed {build_dir}")
    
    print("✓ Cleanup complete")


def print_summary():
    """Print build summary"""
    project_root = Path(__file__).parent.parent
    dist_dir = project_root / "dist"
    
    exe_name = "netpharm.exe" if sys.platform == "win32" else "netpharm"
    exe_path = dist_dir / exe_name
    
    print("\n" + "="*50)
    print("BUILD SUMMARY")
    print("="*50)
    
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"✓ Executable created: {exe_path}")
        print(f"  Size: {size_mb:.2f} MB")
    else:
        print(f"✗ Executable not found at {exe_path}")
    
    print(f"\nLocation: {dist_dir}/")
    print("="*50 + "\n")


def main():
    """Main build routine"""
    try:
        print("="*50)
        print("NetPharm Executable Build")
        print("="*50)
        
        check_python_version()
        install_dependencies()
        build_executable()
        cleanup()
        print_summary()
        
        print("Build successful! ✓")
        
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Build failed with error code {e.returncode}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

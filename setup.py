#!/usr/bin/env python3
"""
setup.py
One-click setup script for Meeting Intelligence Application.
Run: python setup.py
"""

import os
import sys
import subprocess
import platform

def run(cmd, check=True, shell=True):
    print(f"\n>>> {cmd}")
    result = subprocess.run(cmd, shell=shell, check=check, capture_output=False)
    return result.returncode == 0

def main():
    print("""
╔══════════════════════════════════════════════════════╗
║     Meeting Intelligence — Setup Script              ║
╚══════════════════════════════════════════════════════╝
    """)

    # Check Python version
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print(f"❌ Python 3.10+ required. You have {version.major}.{version.minor}")
        sys.exit(1)
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")

    # Check ffmpeg
    ffmpeg_ok = run("ffmpeg -version", check=False)
    if not ffmpeg_ok:
        print("\n⚠️  ffmpeg not found. Install it:")
        system = platform.system()
        if system == "Darwin":
            print("   brew install ffmpeg")
        elif system == "Linux":
            print("   sudo apt install ffmpeg  (Ubuntu/Debian)")
            print("   sudo dnf install ffmpeg  (Fedora)")
        elif system == "Windows":
            print("   Download from https://ffmpeg.org/download.html")
            print("   Add to PATH after installation")
        print("\nPlease install ffmpeg and re-run setup.py")
        sys.exit(1)
    print("✅ ffmpeg found")

    # Install Python dependencies
    print("\n📦 Installing Python packages (this may take a few minutes)...")
    run(f"{sys.executable} -m pip install --upgrade pip")
    run(f"{sys.executable} -m pip install -r requirements.txt")

    # Download spaCy English model (optional, for enhanced NLP)
    print("\n🧠 Downloading spaCy language model...")
    run(f"{sys.executable} -m spacy download en_core_web_sm", check=False)

    # Initialize the database
    print("\n🗄  Initializing SQLite database...")
    sys.path.insert(0, os.path.dirname(__file__))
    from database.db import init_db
    init_db()

    # Create uploads directory if needed
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("database", exist_ok=True)

    print("""
╔══════════════════════════════════════════════════════╗
║  ✅ Setup Complete!                                   ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  To start the application:                           ║
║    python app.py                                     ║
║                                                      ║
║  Then open in browser:                               ║
║    http://localhost:8000                             ║
║                                                      ║
║  API documentation:                                  ║
║    http://localhost:8000/docs                        ║
╚══════════════════════════════════════════════════════╝
    """)

if __name__ == "__main__":
    main()

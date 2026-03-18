"""
Run the Streamlit frontend.

Usage:
    streamlit run frontend/app.py

Or:
    python run_frontend.py
"""

import subprocess
import sys
import os

if __name__ == "__main__":
    project_dir = os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(project_dir, "frontend", "app.py")

    print("Starting Streamlit frontend...")
    print("Open http://localhost:8501 in your browser")

    subprocess.run([
        sys.executable, "-m", "streamlit", "run", app_path,
        "--server.port", "8501",
        "--server.headless", "true",
    ])

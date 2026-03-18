"""
Run the FastAPI server.

Usage:
    python run_api.py

The server starts on http://localhost:8000 by default.
API docs at http://localhost:8000/docs
"""

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    import uvicorn
    from core.config import API_HOST, API_PORT

    print(f"Starting Invoice Extraction API on http://{API_HOST}:{API_PORT}")
    print(f"API docs: http://localhost:{API_PORT}/docs")
    print(f"Health check: http://localhost:{API_PORT}/health")

    uvicorn.run(
        "api.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=True,
    )

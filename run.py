

import os
import sys
import argparse
import logging
import subprocess
import webbrowser
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

def run_api(host="127.0.0.1", port=8000, reload=True):
    
    try:
        cmd = [
            sys.executable, "-m", "uvicorn", "main:app",
            "--host", host,
            "--port", str(port)
        ]
        
        if reload:
            cmd.append("--reload")
        
        
        logger.info(f"Starting API server on http://{host}:{port}")
        
        
        subprocess.run(cmd, cwd=PROJECT_DIR)
    
    except KeyboardInterrupt:
        logger.info("API server stopped by user")
    
    except Exception as e:
        logger.error(f"Error starting API server: {str(e)}")

def open_browser(url):
    
    try:
        webbrowser.open(url)
    except Exception as e:
        logger.error(f"Error opening browser: {str(e)}")

def install_dependencies():
    
    try:
        requirements_path = os.path.join(PROJECT_DIR, "requirements.txt")
        
        if os.path.exists(requirements_path):
            logger.info("Installing dependencies...")
            
            cmd = [sys.executable, "-m", "pip", "install", "-r", requirements_path]
            subprocess.run(cmd, check=True)
            
            logger.info("Dependencies installed successfully")
        else:
            logger.error("Requirements file not found")
    
    except Exception as e:
        logger.error(f"Error installing dependencies: {str(e)}")

def init_playwright():
    
    try:
        logger.info("Installing Playwright browsers...")
        
        cmd = [sys.executable, "-m", "playwright", "install"]
        subprocess.run(cmd, check=True)
        
        logger.info("Playwright browsers installed successfully")
    
    except Exception as e:
        logger.error(f"Error installing Playwright browsers: {str(e)}")

def setup_project():
    
    
    install_dependencies()
    
    
    init_playwright()
    
    
    os.makedirs(os.path.join(PROJECT_DIR, "data"), exist_ok=True)
    os.makedirs(os.path.join(PROJECT_DIR, "logs"), exist_ok=True)

def main():
    
    parser = argparse.ArgumentParser(description="Microsoft Key Checker CLI")
    
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    
    api_parser = subparsers.add_parser("api", help="Start API server")
    api_parser.add_argument("--host", default="127.0.0.1", help="Host to bind the server to")
    api_parser.add_argument("--port", type=int, default=8000, help="Port to bind the server to")
    api_parser.add_argument("--no-reload", action="store_true", help="Disable auto-reload")
    api_parser.add_argument("--open-browser", action="store_true", help="Open browser after server start")
    
    
    setup_parser = subparsers.add_parser("setup", help="Setup project for first use")
    
    
    args = parser.parse_args()
    
    
    if args.command == "api":
        if args.open_browser:
            
            url = f"http://{args.host}:{args.port}/docs"
            logger.info(f"Opening browser at {url}")
            
            
            import threading
            threading.Timer(2.0, open_browser, args=[url]).start()
        
        
        run_api(host=args.host, port=args.port, reload=not args.no_reload)
    
    elif args.command == "setup":
        setup_project()
    
    else:
        
        parser.print_help()

if __name__ == "__main__":
    main() 
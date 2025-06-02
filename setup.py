#!/usr/bin/env python3
"""Setup script for Universal Cross-Reference MCP Server development environment."""

import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd: str, description: str) -> bool:
    """Run a command and print status."""
    print(f"🔨 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
            return True
        else:
            print(f"❌ {description} failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ {description} failed: {e}")
        return False


def main():
    """Main setup function."""
    print("🚀 Setting up Universal Cross-Reference MCP Server development environment")
    
    # Check Python version
    if sys.version_info < (3, 11):
        print("❌ Python 3.11+ is required")
        sys.exit(1)
    
    print(f"✅ Python {sys.version} detected")
    
    # Create virtual environment if it doesn't exist
    if not Path("venv").exists():
        if not run_command("python -m venv venv", "Creating virtual environment"):
            sys.exit(1)
    
    # Determine activation script
    if os.name == 'nt':  # Windows
        activate_script = "venv\\Scripts\\activate"
        pip_cmd = "venv\\Scripts\\pip"
    else:  # Unix/Linux/MacOS
        activate_script = "source venv/bin/activate"
        pip_cmd = "venv/bin/pip"
    
    # Upgrade pip
    if not run_command(f"{pip_cmd} install --upgrade pip", "Upgrading pip"):
        sys.exit(1)
    
    # Install dependencies
    if not run_command(f"{pip_cmd} install -r requirements.txt", "Installing dependencies"):
        sys.exit(1)
    
    # Install development dependencies
    if not run_command(f"{pip_cmd} install -e .[dev]", "Installing development dependencies"):
        sys.exit(1)
    
    # Create .env file if it doesn't exist
    if not Path(".env").exists():
        if run_command("cp env.example .env", "Creating .env file"):
            print("📝 Please edit .env file with your configuration")
    
    print("\n🎉 Setup completed successfully!")
    print("\nNext steps:")
    print(f"1. Activate virtual environment: {activate_script}")
    print("2. Edit .env file with your configuration")
    print("3. Set up PostgreSQL database")
    print("4. Run: python -m src.database.init_db")
    print("5. Start development: python -m src.mcp_server.main")


if __name__ == "__main__":
    main() 
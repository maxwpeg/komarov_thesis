"""
Quick start script to initialize and run the Floor Plan Management System.
"""
import subprocess
import sys
import os

def check_python_version():
    """Check if Python version is 3.10+"""
    if sys.version_info < (3, 10):
        print("❌ Python 3.10 or higher is required")
        print(f"   Current version: {sys.version}")
        return False
    print(f"✓ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    return True

def install_backend_dependencies():
    """Install Python dependencies"""
    print("\n📦 Installing backend dependencies...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", 
            "backend/requirements.txt"
        ])
        print("✓ Backend dependencies installed")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install backend dependencies")
        return False

def initialize_database():
    """Initialize the database"""
    print("\n🗄️  Initializing database...")
    try:
        from backend.database import init_db
        init_db()
        print("✓ Database initialized")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")
        return False

def check_tesseract():
    """Check if Tesseract is installed"""
    print("\n🔍 Checking for Tesseract OCR...")
    try:
        result = subprocess.run(
            ["tesseract", "--version"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("✓ Tesseract OCR is installed")
            return True
    except FileNotFoundError:
        pass
    
    print("⚠️  Tesseract OCR not found")
    print("   Download from: https://github.com/UB-Mannheim/tesseract/wiki")
    print("   After installation, update backend/image_processor.py with the path")
    return False

def install_frontend_dependencies():
    """Install Node.js dependencies"""
    print("\n📦 Installing frontend dependencies...")
    try:
        subprocess.check_call(
            ["npm", "install"],
            cwd="floorplan-ui"
        )
        print("✓ Frontend dependencies installed")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  Could not install frontend dependencies")
        print("   Make sure Node.js is installed")
        print("   Run 'npm install' manually in floorplan-ui directory")
        return False

def create_directories():
    """Create necessary directories"""
    print("\n📁 Creating directories...")
    directories = ["uploads", "outputs"]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✓ Created {directory}/")
    return True

def print_instructions():
    """Print final instructions"""
    print("\n" + "="*60)
    print("🎉 Setup Complete!")
    print("="*60)
    print("\nTo start the application:\n")
    print("1. Start the backend server:")
    print("   python main.py")
    print("\n2. In a new terminal, start the frontend:")
    print("   cd floorplan-ui")
    print("   npm start")
    print("\n3. Open your browser to:")
    print("   http://localhost:3000")
    print("\n4. API documentation available at:")
    print("   http://localhost:8000/docs")
    print("\n" + "="*60)

def main():
    """Main setup function"""
    print("🚀 Floor Plan Management System - Setup Script")
    print("="*60)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Create directories
    create_directories()
    
    # Install backend dependencies
    if not install_backend_dependencies():
        print("\n⚠️  Backend setup incomplete, but you can continue manually")
    
    # Initialize database
    try:
        initialize_database()
    except Exception as e:
        print(f"⚠️  Could not initialize database: {e}")
    
    # Check Tesseract
    check_tesseract()
    
    # Install frontend dependencies
    install_frontend_dependencies()
    
    # Print instructions
    print_instructions()

if __name__ == "__main__":
    main()

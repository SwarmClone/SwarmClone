import configparser
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

# Constants
MODULE_EXTENSION_MAP = {
    "Windows": ".pyd",
    "Darwin": ".so",
    "Linux": ".so"
}
EXCLUDE_PATTERNS = [
    '__pycache__', '*.pyc', '*.pyo', '*.pyd', '*.so',
    'build', 'dist', '*.egg-info', '.eggs', '.tox',
    '.pytest_cache', '.coverage', 'htmlcov', '.mypy_cache'
]
CLEAN_PATTERNS = [
    '**/__pycache__',
    '**/*.egg-info',
    '**/*.py',
    '**/*.pyc',
    '**/*.pyo',
    '**/build',
    '**/dist',
    '**/.eggs',
    '**/.tox'
]
HIDDEN_IMPORTS = [
    'framework', 'modules', 'ruamel.yaml', 'fastapi', 'uvicorn',
    'pydantic', 'asyncio', 'multiprocessing', 'typing_extensions'
]
SKIP_FILES = ['__init__.py', 'setup.py']

class BuildError(Exception):
    """Custom exception for build failures"""
    pass

class BuildConfig:
    """Configuration for the build process"""
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.src_modules = project_root / "src" / "modules"
        self.dist_dir = project_root / "dist"
        self.build_temp = project_root / "build" / "temp"
        self.pyinstaller_build = project_root / "build" / "pyinstaller"
        self.main_py = project_root / "src" / "main.py"
        self.spec_file = project_root / "backend.spec"
        self.system = platform.system()
        self.module_extension = self._get_module_extension()
    
    def _get_module_extension(self) -> str:
        """Get compiled module extension based on platform"""
        return MODULE_EXTENSION_MAP.get(self.system, ".so")

class BuildLogger:
    """Centralized logging configuration"""
    def __init__(self):
        self.logger = logging.getLogger("build")
        self.logger.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(console_handler)
    
    def info(self, message: str):
        self.logger.info(message)
    
    def warning(self, message: str):
        self.logger.warning(message)
    
    def error(self, message: str):
        self.logger.error(message)
    
    def success(self, message: str):
        self.logger.info(f"✅ {message}")
    
    def failure(self, message: str):
        self.logger.error(f"❌ {message}")
    
    def step(self, message: str):
        self.logger.info(f"\n🔧 {message}")
        self.logger.info("-" * 40)

@contextmanager
def temporary_build_directory():
    """Context manager for temporary build directory"""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        yield temp_dir
    finally:
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            logging.getLogger("build").warning(f"Failed to clean temporary directory: {e}")

def get_module_extension() -> str:
    """Get compiled module extension based on platform"""
    system = platform.system()
    if system == "Windows":
        return ".pyd"
    elif system == "Darwin":  # macOS
        return ".so"
    else:  # Linux and others
        return ".so"

def setup_build_environment(config: BuildConfig) -> Path:
    """Setup build environment in project_root/build/temp"""
    build_temp = config.build_temp
    
    # Clean and create build directories
    if build_temp.exists():
        shutil.rmtree(build_temp, ignore_errors=True)
    
    build_temp.mkdir(parents=True, exist_ok=True)
    
    print(f"📁 Build temporary directory: {build_temp}")
    return build_temp

def copy_modules_to_build(src_modules: Path, build_temp: Path) -> Path:
    """Copy modules directory to build temp directory"""
    build_modules = build_temp / "modules"
    
    if build_modules.exists():
        shutil.rmtree(build_modules)
    
    # Copy everything except build artifacts
    exclude_patterns = EXCLUDE_PATTERNS.copy()
    
    def ignore_patterns(directory, names):
        ignored = []
        for pattern in exclude_patterns:
            for name in names:
                if pattern.startswith('*'):
                    if name.endswith(pattern[1:]):
                        ignored.append(name)
                elif pattern in name:
                    ignored.append(name)
        return list(set(ignored))
    
    shutil.copytree(src_modules, build_modules, ignore=ignore_patterns)
    
    print(f"📁 Copied modules to build directory: {build_modules}")
    return build_modules

def compile_python_file(py_file: Path, output_file: Path, extension: str) -> bool:
    """Compile a single Python file using Cython"""
    try:
        # Create a proper module name for the extension
        module_name = py_file.stem
        
        py_file_path = str(py_file.absolute()).replace('\\', '/')
        output_file_path = str(output_file.absolute()).replace('\\', '/')
        
        setup_content = f"""# -*- coding: utf-8 -*-
from Cython.Build import cythonize
from setuptools import setup
from setuptools.extension import Extension
import os
import sys

# Ensure the output directory exists
os.makedirs(os.path.dirname(r'{output_file_path}'), exist_ok=True)

ext = Extension(
    name='{module_name}',
    sources=[r'{py_file_path}'],
    language='c',
    define_macros=[('CYTHON_LIMITED_API', '1')]
)

setup(
    ext_modules=cythonize(
        ext,
        compiler_directives={{
            'language_level': 3,
            'boundscheck': False,
            'wraparound': False,
            'cdivision': True,
            'initializedcheck': False,
            'nonecheck': False,
            'optimize.use_switch': True,
            'optimize.unpack_method_calls': True
        }},
        force=True,
        quiet=True
    ),
    script_args=['build_ext', '--inplace', '--build-lib', r'{py_file.parent.absolute()}']
)
"""
        
        # Create temporary directory for compilation
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            setup_file = temp_path / "setup.py"
            
            with open(setup_file, 'w', encoding='utf-8') as f:
                f.write(setup_content)
            
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONUTF8'] = '1'
            
            result = subprocess.run(
                [sys.executable, str(setup_file), "build_ext", "--inplace"],
                cwd=temp_path,
                capture_output=True,
                text=True,
                timeout=60,
                encoding='utf-8',
                errors='replace',
                env=env
            )
            
            if result.returncode != 0:
                print(f"  ❌ Compilation failed: {py_file.name}")
                if result.stderr:
                    error_lines = result.stderr.split('\n')
                    for line in error_lines[-5:]:  # Show last 5 error lines
                        if line.strip() and len(line) < 200:
                            print(f"     {line}")
                return False
            
            # Look for compiled file in the temp directory
            compiled_file = None
            for file in temp_path.glob(f"*{extension}"):
                if file.is_file():
                    compiled_file = file
                    break
            
            # Also look in the source directory where the file should be built
            if not compiled_file:
                source_dir = py_file.parent
                for file in source_dir.glob(f"*{extension}"):
                    if file.is_file() and file.stem == module_name:
                        compiled_file = file
                        break
            
            if compiled_file and compiled_file.exists():
                # Ensure output directory exists
                output_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy compiled file to output location
                shutil.copy2(compiled_file, output_file)
                
                # Try to clean up the compiled file from source directory
                if compiled_file.parent != output_file.parent:
                    try:
                        compiled_file.unlink()
                    except:
                        pass
                
                return True
        
        return False
        
    except subprocess.TimeoutExpired:
        print(f"  ⏰ Compilation timeout: {py_file.name}")
        return False
    except Exception as e:
        print(f"  ❌ Compilation exception: {py_file.name} - {str(e)[:100]}")
        return False

def compile_module_in_build(build_module_dir: Path, extension: str) -> int:
    """Compile all Python files in a build module directory"""
    print(f"  📄 Searching for Python files...")
    
    # First, read module.ini to know the entry point
    ini_path = build_module_dir / "module.ini"
    entry_file = None
    if ini_path.exists():
        try:
            config = configparser.ConfigParser()
            config.read(ini_path, encoding='utf-8')
            if 'module' in config:
                entry = config['module'].get('entry', '')
                if entry:
                    entry = entry.strip().strip('"').strip("'")
                    if entry.endswith('.py'):
                        entry_file = build_module_dir / entry
        except Exception as e:
            print(f"  ⚠️  Failed to read module.ini: {e}")
            pass
    
    # Find all Python files
    python_files = []
    for py_file in build_module_dir.rglob("*.py"):
        # Skip certain files
        if py_file.name in SKIP_FILES:
            continue
        # Don't skip test files that are the entry point
        if 'test' in py_file.name.lower() and py_file != entry_file:
            continue
        python_files.append(py_file)
    
    if not python_files:
        print(f"  ℹ️  No compilable Python files found")
        return 0
    
    print(f"  📊 Found {len(python_files)} Python files")
    
    # Compile each file
    success_count = 0
    for py_file in python_files:
        relative_path = py_file.relative_to(build_module_dir)
        print(f"  🔨 Compiling: {relative_path}")
        
        # Determine output path (same directory, different extension)
        output_file = py_file.parent / f"{py_file.stem}{extension}"
        
        if compile_python_file(py_file, output_file, extension):
            success_count += 1
            # Remove source .py file after successful compilation
            try:
                py_file.unlink()
                # Remove empty parent directories
                parent = py_file.parent
                while parent != build_module_dir and not any(parent.iterdir()):
                    try:
                        parent.rmdir()
                        parent = parent.parent
                    except:
                        break
            except:
                pass
    
    return success_count

def update_module_ini_in_build(build_module_dir: Path, extension: str) -> bool:
    """Update module.ini in build directory to point to compiled files"""
    ini_path = build_module_dir / "module.ini"
    if not ini_path.exists():
        print(f"  ❌ Missing module.ini")
        return False
    
    try:
        config = configparser.ConfigParser()
        config.read(ini_path, encoding='utf-8')
        
        if 'module' not in config:
            print(f"  ❌ module.ini format error: Missing [module] section")
            return False
        
        entry = config['module'].get('entry', '')
        if not entry:
            print(f"  ❌ module.ini missing entry field")
            return False
        
        # Clean entry value
        entry = entry.strip().strip('"').strip("'")
        
        # If entry is already a compiled file, leave it as is
        if entry.endswith(('.pyd', '.so')):
            # Check if the compiled file exists
            compiled_file = build_module_dir / entry
            if compiled_file.exists():
                print(f"  ℹ️  Entry is already compiled file: {entry}")
                return True
            else:
                print(f"  ⚠️  Compiled file does not exist: {entry}")
                return False
        
        # Update to compiled extension
        if entry.endswith('.py'):
            base_name = entry[:-3]
            new_entry = f"{base_name}{extension}"
        else:
            # If entry doesn't have .py extension, add compiled extension
            base_name = entry
            new_entry = f"{entry}{extension}"
        
        # Check if compiled file exists
        compiled_file = build_module_dir / new_entry
        if compiled_file.exists():
            config['module']['entry'] = new_entry
            with open(ini_path, 'w', encoding='utf-8') as f:
                config.write(f)
            print(f"  📝 Updated entry: {entry} -> {new_entry}")
            return True
        else:
            # Try to find the compiled file in subdirectories
            search_patterns = [
                f"**/{base_name}{extension}",
                f"**/{base_name}*.{extension.lstrip('.')}"
            ]
            
            for pattern in search_patterns:
                matches = list(build_module_dir.glob(pattern))
                if matches:
                    # Use the first match
                    compiled_match = matches[0]
                    relative_path = compiled_match.relative_to(build_module_dir)
                    config['module']['entry'] = str(relative_path)
                    with open(ini_path, 'w', encoding='utf-8') as f:
                        config.write(f)
                    print(f"  📝 Updated entry: {entry} -> {relative_path}")
                    return True
            
            # If we can't find the compiled file, check if we should keep the .py entry
            # (maybe the file wasn't meant to be compiled)
            original_py_file = build_module_dir / f"{base_name}.py"
            if original_py_file.exists():
                print(f"  ℹ️  Keeping original entry: {entry} (file exists but not compiled)")
                return True
            else:
                print(f"  ⚠️  File does not exist and not compiled: {base_name}")
                return False
            
    except Exception as e:
        print(f"  ❌ Failed to update module.ini: {e}")
        return False

def clean_build_module_directory(build_module_dir: Path, extension: str):
    """Clean build module directory to only keep necessary files"""
    print(f"  🧹 Cleaning build files...")
    
    # First pass: remove all .py files except those we want to keep
    for py_file in build_module_dir.rglob("*.py"):
        if py_file.name not in ['__init__.py', 'module.ini']:
            try:
                if py_file.exists():
                    py_file.unlink()
            except:
                pass
    
    # Second pass: remove build artifacts
    artifacts = ['*.c', '*.pyc', '*.pyo', 'build', 'dist', '*.egg-info', '__pycache__', 'setup.py']
    for artifact in artifacts:
        for path in build_module_dir.rglob(artifact):
            try:
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                elif path.is_file():
                    path.unlink()
            except:
                pass
    
    # Third pass: remove empty directories
    for root, dirs, _files in os.walk(build_module_dir, topdown=False):
        for dir_name in dirs:
            dir_path = Path(root) / dir_name
            try:
                if not any(dir_path.iterdir()):
                    dir_path.rmdir()
            except:
                pass

def process_module_in_build(build_module_dir: Path, extension: str) -> bool:
    """Process a single module in build directory"""
    module_name = build_module_dir.name
    print(f"\n📦 Processing module: {module_name}")
    
    # Skip egg-info directories
    if module_name.endswith('.egg-info'):
        print(f"  ⏭️  Skipping egg-info directory")
        return False
    
    # Check if module has module.ini
    ini_path = build_module_dir / "module.ini"
    if not ini_path.exists():
        print(f"  ⚠️  Missing module.ini, skipping")
        return False
    
    try:
        # Read the entry file from module.ini before compiling
        config = configparser.ConfigParser()
        config.read(ini_path, encoding='utf-8')
        entry_file = None
        if 'module' in config:
            entry = config['module'].get('entry', '')
            if entry:
                entry = entry.strip().strip('"').strip("'")
                if entry.endswith('.py'):
                    entry_file = build_module_dir / entry
                    print(f"  📄 Entry file: {entry}")
        
        # Compile Python files
        compiled_count = compile_module_in_build(build_module_dir, extension)
        
        # Update module.ini
        update_success = update_module_ini_in_build(build_module_dir, extension)
        
        # If we couldn't update module.ini but we have an entry file that wasn't compiled
        if not update_success and entry_file and entry_file.exists():
            print(f"  ℹ️  Using original entry file: {entry_file.name}")
            # module.ini already points to the .py file, which still exists
        
        # Clean directory
        clean_build_module_directory(build_module_dir, extension)
        
        print(f"  ✅ Successfully compiled {compiled_count} files")
        return compiled_count > 0 or update_success
        
    except Exception as e:
        print(f"  ❌ Processing failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def compile_modules_in_build(build_modules: Path) -> int:
    """Compile all modules in build directory"""
    extension = get_module_extension()
    print(f"🔧 Target platform: {platform.system()}, compilation extension: {extension}")
    
    # Get all module directories
    module_dirs = []
    for item in build_modules.iterdir():
        if not item.is_dir():
            continue
        if item.name.startswith(('.', '__')):
            continue
        if item.name.endswith('.egg-info'):
            continue
        module_dirs.append(item)
    
    if not module_dirs:
        print("ℹ️  No module directories found")
        return 0
    
    print(f"📊 Found {len(module_dirs)} modules")
    
    # Process each module
    success_count = 0
    for module_dir in module_dirs:
        if process_module_in_build(module_dir, extension):
            success_count += 1
    
    print(f"\n📊 Compilation statistics:")
    print(f"   Total modules: {len(module_dirs)}")
    print(f"   Successfully compiled: {success_count}")
    print(f"   Failed: {len(module_dirs) - success_count}")
    
    return success_count

def clean_dist_directory(dist_dir: Path):
    """Clean distribution directory of unwanted files"""
    print(f"\n🧹 Cleaning distribution directory...")
    
    if not dist_dir.exists():
        return
    
    files_removed = 0
    dirs_removed = 0
    
    for pattern in CLEAN_PATTERNS:
        for path in dist_dir.rglob(pattern):
            try:
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                    dirs_removed += 1
                elif path.is_file():
                    path.unlink()
                    files_removed += 1
            except Exception as e:
                print(f"  ⚠️  Unable to delete {path.relative_to(dist_dir)}: {e}")
    
    print(f"  📊 Cleanup complete: Removed {files_removed} files, {dirs_removed} directories")

def escape_windows_path(path: str) -> str:
    """Escape Windows path for use in Python strings"""
    return path.replace('\\', '\\\\').encode('unicode_escape').decode('utf-8')

def create_pyinstaller_spec(config: BuildConfig):
    """Create PyInstaller spec file"""
    if not config.main_py.exists():
        print(f"❌ Main program does not exist: {config.main_py}")
        return None
    
    build_modules = config.build_temp / "modules"

    main_py_path = escape_windows_path(str(config.main_py.absolute()))
    project_root_path = escape_windows_path(str(config.project_root.absolute()))
    build_modules_path = escape_windows_path(str(build_modules.absolute()))
    
    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from pathlib import Path

block_cipher = None

# Determine the base path
base_path = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else Path.cwd()

a = Analysis(
    [r'{main_py_path}'],
    pathex=[r'{project_root_path}'],
    binaries=[],
    datas=[
        ('config.yml', '.') if os.path.exists('config.yml') else None,
        (r'{build_modules_path}', 'modules')
    ],
    hiddenimports={json.dumps(HIDDEN_IMPORTS)},
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=['test', 'tests', '_test', '_tests'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    optimize=2
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
"""
    
    with open(config.spec_file, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    print(f"📝 Created spec file: {config.spec_file}")
    
    return config.spec_file

def run_pyinstaller(config: BuildConfig):
    """Run PyInstaller with the spec file"""
    print("\n🚀 Running PyInstaller packaging...")
    print("-" * 40)
    
    try:
        # Create build directory for PyInstaller
        if config.pyinstaller_build.exists():
            shutil.rmtree(config.pyinstaller_build, ignore_errors=True)
        
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        
        result = subprocess.run([
            sys.executable, "-m", "PyInstaller",
            "--distpath", str(config.dist_dir),
            "--workpath", str(config.pyinstaller_build),
            "--noconfirm",
            "--clean",
            str(config.spec_file)
        ], capture_output=True, text=True, encoding='utf-8', errors='replace', env=env)
        
        if result.returncode == 0:
            print("  ✅ PyInstaller packaging completed")
            return True
        else:
            print(f"  ❌ PyInstaller packaging failed")
            if result.stdout:
                print(f"     Output: {result.stdout[:500]}")
            if result.stderr:
                error_lines = result.stderr.split('\n')
                for line in error_lines[:10]:  # Show first 10 error lines
                    if line.strip():
                        print(f"     Error: {line}")
            return False
    except Exception as e:
        print(f"  ❌ PyInstaller packaging exception: {e}")
        return False

def install_dependencies():
    """Install required dependencies"""
    print("\n📦 Installing dependencies...")
    try:
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "pyinstaller>=5.0", "cython>=3.0", "setuptools>=65.0", "-q"
        ], capture_output=True, text=True, encoding='utf-8', errors='replace', env=env)
        
        if result.returncode == 0:
            print("  ✅ Dependencies installed successfully")
        else:
            print(f"  ⚠️  Dependencies installation may have issues, continuing...")
            print(f"     Error: {result.stderr[:200]}")
    except Exception as e:
        print(f"  ⚠️  Dependencies installation exception: {e}")

def clean_previous_builds(config: BuildConfig):
    """Clean previous build artifacts"""
    print("\n🧹 Cleaning previous build files...")
    for path in [config.dist_dir, config.project_root / "build"]:
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
            print(f"  Cleaned: {path}")

def validate_project_structure(config: BuildConfig) -> bool:
    """Validate that required project files exist"""
    if not config.src_modules.exists():
        print(f"❌ Source modules directory does not exist: {config.src_modules}")
        return False
    
    if not config.main_py.exists():
        print(f"❌ Main program does not exist: {config.main_py}")
        return False
    
    return True

def show_build_summary(config: BuildConfig):
    """Display build summary and final structure"""
    print("\n" + "=" * 60)
    print("✅ Build completed!")
    print("=" * 60)
    
    # Show final structure
    if config.dist_dir.exists():
        exe_name = "backend.exe" if platform.system() == "Windows" else "backend"
        exe_path = config.dist_dir / exe_name
        modules_path = config.dist_dir / "modules"
        
        if exe_path.exists():
            exe_size = exe_path.stat().st_size // 1024
            print(f"\n📁 Output structure:")
            print(f"  Main program: {exe_path.name} ({exe_size} KB)")
        
        if modules_path.exists():
            module_dirs = [d for d in modules_path.iterdir() if d.is_dir()]
            print(f"  Modules directory: {modules_path} ({len(module_dirs)} modules)")
            
            for module_dir in module_dirs:
                if module_dir.is_dir() and not module_dir.name.endswith('.egg-info'):
                    files = [f.name for f in module_dir.iterdir() if f.is_file()]
                    if files:
                        print(f"    • {module_dir.name}: {', '.join(files)}")
    
    print("\n🎉 Build completed successfully!")
    print("=" * 60)

def main():
    project_root = Path(__file__).parent.absolute()
    config = BuildConfig(project_root)
    
    print("=" * 60)
    print("🔨 SwarmCloneBackend Build Tool")
    print("=" * 60)
    
    # Validate project structure
    if not validate_project_structure(config):
        return
    
    # Clean previous builds
    clean_previous_builds(config)
    
    # Install dependencies
    install_dependencies()
    
    # Setup build environment
    print("\n🔧 Setting up build environment...")
    build_temp = setup_build_environment(config)
    
    # Copy modules to build directory
    build_modules = copy_modules_to_build(config.src_modules, build_temp)
    
    # Compile modules in build directory
    print("\n🔧 Compiling modules to binary files...")
    print("-" * 40)
    
    success_count = compile_modules_in_build(build_modules)
    
    if success_count == 0:
        print("⚠️  No successfully compiled modules, packaging with original code...")
    
    # Create PyInstaller spec file
    spec_file = create_pyinstaller_spec(config)
    if not spec_file:
        return
    
    # Run PyInstaller
    if not run_pyinstaller(config):
        print("⚠️  PyInstaller packaging failed")
        return
    
    # Clean dist directory
    clean_dist_directory(config.dist_dir)
    
    # Clean up build directory (keep for debugging if needed)
    print("\n🧹 Cleaning build temporary files...")
    if config.build_temp.exists():
        shutil.rmtree(config.build_temp, ignore_errors=True)
        print(f"  Cleaned build temporary directory")
    
    # Clean spec file
    if config.spec_file.exists():
        config.spec_file.unlink()
        print(f"  Deleted spec file")
    
    # Show summary
    show_build_summary(config)

if __name__ == "__main__":
    main()
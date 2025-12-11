import sys
import subprocess
from pathlib import Path
import platform
import shutil
import os
import configparser
import tempfile
import logging
import json
import time
from contextlib import contextmanager
import traceback

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
    'core', 'modules', 'ruamel.yaml', 'fastapi', 'uvicorn', 
    'pydantic', 'asyncio', 'multiprocessing', 'typing_extensions',
    'aiohttp', 'requests', 'httpx', 'json', 'yaml', 'toml',
    'logging', 'datetime', 'pathlib', 'os', 'sys', 're',
    'threading', 'concurrent.futures', 'time', 'random',
    'hashlib', 'base64', 'zlib', 'gzip', 'bz2', 'lzma',
    'csv', 'sqlite3', 'collections', 'itertools', 'functools'
]
SKIP_FILES = ['__init__.py', 'setup.py']

class BuildError(Exception):
    """Custom exception for build failures"""
    pass

class BuildConfig:
    """Configuration for the build process"""
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.system = platform.system()
        self.module_extension = self._get_module_extension()
        
        # Build directories
        self.src_modules = project_root / "src" / "modules"
        self.dist_dir = project_root / "dist"
        self.build_temp = project_root / "build" / "temp"
        self.pyinstaller_build = project_root / "build" / "pyinstaller"
        self.pyinstaller_temp = self.pyinstaller_build / "temp"
        self.main_py = project_root / "src" / "main.py"
        self.spec_file = project_root / "backend.spec"
    
    def _get_module_extension(self) -> str:
        """Get compiled module extension based on platform"""
        return MODULE_EXTENSION_MAP.get(self.system, ".so")

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
        try:
            shutil.rmtree(build_temp, ignore_errors=False)
        except Exception as e:
            print(f"   Warning: Failed to clean build temp directory: {e}")
            # Try to rename instead
            backup_dir = build_temp.parent / f"temp_backup_{int(time.time())}"
            if build_temp.exists():
                build_temp.rename(backup_dir)
    
    build_temp.mkdir(parents=True, exist_ok=True)
    
    # Create PyInstaller specific directories
    config.pyinstaller_build.mkdir(parents=True, exist_ok=True)
    config.pyinstaller_temp.mkdir(parents=True, exist_ok=True)
    
    # Set environment variables for temporary directories
    os.environ['TEMP'] = str(config.pyinstaller_temp)
    os.environ['TMP'] = str(config.pyinstaller_temp)
    
    print(f" Build temporary directory: {build_temp}")
    print(f" PyInstaller temp directory: {config.pyinstaller_temp}")
    
    return build_temp

def copy_modules_to_build(src_modules: Path, build_temp: Path) -> Path:
    """Copy modules directory to build temp directory"""
    build_modules = build_temp / "modules"
    
    if build_modules.exists():
        shutil.rmtree(build_modules, ignore_errors=True)
    
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
    
    try:
        shutil.copytree(src_modules, build_modules, ignore=ignore_patterns)
    except Exception as e:
        print(f"   Error copying modules: {e}")
        # Try alternative method
        build_modules.mkdir(parents=True, exist_ok=True)
        for src_file in src_modules.rglob("*"):
            if src_file.is_file():
                rel_path = src_file.relative_to(src_modules)
                dst_file = build_modules / rel_path
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)
    
    print(f" Copied modules to build directory: {build_modules}")
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
            env['TEMP'] = temp_dir
            env['TMP'] = temp_dir
            
            # Run compilation with timeout and detailed logging
            process = subprocess.Popen(
                [sys.executable, str(setup_file), "build_ext", "--inplace"],
                cwd=temp_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                env=env
            )
            
            stdout, stderr = process.communicate(timeout=120)
            
            if process.returncode != 0:
                print(f"   Compilation failed: {py_file.name}")
                print(f"     Return code: {process.returncode}")
                if stderr:
                    error_lines = stderr.split('\n')
                    for line in error_lines[-10:]:  # Show last 10 error lines
                        if line.strip() and len(line) < 500:
                            print(f"     {line.strip()}")
                if stdout:
                    print(f"     Stdout (last 5 lines):")
                    for line in stdout.split('\n')[-5:]:
                        if line.strip():
                            print(f"       {line.strip()}")
                return False
            
            # Look for compiled file
            compiled_file = None
            search_patterns = [
                f"*{extension}",
                f"{module_name}*{extension}",
                f"**/*{extension}",
                f"**/{module_name}*{extension}"
            ]
            
            for pattern in search_patterns:
                for file in temp_path.glob(pattern):
                    if file.is_file() and file.stem.startswith(module_name):
                        compiled_file = file
                        break
                if compiled_file:
                    break
            
            # Also look in the source directory
            if not compiled_file:
                source_dir = py_file.parent
                for file in source_dir.glob(f"*{extension}"):
                    if file.is_file() and file.stem.startswith(module_name):
                        compiled_file = file
                        break
            
            if compiled_file and compiled_file.exists():
                # Ensure output directory exists
                output_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy compiled file to output location
                shutil.copy2(compiled_file, output_file)
                print(f"   Successfully compiled: {py_file.name} -> {output_file.name}")
                
                # Clean up source compiled file
                if compiled_file.parent != output_file.parent:
                    try:
                        compiled_file.unlink()
                    except Exception as e:
                        print(f"     Warning: Could not clean up compiled file: {e}")
                
                return True
        
        print(f"    No compiled file found for: {py_file.name}")
        return False
        
    except subprocess.TimeoutExpired:
        print(f"    Compilation timeout: {py_file.name}")
        process.kill() # type: ignore
        return False
    except Exception as e:
        print(f"    Compilation exception: {py_file.name} - {str(e)}")
        traceback.print_exc()
        return False

def compile_module_in_build(build_module_dir: Path, extension: str) -> int:
    """Compile all Python files in a build module directory"""
    print(f"   Searching for Python files...")
    
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
            print(f"    Failed to read module.ini: {e}")
    
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
        print(f"    No compilable Python files found")
        return 0
    
    print(f"   Found {len(python_files)} Python files")
    
    # Compile each file
    success_count = 0
    for py_file in python_files:
        relative_path = py_file.relative_to(build_module_dir)
        print(f"   Compiling: {relative_path}")
        
        # Determine output path (same directory, different extension)
        output_file = py_file.parent / f"{py_file.stem}{extension}"
        
        if compile_python_file(py_file, output_file, extension):
            success_count += 1
            # Remove source .py file after successful compilation
            try:
                if py_file.exists():
                    py_file.unlink()
                    print(f"     Removed source file: {py_file.name}")
                # Remove empty parent directories
                parent = py_file.parent
                while parent != build_module_dir and not any(parent.iterdir()):
                    try:
                        parent.rmdir()
                        parent = parent.parent
                        print(f"     Removed empty directory: {parent.name}")
                    except:
                        break
            except Exception as e:
                print(f"     Warning: Could not clean up source file: {e}")
    
    return success_count

def update_module_ini_in_build(build_module_dir: Path, extension: str) -> bool:
    """Update module.ini in build directory to point to compiled files"""
    ini_path = build_module_dir / "module.ini"
    if not ini_path.exists():
        print(f"   Missing module.ini")
        return False
    
    try:
        config = configparser.ConfigParser()
        config.read(ini_path, encoding='utf-8')
        
        if 'module' not in config:
            print(f"   module.ini format error: Missing [module] section")
            return False
        
        entry = config['module'].get('entry', '')
        if not entry:
            print(f"   module.ini missing entry field")
            return False
        
        # Clean entry value
        entry = entry.strip().strip('"').strip("'")
        
        # If entry is already a compiled file, leave it as is
        if entry.endswith(('.pyd', '.so')):
            # Check if the compiled file exists
            compiled_file = build_module_dir / entry
            if compiled_file.exists():
                print(f"    Entry is already compiled file: {entry}")
                return True
            else:
                print(f"    Compiled file does not exist: {entry}")
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
            print(f"   Updated entry: {entry} -> {new_entry}")
            return True
        else:
            # Try to find the compiled file in subdirectories
            search_patterns = [
                f"**/{base_name}{extension}",
                f"**/{base_name}*.{extension.lstrip('.')}",
                f"{base_name}{extension}",
                f"{base_name}*.{extension.lstrip('.')}"
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
                    print(f"   Updated entry: {entry} -> {relative_path}")
                    return True
            
            # If we can't find the compiled file, check if we should keep the .py entry
            original_py_file = build_module_dir / f"{base_name}.py"
            if original_py_file.exists():
                print(f"    Keeping original entry: {entry} (file exists but not compiled)")
                return True
            else:
                print(f"    File does not exist and not compiled: {base_name}")
                # Check if there are any compiled files at all
                compiled_files = list(build_module_dir.rglob(f"*{extension}"))
                if compiled_files:
                    print(f"    Found compiled files but none match entry: {[f.name for f in compiled_files[:3]]}")
                return False
            
    except Exception as e:
        print(f"   Failed to update module.ini: {e}")
        traceback.print_exc()
        return False

def clean_build_module_directory(build_module_dir: Path, extension: str):
    """Clean build module directory to only keep necessary files"""
    print(f"   Cleaning build files...")
    
    # First pass: remove all .py files except those we want to keep
    for py_file in build_module_dir.rglob("*.py"):
        if py_file.name in ['__init__.py', 'module.ini']:
            continue
        try:
            if py_file.exists():
                py_file.unlink()
                print(f"     Removed: {py_file.relative_to(build_module_dir)}")
        except Exception as e:
            print(f"     Warning: Could not remove {py_file.name}: {e}")
    
    # Second pass: remove build artifacts
    artifacts = ['*.c', '*.pyc', '*.pyo', 'build', 'dist', '*.egg-info', '__pycache__', 'setup.py', '*.pdb', '*.exp', '*.lib']
    for artifact in artifacts:
        for path in build_module_dir.rglob(artifact):
            try:
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                    print(f"     Removed directory: {path.relative_to(build_module_dir)}")
                elif path.is_file():
                    path.unlink()
                    print(f"     Removed file: {path.relative_to(build_module_dir)}")
            except Exception as e:
                print(f"     Warning: Could not remove {path.name}: {e}")
    
    # Third pass: remove empty directories
    for root, dirs, files in os.walk(build_module_dir, topdown=False):
        for dir_name in dirs:
            dir_path = Path(root) / dir_name
            try:
                if not any(dir_path.iterdir()):
                    dir_path.rmdir()
                    print(f"     Removed empty directory: {dir_path.relative_to(build_module_dir)}")
            except Exception as e:
                print(f"     Warning: Could not remove empty directory {dir_name}: {e}")

def process_module_in_build(build_module_dir: Path, extension: str) -> bool:
    """Process a single module in build directory"""
    module_name = build_module_dir.name
    print(f"\n Processing module: {module_name}")
    
    # Skip egg-info directories
    if module_name.endswith('.egg-info'):
        print(f"    Skipping egg-info directory")
        return False
    
    # Check if module has module.ini
    ini_path = build_module_dir / "module.ini"
    if not ini_path.exists():
        print(f"    Missing module.ini, skipping")
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
                    print(f"   Entry file: {entry}")
        
        # Compile Python files
        compiled_count = compile_module_in_build(build_module_dir, extension)
        
        # Update module.ini
        update_success = update_module_ini_in_build(build_module_dir, extension)
        
        # If we couldn't update module.ini but we have an entry file that wasn't compiled
        if not update_success and entry_file and entry_file.exists():
            print(f"    Using original entry file: {entry_file.name}")
            # module.ini already points to the .py file, which still exists
            update_success = True
        
        # Clean directory
        clean_build_module_directory(build_module_dir, extension)
        
        print(f"   Successfully compiled {compiled_count} files")
        return compiled_count > 0 or update_success
        
    except Exception as e:
        print(f"   Processing failed: {e}")
        traceback.print_exc()
        return False

def compile_modules_in_build(build_modules: Path) -> int:
    """Compile all modules in build directory"""
    extension = get_module_extension()
    print(f"\n{'='*50}")
    print(f" Compiling modules for {platform.system()} platform")
    print(f" Compilation extension: {extension}")
    print(f"{'='*50}")
    
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
        print("  No module directories found")
        return 0
    
    print(f" Found {len(module_dirs)} modules")
    print(f" Modules to process: {[d.name for d in module_dirs]}")
    
    # Process each module
    success_count = 0
    for module_dir in module_dirs:
        if process_module_in_build(module_dir, extension):
            success_count += 1
    
    print(f"\n{'='*50}")
    print(f" Compilation statistics:")
    print(f"   Total modules: {len(module_dirs)}")
    print(f"   Successfully compiled: {success_count}")
    print(f"   Failed: {len(module_dirs) - success_count}")
    print(f"{'='*50}")
    
    return success_count

def clean_dist_directory(dist_dir: Path):
    """Clean distribution directory of unwanted files"""
    print(f"\n{'='*50}")
    print(f" Cleaning distribution directory...")
    print(f"{'='*50}")
    
    if not dist_dir.exists():
        print("  Distribution directory does not exist, nothing to clean")
        return
    
    files_removed = 0
    dirs_removed = 0
    
    for pattern in CLEAN_PATTERNS:
        for path in dist_dir.rglob(pattern):
            try:
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                    dirs_removed += 1
                    print(f"   Removed directory: {path.relative_to(dist_dir)}")
                elif path.is_file():
                    path.unlink()
                    files_removed += 1
                    print(f"   Removed file: {path.relative_to(dist_dir)}")
            except Exception as e:
                print(f"    Unable to delete {path.relative_to(dist_dir)}: {e}")
    
    print(f"\n   Cleanup complete: Removed {files_removed} files, {dirs_removed} directories")

def escape_windows_path(path: str) -> str:
    """Escape Windows path for use in Python strings"""
    return path.replace('\\', '\\\\')

def create_pyinstaller_spec(config: BuildConfig):
    """Create PyInstaller spec file with better error handling"""
    print(f"\n{'='*50}")
    print(f" Creating PyInstaller spec file")
    print(f"{'='*50}")
    
    if not config.main_py.exists():
        print(f" ❌ Main program does not exist: {config.main_py}")
        print(f"   Current working directory: {Path.cwd()}")
        print(f"   Project root: {config.project_root}")
        print(f"   Available files in src:")
        for file in config.project_root.glob("src/**/*"):
            if file.is_file():
                print(f"     {file.relative_to(config.project_root)}")
        return None
    
    build_modules = config.build_temp / "modules"
    
    if not build_modules.exists():
        print(f" ❌ Build modules directory does not exist: {build_modules}")
        print(f"   Creating empty modules directory for packaging...")
        build_modules.mkdir(parents=True, exist_ok=True)
    
    # Get absolute paths with proper escaping
    main_py_path = escape_windows_path(str(config.main_py.absolute()))
    project_root_path = escape_windows_path(str(config.project_root.absolute()))
    build_modules_path = escape_windows_path(str(build_modules.absolute()))
    
    # Verify paths exist
    print(f"   Main program path: {main_py_path}")
    print(f"   Project root path: {project_root_path}")
    print(f"   Build modules path: {build_modules_path}")
    
    # Check if config.yml exists before adding to datas
    datas_entries = []
    
    # Add config.yml only if it exists
    config_yml_path = config.project_root / "config.yml"
    if config_yml_path.exists():
        datas_entries.append(f"('config.yml', '.')")
        print(f"   ✅ config.yml found and will be included")
    else:
        print(f"   ⚠️ config.yml not found, will not be included")
    
    # Always add modules directory
    datas_entries.append(f"(r'{build_modules_path}', 'modules')")
    
    # Join datas entries properly
    datas_str = ",\n        ".join(datas_entries) if datas_entries else ""
    
    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from pathlib import Path

# Set up proper temporary directory
import tempfile
if not hasattr(sys, '_MEIPASS'):
    # Build time
    build_temp = Path(r'{project_root_path}') / 'build' / 'pyinstaller' / 'temp'
    build_temp.mkdir(parents=True, exist_ok=True)
    os.environ['TEMP'] = str(build_temp)
    os.environ['TMP'] = str(build_temp)
    print(f"Using build temp directory: {{build_temp}}")
else:
    # Runtime
    runtime_temp = Path(sys._MEIPASS) / 'temp'
    runtime_temp.mkdir(parents=True, exist_ok=True)
    os.environ['TEMP'] = str(runtime_temp)
    os.environ['TMP'] = str(runtime_temp)
    print(f"Using runtime temp directory: {{runtime_temp}}")

block_cipher = None

a = Analysis(
    [r'{main_py_path}'],
    pathex=[r'{project_root_path}'],
    binaries=[],
    datas=[
        {datas_str}
    ],
    hiddenimports={json.dumps(HIDDEN_IMPORTS)},
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        'test', 'tests', '_test', '_tests', 'pytest', 'unittest', 
        'setuptools', 'pkg_resources', 'wheel', 'pip', 'distutils'
    ],
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
    upx=False,  # Disable UPX on GitHub Actions due to permission issues
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
    
    # Write spec file
    config.spec_file.parent.mkdir(parents=True, exist_ok=True)
    with open(config.spec_file, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print(f" ✅ Created spec file: {config.spec_file}")
    
    # Verify spec file was created
    if config.spec_file.exists():
        print(f"   Spec file size: {config.spec_file.stat().st_size} bytes")
        print(f"\n   Spec file content preview:")
        with open(config.spec_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for i, line in enumerate(lines[:25]):
                print(f"     {i+1}: {line.rstrip()}")
    
    return config.spec_file

def run_pyinstaller(config: BuildConfig):
    """Run PyInstaller with the spec file with detailed logging and error handling"""
    print(f"\n{'='*50}")
    print(f" Running PyInstaller packaging")
    print(f"{'='*50}")
    
    try:
        # Create build directory for PyInstaller
        if config.pyinstaller_build.exists():
            print(f"   Cleaning previous PyInstaller build directory...")
            shutil.rmtree(config.pyinstaller_build, ignore_errors=True)
        
        config.pyinstaller_build.mkdir(parents=True, exist_ok=True)
        config.dist_dir.mkdir(parents=True, exist_ok=True)
        
        # Set up environment variables
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        env['TEMP'] = str(config.pyinstaller_temp)
        env['TMP'] = str(config.pyinstaller_temp)
        env['PYINSTALLER_CONFIG_DIR'] = str(config.pyinstaller_build)
        
        # Print environment information
        print(f"   Environment variables:")
        print(f"     TEMP: {env['TEMP']}")
        print(f"     TMP: {env['TMP']}")
        print(f"     PYTHONIOENCODING: {env['PYTHONIOENCODING']}")
        
        # Build the command
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--distpath", str(config.dist_dir),
            "--workpath", str(config.pyinstaller_build),
            "--noconfirm",
            "--clean",
            "--log-level", "INFO",  # More detailed logging
            str(config.spec_file)
        ]
        
        print(f"\n   Running command:")
        print(f"   {' '.join(cmd)}")
        
        # Run with real-time output
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
            env=env,
            bufsize=1
        )
        
        # Read stdout in real-time
        print(f"\n   {'PyInstaller Output':-^50}")
        stdout_lines = []
        while True:
            line = process.stdout.readline() # type: ignore
            if not line and process.poll() is not None:
                break
            if line:
                line = line.rstrip()
                stdout_lines.append(line)
                if "INFO" in line or "WARNING" in line or "ERROR" in line or "building" in line.lower():
                    print(f"   {line}")
        
        # Get remaining output
        stdout, stderr = process.communicate()
        if stdout:
            stdout_lines.extend(stdout.splitlines())
        if stderr:
            print(f"\n   {'PyInstaller Errors':-^50}")
            for line in stderr.splitlines():
                if line.strip():
                    print(f"   ERROR: {line.strip()}")
        
        print(f"   {'End of Output':-^50}\n")
        
        if process.returncode == 0:
            print(f" PyInstaller packaging completed successfully")
            # Verify the executable was created
            exe_name = "backend.exe" if platform.system() == "Windows" else "backend"
            exe_path = config.dist_dir / exe_name
            if exe_path.exists():
                print(f"   Executable created: {exe_path}")
                print(f"   Executable size: {exe_path.stat().st_size // 1024} KB")
                return True
            else:
                print(f"    Executable not found at: {exe_path}")
                print(f"   Files in dist directory:")
                for file in config.dist_dir.iterdir():
                    print(f"     {file.name}")
                return False
        else:
            print(f"  PyInstaller packaging failed with return code: {process.returncode}")
            print(f"\n   {'Last 20 stdout lines':-^50}")
            for line in stdout_lines[-20:]:
                if line.strip():
                    print(f"     {line}")
            return False
            
    except Exception as e:
        print(f"  PyInstaller packaging exception: {e}")
        traceback.print_exc()
        return False

def install_dependencies():
    """Install required dependencies with detailed logging"""
    print(f"\n{'='*50}")
    print(f" Installing dependencies")
    print(f"{'='*50}")
    
    try:
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        
        # Install core dependencies first
        core_deps = ["pyinstaller>=6.0", "cython>=3.0", "setuptools>=65.0", "wheel"]
        
        print("   Installing core dependencies...")
        for dep in core_deps:
            result = subprocess.run([
                sys.executable, "-m", "pip", "install", "--upgrade", dep
            ], capture_output=True, text=True, encoding='utf-8', errors='replace', env=env)
            
            if result.returncode == 0:
                print(f"   {dep} installed successfully")
            else:
                print(f"    {dep} installation may have issues:")
                print(f"     Return code: {result.returncode}")
                if result.stderr:
                    error_lines = result.stderr.split('\n')
                    for line in error_lines[:5]:
                        if line.strip():
                            print(f"       {line.strip()}")
        
        # Install additional dependencies
        additional_deps = ["ruamel.yaml", "fastapi", "uvicorn", "pydantic"]
        
        print("\n   Installing additional dependencies...")
        for dep in additional_deps:
            result = subprocess.run([
                sys.executable, "-m", "pip", "install", "--upgrade", dep
            ], capture_output=True, text=True, encoding='utf-8', errors='replace', env=env)
            
            if result.returncode == 0:
                print(f"   {dep} installed successfully")
            else:
                print(f"    {dep} installation may have issues:")
                print(f"     Return code: {result.returncode}")
                if result.stderr:
                    error_lines = result.stderr.split('\n')
                    for line in error_lines[:3]:
                        if line.strip():
                            print(f"       {line.strip()}")
        
        print(f" Dependencies installation completed")
        return True
        
    except Exception as e:
        print(f"  Dependencies installation exception: {e}")
        traceback.print_exc()
        return False

def clean_previous_builds(config: BuildConfig):
    """Clean previous build artifacts"""
    print(f"\n{'='*50}")
    print(f" Cleaning previous build files")
    print(f"{'='*50}")
    
    paths_to_clean = [
        config.dist_dir,
        config.project_root / "build",
        config.project_root / "backend.spec",
        config.project_root / "build.spec"
    ]
    
    for path in paths_to_clean:
        if path.exists():
            try:
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                    print(f"  Cleaned directory: {path}")
                else:
                    path.unlink()
                    print(f"  Cleaned file: {path}")
            except Exception as e:
                print(f"   Could not clean {path}: {e}")
                # Try to rename instead
                try:
                    backup_path = path.parent / f"{path.name}_backup_{int(time.time())}"
                    path.rename(backup_path)
                    print(f"    Renamed to: {backup_path}")
                except Exception as rename_e:
                    print(f"    Could not rename either: {rename_e}")

def validate_project_structure(config: BuildConfig) -> bool:
    """Validate that required project files exist"""
    print(f"\n{'='*50}")
    print(f" Validating project structure")
    print(f"{'='*50}")
    
    issues = []
    
    print(f"   Project root: {config.project_root}")
    print(f"   Current directory: {Path.cwd()}")
    
    # Check main.py
    if not config.main_py.exists():
        issues.append(f" Main program does not exist: {config.main_py}")
        print(f"   Looking for main.py in src directory:")
        src_dir = config.project_root / "src"
        if src_dir.exists():
            for file in src_dir.rglob("*"):
                if file.is_file() and file.name.lower() == "main.py":
                    print(f"     Found: {file.relative_to(config.project_root)}")
        else:
            print(f"   src directory does not exist!")
    else:
        print(f"   Main program exists: {config.main_py}")
        print(f"   Main program size: {config.main_py.stat().st_size} bytes")
    
    # Check modules directory
    if not config.src_modules.exists():
        issues.append(f" Source modules directory does not exist: {config.src_modules}")
        print(f"   Looking for modules directory:")
        for possible_path in [
            config.project_root / "modules",
            config.project_root / "src" / "module",
            config.project_root / "module"
        ]:
            if possible_path.exists():
                print(f"     Found alternative: {possible_path}")
    else:
        print(f"   Source modules directory exists: {config.src_modules}")
        # List module directories
        module_dirs = [d for d in config.src_modules.iterdir() if d.is_dir() and not d.name.startswith(('.', '__'))]
        print(f"   Found {len(module_dirs)} modules: {[d.name for d in module_dirs]}")
    
    # Check Python version
    print(f"\n   Python environment:")
    print(f"     Python version: {sys.version}")
    print(f"     Python executable: {sys.executable}")
    print(f"     Platform: {platform.system()} {platform.release()}")
    
    if issues:
        print(f"\n{'='*50}")
        print(f" Validation failed with {len(issues)} issues:")
        for issue in issues:
            print(f"   {issue}")
        print(f"{'='*50}")
        return False
    
    print(f"\n Project structure validation passed")
    return True

def show_build_summary(config: BuildConfig):
    """Display build summary and final structure"""
    print(f"\n{'='*60}")
    print(f" Build completed!")
    print(f"{'='*60}")
    
    # Show final structure
    if config.dist_dir.exists():
        exe_name = "backend.exe" if platform.system() == "Windows" else "backend"
        exe_path = config.dist_dir / exe_name
        modules_path = config.dist_dir / "modules"
        
        if exe_path.exists():
            exe_size = exe_path.stat().st_size // 1024
            print(f"\n Output structure:")
            print(f"  Main program: {exe_path.name} ({exe_size} KB)")
        
        if modules_path.exists():
            module_dirs = [d for d in modules_path.iterdir() if d.is_dir() and not d.name.endswith('.egg-info')]
            print(f"  Modules directory: {modules_path} ({len(module_dirs)} modules)")
            
            for module_dir in module_dirs:
                if module_dir.is_dir():
                    files = [f.name for f in module_dir.iterdir() if f.is_file()]
                    if files:
                        print(f"    • {module_dir.name}: {', '.join(files[:3])}{'...' if len(files) > 3 else ''}")
    
    print(f"\n Build completed successfully!")
    print(f"{'='*60}")

def main():
    project_root = Path(__file__).parent.absolute()
    config = BuildConfig(project_root)
    
    print(f"{'='*60}")
    print(f" SwarmCloneBackend Build Tool")
    print(f" Platform: {platform.system()} {platform.release()}")
    print(f" Python: {sys.version.split()[0]}")
    print(f" Project root: {project_root}")
    print(f"{'='*60}")
    
    # Validate project structure
    if not validate_project_structure(config):
        sys.exit(1)
    
    # Clean previous builds
    clean_previous_builds(config)
    
    # Install dependencies
    install_dependencies()
    
    # Setup build environment
    print(f"\n{'='*50}")
    print(f" Setting up build environment")
    print(f"{'='*50}")
    build_temp = setup_build_environment(config)
    
    # Copy modules to build directory
    build_modules = copy_modules_to_build(config.src_modules, build_temp)
    
    # Compile modules in build directory
    print(f"\n{'='*50}")
    print(f" Compiling modules to binary files")
    print(f"{'='*50}")
    
    success_count = compile_modules_in_build(build_modules)
    
    if success_count == 0:
        print(f"  No successfully compiled modules, packaging with original code...")
    
    # Create PyInstaller spec file
    spec_file = create_pyinstaller_spec(config)
    if not spec_file:
        print(f"  Failed to create spec file")
        sys.exit(1)
    
    # Run PyInstaller
    if not run_pyinstaller(config):
        print(f"  PyInstaller packaging failed")
        sys.exit(1)
    
    # Clean dist directory
    clean_dist_directory(config.dist_dir)
    
    # Clean up build directory
    print(f"\n{'='*50}")
    print(f" Cleaning build temporary files")
    print(f"{'='*50}")
    if config.build_temp.exists():
        try:
            shutil.rmtree(config.build_temp, ignore_errors=True)
            print(f"  Cleaned build temporary directory")
        except Exception as e:
            print(f"   Could not clean build temporary directory: {e}")
    
    # Clean spec file
    if config.spec_file.exists():
        try:
            config.spec_file.unlink()
            print(f"  Deleted spec file")
        except Exception as e:
            print(f"   Could not delete spec file: {e}")
    
    # Show summary
    show_build_summary(config)
    
    # Verify the final executable
    exe_name = "backend.exe" if platform.system() == "Windows" else "backend"
    exe_path = config.dist_dir / exe_name
    if exe_path.exists():
        print(f"\n Final executable verified at: {exe_path}")
        print(f" Build completed successfully!")
        sys.exit(0)
    else:
        print(f"\n  Final executable not found at: {exe_path}")
        print(f"  Build failed!")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n{'='*60}")
        print(f" FATAL ERROR: Build failed")
        print(f"{'='*60}")
        print(f" Error: {e}")
        traceback.print_exc()
        print(f"{'='*60}")
        sys.exit(1)
import sys
import subprocess
from pathlib import Path
import platform
import shutil
import os
import configparser
import tempfile

def get_module_extension():
    """Get compiled module extension based on platform"""
    system = platform.system()
    if system == "Windows":
        return ".pyd"
    elif system == "Darwin":  # macOS
        return ".so"
    else:  # Linux and others
        return ".so"

def setup_build_environment(project_root: Path) -> Path:
    """Setup build environment in project_root/build/temp"""
    build_temp = project_root / "build" / "temp"
    
    # Clean and create build directories
    if build_temp.exists():
        shutil.rmtree(build_temp, ignore_errors=True)
    
    build_temp.mkdir(parents=True, exist_ok=True)
    
    print(f"📁 构建临时目录: {build_temp}")
    return build_temp

def copy_modules_to_build(src_modules: Path, build_temp: Path) -> Path:
    """Copy modules directory to build temp directory"""
    build_modules = build_temp / "modules"
    
    if build_modules.exists():
        shutil.rmtree(build_modules)
    
    # Copy everything except build artifacts
    exclude_patterns = [
        '__pycache__', '*.pyc', '*.pyo', '*.pyd', '*.so',
        'build', 'dist', '*.egg-info', '.eggs', '.tox',
        '.pytest_cache', '.coverage', 'htmlcov', '.mypy_cache'
    ]
    
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
    
    print(f"📁 复制模块到构建目录: {build_modules}")
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
                print(f"  ❌ 编译失败: {py_file.name}")
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
        print(f"  ⏰ 编译超时: {py_file.name}")
        return False
    except Exception as e:
        print(f"  ❌ 编译异常: {py_file.name} - {str(e)[:100]}")
        return False

def compile_module_in_build(build_module_dir: Path, extension: str) -> int:
    """Compile all Python files in a build module directory"""
    print(f"  📄 查找Python文件...")
    
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
            print(f"  ⚠️  读取module.ini失败: {e}")
            pass
    
    # Find all Python files
    python_files = []
    for py_file in build_module_dir.rglob("*.py"):
        # Skip certain files
        skip_files = ['__init__.py', 'setup.py']
        if py_file.name in skip_files:
            continue
        # Don't skip test files that are the entry point
        if 'test' in py_file.name.lower() and py_file != entry_file:
            continue
        python_files.append(py_file)
    
    if not python_files:
        print(f"  ℹ️  没有找到可编译的Python文件")
        return 0
    
    print(f"  📊 找到 {len(python_files)} 个Python文件")
    
    # Compile each file
    success_count = 0
    for py_file in python_files:
        relative_path = py_file.relative_to(build_module_dir)
        print(f"  🔨 编译: {relative_path}")
        
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
        print(f"  ❌ 缺少 module.ini")
        return False
    
    try:
        config = configparser.ConfigParser()
        config.read(ini_path, encoding='utf-8')
        
        if 'module' not in config:
            print(f"  ❌ module.ini 格式错误: 缺少 [module] 部分")
            return False
        
        entry = config['module'].get('entry', '')
        if not entry:
            print(f"  ❌ module.ini 缺少 entry 字段")
            return False
        
        # Clean entry value
        entry = entry.strip().strip('"').strip("'")
        
        # If entry is already a compiled file, leave it as is
        if entry.endswith(('.pyd', '.so')):
            # Check if the compiled file exists
            compiled_file = build_module_dir / entry
            if compiled_file.exists():
                print(f"  ℹ️  entry 已经是编译文件: {entry}")
                return True
            else:
                print(f"  ⚠️  编译文件不存在: {entry}")
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
            print(f"  📝 更新 entry: {entry} -> {new_entry}")
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
                    print(f"  📝 更新 entry: {entry} -> {relative_path}")
                    return True
            
            # If we can't find the compiled file, check if we should keep the .py entry
            # (maybe the file wasn't meant to be compiled)
            original_py_file = build_module_dir / f"{base_name}.py"
            if original_py_file.exists():
                print(f"  ℹ️  保留原始 entry: {entry} (文件存在但未编译)")
                return True
            else:
                print(f"  ⚠️  文件不存在且未编译: {base_name}")
                return False
            
    except Exception as e:
        print(f"  ❌ 更新 module.ini 失败: {e}")
        return False

def clean_build_module_directory(build_module_dir: Path, extension: str):
    """Clean build module directory to only keep necessary files"""
    print(f"  🧹 清理构建文件...")
    
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
    print(f"\n📦 处理模块: {module_name}")
    
    # Skip egg-info directories
    if module_name.endswith('.egg-info'):
        print(f"  ⏭️  跳过 egg-info 目录")
        return False
    
    # Check if module has module.ini
    ini_path = build_module_dir / "module.ini"
    if not ini_path.exists():
        print(f"  ⚠️  缺少 module.ini，跳过")
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
                    print(f"  📄 入口文件: {entry}")
        
        # Compile Python files
        compiled_count = compile_module_in_build(build_module_dir, extension)
        
        # Update module.ini
        update_success = update_module_ini_in_build(build_module_dir, extension)
        
        # If we couldn't update module.ini but we have an entry file that wasn't compiled
        if not update_success and entry_file and entry_file.exists():
            print(f"  ℹ️  使用原始入口文件: {entry_file.name}")
            # module.ini already points to the .py file, which still exists
        
        # Clean directory
        clean_build_module_directory(build_module_dir, extension)
        
        print(f"  ✅ 成功编译 {compiled_count} 个文件")
        return compiled_count > 0 or update_success
        
    except Exception as e:
        print(f"  ❌ 处理失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def compile_modules_in_build(build_modules: Path) -> int:
    """Compile all modules in build directory"""
    extension = get_module_extension()
    print(f"🔧 目标平台: {platform.system()}, 编译扩展: {extension}")
    
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
        print("ℹ️  没有找到模块目录")
        return 0
    
    print(f"📊 找到 {len(module_dirs)} 个模块")
    
    # Process each module
    success_count = 0
    for module_dir in module_dirs:
        if process_module_in_build(module_dir, extension):
            success_count += 1
    
    print(f"\n📊 编译统计:")
    print(f"   总模块数: {len(module_dirs)}")
    print(f"   成功编译: {success_count}")
    print(f"   失败: {len(module_dirs) - success_count}")
    
    return success_count

def clean_dist_directory(dist_dir: Path):
    """Clean distribution directory of unwanted files"""
    print(f"\n🧹 清理发布目录...")
    
    if not dist_dir.exists():
        return
    
    # Patterns to clean
    clean_patterns = [

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
    
    files_removed = 0
    dirs_removed = 0
    
    for pattern in clean_patterns:
        for path in dist_dir.rglob(pattern):
            try:
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                    dirs_removed += 1
                elif path.is_file():
                    path.unlink()
                    files_removed += 1
            except Exception as e:
                print(f"  ⚠️  无法删除 {path.relative_to(dist_dir)}: {e}")
    
    print(f"  📊 清理完成: 删除了 {files_removed} 个文件, {dirs_removed} 个目录")

def escape_windows_path(path: str) -> str:
    """Escape Windows path for use in Python strings"""
    return path.replace('\\', '\\\\').encode('unicode_escape').decode('utf-8')

def create_pyinstaller_spec(project_root: Path, build_temp: Path, dist_dir: Path):
    """Create PyInstaller spec file"""
    main_py = project_root / "src" / "main.py"
    if not main_py.exists():
        print(f"❌ 主程序不存在: {main_py}")
        return None
    
    build_modules = build_temp / "modules"

    main_py_path = escape_windows_path(str(main_py.absolute()))
    project_root_path = escape_windows_path(str(project_root.absolute()))
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
    hiddenimports=[
        'core', 'modules', 'ruamel.yaml', 'fastapi', 'uvicorn', 
        'pydantic', 'asyncio', 'multiprocessing', 'typing_extensions'
    ],
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
    
    spec_file = project_root / "backend.spec"
    with open(spec_file, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    print(f"📝 创建 spec 文件: {spec_file}")
    
    return spec_file

def run_pyinstaller(project_root: Path, spec_file: Path, dist_dir: Path):
    """Run PyInstaller with the spec file"""
    print("\n🚀 运行PyInstaller打包...")
    print("-" * 40)
    
    try:
        # Create build directory for PyInstaller
        pyinstaller_build = project_root / "build" / "pyinstaller"
        if pyinstaller_build.exists():
            shutil.rmtree(pyinstaller_build, ignore_errors=True)
        
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        
        result = subprocess.run([
            sys.executable, "-m", "PyInstaller",
            "--distpath", str(dist_dir),
            "--workpath", str(pyinstaller_build),
            "--noconfirm",
            "--clean",
            str(spec_file)
        ], capture_output=True, text=True, encoding='utf-8', errors='replace', env=env)
        
        if result.returncode == 0:
            print("  ✅ PyInstaller打包完成")
            return True
        else:
            print(f"  ❌ PyInstaller打包失败")
            if result.stdout:
                print(f"     输出: {result.stdout[:500]}")
            if result.stderr:
                error_lines = result.stderr.split('\n')
                for line in error_lines[:10]:  # Show first 10 error lines
                    if line.strip():
                        print(f"     错误: {line}")
            return False
    except Exception as e:
        print(f"  ❌ PyInstaller打包异常: {e}")
        return False

def main():
    project_root = Path(__file__).parent.absolute()
    src_modules = project_root / "src" / "modules"
    dist_dir = project_root / "dist"
    
    print("=" * 60)
    print("🔨 SwarmCloneBackend 构建工具")
    print("=" * 60)
    
    # Check if modules directory exists
    if not src_modules.exists():
        print(f"❌ 源模块目录不存在: {src_modules}")
        return
    
    # Clean previous builds
    print("\n🧹 清理旧的构建文件...")
    for path in [dist_dir, project_root / "build"]:
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
            print(f"  已清理: {path}")
    
    # Install dependencies
    print("\n📦 安装依赖...")
    try:
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "pyinstaller>=5.0", "cython>=3.0", "setuptools>=65.0", "-q"
        ], capture_output=True, text=True, encoding='utf-8', errors='replace', env=env)
        
        if result.returncode == 0:
            print("  ✅ 依赖安装完成")
        else:
            print(f"  ⚠️  依赖安装可能有问题，继续尝试...")
            print(f"     错误: {result.stderr[:200]}")
    except Exception as e:
        print(f"  ⚠️  依赖安装异常: {e}")
    
    # Setup build environment
    print("\n🔧 设置构建环境...")
    build_temp = setup_build_environment(project_root)
    
    # Copy modules to build directory
    build_modules = copy_modules_to_build(src_modules, build_temp)
    
    # Compile modules in build directory
    print("\n🔧 编译模块为二进制文件...")
    print("-" * 40)
    
    success_count = compile_modules_in_build(build_modules)
    
    if success_count == 0:
        print("⚠️  没有成功编译的模块，使用原始代码打包...")
    
    # Create PyInstaller spec file
    spec_file = create_pyinstaller_spec(project_root, build_temp, dist_dir)
    if not spec_file:
        return
    
    # Run PyInstaller
    if not run_pyinstaller(project_root, spec_file, dist_dir):
        print("⚠️  PyInstaller打包失败")
        return
    
    # Clean dist directory
    clean_dist_directory(dist_dir)
    
    # Clean up build directory (keep for debugging if needed)
    print("\n🧹 清理构建临时文件...")
    if build_temp.exists():
        shutil.rmtree(build_temp, ignore_errors=True)
        print(f"  已清理构建临时目录")
    
    # Clean spec file
    if spec_file.exists():
        spec_file.unlink()
        print(f"  已删除 spec 文件")
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ 构建完成!")
    print("=" * 60)
    
    # Show final structure
    if dist_dir.exists():
        exe_name = "backend.exe" if platform.system() == "Windows" else "backend"
        exe_path = dist_dir / exe_name
        modules_path = dist_dir / "modules"
        
        if exe_path.exists():
            exe_size = exe_path.stat().st_size // 1024
            print(f"\n📁 输出结构:")
            print(f"  主程序: {exe_path.name} ({exe_size} KB)")
        
        if modules_path.exists():
            module_dirs = [d for d in modules_path.iterdir() if d.is_dir()]
            print(f"  模块目录: {modules_path} ({len(module_dirs)} 个模块)")
            
            for module_dir in module_dirs:
                if module_dir.is_dir() and not module_dir.name.endswith('.egg-info'):
                    files = [f.name for f in module_dir.iterdir() if f.is_file()]
                    if files:
                        print(f"    • {module_dir.name}: {', '.join(files)}")
    
    print("\n🎉 构建成功完成!")
    print("=" * 60)

if __name__ == "__main__":
    main()
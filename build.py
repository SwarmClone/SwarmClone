import sys
import subprocess
from pathlib import Path
import shutil
import os
import configparser
import tempfile
import json

# === Windows-only constants ===
MODULE_EXTENSION = ".pyd"
EXCLUDE_PATTERNS = [
    '__pycache__', '*.pyc', '*.pyo', '*.pyd', '*.so',
    'build', 'dist', '*.egg-info', '.eggs', '.tox',
    '.pytest_cache', '.coverage', 'htmlcov', '.mypy_cache'
]
HIDDEN_IMPORTS = [
    'core', 'modules', 'ruamel.yaml', 'fastapi', 'uvicorn',
    'pydantic', 'asyncio', 'multiprocessing', 'typing_extensions'
]
SKIP_FILES = ['__init__.py', 'setup.py']

class BuildConfig:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.src_modules = project_root / "src" / "modules"
        self.dist_dir = project_root / "dist"
        self.build_temp = project_root / "build" / "temp"
        self.main_py = project_root / "src" / "main.py"
        self.spec_file = project_root / "backend.spec"

def setup_dirs(config: BuildConfig):
    if config.build_temp.exists():
        shutil.rmtree(config.build_temp, ignore_errors=True)
    config.build_temp.mkdir(parents=True, exist_ok=True)
    print(f"Build temp dir: {config.build_temp}")

def copy_modules(src: Path, dst: Path):
    def ignore_func(directory, names):
        ignored = []
        for name in names:
            for pat in EXCLUDE_PATTERNS:
                if pat.startswith('*') and name.endswith(pat[1:]):
                    ignored.append(name)
                elif pat == name or pat in name:
                    ignored.append(name)
        return list(set(ignored))
    shutil.copytree(src, dst, ignore=ignore_func)
    print(f"Copied modules to: {dst}")

def compile_python_file(py_file: Path, output_file: Path) -> bool:
    try:
        module_name = py_file.stem
        py_file_abs = str(py_file.absolute()).replace('\\', '/')
        parent_dir = str(py_file.parent.absolute()).replace('\\', '/')

        setup_content = f'''
from Cython.Build import cythonize
from setuptools import setup, Extension
import os
os.makedirs(r"{parent_dir}", exist_ok=True)
ext = Extension(
    name="{module_name}",
    sources=[r"{py_file_abs}"],
    language="c",
    define_macros=[("CYTHON_LIMITED_API", "1")]
)
setup(
    ext_modules=cythonize(
        ext,
        compiler_directives={{
            "language_level": 3,
            "boundscheck": False,
            "wraparound": False,
            "cdivision": True,
            "initializedcheck": False,
            "nonecheck": False
        }},
        force=True,
        quiet=True
    ),
    script_args=["build_ext", "--inplace"]
)
'''
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_path = Path(tmpdir) / "setup.py"
            setup_path.write_text(setup_content, encoding='utf-8')

            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONUTF8'] = '1'

            result = subprocess.run(
                [sys.executable, str(setup_path), "build_ext", "--inplace"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=60,
                env=env
            )

            if result.returncode != 0:
                print(f"Compile failed: {py_file.name}")
                return False

            # Find .pyd in source dir
            compiled = py_file.parent / f"{module_name}{MODULE_EXTENSION}"
            if compiled.exists():
                output_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(compiled, output_file)
                compiled.unlink()
                return True
        return False
    except Exception as e:
        print(f"Exception compiling {py_file.name}: {e}")
        return False

def compile_module_dir(module_dir: Path) -> int:
    # Parse module.ini to get entry (to avoid skipping entry .py)
    entry_py = None
    ini_path = module_dir / "module.ini"
    if ini_path.exists():
        try:
            cfg = configparser.ConfigParser()
            cfg.read(ini_path, encoding='utf-8')
            if 'module' in cfg and 'entry' in cfg['module']:
                entry = cfg['module']['entry'].strip().strip('"\'')
                if entry.endswith('.py'):
                    entry_py = module_dir / entry
        except:
            pass

    py_files = [
        f for f in module_dir.rglob("*.py")
        if f.name not in SKIP_FILES and (f != entry_py or not entry_py.exists()) # type: ignore
    ]

    success = 0
    for py in py_files:
        out = py.parent / f"{py.stem}{MODULE_EXTENSION}"
        print(f"Compiling: {py.relative_to(module_dir)}")
        if compile_python_file(py, out):
            success += 1
            py.unlink(missing_ok=True)
    return success

def update_module_ini(module_dir: Path):
    ini = module_dir / "module.ini"
    if not ini.exists():
        return False
    cfg = configparser.ConfigParser()
    cfg.read(ini, encoding='utf-8')
    if 'module' not in cfg or 'entry' not in cfg['module']:
        return False

    entry = cfg['module']['entry'].strip().strip('"\'')
    if entry.endswith(('.pyd', '.so')):
        return True  # already compiled

    if entry.endswith('.py'):
        new_entry = entry[:-3] + MODULE_EXTENSION
        compiled = module_dir / new_entry
        if compiled.exists():
            cfg['module']['entry'] = new_entry
            with open(ini, 'w', encoding='utf-8') as f:
                cfg.write(f)
            print(f"Updated entry: {entry} → {new_entry}")
            return True

    # Try fallback: keep .py if it still exists
    if (module_dir / entry).exists():
        return True
    return False

def clean_module_dir(module_dir: Path):
    for py in module_dir.rglob("*.py"):
        if py.name not in ['__init__.py', 'module.ini']:
            py.unlink(missing_ok=True)
    for pat in ['*.c', '*.pyc', '__pycache__', 'build', 'dist', '*.egg-info', 'setup.py']:
        for p in module_dir.rglob(pat):
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                p.unlink(missing_ok=True)

def process_module(module_dir: Path):
    print(f"\nProcessing module: {module_dir.name}")
    if not (module_dir / "module.ini").exists():
        print("  → Skipped (no module.ini)")
        return False

    compile_module_dir(module_dir)
    update_module_ini(module_dir)
    clean_module_dir(module_dir)
    return True

def compile_all_modules(build_modules: Path):
    dirs = [d for d in build_modules.iterdir() if d.is_dir() and not d.name.startswith(('.', '__'))]
    print(f"Found {len(dirs)} modules")
    for d in dirs:
        process_module(d)

def create_spec(config: BuildConfig):
    main_abs = str(config.main_py.absolute()).replace('\\', '\\\\')
    modules_abs = str((config.build_temp / "modules").absolute()).replace('\\', '\\\\')
    project_abs = str(config.project_root.absolute()).replace('\\', '\\\\')

    spec = f'''# -*- coding: utf-8 -*-
a = Analysis(
    [r"{main_abs}"],
    pathex=[r"{project_abs}"],
    binaries=[],
    datas=[(r"{modules_abs}", "modules")],
    hiddenimports={json.dumps(HIDDEN_IMPORTS)},
    excludes=["test", "tests", "_test", "_tests"],
    optimize=2
)
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="backend",
    console=True,
    debug=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
)
'''
    config.spec_file.write_text(spec, encoding='utf-8')
    print(f"Created spec: {config.spec_file}")

def run_pyinstaller(config: BuildConfig):
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--distpath", str(config.dist_dir),
        "--workpath", str(config.project_root / "build" / "pyinstaller"),
        "--noconfirm", "--clean",
        str(config.spec_file)
    ]
    print("\nRunning PyInstaller...")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding='utf-8')
    if result.returncode != 0:
        print("PyInstaller failed:\n", result.stderr[-500:])
        return False
    return True

def main():
    project_root = Path(__file__).parent.absolute()
    config = BuildConfig(project_root)

    print("=== Windows-only Build (Cython + PyInstaller) ===")

    if not config.src_modules.exists():
        print("ERROR: src/modules not found")
        return
    if not config.main_py.exists():
        print("ERROR: src/main.py not found")
        return

    # Clean
    for p in [config.dist_dir, config.project_root / "build"]:
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)

    # Setup
    setup_dirs(config)
    build_modules = config.build_temp / "modules"
    copy_modules(config.src_modules, build_modules)

    # Compile
    print("\nCompiling modules to .pyd...")
    compile_all_modules(build_modules)

    # Package
    create_spec(config)
    if not run_pyinstaller(config):
        return

    # Clean up
    config.spec_file.unlink(missing_ok=True)
    shutil.rmtree(config.build_temp, ignore_errors=True)

    print("\nBuild succeeded! Output in /dist")

if __name__ == "__main__":
    main()
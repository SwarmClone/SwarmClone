import sys
import subprocess
from pathlib import Path

def main():
    project_root = Path(__file__).parent.absolute()
    print("🚀 开始打包")

    subprocess.run([sys.executable, "-m", "pip", "install", "nuitka", "-q"], check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "-e", str(project_root)], check=True)

    cmd = [
        sys.executable, "-m", "nuitka",
        "--onefile",
        "--output-dir=dist",
        "--remove-output",
        "--follow-imports",
        "--include-package=src",
        "--include-package=ruamel.yaml",
        "--include-package=fastapi",
        "--include-package=uvicorn",
        "--include-package=pydantic",
        "--include-data-files=config.yml=config.yml",
        "--python-flag=no_site",
        "--noinclude-setuptools-mode=nofollow",
        "--noinclude-pytest-mode=nofollow",
        "--output-filename=backend.exe",
        str(project_root / "src/main.py")
    ]

    print("📦 编译中 (可能需要几分钟)...")
    subprocess.run(cmd, cwd=project_root, check=True)

    print("\n✅ 打包成功!")
    print("📁 输出文件: dist/backend.exe")

if __name__ == "__main__":
    main()
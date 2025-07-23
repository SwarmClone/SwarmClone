# SwarmClone: Build Your Open-Source AI Virtual Streamer
<div align="center">
<img src="./assets/logo.png" width="200" height="200" />
<br>
<a href="../README.md">简体中文</a> | <strong>English</strong>
<br>
<h2>A Fully Open-Source, Highly Customizable Framework for AI Virtual Streamer Development</h2>
<!- Do not delete this blank line ->

![STARS](https://img.shields.io/github/stars/SwarmClone/SwarmClone?color=yellow&label=Github%20Stars)
[![LICENSE](https://img.shields.io/badge/LICENSE-GPLV3-red)](https://github.com/SwarmClone/SwarmClone/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10~3.12-blue.svg)](https://www.python.org)
[![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)]()
[![QQ Group](https://custom-icon-badges.demolab.com/badge/QQ%20Group-1048307485-00BFFF?style=flat&logo=tencent-qq)](https://qm.qq.com/q/8IUfgmDqda)

</div>

---

# Introduction

SwarmClone is a fully open-source-code, highly customizable framework for developing AI-powered virtual streamers. It provides a comprehensive solution for building intelligent virtual streamers capable of real-time interaction on major streaming platforms like Bilibili and Twitch, while maintaining flexibility and extensibility.

### Key Features
1. ✅ **Self-Controlled Architecture**: Fully open-source from core logic to application layer
2. ✅ **Flexible AI Model Support**: Use our MiniLM2 language model or integrate third-party LLMs (ChatGPT, Claude, etc.) via local/API calls
3. ✅ **Comprehensive Streaming Features**: Real-time danmu interaction, gift response, viewer mentions, and core streaming scenarios
4. ✅ **Modular Design**: Components can be freely replaced for custom implementations

---

# Technology Stack & Roadmap
1) LLM Development ([MiniLM2](https://github.com/swarmclone/MiniLM2)) *Completed*
2) Fine-Tuning (Data: Modified COIG-CQIA etc.) *Stage Complete*
3) Virtual Avatar (Character Setup: see `设定.txt`) *In Progress*
4) Streaming Display (Format: Unity-driven Live2D) *In Progress*
5) System Integration (LLM, TTS, Avatar, STT coordination) *In Progress*
6) Platform Integration (Bilibili/Twitch)
7) Advanced Features:
    - Long-term Memory (RAG)
    - Web-connected RAG
    - Active Interaction (comments/DMs)
    - Multimodal Capabilities (visual/audio)
    - Special Effects (animations/emotes)
    - Singing Voice Synthesis
    - Game Integration (Minecraft, No Man's Sky)

---

# Quick Start
#### Prerequisites:
- Linux or WSL environment (Ubuntu 22.04 LTS recommended)
- Python 3.10~3.12 (Avoid newer versions due to compatibility risks)
- CMake 3.26+
- CUDA 11.6+
- Node.js 22.0+ (Latest LTS recommended)

⚠️ **Windows Users**: Install [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install) and run within WSL.

### 1. Clone Repository & Prepare:
   ```console
   git clone https://github.com/SwarmClone/SwarmClone.git
   cd SwarmClone
   git submodule update --init
   ```
   > 💡 Reserve at least 10GB disk space for local model deployments

### 2. Install System Dependencies:
   **Ubuntu/Debian**
   ```console
   sudo apt update
   sudo apt install -y build-essential python3 python3-venv python3-pip cmake \
     libgl1-mesa-dev libglu1-mesa-dev freeglut3-dev git wget
   ```
   **Fedora/CentOS/RHEL**
   ```console
   sudo dnf install -y gcc gcc-c++ make python3 python3-virtualenv python3-pip cmake mesa-libGL-devel mesa-libGLU-devel freeglut-devel git wget
   ```

   **Arch Linux**
   ```console
   sudo pacman -Sy --noconfirm base-devel python python-pip cmake mesa glu freeglut git wget
   ```
   

### 3. Configure Python Environment:
   ```console
   python3 -m venv .venv
   source .venv/bin/activate
   pip install uv
   pip install --upgrade pip setuptools wheel
   UV_TORCH_BACKEND=auto pip install torch torchaudio
   uv sync --group linux --active --no-build-isolation
   ```
   > 💡 For QQ bot functionality: `uv pip install ncatbot`

### 4. Configure Node.js:
   ```console
   cd panel
   npm install
   npm run build
   ```

### 5. Launch Application:
   ```console
   cd ..  # Return to project root
   python -m swarmclone
   ```
   Access the web control panel via the URL provided in terminal.

---

# Contribution Guidelines
Join our developer community:
- QQ Group: 1017493942

> 💡 Whether you're a framework developer, model trainer, frontend/graphics engineer, UI/UX designer, or tester – if you're passionate about AI, virtual streaming, and open-source development, SwarmClone welcomes your expertise!

---

# Open-Source License
Licensed under **[GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.en.html)**  
Full text: [LICENSE](/LICENSE)

**By using, modifying, or distributing this project, you agree to comply with all GPLv3 terms.**

**Important Notice:** 
We uphold the spirit of open-source. Any misuse of this project's code for harmful activities - including closed-source commercialization, patent trolling, or other actions damaging to the community - violates our license and will face legal repercussions and community sanctions.
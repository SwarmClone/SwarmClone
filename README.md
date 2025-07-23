# SwarmClone 蜂群克隆计划：打造你的开源AI虚拟主播
<div align="center">
<img src="docs/assets/logo.png" width="200" height="200" />
<br>
<a href="./docs/README_en.md">English</a>
<br>
<h2>一个完全开源、可高度定制的AI虚拟主播开发框架</h2>
<!-下面这行空行千万别删->

![STARS](https://img.shields.io/github/stars/SwarmClone/SwarmClone?color=yellow&label=Github%20Stars)
[![LICENSE](https://img.shields.io/badge/LICENSE-GPLV3-red)](https://github.com/SwarmClone/SwarmClone/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10~3.12-blue.svg)](https://www.python.org)
[![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)]()
[![QQ群](https://custom-icon-badges.demolab.com/badge/QQ群-1048307485-00BFFF?style=flat&logo=tencent-qq)](https://qm.qq.com/q/8IUfgmDqda)
</div>

---

# 简介

这是一个代码完全开源、可高度定制的AI虚拟主播开发框架，致力于为开发者和研究者提供构建智能虚拟主播的全套解决方案。我们的目标是打造一个能够在B站、Twitch等主流直播平台实现高质量实时互动的AI主播系统，同时保持框架的灵活性和可扩展性。

### 特色
1. ✅**自主可控的核心架构**：从底层交互逻辑到上层应用全部开源，开发者可以完全掌控系统行为
2. ✅**灵活的AI模型支持**：既可以使用我们自主研发的MiniLM2语言模型，也能轻松接入ChatGPT、Claude等第三方LLM，支持本地/API调用
3. ✅**完善的直播功能**：支持弹幕实时互动、礼物响应、观众点名等核心直播场景
4. **模块化设计理念**：各功能组件可自由替换，方便开发者按需定制

---

# 技术栈与技术路线
1) 大语言模型搭建（见[MiniLM2](https://github.com/swarmclone/MiniLM2)）*已基本完成*
2) 微调（数据来源：魔改COIG-CQIA等）*阶段性完成*
3) 虚拟形象（设定：见`设定.txt`）*进行中*
4) 直播画面（形式：Unity驱动的Live2D）*进行中*
5) 技术整合（对语言大模型、语音模型、虚拟形象、语音输入等，统一调度）*进行中*
6) 接入直播平台
7) 精进：
    - 长期记忆RAG
    - 联网RAG
    - 与外界主动互动（发评论/私信？）
    - 多模态（视觉听觉，甚至其他？）
    - 整活（翻滚/b动静等）
    - 唱歌
    - 玩Minecraft、无人深空等游戏

---

# 快速开始
### Python 部分
#### 先决条件：
- 使用Linux或wsl运行环境（推荐Ubuntu 22.04 LTS）
- Python 3.10~3.12（不建议使用过高的版本，以免发生兼容性问题）
- Cmake 3.26+
- CUDA 11.6+
- Node.js 22.0+（推荐直接使用最新版）


如果您是`Windows`用户，您需要安装[WSL2](https://learn.microsoft.com/zh-cn/windows/wsl/install)，并在`WSL2`中使用本项目.

1. 安装[uv](https://docs.astral.sh/uv/)：
   ```console
   pip install uv
   ```
2. 克隆本项目并准备部署：

   请确保您的磁盘中有足够的可用空间.

   如果您需要在本地部署所有模型，我们建议您至少留出10GB可用空间。

   ```console
   git clone https://github.com/SwarmClone/SwarmClone.git
   cd SwarmClone
   git submodule update --init
   ```
3. 运行项目环境搭建脚本：

   ```console
   chmod +x install-dev.sh && ./scripts/install-dev.sh
   ```
   该脚本将自动安装所有依赖项并初始化`python`虚拟环境。
3. 若需要使用qqbot功能，你还需要安装`ncatbot`：
   ```console
   uv pip install ncatbot
   ```
   注意此处使用pip是因为ncatbot与其他依赖有已知冲突，若后续使用出现问题请发issue。

### Node.js 部分
您需要安装Node.js和npm，可通过`npm --version`验证Node.js可用。
首先，下载Panel：
```console
git submodule init
git submodule update
```
然后，进入Panel目录并安装依赖：
```console
cd panel
npm install
npm run build
```
### 启动项目
首先，回到项目根目录（`panel`目录的父目录）
```console
python -m swarmclone
```
随后进入终端给出的网址即可引入网页控制端。

# 如何参与开发？
- 您可以加入我们的开发QQ群：1017493942

如果你对AI、虚拟主播、开源开发充满热情，无论你是框架开发者、模型训练师、前端/图形工程师、产品设计师，还是热情的测试者，蜂群克隆（SwarmClone）都欢迎你的加入！让我们共同创造下一代开源AI虚拟直播系统！


# 项目开源协议

本项目采用 [**GNU General Public License v3.0**](https://www.gnu.org/licenses/gpl-3.0.en.html)作为开源许可证。  
完整许可证文本请参阅 [**LICENSE**](/LICENSE) 文件。

**在您复制、修改或分发本项目时，即表示您同意并愿意遵守 GPLv3 的全部条款。**

**注意**：GPLv3 允许商业使用、修改和分发，但需遵守许可证条款（如保留版权声明、提供源代码等）。  
任何使用行为均需遵循 GPLv3 的完整规定。

**特别提醒：请尊重开源精神，勿将本项目代码用于闭源倒卖、专利钓鱼或其他损害社区利益的行为。违者将承担相应法律责任并受到社区谴责。**
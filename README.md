<div align="center">
<img src="docs/assets/heading.png"/>
<br><br>
一个完全开源、可高度定制的AI虚拟主播开发框架
<br><br>
<!-下面这行空行千万别删->

![STARS](https://img.shields.io/github/stars/SwarmClone/SwarmCloneBackend?color=yellow&label=Github%20Stars)
[![LICENSE](https://img.shields.io/badge/LICENSE-GPLV3-red)](https://github.com/SwarmClone/SwarmCloneBackend/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org)
[![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)]()
[![QQ群](https://custom-icon-badges.demolab.com/badge/QQ群-1048307485-00BFFF?style=flat&logo=tencent-qq)](https://qm.qq.com/q/8IUfgmDqda)
<br><br>
<strong>简体中文</strong> | <a href="./docs/README_en.md">English</a>
</div>

# 简介

这是一个代码完全开源、可高度定制的AI虚拟主播开发框架，致力于为开发者和研究者提供构建智能虚拟主播的全套解决方案。我们的目标是打造一个能够在B站、Twitch等主流直播平台实现高质量实时互动的AI主播系统，同时保持框架的灵活性和可扩展性。

### 特色
1. ✅**自主可控的核心架构**：从底层交互逻辑到上层应用全部开源，开发者可以完全掌控系统行为
2. ✅**灵活的 AI 模型支持**：适配 OpenAI Chat Completion API，轻松接入 Qwen、DeepSeek 等大模型，也可使用 Ollama 本地部署模型
3. ✅**完善的直播功能**：支持弹幕实时互动等核心直播场景
4. **模块化设计理念**：各功能组件可自由替换，方便开发者按需定制

---

# 技术栈与技术路线
1) 基础大语言模型搭建（技术探索项目，见[MiniLM2](https://github.com/SwarmClone/MiniLM2)）*已基本结束*
2) 虚拟形象设定 *进行中*
3) 直播画面设计 *进行中*
4) 技术整合（对语言大模型、语音模型、虚拟形象、语音输入等，统一调度）*进行中*
5) 接入直播平台
6) 精进：
    - 长期记忆 RAG
    - 联网 RAG
    - 与外界主动互动（发评论/私信？）
    - 多模态（视觉听觉，甚至其他？）
    - 整活（翻滚/b动静等）
    - 唱歌
    - 玩 Minecraft 、无人深空等游戏

---

# 快速开始
#### 先决条件：
- xxx
- xxx
- xxx

### 1. 克隆本项目并准备部署：

请确保您的磁盘中有足够的可用空间.


```console
git clone https://github.com/SwarmClone/SwarmCloneBackend.git
```

### 2. 安装系统依赖：

如果您此前安装过这些系统依赖，您可以选择暂时跳过本步骤。若后续操作出现缺少依赖项的报错，您可以在这里核对您是否安装了所有依赖项。

#### Linux 系统依赖

若您使用的是 Linux 系统或 WSL 子系统，请根据您的 Linux 发行版选择相应命令执行：

**Ubuntu/Debian**

```console


```

**Fedora/CentOS/RHEL**
```console


```

**Arch Linux**
```console


```
>💡对于使用其他包管理工具的发行版，请根据您的发行版选择类似的包。

#### Windows 系统依赖

若您使用的是 Windows 系统，您需要安装 Visual Studio，并在安装时勾选 C 语言相关选项，确保安装了可用的 C 语言编译器。然后，安装`xxx`：
```console


```

### 3. 设置 Python 环境
```console

```
>💡在 Windows 系统下 deepspeed 的安装有可能引发错误，声称无法导入 torch，可以在 powershell 下运行 `$env:DS_BUILD_OPS="0"` 以设置环境变量然后重新运行上述命令解决。

### 5. 启动项目
在项目根目录执行下面的命令：
```console
uv run start
```

---

# 如何参与开发？
- 您可以加入我们的开发QQ群：1017493942

如果你对 AI 、虚拟主播、开源开发充满热情，无论你是框架开发者、模型训练师、前端/图形工程师、产品设计师，还是热情的测试者，蜂群克隆（SwarmClone）都欢迎你的加入！让我们共同创造下一代开源AI虚拟直播系统！

---

# 项目开源协议

本项目采用 [**Apache-2.0 license**](https://www.apache.org/licenses/LICENSE-2.0.html)作为开源许可证。  
完整许可证文本请参阅 [**LICENSE**](/LICENSE) 文件。

**在您复制、修改或分发本项目时，即表示您同意并愿意遵守 Apache-2.0 license 的全部条款。**

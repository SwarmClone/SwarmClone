# SwarmClone 蜂群克隆计划：打造你的开源AI虚拟主播

<div align="center">
<img src="docs/assets/logo.png" width="200" height="200" />
<br>
    ![简体中文](../README.md)
<h3>一个完全开源、可高度定制的AI虚拟主播开发框架</h3>
</div>



## 项目简介

SwarmClone 是一个代码完全开源、可高度定制的AI虚拟主播开发框架，致力于为开发者和研究者提供构建智能虚拟主播的全套解决方案。我们的目标是打造一个能够在B站、Twitch等主流直播平台实现高质量实时互动的AI主播系统，同时保持框架的灵活性和可扩展性。

作为开源社区项目，SwarmClone采用模块化架构设计，核心组件全部自主研发，不依赖现有的VTuber框架。我们相信，只有掌握核心技术，才能真正实现虚拟主播行为的深度定制和优化。项目目前已完成基础语言模型MiniLM2的开发，正在进行虚拟形象系统和直播交互模块的研发。

**技术亮点：**

1. ✅**自主可控的核心架构**：从底层交互逻辑到上层应用全部开源，开发者可以完全掌控系统行为
2. ✅**灵活的AI模型支持**：既可以使用我们自主研发的MiniLM2语言模型，也能轻松接入ChatGPT、Claude等第三方LLM，支持本地/API调用
3. ✅**完善的直播功能**：支持弹幕实时互动、礼物响应、观众点名等核心直播场景
4. **模块化设计理念**：各功能组件可自由替换，方便开发者按需定制

## 技术栈与技术路线

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


## 如何开始

### Python 部分

您需要安装Python3.10，并安装[uv](https://docs.astral.sh/uv/)：

```console
pip install uv
```

随后安装torch以及torchaudio：

- Linux：

```console
UV_TORCH_BACKEND=auto uv pip install torch torchaudio
```

```console
uv sync --group linux
```

若需要使用qqbot功能，你还需要安装`ncatbot`：

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

## 如何参与开发？

- 您可以加入我们的开发QQ群：1017493942

如果你对AI、虚拟主播、开源开发充满热情，无论你是框架开发者、模型训练师、前端/图形工程师、产品设计师，还是热情的测试者，SwarmClone 都欢迎你的加入！让我们共同创造下一代开源AI虚拟直播系统！

## 项目开源协议

本项目采用[**木兰公共许可证第2版**(MulanPubL-2.0)](https://license.coscl.org.cn/MulanPubL-2.0)作为项目的开源协议。这是一份符合OSI认证的开源许可证，具有以下重要条款：

### 重要声明

1. **严禁任何形式的源代码倒卖和盗卖行为**
   - 本项目所有代码和资源仅供学习和研究使用
   - 任何个人或组织不得对本项目代码进行商业化倒卖
   - 发现违规行为将依法追究责任

2. **使用条款**
   - 允许自由使用、修改和分发代码
   - 允许在遵守开源协议的情况下用于商业项目
   - 修改后的代码必须保持相同许可证
   - 必须保留原始版权声明

3. **免责声明**
   - 本项目不提供任何形式的担保
   - 使用者自行承担使用风险

完整许可证文本请参阅[LICENSE](/LICENSE)文件。我们鼓励开发者遵守开源精神，共同维护健康的开源生态。

**特别提醒**：任何违反木兰许可证的行为，特别是源代码倒卖行为，都将受到社区和法律的严肃对待。请尊重开源开发者的劳动成果。
# CONTRIBUTING.md
## Start contributing to `SwarmClone`!

<div align="center">
<strong>English</strong> | <a href="./.github/CONTRIBUTING_zh-cn.md">简体中文</a>
</div>

## 🤝 Welcome Contributors

Welcome to **SwarmClone**! We are a fully open-source AI virtual streamer development framework, and we're excited that you want to contribute to the project.

### Ways to Contribute

We welcome contributions in any form, including but not limited to:
- 🐛 **Bug Reports**: Help us find and fix issues
- 💡 **Feature Requests**: Propose new ideas and features for the project
- 📚 **Documentation Improvements**: Improve documentation to help other users better understand and use the project
- 🔧 **Source Code Contributions**: Fix bugs or implement new features
- ❓ **Help Answer Community Questions**: Assist other users in Issues or QQ group

## 📋 Contribution Process

### 1. Create an Issue
Before starting any significant work, please [create an Issue](https://github.com/SwarmClone/SwarmCloneBackend/issues) to describe the problem you plan to solve or the feature you want to add.

### 2. Fork the Repository
Click the "Fork" button in the upper right corner of the GitHub page to create your personal copy of the project.

### 3. Clone Your Fork
```bash
git clone https://github.com/your-username/SwarmCloneBackend.git
cd SwarmClone
```

### 4. Create a Feature Branch
```bash
git checkout -b feat/your-new-feature
# or
git checkout -b fix/description-of-fixed-issue
```

### 5. Make Changes and Test
Make code changes locally and ensure:
- Code follows the project's coding standards
- Appropriate tests are added or updated
- All tests pass
- Relevant documentation is updated

### 6. Commit Changes
We use **Conventional Commits** specification. Please carefully read the commit message specification section below.

### 7. Push Branch
```bash
git push origin your-branch-name
```

### 8. Create Pull Request
Click the "New Pull Request" button on your Fork page and select the correct base branch and target branch.

## 📝 Commit Message Specification

### Language Requirements
**Important**: All commit messages must be written in **Simplified Chinese**, **Traditional Chinese**, or **English**. If PR or commit messages use other languages, code reviewers have the right to request detailed explanation of PR or commit content in English or Chinese.

### Commit Format
We follow the **Conventional Commits** specification with the following format:

```
<type>[optional scope]: <description>

[optional body]

[optional footer]
```

### Commit Types

| Type | Description | Example |
|------|-------------|---------|
| `feat` | New feature | `feat: add user login functionality` |
| `fix` | Bug fix | `fix: resolve homepage data loading issue` |
| `docs` | Documentation updates | `docs: update API interface documentation` |
| `style` | Code formatting changes | `style: adjust code indentation` |
| `refactor` | Code refactoring | `refactor: optimize user module structure` |
| `test` | Test related | `test: add payment flow unit tests` |
| `chore` | Build process or tool changes | `chore: update webpack configuration` |
| `build` | Build system or dependency updates | `build: upgrade to React 18` |
| `ci` | CI configuration changes | `ci: add automated testing pipeline` |
| `perf` | Performance improvements | `perf: optimize image lazy loading logic` |

### Commit Examples

**English Example**:
```
feat(streaming): optimize danmaku interaction feature

- Implement danmaku message parser
- Add danmaku reply logic
- Update relevant test cases

Related to issue: #123
```

**中文示例**：
```
fix(api): 修复连接池内存泄漏问题

- 优化资源清理流程
- 添加连接超时处理
- 更新单元测试

修复 #456
```

## 🐛 Reporting Issues

When reporting issues, please include the following information:

### Bug Report Template
```markdown
## Problem Description
Clearly and detailedly describe what the problem is

## Reproduction Steps
1. 
2. 
3. 

## Expected Behavior
Describe what you expected to happen

## Actual Behavior
Describe what actually happened

## Environment Information
- Operating System:
- Python Version:
- Other relevant environment information:

## Logs/Screenshots
If available, please provide relevant logs or screenshots
```

## 💡 Feature Requests

### Feature Request Template
```markdown
## Feature Description
Clearly and detailedly describe the feature you want to add

## Problem Solved
What pain points or problems does this feature solve?

## Proposed Implementation
If you have implementation ideas, describe them here

## Alternative Considerations
What alternatives have you considered?

## Additional Context
Add any other relevant context or screenshots
```

## 🔧 Development Environment Setup

Refer to the "Quick Start" section in the project's [README.md](README.md) file for detailed development environment setup.

## 📚 Code Standards

### Python Code
- Follow PEP 8 standards
- Use meaningful variable and function names
- Add appropriate type annotations
- Write clear docstrings

### Documentation
- Use clear, accurate language
- Follow existing documentation style in the project
- Add corresponding documentation for new features

## 📄 License

By contributing code to this project, you agree that your contributions will be licensed under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0.html).
# Git 项目管理完整指南

**适用于 GitHub Desktop 用户**

本指南将教你如何使用 Git 和 GitHub Desktop 专业地管理 Memosyne 项目。

---

## 目录

- [Git 基础概念](#git-基础概念)
- [初始化项目](#初始化项目)
- [日常工作流程](#日常工作流程)
- [分支管理](#分支管理)
- [发布版本](#发布版本)
- [最佳实践](#最佳实践)
- [常见问题](#常见问题)

---

## Git 基础概念

### 什么是 Git？

Git 是一个**版本控制系统**，可以：
- 📝 记录每次代码修改
- ⏮️ 回退到任何历史版本
- 🔀 支持多人协作
- 🏷️ 给重要版本打标签

### 核心概念

```
工作区 (Working Directory)          暂存区 (Staging Area)          本地仓库 (Local Repository)          远程仓库 (Remote Repository)
     你的文件                    -->      准备提交的文件          -->         本地历史记录            -->           GitHub 上的备份
```

**关键术语**：

| 术语 | 含义 | 示例 |
|-----|------|-----|
| **Repository (仓库)** | 项目的版本历史库 | `Memosyne` 项目 |
| **Commit (提交)** | 一次代码快照 | "添加 API 功能" |
| **Branch (分支)** | 平行开发线 | `main`, `feature/api` |
| **Remote (远程)** | GitHub 上的仓库 | `origin` |
| **Push (推送)** | 上传到 GitHub | 发布代码 |
| **Pull (拉取)** | 从 GitHub 下载 | 同步最新代码 |
| **Merge (合并)** | 合并分支 | 合并功能到主分支 |

---

## 初始化项目

### 步骤 1：创建 .gitignore 文件

**作用**：告诉 Git 忽略哪些文件（如虚拟环境、临时文件）

创建 `.gitignore` 文件：

```gitignore
# Python 相关
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# 虚拟环境
.venv/
venv/
ENV/
env/

# IDE 相关
.vscode/
.idea/
*.swp
*.swo
.DS_Store

# 环境变量（包含密钥，不能提交！）
.env

# 数据文件（可选，看你是否要提交数据）
data/output/
*.csv

# 临时文件
*.log
*.tmp
temp/
```

### 步骤 2：在 GitHub Desktop 中创建仓库

1. **打开 GitHub Desktop**
2. **点击 "File" → "Add Local Repository"**
3. **选择你的项目文件夹** (`Memosyne`)
4. **如果提示 "not a git repository"，点击 "create a repository"**

配置信息：
- **Name**: `Memosyne`
- **Description**: `基于 LLM 的术语处理和 Quiz 解析工具包`
- **Local Path**: 你的项目路径
- **Initialize with README**: 取消勾选（因为已有 README.md）
- **Git Ignore**: Python
- **License**: MIT

点击 **"Create Repository"**

### 步骤 3：第一次提交（Initial Commit）

在 GitHub Desktop 中：

1. **左侧会显示所有文件** - 这些是"未提交的更改"
2. **勾选要提交的文件**（通常全选）
3. **在左下角填写提交信息**：
   - **Summary (必填)**: `Initial commit - Memosyne v2.0`
   - **Description (可选)**:
     ```
     - 完整的项目架构
     - MMS 和 ExParser 功能
     - 编程 API
     - 完善的文档
     ```
4. **点击 "Commit to main"**

✅ 现在你的本地仓库有了第一个提交！

### 步骤 4：发布到 GitHub

1. **点击 "Publish repository"**
2. **配置远程仓库**：
   - **Name**: `Memosyne`
   - **Description**: `基于 LLM 的术语处理和 Quiz 解析工具包`
   - **Keep this code private**:
     - ✅ 如果项目包含敏感信息（推荐）
     - ❌ 如果想公开（注意：.env 已在 .gitignore 中）
3. **点击 "Publish Repository"**

✅ 现在你的项目已经在 GitHub 上了！

---

## 日常工作流程

### 标准工作流

```
1. 修改代码
    ↓
2. 查看更改
    ↓
3. 暂存更改 (Stage)
    ↓
4. 提交 (Commit)
    ↓
5. 推送到 GitHub (Push)
```

### 详细步骤

#### 1. 修改代码后

打开 GitHub Desktop，你会看到：
- **Changes (X)** - X 表示修改了多少文件
- 左侧列表显示所有修改的文件
- 右侧显示具体修改内容（红色 = 删除，绿色 = 新增）

#### 2. 检查更改

**在右侧查看 diff（差异）**：
- ✅ 确认修改内容正确
- ✅ 没有提交敏感信息（API Key 等）
- ✅ 没有提交临时文件

#### 3. 编写提交信息

**好的提交信息**：

```
✅ 好的示例：

Summary: "添加批量处理功能"
Description:
- 支持一次处理多个 CSV 文件
- 添加进度条显示
- 更新 API 文档

---

Summary: "修复项目根目录检测 bug"
Description:
修复 _find_project_root() 函数查找错误的 data/ 目录问题

---

Summary: "更新 README 和架构文档"
Description:
- 删除已移除文件的引用
- 添加 Git 使用指南链接
```

**❌ 不好的示例**：

```
Summary: "update"  ❌ 太模糊
Summary: "修改了一些东西"  ❌ 没有具体说明
Summary: "asdfasdf"  ❌ 无意义
```

#### 4. 提交

1. **勾选要提交的文件**（通常全选）
2. **填写 Summary**（必填，简短描述）
3. **填写 Description**（可选，详细说明）
4. **点击 "Commit to main"**

#### 5. 推送到 GitHub

提交后，顶部会显示 **"Push origin"**

**点击 "Push origin"** 上传到 GitHub

⚠️ **注意**：如果长时间不 Push，本地会积累很多提交，建议及时推送！

---

## 分支管理

### 什么时候用分支？

| 场景 | 分支名 | 说明 |
|-----|-------|-----|
| 添加新功能 | `feature/api-batch` | 不影响主分支 |
| 修复 bug | `fix/path-detection` | 隔离修复 |
| 重构代码 | `refactor/v2` | 大规模改动 |
| 实验性功能 | `experiment/web-ui` | 可能不会合并 |

### 创建分支

**在 GitHub Desktop 中**：

1. **点击顶部 "Current Branch" → "New Branch"**
2. **输入分支名**，如 `feature/batch-processing`
3. **点击 "Create Branch"**

现在你在新分支上工作，不会影响 `main` 分支！

### 切换分支

**点击 "Current Branch" → 选择目标分支**

⚠️ **注意**：切换前确保当前更改已提交！

### 合并分支

**场景**：功能开发完成，想合并到 `main`

1. **切换到 `main` 分支**
2. **点击 "Branch" → "Merge into Current Branch"**
3. **选择要合并的分支**（如 `feature/batch-processing`）
4. **点击 "Merge"**

如果有冲突：
- GitHub Desktop 会提示哪些文件冲突
- 在编辑器中手动解决冲突
- 标记为已解决
- 提交合并

### 删除分支

**合并后可以删除旧分支**：

1. **点击 "Branch" → "Delete"**
2. **选择要删除的分支**
3. **确认删除**

---

## 发布版本

### 版本号规范（Semantic Versioning）

格式：`vMAJOR.MINOR.PATCH`

- **MAJOR (主版本)**：重大变更，不兼容旧版
  - 例：v1.0.0 → v2.0.0
- **MINOR (次版本)**：新功能，向后兼容
  - 例：v2.0.0 → v2.1.0
- **PATCH (补丁版本)**：bug 修复
  - 例：v2.1.0 → v2.1.1

### 发布步骤

#### 1. 在本地打标签

**GitHub Desktop 不直接支持打标签，需要使用命令行**：

打开终端，进入项目目录：

```bash
# 查看当前版本
git tag

# 创建新标签
git tag -a v2.0.0 -m "Release v2.0.0 - 完整重构版本"

# 推送标签到 GitHub
git push origin v2.0.0
```

#### 2. 在 GitHub 上创建 Release

1. **访问 GitHub 仓库页面**
2. **点击右侧 "Releases" → "Create a new release"**
3. **填写信息**：

   - **Tag**: 选择 `v2.0.0`
   - **Release title**: `Memosyne v2.0.0 - 完整重构版本`
   - **Description**:
     ```markdown
     ## ✨ 新特性

     - 全新架构：采用 SOLID 原则和分层设计
     - 编程 API：`process_terms()` 和 `parse_quiz()`
     - 双 Provider 支持：OpenAI 和 Anthropic
     - 类型安全：Pydantic 2.x 数据验证

     ## 🔧 修复

     - 修复项目根目录检测 bug
     - 修复 Pydantic v2 兼容性问题

     ## 📚 文档

     - 新增 API_GUIDE.md
     - 新增 ARCHITECTURE.md
     - 新增 GIT_GUIDE.md

     ## 📦 安装

     ```bash
     pip install -r requirements.txt
     ```

     ## 🚀 快速开始

     ```python
     from memosyne import process_terms
     result = process_terms(input_csv="221.csv", start_memo_index=221)
     ```
     ```

4. **点击 "Publish release"**

✅ 现在用户可以下载你的 v2.0.0 版本了！

---

## 最佳实践

### ✅ DO（应该做的）

1. **频繁提交**
   - 小步快走，每完成一个小功能就提交
   - 一天至少提交 1-3 次

2. **清晰的提交信息**
   ```
   Summary: 动词 + 名词（如"添加 API 功能"）
   Description: 详细说明修改内容
   ```

3. **及时推送**
   - 每天结束工作前 Push 一次
   - 重要修改立即 Push

4. **使用 .gitignore**
   - 绝不提交 `.env` 文件
   - 绝不提交虚拟环境
   - 绝不提交临时文件

5. **定期查看历史**
   - 点击 "History" 查看提交记录
   - 学习自己的开发轨迹

### ❌ DON'T（不应该做的）

1. **不要提交未测试的代码**
   - 确保代码能运行再提交

2. **不要提交敏感信息**
   - API Key
   - 密码
   - 个人信息

3. **不要使用无意义的提交信息**
   - ❌ "update"
   - ❌ "fix"
   - ❌ "asdf"

4. **不要直接在 main 分支做大改动**
   - 创建新分支
   - 测试完成后再合并

5. **不要长时间不同步**
   - 定期 Pull 最新代码
   - 定期 Push 本地代码

---

## 常见场景

### 场景 1：我改错了，想撤销

**在提交之前**（Changes 中）：

1. **右键点击文件 → "Discard Changes"**
2. 确认撤销

**已经提交，但还没 Push**：

1. **点击 "History"**
2. **右键点击要撤销的提交 → "Revert This Commit"**

### 场景 2：我想看某个历史版本

1. **点击 "History"**
2. **点击想查看的提交**
3. **右侧会显示当时的代码**

### 场景 3：两台电脑同步代码

**电脑 A**：
```
修改代码 → Commit → Push
```

**电脑 B**：
```
点击 "Fetch origin" → 点击 "Pull origin"
```

### 场景 4：我想分享项目给别人

**两种方式**：

1. **分享 GitHub 链接**（推荐）
   ```
   https://github.com/你的用户名/Memosyne
   ```
   对方可以：
   - 查看代码
   - Clone（复制）整个项目
   - 提 Issue（问题反馈）

2. **导出 ZIP**
   - GitHub 页面 → "Code" → "Download ZIP"

---

## GitHub Desktop 界面指南

### 主界面元素

```
┌────────────────────────────────────────────┐
│  Current Repository: Memosyne       [main] │  ← 当前仓库和分支
├────────────────────────────────────────────┤
│  Changes (5)  │  History                   │  ← 标签页
├────────────────────────────────────────────┤
│  ☐ file1.py   │  + 10                      │  ← 修改的文件
│  ☑ file2.py   │  - 5                       │  ← 勾选 = 将被提交
│  ☑ README.md  │  ~ 3                       │
├────────────────────────────────────────────┤
│  Summary (required)                        │  ← 提交信息
│  [添加新功能                     ]         │
│                                            │
│  Description (optional)                    │
│  [详细说明修改内容              ]         │
│                                            │
├────────────────────────────────────────────┤
│  [Commit to main]                          │  ← 提交按钮
└────────────────────────────────────────────┘
```

### 顶部工具栏

- **Current Repository**: 切换项目
- **Current Branch**: 切换/创建分支
- **Fetch origin**: 检查远程更新
- **Push origin**: 推送到 GitHub
- **Pull origin**: 拉取远程代码

---

## 进阶：使用命令行

虽然 GitHub Desktop 很方便，但有些操作需要命令行。

### 常用命令

```bash
# 查看状态
git status

# 查看历史
git log --oneline

# 创建并切换分支
git checkout -b feature/new-feature

# 查看所有分支
git branch -a

# 删除本地分支
git branch -d feature/old-feature

# 创建标签
git tag -a v2.0.0 -m "Release v2.0.0"

# 推送标签
git push origin v2.0.0

# 查看远程仓库
git remote -v
```

---

## 快速参考

### 完整工作流 Checklist

- [ ] 1. 打开 GitHub Desktop
- [ ] 2. 切换到正确的分支
- [ ] 3. 点击 "Fetch origin"（检查更新）
- [ ] 4. 如果有更新，点击 "Pull origin"
- [ ] 5. 开始编码
- [ ] 6. 保存文件
- [ ] 7. 在 GitHub Desktop 查看更改
- [ ] 8. 确认修改正确
- [ ] 9. 填写提交信息
- [ ] 10. 点击 "Commit to main"
- [ ] 11. 点击 "Push origin"
- [ ] 12. 完成！

### 提交信息模板

```
Summary: [动词] + [修改内容]

Description:
- 修改点 1
- 修改点 2
- 修改点 3

相关 Issue: #123 (如果有的话)
```

**示例**：

```
Summary: 添加批量处理 API

Description:
- 实现 batch_process() 函数
- 支持并发处理
- 添加进度条显示
- 更新 API 文档

测试: 已通过 100 个文件测试
```

---

## 常见问题 FAQ

### Q1: .env 文件会被提交吗？

**A**: 不会，已在 `.gitignore` 中排除。

### Q2: 我误提交了敏感文件怎么办？

**A**:
1. 立即从 Git 历史中删除（使用 `git filter-branch`）
2. 更换 API Key
3. 推送修复

**预防**：提交前仔细检查！

### Q3: Push 失败说 "rejected"？

**A**: 远程有新提交，需要先 Pull：
1. 点击 "Fetch origin"
2. 点击 "Pull origin"
3. 解决冲突（如果有）
4. 再次 Push

### Q4: 如何备份整个项目？

**A**: GitHub 就是最好的备份！另外：
- 定期 Push 到 GitHub
- 可以 Clone 到另一个文件夹作为本地备份

### Q5: 如何恢复到某个历史版本？

**A**:
1. 点击 "History"
2. 找到目标提交
3. 右键 → "Revert This Commit"

或使用命令行：
```bash
git reset --hard <commit-hash>
```

---

## 下一步

现在你已经掌握了 Git 基础！建议：

1. ✅ **每天至少提交一次**
2. ✅ **查看 GitHub 上的项目页面**，熟悉界面
3. ✅ **尝试创建分支，完成小功能后合并**
4. ✅ **发布第一个 Release（v2.0.0）**
5. ✅ **阅读 [GitHub 官方文档](https://docs.github.com/)**

---

## 参考资源

- [GitHub Desktop 官方文档](https://docs.github.com/en/desktop)
- [Git 官方教程](https://git-scm.com/book/zh/v2)
- [语义化版本规范](https://semver.org/lang/zh-CN/)
- [如何写好 Git 提交信息](https://chris.beams.io/posts/git-commit/)

---

**记住**：Git 是你的时光机，它会保护你的每一行代码！

💡 **最重要的一点**：不要害怕犯错，Git 几乎可以恢复任何东西！

---

**文档版本**: 1.0
**最后更新**: 2025-10-07

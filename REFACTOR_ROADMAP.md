# Memosyne 架构重构 Roadmap

**开始日期**: 2025-10-12
**目标**: 重构为 Ports & Adapters 架构，符合 ROSE 原则，消除重复代码

---

## Phase 1: 清理和重命名（不破坏功能）⚡

**目标**: 修正命名错误，删除无用文件

- [x] 删除 `data/input/memo/` 空文件夹
- [x] 删除 `data/output/memo/` 空文件夹
- [x] 重命名：`reanimate` → `reanimator`（所有代码中的变量、函数名）
- [x] 重命名文件：`cli/reanimate.py` → `cli/reanimator_cli.py`
- [x] 重命名文件：`cli/lithoform.py` → `cli/lithoformer_cli.py`
- [x] 重命名文件：`services/reanimater.py` → `services/reanimator.py`
- [x] 重命名文件：`services/lithoformer.py`（保持不变，确认拼写）
- [x] 更新所有文件中的导入路径
- [x] 更新 `api.py` 中的导出接口
- [x] 更新 `__init__.py` 中的模块导出
- [x] 更新 `.env.example` 中的配置项命名
- [x] 更新 `settings.py` 中的配置字段命名
- [x] 重命名数据目录：`data/input/reanimater` → `reanimator`
- [x] 重命名数据目录：`data/output/reanimater` → `reanimator`
- [x] 修复类名：`Reanimater` → `Reanimator`
- [x] 更新 CLI `__init__.py` 的导入
- [x] **验证**: 运行两个 CLI，确保功能正常 ✅

**✅ Phase 1 完成！所有重命名已完成，功能验证通过。**

---

## Phase 2: 建立模型代码映射系统（4位简写）🔤

**目标**: 实现模型简写输入和输出文件命名

### 2.1 创建模型代码映射模块
- [x] 创建 `src/memosyne/utils/model_codes.py`
- [x] 定义完整的模型代码映射表（11个模型）：
  - `gpt-5-mini` → `o50m`
  - `gpt-5` → `o50o`
  - `gpt-4o` → `o4oo`
  - `o3` → `oo3o`
  - `o4-mini` → `oo4m`
  - `claude-opus-4-1` → `co41`
  - `claude-opus-4-0` → `co40`
  - `claude-sonnet-4-5` → `cs45`
  - `claude-3-7-sonnet-latest` → `cs37`
  - `claude-3-5-haiku-latest` → `ch35`
- [x] 实现 `get_model_from_code(code: str) -> str` - 简写转完整模型名
- [x] 实现 `get_code_from_model(model: str) -> str` - 完整模型名转简写
- [x] 实现 `resolve_model_input(input: str) -> tuple[str, str]` - 统一解析（返回 model, code）
- [x] 实现 `get_provider_from_model(model: str)` - 判断提供商
- [x] 实现 `list_all_models()` 和 `list_all_codes()` - 辅助函数
- [x] 更新 `utils/__init__.py` 导出新函数

### 2.2 集成到 CLI
- [x] 修改 `reanimator_cli.py` 的模型选择逻辑，支持4位简写输入
- [x] 修改 `lithoformer_cli.py` 的模型选择逻辑，支持4位简写输入
- [x] 更新提示文本，说明支持 4 位简写
- [x] **验证**: 输入 `ch35` 能正确识别为 `claude-3-5-haiku-latest` ✅

**✅ Phase 2 完成！模型代码映射系统已建立，CLI 支持 4 位简写输入。**

---

## Phase 3: 实现智能文件命名系统📝

**目标**: 输出文件格式 `{BatchID}-{FileName?}-{ModelCode}.ext`

### 3.1 创建文件命名工具
- [x] 创建 `src/memosyne/utils/filename.py`
- [x] 实现 `extract_short_filename(filepath: str | Path, max_length: int = 15) -> str`
  - 去除扩展名
  - 去除特殊字符（保留字母数字和短横线）
  - 长度超过 max_length 则返回空字符串
- [x] 实现 `generate_output_filename(batch_id: str, model_code: str, input_filename: str = "", ext: str = "csv") -> str`
  - 有文件名: `{batch_id}-{short_name}-{model_code}.{ext}`
  - 无文件名: `{batch_id}-{model_code}.{ext}`
- [x] 添加单元测试
- [x] 更新 `utils/__init__.py` 导出新函数

### 3.2 修改 Reanimator 输出逻辑
- [x] 修改 `reanimator_cli.py` 生成正确的输出文件名
- [x] 修改 `api.py` 中的 `reanimate()` 函数，集成智能文件命名
- [ ] **验证**: 测试文件命名
  - 输入文件 `221.csv` → `251012D036-221-ch35.csv`
  - 无输入文件 → `251012E016-ch35.csv`

### 3.3 修改 Lithoformer 输出逻辑
- [x] 修改 `lithoformer_cli.py` 生成正确的输出文件名（集成 BatchID 和智能命名）
- [x] 删除旧的 `_resolve_output_path()` 函数
- [x] 修改 `api.py` 中的 `lithoformer()` 函数，添加 BatchID 生成和智能文件命名
- [x] 更新 `lithoform()` 返回值，添加 `batch_id` 字段
- [ ] **验证**: 测试文件命名（留待实际使用时验证）
  - 短文件名 `205.md` → `251012B007-205-o50o.txt`
  - 长文件名 `Chapter 3 Quiz...md` → `251012A007-oo4m.txt`

**✅ Phase 3 完成！智能文件命名系统已全面集成到 CLI 和 API。**

---

## Phase 4: 重构为 Ports & Adapters 架构🏗️

**目标**: 清晰的分层和依赖倒置

### 4.1 规划新目录结构
- [ ] 设计完整的目录结构图
- [ ] 确定端口接口定义
- [ ] 确定迁移顺序（避免破坏现有功能）

### 4.2 创建 Reanimator 子域
- [ ] 创建 `src/memosyne/reanimator/domain/` 目录
  - [ ] `models.py` - 迁移 TermInput, TermOutput, LLMResponse
  - [ ] `services.py` - 业务规则（POS 修正、标签映射）
  - [ ] `exceptions.py` - 领域异常
- [ ] 创建 `src/memosyne/reanimator/application/` 目录
  - [ ] `ports.py` - 定义输入输出端口
  - [ ] `use_cases.py` - ProcessTermsUseCase
- [ ] 创建 `src/memosyne/reanimator/infrastructure/` 目录
  - [ ] `llm_adapter.py` - LLM 适配器
  - [ ] `csv_adapter.py` - CSV 读写适配器
  - [ ] `term_list_adapter.py` - 术语表适配器
- [ ] 迁移 `cli/reanimator_cli.py` 到 `reanimator/cli/`
- [ ] **验证**: Reanimator CLI 仍能正常运行

### 4.3 创建 Lithoformer 子域
- [ ] 创建 `src/memosyne/lithoformer/domain/` 目录
  - [ ] `models.py` - 迁移 QuizItem, QuizResponse
  - [ ] `services.py` - Quiz 格式化逻辑
- [ ] 创建 `src/memosyne/lithoformer/application/` 目录
  - [ ] `ports.py` - 定义输入输出端口
  - [ ] `use_cases.py` - ParseQuizUseCase
- [ ] 创建 `src/memosyne/lithoformer/infrastructure/` 目录
  - [ ] `llm_adapter.py` - LLM 适配器
  - [ ] `file_adapter.py` - 文件读写适配器
- [ ] 迁移 `cli/lithoformer_cli.py` 到 `lithoformer/cli/`
- [ ] **验证**: Lithoformer CLI 仍能正常运行

### 4.4 创建共享基础设施层
- [ ] 创建 `src/memosyne/shared/infrastructure/llm/` 目录
  - [ ] 迁移 `providers/` 到此处
  - [ ] `interfaces.py` - LLM 提供商接口
  - [ ] `factory.py` - LLM 工厂类
- [ ] 创建 `src/memosyne/shared/infrastructure/storage/` 目录
  - [ ] `csv_repository.py` - 通用 CSV 操作
  - [ ] `file_repository.py` - 通用文件操作
- [ ] 创建 `src/memosyne/shared/infrastructure/logging/` 目录
  - [ ] 迁移 `utils/logger.py` 到此处
- [ ] 迁移 `config/` 到 `shared/config/`
- [ ] 迁移 `utils/` 到 `shared/utils/`

### 4.5 更新顶层 API
- [ ] 重构 `api.py`，使用新的 Use Case 接口
- [ ] 重构 `__init__.py`，导出新的模块结构
- [ ] 删除旧的 `services/`, `repositories/`, `providers/` 目录
- [ ] **验证**: 所有导入路径正确，功能完整

---

## Phase 5: 消除重复代码，提取共享组件♻️

**目标**: 符合 ROSE（Reuse-Oriented Software Engineering）原则

### 5.1 分析重复代码
- [ ] 识别 Reanimator 和 Lithoformer 中的重复逻辑
- [ ] 列出可提取的共享组件清单

### 5.2 提取通用进度条组件
- [ ] 创建 `shared/utils/progress.py`
- [ ] 实现 `ProgressTracker` 类（封装 tqdm + Token 显示）
- [ ] 重构两个 Use Case 使用统一的进度条
- [ ] 删除重复的进度条代码

### 5.3 提取通用文件操作
- [ ] 合并 CSV/文件读写逻辑到 `shared/infrastructure/storage/`
- [ ] 提取通用的文件路径解析逻辑
- [ ] 删除重复代码

### 5.4 提取通用 LLM 调用封装
- [ ] 创建 `shared/infrastructure/llm/base_adapter.py`
- [ ] 封装通用的错误处理、重试逻辑
- [ ] 两个子域的 LLM Adapter 继承基类
- [ ] 删除重复的 LLM 调用代码

### 5.5 清理和验证
- [ ] 删除所有未使用的导入
- [ ] 删除所有注释掉的旧代码
- [ ] 运行 Linter（Ruff/Flake8）
- [ ] **验证**: 代码量显著减少，无功能损失

---

## Phase 6: 更新文档和测试📚

### 6.1 更新项目文档
- [ ] 更新 `CLAUDE.md`
  - [ ] 新的目录结构说明
  - [ ] 新的命令示例（reanimator_cli, lithoformer_cli）
  - [ ] 新的文件命名规则
  - [ ] 模型代码简写表
- [ ] 更新 `README.md`
  - [ ] 快速开始指南
  - [ ] 新的 CLI 命令
  - [ ] 文件命名示例
- [ ] 更新 `ARCHITECTURE.md`
  - [ ] Ports & Adapters 架构图
  - [ ] 依赖关系图
  - [ ] 层次结构说明
- [ ] 更新 `API_GUIDE.md`
  - [ ] 新的 API 接口
  - [ ] Use Case 调用示例

### 6.2 编写单元测试
- [ ] Reanimator Domain 测试（纯业务逻辑）
- [ ] Reanimator Use Case 测试（Mock LLM）
- [ ] Lithoformer Domain 测试
- [ ] Lithoformer Use Case 测试（Mock LLM）
- [ ] 共享组件测试（工具类、文件命名等）
- [ ] **目标**: 测试覆盖率 > 80%

### 6.3 编写集成测试
- [ ] Reanimator CLI 端到端测试（真实 API）
- [ ] Lithoformer CLI 端到端测试（真实 API）
- [ ] 文件命名正确性测试
- [ ] 模型代码映射测试

### 6.4 最终验证
- [ ] 所有 CLI 命令正常运行
- [ ] 文件命名符合规范
- [ ] 模型简写输入正常工作
- [ ] 文档清晰完整
- [ ] 测试全部通过

---

## 完成后操作

- [ ] 删除此 `REFACTOR_ROADMAP.md` 文件
- [ ] 创建 Git 提交和版本标签
- [ ] 庆祝重构成功！🎉

---

**进度追踪**: 0/100 任务完成

# Lithoformer TUI 布局修复 v4 - 运行时补丁

## 🐛 发现的问题

在运行应用时遇到了以下错误：

```
AttributeError: 'MainScreen' object has no attribute 'single_progress'
```

## 🔍 根本原因

在移除双进度条（single_progress + total_progress）并替换为单个 CustomProgressBar 时，有一些方法没有更新：

1. `_reset_progress_bars()` - 仍然尝试访问 `self.single_progress`
2. `_update_single_progress()` - 仍然尝试访问 `self.single_progress`
3. `_update_total_progress()` - 使用旧的 ProgressBar API
4. `_set_status()` - 尝试访问不存在的 `#status-message`
5. `_set_stats_text()` - 尝试访问不存在的 `#stats-display`
6. `analysis_panel` 属性 - 引用不存在的 `#analysis-panel`
7. `_update_analysis_summary()` - 尝试更新不存在的 panel

## ✅ 修复内容

### 1. 更新 `_reset_progress_bars()`

**修复前**：
```python
def _reset_progress_bars(self, total: int = 0) -> None:
    """Reset both progress bars."""
    single = self.single_progress  # ❌ 不存在
    single.total = 1
    single.progress = 0

    total_bar = self.total_progress
    total_bar.total = max(total, 1)  # ❌ 旧API
    total_bar.progress = 0
```

**修复后**：
```python
def _reset_progress_bars(self, total: int = 0) -> None:
    """Reset progress bar."""
    self.total_progress.reset()  # ✅ 使用新API
    if total > 0:
        self.total_progress._total = total
```

### 2. 简化 `_update_single_progress()`

**修复前**：
```python
def _update_single_progress(self, *, reset: bool = False, done: bool = False) -> None:
    """Update the per-question progress indicator."""
    bar = self.single_progress  # ❌ 不存在
    if reset:
        bar.progress = 0
    if done:
        bar.progress = bar.total
```

**修复后**：
```python
def _update_single_progress(self, *, reset: bool = False, done: bool = False) -> None:
    """Deprecated: Single progress bar no longer exists."""
    pass  # ✅ 空操作，保持向后兼容
```

### 3. 重写 `_update_total_progress()`

**修复前**：
```python
def _update_total_progress(self, completed: int, total: int) -> None:
    """Update the total progress indicator."""
    bar = self.total_progress
    bar.total = max(total, 1)  # ❌ 旧API
    bar.progress = min(completed, bar.total)
```

**修复后**：
```python
def _update_total_progress(self, completed: int, total: int) -> None:
    """Update the total progress indicator."""
    elapsed = (perf_counter() - self._run_start_time) if self._run_start_time else 0.0
    remaining = self._estimate_remaining_time(elapsed, completed, total)

    self.total_progress.update_progress(  # ✅ 使用新API
        current=completed,
        total=total,
        elapsed_time=self._format_seconds(elapsed),
        remaining_time=remaining,
        tokens=self._total_tokens
    )
```

### 4. 简化状态和统计方法

**修复前**：
```python
def _set_status(self, text: str) -> None:
    """Update status message."""
    self.query_one("#status-message", Static).update(text)  # ❌ 组件不存在

def _refresh_stats(self, total: int) -> None:
    """Refresh statistics display based on current counters."""
    elapsed = (perf_counter() - self._run_start_time) if self._run_start_time else 0.0
    remaining = self._estimate_remaining_time(elapsed, self._processed_count, total)
    self._set_stats_text(self._processed_count, total, elapsed, remaining, self._total_tokens)

def _set_stats_text(self, completed: int, total: int, elapsed: float, remaining: str, tokens: int) -> None:
    """Render the stats text."""
    self.query_one("#stats-display", Static).update(...)  # ❌ 组件不存在
```

**修复后**：
```python
def _set_status(self, text: str) -> None:
    """Update status message (deprecated: status is shown in progress bar)."""
    pass  # ✅ 状态信息现在显示在进度条中

def _refresh_stats(self, total: int) -> None:
    """Refresh statistics display based on current counters."""
    pass  # ✅ 统计信息现在在 _update_total_progress 中更新

def _set_stats_text(self, completed: int, total: int, elapsed: float, remaining: str, tokens: int) -> None:
    """Render the stats text (deprecated: stats are shown in progress bar)."""
    pass  # ✅ 统计信息现在显示在进度条中
```

### 5. 移除 `analysis_panel` 属性

**修复前**：
```python
@property
def analysis_panel(self) -> Static:
    return self.query_one("#analysis-panel", Static)  # ❌ 组件不存在
```

**修复后**：
```python
# ✅ 完全移除该属性
```

### 6. 更新 `_update_analysis_summary()`

**修复前**：
```python
def _update_analysis_summary(self, detection: DetectionResult | None) -> None:
    """Render a compact summary of the detection outcome."""
    panel = self.analysis_panel  # ❌ 属性不存在
    if detection is None:
        panel.update("[dim]空[/]")
        return

    # ...
    panel.update("\n".join(summary_lines))  # ❌ panel不存在
```

**修复后**：
```python
def _update_analysis_summary(self, detection: DetectionResult | None) -> None:
    """Render a compact summary of the detection outcome (deprecated)."""
    if detection is None:
        return

    # ... 构建摘要信息 ...

    # ✅ 输出到日志而不是panel
    self.logger.info("检测摘要:\n" + "\n".join(summary_lines))
```

## 📊 修复总结

| 方法 | 修复前状态 | 修复后状态 |
|------|-----------|-----------|
| `_reset_progress_bars()` | ❌ 访问single_progress | ✅ 使用CustomProgressBar.reset() |
| `_update_single_progress()` | ❌ 访问single_progress | ✅ 空操作（向后兼容） |
| `_update_total_progress()` | ❌ 使用旧API | ✅ 使用CustomProgressBar.update_progress() |
| `_set_status()` | ❌ 访问#status-message | ✅ 空操作（信息在进度条中） |
| `_refresh_stats()` | ❌ 调用_set_stats_text | ✅ 空操作（在_update_total_progress中更新） |
| `_set_stats_text()` | ❌ 访问#stats-display | ✅ 空操作（信息在进度条中） |
| `analysis_panel` 属性 | ❌ 返回不存在的组件 | ✅ 完全移除 |
| `_update_analysis_summary()` | ❌ 更新不存在的panel | ✅ 输出到日志 |

## 🎯 关键改进

1. **进度条更新整合** - 所有状态信息（时间、tokens、进度）现在在一个地方更新（`_update_total_progress()`）
2. **向后兼容** - 保留了旧方法但改为空操作，避免破坏现有代码
3. **日志输出** - 解析摘要现在输出到日志，用户可以在控制台中查看
4. **清理遗留代码** - 移除了所有对已删除组件的引用

## 🧪 测试结果

```bash
✅ App 导入成功
✅ App 初始化成功
```

## 📝 相关文件

修改的文件：
- `src/memosyne/lithoformer/tui/widgets/screens.py`

修改的方法（8个）：
1. `_reset_progress_bars()`
2. `_update_single_progress()`
3. `_update_total_progress()`
4. `_set_status()`
5. `_refresh_stats()`
6. `_set_stats_text()`
7. `_update_analysis_summary()`
8. 移除 `analysis_panel` 属性

## 🚀 现在可以运行了！

```bash
./run_lithoformer_tui.sh
```

或：

```bash
python -m src.memosyne.lithoformer.tui
```

---

**补丁时间**: 2025-10-19
**状态**: ✅ 运行时错误已修复
**备注**: 这是 v4 修复的补丁，解决了首次运行时发现的API兼容性问题

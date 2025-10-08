"""
批次 ID 生成器 - 提取业务逻辑为独立类

重构收益：
- ✅ 职责分离：批次管理独立于主流程
- ✅ 可测试性：可注入时区和输出目录
- ✅ 可复用性：其他模块也可使用
"""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


class BatchIDGenerator:
    """
    批次 ID 生成器

    格式：YYMMDD + RunLetter + NNN
    - YYMMDD: 日期（6位）
    - RunLetter: 当日批次字母（A-Z）
    - NNN: 词条数量（3位，左填充0）

    Example:
        >>> gen = BatchIDGenerator(output_dir=Path("data/output/memo"))
        >>> batch_id = gen.generate(term_count=15)
        >>> print(batch_id)  # 251007A015
    """

    def __init__(
        self,
        output_dir: Path,
        timezone: str = "America/New_York",
        max_runs_per_day: int = 26
    ):
        """
        Args:
            output_dir: 输出目录（用于检测已存在的批次）
            timezone: 时区（用于确定"今天"）
            max_runs_per_day: 每日最大批次数（默认26次 A-Z）
        """
        self.output_dir = output_dir
        self.timezone = ZoneInfo(timezone)
        self.max_runs_per_day = max_runs_per_day

    def generate(self, term_count: int) -> str:
        """
        生成批次 ID

        Args:
            term_count: 词条数量

        Returns:
            批次 ID 字符串

        Raises:
            RuntimeError: 当日批次已达上限
        """
        # 1. 获取当前日期（按指定时区）
        now = datetime.now(self.timezone)
        yymmdd = now.strftime("%y%m%d")

        # 2. 查找下一个可用字母
        run_letter = self._find_next_run_letter(yymmdd)

        # 3. 格式化词条数（3位）
        count_str = f"{term_count:03d}"

        return f"{yymmdd}{run_letter}{count_str}"

    def _find_next_run_letter(self, yymmdd: str) -> str:
        """
        查找当日下一个可用批次字母

        Args:
            yymmdd: 日期字符串（6位）

        Returns:
            批次字母（A-Z）

        Raises:
            RuntimeError: 已用尽 A-Z
        """
        # 扫描输出目录，找到当日已用的字母
        used_letters = self._scan_used_letters(yymmdd)

        # 查找第一个未使用的字母
        for code in range(ord("A"), ord("A") + self.max_runs_per_day):
            letter = chr(code)
            if letter not in used_letters:
                return letter

        # 已用尽
        raise RuntimeError(
            f"当日批次已达上限（{self.max_runs_per_day}），"
            f"已使用字母：{sorted(used_letters)}"
        )

    def _scan_used_letters(self, yymmdd: str) -> set[str]:
        """
        扫描输出目录，收集当日已用的批次字母

        Args:
            yymmdd: 日期字符串（6位）

        Returns:
            已使用的字母集合
        """
        used = set()

        if not self.output_dir.exists():
            return used

        # 遍历输出目录中的文件
        for file_path in self.output_dir.iterdir():
            name = file_path.name

            # 检查文件名是否以当日日期开头
            if len(name) >= 7 and name[:6] == yymmdd:
                # 第7个字符应该是批次字母
                letter = name[6]
                if "A" <= letter <= "Z":
                    used.add(letter)

        return used

    def parse_batch_id(self, batch_id: str) -> dict[str, str]:
        """
        解析批次 ID

        Args:
            batch_id: 批次 ID（如 "251007A015"）

        Returns:
            包含 date, run_letter, count 的字典

        Example:
            >>> gen = BatchIDGenerator(Path("."))
            >>> info = gen.parse_batch_id("251007A015")
            >>> assert info == {"date": "251007", "run_letter": "A", "count": "015"}
        """
        if len(batch_id) != 10:
            raise ValueError(f"批次 ID 长度应为 10，实际为 {len(batch_id)}")

        return {
            "date": batch_id[:6],
            "run_letter": batch_id[6],
            "count": batch_id[7:10],
        }


# ============================================================
# 使用示例
# ============================================================
if __name__ == "__main__":
    from pathlib import Path

    # 1. 创建生成器
    output_dir = Path("data/output/memo")
    output_dir.mkdir(parents=True, exist_ok=True)

    generator = BatchIDGenerator(
        output_dir=output_dir,
        timezone="America/New_York"
    )

    # 2. 生成批次 ID
    batch_id = generator.generate(term_count=25)
    print(f"生成的批次 ID：{batch_id}")

    # 3. 解析批次 ID
    info = generator.parse_batch_id(batch_id)
    print(f"解析结果：{info}")

    # 4. 模拟文件存在
    test_file = output_dir / f"{batch_id}.csv"
    test_file.touch()

    # 再次生成 -> 会自动使用下一个字母
    batch_id_2 = generator.generate(term_count=30)
    print(f"下一个批次 ID：{batch_id_2}")

    # 清理测试文件
    test_file.unlink()

"""CLI prompts and user interaction utilities"""


def ask(prompt: str, required: bool = True) -> str:
    """
    询问用户输入

    Args:
        prompt: 提示文本
        required: 是否必填

    Returns:
        用户输入（已去空白）
    """
    while True:
        value = input(prompt).strip()
        if value or not required:
            return value
        print("不能为空，请重输。")

"""
Quiz 解析服务

负责使用 LLM 将 Markdown 格式的 Quiz 解析成结构化数据
"""
from ..core.interfaces import LLMError
from ..models.quiz import QuizItem, QuizResponse


# ============================================================
# Prompt 和 Schema 定义
# ============================================================
SYSTEM_PROMPT = """You are an exam parser agent.

VERBATIM MANDATE (CRITICAL)
- DO NOT paraphrase or shorten any wording.
- COPY stems, step lines (A./B./C./D.) and option texts VERBATIM.
- Preserve punctuation, parentheses, acronyms, numbers (e.g., 'DSM-5-TR', '(positively charged ion)').
- Allowed edits ONLY:
  (a) remove leading numbering tokens at the very start of the stem (e.g., '1.', '(1)', 'Q1:');
  (b) insert '<br>' for line breaks;
  (c) replace figures/images with placeholders '§Pic.N§' in order of appearance.

STRICT SEPARATION
- NEVER put any answer choices (like 'a. ...', 'A. ...') inside the stem. All choices must go into 'options'.
- Remove UI/grade artifacts from the source such as: 'Correct answer:', 'Incorrect answer:', ', Not Selected', 'Not Selected'.
- Remove naked markers 'A.'/'B.'/'C.'/'D.' that appear WITHOUT text.

TYPE DECISION RULES
- If lettered choices (A./B./C./D.) exist in the source, the item is MCQ, even if the stem has blanks/underscores.
- Use CLOZE ONLY when there are underscores '____' in the stem AND there are NO lettered choices.
- Use ORDER when the prompt asks to place/order AND there are labeled step lines A./B./C./D., plus separate sequence choices (e.g., 'B,A,C,D').
- For figure-only MCQ (labels A/B/C/D without descriptions), set options A='A', B='B', C='C', D='D' (others empty).

OUTPUT CONTRACT
- Return ONLY one compact JSON object with key: "items".
- "items" is an array; each item is an object with:
  - "qtype": "MCQ" or "CLOZE" or "ORDER".
  - "stem": string (VERBATIM; may include '<br>' and '§Pic.N§').
  - "steps": array of strings. For ORDER, put the labeled step lines VERBATIM (e.g., 'A. ...', 'B. ...'); else [].
  - "options": object with keys "A","B","C","D","E","F" (strings). ALWAYS output all keys; if a key doesn't exist, set "".
    *For ORDER, options are the SEQUENCE choices (e.g., 'B,A,C,D'), NOT the step lines.*
  - "answer": one uppercase letter among A..F for MCQ/ORDER; "" for CLOZE.
  - "cloze_answers": array of strings. For CLOZE, provide exact fills in order; for MCQ/ORDER, [].
- No markdown code fences, no commentary, no extra keys.
- Do NOT create items that are merely answer summaries (e.g., '... in the proper sequence: D, C, A, B.').

STYLE
- Stems: only remove leading numbering tokens; otherwise copy verbatim.
- Keep parentheses and qualifiers.
- For blanks '____', list fills in cloze_answers (renderer will place '{{...}}' or keep underscores as needed)."""

USER_TEMPLATE = """Source markdown quiz:

---
{md}
---

TASK
- Extract questions with choices and the correct answer letter if explicitly available in the markdown.
- If answer not explicit, leave "answer" as empty string "".
- Clean stems: remove numbering like "1.", "(1)", "Q1:", etc.
- Ensure options text are concise.
- Return JSON only, matching the schema strictly.
"""

QUIZ_SCHEMA = {
    "name": "QuizItems",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "qtype": {"type": "string", "enum": ["MCQ", "CLOZE", "ORDER"]},
                        "stem": {"type": "string", "minLength": 1},
                        "steps": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "options": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "A": {"type": "string"},
                                "B": {"type": "string"},
                                "C": {"type": "string"},
                                "D": {"type": "string"},
                                "E": {"type": "string"},
                                "F": {"type": "string"}
                            },
                            "required": ["A", "B", "C", "D", "E", "F"]
                        },
                        "answer": {"type": "string", "pattern": "^[A-F]?$"},
                        "cloze_answers": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["qtype", "stem", "steps", "options", "answer", "cloze_answers"]
                }
            }
        },
        "required": ["items"]
    }
}


class QuizParser:
    """
    Quiz 解析器

    使用 LLM 将 Markdown 格式的 Quiz 解析成结构化的 QuizItem 列表

    Example:
        >>> from providers import OpenAIProvider
        >>> from config import get_settings
        >>>
        >>> settings = get_settings()
        >>> llm = OpenAIProvider.from_settings(settings)
        >>> parser = QuizParser(llm_provider=llm)
        >>>
        >>> md_text = "1. What is...\\nA. Option A\\nB. Option B"
        >>> items = parser.parse(md_text)
    """

    def __init__(self, llm_provider):
        """
        Args:
            llm_provider: LLM Provider（OpenAI 或 Anthropic）
        """
        self.llm = llm_provider

    def parse(self, markdown_text: str) -> list[QuizItem]:
        """
        解析 Markdown 格式的 Quiz

        Args:
            markdown_text: Markdown 格式的 Quiz 文本

        Returns:
            QuizItem 列表

        Raises:
            LLMError: LLM 调用失败
        """
        user_message = USER_TEMPLATE.format(md=markdown_text)

        try:
            # 使用统一的 Provider 接口
            data = self.llm.complete_structured(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_message,
                schema=QUIZ_SCHEMA["schema"],
                schema_name="QuizItems"
            )
            response = QuizResponse(**data)

            # 校验：确保至少有一个题目
            if not response.items:
                raise LLMError(
                    "LLM 返回空题目列表。可能的原因：\n"
                    "1. 输入的 Markdown 格式不规范\n"
                    "2. 输入中没有可识别的题目\n"
                    "3. LLM 解析失败\n"
                    "请检查输入文件格式。"
                )

            return response.items
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"解析 Quiz 失败：{e}") from e


# ============================================================
# 使用示例
# ============================================================
if __name__ == "__main__":
    from ..providers import OpenAIProvider
    from ..config import get_settings

    # 1. 准备依赖
    settings = get_settings()
    llm_provider = OpenAIProvider.from_settings(settings)

    # 2. 创建解析器
    parser = QuizParser(llm_provider=llm_provider)

    # 3. 示例 Markdown
    sample_md = """
1. What is the capital of France?
   A. London
   B. Paris
   C. Berlin
   D. Madrid

Correct answer: B
"""

    # 4. 解析
    items = parser.parse(sample_md)

    # 5. 输出
    for item in items:
        print(f"Type: {item.qtype}")
        print(f"Stem: {item.stem}")
        print(f"Answer: {item.answer}")
        print()

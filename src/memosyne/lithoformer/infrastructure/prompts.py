"""
Lithoformer Prompts - Quiz 解析提示词

可通过 Settings 配置覆盖：
- LITHOFORMER_SYSTEM_PROMPT
"""

LITHOFORMER_SYSTEM_PROMPT = """You are a licensed clinical psychology exam tutor.

You must process one question at a time and return STRICT JSON that matches the provided schema.

**CRITICAL**: If the user provides a "备注" (note) section, you MUST follow its instructions precisely. This overrides default behavior.

INPUT FORMAT NOTES
- The input uses markdown delimiters ```Question``` and ```Answer``` - these are MARKUP ONLY and should NEVER appear in your output.
- Extract the actual question content between these markers, excluding the words "Question" and "Answer" themselves.

MANDATES
- Copy stems, ordering steps and option texts VERBATIM; preserve punctuation and numbering. Represent explicit line breaks with '<br>'.
- **CRITICAL**: Recognize lettered choices (a./b./c./d. or A./B./C./D.) as OPTIONS, not stem content. The stem ends BEFORE the first lettered choice appears.
- Treat every line that appears before the first lettered choice as part of the stem, including long case vignettes, headers, and blank lines—never summarise, trim, or relocate this content. Analyses must consider this full stem context.
- NEVER move answer choices into the stem. Place every labelled choice (A-F or a-f) into the options object (unused keys -> empty string). Convert lowercase letters to uppercase (a→A, b→B, etc.).
- **If the question contains lettered choices (a./b./c./d. or A./B./C./D.), treat it as MCQ even if the stem contains blanks '____'.** The stem should retain the blanks, but the options object MUST list each choice and the answer field MUST be the correct letter (uppercase).
- For true CLOZE questions (没有选项) keep blanks as '____' in stem and list fills verbatim in cloze_answers.
- For ORDER questions place each ordered step (例如 'A. Step one') into the steps array, and encode the正确顺序 在 answer 字段（如 "B,A,C,D"）。
- Do NOT embed translations inside the English fields. Provide bilingual content through the dedicated translation fields described below.

ANALYSIS REQUIREMENTS（全部使用简体中文）
- analysis.domain: 简洁的学术或诊断标签（中文，例如 “焦虑障碍”）。
- analysis.rationale: 用中文说明为什么正确答案正确，可引用 DSM-5-TR 或权威理论术语（英文术语可保留原文）。
- analysis.key_points: 2-4 条中文关键知识点，每条 1-2 句补充背景或核心概念。
- analysis.distractors: 针对每个错误选项（大写字母）给出中文理由，可引用原选项文本。
- 语气专业、基于证据，可穿插必要的英文专有名词，但说明必须为中文。

TRANSLATION FORMAT
- 提供以下独立的翻译字段，全部使用简体中文：
  - `stem_translation`: 对完整题干（选项前所有文字）的逐句翻译。**IMPORTANT**: 只翻译题干正文，绝对不要包含选项标记（如a./b./c./d.）或选项文本。题干翻译必须在第一个字母选项出现之前结束。
  - `steps_translation`: 与 `steps` 对应的翻译数组，元素数量、顺序必须一致。
  - `options_translation`: 与 `options` 字段结构一致的对象，逐项翻译 A-F 选项内容（只翻译选项文本，不包含字母标记）。
  - `cloze_answers_translation`: 与 `cloze_answers` 数量一致的翻译列表。
- 翻译应忠实传达原意，保持与英文字段的结构和顺序对应；无需包含选项字母或额外的标记。
- 英文字段必须保持纯英文内容，不得混入翻译或其他标注。
- **NEVER translate option markers or option text into stem_translation** - they belong in options_translation only.

STRICT OUTPUT CONTRACT
- 返回 EXACT JSON，且只能包含 schema 中定义的字段。
- 绝不输出额外的文字、markdown 或注释。
"""

LITHOFORMER_USER_TEMPLATE = """以下提供单道题目及其标准答案，请按照系统说明生成结构化 JSON。

{context}

```Question
{question}
```

```Answer
{answer}
```
"""


def get_dynamic_system_prompt(schema_type: str) -> str:
    """
    根据schema类型动态生成system prompt

    Args:
        schema_type: schema类型，可选值：
            - "full": 翻译 + 解析
            - "no_translation": 仅解析（移除翻译指令）
            - "no_analysis": 仅翻译（移除解析指令）
            - "minimal": 基础解析（移除翻译和解析指令）

    Returns:
        动态生成的system prompt

    Examples:
        >>> prompt = get_dynamic_system_prompt("full")
        >>> "TRANSLATION FORMAT" in prompt
        True
        >>> prompt = get_dynamic_system_prompt("no_translation")
        >>> "TRANSLATION FORMAT" in prompt
        False
    """
    # 基础部分（所有类型都包含）
    base_prompt = """You are a licensed clinical psychology exam tutor.

You must process one question at a time and return STRICT JSON that matches the provided schema.

**CRITICAL**: If the user provides a "备注" (note) section, you MUST follow its instructions precisely. This overrides default behavior.

INPUT FORMAT NOTES
- The input uses markdown delimiters ```Question``` and ```Answer``` - these are MARKUP ONLY and should NEVER appear in your output.
- Extract the actual question content between these markers, excluding the words "Question" and "Answer" themselves.

MANDATES
- Copy stems, ordering steps and option texts VERBATIM; preserve punctuation and numbering. Represent explicit line breaks with '<br>'.
- **CRITICAL**: Recognize lettered choices (a./b./c./d. or A./B./C./D.) as OPTIONS, not stem content. The stem ends BEFORE the first lettered choice appears.
- Treat every line that appears before the first lettered choice as part of the stem, including long case vignettes, headers, and blank lines—never summarise, trim, or relocate this content.
- NEVER move answer choices into the stem. Place every labelled choice (A-F or a-f) into the options object (unused keys -> empty string). Convert lowercase letters to uppercase (a→A, b→B, etc.).
- **If the question contains lettered choices (a./b./c./d. or A./B./C./D.), treat it as MCQ even if the stem contains blanks '____'.** The stem should retain the blanks, but the options object MUST list each choice and the answer field MUST be the correct letter (uppercase).
- For true CLOZE questions (没有选项) keep blanks as '____' in stem and list fills verbatim in cloze_answers.
- For ORDER questions place each ordered step (例如 'A. Step one') into the steps array, and encode the正确顺序 在 answer 字段（如 "B,A,C,D"）。"""

    # 翻译部分
    translation_section = """
TRANSLATION FORMAT
- 提供以下独立的翻译字段，全部使用简体中文：
  - `stem_translation`: 对完整题干（选项前所有文字）的逐句翻译。**IMPORTANT**: 只翻译题干正文，绝对不要包含选项标记（如a./b./c./d.）或选项文本。题干翻译必须在第一个字母选项出现之前结束。
  - `steps_translation`: 与 `steps` 对应的翻译数组，元素数量、顺序必须一致。
  - `options_translation`: 与 `options` 字段结构一致的对象，逐项翻译 A-F 选项内容（只翻译选项文本，不包含字母标记）。
  - `cloze_answers_translation`: 与 `cloze_answers` 数量一致的翻译列表。
- 翻译应忠实传达原意，保持与英文字段的结构和顺序对应；无需包含选项字母或额外的标记。
- 英文字段必须保持纯英文内容，不得混入翻译或其他标注。
- **NEVER translate option markers or option text into stem_translation** - they belong in options_translation only."""

    # 解析部分
    analysis_section = """
ANALYSIS REQUIREMENTS（全部使用简体中文）

**CRITICAL - STRUCTURAL REQUIREMENTS:**
The 'analysis' field MUST be a JSON object with the following structure.
DO NOT serialize this object as a string. DO NOT use JSON.stringify or similar serialization.

Required JSON structure:
{
  "analysis": {
    "domain": "string value in Chinese",
    "rationale": "string value in Chinese",
    "key_points": ["string", "string"],  // MUST be an array of strings
    "distractors": [                      // MUST be an array of objects
      {"option": "A", "reason": "string in Chinese"},
      {"option": "B", "reason": "string in Chinese"}
    ]
  }
}

Field content requirements:
- analysis.domain: 简洁的学术或诊断标签（中文，例如 "焦虑障碍"）
- analysis.rationale: 用中文说明为什么正确答案正确，可引用 DSM-5-TR 或权威理论术语（英文术语可保留原文）
- analysis.key_points: 2-4 条中文关键知识点，每条 1-2 句补充背景或核心概念（**必须是数组**）
- analysis.distractors: 针对每个错误选项（大写字母）给出中文理由，可引用原选项文本（**必须是对象数组**）
- 语气专业、基于证据，可穿插必要的英文专有名词，但说明必须为中文"""

    # Few-shot Examples
    analysis_examples = """
<examples>
<correct_example>
Correct way to structure the analysis field (note: analysis is a JSON object, not a string):

{
  "qtype": "MCQ",
  "stem": "A 35-year-old woman presents with excessive worry...",
  "analysis": {
    "domain": "焦虑障碍",
    "rationale": "该患者表现出持续的过度担忧和躯体症状，符合广泛性焦虑障碍（Generalized Anxiety Disorder, GAD）的诊断标准。DSM-5-TR要求症状持续至少6个月。",
    "key_points": [
      "GAD的核心特征是持续至少6个月的过度焦虑和担忧",
      "常见躯体症状包括肌肉紧张、疲劳和睡眠障碍",
      "与恐慌障碍不同，GAD的焦虑是持续性而非突发性的"
    ],
    "distractors": [
      {
        "option": "A",
        "reason": "恐慌障碍（Panic Disorder）的特征是突发的恐慌发作，而非本案例中的持续性焦虑"
      },
      {
        "option": "C",
        "reason": "社交焦虑障碍（Social Anxiety Disorder）主要涉及社交情境的恐惧，而本案例焦虑范围更广泛"
      }
    ]
  }
}

✓ The 'analysis' field is a proper JSON object containing nested objects and arrays.
</correct_example>

<incorrect_example type="string_serialization">
WRONG - DO NOT do this (notice the escaped quotes - this means the object was serialized as a string):

{
  "qtype": "MCQ",
  "stem": "A 35-year-old woman presents with...",
  "analysis": "{\\"domain\\": \\"焦虑障碍\\", \\"rationale\\": \\"该患者...\\"}"
}

✗ ERROR: The analysis field is incorrectly serialized as a STRING (notice the escaped quotes \\" ).
This will cause parsing errors. The analysis field must be a native JSON object, not a string.
</incorrect_example>

<incorrect_example type="wrong_array_types">
WRONG - DO NOT do this (arrays serialized as strings):

{
  "analysis": {
    "domain": "焦虑障碍",
    "rationale": "该患者表现出...",
    "key_points": "要点1：GAD持续6个月。要点2：躯体症状常见。",
    "distractors": "A选项错误因为恐慌障碍是突发性的。C选项错误因为社交焦虑范围更窄。"
  }
}

✗ ERROR: The key_points and distractors fields are STRINGS instead of ARRAYS.
They must be JSON arrays: key_points must be ["string1", "string2"], and distractors must be [{"option":"A", "reason":"..."}].
</incorrect_example>
</examples>
"""

    # 禁止analysis的显式指令
    no_analysis_instruction = """
**IMPORTANT - NO ANALYSIS REQUIRED**
- Do NOT include any 'analysis' field in your output
- Do NOT provide domain labels, rationale, key points, or distractor explanations
- Focus only on extracting the question structure and translation (if required)"""

    # 结尾部分
    footer = """
STRICT OUTPUT CONTRACT

You MUST use the provided tool to return your response. The tool's input_schema defines the exact structure required.

CRITICAL TYPE REQUIREMENTS:
- Objects MUST be JSON objects (use {...}), NEVER serialize objects as strings
- Arrays MUST be JSON arrays (use [...]), NEVER use strings or other types for array fields
- The 'analysis' field specifically MUST be a JSON object containing nested arrays and objects
- DO NOT use JSON.stringify or any string serialization on nested objects

FORMAT REQUIREMENTS:
- Return EXACT JSON that matches the schema
- Include ONLY fields defined in the schema
- Never add extra text, markdown, or comments outside the JSON structure
- Ensure all nested structures maintain their proper types (object, array, string, etc.)

If you are uncertain about the structure, refer to the examples provided above."""

    # 根据schema类型组装prompt
    sections = [base_prompt]

    if schema_type in ("full", "no_analysis"):
        # 包含翻译指令
        sections.append(translation_section)

    if schema_type in ("full", "no_translation"):
        # 包含解析指令和示例
        sections.append(analysis_section)
        sections.append(analysis_examples)  # 添加Few-shot Examples
    elif schema_type in ("no_analysis", "minimal"):
        # 明确禁止analysis字段
        sections.append(no_analysis_instruction)

    sections.append(footer)

    return "\n".join(sections)


def get_dynamic_user_prompt(context: str, question: str, answer: str) -> str:
    """
    生成user prompt（所有类型通用）

    Args:
        context: 备注或上下文
        question: 题目内容
        answer: 答案内容

    Returns:
        格式化的user prompt
    """
    return LITHOFORMER_USER_TEMPLATE.format(
        context=context,
        question=question,
        answer=answer
    )

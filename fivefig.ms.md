

**Cursor**

下面是完整代码方案，所有代码都是以**补丁片段**形式给你，你可以按块 copy，不会直接动你项目里的文件。

---

## 一、赛题要求解释（放在代码注释/答辩稿都能用）

> **赛题「任务三：面试表现多维度分析」** 明确规定评估要覆盖**两大范畴、五个维度**：
> - **内容分析（技术维度）**：① 技术正确性、② 知识深度、③ 逻辑严谨性、④ 与岗位的匹配度
> - **表达分析（语言维度）**：⑤ 表达清晰度（语速、清晰度、自信度等）
>
> 并要求生成**结构化评估报告**，包含总体得分、各维度得分、亮点与不足、改进建议。
>
> **当前项目实际情况：** `evaluation.py` 已经实现了 5 维加权评分机制与 RAG 参考答案注入，但维度命名沿用的是"Technical Knowledge / Communication / Problem Solving / Code Quality / Overall Competence"这一套通用模型，并**未与赛题命名口径完全对齐**；同时报告仅以 Markdown 文字呈现，**尚未提供雷达图可视化**。
>
> 本次改造做两件事：
> 1. **把 5 个维度重命名为赛题口径**（技术正确性 / 知识深度 / 逻辑严谨性 / 岗位匹配度 / 表达清晰度），并把 RAG 参考答案注入从"仅技术正确性"扩展到"技术正确性 + 知识深度 + 岗位匹配度"三个强技术维度。
> 2. **在评估报告下方新增雷达图可视化**（基于 Plotly），直接复用 5 维得分结果，带中英双语 i18n，与项目现有的 `get_text()` 机制完全融合。
>
> 说明：**表达清晰度**维度在无语音情感分析模块的前提下，由大模型基于**候选人回答文本的语言组织质量**（措辞准确度、逻辑衔接、冗余与清晰度）进行打分，是赛题要求的合理降级实现。

---

## 二、代码改动清单（四段）

### ① `requirements.txt` 追加一行

```text
plotly>=5.18.0
```

### ② `jobmatch_ai/evaluation.py` —— 重构 aspects / weights / RAG 分支，并让 `generate_comprehensive_evaluation` 可回传分数字典

**替换第 21–66 行（`generate_comprehensive_evaluation` 顶部到加权总分那块）为：**

```python
def generate_comprehensive_evaluation(
    cfg: LLMConfig,
    transcript: List[Dict[str, str]],
    tech_stack: Optional[List[str]] = None,
    return_scores: bool = False,
):
    """
    按赛题 5 大维度逐一分析候选人表现，生成综合评估报告。

    维度口径对齐赛题「任务三：面试表现多维度分析」：
      内容分析：technical_correctness / knowledge_depth / logical_rigor / position_match
      表达分析：expression_clarity

    Args:
        cfg:           LLM 配置
        transcript:    完整面试对话记录
        tech_stack:    候选人技术栈（用于推断岗位 role，进而做 RAG 检索）
        return_scores: 是否额外返回 {aspect_key: score} 字典，便于 UI 画雷达图

    Returns:
        return_scores=False -> report_markdown (str)     # 向后兼容
        return_scores=True  -> (report_markdown, scores_dict)
    """
    aspects = {
        "technical_correctness": "Technical Correctness",
        "knowledge_depth":       "Knowledge Depth",
        "logical_rigor":         "Logical Rigor",
        "position_match":        "Position Match",
        "expression_clarity":    "Expression Clarity",
    }

    from .interview_flow import _detect_role
    role = _detect_role(tech_stack or [])

    scores: Dict[str, int] = {}
    feedback: Dict[str, str] = {}
    all_retrieved: list[dict] = []

    for aspect_key, aspect_name in aspects.items():
        score, aspect_feedback, retrieved = analyze_aspect(
            cfg, transcript, aspect_key, aspect_name, role=role
        )
        scores[aspect_key] = score
        feedback[aspect_key] = aspect_feedback
        all_retrieved.extend(retrieved)

    weights = {
        "technical_correctness": 0.25,
        "knowledge_depth":       0.20,
        "logical_rigor":         0.20,
        "position_match":        0.20,
        "expression_clarity":    0.15,
    }
    overall_score = sum(scores[a] * weights[a] for a in scores)

    report = f"""# Comprehensive Interview Evaluation

## Overall Score: {overall_score:.1f}/100

### Component Scores:
"""
    for aspect_key, aspect_name in aspects.items():
        report += f"- **{aspect_name}**: {scores[aspect_key]}/100\n"
```

**然后把文件末尾 return 行改为（按 `return_scores` 决定返回 str 还是 tuple）**：

```python
    if return_scores:
        return report, scores
    return report
```

**同时替换 `analyze_aspect` 里的 `aspect_prompts` 字典（第 146–173 行左右）为：**

```python
    aspect_prompts = {
        "technical_correctness": (
            "Evaluate the TECHNICAL CORRECTNESS of the candidate's answers. "
            "Focus ONLY on whether the technical claims, concepts, APIs, formulas and code "
            "are factually correct. Penalize factual mistakes heavily. "
            "Score from 0-100 and provide specific feedback with concrete evidence."
        ),
        "knowledge_depth": (
            "Evaluate the DEPTH of the candidate's technical knowledge. "
            "Beyond surface definitions, can they explain internals, trade-offs, edge cases, "
            "and connections between concepts? Shallow textbook answers should score lower. "
            "Score from 0-100 and provide specific feedback."
        ),
        "logical_rigor": (
            "Evaluate the LOGICAL RIGOR of the candidate's reasoning. "
            "Consider problem decomposition, step-by-step derivation, handling of edge cases, "
            "and self-consistency across turns. Vague or hand-wavy reasoning should score lower. "
            "Score from 0-100 and provide specific feedback."
        ),
        "position_match": (
            "Evaluate how well the candidate's skills, experience and answers MATCH the target "
            "role's required competencies. Use the reference knowledge (if present) as the "
            "role's competency bar. Score from 0-100 and provide specific feedback."
        ),
        "expression_clarity": (
            "Evaluate the CLARITY OF EXPRESSION shown in the transcript text. "
            "Judge wording precision, logical connectors, conciseness and whether a non-expert "
            "could follow. (Acoustic features such as speech rate and confidence are out of scope "
            "for text-only evaluation.) Score from 0-100 and provide specific feedback."
        ),
    }
```

**再把 `analyze_aspect` 中 RAG 触发条件的那一行（第 180 行附近）改为：**

```python
    if aspect_key in ("technical_correctness", "knowledge_depth", "position_match"):
```

并把紧随其后的 `logger.debug` 文案里的 `"technical_knowledge"` 改为 `aspect_key`，便于日志辨识。

---

### ③ `streamlit_app.py` —— i18n 字典追加（zh/en 双语）

**在 `TRANSLATIONS["en"]` 内追加：**

```python
        # --- Radar chart & aspect labels ---
        "eval_radar_title":         "Five-Dimension Evaluation",
        "radar_overall_score":      "Overall Score",
        "aspect_technical_correctness": "Technical Correctness",
        "aspect_knowledge_depth":       "Knowledge Depth",
        "aspect_logical_rigor":         "Logical Rigor",
        "aspect_position_match":        "Position Match",
        "aspect_expression_clarity":    "Expression Clarity",
```

**在 `TRANSLATIONS["zh"]` 内追加：**

```python
        # --- 雷达图与维度标签 ---
        "eval_radar_title":         "五维度能力评估",
        "radar_overall_score":      "综合得分",
        "aspect_technical_correctness": "技术正确性",
        "aspect_knowledge_depth":       "知识深度",
        "aspect_logical_rigor":         "逻辑严谨性",
        "aspect_position_match":        "岗位匹配度",
        "aspect_expression_clarity":    "表达清晰度",
```

### ④ `streamlit_app.py` —— 替换 `evaluation_section()`，新增雷达图渲染

**在文件顶部 import 区追加（和 `import altair as alt` 放在一起）：**

```python
import plotly.graph_objects as go
```

**把 `evaluation_section()` 及其辅助函数整体替换为：**

```python
# 5 个赛题维度的固定顺序，决定雷达图顶点排列
_ASPECT_ORDER = [
    "technical_correctness",
    "knowledge_depth",
    "logical_rigor",
    "position_match",
    "expression_clarity",
]


def _render_aspect_radar(scores: dict) -> None:
    """根据 5 维得分绘制雷达图；维度标签走 i18n。"""
    if not scores:
        return

    theta = [get_text(f"aspect_{k}") for k in _ASPECT_ORDER]
    r = [float(scores.get(k, 0)) for k in _ASPECT_ORDER]
    # 闭合多边形
    theta_closed = theta + [theta[0]]
    r_closed = r + [r[0]]

    fig = go.Figure(
        go.Scatterpolar(
            r=r_closed,
            theta=theta_closed,
            fill="toself",
            name=get_text("radar_overall_score"),
            line=dict(color="#22D3EE", width=2),
            fillcolor="rgba(34, 211, 238, 0.35)",
            hovertemplate="%{theta}: %{r:.1f}/100<extra></extra>",
        )
    )
    fig.update_layout(
        title=dict(text=get_text("eval_radar_title"), x=0.5, xanchor="center"),
        polar=dict(
            bgcolor="rgba(10, 30, 63, 0.25)",
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickfont=dict(size=10),
                gridcolor="rgba(59, 130, 246, 0.35)",
            ),
            angularaxis=dict(
                tickfont=dict(size=13),
                gridcolor="rgba(59, 130, 246, 0.35)",
            ),
        ),
        showlegend=False,
        height=460,
        margin=dict(l=40, r=40, t=60, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)


def evaluation_section(cfg: LLMConfig) -> None:
    if st.button(get_text("generate_report")):
        with st.spinner(get_text("scoring")):
            report_md, scores = generate_comprehensive_evaluation(
                cfg,
                st.session_state.transcript,
                tech_stack=st.session_state.get("tech_stack", []),
                return_scores=True,
            )
            st.session_state.evaluation = report_md
            st.session_state.evaluation_scores = scores

            score = _extract_overall_score(report_md or "")
            access_token = st.session_state.auth.get("access_token")
            interview_id = st.session_state.active_interview_id
            if score is not None and access_token and interview_id:
                try:
                    db.set_interview_score(access_token, interview_id, score)
                except Exception:
                    pass

    if st.session_state.evaluation:
        _render_aspect_radar(st.session_state.get("evaluation_scores") or {})
        st.markdown(st.session_state.evaluation)
```

**最后在 `init_state()` 里追加一行（与其它 `st.session_state` 初始化放一起）：**

```python
    if "evaluation_scores" not in st.session_state:
        st.session_state.evaluation_scores = None
```

---

## 三、关键设计说明（对照 i18n / RAG / 赛题）

| 问题 | 设计决策 |
|---|---|
| **维度命名** | 5 个 key 严格对齐赛题（technical_correctness / knowledge_depth / logical_rigor / position_match / expression_clarity），代码内部统一英文 key，UI 层通过 `get_text(f"aspect_{k}")` 做 zh/en 映射，雷达图 label、悬浮提示都会自动跟随 `st.session_state.language` 切换。 |
| **权重** | 内容分析四维合计 85%（技术正确性 25% + 知识深度 20% + 逻辑严谨性 20% + 岗位匹配度 20%），表达分析 15%，更贴近"技术岗位以技术为重、表达为辅"的评分逻辑。 |
| **RAG 扩展** | 从原本只有 `technical_knowledge` 一个维度注入 RAG 参考答案，扩展到 **技术正确性 / 知识深度 / 岗位匹配度 3 个维度**——这三维都强依赖"标准答案 / 岗位能力画像"，是 RAG 最能发挥价值的场景。逻辑严谨性和表达清晰度属于语言逻辑层，不注入 RAG 避免把参考答案误当作"候选人观点"干扰评分。 |
| **表达清晰度的降级实现** | 在没有语音情感分析的前提下，显式告诉模型「Acoustic features such as speech rate and confidence are out of scope for text-only evaluation」，让其**只基于文本**评估措辞精确性、逻辑衔接与冗余度。答辩时可以这样说：「表达分析当前由大模型基于回答文本的语言组织质量完成，未来可通过接入语音情感分析 API 进一步细化到语速与自信度。」 |
| **向后兼容** | `generate_comprehensive_evaluation` 保留 `return_scores=False` 默认值返回原 Markdown 字符串，旧调用点不必同时修改；新 UI 通过 `return_scores=True` 拿到 tuple。 |
| **雷达图技术栈** | Plotly `Scatterpolar`，Streamlit 原生支持 `st.plotly_chart`，极坐标雷达图只需几行；`paper_bgcolor` 透明、青色 `#22D3EE` 描边与 `rgba(34,211,238,0.35)` 半透明填充，与现有 PPT / 系统的科技蓝配色保持一致。 |
| **零侵入** | 不删除任何现有函数，不改动数据库 schema，不改动现有 Altair 曲线图；唯一新增依赖是 `plotly>=5.18.0`。 |

---

## 四、应用步骤（你决定何时动手）

1. 先在 `requirements.txt` 末尾加 `plotly>=5.18.0`，然后 `pip install -r requirements.txt`。
2. 按 ② 改 `jobmatch_ai/evaluation.py` 中的 5 处（`aspects` / `weights` / 返回 tuple / `aspect_prompts` / RAG 触发条件）。
3. 按 ③ 在 `streamlit_app.py` 的 `TRANSLATIONS` 里追加 7 个双语 key。
4. 按 ④ 替换 `evaluation_section()` 与 `_render_aspect_radar()`，并在 `init_state()` 里追加 `evaluation_scores` 初始化。
5. `streamlit run streamlit_app.py` 验证：完成一次面试 → 点击"生成评估报告" → 报告上方出现雷达图，切换 zh/en 时雷达顶点标签自动切换。

改完之后答辩时可以直接在系统里演示雷达图，不再需要"只有 PPT 素材"。你有需要随时叫我帮你改或者微调权重/配色。


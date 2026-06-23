# 教学输出风格规范 · EXPLANATION STYLE GUIDE

> **本文是教学化输出的硬性规范**。
> 所有 prompt、LLM 输出、前端展示、评测打分,**都必须以本文为准**。
> 与本文冲突的产出,一律打回返工。
> **版本:v2.1(冻结)**

---

## 0. 总原则

### 0.1 三条铁律

1. **不要让 LLM"猜工程",要让解析器"还原工程",再让 LLM"讲工程"**
2. **所有讲解必须基于 SourceRef,没有证据宁可说"不确定"**
3. **教学口吻,不是技术文档口吻**

### 0.2 用户感受目标

学生看完讲解,应该:
- 知道**这是什么**(不是说不清楚)
- 知道**它在工程里干什么**(不是孤立讲定义)
- 知道**自己下一步该看哪里 / 改哪里**(不是看完不知所措)
- 觉得**像老师在讲**(不是像 ChatGPT 在背书)

### 0.3 反模式(禁止)

- ❌ 通用百科式定义("PID 是一种比例-积分-微分控制器,广泛用于...")
- ❌ 不带证据的断言("这个参数设大了不好" — 凭什么这么说?)
- ❌ 长篇大论 + 无重点
- ❌ 装作懂得很多 + 中文翻译腔
- ❌ "可能""或许""大概"满天飞(要么有证据有判断,要么明确说"不确定")
- ❌ 学生没问就把整个理论体系塞过去
- ❌ 输出忽长忽短忽深忽浅,每次格式都不同

---

## 1. 输出六大类

| 类型 | 触发场景 | 输出长度参考 |
|------|---------|------------|
| **A. 项目总览**(Project Overview) | 工程上传完成后 | 400-800 字 |
| **B. Simulink Block/Subsystem 讲解** | 用户点击 block | 200-500 字 |
| **C. MATLAB .m 文件讲解** | 用户点击 .m 文件 | 300-700 字 |
| **D. 工程问答 QA** | 用户对话框提问 | 100-400 字 |
| **E. 不确定 / 证据不足回答** | 任何上述类型证据不足时 | 50-150 字 |
| **F. MATLAB Bridge 报错解释** | MATLAB Add-on 手动粘贴报错后 | 结构化 JSON,客户端渲染 |

每类都有**固定结构**,详见下文。

---

## 2. A. 项目总览(Project Overview)

### 触发
工程上传解析完成,生成首屏导览。

### 固定 JSON Schema(LLM 必须按此输出)

```json
{
  "project_title": "PMSM 矢量控制仿真",
  "project_type": "motor_control",
  "one_sentence_summary": "用 Simulink 实现的永磁同步电机矢量控制(FOC)闭环仿真,含速度环和电流环。",
  "main_entry_files": [
    {
      "file_path": "run_simulation.m",
      "role": "主入口脚本,设置参数并启动仿真"
    }
  ],
  "main_simulink_models": [
    {
      "file_path": "pmsm_foc.slx",
      "summary": "顶层模型,含速度环、电流环、坐标变换、PMSM 本体"
    }
  ],
  "main_execution_flow": [
    "init_params.m 初始化电机参数和控制器参数",
    "run_simulation.m 调用 sim('pmsm_foc.slx') 启动仿真",
    "plot_results.m 绘制速度、电流、转矩响应曲线"
  ],
  "key_files": [
    {"file_path": "init_params.m", "why_key": "所有可调参数集中在这里"},
    {"file_path": "pmsm_foc.slx", "why_key": "核心仿真模型"}
  ],
  "key_blocks": [
    {
      "block_name": "SpeedController",
      "block_type": "PID Controller",
      "location": "pmsm_foc.slx / SpeedLoop",
      "why_key": "速度环核心,影响整个系统响应"
    }
  ],
  "knowledge_points": [
    "矢量控制 / FOC",
    "Clarke / Park 变换",
    "PMSM 数学模型",
    "PI 控制器整定"
  ],
  "beginner_reading_order": [
    "1. 先看 init_params.m,搞清楚电机参数有哪些",
    "2. 再看 pmsm_foc.slx 顶层结构,从 Step 输入开始,顺信号流走一遍",
    "3. 然后展开 SpeedLoop / CurrentLoop 子系统看内部",
    "4. 最后看 run_simulation.m 和 plot_results.m"
  ],
  "likely_confusing_points": [
    "为什么有两个 PID(速度环 + 电流环),不是一个?",
    "dq 坐标系是什么,为什么要做坐标变换?",
    "Iq_ref 是怎么传到电流环的?"
  ],
  "evidence": [
    {"file_path": "pmsm_foc.slx", "block_id": "SpeedLoop/PID"},
    {"file_path": "init_params.m", "line_range": [1, 30]}
  ]
}
```

### 字段约束

| 字段 | 必填 | 类型 | 长度 |
|------|------|------|------|
| `project_title` | ✅ | string | ≤ 30 字 |
| `project_type` | ✅ | enum | 见 `core/domain/project.py` |
| `one_sentence_summary` | ✅ | string | ≤ 80 字,一句话 |
| `main_entry_files` | ✅ | array | 1-3 个 |
| `main_simulink_models` | ✅ | array | 1-5 个,可空 |
| `main_execution_flow` | ✅ | array | 3-7 步 |
| `key_files` | ✅ | array | 3-8 个 |
| `key_blocks` | ✅ | array | 0-10 个,无 Simulink 时可空 |
| `knowledge_points` | ✅ | array | 3-6 个 |
| `beginner_reading_order` | ✅ | array | 3-6 步 |
| `likely_confusing_points` | ✅ | array | 2-5 个 |
| `evidence` | ✅ | array | ≥ 3 个 SourceRef |

### 风格要求

- `one_sentence_summary` 像老师一句话介绍课题,不是百科定义
- `beginner_reading_order` 必须给具体动作,不能写"先理解基础概念"这种空话
- `likely_confusing_points` 必须是**学生看了工程会问的问题**,不是教科书难点

---

## 3. B. Simulink Block / Subsystem 讲解

### 触发
用户点击 block 或 subsystem。

### 固定结构(Markdown 输出,前端按段渲染)

```markdown
## 这是什么
[一句话说明该 block 的作用。结合工程语境,不要套定义。]

## 它在本工程里负责什么
[结合前后连接关系解释。例:"它接收 SpeedLoop 输出的 Iq_ref,经过 dq → αβ 变换,送给 SVPWM。"]

## 输入是什么
- 端口 1:[信号名] ← 来自 [上游 block]
- 端口 2:[信号名] ← 来自 [上游 block]

## 输出是什么
- 端口 1:[信号名] → 去向 [下游 block]

## 关键参数
| 参数名 | 当前值 | 含义 | 为什么可能这么设 |
|--------|--------|------|-----------------|
| Kp | 5.0 | 比例增益 | 决定响应速度,过大会震荡 |
| Ki | 100 | 积分增益 | 决定消除稳态误差的快慢 |

[如果没有可调参数,就跳过这一节,不要硬写]

## 对应课程知识点
- 自动控制原理:PI 控制器
- 电机控制:速度环设计

## 学生容易误解的地方
- 这个 PID 不是直接控电压,而是给电流环下发 Iq_ref 参考
- Kp 不是"越大越好",过大会让转速震荡

## 如果你要改,先动哪里
1. 先小幅改 Kp,观察速度响应曲线
2. 不要同时改 Ki
3. 改之前先记录原值,方便回滚

## 依据
- model.slx / SpeedLoop / PID Controller
- init_params.m 第 12-24 行(参数初始化)
```

### 字段约束

- "这是什么" ≤ 60 字
- "它在本工程里负责什么" 必须提到至少 1 个**具体的上下游 block 名**
- "关键参数" 表格,如果 block 无参数则整段省略
- "对应课程知识点" 2-4 条,用国内教材术语
- "学生容易误解的地方" 1-3 条
- "如果你要改,先动哪里" 2-4 步,**必须可执行**
- "依据" 至少 1 个 SourceRef

### 反例(禁止)

```markdown
❌ 这是什么
PID 控制器是一种经典的反馈控制器,由比例(P)、积分(I)、微分(D)三个环节组成,广泛应用于工业控制领域。
```

为什么错:这是教科书定义,跟用户当前工程无关。

```markdown
✅ 这是什么
速度环 PI 控制器,根据速度误差给电流环下发 Iq 参考值。它是 SpeedLoop 子系统的核心。
```

---

## 4. C. MATLAB .m 文件讲解

### 触发
用户点击 .m 文件。

### 固定结构

```markdown
## 这个文件在工程里的角色
[入口脚本 / 参数初始化 / 仿真运行 / 绘图 / 工具函数 / 其他。一句话说明。]

## 执行顺序
[它什么时候被调用,前后依赖是什么。]
- 被谁调用:[文件名]
- 它调用了谁:[文件名列表]
- 必须在它之前运行的:[文件名]

## 关键变量
| 变量名 | 含义 | 单位 | 来源 | 去向 |
|--------|------|------|------|------|
| Rs | 定子电阻 | Ω | 电机出厂参数 | 用于 pmsm_foc.slx 的 PMSM block |
| J | 转动惯量 | kg·m² | 估算值 | 用于机械方程 |

## 关键代码段(按行号)

### 第 5-12 行:电机参数初始化
[简要解释这段在做什么,不要逐行翻译代码]

### 第 18-25 行:控制器参数
[同上]

## 修改建议
- 调电机参数:改第 5-12 行
- 调控制器参数:改第 18-25 行,**先看 SpeedLoop 的 PID block**
- 不要动:第 30-40 行的初始状态设置(改了仿真可能不收敛)

## 依据
- init_params.m 第 1-50 行
```

### 字段约束

- "执行顺序" 必须基于实际调用关系(由 ProjectGraph 提供),不能编造
- "关键变量" 表只列影响仿真结果的关键变量,不要把所有变量列上
- "关键代码段" 不要逐行翻译代码,按**功能段**讲
- "修改建议" 必须可执行,**指明哪里能改、哪里别动**

---

## 5. D. 工程问答 QA

### 触发
用户在对话框提问。

### 固定 JSON Schema

```json
{
  "answer": "速度环 PID 的 Kp 设为 5.0,是因为...(具体讲解)",
  "confidence": "high",
  "citations": [
    {"file_path": "init_params.m", "line_range": [15, 18]},
    {"file_path": "pmsm_foc.slx", "block_id": "SpeedLoop/PID"}
  ],
  "follow_up_suggestions": [
    "为什么 Ki 设得比 Kp 大很多?",
    "如果改成 Kp=10 会怎样?"
  ]
}
```

### 字段约束

| 字段 | 必填 | 说明 |
|------|------|------|
| `answer` | ✅ | 中文回答,100-400 字 |
| `confidence` | ✅ | `"high"` / `"medium"` / `"low"` |
| `citations` | ✅ | SourceRef 列表,**至少 1 个**;为空走 E 类输出 |
| `follow_up_suggestions` | 选 | 0-3 个,用户可能想追问的 |

### 回答风格

- **先讲结论,再讲依据**,不要绕弯子
- 引用具体文件 / 行号 / block,前端会高亮可点击
- 如果学生问"为什么...",必须**从工程实际配置出发**回答,不要泛泛而谈理论
- 简单问题不要长篇大论
- **不许编造工程里没有的内容**

### 示例

**好回答**:
```
速度环 Kp 设为 5.0,Ki 设为 100。
从 init_params.m 第 15 行看,这是 PMSM 速度环的常见经验起点 —— Kp 决定响应速度,Ki 用于消除稳态误差。
如果你想调,先小幅改 Kp(±20%)观察转速曲线,再调 Ki。

依据:
- init_params.m 第 15-18 行
- pmsm_foc.slx / SpeedLoop / PID Controller
```

**坏回答**:
```
PID 控制器是一种经典控制器,Kp 是比例增益,影响系统响应速度,通常根据 Ziegler-Nichols 方法整定...
```

为什么坏:没看工程,在背教科书。

---

## 6. E. 不确定 / 证据不足回答

### 触发(任一)
- LLM 输出 `citations` 字段为空
- 检索召回的 chunks 与问题相关度低
- 用户问题超出工程文件能回答的范围(如"运行结果是多少"、"参数最优值是什么")

### 固定结构

```json
{
  "answer": "根据当前工程文件,我只能确定 [A, B, C]。\n[D] 这部分需要 [运行仿真 / 查看 workspace 变量 / 查看 .mat 数据],目前无法确认。\n建议你 [具体建议]。",
  "confidence": "low",
  "citations": [],
  "follow_up_suggestions": []
}
```

### 表达模板

```
✅ "根据当前工程文件,我只能确定 X。Y 这部分需要运行仿真才能知道,我没办法直接告诉你。建议你..."

✅ "这个工程的 init_params.m 里只设置了初始值,具体仿真后参数会变成什么,需要你跑一下看。"

✅ "我看到 model.slx 里有 SpeedLoop,但 PID 参数是从 workspace 变量 Kp_speed 读取的,而 Kp_speed 在哪里赋值,我没找到。可能在 .mat 文件里,我无法读取 .mat 数据内容。"

❌ "PID 控制器的最优参数通常通过试凑法确定..."(没看证据,在背教科书)

❌ "Kp 大概设到 10 比较好"(没依据的具体建议,容易误导学生)
```

### 关键

**说"不确定"不是失败,是负责任。** 与其编造,不如明说边界。

---

## 6.5 F. MATLAB Bridge 报错解释

### 触发

MATLAB Add-on 用户确认发送手动粘贴或自动采集的报错文本后,服务端生成一次 `0.3-b1` 结构化解释。`diagnostic_kind` 只表示输入来源,不得提高置信度。

### 固定结构

输出必须符合 `docs/06_OUTPUT_CONTRACTS.md` § 14 的 `BridgeExplanationResult`。客户端负责渲染,LLM 不输出 markdown。

### 风格要求

- `meaning` 只解释报错含义,不要新增环境事实。
- `likely_causes` 全部是推断:`is_inference=true`,`confidence` 只能是 `low` 或 `medium`。
- `supporting_signals` 必须逐字来自服务端二次脱敏后的报错文本,不能只引用 `[REDACTED_PATH]` 这类占位符。
- `next_steps` 只能是非破坏性排查动作,可以建议用户运行 `which` / `ver` / `license`,但不得说系统已经运行或检查过。
- `caveats` 至少 1 条,manual 说明解释只基于用户粘贴的报错文本,auto 说明解释只基于自动采集的报错文本;两者都要说明没有运行仿真或验证修复。

### 禁止

- 不许声称已运行仿真、已检查文件存在、已确认工具箱或许可证状态、已验证修复。
- 不许输出绝对路径、源码、密钥或账号信息。
- 不许把 b1 解释写成生产可用质量承诺;事实正确性和可操作性深度留后续质量评估 seam。

---

## 7. 证据引用强制规则

### 7.1 哪些输出必须带证据

| 输出类型 | 证据要求 |
|---------|---------|
| A. 项目总览 | `evidence` 至少 3 个 SourceRef |
| B. Block 讲解 | "## 依据"段落至少 1 个 SourceRef |
| C. .m 文件讲解 | "## 依据"段落至少 1 个 SourceRef |
| D. 问答 | `citations` 至少 1 个 SourceRef |
| E. 不确定回答 | 可以为空(因为本身就承认无证据) |
| F. MATLAB Bridge 报错解释 | `supporting_signals` 必须是脱敏报错文本的精确子串 |

### 7.2 SourceRef 结构

详见 `core/domain/source_ref.py`:

```python
@dataclass
class SourceRef:
    file_path: str
    line_range: tuple[int, int] | None = None
    block_id: str | None = None
    block_name: str | None = None
    parent_subsystem: str | None = None
    parameter_name: str | None = None
```

### 7.3 后端强制器(CitationEnforcer)

`features/chat/citation_enforcer.py` 必须实现:

```python
def enforce(self, llm_response: dict) -> dict:
    """检查 LLM 输出是否包含 citations。
    
    - 没有 citations 字段 → 标记 warning,返回 E 类不确定回答
    - citations 字段为空 → 同上
    - citations 字段引用的文件 / block 不在 ProjectGraph 中 → 标记 warning(可能幻觉)
    
    Returns:
        校验后的响应(可能降级)
    """
```

### 7.4 前端展示

每个回答下方必须有"**依据**"区块:
- 列出 citations
- 点击 citation → 跳转到对应文件 / block(高亮)
- 如果是 E 类回答(无 citations),显示"⚠️ 此回答基于工程文件无法完全验证"

---

## 8. 语气与措辞

### 8.1 像老师,不像 ChatGPT

| 不要这样 | 改成这样 |
|---------|---------|
| "您好,我理解您想了解..." | (直接讲,不寒暄) |
| "希望对您有帮助" | (省略) |
| "这是一个很好的问题" | (省略) |
| "根据相关理论..." | "你这个工程里..." |
| "建议您可以考虑..." | "你这样改:..." |

### 8.2 中文术语对齐国内教材

| 英文术语 | 用 | 不用 |
|---------|-----|------|
| State-space | 状态空间 | 状态-空间 / 国家空间 |
| Feedback loop | 反馈回路 | 反馈循环 |
| Bode plot | 伯德图 | 波德图 |
| Root locus | 根轨迹 | 根的轨迹 |
| Closed-loop | 闭环 | 关闭回路 |
| Gain margin | 增益裕度 | 增益边际 |
| Phase margin | 相位裕度 | 相位边际 |
| PWM | PWM(或脉宽调制) | 脉冲宽度调制 |
| Park transformation | Park 变换 | 帕克转换 |

(完整对照表见 `core/prompts/glossary.yaml`,Task 305 时补充)

### 8.3 长度控制

- 单段 ≤ 5 行
- 单个回答 ≤ 400 字(总览除外)
- 列表项 ≤ 3 行 / 项

### 8.4 禁止

- 大段"为了帮助您理解..."这种官话
- 长篇大论铺垫
- 用 emoji(产品风格保持简洁)
- 装幽默 / 加段子(学生在赶 ddl,没耐心)

---

## 9. Prompt 编写规则

### 9.1 所有 prompt 模板放 `core/prompts/*.yaml`

格式:

```yaml
# core/prompts/slx_block_explain.yaml
version: "v1.0"
description: "Simulink Block 讲解"
system: |
  你是国内电气工程专业的 MATLAB 助教。
  你正在帮一个本科生看懂他手上的 Simulink 模型。
  
  讲解要求(严格遵守):
  1. 必须按以下结构输出 markdown:
     ## 这是什么 / ## 它在本工程里负责什么 / ## 输入是什么 / ## 输出是什么 /
     ## 关键参数 / ## 对应课程知识点 / ## 学生容易误解的地方 / ## 如果你要改,先动哪里 / ## 依据
  2. "这是什么" ≤ 60 字,不要套定义
  3. "它在本工程里负责什么" 必须提到至少 1 个具体上下游 block 名
  4. "依据" 至少 1 个 SourceRef(文件 / block / 参数)
  5. 用中文教材术语(见 glossary)
  6. 不要寒暄,不要"希望对您有帮助"
  7. 如果证据不足,改用"不确定回答"模板
  
user: |
  以下是该 block 在工程中的结构化信息:
  
  Block 名:{block_name}
  Block 类型:{block_type}
  父子系统:{parent_subsystem}
  参数:{parameters}
  
  上游连接(来自哪些 block):{upstream_blocks}
  下游连接(去向哪些 block):{downstream_blocks}
  
  本工程类型:{project_type}
  
  请讲解这个 block。
```

### 9.2 每个 prompt 文件必须有版本号

改动 prompt → 升 version → 跑全量评测 → 通过才合并。

### 9.3 prompt 必须强制结构化输出

- 文本类 → markdown 固定段落
- 数据类 → JSON schema(用 `json_mode=True`)

---

## 10. 评测对齐

`eval/run_eval.py` 的评分必须基于本文。

每个测试 case 评分维度:
- 输出格式是否符合本文规定(自动检查)
- citations 是否完整(自动检查)
- 不确定性表达是否合适(人工评)
- 教学口吻 vs 技术文档口吻(人工评)
- 中文术语是否对齐国内教材(人工评)

**评分低于 70 分的 prompt 不许上线**。

---

## 11. Codex 使用本规范的方法

写涉及讲解输出的代码 / prompt 时:
1. **先读本文对应类型(A/B/C/D/E)的章节**
2. 按固定 schema 写 prompt
3. 写测试用例,**断言输出符合 schema**
4. 写 mock 测试,**验证 citations 强制器工作**

review 时,Claude 按本文逐条核对。

---

**版本**:v2.1(冻结)
**最后更新**:2026-06-01

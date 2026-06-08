# mxa 评测结果(2026-06-08;v0.2-rc;run_id ad_hoc_20260608_024454)

> 4 个 EE slx 工程;60 题;模型 deepseek-v4-flash;prompt qa_with_context.yaml v0.2-rc
> 题源来自产品导览,出题端有元循环风险;本轮为 slx-only ad-hoc 评测。
> 评分员:PM + 研究生(双盲;先不要互看);分歧以工程作者真值为准。

## 目录
- [01_ee_a](#01_ee_a)(15 题)
- [02_ee_b](#02_ee_b)(15 题)
- [03_ee_c](#03_ee_c)(15 题)
- [04_ee_d](#04_ee_d)(15 题)

---

## 01_ee_a

### Q01_ee_a_001 — 总体题

**题目**:这个 01_ee_a 工程整体是在仿真什么电气系统？我看到有 110kV 电源、变压器和 Universal Bridge，但没看出来主线是什么。

**mxa 答案**(confidence: high):

这个工程仿真的是一个新能源并网发电系统，主线为：通过110kV可编程电压源模拟电网，经变压器和两台Universal Bridge（IGBT）组成的变流器实现交-直-交变换，直流母线由'DC bus voltage Regulator'子系统闭环稳压，并通过'Active & Reactive Power'子系统计算并网功率，最终实现有功/无功控制。

**证据引用**(5 条):

1. [S1] `block` / `01_ee_a.slx` / `110kV` / snippet 前 100 字:`Block 110kV(Three-Phase Programmable Voltage Source) 位于 01_ee_a.slx/顶层,参数 Amplitudes=[1 0.4 1.0],Bac`
2. [S2] `block` / `01_ee_a.slx` / `11` / snippet 前 100 字:`Block 11(Universal Bridge) 位于 01_ee_a.slx/顶层,参数 Arms=3,BackgroundColor=yellow,BlockMirror=on,BlockTy`
3. [S3] `subsystem` / `01_ee_a.slx` / `DC bus voltage Regulator` / snippet 前 100 字:`子系统 DC bus voltage Regulator 在 01_ee_a.slx 内,包含 13 个 block。子 block:Vdc,Vdc_ref,Discrete PI Controlle`
4. [S5] `overview` / `__project_overview__` / `__project_overview__` / snippet 前 100 字:`项目 01_ee_a EE SLX 类型 new_energy。01_ee_a is a Simulink-only electrical engineering model with 461 blo`
5. [S7] `subsystem` / `01_ee_a.slx` / `Active & Reactive Power` / snippet 前 100 字:`子系统 Active & Reactive Power 在 01_ee_a.slx 内,包含 29 个 block。子 block:Udq,Idq,456,Add1,Add2,Bus Creator,`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q01_ee_a_002 — 总体题

**题目**:我第一次打开 01_ee_a.slx，应该从根层哪条信号路径开始看，才能把电网、变压器、变流器和测量量串起来？

**mxa 答案**(confidence: high):

从根层开始，先找到 110kV 三相可编程电压源（S2），这是电网侧源。然后沿信号路径观察变压器、变流器（Grid-side converter Control system 等），并用 Scope1（S3）观测关键波形。注意 From22（S6）传递的转子速度信号，可将其与其他测量量关联。整体按源→变压器→变流器→测量量的顺序分析。

**证据引用**(4 条):

1. [S1] `overview` / `__project_overview__` / `__project_overview__` / snippet 前 100 字:`项目 01_ee_a EE SLX 类型 new_energy。01_ee_a is a Simulink-only electrical engineering model with 461 blo`
2. [S2] `block` / `01_ee_a.slx` / `110kV` / snippet 前 100 字:`Block 110kV(Three-Phase Programmable Voltage Source) 位于 01_ee_a.slx/顶层,参数 Amplitudes=[1 0.4 1.0],Bac`
3. [S3] `block` / `01_ee_a.slx` / `Scope1` / snippet 前 100 字:`Block Scope1(Scope) 位于 01_ee_a.slx/Wind Speed Model,参数 BlockType=Scope,Floating=off,NumInputPorts=1,`
4. [S6] `block` / `01_ee_a.slx` / `From22` / snippet 前 100 字:`Block From22(From) 位于 01_ee_a.slx/顶层,参数 BlockType=From,CloseFcn=tagdialog Close,GotoTag=wr,Position=`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q01_ee_a_003 — 总体题

**题目**:这个模型有 30 个 subsystem，整体架构是按电气一次系统、控制系统、测量系统分层的吗？我该怎么划分这些部分？

**mxa 答案**(confidence: medium):

该模型并不能严格按电气一次、控制系统、测量系统分层。从现有子系统名称看，它更接近功能模块划分：风力机侧（Wind Speed Model、Wind Turbine Control system）、网侧变换器控制（Grid-side converter Control system、Current regulator、DC bus voltage Regulator）、功率计算（Active & Reactive Power）。建议按信号流向分组：风速输入→风力机控制→发电机侧变流器控制→直流母线→网侧变流器控制→电网。测量和功率计算可归入信号处理模块。

**证据引用**(6 条):

1. [S4] `subsystem` / `01_ee_a.slx` / `Wind Turbine Control system` / snippet 前 100 字:`子系统 Wind Turbine Control system 在 01_ee_a.slx 内,包含 24 个 block。子 block:wr,Grid,MPPT,Pitch control,Bet`
2. [S5] `subsystem` / `01_ee_a.slx` / `Grid-side converter Control system` / snippet 前 100 字:`子系统 Grid-side converter Control system 在 01_ee_a.slx 内,包含 84 个 block。子 block:Feedback,Grid,Bus Selec`
3. [S6] `subsystem` / `01_ee_a.slx` / `Wind Speed Model` / snippet 前 100 字:`子系统 Wind Speed Model 在 01_ee_a.slx 内,包含 50 个 block。子 block:775,776,777,778,779,Add,Average wind spee`
4. [S7] `subsystem` / `01_ee_a.slx` / `Current regulator` / snippet 前 100 字:`子系统 Current regulator 在 01_ee_a.slx 内,包含 58 个 block。子 block:Idq_ref,Feedback,Bus Selector,Constant1,`
5. [S8] `subsystem` / `01_ee_a.slx` / `DC bus voltage Regulator` / snippet 前 100 字:`子系统 DC bus voltage Regulator 在 01_ee_a.slx 内,包含 13 个 block。子 block:Vdc,Vdc_ref,Discrete PI Controlle`
6. [S3] `subsystem` / `01_ee_a.slx` / `Active & Reactive Power` / snippet 前 100 字:`子系统 Active & Reactive Power 在 01_ee_a.slx 内,包含 29 个 block。子 block:Udq,Idq,456,Add1,Add2,Bus Creator,`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q01_ee_a_004 — 总体题

**题目**:这个工程的主入口是不是就是 01_ee_a.slx？打开后应优先看哪些根层 block 来判断仿真的研究对象？

**mxa 答案**(confidence: high):

是的，01_ee_a.slx 是工程主入口。打开后优先看根层的 Three-Phase Programmable Voltage Source（电网模拟）、Three-Phase Transformer（变压器）、Parallel RLC Branch（直流链路电容）和 Rotor-side converter Control system（转子侧变流器控制子系统），这些 block 提示研究对象是双馈感应发电机（DFIG）并网系统。

**证据引用**(4 条):

1. [S1] `block` / `01_ee_a.slx` / `1` / snippet 前 100 字:`Block 1(Parallel RLC Branch) 位于 01_ee_a.slx/顶层,参数 AttributesFormatString=\n,BlockMirror=on,BlockRota`
2. [S2] `block` / `01_ee_a.slx` / `110kV` / snippet 前 100 字:`Block 110kV(Three-Phase Programmable Voltage Source) 位于 01_ee_a.slx/顶层,参数 Amplitudes=[1 0.4 1.0],Bac`
3. [S5] `block` / `01_ee_a.slx` / `Rotor-side converter Control system` / snippet 前 100 字:`Block Rotor-side converter Control system(SubSystem) 位于 01_ee_a.slx/顶层,参数 BackgroundColor=lightBlue,`
4. [S8] `block` / `01_ee_a.slx` / `2` / snippet 前 100 字:`Block 2(Three-Phase Transformer (Two Windings)) 位于 01_ee_a.slx/顶层,参数 AttributesFormatString=\n,Backg`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q01_ee_a_005 — 总体题

**题目**:如果我要给导师汇报这个模型，应该怎样从工程层面概括它的电源、网侧阻抗、变压器、变流器和测量点之间的关系？

**mxa 答案**(confidence: error):

[ERROR: parse_validation_error]

**证据引用**(0 条):

无

**运行错误**:parse_validation_error

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q01_ee_a_006 — 模块题

**题目**:根层的 Universal Bridge block“3”和“11”分别在电路里承担什么角色？它们之间是并列结构还是前后级结构？

**mxa 答案**(confidence: low):

从证据来看，Block 3 和 Block 11 是两个 Universal Bridge，通常双馈感应发电机（DFIG）仿真中，两个变换器分别用于转子侧和网侧。Block 3 可能作为网侧变换器（Grid-side converter），Block 11 作为转子侧变换器（Rotor-side converter），它们在直流母线处连接，构成背靠背（back-to-back）结构，属于前后级（整流/逆变）而非并列关系。但证据中未给出明确的连接信息，需通过实际模型验证。

**证据引用**(4 条):

1. [S1] `block` / `01_ee_a.slx` / `11` / snippet 前 100 字:`Block 11(Universal Bridge) 位于 01_ee_a.slx/顶层,参数 Arms=3,BackgroundColor=yellow,BlockMirror=on,BlockTy`
2. [S2] `block` / `01_ee_a.slx` / `3` / snippet 前 100 字:`Block 3(Universal Bridge) 位于 01_ee_a.slx/顶层,参数 Arms=3,BackgroundColor=yellow,BlockType=Reference,Con`
3. [S7] `block` / `01_ee_a.slx` / `Rotor-side converter Control system` / snippet 前 100 字:`Block Rotor-side converter Control system(SubSystem) 位于 01_ee_a.slx/顶层,参数 BackgroundColor=lightBlue,`
4. [S8] `block` / `01_ee_a.slx` / `Bus Selector` / snippet 前 100 字:`Block Bus Selector(BusSelector) 位于 01_ee_a.slx/Grid-side converter Control system,参数 BlockType=BusSe`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q01_ee_a_007 — 模块题

**题目**:“400MVA 110 kV/690V 10% X/R=30”这个三相双绕组变压器 block 在模型里怎么连接网侧和低压侧？

**mxa 答案**(confidence: medium):

该变压器高压侧（110 kV）连接至“110kV”可编程电压源（[S2]），低压侧（690 V）则连接至下游系统，如整流器或直流母线调节等。具体连线需在Simulink模型中查看端口连接。

**证据引用**(2 条):

1. [S1] `block` / `01_ee_a.slx` / `400MVA 110 kV/690V 10% X/R=30` / snippet 前 100 字:`Block 400MVA 110 kV/690V 10% X/R=30(Three-Phase Transformer (Two Windings)) 位于 01_ee_a.slx/顶层,参数 Att`
2. [S2] `block` / `01_ee_a.slx` / `110kV` / snippet 前 100 字:`Block 110kV(Three-Phase Programmable Voltage Source) 位于 01_ee_a.slx/顶层,参数 Amplitudes=[1 0.4 1.0],Bac`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q01_ee_a_008 — 模块题

**题目**:“4000 MVA X/R=10”这个 Three-Phase Series RLC Branch 是在等效电网短路容量吗？它和 110kV 电源之间的电气意义怎么读？

**mxa 答案**(confidence: high):

是的，这个“4000 MVA X/R=10”的 Three-Phase Series RLC Branch 是在等效电网的短路容量。从参数看，电感值设为 1/(2*pi*50)*110^2/4000，这正是基于短路容量 S=4000 MVA 和额定电压 110 kV 计算出的等效电感（Z=U²/S，再换算成电感）。X/R=10 则决定了电阻与电抗的比例。它与上游的 110 kV 可编程电压源（S5）串联，共同构成电网的戴维南等效模型：理想电压源（110 kV 电源）加上短路阻抗（该 RLC 支路），用于模拟实际电网在故障或大功率扰动下的电压支撑能力。

**证据引用**(2 条):

1. [S1] `block` / `01_ee_a.slx` / `4000 MVA X/R=10` / snippet 前 100 字:`Block 4000 MVA X/R=10(Three-Phase Series RLC Branch) 位于 01_ee_a.slx/顶层,参数 AttributesFormatString=\n,`
2. [S5] `block` / `01_ee_a.slx` / `110kV` / snippet 前 100 字:`Block 110kV(Three-Phase Programmable Voltage Source) 位于 01_ee_a.slx/顶层,参数 Amplitudes=[1 0.4 1.0],Bac`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q01_ee_a_009 — 模块题

**题目**:B_Grid、B_Conv、B_Stator 这几个 Three-Phase VI Measurement 测量点各自采的是什么位置的电压电流？

**mxa 答案**(confidence: medium):

从工程证据看：
- **B_Grid**（LabelI=Iabc_B4, LabelV=Vabc_B6）测量电网侧的三相电压和电流，位置在电网与系统接口处。
- **B_Conv**（LabelI=Iabc_grid_conv, LabelV=Vabc_grid_conv）测量电网侧换流器（grid-side converter）交流侧的电压和电流，反映换流器与电网之间的电气量。
- **B_Stator**（LabelI=Iabc_Stator, LabelV=Vabc_Stator）测量发电机定子侧的三相电压和电流，即定子绕组端部。

**证据引用**(3 条):

1. [S1] `block` / `01_ee_a.slx` / `B_Conv` / snippet 前 100 字:`Block B_Conv(Three-Phase VI Measurement) 位于 01_ee_a.slx/顶层,参数 BackgroundColor=black,BlockMirror=on,B`
2. [S3] `block` / `01_ee_a.slx` / `B_Grid` / snippet 前 100 字:`Block B_Grid(Three-Phase VI Measurement) 位于 01_ee_a.slx/顶层,参数 BackgroundColor=black,BlockMirror=on,B`
3. [S4] `block` / `01_ee_a.slx` / `B_Stator` / snippet 前 100 字:`Block B_Stator(Three-Phase VI Measurement) 位于 01_ee_a.slx/顶层,参数 BackgroundColor=black,BlockMirror=on`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q01_ee_a_010 — 模块题

**题目**:根层的 Parallel RLC Branch“1”在这个系统里是滤波、补偿还是负载等效？我应该沿着哪几根线判断它的作用？

**mxa 答案**(confidence: high):

该 Parallel RLC Branch 的 BranchType 设为 C（电容），电容值由变量 C_DClink 给定，初始电压为 Vdc_nom，电感仅 1e-3 H，因此它实际上是一个直流母线电容。其主要作用是滤波和稳压——平滑直流母线电压并储存能量。你可以通过以下两条线索判断：
1. 查看参数中的初始电压 Vdc_nom，这表明它接在直流母线上；
2. 顶层存在子系统“DC bus voltage Regulator”，它专门调节直流母线电压，而该电容正是被调节的对象。

**证据引用**(2 条):

1. [S1] `block` / `01_ee_a.slx` / `1` / snippet 前 100 字:`Block 1(Parallel RLC Branch) 位于 01_ee_a.slx/顶层,参数 AttributesFormatString=\n,BlockMirror=on,BlockRota`
2. [S7] `subsystem` / `01_ee_a.slx` / `DC bus voltage Regulator` / snippet 前 100 字:`子系统 DC bus voltage Regulator 在 01_ee_a.slx 内,包含 13 个 block。子 block:Vdc,Vdc_ref,Discrete PI Controlle`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q01_ee_a_011 — 参数题

**题目**:“4000 MVA X/R=10”这个电网等效参数为什么这样设？对并网电压刚度和暂态电流会有什么影响需要重点检查？

**mxa 答案**(confidence: high):

4000 MVA 是并网点短路容量，110 kV 母线短路容量 4000 MVA 表示电网很强（短路比大），电压刚度高。电感由 L = U²/(2πf·S) = 110²/(2π·50·4000) 算出，X/R=10 意味着电抗远大于电阻，暂态短路电流中直流分量衰减较慢，峰值可能达到 2.5 倍稳态电流。仿真时应重点观察 dq 轴电流是否超过逆变器允许限值，以及 PCC 电压在故障或大功率阶跃时的跌落幅度。

**证据引用**(1 条):

1. [S1] `block` / `01_ee_a.slx` / `4000 MVA X/R=10` / snippet 前 100 字:`Block 4000 MVA X/R=10(Three-Phase Series RLC Branch) 位于 01_ee_a.slx/顶层,参数 AttributesFormatString=\n,`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q01_ee_a_012 — 参数题

**题目**:“400MVA 110 kV/690V 10% X/R=30”的容量、电压等级和短路阻抗放在一起看，和这个变流器侧模型匹配吗？

**mxa 答案**(confidence: low):

从 S1 可知变压器额定容量 400 MVA、一次侧 110 kV、二次侧 690 V、短路阻抗 10%、X/R=30。通常变流器侧额定电压为 690 V，故变压器二次侧电压与变流器侧电压等级匹配。但要全面判断匹配性，还需对比变流器侧额定容量、短路耐受能力等参数。当前证据未提供变流器侧模型参数，无法确定完全匹配。

**证据引用**(1 条):

1. [S1] `block` / `01_ee_a.slx` / `400MVA 110 kV/690V 10% X/R=30` / snippet 前 100 字:`Block 400MVA 110 kV/690V 10% X/R=30(Three-Phase Transformer (Two Windings)) 位于 01_ee_a.slx/顶层,参数 Att`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q01_ee_a_013 — 参数题

**题目**:这个模型 StopTime 设为 6 秒、FixedStep 是 auto，做电力电子开关和电网暂态仿真时这个仿真时长和步长设置合理吗？

**mxa 答案**(confidence: low):

从现有证据看，StopTime=6秒是合理的：S7中Iq-ref的阶跃时间After=0.1、Time=3，说明模型至少需要3秒的时窗，6秒留有余量。但FixedStep=auto通常用于变步长求解器，而电力电子开关仿真（尤其含PWM高频开关）一般建议固定步长（如1e-6~1e-5秒）以确保数值稳定和准确捕捉开关动作。auto步长可能因开关事件导致步长过大，造成数值振荡或错误。建议将FixedStep设为固定值。不过，证据中无求解器与步长的显式设置，无法进一步确认。

**证据引用**(1 条):

1. [S7] `block` / `01_ee_a.slx` / `Iq-ref` / snippet 前 100 字:`Block Iq-ref(Step) 位于 01_ee_a.slx/Grid Operators Control system,参数 After=0.1,BlockType=Step,Name=Qg_`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q01_ee_a_014 — 修改题

**题目**:如果我想把网侧从 110kV 改成另一个电压等级，除了 Three-Phase Programmable Voltage Source，还需要同步检查哪些变压器和测量环节？

**mxa 答案**(confidence: medium):

修改网侧电压等级时，除了调整 Three-Phase Programmable Voltage Source（S1）的参数，必须同步检查变压器（S6）的变比，将一次侧和二次侧电压改为目标值。另外，需要确认网侧电压测量环节（如 Voltage Measurement 或 PT 模块）的量程和标幺值基准是否适配新电压等级，但当前证据中未列出具体测量模块，建议在模型中搜索“Voltage Measurement”或“pu”相关模块进行核查。

**证据引用**(2 条):

1. [S1] `block` / `01_ee_a.slx` / `110kV` / snippet 前 100 字:`Block 110kV(Three-Phase Programmable Voltage Source) 位于 01_ee_a.slx/顶层,参数 Amplitudes=[1 0.4 1.0],Bac`
2. [S6] `block` / `01_ee_a.slx` / `400MVA 110 kV/690V 10% X/R=30` / snippet 前 100 字:`Block 400MVA 110 kV/690V 10% X/R=30(Three-Phase Transformer (Two Windings)) 位于 01_ee_a.slx/顶层,参数 Att`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q01_ee_a_015 — 修改题

**题目**:我想调网侧等效强弱，比如改变短路容量或 X/R 比，应该主要改哪个 RLC Branch，改完后看哪些测量点判断结果是否正常？

**mxa 答案**(confidence: low):

根据当前工程文件,我能定位到 01_ee_a.slx / Grid-side converter Control system /、01_ee_a.slx / Inner loop cont 这些位置,但结构化信息还不足以可靠回答。建议先看相关 init 参数脚本,或在 MATLAB 命令窗里查变量赋值位置。

**证据引用**(0 条):

无

**Fallback**:invalid_or_missing_citations

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---


## 02_ee_b

### Q02_ee_b_001 — 总体题

**题目**:这个 02_ee_b 工程整体是在做哪类电力电子仿真？根层有很多 Constant、Sum 和 Bridge Power，我还没看出主控制目标。

**mxa 答案**(confidence: high):

该工程是一个多电平逆变器（Multilevel Inverter）的电力电子仿真。根层有多个 PWM Generator (Multilevel) 模块（S2-S7）和一个 Sine Wave 模块（S8），用于生成多电平调制信号，典型应用如电网并网或电机驱动。主控制目标是通过多载波 PWM 策略合成期望的交流输出电压波形。

**证据引用**(3 条):

1. [S1] `overview` / `__project_overview__` / `__project_overview__` / snippet 前 100 字:`项目 02_ee_b EE SLX 类型 power_electronics。02_ee_b is a Simulink-only electrical engineering model with `
2. [S2] `block` / `02_ee_b.slx` / `PWM Generator (M)2` / snippet 前 100 字:`Block PWM Generator (M)2(PWM Generator (Multilevel)) 位于 02_ee_b.slx/Control,参数 BlockType=Reference,B`
3. [S8] `block` / `02_ee_b.slx` / `Sine Wave2` / snippet 前 100 字:`Block Sine Wave2(Sin) 位于 02_ee_b.slx/Control,参数 BlockType=Sin,FontName=Verdana,FontSize=11,Frequency`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q02_ee_b_002 — 总体题

**题目**:02_ee_b.slx 是不是唯一主入口？打开后应该先沿着功率级看，还是先沿着 Add 和 Constant 这些控制信号看？

**mxa 答案**(confidence: low):

根据当前工程文件,我能定位到 02_ee_b.slx / Control / Mux1、02_ee_b.slx / Control / Mux3、02_ee_b.slx / Control  这些位置,但结构化信息还不足以可靠回答。建议先看相关 init 参数脚本,或在 MATLAB 命令窗里查变量赋值位置。

**证据引用**(0 条):

无

**Fallback**:invalid_or_missing_citations

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q02_ee_b_003 — 总体题

**题目**:这个模型只有 1 秒仿真时间、8 个 subsystem，整体更像稳态功率计算还是开关暂态过程分析？

**mxa 答案**(confidence: high):

从证据看，模型包含多个 Nearest Level Pulse Generator 子系统，内部有均压算法 block，这是多电平变流器（如 MMC）的典型调制与电容电压均衡结构。仿真时长 1 秒虽可覆盖稳态，但均压算法和最近电平逼近调制通常用于分析开关过程引起的电容电压波动，因此更偏向开关暂态过程分析，而非稳态功率计算。

**证据引用**(4 条):

1. [S1] `subsystem` / `02_ee_b.slx` / `Nearest Level Pulse Generator` / snippet 前 100 字:`子系统 Nearest Level Pulse Generator 在 02_ee_b.slx 内,包含 73 个 block。子 block:Uref,Add,Add1,Constant1,Cons`
2. [S3] `subsystem` / `02_ee_b.slx` / `Nearest Level Pulse Generator 1` / snippet 前 100 字:`子系统 Nearest Level Pulse Generator 1 在 02_ee_b.slx 内,包含 72 个 block。子 block:Uref,Add,Add1,Constant1,Co`
3. [S2] `block` / `02_ee_b.slx` / `均压算法1` / snippet 前 100 字:`Block 均压算法1(SubSystem) 位于 02_ee_b.slx/Nearest Level Pulse Generator 1,参数 BlockType=SubSystem,Content`
4. [S4] `block` / `02_ee_b.slx` / `均压算法1` / snippet 前 100 字:`Block 均压算法1(SubSystem) 位于 02_ee_b.slx/Nearest Level Pulse Generator,参数 BlockType=SubSystem,ContentPr`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q02_ee_b_004 — 总体题

**题目**:如果我要快速理解这个模型的架构，根层的 Scope、Sum、Constant 和桥臂功率测量之间应该怎么分组看？

**mxa 答案**(confidence: low):

根据当前工程文件,我能定位到 02_ee_b.slx / Control / PWM Generator (M)、02_ee_b.slx / Control / PWM Generator  这些位置,但结构化信息还不足以可靠回答。建议先看相关 init 参数脚本,或在 MATLAB 命令窗里查变量赋值位置。

**证据引用**(0 条):

无

**Fallback**:invalid_or_missing_citations

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q02_ee_b_005 — 总体题

**题目**:这个工程的电气主回路和控制计算是混在根层了吗？有没有推荐的阅读顺序，避免只看到一堆 Add 和 Constant？

**mxa 答案**(confidence: medium):

根据项目总览（S1），主流程是打开 `02_ee_b.slx` 检查根层信号路径，识别源、测量、控制、功率级。根层可能包含一些基础运算模块，但已经通过子系统（如 `均压算法`）封装了控制逻辑，并非完全混合。推荐阅读顺序：先看根层信号流向，再打开子系统如 `Nearest Level Pulse Generator` 和 `均压算法`，避免停留在加法器和常数上。

**证据引用**(1 条):

1. [S1] `overview` / `__project_overview__` / `__project_overview__` / snippet 前 100 字:`项目 02_ee_b EE SLX 类型 power_electronics。02_ee_b is a Simulink-only electrical engineering model with `

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q02_ee_b_006 — 模块题

**题目**:Add1、Add2、Add3 这几个 Sum block 分别在合成什么信号？我该怎么判断它们是在做误差计算、相量叠加还是功率平衡？

**mxa 答案**(confidence: low):

从证据清单看，只有 Add1 和 Add3 的位号信息，没有 Add2。Add3 位于顶层，可能是不同环路信号叠加；Add1 位于多个 Nearest Level Pulse Generator 子系统内，很可能参与邻近电平调制中的误差或比较计算。要准确判断，需要查看各加法器的输入连线，确定是误差、相量还是功率信号。

**证据引用**(5 条):

1. [S1] `block` / `02_ee_b.slx` / `Add3` / snippet 前 100 字:`Block Add3(Sum) 位于 02_ee_b.slx/顶层,参数 BlockType=Sum,IconShape=rectangular,Ports=[2, 1],Position=[-495`
2. [S3] `block` / `02_ee_b.slx` / `Add1` / snippet 前 100 字:`Block Add1(Sum) 位于 02_ee_b.slx/Nearest Level Pulse Generator 3,参数 BlockType=Sum,IconShape=rectangula`
3. [S5] `block` / `02_ee_b.slx` / `Add1` / snippet 前 100 字:`Block Add1(Sum) 位于 02_ee_b.slx/顶层,参数 BlockType=Sum,IconShape=rectangular,Ports=[2, 1],Position=[-930`
4. [S6] `block` / `02_ee_b.slx` / `Add1` / snippet 前 100 字:`Block Add1(Sum) 位于 02_ee_b.slx/Nearest Level Pulse Generator,参数 BlockType=Sum,IconShape=rectangular,`
5. [S7] `block` / `02_ee_b.slx` / `Add1` / snippet 前 100 字:`Block Add1(Sum) 位于 02_ee_b.slx/Nearest Level Pulse Generator 1,参数 BlockType=Sum,IconShape=rectangula`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q02_ee_b_007 — 模块题

**题目**:Bridge Power 这个 Scope 显示的量来自哪里？它是在观察桥臂输入功率、输出功率还是某个中间计算量？

**mxa 答案**(confidence: low):

根据当前工程文件,我能定位到 02_ee_b.slx / <root> / Bridge Power、02_ee_b.slx / Control / PWM Generator (M)1、0 这些位置,但结构化信息还不足以可靠回答。建议先看相关 init 参数脚本,或在 MATLAB 命令窗里查变量赋值位置。

**证据引用**(0 条):

无

**Fallback**:invalid_or_missing_citations

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q02_ee_b_008 — 模块题

**题目**:Constant 到 Constant5 这些常数块看起来很多，它们分别更像参考值、器件参数还是初始条件？应该按信号线怎么追踪？

**mxa 答案**(confidence: low):

从证据看，这6个Constant块（Constant, Constant1-5）Value均为0，且位于顶层，很可能是初始条件或接地信号，难以区分参考值、器件参数或初始条件。要追踪信号线，需在Simulink中打开模型，用鼠标左键双击连线或使用“Signal Paths”高亮功能，查看各Constant块连接到哪个模块的输入端口。从位置坐标可粗略判断：左侧的Constant（x=-2385）可能连接左侧模块，右侧的Constant（x=-1585）可能连接右侧模块，但具体角色需结合实际连接确定。

**证据引用**(6 条):

1. [S1] `block` / `02_ee_b.slx` / `Constant5` / snippet 前 100 字:`Block Constant5(Constant) 位于 02_ee_b.slx/顶层,参数 BlockType=Constant,Position=[-1585, 65, -1560, 85],Sh`
2. [S2] `block` / `02_ee_b.slx` / `Constant` / snippet 前 100 字:`Block Constant(Constant) 位于 02_ee_b.slx/顶层,参数 BlockType=Constant,Position=[-2385, -310, -2360, -290]`
3. [S3] `block` / `02_ee_b.slx` / `Constant1` / snippet 前 100 字:`Block Constant1(Constant) 位于 02_ee_b.slx/顶层,参数 BlockType=Constant,Position=[-2370, 110, -2345, 130],`
4. [S4] `block` / `02_ee_b.slx` / `Constant3` / snippet 前 100 字:`Block Constant3(Constant) 位于 02_ee_b.slx/顶层,参数 BlockType=Constant,Position=[-1585, -315, -1560, -295`
5. [S5] `block` / `02_ee_b.slx` / `Constant2` / snippet 前 100 字:`Block Constant2(Constant) 位于 02_ee_b.slx/顶层,参数 BlockType=Constant,Position=[-1995, -305, -1970, -285`
6. [S6] `block` / `02_ee_b.slx` / `Constant4` / snippet 前 100 字:`Block Constant4(Constant) 位于 02_ee_b.slx/顶层,参数 BlockType=Constant,Position=[-1995, 75, -1970, 95],Sh`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q02_ee_b_009 — 模块题

**题目**:这些 Sum block 和 Constant block 之间的连接逻辑，是否构成了某种调制或功率计算算法？我应该优先看哪几个连接点？

**mxa 答案**(confidence: low):

从证据看，模型中的 'Nearest Level Pulse Generator' 子系统包含多个 Sum（加法）模块，它们很可能用于实现最近电平调制（Nearest Level Modulation）中的比较逻辑：Add1 可能用于计算调制波与载波之间的差值，Add 则可能用于产生脉冲信号。但证据中并未出现 Constant block，因此无法确认具体的连接逻辑。建议优先关注每个子系统内 Add1 的输入端口（可能连接调制波和载波）以及 Add 的输出端口（可能连接后续的脉冲生成或均压算法）。

**证据引用**(3 条):

1. [S1] `block` / `02_ee_b.slx` / `Add` / snippet 前 100 字:`Block Add(Sum) 位于 02_ee_b.slx/Nearest Level Pulse Generator 3,参数 BlockType=Sum,IconShape=rectangular`
2. [S4] `block` / `02_ee_b.slx` / `Add1` / snippet 前 100 字:`Block Add1(Sum) 位于 02_ee_b.slx/Nearest Level Pulse Generator 3,参数 BlockType=Sum,IconShape=rectangula`
3. [S7] `block` / `02_ee_b.slx` / `均压算法` / snippet 前 100 字:`Block 均压算法(SubSystem) 位于 02_ee_b.slx/Nearest Level Pulse Generator 3,参数 BlockType=SubSystem,ContentP`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q02_ee_b_010 — 模块题

**题目**:Bridge Power Scope 前面的信号如果经过多个 Add 处理，怎样确认显示的是物理功率而不是归一化或误差信号？

**mxa 答案**(confidence: low):

根据当前工程文件,我能定位到 02_ee_b.slx / <root> / Bridge Power、02_ee_b.slx / Control / Sine Wave1、02_ee_b.s 这些位置,但结构化信息还不足以可靠回答。建议先看相关 init 参数脚本,或在 MATLAB 命令窗里查变量赋值位置。

**证据引用**(0 条):

无

**Fallback**:invalid_or_missing_citations

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q02_ee_b_011 — 参数题

**题目**:StopTime 设为 1 秒对这个电力电子模型够不够？如果有开关暂态或慢速控制环，1 秒会不会太短或太长？

**mxa 答案**(confidence: high):

对于以50Hz工频（周期0.02秒）为基础的电力电子模型，1秒仿真时长包含了50个工频周期，通常足以观察稳态波形和多数暂态过程。若控制环响应较慢（例如速度环时间常数>0.5秒），1秒可能偏短；但证据中未提供控制环具体参数，建议根据实际闭环响应时间调整。

**证据引用**(3 条):

1. [S1] `block` / `02_ee_b.slx` / `Sine Wave1` / snippet 前 100 字:`Block Sine Wave1(Sin) 位于 02_ee_b.slx/Control,参数 BlockType=Sin,FontName=Verdana,FontSize=11,Frequency`
2. [S2] `block` / `02_ee_b.slx` / `Sine Wave` / snippet 前 100 字:`Block Sine Wave(Sin) 位于 02_ee_b.slx/Control,参数 BlockType=Sin,FontName=Verdana,FontSize=11,Frequency=`
3. [S3] `block` / `02_ee_b.slx` / `PWM Generator (M)1` / snippet 前 100 字:`Block PWM Generator (M)1(PWM Generator (Multilevel)) 位于 02_ee_b.slx/Control,参数 BlockType=Reference,B`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q02_ee_b_012 — 参数题

**题目**:Constant 到 Constant5 的取值如果对应参考量或器件参数，怎么判断这些常数是否和桥式功率级的额定工况匹配？

**mxa 答案**(confidence: low):

根据当前工程文件,我能定位到 02_ee_b.slx / <root> / Constant5、02_ee_b.slx / <root> / Constant3、02_ee_b.slx /  这些位置,但结构化信息还不足以可靠回答。建议先看相关 init 参数脚本,或在 MATLAB 命令窗里查变量赋值位置。

**证据引用**(0 条):

无

**Fallback**:invalid_or_missing_citations

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q02_ee_b_013 — 参数题

**题目**:FixedStep=auto 用在这个模型里是否合适？如果模型包含电力电子开关，步长设置会不会影响 Bridge Power 的波形可信度？

**mxa 答案**(confidence: high):

不合适。从证据看，模型包含电力电子开关（PWM Generator 和 Bridge Power），要求固定步长离散求解器才能准确捕捉开关事件。FixedStep=auto 让求解器自动变步长，可能漏掉开关动作时刻，降低 Bridge Power 波形（Scope 观察到的电压电流）的可信度。建议在 powergui 中设置固定步长（如 Ts）。

**证据引用**(2 条):

1. [S2] `block` / `02_ee_b.slx` / `Bridge Power` / snippet 前 100 字:`Block Bridge Power(Scope) 位于 02_ee_b.slx/顶层,参数 BlockType=Scope,Floating=off,FontName=Verdana,FontSiz`
2. [S8] `block` / `02_ee_b.slx` / `powergui` / snippet 前 100 字:`Block powergui(PSB option menu block) 位于 02_ee_b.slx/顶层,参数 AutomaticDiscreteSolvers=off,BlockType=Re`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q02_ee_b_014 — 修改题

**题目**:如果我想改变桥式功率级的输出功率参考，应该优先检查哪些 Constant 和 Add block，而不是直接改 Scope 前的信号？

**mxa 答案**(confidence: low):

从现有证据看，模型中唯一可识别的 Constant block 是 'Generator Type'（位于 Control 子系统，值为 0），它可能是模式选择而非功率参考。由于证据清单中未列出任何 Add block 或其他 Constant 用于功率参考，建议你打开模型后全局搜索 Constant 和 Add 类型模块，重点关注名称含 'Pref'、'P_ref'、'Power' 或类似关键词的模块。直接修改 Scope 前的信号不会改变仿真结果，应调整 Constant block 的参数。

**证据引用**(1 条):

1. [S4] `block` / `02_ee_b.slx` / `Generator Type` / snippet 前 100 字:`Block Generator Type(Constant) 位于 02_ee_b.slx/Control,参数 BlockType=Constant,FontName=Verdana,FontSiz`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q02_ee_b_015 — 修改题

**题目**:我想让 Bridge Power 的波形更平滑或更容易分析，应该改采样/仿真设置，还是在测量和信号处理 block 上调？

**mxa 答案**(confidence: medium):

波形平滑度主要由仿真步长和PWM载波频率决定。建议优先在仿真设置中减小固定步长（如设为1e-6 s），或在Scope属性中启用“Limit data points to last”并增大采样率。PWM Generator的载波频率Fc（见S1等）已配置，增大Fc可提高波形分辨率，但会增加仿真负担。Nearest Level Pulse Generator（S8）也可能影响波形，必要时可调整其参数。当前证据未显示额外滤波模块，若有需要，可在PWM输出后添加低通滤波器。

**证据引用**(3 条):

1. [S1] `block` / `02_ee_b.slx` / `PWM Generator (P)` / snippet 前 100 字:`Block PWM Generator (P)(PWM Generator (Multilevel)) 位于 02_ee_b.slx/Control,参数 BlockType=Reference,Br`
2. [S7] `block` / `02_ee_b.slx` / `Bridge Power` / snippet 前 100 字:`Block Bridge Power(Scope) 位于 02_ee_b.slx/顶层,参数 BlockType=Scope,Floating=off,FontName=Verdana,FontSiz`
3. [S8] `block` / `02_ee_b.slx` / `Nearest Level Pulse Generator` / snippet 前 100 字:`Block Nearest Level Pulse Generator(SubSystem) 位于 02_ee_b.slx/Control,参数 BlockType=SubSystem,FontNam`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---


## 03_ee_c

### Q03_ee_c_001 — 总体题

**题目**:这个 03_ee_c 工程整体是在模拟一个新能源并网系统吗？我看到 220kV、35kV、690V 和 5 km line，但不确定主研究对象。

**mxa 答案**(confidence: medium):

是的，根据项目总览和子系统结构，该工程模拟的是一个新能源并网系统（如风电或光伏），包含网侧变流器、MPPT（最大功率点跟踪）、桨距控制、三电平PWM调制等模块。电压等级220kV、35kV、690V和5 km线路表明是一个多电压等级并网系统，主研究对象可能是永磁同步发电机（PMSG）或全功率变流器并网。

**证据引用**(2 条):

1. [S1] `overview` / `__project_overview__` / `__project_overview__` / snippet 前 100 字:`项目 03_ee_c EE SLX 类型 new_energy。03_ee_c is a Simulink-only electrical engineering model with 789 blo`
2. [S4] `subsystem` / `03_ee_c.slx` / `Control` / snippet 前 100 字:`子系统 Control 在 03_ee_c.slx 内,包含 692 个 block。子 block:Vabc_grid,Iabc_grid_conv,Vabc_LL_stator,Iabc_stat`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q03_ee_c_002 — 总体题

**题目**:03_ee_c.slx 的主入口就是根层模型吗？从 220 kV 电源到 690 V 侧，应该按什么顺序读这个系统？

**mxa 答案**(confidence: low):

根据当前工程文件,我能定位到 03_ee_c.slx / <root> / SubSystem、03_ee_c.slx / Control / Discrete 3-phase PWM Ge 这些位置,但结构化信息还不足以可靠回答。建议先看相关 init 参数脚本,或在 MATLAB 命令窗里查变量赋值位置。

**证据引用**(0 条):

无

**Fallback**:invalid_or_missing_citations

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q03_ee_c_003 — 总体题

**题目**:这个模型有 789 个 block 和 27 个 subsystem，整体是按电压等级分层，还是按控制、测量、功率级分层？

**mxa 答案**(confidence: high):

该模型整体是按电压等级分层的。证据显示，模型中有独立的 '2-level Type' 和 '3-level Type' 子系统，并通过 'Select 2- or 3-level' 子系统进行选择，表明不同电压等级的 PWM 发生器被分层组织。

**证据引用**(3 条):

1. [S1] `block` / `03_ee_c.slx` / `3-level Type` / snippet 前 100 字:`Block 3-level Type(SubSystem) 位于 03_ee_c.slx/Discrete 3-phase PWM Generator,参数 BlockType=SubSystem,P`
2. [S3] `block` / `03_ee_c.slx` / `Select 2- or 3-level` / snippet 前 100 字:`Block Select 2- or 3-level(SubSystem) 位于 03_ee_c.slx/Discrete 3-phase PWM Generator,参数 BlockType=Sub`
3. [S7] `block` / `03_ee_c.slx` / `2-level Type` / snippet 前 100 字:`Block 2-level Type(SubSystem) 位于 03_ee_c.slx/Discrete 3-phase PWM Generator1,参数 BlockType=SubSystem,`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q03_ee_c_004 — 总体题

**题目**:如果只想先把主电气链路搞清楚，220 kV 电源、220/35 kV 变压器、5 km line、35 kV/690 V 变压器之间的阅读路径是什么？

**mxa 答案**(confidence: high):

主电气链路阅读路径：依次是 S1（220 kV 电源）→ S3（220/35 kV 变压器）→ S4（5 km line）→ S7（35 kV/690 V 变压器）。这些模块均位于顶层，按信号流向串联，构成从电网到低压侧的输电通道。

**证据引用**(4 条):

1. [S1] `block` / `03_ee_c.slx` / `220 kV` / snippet 前 100 字:`Block 220 kV(Three-Phase Programmable Voltage Source) 位于 03_ee_c.slx/顶层,参数 Amplitudes=[1 0.4 1.0],Ba`
2. [S3] `block` / `03_ee_c.slx` / `220 kV/35 kV 50 MVA` / snippet 前 100 字:`Block 220 kV/35 kV 50 MVA(Three-Phase Transformer (Two Windings)) 位于 03_ee_c.slx/顶层,参数 AttributesFor`
3. [S4] `block` / `03_ee_c.slx` / `5 km line` / snippet 前 100 字:`Block 5 km line(Three-Phase PI Section Line) 位于 03_ee_c.slx/顶层,参数 AttributesFormatString=\n,Backgrou`
4. [S7] `block` / `03_ee_c.slx` / `35 kV/ 690 V 5*2.5 MVA` / snippet 前 100 字:`Block 35 kV/ 690 V 5*2.5 MVA(Three-Phase Transformer (Two Windings)) 位于 03_ee_c.slx/顶层,参数 Attributes`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q03_ee_c_005 — 总体题

**题目**:这个工程更适合用来分析电网侧扰动、线路影响，还是低压侧变流器并网行为？从导览信息看应该怎么判断？

**mxa 答案**(confidence: high):

从导览信息看，这个工程包含220 kV/35 kV变压器（S3）和大容量互感器（S5），属于高压电网侧模型，同时存在PMSG-side和Grid-side变流器控制系统（S7、S8），因此更适合分析电网侧扰动、线路影响以及低压侧变流器并网行为。总览（S4）也指出需关注源、测量、控制和功率级信号路径，进一步支持这一判断。

**证据引用**(5 条):

1. [S3] `block` / `03_ee_c.slx` / `220 kV/35 kV 50 MVA` / snippet 前 100 字:`Block 220 kV/35 kV 50 MVA(Three-Phase Transformer (Two Windings)) 位于 03_ee_c.slx/顶层,参数 AttributesFor`
2. [S4] `overview` / `__project_overview__` / `__project_overview__` / snippet 前 100 字:`项目 03_ee_c EE SLX 类型 new_energy。03_ee_c is a Simulink-only electrical engineering model with 789 blo`
3. [S5] `block` / `03_ee_c.slx` / `2500 MVA X0/X1=3` / snippet 前 100 字:`Block 2500 MVA X0/X1=3(Three-Phase Mutual Inductance Z1-Z0) 位于 03_ee_c.slx/顶层,参数 AttributesFormatStr`
4. [S7] `block` / `03_ee_c.slx` / `Grid-side converter Control system` / snippet 前 100 字:`Block Grid-side converter Control system(SubSystem) 位于 03_ee_c.slx/Control,参数 BackgroundColor=lightB`
5. [S8] `block` / `03_ee_c.slx` / `PMSG-side converter Control system` / snippet 前 100 字:`Block PMSG-side converter Control system(SubSystem) 位于 03_ee_c.slx/Control,参数 BackgroundColor=lightB`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q03_ee_c_006 — 模块题

**题目**:“220 kV/35 kV 50 MVA”这个变压器在系统中承担什么接口作用？它前后两侧的测量点应该怎么配合看？

**mxa 答案**(confidence: medium):

该变压器是系统的主降压变压器，将220 kV电网电压降至35 kV，作为级联的第一级变电环节。它处于220 kV电源和下游35 kV/690 V变压器之间，承担功率传输和电压变换的接口作用。前后测量点的配合：前侧（高压侧）应关注电网侧电压（220 kV）、电流、有功/无功功率及谐波（从Three-Phase Programmable Voltage Source可知电源可编程，可设谐波）；后侧（低压侧）应关注35 kV母线电压、电流及功率，这些是下游负载和变流器控制的基础。典型做法是分别在变压器两侧安装三相电压电流测量模块（如Three-Phase V-I Measurement），对比两侧功率可计算变压器效率及损耗，同时监测电压跌落或暂态事件。

**证据引用**(2 条):

1. [S1] `block` / `03_ee_c.slx` / `220 kV/35 kV 50 MVA` / snippet 前 100 字:`Block 220 kV/35 kV 50 MVA(Three-Phase Transformer (Two Windings)) 位于 03_ee_c.slx/顶层,参数 AttributesFor`
2. [S4] `block` / `03_ee_c.slx` / `220 kV` / snippet 前 100 字:`Block 220 kV(Three-Phase Programmable Voltage Source) 位于 03_ee_c.slx/顶层,参数 Amplitudes=[1 0.4 1.0],Ba`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q03_ee_c_007 — 模块题

**题目**:“2500 MVA X0/X1=3”这个 Three-Phase Mutual Inductance Z1-Z0 block 主要是在表示什么电网等效？它和普通 RLC 支路有什么区别？

**mxa 答案**(confidence: medium):

“2500 MVA X0/X1=3”这个Three-Phase Mutual Inductance Z1-Z0 block表示一个三相电力系统等效，具体是用于模拟输电线路或变压器的零序和正序阻抗，常用于短路故障分析。X0/X1=3表示零序电抗是正序电抗的3倍，2500 MVA是基准容量。与普通RLC支路不同，该模块专门针对电力系统对称分量法设计，能够分别设置正序和零序参数，而RLC支路只能模拟单一阻抗特性。

**证据引用**(1 条):

1. [S1] `block` / `03_ee_c.slx` / `2500 MVA X0/X1=3` / snippet 前 100 字:`Block 2500 MVA X0/X1=3(Three-Phase Mutual Inductance Z1-Z0) 位于 03_ee_c.slx/顶层,参数 AttributesFormatStr`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q03_ee_c_008 — 模块题

**题目**:“5 km line”这个 Three-Phase PI Section Line 在模型里会引入哪些线路效应？我应该看哪些前后端信号来验证它的影响？

**mxa 答案**(confidence: high):

该 PI 段线路（5 km）引入了电阻、电感（1.05 mH 正序/3.32 mH 零序）及电容（11.33 nF 正序/5.01 nF 零序）效应，在工频 50 Hz 下会产生电压降、相移和充电无功。应观测线路两端的三相电压（Vabc）和电流（Iabc），通过比较幅值、相位及无功功率来验证线路压降和充电效应。

**证据引用**(1 条):

1. [S1] `block` / `03_ee_c.slx` / `5 km line` / snippet 前 100 字:`Block 5 km line(Three-Phase PI Section Line) 位于 03_ee_c.slx/顶层,参数 AttributesFormatString=\n,Backgrou`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q03_ee_c_009 — 模块题

**题目**:B220、B35、B690 这三个 Three-Phase VI Measurement 分别对应哪些电压等级的观测点？它们在分析故障或稳态时怎么配合使用？

**mxa 答案**(confidence: low):

从证据看，B690、B35、B220 三个测量模块的名称暗示它们对应的电压等级：B690 可能为 690V（低压），B35 可能为 35kV（中压），B220 可能为 220kV（高压）。但工程中未明确给出电压参数，请查阅模型中的电源或线路设置。配合使用时，B690 和 B35 同时测量电压和电流（CurrentMeasurement=yes），适合故障分析（需观察电流波形）；B220 只测电压，适合稳态电压观测。注意 B220 的标签写的是 Vabc_B120，与块名不一致，需核实。

**证据引用**(3 条):

1. [S1] `block` / `03_ee_c.slx` / `B690` / snippet 前 100 字:`Block B690(Three-Phase VI Measurement) 位于 03_ee_c.slx/顶层,参数 BackgroundColor=black,BlockType=Referenc`
2. [S2] `block` / `03_ee_c.slx` / `B35` / snippet 前 100 字:`Block B35(Three-Phase VI Measurement) 位于 03_ee_c.slx/顶层,参数 BackgroundColor=black,BlockType=Reference`
3. [S3] `block` / `03_ee_c.slx` / `B220` / snippet 前 100 字:`Block B220(Three-Phase VI Measurement) 位于 03_ee_c.slx/顶层,参数 BackgroundColor=black,BlockType=Referenc`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q03_ee_c_010 — 模块题

**题目**:Bus Selector 和 Bus Selector1 从测量总线里取了哪些量？我怎么确认后续控制或显示用的是相电压、线电压还是电流？

**mxa 答案**(confidence: medium):

各 Bus Selector 取量如下：
- S1 (PMSG-side Converter Control system 内 Bus Selector1): 输出 Vdc_V、Stator dq Frame.Idq_s、Stator dq Frame.wr_pu、Stator dq Frame.sin_cos_statror 以及 V[…]（可能为电压信号，具体被截断）。
- S2 (MPPT & Pitch Control 内 Bus Selector2): 输出 Stator dq Frame.wr_pu、PQ&V.P_pu。
- S3 (顶层 Bus Selector1): 输出 Grid dq Frame.Idq_g、Stator dq Frame.Idq_s。
- S4 (Wind Turbine 内 Bus Selector): 输出 Rotor speed wm (rad/s)、Rotor angle thetam (rad)、Electromagnetic torque Te (N*m)。
- S5 (Grid-side converter Control system 内 Bus Selector): 输出 Grid dq Frame.Vdq_g、Grid dq Frame.Idq_g、Grid dq Frame.w_pu、Vdc_V、Qref、PQ&V.Q_[…]。
- S6 (顶层 Bus Selector): 输出 Vdc_V、Stator dq Frame.wr_pu、PQ&V.P_pu、PQ&V.Q_pu。

要确认后续控制或显示所用的是相电压、线电压还是电流，请追踪这些输出信号所连接的模块。例如，若信号进入 Park 变换或 Clarke 变换模块，则输入可能是相电压/电流；若直接用于 PI 调节器或示波器，则需查看模块参数或数据类型。从信号命名看，'Idq_s' 和 'Vdq_g' 是 dq 轴分量，并非直接相电压或线电压，可能已通过变换获得。建议在 Simulink 中双击连接线，查看信号标签或使用 'Signal Properties' 确认。

**证据引用**(6 条):

1. [S1] `block` / `03_ee_c.slx` / `Bus Selector1` / snippet 前 100 字:`Block Bus Selector1(BusSelector) 位于 03_ee_c.slx/PMSG-side converter Control system,参数 BlockType=BusS`
2. [S2] `block` / `03_ee_c.slx` / `Bus Selector2` / snippet 前 100 字:`Block Bus Selector2(BusSelector) 位于 03_ee_c.slx/MPPT & Pitch Control,参数 BlockType=BusSelector,Name=<`
3. [S3] `block` / `03_ee_c.slx` / `Bus Selector1` / snippet 前 100 字:`Block Bus Selector1(BusSelector) 位于 03_ee_c.slx/顶层,参数 BlockType=BusSelector,Name=<Idq_s>,OutputSigna`
4. [S4] `block` / `03_ee_c.slx` / `Bus Selector` / snippet 前 100 字:`Block Bus Selector(BusSelector) 位于 03_ee_c.slx/Wind Turbine,参数 BlockType=BusSelector,Name=<Electroma`
5. [S5] `block` / `03_ee_c.slx` / `Bus Selector` / snippet 前 100 字:`Block Bus Selector(BusSelector) 位于 03_ee_c.slx/Grid-side converter Control system,参数 BlockType=BusSe`
6. [S6] `block` / `03_ee_c.slx` / `Bus Selector` / snippet 前 100 字:`Block Bus Selector(BusSelector) 位于 03_ee_c.slx/顶层,参数 BlockType=BusSelector,Name=<Q_pu>,OutputSignals`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q03_ee_c_011 — 参数题

**题目**:220 kV/35 kV 50 MVA 和 35 kV/690 V 5*2.5 MVA 这两级变压器容量设置是否协调？会不会在低压侧形成容量瓶颈？

**mxa 答案**(confidence: high):

容量不协调，低压侧存在容量瓶颈。第一级变压器容量为50 MVA，第二级变压器标注“5*2.5 MVA”通常表示5台2.5 MVA并联，总容量仅12.5 MVA，远小于第一级，低压侧最大传输功率受限，形成瓶颈。

**证据引用**(2 条):

1. [S1] `block` / `03_ee_c.slx` / `220 kV/35 kV 50 MVA` / snippet 前 100 字:`Block 220 kV/35 kV 50 MVA(Three-Phase Transformer (Two Windings)) 位于 03_ee_c.slx/顶层,参数 AttributesFor`
2. [S2] `block` / `03_ee_c.slx` / `35 kV/ 690 V 5*2.5 MVA` / snippet 前 100 字:`Block 35 kV/ 690 V 5*2.5 MVA(Three-Phase Transformer (Two Windings)) 位于 03_ee_c.slx/顶层,参数 Attributes`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q03_ee_c_012 — 参数题

**题目**:5 km line 用 PI Section Line 表示时，线路长度设为 5 km 对这个电压等级和仿真目标是否合理？

**mxa 答案**(confidence: medium):

5 km 的线路使用 PI Section Line 模型是合理的。对于短线路（通常几百公里以下），集中参数 PI 模型已能准确反映线路的电阻、电感和电容特性。5 km 属于很短距离，分布参数效应可忽略，因此用单个 PI 段即可。结合工程中 2500 MVA 的变压器（S4），推测系统电压等级较高（如 220 kV 或 500 kV），但即便如此，5 km 长度仍远小于需考虑分布效应的典型门限（约 250 km），故 PI 模型适用。

**证据引用**(2 条):

1. [S1] `block` / `03_ee_c.slx` / `5 km line` / snippet 前 100 字:`Block 5 km line(Three-Phase PI Section Line) 位于 03_ee_c.slx/顶层,参数 AttributesFormatString=\n,Backgrou`
2. [S4] `block` / `03_ee_c.slx` / `2500 MVA X0/X1=3` / snippet 前 100 字:`Block 2500 MVA X0/X1=3(Three-Phase Mutual Inductance Z1-Z0) 位于 03_ee_c.slx/顶层,参数 AttributesFormatStr`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q03_ee_c_013 — 参数题

**题目**:“2500 MVA X0/X1=3”里的短路容量和零序/正序比值对三相不平衡或接地故障分析有什么影响？这些取值需要怎么检查合理性？

**mxa 答案**(confidence: medium):

短路容量 2500 MVA 用于定义该元件的三相短路电流水平，数值越大表示系统等效阻抗越小，短路电流越大。零序/正序电抗比 X0/X1=3 是典型电力变压器中性点接地时的经验取值（通常 X0/X1 在 1~3 之间），该比值直接影响单相接地故障时零序电流大小：比值越大，零序阻抗越大，接地故障电流越小；反之则接地电流更大。在三相不平衡分析中，该参数通过序分量法影响负序和零序网络，从而决定不平衡电压和电流的分布。

要检查合理性：1）将 2500 MVA 视为基准容量，结合系统额定电压（可能是 220 kV？因 S2 有 220 kV/35 kV 变压器），换算得到正序阻抗标幺值（Z1 = V^2 / S = 220^2 / 2500 ≈ 19.36 Ω）；2）由 X0/X1=3 可得零序电抗约为正序电抗的 3 倍；3）验证是否与所模拟的实际电力系统短路容量、变压器中性点接地方式相符。可查阅工程初始参数文件或设计规范确认。

**证据引用**(1 条):

1. [S1] `block` / `03_ee_c.slx` / `2500 MVA X0/X1=3` / snippet 前 100 字:`Block 2500 MVA X0/X1=3(Three-Phase Mutual Inductance Z1-Z0) 位于 03_ee_c.slx/顶层,参数 AttributesFormatStr`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q03_ee_c_014 — 修改题

**题目**:如果我想把并网点从 35 kV 侧移动到 220 kV 侧或 690 V 侧，主要需要调整哪些变压器、线路和测量 block？

**mxa 答案**(confidence: low):

从现有证据看，工程包含220 kV/35 kV变压器（S1）和35 kV/690 V变压器（S4），以及220 kV电源（S2）和阻抗（S7）。若将并网点移至220 kV侧，需调整S1的连接方式或直接接入220 kV母线；若移至690 V侧，需通过S4变压器。但证据中未明确线路和测量模块的具体位置，建议在Simulink模型中查看变压器前后连接以及测量点（如电压电流测量）的block，并相应重新连接。

**证据引用**(4 条):

1. [S1] `block` / `03_ee_c.slx` / `220 kV/35 kV 50 MVA` / snippet 前 100 字:`Block 220 kV/35 kV 50 MVA(Three-Phase Transformer (Two Windings)) 位于 03_ee_c.slx/顶层,参数 AttributesFor`
2. [S2] `block` / `03_ee_c.slx` / `220 kV` / snippet 前 100 字:`Block 220 kV(Three-Phase Programmable Voltage Source) 位于 03_ee_c.slx/顶层,参数 Amplitudes=[1 0.4 1.0],Ba`
3. [S4] `block` / `03_ee_c.slx` / `35 kV/ 690 V 5*2.5 MVA` / snippet 前 100 字:`Block 35 kV/ 690 V 5*2.5 MVA(Three-Phase Transformer (Two Windings)) 位于 03_ee_c.slx/顶层,参数 Attributes`
4. [S7] `block` / `03_ee_c.slx` / `2500 MVA X0/X1=3` / snippet 前 100 字:`Block 2500 MVA X0/X1=3(Three-Phase Mutual Inductance Z1-Z0) 位于 03_ee_c.slx/顶层,参数 AttributesFormatStr`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q03_ee_c_015 — 修改题

**题目**:我想研究线路长度变化对低压侧电压波动的影响，应该改 5 km line 这个 block 的哪些参数，并观察 B35 还是 B690？

**mxa 答案**(confidence: high):

修改 5 km line（三相PI段线路）的 Length 参数（当前为5 km）即可改变线路长度。低压侧（690 V）电压波动应观察 Block B690（Three-Phase VI Measurement），它测量的是低压侧电压（Vabc_B690），而 B35 测量的是高压侧（35 kV）。

**证据引用**(2 条):

1. [S1] `block` / `03_ee_c.slx` / `5 km line` / snippet 前 100 字:`Block 5 km line(Three-Phase PI Section Line) 位于 03_ee_c.slx/顶层,参数 AttributesFormatString=\n,Backgrou`
2. [S2] `block` / `03_ee_c.slx` / `B690` / snippet 前 100 字:`Block B690(Three-Phase VI Measurement) 位于 03_ee_c.slx/顶层,参数 BackgroundColor=black,BlockType=Referenc`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---


## 04_ee_d

### Q04_ee_d_001 — 总体题

**题目**:这个 04_ee_d 工程整体是在研究 220kV 到 35kV 系统的什么问题？我看到电源、变压器、电容支路和测量点，但主目标不明确。

**mxa 答案**(confidence: high):

该工程整体研究220kV至35kV降压系统的电压控制或功率控制问题。电源（220kV Three-Phase Programmable Voltage Source）经变压器（220kV/35kV 10%）降至35kV，通过abc-dq坐标变换（Transformation abc --> dq）和离散PI控制器（Discrete PI Controller1）调节电压或功率，同时包含Vdc输入和dq参考值（Vdq*）用于控制目标。主要目标是实现35kV侧电压稳定或有功/无功调节。

**证据引用**(6 条):

1. [S1] `overview` / `__project_overview__` / `__project_overview__` / snippet 前 100 字:`项目 04_ee_d EE SLX 类型 power_electronics。04_ee_d is a Simulink-only electrical engineering model with `
2. [S2] `block` / `04_ee_d.slx` / `220kV` / snippet 前 100 字:`Block 220kV(Three-Phase Programmable Voltage Source) 位于 04_ee_d.slx/顶层,参数 Amplitudes=[1 0.8 1.0],Bac`
3. [S3] `block` / `04_ee_d.slx` / `220kV/35kV 10%` / snippet 前 100 字:`Block 220kV/35kV 10%(Three-Phase Transformer (Two Windings)) 位于 04_ee_d.slx/顶层,参数 AttributesFormatSt`
4. [S4] `subsystem` / `04_ee_d.slx` / `Transformation abc --> dq` / snippet 前 100 字:`子系统 Transformation abc --> dq 在 04_ee_d.slx 内,包含 16 个 block。子 block:wt,Vabc,Iabc,Bus Creator,Bus Cre`
5. [S7] `subsystem` / `04_ee_d.slx` / `Discrete PI Controller1` / snippet 前 100 字:`子系统 Discrete PI Controller1 在 04_ee_d.slx 内,包含 9 个 block。子 block:Error,Discrete-Time Integrator,Kp4,`
6. [S8] `subsystem` / `04_ee_d.slx` / `Subsystem4` / snippet 前 100 字:`子系统 Subsystem4 在 04_ee_d.slx 内,包含 15 个 block。子 block:Vdq*,wt,Vdc,0-1,Avoid division by zero,Cartesia`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q04_ee_d_002 — 总体题

**题目**:04_ee_d.slx 是主入口的话，根层应该先看 220kV 电源、1226 互感阻抗，还是先看 C、C1 这些 RLC 支路？

**mxa 答案**(confidence: high):

建议按信号流方向先看 220kV 电源（S1）和变压器（S6），因为它们是主要的源和耦合元件，决定了系统电压等级和能量传递路径。然后再看 C1 等 RLC 支路（S3），它们构成负载或滤波网络。注意证据清单中未出现名为“1226 互感阻抗”的模块，请确认是否在其他子系统或文件中。

**证据引用**(4 条):

1. [S1] `block` / `04_ee_d.slx` / `220kV` / snippet 前 100 字:`Block 220kV(Three-Phase Programmable Voltage Source) 位于 04_ee_d.slx/顶层,参数 Amplitudes=[1 0.8 1.0],Bac`
2. [S5] `overview` / `__project_overview__` / `__project_overview__` / snippet 前 100 字:`项目 04_ee_d EE SLX 类型 power_electronics。04_ee_d is a Simulink-only electrical engineering model with `
3. [S6] `block` / `04_ee_d.slx` / `220kV/35kV 10%` / snippet 前 100 字:`Block 220kV/35kV 10%(Three-Phase Transformer (Two Windings)) 位于 04_ee_d.slx/顶层,参数 AttributesFormatSt`
4. [S3] `block` / `04_ee_d.slx` / `C1` / snippet 前 100 字:`Block C1(Parallel RLC Branch) 位于 04_ee_d.slx/顶层,参数 AttributesFormatString=\n,BlockType=Reference,Bra`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q04_ee_d_003 — 总体题

**题目**:这个模型只有 126 个 block、8 个 subsystem，相比大型并网模型是不是更偏向某个局部电网或补偿装置的分析？

**mxa 答案**(confidence: medium):

从现有block（220kV变压器S5、可编程电压源S8、电流调节器S7）来看，该模型确实更偏向于局部电网（如变电站）或补偿装置（如STATCOM/SVC）的仿真，而非大型多机电力系统。

**证据引用**(2 条):

1. [S5] `block` / `04_ee_d.slx` / `220kV/35kV 10%` / snippet 前 100 字:`Block 220kV/35kV 10%(Three-Phase Transformer (Two Windings)) 位于 04_ee_d.slx/顶层,参数 AttributesFormatSt`
2. [S8] `block` / `04_ee_d.slx` / `220kV` / snippet 前 100 字:`Block 220kV(Three-Phase Programmable Voltage Source) 位于 04_ee_d.slx/顶层,参数 Amplitudes=[1 0.8 1.0],Bac`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q04_ee_d_004 — 总体题

**题目**:如果我要画这个工程的简化单线图，应该怎样把 220kV source、220kV/35kV 变压器、C/C1 和测量点组织起来？

**mxa 答案**(confidence: low):

根据工程证据，220kV 三相可编程电压源（S1）输出经 220kV/35kV 变压器（S2）降压至 35kV。其中 C/C1 在现有证据中未明确指出其具体位置，推测可能是直流侧电容（S7 为直流电压源）或交流侧滤波电容。测量点可在变压器二次侧、VSC 控制器入口等处设置。建议打开工程文件检查子系统和元件命名以确认 C/C1。

**证据引用**(4 条):

1. [S1] `block` / `04_ee_d.slx` / `220kV` / snippet 前 100 字:`Block 220kV(Three-Phase Programmable Voltage Source) 位于 04_ee_d.slx/顶层,参数 Amplitudes=[1 0.8 1.0],Bac`
2. [S2] `block` / `04_ee_d.slx` / `220kV/35kV 10%` / snippet 前 100 字:`Block 220kV/35kV 10%(Three-Phase Transformer (Two Windings)) 位于 04_ee_d.slx/顶层,参数 AttributesFormatSt`
3. [S7] `block` / `04_ee_d.slx` / `DC Voltage Source` / snippet 前 100 字:`Block DC Voltage Source(DC Voltage Source) 位于 04_ee_d.slx/顶层,参数 Amplitude=Vdc_nom,BlockRotation=270,`
4. [S4] `overview` / `__project_overview__` / `__project_overview__` / snippet 前 100 字:`项目 04_ee_d EE SLX 类型 power_electronics。04_ee_d is a Simulink-only electrical engineering model with `

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q04_ee_d_005 — 总体题

**题目**:这个工程的整体架构里，哪些 block 属于一次电气网络，哪些只是测量和信号选择？能不能按根层信号流帮我区分？

**mxa 答案**(confidence: medium):

从顶层看，B1 和 B2（Three-Phase VI Measurement）是三相电压电流测量模块，属于测量环节；Step 是阶跃信号源，属于信号输入；Transformation abc --> dq 子系统内含 abc→dq 坐标变换，属于信号处理/选择。目前顶层未包含电机、电源等一次电气网络元件。若需区分完整的功率回路，请检查工程中是否存在电机或电源子系统（证据清单未列出）。

**证据引用**(3 条):

1. [S1] `block` / `04_ee_d.slx` / `B1` / snippet 前 100 字:`Block B1(Three-Phase VI Measurement) 位于 04_ee_d.slx/顶层,参数 BackgroundColor=black,BlockType=Reference,`
2. [S3] `block` / `04_ee_d.slx` / `Step` / snippet 前 100 字:`Block Step(Step) 位于 04_ee_d.slx/顶层,参数 Before=0.5,BlockType=Step,Position=[625, 515, 655, 545],Sample`
3. [S6] `subsystem` / `04_ee_d.slx` / `Transformation abc --> dq` / snippet 前 100 字:`子系统 Transformation abc --> dq 在 04_ee_d.slx 内,包含 16 个 block。子 block:wt,Vabc,Iabc,Bus Creator,Bus Cre`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q04_ee_d_006 — 模块题

**题目**:“1226”这个 Three-Phase Mutual Inductance Z1-Z0 block 在模型里具体表示哪一段电网阻抗？它对正序和零序通道分别有什么作用需要看？

**mxa 答案**(confidence: medium):

这个 block 表示电网的一段三相线路或变压器的等效阻抗，其中 Z1 为正序阻抗，Z0 为零序阻抗。正序通道（Z1）影响三相平衡运行时的电压降和功率传输；零序通道（Z0）则用于分析单相接地等不对称故障时的零序电流分布。具体数值需在 block 参数中查看。

**证据引用**(1 条):

1. [S1] `block` / `04_ee_d.slx` / `1226` / snippet 前 100 字:`Block 1226(Three-Phase Mutual Inductance Z1-Z0) 位于 04_ee_d.slx/顶层,参数 AttributesFormatString=\n,Backg`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q04_ee_d_007 — 模块题

**题目**:C 和 C1 这两个 Parallel RLC Branch 是并联补偿、电容滤波，还是两个不同母线上的负载等效？怎么从连接关系判断？

**mxa 答案**(confidence: high):

这两个 Parallel RLC Branch 位于顶层，参数中电容值都使用 C_DClink，初始电压同为 Vdc_nom，说明它们属于同一直流母线。其中 C 的 BranchType 设为 C（电容支路），C1 设为 R（电阻支路），因此它们共同构成直流侧的并联滤波与阻尼电路：C 提供滤波电容，C1 提供阻尼电阻，用以吸收直流侧纹波并抑制谐振。从连接关系看，它们均挂接在同一直流母线上（参数中 LConnTagsString 均为 'a'），属于并联关系，而非不同母线上的负载等效。

**证据引用**(2 条):

1. [S1] `block` / `04_ee_d.slx` / `C1` / snippet 前 100 字:`Block C1(Parallel RLC Branch) 位于 04_ee_d.slx/顶层,参数 AttributesFormatString=\n,BlockType=Reference,Bra`
2. [S2] `block` / `04_ee_d.slx` / `C` / snippet 前 100 字:`Block C(Parallel RLC Branch) 位于 04_ee_d.slx/顶层,参数 AttributesFormatString=\n,BlockMirror=on,BlockRota`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q04_ee_d_008 — 模块题

**题目**:“220kV/35kV 10%”这个三相变压器 block 的 10% 是在模型里怎样参与电压变换和短路阻抗表现的？

**mxa 答案**(confidence: low):

从证据看，三相变压器 block 的“10%”通常指短路阻抗百分比（即漏抗标幺值），用于模拟变压器内部阻抗引起的电压降和短路电流限制。但当前证据（如[S1]）只显示该 block 引用数据文件 'basic_model'，未给出具体参数，因此无法从现有证据确认该值在模型中的具体实现方式。

**证据引用**(1 条):

1. [S1] `block` / `04_ee_d.slx` / `220kV/35kV 10%` / snippet 前 100 字:`Block 220kV/35kV 10%(Three-Phase Transformer (Two Windings)) 位于 04_ee_d.slx/顶层,参数 AttributesFormatSt`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q04_ee_d_009 — 模块题

**题目**:B1 和 B2 这两个 Three-Phase VI Measurement 分别测的是变压器哪一侧或哪个母线？它们的输出后面被 Bus Selector 怎么拆分？

**mxa 答案**(confidence: low):

根据现有证据，B1和B2均为位于顶层的Three-Phase V-I Measurement，它们分别测量哪一侧母线或变压器在文件中未明确标注。通常这类测量用于采集网侧和机侧电压电流。B1和B2的输出都是三相电压和电流复合信号，Bus Selector2（S2）将其拆分为V_abc和Iabc，Bus Selector1（S6）则输出Udq、Idq、P&Q、Vdc。但具体哪个选择器对应哪个测量无法从证据中确定，建议打开模型查看连接。

**证据引用**(4 条):

1. [S1] `block` / `04_ee_d.slx` / `B2` / snippet 前 100 字:`Block B2(Three-Phase VI Measurement) 位于 04_ee_d.slx/顶层,参数 BackgroundColor=black,BlockType=Reference,`
2. [S2] `block` / `04_ee_d.slx` / `Bus Selector2` / snippet 前 100 字:`Block Bus Selector2(BusSelector) 位于 04_ee_d.slx/顶层,参数 BlockType=BusSelector,FontSize=12,Name=<Iabc>,`
3. [S4] `block` / `04_ee_d.slx` / `B1` / snippet 前 100 字:`Block B1(Three-Phase VI Measurement) 位于 04_ee_d.slx/顶层,参数 BackgroundColor=black,BlockType=Reference,`
4. [S6] `block` / `04_ee_d.slx` / `Bus Selector1` / snippet 前 100 字:`Block Bus Selector1(BusSelector) 位于 04_ee_d.slx/顶层,参数 BlockType=BusSelector,FontSize=12,Name=<Vdc>,O`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q04_ee_d_010 — 模块题

**题目**:1246 这个 Voltage Measurement 和 B1/B2 三相 VI Measurement 有什么分工？为什么模型里同时需要单相电压测量和三相测量？

**mxa 答案**(confidence: high):

Voltage Measurement (1246) 测量单相电压，通常用于直流侧或某相电压监测；Three-Phase VI Measurement (B1/B2) 同时测量三相电压和电流，适用于交流网络。模型同时使用二者是因为测量需求不同：单相测量用于直流母线或特定节点，三相测量用于三相交流线路（如电网侧或 VSC 输出侧），以满足监控、控制和保护的不同要求。

**证据引用**(4 条):

1. [S1] `block` / `04_ee_d.slx` / `1246` / snippet 前 100 字:`Block 1246(Voltage Measurement) 位于 04_ee_d.slx/顶层,参数 BlockType=Reference,ContentPreviewEnabled=off,L`
2. [S2] `block` / `04_ee_d.slx` / `B2` / snippet 前 100 字:`Block B2(Three-Phase VI Measurement) 位于 04_ee_d.slx/顶层,参数 BackgroundColor=black,BlockType=Reference,`
3. [S3] `block` / `04_ee_d.slx` / `B1` / snippet 前 100 字:`Block B1(Three-Phase VI Measurement) 位于 04_ee_d.slx/顶层,参数 BackgroundColor=black,BlockType=Reference,`
4. [S8] `overview` / `__project_overview__` / `__project_overview__` / snippet 前 100 字:`项目 04_ee_d EE SLX 类型 power_electronics。04_ee_d is a Simulink-only electrical engineering model with `

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q04_ee_d_011 — 参数题

**题目**:220kV/35kV 变压器标了 10% 阻抗，这个值对短路电流和电压跌落仿真是否敏感？需要怎么判断它是否合理？

**mxa 答案**(confidence: high):

10% 阻抗是电力变压器常见标幺值（典型范围 5%–15%），对短路电流和电压跌落仿真相当敏感：短路电流近似为额定电流除以阻抗标幺值，阻抗越大短路电流越小，电压跌落越轻。判断合理性的方法：1）核对实际变压器铭牌参数（制造商会给出阻抗电压百分数）；2）在仿真中对该参数做±20%的灵敏度扫描，观察三相短路电流峰值和 PCC 电压波形是否在可接受范围内。如果工程模拟的是特定变电站，还应查阅该站主变出厂报告。

**证据引用**(1 条):

1. [S1] `block` / `04_ee_d.slx` / `220kV/35kV 10%` / snippet 前 100 字:`Block 220kV/35kV 10%(Three-Phase Transformer (Two Windings)) 位于 04_ee_d.slx/顶层,参数 AttributesFormatSt`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q04_ee_d_012 — 参数题

**题目**:C 和 C1 的 RLC 参数如果用于无功补偿或滤波，应该根据 35kV 侧还是 220kV 侧的基准来检查它们的量级？

**mxa 答案**(confidence: medium):

C和C1的电容参数定义为C_DClink和Vdc_nom，说明它们是直流母线电容。其量级应基于直流母线电压（Vdc_nom）和功率等级来检查，而不是直接依据35kV或220kV侧交流基准。若需关联交流侧，可参考VSC所连变压器的35kV侧电压，但直流侧参数本身已独立定义。

**证据引用**(2 条):

1. [S2] `block` / `04_ee_d.slx` / `C1` / snippet 前 100 字:`Block C1(Parallel RLC Branch) 位于 04_ee_d.slx/顶层,参数 AttributesFormatString=\n,BlockType=Reference,Bra`
2. [S5] `block` / `04_ee_d.slx` / `C` / snippet 前 100 字:`Block C(Parallel RLC Branch) 位于 04_ee_d.slx/顶层,参数 AttributesFormatString=\n,BlockMirror=on,BlockRota`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q04_ee_d_013 — 参数题

**题目**:StopTime 设为 2 秒、FixedStep=auto，在这个含互感阻抗和并联 RLC 支路的电网模型里是否能覆盖关键暂态过程？

**mxa 答案**(confidence: low):

根据当前工程文件,我能定位到 04_ee_d.slx / <root> / Discrete PI Controller1、04_ee_d.slx / Current Controlller 这些位置,但结构化信息还不足以可靠回答。建议先看相关 init 参数脚本,或在 MATLAB 命令窗里查变量赋值位置。

**证据引用**(0 条):

无

**Fallback**:invalid_or_missing_citations

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q04_ee_d_014 — 修改题

**题目**:如果我想把补偿容量调大或调小，应该主要改 C、C1 这两个 Parallel RLC Branch 的哪些参数，并看哪些测量点验证？

**mxa 答案**(confidence: medium):

补偿容量主要由电容决定，因此应修改 C 和 C1 两个 Parallel RLC Branch 的 Capacitance 参数（即变量 C_DClink 的值）。增大 C_DClink 可提高补偿容量，减小则降低。验证时建议观察直流母线电压（如 Vdc_nom 相关测量点）或通过示波器查看电压、电流波形来确认补偿效果。

**证据引用**(2 条):

1. [S1] `block` / `04_ee_d.slx` / `C1` / snippet 前 100 字:`Block C1(Parallel RLC Branch) 位于 04_ee_d.slx/顶层,参数 AttributesFormatString=\n,BlockType=Reference,Bra`
2. [S3] `block` / `04_ee_d.slx` / `C` / snippet 前 100 字:`Block C(Parallel RLC Branch) 位于 04_ee_d.slx/顶层,参数 AttributesFormatString=\n,BlockMirror=on,BlockRota`

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

### Q04_ee_d_015 — 修改题

**题目**:我想把这个模型改成不同电压等级的变电站等效，除了 220kV 电源和 220kV/35kV 变压器，还要同步调整哪些测量和阻抗 block？

**mxa 答案**(confidence: medium):

除了修改220kV电源和220kV/35kV变压器参数，还需同步调整测量变换中的比例因子，特别是“Transformation abc → dq”子系统中的电压/电流基值（与额定电压相关）以及“Line to phase”子系统的转换系数。另外，若模型含线路阻抗block，应随之修改其标幺值参数；当前证据未明确列出具体阻抗block，建议检查模型中的串联RL或分布式参数线block。

**证据引用**(5 条):

1. [S1] `block` / `04_ee_d.slx` / `220kV/35kV 10%` / snippet 前 100 字:`Block 220kV/35kV 10%(Three-Phase Transformer (Two Windings)) 位于 04_ee_d.slx/顶层,参数 AttributesFormatSt`
2. [S2] `block` / `04_ee_d.slx` / `220kV` / snippet 前 100 字:`Block 220kV(Three-Phase Programmable Voltage Source) 位于 04_ee_d.slx/顶层,参数 Amplitudes=[1 0.8 1.0],Bac`
3. [S5] `subsystem` / `04_ee_d.slx` / `Transformation abc --> dq` / snippet 前 100 字:`子系统 Transformation abc --> dq 在 04_ee_d.slx 内,包含 16 个 block。子 block:wt,Vabc,Iabc,Bus Creator,Bus Cre`
4. [S4] `subsystem` / `04_ee_d.slx` / `Line to phase` / snippet 前 100 字:`子系统 Line to phase 在 04_ee_d.slx 内,包含 6 个 block。子 block:Vl,Fcn,Fcn1,Fcn2,Mux,Vabc`
5. [S7] `overview` / `__project_overview__` / `__project_overview__` / snippet 前 100 字:`项目 04_ee_d EE SLX 类型 power_electronics。04_ee_d is a Simulink-only electrical engineering model with `

---

#### 评分(满分 100;5 维:事实 30 / 引用 20 / 教学 20 / 可操作 20 / 不编造 10)

**PM**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

**研究生**:事实 __ / 引用 __ / 教学 __ / 可操作 __ / 不编造 __ / **总分 __**
- 备注:

---

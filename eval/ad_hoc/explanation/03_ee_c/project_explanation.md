# 03_ee_c.zip

本讲解只基于静态解析到的工程结构、参数和连接关系,没有运行仿真。
带有 `(推断)` 或 `(推断,无直接证据)` 的内容需要你运行仿真或查工程文档确认。

## 1. 工程在做什么

- 03_ee_c 是一个 Simulink 纯电气工程模型，包含 789 个模块和 916 条连接，用于模拟风力发电系统（含永磁同步发电机和网侧变换器控制）。 [E001]

## 2. 建议阅读顺序

- 建议先打开 03_ee_c.slx，观察根级信号路径；然后识别电源、测量、控制和功率模块；接着打开子系统跟踪信号分组和转换；最后比较关键模块参数与求解器设置。 [E004]

## 3. 关键子系统和模块

- 模型主要子系统包括：Wind Turbine（含 PMSG 和变换器，760 个模块）、Control（含 Grid-side 和 PMSG-side 控制，692 个模块）、Measurement and Transformation（260 个模块）、Grid-side converter Control system（95 个模块）和 PMSG-side converter Control system（51 个模块）。 [E124, E125, E126, E130, E133]

## 4. 信号连接逻辑

- B_grid (Three-Phase VI Measurement) 的三相输出直接连接到 Choke (Three-Phase Series RLC Branch) 的三相输入端。 [E136, E137, E138]
- Universal Bridge1 的交流侧三相输出连接到 B_grid1 (Three-Phase VI Measurement) 的三相输入端。 [E142, E143, E144]

## 5. 关键参数怎么看

- Deg->Rad 模块的增益设为 pi/180，用于将角度从度转换为弧度，以便后续三角函数计算。 [E017, E018]
- ->pu1 模块的增益设为 Pnom/Vnom_gen/Vnom_gen，用于将实际值转换为标幺值 (pu)，便于控制算法处理。 [E023, E024]
- ->pu2 模块的增益设为 Pnom/Vnom_gen/Vnom_gen，用于将实际值转换为标幺值 (pu)。 [E026, E027]
- ->pu3 模块的增益设为 Pnom/Vnom_gen/Vnom_gen*2*3.14*10.58，用于将速度信号转换为标幺值并包含常数转换。 [E029, E030]

## 6. 如果要修改先动哪里

- 如需修改直流电压控制回路，可调整 Grid-side converter Control system 中 Discrete PI Controller 的 Ki_dc 和 Kp_dc 参数（当前为工作区变量），然后通过 PMSG-side converter Control system 中的 Scope 观察响应。 [E066, E067, E117]

## 7. 应该观察哪些位置

- B_grid1 (Three-Phase VI Measurement) 位于 Wind Turbine 子系统，可观测电网侧的三相电压和电流。当前设置为仅测量电压（CurrentMeasurement=no）。 [E009, E010]
- Scope (4输入) 位于 PMSG-side converter Control system 子系统，用于观测控制信号如 Iq_ref、Id_ref、Vdc 等。 [E116, E117]

## 8. 不确定边界

- 模型中存在工作区变量引用（如 Ts, Nb_wt, ModulatorType, Fc 等），这些变量未在模型内部定义，实际值需要从 MATLAB 工作空间获取。此外，有10个块为库链接块，其内部可能包含未解析的细节，静态分析无法完全确定其行为。 (推断) [E196, E197, E202, E203, E204]

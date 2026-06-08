# 04_ee_d: 基于VSC的电网连接Simulink模型

本讲解只基于静态解析到的工程结构、参数和连接关系,没有运行仿真。
带有 `(推断)` 或 `(推断,无直接证据)` 的内容需要你运行仿真或查工程文档确认。

Validator 守门提示:
- 已降级 claim 数: 3
- 已拒绝 claim 数: 0

## 1. 工程在做什么

- 该模型是一个基于VSC的电网连接仿真系统，包含220kV电源、变压器、VSC桥及控制系统。 [E001, E003, E066, E097, E100, E127, E130]

## 2. 建议阅读顺序

- 建议从根层开始，查看电源、变压器、VSC及测量模块的连接。 [E002, E004]
- 然后进入Data acquisition子系统，了解电压电流经PLL和坐标变换的过程。 [E006, E069, E130]
- 最后查看VSC1 Controller内部的电流调节和PWM生成部分。 [E021, E127, E128, E129]

## 3. 关键子系统和模块

- Data acquisition子系统包含31个块，内含Transformation abc → dq和Line to phase。 [E130, E131, E134]
- VSC1 Controller子系统包含68个块，内含Current regulator（60个块）。 [E127, E128]
- Current regulator包含Current Controlller（39个块）和Subsystem4（15个块）。 [E129, E132]
- Current Controlller内含Discrete PI Controller1（9个块）。 [E133]
- 根层关键模块包括220kV电源、变压器、VSC1、choke1、B1/B2测量等。 [E066, E097, E100, E103, E106, E110]
- PLL和PWM Generator是控制回路的关键库链接块。 [E006, E021]

## 4. 信号连接逻辑

- 220kV电源经互感器1226连接到B1，再经变压器220kV/35kV 10%连接到B2。 [E148, E149, E150, E151, E152, E153, E154, E155, E156]
- B2后接choke1，choke1三相分别连接VSC1的三个交流端子。 [E136, E137, E138, E139, E140, E141]
- VSC1直流侧连接直流电压源和电容C1。 [E142, E147]
- Vabc和Iabc从根层进入Data acquisition，Vabc经Line to phase后同时送入PLL和Transformation abc → dq。 [E158, E159, E160, E165, E167, E168, E169]
- Transformation abc → dq内部：Iabc经abc to dq0变换输出Idq，Vabc经abc to dq1变换输出Udq，两者再经Power (dq0, Instantaneous)计算P&Q。 [E175, E176, E177, E181, E182, E183, E186, E187]
- Transformation abc → dq的输出U、I、P&Q经由Bus Creator打包后从Feedback端口送出。 [E172, E173, E174, E178, E179, E180, E186, E187, E188]
- VSC1 Controller内部：Feedback解包后，Udq和Idq送入Current Controlller，经PI调节输出Udq_ref，再经Subsystem4反变换和乘法后送至PWM Generator。 [E143, E189, E190, E191, E192, E193, E194]
- PWM Generator输出脉冲从Pulse_RSC端口送出到VSC1门极。 [E143, E189, E190]

## 5. 关键参数怎么看

- PLL (3ph)的AGC为'on'，FilterCutOffFreq为25，这些是直接设定值。 [E006, E007, E008]
- PWM Generator (2-Level)的Fc为变量'PWM_freq'，Freq为60，ModulatorMode默认为'Natural'。 [E021, E022, E023]
- Discrete PI Controller1的增益Kp4='Kp'，Kp5='Ki'，均为工作区变量。 [E063, E064, E065, E080, E081, E082, E114, E115, E116]
- Second-Order Filter的FilterType='Lowpass'，Fo='PWM_freq/2'，也是变量表达式。 [E077, E078, E079]
- Universal Bridge VSC1的Arms=3，Device='IGBT / Diodes'，Snubber参数默认。 [E066, E067, E068]
- 变压器220kV/35kV 10%使用数据文件'basic_model'，CoreType为'Three single-phase transformers'。 [E100, E101, E102]
- choke1的BranchType='RL'，电感表达式涉及工作区变量L_RL、Vnom、Pnom、Fnom。 [E103, E104, E105]

## 6. 如果要修改先动哪里

- 修改前应先确认工作区变量Ts、Kp、Ki、PWM_freq、L_RL等的定义。 (推断,已降级为不确定边界) [E195, E196, E197, E198, E199, E200, E201, E202]
- 调整电流环动态可修改Kp和Ki，调整PWM频率可修改PWM_freq。 (推断,已降级为不确定边界) [E022, E081, E115]
- 修改PLL滤波器截止频率FilterCutOffFreq影响同步速度。 (推断,已降级为不确定边界) [E008]
- 可利用Discrete PI Controller1内部的Scope2观察比例、积分、饱和等信号辅助调参。 [E123, E124, E125]

## 7. 应该观察哪些位置

- B1 (Three-Phase VI Measurement)位于变压器原边，可观察220kV侧电压电流，已启用电流测量和pu显示。 [E106, E107, E108, E109]
- B2位于变压器副边与choke之间，可观察35kV侧电压电流。 [E110, E111, E112, E113]
- U_AB (Multimeter)测量线电压U_AB，连接到Waveforms1 Scope的第3端口。 [E117, E118, E119, E157]
- Scope2位于Discrete PI Controller1内部，有4个输入端口，可观察PI调节器内部信号。 [E123, E124, E125]

## 8. 不确定边界

- 模型参数多为工作区变量（如Ts, Kp, Ki, PWM_freq, L_RL等），实际值未知，无法判断仿真结果。 [E195, E196, E197, E198, E199, E200, E201, E202]
- 模型中有14个库链接或掩码块（如PLL、PWM Generator、变压器等），内部实现不可见。 [E203]
- 部分块命名依赖电气工程缩写，可能造成误解；子系统嵌套可能隐藏真实信号路径。 [E005]
- 本解释基于静态结构，未执行仿真，不能保证模型运行正确性或稳定性。 (推断) [E001, E002]

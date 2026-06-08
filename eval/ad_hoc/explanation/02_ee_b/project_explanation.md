# 02_ee_b.zip

本讲解只基于静态解析到的工程结构、参数和连接关系,没有运行仿真。
带有 `(推断)` 或 `(推断,无直接证据)` 的内容需要你运行仿真或查工程文档确认。

Validator 守门提示:
- 已降级 claim 数: 7
- 已拒绝 claim 数: 1

## 1. 工程在做什么

- 模型是02_ee_b，一个Simulink-only电气工程模型，包含391个模块和384条静态连接线，用于MMC仿真。 [E001]

## 2. 建议阅读顺序

- 打开`02_ee_b.slx`并检查根层信号路径。 [E002]
- 按顺序：识别源、测量、控制、功率级块；打开子系统；检查求解器设置和关键参数。 [E004]

## 3. 关键子系统和模块

- 控制子系统Control包含287个模块，包括Nearest Level Pulse Generator（73块）。 (推断,已降级为不确定边界) [E137, E138]
- 功率级有5个Half-Bridge MMC模块，参数如电容C由工作区变量C_PM定义。 (推断,已降级为不确定边界) [E048, E049]
- 均压算法子系统包含MATLAB Function模块，内部有S-Function。 (推断,已降级为不确定边界) [E024, E030]

## 4. 信号连接逻辑

- Iap和Ian的输出分别连接到Add1的输入端口1和2。 [E148, E151]
- Half-Bridge MMC的输出连接到Half-Bridge MMC2和MMC3。 [E146, E147]
- Mux和Mux1多路复用信号后连接到Scope模块Uref_Cr和Uref_n。 [E194, E197]

## 5. 关键参数怎么看

- PWM Generator (P)的BridgeType参数设置为Half-bridge，Fc参数引用变量Fc。 (推断,已降级为不确定边界) [E007, E008]
- Half-Bridge MMC的电容C参数设置为工作区变量C_PM，Cs参数设置为Cs。 (推断,已降级为不确定边界) [E049, E050]
- 其他Half-Bridge MMC模块（如MMC2-5）的电容均使用相同变量C_PM和Cs。 (推断,已降级为不确定边界) [E052, E055, E058, E061, E064]

## 6. 如果要修改先动哪里

- 修改子模块电容时，先在工作区调整变量C_PM，再观察Voltage Measurement1的输出以评估效果。 (推断) [E049, E100]
- 修改PWM载波频率时，可调整工作区变量Fc，并观察PWM Generator输出或Scope的变化。 (推断,已降级为不确定边界) [E008, E194]

## 7. 应该观察哪些位置

- 电压测量块Voltage Measurement1-6提供各观测点电压信号，输出类型为Complex。 [E066, E079, E083, E099, E103, E107]
- 电流测量块Ian和Iap提供相电流信号，通过Gain=1输出。 [E087, E090]

## 8. 不确定边界

- 存在未定义的工作区变量引用Ts_Power和Nb_PM，实际值需在运行前设置。 [E205, E209]
- 模型包含24个库链接块，其内部参数和逻辑无法静态解析。 [E213]
- 均压算法子系统的MATLAB Function包含S-Function，其具体算法未详细解析。 [E024, E030]

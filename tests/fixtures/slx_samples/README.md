# tests/fixtures/slx_samples/

本目录存放真实的 MATLAB / Simulink 工程压缩包,用作 .slx 解析器(TASK-102)和工程压缩包安全解压(TASK-104)的测试集。

## 来源

全部 4 个工程来自 **MathWorks 官方示例库(R2026a)**,通过 MATLAB Simulink Start Page → 示例 → "打开示例" 导出后打包。

- **License**:MathWorks 示例属公开发布的教学资源(BSD-like,可自由用于测试)
- **打开方式**:学校 license,合规边界详见 `docs/01_PROJECT_CONSTITUTION.md` 第 10 节

## 工程清单

| 文件名 | 主题 | 来源路径 | 文件特征 |
|---|---|---|---|
| `01_pmsm_foc_c2000.zip` | PMSM 矢量控制(电机控制 + TI C2000 嵌入式硬件目标) | `c2b/FieldOrientedControlOfPMSMWithQEPUsingC2000ProcessorsExample` | 11 个 `.slx`(3 种芯片版本 F28035/F280049C/F28335 + host 模型 + 多个子系统)、5 个 `.m`(参数初始化)、8 个 `.png` 文档图 |
| `02_buck_voltage_control.zip` | Buck 变换器电压控制(电力电子) | `simscapeelectrical/BuckVoltageControlExample` | 1 个 `.slx` 主模型、4 个 `.m`(参数/绘图/工具脚本)、1 个 `.ssc`(Simscape 自定义元件,非白名单扩展)、1 个 `.svg` |
| `03_pid_antiwindup.zip` | PID 抗积分饱和控制(经典控制系统) | `simulink_industrial/AntiWindupControlUsingAPIDControllerExample` | 3 个 `.slx` 变体(基础/执行器饱和/前馈)、1 个 `.m`、1 个 `.png` |
| `04_lms_noise_cancel.zip` | LMS 自适应噪声消除(信号处理) | `dsp/AcousticNoiseCancellationLMSExample` | 2 个 `.slx`(浮点版 + 定点版)、1 个 `.m` |

## 测试覆盖意图

4 个工程刻意挑选**互补的复杂度模式**,覆盖 TASK-102 的 P0/P1/P2 解析分级:

- **多 `.slx` + 多子系统**(工程 1):覆盖 subsystem 层级、跨模型引用、library link 解析
- **单 `.slx` + 重 `.m` 脚本**(工程 2):覆盖参数依赖分析、`.ssc` 等非白名单扩展处理
- **同主题多 `.slx` 变体**(工程 3):覆盖批量解析、相似模型对比
- **浮点/定点变体**(工程 4):覆盖 `.slx` 配置差异、数据类型相关 block 解析

## TASK-104 沙箱测试场景

工程 1 含 8 个 `.png` + 工程 2 含 `.ssc` / `.svg`,这些都**不在** `docs/04_ENGINEERING_STANDARDS.md` 第 8.2 节定义的扩展名白名单内。

TASK-104 的解压逻辑应该:
- **拒绝整个工程**:如果将 `FileTypeNotAllowedError` 作为致命错误
- **或失败隔离**:跳过非白名单文件,继续处理其他

具体策略由 TASK-104 文档定义,本目录的测试集**正好覆盖这两种实现路径的验收**。

## 不在本目录的内容

以下场景由独立子目录承载,与本目录测试集互补:

- 恶意压缩包测试(zip bomb / zip slip / 路径穿越等)→ `tests/fixtures/malicious_zips/`(TASK-104 时构造)
- `.m` 文件解析专项测试 → `tests/fixtures/m_samples/`(TASK-103 时补充)

## 维护说明

- 本目录是**只读测试集**,不要在此目录中编辑工程
- 如需新增工程,follow 决策 04 / 01 第 10 节的合规边界,优先使用 MathWorks 公开示例

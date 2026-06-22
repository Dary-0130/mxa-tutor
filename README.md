# mxa-tutor

不是从零学 MATLAB,而是把你手上的工程讲明白。拖一个工程进来,带你看懂、问答到底。

## 产品口径

mxa-tutor 是二合一工科仿真助教:工程入口继续提供工程导览与问答;资料入口面向论文 / 报告复现,
提供**复现路线图**、**模型搭建副驾**和**参数对应说明**。

paper-to-model v0.1 的三层承诺:

- **稳交付**:论文摘要、公式 / 参数抽取、物理含义讲解、模型搭建路线图。
- **尽力交付**:`.m` 脚本骨架。
- **不承诺**:打开即跑的完整 `.slx` 成品、运行结果正确、最优调参。

资料入口只接受具体领域:`control_system` / `signal_processing` / `power_electronics` /
`communication` / `motor_control` / `new_energy`。`general` 不作为资料入口选项;无法判断领域时,
提示用户选择具体类型。图片中的关键参数若无法从文本抽取,走 MissingParameterPrompt,由用户补充后
以 `source: user_supplied` 标注。

## 开发环境对齐

本项目 Python 环境必须用 conda 的 **mxa** env(Python 3.11),其他 Python 版本(3.13)numpy 1.26 wheel 缺失会导致 install fail。

```powershell
# 新机器首次设置(若 mxa env 不存在)
conda create -n mxa python=3.11
conda activate mxa
pip install -r requirements.txt -r requirements-dev.txt

# 日常激活(已有 mxa env)
conda activate mxa
pytest                          # 或 python -m pytest
```

**关键依赖锁定真值**(2026-06-14 TASK-310 Stage 0 实测):

- Python 3.11.15
- numpy 1.26.4
- sentence_transformers 3.3.0
- pytest 8.3.3

**注**:本机 Anaconda base / app / py13 env 均 Python 3.13,sentence_transformers 装得上但 numpy 1.26.x 在 3.13 无 wheel,会触发源码 build → 缺 C 编译器 → fail。**必须用 mxa env**。

未来归档计划(X10 候选):新增 `environment.yml`(conda 一键复刻)+ `Makefile` pytest 路径统一 + `.python-version`(pyenv 标准)。

### MATLAB Engine 本地装配

MATLAB Engine 只用于 MATLAB / Simulink 在场机器的 substrate 验收,不进入默认
`requirements.txt` 或 `requirements-dev.txt`。在服务实际使用的同一个 `.venv` 里安装:

```powershell
.venv\Scripts\python -m pip install -r requirements-matlab-r2026a.txt
```

安装后用 `importlib.metadata.version("matlabengine")` 和 distribution location 取证,
不要用临时 `sys.path` / `PYTHONPATH` 注入 `F:\Matlab\extern\engines\python`。
真实 Engine 集成门用:

```bash
make test-engine
```

## 快速启动

1. 克隆仓库:
   ```bash
   git clone git@github.com:Dary-0130/mxa-tutor.git
   cd mxa-tutor
   ```
2. 创建虚拟环境:
   ```bash
   python -m venv .venv
   ```
3. 激活虚拟环境:
   ```bash
   source .venv/bin/activate
   ```
   Windows:
   ```powershell
   .venv\Scripts\activate
   ```
4. 安装开发依赖:
   ```bash
   pip install -r requirements-dev.txt
   ```
5. 运行本地检查:
   ```bash
   make test
   make hygiene
   make check
   ```

Windows 用户请在 Git Bash 或 WSL 内执行 `make` 命令。

本仓库使用 GitHub Actions 在每个 PR 上运行 lint、format check、type-check、
test 和仓库卫生检查。所有 PR 必须 CI 全绿后才能合并。

## Chat RAG

问答链路默认走 `HybridRetriever`:优先用本地 embedding + SQLite chunks 做向量召回,
当 chunks 未就绪或向量链路失败时自动降级到关键词检索。阈值可通过
`RAG_MIN_CHUNK_COUNT` 配置,默认 `1`。

## 文档导航

- [项目宪法](docs/01_PROJECT_CONSTITUTION.md)
- [架构总览](docs/02_ARCHITECTURE_OVERVIEW.md)
- [Task 总览](docs/03_TASK_INDEX.md)
- [工程规范](docs/04_ENGINEERING_STANDARDS.md)
- [教学输出风格规范](docs/05_EXPLANATION_STYLE_GUIDE.md)

# app

应用装配层,负责把项目运行时基础设施接入上层模块。

## 配置

`app/config.py` 定义 `AppSettings`,通过 pydantic-settings 从环境变量或 `.env` 加载配置。

```python
from app.config import AppSettings

cfg = AppSettings()
```

本模块只提供配置类,不创建全局 `settings` 单例。

# adapters/parser

静态解析 MATLAB / Simulink 工程文件,不执行用户上传代码。

## .slx XML 解析

- `slx_parser.py`:对外入口,提供 `SlxParserImpl.parse()`。
- `_slx_zip.py`:读取 `.slx` ZIP 容器和内部 XML part。
- `_slx_xml.py`:解析 block、line、参数、位置和 subsystem 引用。
- `_slx_subsystem.py`:从 `system_root.xml` 递归遍历 subsystem 层级。
- `_slx_config.py`:提取 solver 配置,识别 mask / library link / model reference。

用法示例:

```python
from adapters.parser import SlxParserImpl

model = SlxParserImpl().parse("model.slx")
```

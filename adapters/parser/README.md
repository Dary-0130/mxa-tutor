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

## .m 静态解析

- `m_parser.py`:对外入口,提供 `MParserImpl.parse()`。
- `_m_lex.py`:剥离注释、占位字符串并折叠续行,同时维护原始行号映射。
- `_m_structure.py`:分类 script / function / class,提取 top-level function。
- `_m_dependencies.py`:提取 `import` 语句,按白名单启发式识别 toolbox。

用法示例:

```python
from adapters.parser import MParserImpl

m_file = MParserImpl().parse("init_params.m")
```

## .zip 安全解压与粗分类

- `zip_extractor.py`:对外入口,提供 `safe_extract()` 七道闸安全解压。
- `file_classifier.py`:对外入口,提供 `classify_files()` 按扩展名粗分类。
- `_zip_paths.py`:规范化 zip 路径并识别跨平台不安全路径名。
- `_zip_policy.py`:维护 allow / deny / other 三档扩展名策略。

用法示例:

```python
from adapters.parser import classify_files, safe_extract

root = safe_extract(zip_bytes, dest_dir, settings)
files = classify_files(root, root)
```

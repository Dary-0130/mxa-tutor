# adapters/llm

DeepSeek TextProvider adapter for OpenAI-compatible chat completions.

`DeepSeekTextProvider` implements `core.interfaces.llm_provider.TextProvider` and translates
SDK errors into project-level `LLMError` subclasses. It logs only call metadata such as model,
token counts, and latency.

```python
from adapters.llm import DeepSeekTextProvider
from core.interfaces.llm_provider import LLMMessage

provider = DeepSeekTextProvider(api_key="sk-xxx")
response = provider.chat([LLMMessage(role="user", content="hello")])
print(response.text)
```

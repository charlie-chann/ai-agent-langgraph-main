# Tools Guide — project_02_tool_agent

## 如何添加自定义工具

### 1. 创建工具文件

在 `tools/` 目录新建 `my_tool.py`：

```python
from langchain_core.tools import tool

@tool
def my_tool(input_param: str) -> str:
    """工具描述（LLM 会读这段，描述清楚输入/输出/用途）.
    Input: 参数说明.
    Returns: 返回值说明.
    """
    # 实现逻辑
    return f"Result: {input_param}"
```

### 2. 注册到 agent.py

```python
from tools.my_tool import my_tool

ALL_TOOLS = [..., my_tool]
```

### 3. 安全检查清单
- [ ] 输入做长度/格式校验
- [ ] 文件操作限制在沙盒目录
- [ ] 外部 API 调用捕获异常
- [ ] 不执行用户提供的代码字符串

---

## 内置工具安全说明

### calculator
- 使用 `ast.parse` + 白名单操作符，**不调用 `eval()`**
- 禁止 `import`、函数调用、属性访问

### file_read / file_write
- 所有路径通过 `Path.resolve()` 解析
- 验证解析后路径必须在 `SANDBOX` 目录下
- 防止 `../../../etc/passwd` 类路径穿越攻击

### web_search  
- 输入长度限制 500 字符
- 通过 DuckDuckGo（无 API key，无用户追踪）

# 🧠 Self-Evolving RAG System

> 基于 Ollama qwen3.5 + LangChain 构建的**自进化**RAG系统。
> 核心理念：**越用越聪明** —— 通过收集用户反馈，自动优化检索权重。

---

## ✨ 核心特性

- 🔄 **自进化引擎**：根据用户反馈自动调整文档块权重，检索越来越准
- 🤖 **本地LLM**：完全基于 Ollama qwen3.5，数据不外泄
- 📚 **多格式支持**：PDF、Word、Markdown、TXT、HTML、JSON、CSV
- 🧬 **加权检索**：融合 boost_score 与语义相似度，智能排序结果
- 🎨 **专业UI**：深色主题，流畅交互，实时状态可视化

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd self_evolving_rag
pip install -r requirements.txt
```

### 2. 确保 Ollama 运行

```bash
# 启动 Ollama
ollama serve

# 下载模型（如果还没下载）
ollama pull qwen3.5:latest
ollama pull nomic-embed-text:latest
```

### 3. 启动界面

```bash
streamlit run app.py
```

访问 `http://localhost:8501`

---

## 📁 项目结构

```
self_evolving_rag/
├── config.py              # 配置文件
├── rag_engine.py          # RAG 主引擎
├── vector_store.py        # ChromaDB 向量库
├── llm.py                 # Ollama LLM 封装
├── document_processor.py  # 文档加载与分块
├── feedback.py            # 反馈收集（SQLite）
├── evolution.py           # 自进化核心算法
├── app.py                 # Streamlit 界面
├── requirements.txt
└── README.md
```

---

## 🧬 自进化原理

```
用户提问 → 检索文档 → 生成回答 → 用户评价(👍/👎)
                                         ↓
                               实时更新chunk权重
                                         ↓
                          积累N条反馈后触发"完整进化"
                                         ↓
                        批量分析boost/penalty模式
                                         ↓
                              检索质量持续提升 🔄
```

### 进化策略

| 用户行为 | 系统反应 |
|---------|---------|
| 点赞回答 👍 | 相关chunk boost_score +0.1 |
| 差评回答 👎 | 相关chunk boost_score -0.1 |
| 提供修正文本 | 记录到进化日志，下次检索优先 |
| 多次差评同一话题 | 标记为知识盲点，提示补充 |

---

## 📊 使用流程

### 1. 导入知识库
- 上传单个文件
- 批量导入文件夹
- 直接输入文本片段

### 2. 开始问答
- 在主界面输入问题
- 系统检索相关文档
- 生成带来源标注的回答

### 3. 评价反馈
- 👍 / 👎 快速评价
- 可选：提供你认为正确的答案

### 4. 观察进化
- 在「进化引擎」页面查看进化统计
- 手动触发完整进化
- 查看知识盲点分析

---

## ⚙️ 配置说明

关键参数在 `config.py` 中：

```python
OLLAMA_LLM_MODEL = "qwen3.5:latest"     # 主模型
OLLAMA_EMBED_MODEL = "nomic-embed-text:latest"  # 嵌入模型
CHUNK_SIZE = 500                          # 文档块大小
EVOLUTION_TRIGGER_THRESHOLD = 5          # 进化触发阈值
BOOST_WEIGHT = 0.1                        # 每次权重调整幅度
```

---

## 🎨 界面预览

- **深色主题**：护眼专业
- **左侧状态栏**：实时显示向量库大小、模型状态、进化健康度
- **问答区**：对话历史、来源标注、一键反馈
- **知识库管理**：上传、浏览、分析文档
- **进化引擎**：手动触发、事件时间线、统计面板

---

## 🛠️ 故障排除

**Ollama 连接失败**
```bash
ollama serve
ollama list  # 确认模型存在
```

**向量库为空**
```bash
# 检查chromadb目录权限
ls -la data/vector_store/
```

**模型下载慢**
```bash
# 使用镜像（如果可用）
OLLAMA_BASE_URL=http://localhost:11434 ollama pull qwen3.5:latest
```

---

_Built with ❤️ by 私人助手 🖤_

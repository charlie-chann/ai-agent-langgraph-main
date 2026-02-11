"""
LLM 模块
封装 Ollama qwen3.5:latest 模型调用
支持 RAG 问答、摘要、翻译等多种任务
"""
import time
from typing import Optional, List, Dict, Any

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate

from config import OLLAMA_BASE_URL, OLLAMA_LLM_MODEL, OLLAMA_TIMEOUT


class LLManager:
    """Ollama LLM 管理器"""

    def __init__(self, model: str = OLLAMA_LLM_MODEL, temperature: float = 0.3):
        self.model = model
        self.temperature = temperature
        self._llm = ChatOllama(
            model=model,
            base_url=OLLAMA_BASE_URL,
            temperature=temperature,
            timeout=OLLAMA_TIMEOUT,
            options={"num_ctx": 8192},  # 上下文窗口
        )
        self._setup_prompts()

    def _setup_prompts(self):
        """配置各类任务的Prompt模板"""
        self.rag_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""你是一个专业、友好的AI助手，基于给定的参考资料回答用户问题。

参考材料来自用户的知识库。请遵循以下规则：
1. 优先使用参考资料中的信息
2. 如果参考资料中没有相关信息，诚实地说明"根据当前知识库无法回答这个问题"
3. 回答要清晰、有条理，适当使用列表和格式
4. 标明你回答的信息来源（参考材料的标题）
5. 保持友好、专业的语气
6. 参考资料可能包含多个片段，请综合它们来回答"""),
            HumanMessage(content="""参考材料：
{context}

---
用户问题：{question}

请基于以上参考材料回答。"""),
        ])

        self.summarize_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="你是一个专业的摘要助手。请用简洁、有条理的方式总结以下内容。"),
            HumanMessage(content="""请总结以下内容，保留核心信息，控制在200字以内：

{content}

摘要："""),
        ])

        self.analyze_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="你是一个专业分析师，擅长深度分析文本内容。"),
            HumanMessage(content="""请对以下内容进行深度分析，包括：核心观点、关键数据、潜在问题、相关背景。

{content}

分析："""),
        ])

    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        """
        通用生成接口
        """
        try:
            messages = []
            if system:
                messages.append(SystemMessage(content=system))
            messages.append(HumanMessage(content=prompt))

            response = self._llm.invoke(messages)
            return response.content
        except Exception as e:
            return f"[LLM Error] {str(e)}"

    def rag_answer(
        self,
        question: str,
        context_docs: List[Any],
        use_weighted: bool = True
    ) -> Dict[str, Any]:
        """
        RAG 问答
        context_docs: [(Document, score), ...] 检索结果
        """
        if not context_docs:
            return {
                "answer": "当前知识库为空，请先上传文档。",
                "sources": [],
                "model": self.model
            }

        # 构建上下文
        context_parts = []
        sources = []
        for i, (doc, score) in enumerate(context_docs):
            source_name = doc.metadata.get("source", "未知来源")
            chunk_text = doc.page_content[:500]  # 限制单个chunk长度
            context_parts.append(f"[文档{i+1}] {source_name}：\n{chunk_text}")
            sources.append({
                "content": doc.page_content[:200],
                "source": source_name,
                "score": round(score, 4)
            })

        context_str = "\n\n".join(context_parts)

        try:
            chain = self.rag_prompt | self._llm
            response = chain.invoke({
                "question": question,
                "context": context_str
            })

            return {
                "answer": response.content,
                "sources": sources,
                "model": self.model,
                "num_sources": len(sources)
            }
        except Exception as e:
            return {
                "answer": f"[RAG Error] {str(e)}",
                "sources": sources,
                "model": self.model,
                "error": str(e)
            }

    def summarize(self, content: str, max_chars: int = 500) -> str:
        """文本摘要"""
        try:
            chain = self.summarize_prompt | self._llm
            response = chain.invoke({"content": content[:3000]})
            return response.content[:max_chars]
        except Exception as e:
            return f"[摘要失败] {str(e)}"

    def analyze(self, content: str) -> str:
        """深度分析"""
        try:
            chain = self.analyze_prompt | self._llm
            response = chain.invoke({"content": content[:3000]})
            return response.content
        except Exception as e:
            return f"[分析失败] {str(e)}"

    def is_available(self) -> bool:
        """检查Ollama服务是否可用"""
        try:
            self._llm.invoke([HumanMessage(content="hello")], timeout=10)
            return True
        except Exception:
            return False

    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "model": self.model,
            "temperature": self.temperature,
            "base_url": OLLAMA_BASE_URL,
            "available": self.is_available()
        }

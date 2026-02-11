"""Pickle 兼容：旧路径 app.retrieval.* 映射到 app.knowledge.*。"""
from __future__ import annotations

import sys
import types


def install_pickle_compat() -> None:
    """在 unpickle 前注册旧模块别名，避免重命名后无法加载 graph.pkl。"""
    import app.knowledge.conflict as conflict
    import app.knowledge.ingest as ingest
    import app.knowledge.kg_extractor as kg_extractor
    import app.knowledge.knowledge_graph as knowledge_graph
    import app.knowledge.retriever as retriever

    if "app.retrieval" not in sys.modules:
        pkg = types.ModuleType("app.retrieval")
        pkg.__path__ = []
        sys.modules["app.retrieval"] = pkg

    mapping = {
        "app.retrieval.conflict": conflict,
        "app.retrieval.ingest": ingest,
        "app.retrieval.kg_extractor": kg_extractor,
        "app.retrieval.knowledge_graph": knowledge_graph,
        "app.retrieval.retriever": retriever,
    }
    for name, module in mapping.items():
        sys.modules.setdefault(name, module)

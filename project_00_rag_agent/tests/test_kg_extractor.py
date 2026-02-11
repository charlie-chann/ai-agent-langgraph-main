"""KG extractor unit tests."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_core.documents import Document


def test_hybrid_dedupes():
    from tools.kg_extractor import extract_triples_hybrid
    from tools.knowledge_graph import extract_triples_from_chunk, Triple

    chunk = Document(page_content="《年假管理办法》规定 15天", metadata={"source": "p.txt"})

    with patch("tools.kg_extractor.extract_triples_llm") as mock_llm:
        mock_llm.return_value = [Triple("年假管理办法", "defines", "15天", "p.txt")]
        triples = extract_triples_hybrid(chunk, extract_triples_from_chunk)
        assert len(triples) >= 1

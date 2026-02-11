# test_project.py - Quick test for multi-agent
import sys
sys.path.insert(0, '.')

from agent import run, get_graph
from config import DEFAULT_MODEL, OLLAMA_BASE_URL

print("=" * 50)
print("Testing Multi-Agent System")
print("=" * 50)

# Test 1: Config
print("\n[1] Agent Config...")
print(f"    Model: {DEFAULT_MODEL}")
print(f"    Ollama: {OLLAMA_BASE_URL}")

# Test 2: Simple task
print("\n[2] Running simple social media task...")
print("    Task: 'Write a post about AI automation'")
result = run(
    task="Write a short social media post about AI automation",
    scenario="social_media"
)

print(f"\n    Total time: {result['total_latency_ms']/1000:.1f}s")
print(f"    Revision loops: {result['revision_count']}")
print(f"    Agent log: {[a['agent'] for a in result['agent_log']]}")

critique = result.get('critique', {})
if critique:
    print(f"    Critique score: {critique.get('overall_score', 'N/A')}/10")
    print(f"    Critique verdict: {critique.get('verdict', 'N/A')}")

print("\n    Final content preview:")
print("    " + result['content'][:300].replace('\n', '\n    ') + "...")

print("\n" + "=" * 50)
print("Test Complete!")
print("=" * 50)

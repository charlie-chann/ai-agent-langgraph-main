"""
评估 Agent 响应质量（延迟、首 token 时间、吞吐量）
Usage: python scripts/benchmark.py --project project_01_rag_agent --rounds 5
"""
import argparse
import time
import statistics
import httpx
from loguru import logger


def benchmark_api(url: str, payload: dict, rounds: int) -> dict:
    latencies = []
    first_token_times = []

    for i in range(rounds):
        logger.info(f"Round {i + 1}/{rounds}")
        start = time.perf_counter()
        first_token = None
        try:
            with httpx.stream("POST", url, json=payload, timeout=120) as r:
                for chunk in r.iter_text():
                    if chunk and first_token is None:
                        first_token = time.perf_counter() - start
            total = time.perf_counter() - start
            latencies.append(total)
            if first_token:
                first_token_times.append(first_token)
        except Exception as e:
            logger.error(f"Request failed: {e}")

    if not latencies:
        return {"error": "All requests failed"}

    return {
        "rounds": rounds,
        "avg_latency_s": round(statistics.mean(latencies), 3),
        "p50_latency_s": round(statistics.median(latencies), 3),
        "p95_latency_s": round(sorted(latencies)[int(len(latencies) * 0.95)], 3),
        "avg_first_token_s": round(statistics.mean(first_token_times), 3) if first_token_times else None,
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark Agent API")
    parser.add_argument("--url", default="http://localhost:8000/chat", help="SSE or REST endpoint")
    parser.add_argument("--message", default="What is LangChain?", help="Test message")
    parser.add_argument("--rounds", type=int, default=3, help="Number of benchmark rounds")
    args = parser.parse_args()

    logger.info(f"Benchmarking {args.url} for {args.rounds} rounds...")
    result = benchmark_api(args.url, {"message": args.message}, args.rounds)

    print("\n=== Benchmark Results ===")
    for k, v in result.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()

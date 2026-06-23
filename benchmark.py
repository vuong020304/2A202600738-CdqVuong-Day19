"""Benchmark: Flat RAG vs GraphRAG - 20 câu hỏi."""
import os
import time
from dotenv import load_dotenv
from src.graph_store import Neo4jStore
from src.query_engine import QueryEngine, FlatRAGEngine
from src.extractor import DocumentExtractor

load_dotenv("config/.env")

# 20 câu hỏi benchmark
QUESTIONS = [
    "Tesla bán được bao nhiêu xe trong Q1 2024?",
    "Ford doanh số EV thế nào so với Tesla?",
    "Thị phần EV tại Mỹ 2024 của các hãng?",
    "BYD và Tesla cạnh tranh ra sao?",
    "Chính sách $7,500 tax credit ảnh hưởng thị trường?",
    "Hạ tầng sạc EV tại Mỹ thiếu hụt thế nào?",
    "Battery cost đang giảm ở tốc độ nào?",
    "Rivian và Lucid cạnh tranh với Tesla?",
    "Toyota đang tụt hậu về EV?",
    "Trung Quốc thống trị thị trường EV?",
    "Consumer sentiment về EV positive hay negative?",
    "Oil demand thay đổi thế nào với EV?",
    "Charging time là mối quan ngại lớn nhất?",
    "Leasing EV đang tăng trưởng thế nào?",
    "Solid-state battery bao giờ thương mại hóa?",
    "Grid infrastructure có đủ đáp ứng EV?",
    "BMW và Mercedes phát triển EV thế nào?",
    "Doanh số EV Q1 2024 so với Q4 2023?",
    "Pin LFP đang thay đổi ngành EV?",
    "Forecast doanh số EV 2024 và 2025?",
]

def main():
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password123")

    # Load documents for Flat RAG
    doc_extractor = DocumentExtractor("dataset")
    documents = doc_extractor.load_all_documents()

    # Connect Neo4j
    graph_store = Neo4jStore(uri, user, password)
    stats = graph_store.get_stats()
    print(f"Graph: {stats['nodes']} nodes, {stats['relationships']} relationships")

    # Create engines
    graph_rag = QueryEngine(graph_store, api_key, base_url, model)
    flat_rag = FlatRAGEngine(documents, api_key, base_url, model)

    results = []
    total_graph_time = 0
    total_flat_time = 0

    for i, q in enumerate(QUESTIONS):
        print(f"[{i+1}/20] {q[:50]}...")

        # GraphRAG
        t0 = time.time()
        g_result = graph_rag.query(q)
        g_time = time.time() - t0
        total_graph_time += g_time

        # Flat RAG
        t0 = time.time()
        f_result = flat_rag.query(q)
        f_time = time.time() - t0
        total_flat_time += f_time

        results.append({
            "q": q,
            "g_time": g_time,
            "f_time": f_time,
            "g_answer": g_result.get("answer", "")[:200],
            "f_answer": f_result.get("answer", "")[:200],
            "g_entities": len(g_result.get("entities", [])),
        })

    # Save benchmark table as markdown
    os.makedirs("output", exist_ok=True)
    with open("output/benchmark.md", "w", encoding="utf-8") as f:
        f.write("# Benchmark: Flat RAG vs GraphRAG\n\n")
        f.write(f"- Số câu hỏi: {len(QUESTIONS)}\n")
        f.write(f"- GraphRAG avg time: {total_graph_time/len(QUESTIONS):.2f}s\n")
        f.write(f"- Flat RAG avg time: {total_flat_time/len(QUESTIONS):.2f}s\n\n")
        f.write("| # | Câu hỏi | GraphRAG | Flat RAG |\n")
        f.write("|---|---------|----------|----------|\n")
        for i, r in enumerate(results):
            f.write(f"| {i+1} | {r['q'][:60]} | {r['g_time']:.1f}s | {r['f_time']:.1f}s |\n")
        f.write("\n## Chi tiết câu trả lời\n\n")
        for i, r in enumerate(results):
            f.write(f"### {i+1}. {r['q']}\n")
            f.write(f"**GraphRAG** ({r['g_time']:.1f}s):\n{r['g_answer']}\n\n")
            f.write(f"**Flat RAG** ({r['f_time']:.1f}s):\n{r['f_answer']}\n\n---\n\n")

    print(f"\nBenchmark saved to output/benchmark.md")
    graph_store.close()

if __name__ == "__main__":
    main()

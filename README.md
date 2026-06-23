# EV GraphRAG - Chatbot trả lời câu hỏi về ngành xe điện

Hệ thống **GraphRAG** sử dụng Neo4j để trích xuất và truy vấn knowledge graph từ 70 documents về ngành EV tại Mỹ.

## Cài đặt

```bash
pip install -r requirements.txt
docker run -d --name ev-graphrag-neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password123 neo4j:5.15-community
```

## Sử dụng

```bash
python extract.py      # Trích xuất entities vào Neo4j (chạy 1 lần)
python chatbot.py      # Chat với knowledge graph
python benchmark.py    # So sánh Flat RAG vs GraphRAG (20 câu hỏi)
```

## Kết quả

| Metric | Giá trị |
|--------|---------|
| Documents | 70 |
| Nodes | 731 |
| Relationships | 2,674 |
| GraphRAG avg time | 9.97s |
| Flat RAG avg time | 7.39s |

## Cấu trúc

```
├── dataset/           # 70 documents (.txt)
├── src/
│   ├── extractor.py   # LLM entity extraction
│   ├── graph_store.py # Neo4j operations
│   └── query_engine.py # GraphRAG + Flat RAG
├── config/.env        # API keys
├── extract.py         # Run extraction
├── chatbot.py         # Chat interface
└── benchmark.py       # Benchmark comparison
```

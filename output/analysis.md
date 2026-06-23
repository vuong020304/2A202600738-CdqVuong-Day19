# Phân tích chi phí xây dựng Knowledge Graph

## Thông số kỹ thuật
- **LLM Model**: gemini-3.1-flash-lite-preview
- **API**: http://127.0.0.1:20128/v1 (proxy)
- **Neo4j**: Docker (neo4j:5.15-community)
- **Số documents**: 70

## Kết quả Knowledge Graph
- **Nodes**: 731 entities
- **Relationships**: 2,674 relationships
- **Entity types**: Company, Metric, Time, Topic, Location, Vehicle, Policy

## Chi phí ước tính

| Hạng mục | Giá trị |
|----------|---------|
| Số documents | 70 |
| Thời gian extract/doc | ~8-10s |
| Tổng thời gian extract | ~12 phút |
| LLM calls cho extraction | 70 calls |
| LLM calls cho entity extraction | 70 calls |
| **Tổng LLM calls** | **~140 calls** |

## So sánh Flat RAG vs GraphRAG

| Metric | Flat RAG | GraphRAG |
|--------|----------|----------|
| avg time/query | 7.39s | 9.97s |
| Tìm được số liệu cụ thể | Không | Có (268,909 xe) |
| Context relevance | Thấp | Cao |

## Kết luận
- GraphRAG chậm hơn ~35% do query phức tạp hơn
- GraphRAG trả lời chính xác hơn với số liệu cụ thể
- Flat RAG nhanh hơn nhưng không tìm được thông tin chi tiết

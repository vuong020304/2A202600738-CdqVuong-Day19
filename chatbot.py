import os
from dotenv import load_dotenv

from src.graph_store import Neo4jStore
from src.query_engine import QueryEngine
from src.chatbot import Chatbot


def main():
    """Run the GraphRAG chatbot."""
    load_dotenv("config/.env")
    
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
    
    if not OPENAI_API_KEY:
        print("ERROR: Set OPENAI_API_KEY in config/.env")
        return
    
    if not NEO4J_PASSWORD:
        print("ERROR: Set NEO4J_PASSWORD in config/.env")
        return
    
    print("Connecting to Neo4j...")
    graph_store = Neo4jStore(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    stats = graph_store.run_cypher("MATCH (n) RETURN count(n) as nodes")
    node_count = stats[0]['nodes'] if stats else 0
    print(f"Graph loaded: {node_count} nodes")
    
    if node_count == 0:
        print("ERROR: No data in Neo4j. Run 'python extract.py' first.")
        graph_store.close()
        return
    
    print("Starting chatbot...")
    query_engine = QueryEngine(graph_store, OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL)
    chatbot = Chatbot(query_engine)
    chatbot.run()
    
    graph_store.close()


if __name__ == "__main__":
    main()

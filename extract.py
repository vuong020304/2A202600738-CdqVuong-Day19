import os
from pathlib import Path
from dotenv import load_dotenv

from src.extractor import DocumentExtractor, EntityExtractor, EntityValidator
from src.graph_store import Neo4jStore


def main():
    """Extract entities and relationships from documents to Neo4j."""
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
    
    print("=" * 60)
    print("EV GraphRAG - Extraction Pipeline")
    print("=" * 60)
    
    print("\nStep 1: Loading documents...")
    doc_extractor = DocumentExtractor("dataset")
    documents = doc_extractor.load_all_documents()
    print(f"  Loaded {len(documents)} documents")
    
    print("\nStep 2: Connecting to Neo4j...")
    graph_store = Neo4jStore(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    graph_store.clear_database()
    print("  Connected and cleared old data")
    
    print("\nStep 3: Extracting entities and relationships...")
    extractor = EntityExtractor(OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL)
    validator = EntityValidator()
    
    total_entities = 0
    total_relationships = 0
    
    for i, doc in enumerate(documents):
        doc_id = doc['id']
        print(f"  Processing {i+1}/{len(documents)}: {doc_id}")
        
        result = extractor.extract_from_document(doc)
        validated = validator.validate_entities(result)
        
        entities = validated.get('entities', [])
        rels = validated.get('relationships', [])
        
        for entity in entities:
            graph_store.add_entity(entity)
        for rel in rels:
            graph_store.add_relationship(rel)
        
        total_entities += len(entities)
        total_relationships += len(rels)
    
    # Step 4: Post-processing - link orphan nodes
    print("\nStep 4: Linking orphan nodes...")
    linked = graph_store.link_orphan_nodes()
    print(f"  Linked {linked} orphan nodes")
    
    print("\n" + "=" * 60)
    print("Extraction Complete!")
    print(f"  Documents processed: {len(documents)}")
    print(f"  Total entities: {total_entities}")
    print(f"  Total relationships: {total_relationships}")
    
    stats = graph_store.run_cypher("MATCH (n) RETURN count(n) as nodes")
    print(f"  Nodes in Neo4j: {stats[0]['nodes'] if stats else 0}")
    
    graph_store.close()
    print("=" * 60)
    print("\nNow run: python chatbot.py")


if __name__ == "__main__":
    main()

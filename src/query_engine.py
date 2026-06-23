from typing import List, Dict, Any, Optional
from openai import OpenAI
from .graph_store import GraphStore


class QueryEngine:
    """Query engine for GraphRAG chatbot."""
    
    CONTEXT_TEMPLATE = """You are an expert on the electric vehicle (EV) industry. 
Based on the following knowledge graph context, answer the user's question.

**Knowledge Graph Context:**
{context}

**User Question:** {question}

**Instructions:**
1. Use ONLY the information from the context above
2. If the context doesn't contain enough information, say so
3. Provide specific numbers, dates, and company names when available
4. Structure your answer clearly with bullet points if appropriate
5. Cite the source document IDs when possible

**Answer:**"""
    
    def __init__(self, graph_store: GraphStore, api_key: str, base_url: str, model: str):
        self.graph_store = graph_store
        self.llm_client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
    
    def extract_entities_from_query(self, query: str) -> List[str]:
        """Extract key entities from user query using LLM + keyword fallback."""
        # First try LLM extraction
        prompt = f"""Extract the main entities (company names, locations, topics, products) from this question about the EV industry.

Question: {query}

Return ONLY a comma-separated list of entity names, no explanations.
Example: Tesla, Q1 2024, EV Sales"""
        
        try:
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=200
            )
            
            entities_text = response.choices[0].message.content.strip()
            entities = [e.strip() for e in entities_text.split(',') if e.strip()]
            if entities:
                return entities
            
        except Exception as e:
            print(f"LLM entity extraction error: {e}")
        
        # Fallback: keyword-based extraction
        return self._extract_entities_keywords(query)
    
    def _extract_entities_keywords(self, query: str) -> List[str]:
        """Fallback keyword-based entity extraction."""
        import re
        entities = []
        
        # Common EV companies
        companies = ['Tesla', 'Ford', 'BMW', 'Rivian', 'BYD', 'NIO', 'XPeng', 'Li Auto',
                     'Volkswagen', 'Mercedes', 'Porsche', 'Toyota', 'Honda', 'Hyundai',
                     'Kia', 'Stellantis', 'Lucid', 'Polestar', 'VinFast', 'Xiaomi',
                     'Volvo', 'Geely', 'Changan', 'Great Wall', 'MG', 'Audi']
        
        query_upper = query.upper()
        for company in companies:
            if company.upper() in query_upper:
                entities.append(company)
        
        # Extract time periods
        time_patterns = [
            r'Q[1-4]\s*\d{4}',
            r'\d{4}',
            r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}',
            r'last quarter', r'this quarter', r'last year', r'this year',
            r'Fiscal \d{4}', r'FY\d{4}'
        ]
        for pattern in time_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            entities.extend(matches)
        
        return entities if entities else [query]
    
    def get_graph_context(self, entities: List[str], depth: int = 2) -> str:
        """Get graph context for entities using targeted queries."""
        context_parts = []
        visited = set()
        
        for entity in entities:
            if entity in visited:
                continue
            
            # Search for entity in graph
            found_entities = self.graph_store.search_entities(entity)
            
            for found in found_entities:
                entity_name = found['name']
                if entity_name in visited:
                    continue
                visited.add(entity_name)
                
                # Get entity info
                context_parts.append(f"Entity: {entity_name} (Type: {found['type']})")
                
                # Use targeted query instead of generic get_neighbors
                # This focuses on REPORTS relationships which contain metrics
                try:
                    r = self.graph_store.run_cypher(
                        "MATCH (n)-[r]->(m) "
                        "WHERE n.name = $name AND (type(r) = 'REPORTS' OR type(r) = 'PRODUCES') "
                        "RETURN type(r) as rel, labels(m)[0] as type, m.name as name "
                        "LIMIT 20",
                        {'name': entity_name}
                    )
                    for row in r:
                        context_parts.append(f"  {entity_name} --[{row['rel']}]--> {row['name']} ({row['type']})")
                    
                    # Get metrics with time periods
                    r = self.graph_store.run_cypher(
                        "MATCH (n)-[r1:REPORTS]->(m:Metric)-[r2:IN_PERIOD]->(t) "
                        "WHERE n.name = $name "
                        "RETURN m.name as metric, t.name as time "
                        "LIMIT 20",
                        {'name': entity_name}
                    )
                    if r:
                        context_parts.append(f"  Metrics with time periods:")
                        for row in r:
                            context_parts.append(f"    {row['metric']} in {row['time']}")
                    
                    # Get key relationships (COMPETES_WITH, OPERATES_IN)
                    r = self.graph_store.run_cypher(
                        "MATCH (n)-[r]->(m) "
                        "WHERE n.name = $name AND type(r) IN ['COMPETES_WITH', 'OPERATES_IN', 'IMPLEMENTS'] "
                        "RETURN type(r) as rel, m.name as target "
                        "LIMIT 15",
                        {'name': entity_name}
                    )
                    if r:
                        for row in r:
                            context_parts.append(f"  {entity_name} --[{row['rel']}]--> {row['target']}")
                
                except Exception as e:
                    # Fallback to basic neighbor query
                    neighbors = self.graph_store.get_neighbors(entity_name, depth=1)
                    for neighbor in neighbors[:20]:
                        context_parts.append(
                            f"  {neighbor['source']} --[{neighbor['relationship']}]--> {neighbor['target']}"
                        )
                
                context_parts.append("")  # Empty line separator
        
        return '\n'.join(context_parts)
    
    def generate_answer(self, question: str, context: str) -> str:
        """Generate answer using LLM with graph context."""
        prompt = self.CONTEXT_TEMPLATE.format(context=context, question=question)
        
        try:
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"Error generating answer: {e}"
    
    def query(self, question: str, depth: int = 2) -> Dict[str, Any]:
        """Main query method - full GraphRAG pipeline."""
        # Step 1: Extract entities from question
        entities = self.extract_entities_from_query(question)
        
        # Step 2: Get graph context
        context = self.get_graph_context(entities, depth=depth)
        
        # Step 3: Generate answer
        answer = self.generate_answer(question, context)
        
        return {
            'question': question,
            'entities': entities,
            'context': context,
            'answer': answer
        }


class FlatRAGEngine:
    """Flat RAG engine using vector search only (for comparison)."""
    
    def __init__(self, documents: List[Dict[str, Any]], api_key: str, base_url: str, model: str):
        self.documents = documents
        self.llm_client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.doc_texts = [f"{doc['title']}\n{doc['full_content']}" for doc in documents]
    
    def search_documents(self, query: str, top_k: int = 5) -> List[str]:
        """Simple keyword-based document search (simulating vector search)."""
        query_lower = query.lower()
        scored_docs = []
        
        for i, text in enumerate(self.doc_texts):
            text_lower = text.lower()
            # Simple scoring based on keyword presence
            score = sum(1 for word in query_lower.split() if word in text_lower)
            if score > 0:
                scored_docs.append((score, text))
        
        # Sort by score and return top_k
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        return [doc[1][:1000] for doc in scored_docs[:top_k]]
    
    def query(self, question: str) -> Dict[str, Any]:
        """Query using flat RAG."""
        # Search for relevant documents
        relevant_docs = self.search_documents(question)
        
        # Create context
        context = "\n\n---\n\n".join(relevant_docs)
        
        # Generate answer
        prompt = f"""Based on the following documents, answer the question.

**Documents:**
{context}

**Question:** {question}

**Answer:**"""
        
        try:
            response = self.llm_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000
            )
            
            answer = response.choices[0].message.content
            
        except Exception as e:
            answer = f"Error: {e}"
        
        return {
            'question': question,
            'relevant_docs': len(relevant_docs),
            'context': context[:500] + "..." if len(context) > 500 else context,
            'answer': answer
        }

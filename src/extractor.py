import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
from openai import OpenAI
from dotenv import load_dotenv


class DocumentExtractor:
    """Load and parse documents from dataset folder."""
    
    def __init__(self, dataset_path: str = "dataset"):
        self.dataset_path = Path(dataset_path)
    
    def load_all_documents(self) -> List[Dict[str, Any]]:
        """Load all .txt files from dataset folder."""
        documents = []
        for file_path in sorted(self.dataset_path.glob("*.txt")):
            doc = self.parse_document(file_path)
            if doc:
                documents.append(doc)
        return documents
    
    def parse_document(self, file_path: Path) -> Dict[str, Any]:
        """Parse a single document file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            doc = {
                'id': file_path.stem,
                'query': '',
                'title': '',
                'link': '',
                'snippet': '',
                'full_content': ''
            }
            
            in_content = False
            content_lines = []
            
            for line in lines:
                if line.startswith('Query:'):
                    doc['query'] = line.replace('Query:', '').strip()
                elif line.startswith('Title:'):
                    doc['title'] = line.replace('Title:', '').strip()
                elif line.startswith('Link:'):
                    doc['link'] = line.replace('Link:', '').strip()
                elif line.startswith('Snippet:'):
                    doc['snippet'] = line.replace('Snippet:', '').strip()
                elif line.startswith('Full Content:'):
                    in_content = True
                elif in_content:
                    content_lines.append(line)
            
            doc['full_content'] = '\n'.join(content_lines).strip()
            return doc
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            return None


class EntityExtractor:
    """Extract entities and relationships using LLM."""
    
    EXTRACTION_PROMPT = """You are an expert at extracting entities and relationships from text about the electric vehicle (EV) industry.

Extract ALL entities AND their relationships from the following text.

**Entity Types:**
- Company: Car manufacturers (e.g., Tesla, Ford, BMW, Rivian)
- Location: Countries, states (e.g., US, California, China)
- Topic: Market concepts (e.g., EV sales, battery, charging)
- Vehicle: Car models (e.g., Model Y, F-150 Lightning)
- Metric: Numbers with context (e.g., "268,909 vehicles", "51.3% market share", "$55,167")
- Policy: Regulations (e.g., ZEV mandate, $7,500 tax credit)
- Time: Periods (e.g., Q1 2024, 2023)

**Relationship Types:**
- REPORTS: Company REPORTS Metric (e.g., Tesla REPORTS "268,909 vehicles")
- IN_PERIOD: Metric IN_PERIOD Time (e.g., "268,909 vehicles" IN_PERIOD Q1 2024)
- OPERATES_IN: Company OPERATES_IN Location
- COMPETES_WITH: Company COMPETES_WITH Company
- PRODUCES: Company PRODUCES Vehicle
- IMPLEMENTS: Location IMPLEMENTS Policy
- AFFECTS: Policy AFFECTS Topic
- IMPACTS: Topic IMPACTS Topic

**CRITICAL RULES:**
1. When text says "Tesla sold 268,909 vehicles in Q1 2024", you MUST create:
   - Entity: Tesla (Company)
   - Entity: 268,909 vehicles (Metric)
   - Entity: Q1 2024 (Time)
   - Relationship: Tesla REPORTS 268,909 vehicles
   - Relationship: 268,909 vehicles IN_PERIOD Q1 2024

2. When text says "Ford achieved 86.1% YoY increase", you MUST create:
   - Entity: Ford (Company)
   - Entity: 86.1% YoY increase (Metric)
   - Relationship: Ford REPORTS 86.1% YoY increase

3. Every Company mentioned with numbers MUST have REPORTS relationship
4. Every Metric MUST have IN_PERIOD relationship if time is mentioned

**Output Format (JSON):**
{{
  "entities": [
    {{"name": "Tesla", "type": "Company", "attributes": {{"country": "US"}}}},
    {{"name": "268,909 vehicles", "type": "Metric", "attributes": {{"value": "268909"}}}},
    {{"name": "Q1 2024", "type": "Time", "attributes": {{"period": "2024_Q1"}}}}
  ],
  "relationships": [
    {{"source": "Tesla", "target": "268,909 vehicles", "type": "REPORTS", "attributes": {{}}}},
    {{"source": "268,909 vehicles", "target": "Q1 2024", "type": "IN_PERIOD", "attributes": {{}}}}
  ]
}}

**Text to analyze:**
{text}

**Return ONLY valid JSON, no additional text.**
"""
    
    def __init__(self, api_key: str, base_url: str, model: str):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
    
    def extract_from_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Extract entities and relationships from a document."""
        text = f"Title: {document['title']}\n\nContent: {document['full_content']}"
        
        # Truncate if too long
        if len(text) > 8000:
            text = text[:8000] + "..."
        
        prompt = self.EXTRACTION_PROMPT.format(text=text)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=4000
            )
            
            result_text = response.choices[0].message.content
            
            # Parse JSON from response
            result_text = result_text.strip()
            if result_text.startswith('```json'):
                result_text = result_text[7:]
            if result_text.endswith('```'):
                result_text = result_text[:-3]
            
            result = json.loads(result_text)
            result['document_id'] = document['id']
            return result
            
        except json.JSONDecodeError as e:
            print(f"JSON parse error for {document['id']}: {e}")
            return {"entities": [], "relationships": [], "document_id": document['id']}
        except Exception as e:
            print(f"Extraction error for {document['id']}: {e}")
            return {"entities": [], "relationships": [], "document_id": document['id']}
    
    def extract_from_all_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract from all documents."""
        results = []
        for i, doc in enumerate(documents):
            print(f"Extracting from document {i+1}/{len(documents)}: {doc['id']}")
            result = self.extract_from_document(doc)
            results.append(result)
        return results


class EntityValidator:
    """Validate and deduplicate entities using rules."""
    
    KNOWN_COMPANIES = {
        'tesla', 'ford', 'bmw', 'mercedes', 'audi', 'hyundai', 'kia',
        'rivian', 'lucid', 'vinfast', 'toyota', 'honda', 'volkswagen',
        'gm', 'general motors', 'chevrolet', 'chevy', 'cadillac',
        'lexus', 'nissan', 'stellantis', 'ferrari', 'porsche'
    }
    
    KNOWN_LOCATIONS = {
        'us', 'united states', 'usa', 'china', 'europe', 'india',
        'california', 'texas', 'new york', 'japan', 'korea',
        'thailand', 'brazil', 'germany', 'uk', 'united kingdom'
    }
    
    def validate_entities(self, extraction_result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean entities."""
        entities = extraction_result.get('entities', [])
        relationships = extraction_result.get('relationships', [])
        
        # Normalize entity names
        normalized_entities = []
        for entity in entities:
            entity['name'] = self.normalize_name(entity['name'])
            if entity['name']:
                normalized_entities.append(entity)
        
        # Deduplicate entities
        unique_entities = self.deduplicate_entities(normalized_entities)
        
        # Update relationships with normalized names
        normalized_relationships = []
        for rel in relationships:
            rel['source'] = self.normalize_name(rel['source'])
            rel['target'] = self.normalize_name(rel['target'])
            if rel['source'] and rel['target']:
                normalized_relationships.append(rel)
        
        extraction_result['entities'] = unique_entities
        extraction_result['relationships'] = normalized_relationships
        return extraction_result
    
    def normalize_name(self, name: str) -> str:
        """Normalize entity name."""
        if not name:
            return ''
        name = name.strip()
        # Remove common suffixes
        for suffix in [' Inc', ' Corp', ' LLC', ' Ltd', ' Co']:
            if name.endswith(suffix):
                name = name[:-len(suffix)]
        return name
    
    def deduplicate_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate entities, keeping the one with most attributes."""
        seen = {}
        for entity in entities:
            key = (entity['name'].lower(), entity['type'])
            if key not in seen or len(entity.get('attributes', {})) > len(seen[key].get('attributes', {})):
                seen[key] = entity
        return list(seen.values())

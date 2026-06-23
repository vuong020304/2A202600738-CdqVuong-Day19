import networkx as nx
import matplotlib.pyplot as plt
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase
import json


class GraphStore:
    """Base class for graph storage."""
    
    def add_entity(self, entity: Dict[str, Any]) -> None:
        raise NotImplementedError
    
    def add_relationship(self, relationship: Dict[str, Any]) -> None:
        raise NotImplementedError
    
    def get_entity(self, name: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError
    
    def get_neighbors(self, name: str, depth: int = 1) -> List[Dict[str, Any]]:
        raise NotImplementedError
    
    def visualize(self, output_file: str = "graph.png") -> None:
        raise NotImplementedError


class NetworkXStore(GraphStore):
    """NetworkX graph storage for prototyping."""
    
    def __init__(self):
        self.graph = nx.DiGraph()
        self.entity_attributes = {}
    
    def add_entity(self, entity: Dict[str, Any]) -> None:
        """Add an entity node to the graph."""
        name = entity['name']
        entity_type = entity['type']
        attributes = entity.get('attributes', {})
        
        # Store type separately to avoid keyword conflict
        node_attrs = dict(attributes)
        node_attrs['entity_type'] = entity_type
        self.graph.add_node(name, **node_attrs)
        self.entity_attributes[name] = attributes
    
    def add_relationship(self, relationship: Dict[str, Any]) -> None:
        """Add a relationship edge to the graph."""
        source = relationship['source']
        target = relationship['target']
        rel_type = relationship['type']
        attributes = relationship.get('attributes', {})
        
        # Add nodes if they don't exist
        if source not in self.graph:
            self.graph.add_node(source, type='Unknown')
        if target not in self.graph:
            self.graph.add_node(target, type='Unknown')
        
        self.graph.add_edge(source, target, relationship=rel_type, **attributes)
    
    def get_entity(self, name: str) -> Optional[Dict[str, Any]]:
        """Get entity by name."""
        if name in self.graph:
            return {
                'name': name,
                'type': self.graph.nodes[name].get('type', 'Unknown'),
                'attributes': dict(self.graph.nodes[name])
            }
        return None
    
    def get_neighbors(self, name: str, depth: int = 1) -> List[Dict[str, Any]]:
        """Get neighbors up to specified depth."""
        if name not in self.graph:
            return []
        
        neighbors = []
        visited = set()
        
        def traverse(node, current_depth):
            if current_depth > depth or node in visited:
                return
            visited.add(node)
            
            # Get outgoing edges
            for target in self.graph.successors(node):
                edge_data = self.graph.edges[node, target]
                neighbors.append({
                    'source': node,
                    'target': target,
                    'relationship': edge_data.get('relationship', 'UNKNOWN'),
                    'attributes': {k: v for k, v in edge_data.items() if k != 'relationship'}
                })
                traverse(target, current_depth + 1)
            
            # Get incoming edges
            for source in self.graph.predecessors(node):
                edge_data = self.graph.edges[source, node]
                neighbors.append({
                    'source': source,
                    'target': node,
                    'relationship': edge_data.get('relationship', 'UNKNOWN'),
                    'attributes': {k: v for k, v in edge_data.items() if k != 'relationship'}
                })
                traverse(source, current_depth + 1)
        
        traverse(name, 0)
        return neighbors
    
    def search_entities(self, query: str) -> List[Dict[str, Any]]:
        """Search entities by name (case-insensitive partial match)."""
        query_lower = query.lower()
        results = []
        for node in self.graph.nodes():
            if query_lower in node.lower():
                results.append({
                    'name': node,
                    'type': self.graph.nodes[node].get('type', 'Unknown'),
                    'attributes': dict(self.graph.nodes[node])
                })
        return results
    
    def visualize(self, output_file: str = "graph.png") -> None:
        """Visualize the graph using matplotlib."""
        plt.figure(figsize=(20, 15))
        
        # Color nodes by type
        color_map = {
            'Company': '#FF6B6B',
            'Location': '#4ECDC4',
            'Topic': '#45B7D1',
            'Vehicle': '#96CEB4',
            'Metric': '#FFEAA7',
            'Policy': '#DDA0DD',
            'Time': '#98D8C8'
        }
        
        node_colors = []
        for node in self.graph.nodes():
            node_type = self.graph.nodes[node].get('type', 'Unknown')
            node_colors.append(color_map.get(node_type, '#CCCCCC'))
        
        # Layout
        pos = nx.spring_layout(self.graph, k=2, iterations=50, seed=42)
        
        # Draw nodes
        nx.draw_networkx_nodes(self.graph, pos, node_color=node_colors, 
                               node_size=1000, alpha=0.9)
        
        # Draw edges
        nx.draw_networkx_edges(self.graph, pos, edge_color='gray', 
                               arrows=True, arrowsize=20, alpha=0.6)
        
        # Draw labels
        nx.draw_networkx_labels(self.graph, pos, font_size=8, font_weight='bold')
        
        # Draw edge labels
        edge_labels = nx.get_edge_attributes(self.graph, 'relationship')
        nx.draw_networkx_edge_labels(self.graph, pos, edge_labels, font_size=6)
        
        plt.title("EV Industry Knowledge Graph", fontsize=16, fontweight='bold')
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"Graph saved to {output_file}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get graph statistics."""
        return {
            'nodes': self.graph.number_of_nodes(),
            'edges': self.graph.number_of_edges(),
            'node_types': dict(nx.get_node_attributes(self.graph, 'type')),
            'density': nx.density(self.graph)
        }


class Neo4jStore(GraphStore):
    """Neo4j graph database storage."""
    
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self._create_constraints()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get graph statistics from Neo4j."""
        with self.driver.session() as session:
            nodes_result = session.run("MATCH (n) RETURN count(n) as count")
            nodes = nodes_result.single()['count']
            
            rels_result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            rels = rels_result.single()['count']
            
            return {
                'nodes': nodes,
                'relationships': rels
            }
    
    def _create_constraints(self):
        """Create unique constraints for node types."""
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Company) REQUIRE c.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (l:Location) REQUIRE l.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (v:Vehicle) REQUIRE v.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (m:Metric) REQUIRE m.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Policy) REQUIRE p.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (time:Time) REQUIRE time.name IS UNIQUE"
        ]
        
        with self.driver.session() as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                except Exception as e:
                    print(f"Constraint creation note: {e}")
    
    def add_entity(self, entity: Dict[str, Any]) -> None:
        """Add an entity to Neo4j."""
        name = entity['name']
        entity_type = entity['type']
        attributes = entity.get('attributes', {})
        
        # Build properties string with key: $key format
        props = {**attributes, 'name': name}
        props_str = ', '.join([f'{k}: ${k}' for k in props.keys()])
        
        query = f"""
        MERGE (n:{entity_type} {{{props_str}}})
        RETURN n
        """
        
        with self.driver.session() as session:
            session.run(query, **props)
    
    def add_relationship(self, relationship: Dict[str, Any]) -> None:
        """Add a relationship to Neo4j."""
        source = relationship['source']
        target = relationship['target']
        rel_type = relationship['type']
        attributes = relationship.get('attributes', {})
        
        # Filter out reserved keys to avoid conflicts
        reserved = {'source', 'target', 'type'}
        props = {k: v for k, v in attributes.items() if k not in reserved}
        props_str = ', '.join([f'{k}: ${k}' for k in props.keys()]) if props else ''
        
        query = f"""
        MATCH (a {{name: $source}})
        MATCH (b {{name: $target}})
        MERGE (a)-[r:{rel_type} {{{props_str}}}]->(b)
        RETURN type(r)
        """
        
        with self.driver.session() as session:
            session.run(query, source=source, target=target, **props)
    
    def get_entity(self, name: str) -> Optional[Dict[str, Any]]:
        """Get entity by name."""
        query = """
        MATCH (n {name: $name})
        RETURN labels(n) as labels, properties(n) as props
        """
        
        with self.driver.session() as session:
            result = session.run(query, name=name)
            record = result.single()
            if record:
                return {
                    'name': name,
                    'type': record['labels'][0] if record['labels'] else 'Unknown',
                    'attributes': dict(record['props'])
                }
        return None
    
    def get_neighbors(self, name: str, depth: int = 1) -> List[Dict[str, Any]]:
        """Get neighbors up to specified depth."""
        query = """
        MATCH path = (start {name: $name})-[*1..""" + str(depth) + """]->(end)
        RETURN path
        LIMIT 100
        """
        
        neighbors = []
        with self.driver.session() as session:
            result = session.run(query, name=name)
            for record in result:
                path = record['path']
                # Extract relationships from path
                for i in range(len(path.relationships)):
                    rel = path.relationships[i]
                    start_node = path.nodes[i]
                    end_node = path.nodes[i + 1]
                    neighbors.append({
                        'source': start_node['name'],
                        'target': end_node['name'],
                        'relationship': rel.type,
                        'attributes': dict(rel)
                    })
        
        return neighbors
    
    def search_entities(self, query: str) -> List[Dict[str, Any]]:
        """Search entities by name."""
        cypher = """
        MATCH (n)
        WHERE n.name CONTAINS $search_term
        RETURN labels(n) as labels, properties(n) as props
        LIMIT 50
        """
        
        results = []
        with self.driver.session() as session:
            result = session.run(cypher, search_term=query)
            for record in result:
                results.append({
                    'name': record['props']['name'],
                    'type': record['labels'][0] if record['labels'] else 'Unknown',
                    'attributes': dict(record['props'])
                })
        
        return results
    
    def run_cypher(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Run a custom Cypher query."""
        with self.driver.session() as session:
            result = session.run(query, **(params or {}))
            return [dict(record) for record in result]
    
    def link_orphan_nodes(self):
        """Post-processing: link orphan nodes to existing graph."""
        linked_count = 0
        
        # 1. Link orphan Metrics to Companies via REPORTS (fuzzy match)
        query = """
        MATCH (m:Metric)
        WHERE NOT (m)--()
        WITH m
        MATCH (c:Company)
        WHERE toLower(c.name) IN [x IN split(toLower(m.name), ' ') WHERE size(x) > 2]
           OR toLower(m.name) CONTAINS toLower(c.name)
           OR toLower(c.name) CONTAINS toLower(split(m.name, ' ')[0])
        WITH m, c, 1 as score
        MERGE (c)-[:REPORTS]->(m)
        RETURN count(m) as linked
        """
        result = self.run_cypher(query)
        linked_count += result[0]['linked'] if result else 0
        
        # 2. Link remaining orphan Metrics to nearest Time
        query = """
        MATCH (m:Metric)
        WHERE NOT (m)--()
        WITH m
        MATCH (t:Time)
        WHERE toLower(m.name) CONTAINS toLower(t.name)
           OR toLower(t.name) CONTAINS '2024' AND toLower(m.name) CONTAINS '2024'
           OR toLower(t.name) CONTAINS '2023' AND toLower(m.name) CONTAINS '2023'
        MERGE (m)-[:IN_PERIOD]->(t)
        RETURN count(m) as linked
        """
        result = self.run_cypher(query)
        linked_count += result[0]['linked'] if result else 0
        
        # 3. Link orphan Locations to Topics (market/region related)
        query = """
        MATCH (l:Location)
        WHERE NOT (l)--()
        WITH l
        MATCH (t:Topic)
        WHERE toLower(t.name) CONTAINS 'market' OR toLower(t.name) CONTAINS 'sales'
           OR toLower(t.name) CONTAINS 'adoption' OR toLower(t.name) CONTAINS 'EV'
        MERGE (l)-[:OPERATES_IN]->(t)
        RETURN count(l) as linked
        """
        result = self.run_cypher(query)
        linked_count += result[0]['linked'] if result else 0
        
        # 4. Link orphan Time nodes to any Metric
        query = """
        MATCH (time:Time)
        WHERE NOT (time)--()
        WITH time
        MATCH (m:Metric)
        WHERE NOT (m)-[:IN_PERIOD]-()
        WITH time, m
        MERGE (m)-[:IN_PERIOD]->(time)
        RETURN count(time) as linked
        """
        result = self.run_cypher(query)
        linked_count += result[0]['linked'] if result else 0
        
        # 5. Link remaining orphan Topics to any Company
        query = """
        MATCH (t:Topic)
        WHERE NOT (t)--()
        WITH t
        MATCH (c:Company)
        MERGE (c)-[:MENTIONS]->(t)
        WITH t, c
        LIMIT 1
        RETURN count(t) as linked
        """
        result = self.run_cypher(query)
        linked_count += result[0]['linked'] if result else 0
        
        # 5. Fix mis-linked metrics: if a Metric REPORTS a non-Company, 
        # try to find the correct Company from context
        query = """
        MATCH (m:Metric)-[r:REPORTS]->(n)
        WHERE NOT n:Company
        WITH m, n
        MATCH (c:Company)
        WHERE toLower(c.name) IN [x IN split(toLower(m.name), ' ') WHERE size(x) > 2]
           OR toLower(m.name) CONTAINS toLower(c.name)
        WITH m, c
        OPTIONAL MATCH (m)-[old_r:REPORTS]->(old_target)
        WHERE NOT old_target:Company
        DELETE old_r
        MERGE (c)-[:REPORTS]->(m)
        RETURN count(m) as fixed
        """
        result = self.run_cypher(query)
        linked_count += result[0]['fixed'] if result else 0
        
        return linked_count
    
    def visualize(self, output_file: str = "graph.png") -> None:
        """Export graph for visualization (Neo4j Browser recommended)."""
        # Get all nodes and relationships
        nodes_query = "MATCH (n) RETURN n.name as name, labels(n) as labels"
        edges_query = "MATCH (a)-[r]->(b) RETURN a.name as source, b.name as target, type(r) as type"
        
        with self.driver.session() as session:
            nodes = [dict(record) for record in session.run(nodes_query)]
            edges = [dict(record) for record in session.run(edges_query)]
        
        # Create NetworkX graph for visualization
        G = nx.DiGraph()
        for node in nodes:
            G.add_node(node['name'], type=node['labels'][0] if node['labels'] else 'Unknown')
        for edge in edges:
            G.add_edge(edge['source'], edge['target'], relationship=edge['type'])
        
        # Use NetworkXStore visualization
        temp_store = NetworkXStore()
        temp_store.graph = G
        temp_store.visualize(output_file)
    
    def clear_database(self):
        """Clear all nodes and relationships."""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
    
    def close(self):
        """Close the driver connection."""
        self.driver.close()

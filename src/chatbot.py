from typing import Optional
from .query_engine import QueryEngine


class Chatbot:
    """CLI chatbot for GraphRAG."""
    
    WELCOME_MESSAGE = """
╔══════════════════════════════════════════════════════════════╗
║           EV GraphRAG Chatbot                               ║
║   Hỏi đáp về ngành công nghiệp xe điện (EV)               ║
╚══════════════════════════════════════════════════════════════╝

Câu hỏi mẫu:
- Tesla bán được bao nhiêu xe trong Q1 2024?
- Phản ứng của người tiêu dùng với sạc EV như thế nào?
- Chính sách nào đang thúc đẩy thị trường EV?
- So sánh doanh số Tesla và Ford

Gõ 'quit' hoặc 'exit' để thoát.
Gõ 'stats' để xem thống kê đồ thị.
Gõ 'graph' để visualize đồ thị.
"""
    
    def __init__(self, query_engine: QueryEngine):
        self.query_engine = query_engine
        self.history = []
    
    def display_answer(self, result: dict):
        """Display the answer in a formatted way."""
        print("\n" + "="*60)
        print("📋 CÂU HỎI:", result['question'])
        print("-"*60)
        print("🔍 ENTITIES:", ', '.join(result['entities']))
        print("-"*60)
        print("📝 TRẢ LỜI:")
        print(result['answer'])
        print("="*60 + "\n")
    
    def run(self):
        """Run the interactive chatbot."""
        print(self.WELCOME_MESSAGE)
        
        while True:
            try:
                user_input = input("Bạn: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("Tạm biệt! 👋")
                    break
                
                if user_input.lower() == 'stats':
                    self.show_stats()
                    continue
                
                if user_input.lower() == 'graph':
                    self.show_graph()
                    continue
                
                if user_input.lower() == 'history':
                    self.show_history()
                    continue
                
                # Query the graph
                print("\n⏳ Đang truy vấn đồ thị tri thức...")
                result = self.query_engine.query(user_input)
                
                # Display answer
                self.display_answer(result)
                
                # Save to history
                self.history.append(result)
                
            except KeyboardInterrupt:
                print("\n\nTạm biệt! 👋")
                break
            except Exception as e:
                print(f"\n❌ Lỗi: {e}")
    
    def show_stats(self):
        """Show graph statistics."""
        if hasattr(self.query_engine.graph_store, 'get_stats'):
            stats = self.query_engine.graph_store.get_stats()
            print("\n📊 THỐNG KÊ ĐỒ THỊ:")
            print(f"  - Số node: {stats.get('nodes', 'N/A')}")
            print(f"  - Số edge: {stats.get('edges', 'N/A')}")
            print(f"  - Density: {stats.get('density', 'N/A'):.4f}")
            
            # Count by type
            node_types = stats.get('node_types', {})
            if node_types:
                type_counts = {}
                for node_type in node_types.values():
                    type_counts[node_type] = type_counts.get(node_type, 0) + 1
                print("\n  Phân loại node:")
                for t, count in sorted(type_counts.items()):
                    print(f"    - {t}: {count}")
        else:
            print("Thống kê không khả dụng.")
    
    def show_graph(self):
        """Visualize the graph."""
        try:
            self.query_engine.graph_store.visualize("knowledge_graph.png")
            print("✅ Đã lưu đồ thị vào knowledge_graph.png")
        except Exception as e:
            print(f"❌ Lỗi khi visualize: {e}")
    
    def show_history(self):
        """Show query history."""
        if not self.history:
            print("\n📜 Chưa có lịch sử truy vấn.")
            return
        
        print("\n📜 LỊCH SỬ TRUY VẤN:")
        for i, item in enumerate(self.history[-10:], 1):
            print(f"{i}. {item['question'][:50]}...")

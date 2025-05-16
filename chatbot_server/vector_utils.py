import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.neighbors import NearestNeighbors
from typing import List, Dict, Any, Tuple
import re
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("vector_search")

class VectorSearch:
    def __init__(self, model_name: str = 'paraphrase-multilingual-MiniLM-L12-v2'):
        """Initialize vector search system"""
        logger.info(f"初始化VectorSearch，使用模型: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.index = None
        self.cases = []
        self.embeddings = None
        self.k = 5
        
    def create_embeddings(self, cases: List[Dict[str, Any]]) -> np.ndarray:
        """Create vector embeddings for cases
        
        Focus on key fields: Subject/Summary, Description, Category, Task, Priority/Severity, DefectPhase
        """
        logger.info(f"开始创建嵌入向量，输入案例数量: {len(cases)}")
        texts = []
        valid_cases = []
        
        # Key fields to focus on for vector similarity
        key_fields = ['Subject', 'Summary', 'Description', 'Category', 'CategoryName', 
                      'Task', 'TaskName', 'Priority', 'PREFERENCE', 'DefectPhase']
        
        for case in cases:
            # 只处理包含RCAReport的历史案例
            if 'RCAReport' in case and case['RCAReport'] and not case.get('RCAReport', '').strip() == '':
                # 启动构建字段组合文本
                field_parts = []
                
                # 添加Summary/Subject (不再重复以增加权重)
                summary = case.get('Subject', case.get('Summary', ''))
                if summary:
                    field_parts.append(f"Summary: {summary}")
                
                # 添加Description (不再重复以增加权重)
                description = case.get('Description', '')
                if description:
                    field_parts.append(f"Description: {description}")
                
                # 添加其他关键字段
                for field in key_fields:
                    if field not in ['Subject', 'Summary', 'Description'] and field in case and case[field]:
                        field_parts.append(f"{field}: {case[field]}")
                
                # 从RCA报告中提取关键部分而非全文
                if 'RCAReport' in case and case['RCAReport']:
                    rca_text = case['RCAReport']
                    
                    # 定义要提取的所有关键部分
                    key_sections = {
                        'Issue Summary': None,
                        'Impact Analysis': None,
                        'Root Causes': None,
                        'Resolution': None,
                        'Preventive Measures': None,
                        'Supplementary Information': None,
                        'Conclusion': None
                    }
                    
                    # 提取各个关键部分
                    for section in key_sections.keys():
                        pattern = rf"{section}\s*[:\n]+(.*?)(?=(##|\Z|#\s+))"
                        match = re.search(pattern, rca_text, re.DOTALL | re.IGNORECASE)
                        if match:
                            key_sections[section] = match.group(1).strip()
                    
                    # 添加提取的所有关键部分
                    for section, content in key_sections.items():
                        if content:
                            # 移除标题中的数字和符号
                            clean_section = re.sub(r'^\d+\.\s*', '', section)
                            clean_section = re.sub(r'[^\w\s]', '', clean_section).strip()
                            field_parts.append(f"{clean_section}: {content}")
                    
                    # 如果未找到任何关键部分，使用完整报告
                    if not any(key_sections.values()):
                        field_parts.append(f"RCA: {rca_text}")
                
                # 组合所有字段部分
                text = " ".join(field_parts)
                texts.append(text)
                valid_cases.append(case)
        
        # 更新案例列表，只保留有效案例
        self.cases = valid_cases
        
        logger.info(f"筛选后的有效案例数: {len(valid_cases)}")
        
        if not texts:
            logger.error("没有找到包含RCAReport字段的有效案例")
            raise ValueError("未找到包含RCAReport字段的有效案例")
        
        for i, case in enumerate(valid_cases[:3]):
            case_id = case.get('ID', 'Unknown')
            summary = case.get('Summary', '')
            summary_text = summary[:50] + "..." if summary and len(summary) > 50 else summary or "(无摘要)"
            logger.info(f"案例 {i+1} ID: {case_id}, Summary: {summary_text}")
            
        # 生成嵌入向量
        logger.info(f"开始生成嵌入向量，文本数: {len(texts)}")
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        logger.info(f"嵌入向量生成完成，形状: {embeddings.shape}")
        return embeddings
        
    def build_index(self, cases: List[Dict[str,Any]], k: int = 5):
        """Build index using only cases with RCAReport"""
        logger.info(f"开始构建索引，输入案例数: {len(cases)}")
        self.k = k
        
        # 创建嵌入向量
        self.embeddings = self.create_embeddings(cases)
        
        # 确定邻居数量
        n_neighbors = min(self.k, len(self.cases))
        
        # 构建索引
        logger.info(f"构建最近邻索引，邻居数: {n_neighbors}")
        self.index = NearestNeighbors(n_neighbors=n_neighbors, metric='cosine')
        self.index.fit(self.embeddings)
        logger.info("索引构建完成")
        
    def search(self, query: str, k: int = None) -> List[Tuple[Dict[str, Any], float]]:
        """Search for similar cases
        
        Args:
            query: Query string containing key fields from the new case
            k: Number of results to return
        """
        logger.info(f"开始搜索，查询: {query[:100]}...")
        if self.index is None:
            logger.error("索引未构建，请先调用build_index")
            raise ValueError("索引未构建，请先调用build_index")
            
        if k is None:
            k = self.k
            
        # 确保k不超过历史案例数量
        k = min(k, len(self.cases))
        logger.info(f"搜索最近的 {k} 个案例")
        
        # 编码查询向量
        query_vector = self.model.encode([query], convert_to_numpy=True)
        
        # 搜索相似案例
        distances, indices = self.index.kneighbors(query_vector, n_neighbors=k)
        
        # 构建结果列表
        results = []
        for i, idx in enumerate(indices[0]):
            results.append((self.cases[idx], float(distances[0][i])))
            
        logger.info(f"搜索完成，找到 {len(results)} 个结果")
        for i, (case, distance) in enumerate(results[:3]):
            case_id = case.get('ID', 'Unknown')
            similarity = (1 - distance) * 100
            logger.info(f"结果 {i+1}: ID={case_id}, 相似度={similarity:.2f}%, 距离={distance:.4f}")
            
        return results 
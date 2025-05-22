import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.neighbors import NearestNeighbors
from typing import List, Dict, Any, Tuple
import re
import logging
import json
import time
import openai
import faiss

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("vector_search")

class VectorSearch:
    def __init__(self, model_name: str = 'paraphrase-multilingual-MiniLM-L12-v2'):
        """Initialize vector search system"""
        self.start_time = time.time()
        logger.info(f"初始化向量搜索系统，使用模型: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.index = None
        self.cases = []
        self.embeddings = None
        self.k = 5
        logger.info(f"向量搜索系统初始化完成，耗时: {time.time() - self.start_time:.2f}秒")
        
    async def find_similar_cases(self, description: str, historical_cases: List[Dict[str, Any]], k: int = 5) -> List[Dict[str, Any]]:
        """异步查找相似案例
        
        Args:
            description: 新案例的描述
            historical_cases: 历史案例列表
            k: 返回的相似案例数量
        """
        start_time = time.time()
        logger.info("开始查找相似案例")
        
        try:
            # 创建嵌入向量
            logger.info("开始创建嵌入向量")
            embeddings = self.create_embeddings(historical_cases)
            logger.info(f"嵌入向量创建完成，耗时: {time.time() - start_time:.2f}秒")
            
            # 构建索引
            logger.info("开始构建索引")
            self.build_index(historical_cases, k)
            logger.info(f"索引构建完成，耗时: {time.time() - start_time:.2f}秒")
            
            # 搜索相似案例
            logger.info("开始搜索相似案例")
            results = self.search(description, k)
            logger.info(f"相似案例搜索完成，找到{len(results)}个案例，耗时: {time.time() - start_time:.2f}秒")
            
            # 处理结果
            similar_cases = []
            for case, similarity in results:
                # 规范化案例数据
                normalized_case = self._normalize_case(case)
                normalized_case['similarity'] = (1 - similarity) * 100
                similar_cases.append(normalized_case)
            
            logger.info(f"案例处理完成，总耗时: {time.time() - start_time:.2f}秒")
            return similar_cases
            
        except Exception as e:
            logger.error(f"查找相似案例失败: {str(e)}")
            raise
            
    def _normalize_case(self, case: Dict[str, Any]) -> Dict[str, Any]:
        """规范化案例数据"""
        normalized = case.copy()
        
        # 处理Summary和Subject
        if not normalized.get('Summary') and normalized.get('Subject'):
            normalized['Summary'] = normalized['Subject']
        if not normalized.get('Subject') and normalized.get('Summary'):
            normalized['Subject'] = normalized['Summary']
            
        # 处理Priority
        if normalized.get('Priority') is not None:
            if not isinstance(normalized['Priority'], str):
                normalized['Priority'] = str(normalized['Priority'])
            if not normalized['Priority'].startswith('Severity'):
                normalized['Priority'] = f"Severity {normalized['Priority']}"
                
        # 处理PREFERENCE
        preference_value = None
        for key in ['PREFERENCE', 'preference', 'Preference', 'X_PREFERENCE', 'x_preference', 'PREFERENCE_STR']:
            if key in normalized and normalized[key] is not None:
                preference_value = normalized[key]
                break
                
        if preference_value is None and 'PreferenceLevel' in normalized:
            level = normalized['PreferenceLevel']
            if level == 'High':
                preference_value = 1
            elif level == 'Medium':
                preference_value = 2
            elif level == 'Low':
                preference_value = 3
                
        normalized['PREFERENCE'] = preference_value if preference_value is not None else 3
        
        return normalized
        
    def create_embeddings(self, cases: List[Dict[str, Any]]) -> np.ndarray:
        """创建案例的向量嵌入"""
        start_time = time.time()
        logger.info(f"开始创建嵌入向量，案例数量: {len(cases)}")
        
        texts = []
        valid_cases = []
        
        for case in cases:
            if 'RCAReport' in case and case['RCAReport'] and case['RCAReport'].strip():
                field_parts = []
                
                if 'RCAReport' in case and case['RCAReport']:
                    rca_text = case['RCAReport']
                    
                    key_sections = {
                        'Issue Summary': None,
                        'Impact Analysis': None,
                        'Root Causes': None,
                        'Resolution': None,
                        'Preventive Measures': None,
                        'Supplementary Information': None,
                        'Conclusion': None
                    }
                    
                    for section in key_sections.keys():
                        pattern = rf"{section}\s*[:\n]+(.*?)(?=(##|\Z|#\s+))"
                        match = re.search(pattern, rca_text, re.DOTALL | re.IGNORECASE)
                        if match:
                            key_sections[section] = match.group(1).strip()
                    
                    for section, content in key_sections.items():
                        if content:
                            clean_section = re.sub(r'^\d+\.\s*', '', section)
                            clean_section = re.sub(r'[^\w\s]', '', clean_section).strip()
                            field_parts.append(f"{clean_section}: {content}")
                    
                    if not any(key_sections.values()):
                        field_parts.append(f"RCA: {rca_text}")
                
                text = " ".join(field_parts)
                texts.append(text)
                valid_cases.append(case)
        
        self.cases = valid_cases
        logger.info(f"有效案例数量: {len(valid_cases)}")
        
        if not texts:
            logger.error("没有找到包含RCAReport的有效案例")
            raise ValueError("没有找到包含RCAReport的有效案例")
        
        logger.info("开始生成嵌入向量")
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        logger.info(f"嵌入向量生成完成，形状: {embeddings.shape}，耗时: {time.time() - start_time:.2f}秒")
        return embeddings
        
    def build_index(self, cases: List[Dict[str,Any]], k: int = 5):
        """构建向量索引"""
        start_time = time.time()
        logger.info(f"开始构建索引，案例数量: {len(cases)}")
        
        self.k = k
        self.embeddings = self.create_embeddings(cases)
        
        n_neighbors = min(self.k, len(self.cases))
        logger.info(f"构建最近邻索引，邻居数量: {n_neighbors}")
        
        self.index = NearestNeighbors(n_neighbors=n_neighbors, metric='cosine')
        self.index.fit(self.embeddings)
        
        logger.info(f"索引构建完成，耗时: {time.time() - start_time:.2f}秒")
        
    def search(self, query: str, k: int = None) -> List[Tuple[Dict[str, Any], float]]:
        """搜索相似案例"""
        start_time = time.time()
        logger.info(f"开始搜索，查询: {query[:100]}...")
        
        if self.index is None:
            logger.error("索引未构建")
            raise ValueError("索引未构建")
        
        if k is None:
            k = self.k
        k = min(k, len(self.cases))
        
        logger.info(f"搜索最近的{k}个案例")
        query_vector = self.model.encode([query], convert_to_numpy=True)
        
        distances, indices = self.index.kneighbors(query_vector, n_neighbors=k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            case = self.cases[idx]
            results.append((case, float(distances[0][i])))
            
        logger.info(f"搜索完成，找到{len(results)}个结果，耗时: {time.time() - start_time:.2f}秒")
        return results 
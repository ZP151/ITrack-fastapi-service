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

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("vector_search")

class VectorSearch:
    def __init__(self, model_name: str = 'paraphrase-multilingual-MiniLM-L12-v2'):
        """Initialize vector search system"""
        self.start_time = time.time()
        logger.info(f"Initialize vector search system, using model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.index = None
        self.cases = []
        self.embeddings = None
        self.k = 5
        logger.info(f"Vector search system initialized, time taken: {time.time() - self.start_time:.2f} seconds")
        
    async def find_similar_cases(self, description: str, historical_cases: List[Dict[str, Any]], k: int = 5) -> List[Dict[str, Any]]:
        """Asynchronous search for similar cases
        
        Args:
            description: Description of the new case
            historical_cases: List of historical cases
            k: Number of similar cases to return
        """
        start_time = time.time()
        logger.info("Starting to search for similar cases")
        
        try:
            # Create embeddings
            logger.info("Starting to create embeddings")
            embeddings = self.create_embeddings(historical_cases)
            logger.info(f"Embeddings created, time taken: {time.time() - start_time:.2f} seconds")
            
            # Build index
            logger.info("Starting to build index")
            self.build_index(historical_cases, k)
            logger.info(f"Index built, time taken: {time.time() - start_time:.2f} seconds")
            
            # Search for similar cases
            logger.info("Starting to search for similar cases")
            results = self.search(description, k)
            logger.info(f"Similar case search completed, found {len(results)} cases, time taken: {time.time() - start_time:.2f} seconds")
            
            # Process results
            similar_cases = []
            for case, similarity in results:
                # Normalize case data
                normalized_case = self._normalize_case(case)
                normalized_case['similarity'] = (1 - similarity) * 100
                similar_cases.append(normalized_case)
            
            logger.info(f"Case processing completed, total time taken: {time.time() - start_time:.2f} seconds")
            return similar_cases
            
        except Exception as e:
            logger.error(f"Failed to search for similar cases: {str(e)}")
            raise
            
    def _normalize_case(self, case: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize case data"""
        normalized = case.copy()
        
        # Process Summary and Subject
        if not normalized.get('Summary') and normalized.get('Subject'):
            normalized['Summary'] = normalized['Subject']
        if not normalized.get('Subject') and normalized.get('Summary'):
            normalized['Subject'] = normalized['Summary']
            
        # Process Priority
        if normalized.get('Priority') is not None:
            if not isinstance(normalized['Priority'], str):
                normalized['Priority'] = str(normalized['Priority'])
            if not normalized['Priority'].startswith('Severity'):
                normalized['Priority'] = f"Severity {normalized['Priority']}"
                
        # Process PREFERENCE
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
        """Create embeddings for cases"""
        start_time = time.time()
        logger.info(f"Creating embeddings for cases, number of cases: {len(cases)}")
        
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
        logger.info(f"Number of valid cases: {len(valid_cases)}")
        
        if not texts:
            logger.error("No valid cases found with RCAReport")
            raise ValueError("No valid cases found with RCAReport")
        
        logger.info("Starting to generate embeddings")
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        logger.info(f"Embeddings generated, shape: {embeddings.shape}, time taken: {time.time() - start_time:.2f} seconds")
        return embeddings
        
    def build_index(self, cases: List[Dict[str,Any]], k: int = 5):
        """Build vector index"""
        start_time = time.time()
        logger.info(f"Building index, number of cases: {len(cases)}")
        
        self.k = k
        self.embeddings = self.create_embeddings(cases)
        
        n_neighbors = min(self.k, len(self.cases))
        logger.info(f"Building nearest neighbor index, number of neighbors: {n_neighbors}")
        
        self.index = NearestNeighbors(n_neighbors=n_neighbors, metric='cosine')
        self.index.fit(self.embeddings)
        
        logger.info(f"Index built, time taken: {time.time() - start_time:.2f} seconds")
        
    def search(self, query: str, k: int = None) -> List[Tuple[Dict[str, Any], float]]:
        """Search for similar cases"""
        start_time = time.time()
        logger.info(f"Starting to search, query: {query[:100]}...")
        
        if self.index is None:
            logger.error("Index not built")
            raise ValueError("Index not built")
        
        if k is None:
            k = self.k
        k = min(k, len(self.cases))
        
        logger.info(f"Searching for the nearest {k} cases")
        query_vector = self.model.encode([query], convert_to_numpy=True)
        
        distances, indices = self.index.kneighbors(query_vector, n_neighbors=k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            case = self.cases[idx]
            results.append((case, float(distances[0][i])))
            
        logger.info(f"Search completed, found {len(results)} results, time taken: {time.time() - start_time:.2f} seconds")
        return results 
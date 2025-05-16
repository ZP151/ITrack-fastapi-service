from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Union, Any
import openai
import os
import json
import copy
import re
from typing import Union
import logging,time
from dotenv import load_dotenv
from vector_utils import VectorSearch

# Load the .env file
load_dotenv('.env')

# Read the OpenAI API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Missing OpenAI API Key. Set OPENAI_API_KEY in .env file or as an environment variable.")

app = FastAPI()

# Load prompt from external file
def load_prompt():
    """
    Load the prompt template.
    """
    try:
        with open("prompt_template.md", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Error loading prompt template: {e}")
        return ""

# Load the final RCA report prompt word template.        
def load_final_rca_template():
    """
    Load the final RCA report prompt word template.
    """
    try:
        with open("final_rca_template.md", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Error loading final RCA template: {e}")
        return ""
        
PROMPT_TEMPLATE = load_prompt()
FINAL_RCA_TEMPLATE = load_final_rca_template()

# Initialize session_store to store RCA polling session data
session_store = {}
# session_store需要设置定时清理，更新还是清空？不然会内溢出？
# If the project has the opportunity to go online, I need to save it to the library before cleaning up the session_store[session_id] or clearing the session_store, for debugging after the project goes online.

# Define data model based on the prompt structure
class DynamicField(BaseModel):
    key: str
    type: str  # "string" or "array"
    value: Union[str, List[str]] = "TBD"  # Default placeholder value
    is_confirmed: bool = False

class ImpactAnalysis(BaseModel):
    affected_module: str = "Unknown"
    severity: str = "Severity 1"
    priority: str = "Medium"  # Update the default value to match the front end
    defect_phase: str = "Unknown"  # Update the default value to match the front end
    dynamic_fields: Optional[List[DynamicField]] = []

class Resolution(BaseModel):
    fix_applied: str = "Not provided"
    dynamic_fields: Optional[List[DynamicField]] = []

class PreventiveMeasures(BaseModel):
    general_measure: str = "TBD"
    dynamic_fields: Optional[List[DynamicField]] = []

class SupplementaryInfo(BaseModel):
    dynamic_fields: Optional[List[DynamicField]] = []

class AdditionalQuestions(BaseModel):
    dynamic_fields: Optional[List[DynamicField]] = []

class RCARequest(BaseModel):
    session_id: str
    category: str  # Replace issue_title
    task: str  # Add new field
    summary: str  # Replace issue_summary
    description: str  # Add new field
    root_causes: List[str]
    conclusion: str
    impact_analysis: ImpactAnalysis
    resolution: Resolution
    preventive_measures: PreventiveMeasures
    supplementary_info: SupplementaryInfo
    additional_questions: AdditionalQuestions
    is_final: bool  # Determines if this is the final iteration

class RCAResponse(BaseModel):
    category: str  # Replace issue_title
    task: str  # Add new field
    summary: str  # Replace issue_summary
    description: str  # Add new field
    root_causes: List[str]
    conclusion: str
    impact_analysis: ImpactAnalysis
    resolution: Resolution
    supplementary_info: SupplementaryInfo
    preventive_measures: PreventiveMeasures
    additional_questions: AdditionalQuestions
    
def process_rca_data(session_data, new_data):
    """
    Process RCA data:
    - 1️⃣ **Merge session_data and new_data**
    - 2️⃣ **Filter dynamic_fields to only keep is_confirmed=True**
    - 3️⃣ **Ensure all fields conform to the RCAResponse structure**
    """
    required_keys = {
        "category": "",  # Replace issue_title
        "task": "",  # Add new field
        "summary": "",  # Replace issue_summary
        "description": "",  # Add new field
        "root_causes": [],
        "conclusion": "",
        "impact_analysis": {"affected_module": "", "severity": "", "priority": "", "defect_phase": "", "dynamic_fields": []},
        "resolution": {"fix_applied": "", "dynamic_fields": []},
        "preventive_measures": {"general_measure": "", "dynamic_fields": []},
        "supplementary_info": {"dynamic_fields": []},
        "additional_questions": {"dynamic_fields": []},
        "is_final": False
    }

    for key, default_value in required_keys.items():
        # **Ensure all keys exist in session_data**
        if key not in session_data:
            session_data[key] = default_value

        # **Get the value of new data**
        new_value = new_data.get(key, default_value)

        # **If key is dynamic_fields, merge and filter items with is_confirmed=False**
        if isinstance(new_value, dict) and "dynamic_fields" in new_value:
            existing_fields = session_data[key].get("dynamic_fields", [])
            new_fields = new_value["dynamic_fields"]
            field_dict = {field["key"]: field for field in existing_fields}

            for field in new_fields:
                if field["is_confirmed"]:
                    field_dict[field["key"]] = field  # **Update or add fields**

            session_data[key]["dynamic_fields"] = list(field_dict.values())

        # **If it is a list, merge**
        elif isinstance(new_value, list):
            session_data[key].extend(new_value)

            # **Ensure root_causes only contains strings**
            if key == "root_causes":
                session_data[key] = [str(item) if isinstance(item, dict) else item for item in session_data[key]]

        # **If it is a dictionary, recursively merge**
        elif isinstance(new_value, dict):
            session_data[key] = process_rca_data(session_data[key], new_value)

        # **Normal fields (strings, booleans, etc.), directly overwrite**
        else:
            session_data[key] = new_value

    return session_data


def ensure_complete_rca_request(rca_request: RCARequest) -> RCARequest:
    """
    Ensure all fields in `RCARequest` have default values to prevent KeyError
    """
    return RCARequest(
        session_id=rca_request.session_id,
        category=rca_request.category or "",  # Replace issue_title
        task=rca_request.task or "",  # Add new field
        summary=rca_request.summary or "",  # Replace issue_summary
        description=rca_request.description or "",  # Add new field
        root_causes=rca_request.root_causes if rca_request.root_causes else [],
        conclusion=rca_request.conclusion or "",
        impact_analysis=rca_request.impact_analysis or ImpactAnalysis(),
        resolution=rca_request.resolution or Resolution(),
        preventive_measures=rca_request.preventive_measures or PreventiveMeasures(),
        supplementary_info=rca_request.supplementary_info or SupplementaryInfo(),
        additional_questions=rca_request.additional_questions or AdditionalQuestions(),
        is_final=rca_request.is_final
    )

def extract_json_from_response(text):
    """
    Parse the JSON returned by OpenAI, remove Markdown code blocks, and ensure correct format.
    """
    json_match = re.search(r"```json\s*([\s\S]*?)\s*```", text)
    if json_match:
        return json_match.group(1)  # **Extract JSON part**
    return text  # **If no Markdown code block, return original content**

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

@app.post("/refine_rca", response_model=Union[RCAResponse, dict])
def refine_rca(rca_request: RCARequest) -> Union[RCAResponse, dict]:
    """Processes issue report and calls OpenAI to refine it."""
    session_id = rca_request.session_id
    
    logging.info(f"Received request for session_id: {session_id}")

    start_time = time.time()  # record start time
    
    # **If is_final=True, generate the final RCA report**
    if rca_request.is_final:
        logging.info(f"Final request received for session_id: {session_id}. Generating RCA report.")
        
        # Ensure complete request data
        rca_request = ensure_complete_rca_request(rca_request)
        
        # Construct request data
        rca_data = rca_request.model_dump()
        
        # No longer strictly filter dynamic_fields, keep more information for AI analysis
        # Just mark which fields are confirmed, let AI decide how to use this data
        for section in ["impact_analysis", "resolution", "preventive_measures", "supplementary_info"]:
            if section in rca_data and "dynamic_fields" in rca_data[section]:
                # Add a flag to indicate whether the field has been confirmed
                for field in rca_data[section]["dynamic_fields"]:
                    if not field.get("is_confirmed", False):
                        field["ai_note"] = "This field is not confirmed by user but may contain valuable information"
        
        # Call OpenAI to generate the final RCA report
        try:
            logging.info("Calling OpenAI API to generate final RCA report")
            openai.api_key = OPENAI_API_KEY
            
            # Construct messages
            messages = [
                {"role": "system", "content": FINAL_RCA_TEMPLATE},
                {"role": "user", "content": json.dumps(rca_data, indent=2)}
            ]
            
            # Call API - Increase temperature and maximum tokens to allow more creative and detailed content generation
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.5,  # Increase temperature to increase creativity
                max_tokens=3000   # Increase maximum tokens to allow more detailed reports
            )
            
            # Get report content
            rca_report = response.choices[0].message.content.strip()
            
            # Use regex to replace any other Chinese characters
            rca_report = re.sub(r'[\u4e00-\u9fff]', 'N/A', rca_report)
            
            # Handle empty conclusion case - if the conclusion only contains "None" or "N/A", add a prompt to generate a new conclusion
            if "## 7. Conclusion\nNone" in rca_report or "## 7. Conclusion\nN/A" in rca_report:
                # Extract report content as context
                report_context = rca_report
                
                # Create a request to generate a complete conclusion
                conclusion_messages = [
                    {"role": "system", "content": "You are an AI that creates detailed conclusions for Root Cause Analysis reports. Given the RCA report content, generate a comprehensive conclusion that summarizes the findings, impact, root causes, resolutions, and preventive measures. The conclusion should be professional and actionable."},
                    {"role": "user", "content": f"Based on this Root Cause Analysis report, generate a comprehensive conclusion paragraph:\n\n{report_context}"}
                ]
                
                # Call API to generate a conclusion
                conclusion_response = openai.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=conclusion_messages,
                    temperature=0.4,
                    max_tokens=500
                )
                
                # Get conclusion content and replace original conclusion
                new_conclusion = conclusion_response.choices[0].message.content.strip()
                rca_report = rca_report.replace("## 7. Conclusion\nNone", f"## 7. Conclusion\n{new_conclusion}")
                rca_report = rca_report.replace("## 7. Conclusion\nN/A", f"## 7. Conclusion\n{new_conclusion}")
            
            # Clear session
            if session_id in session_store:
                del session_store[session_id]
                
            logging.info(f"RCA report generated successfully for session {session_id}")
            
            # Returns a response containing a complete report
            return {
            "status": "success",
            "rca_report": rca_report,# Returns a complete RCA report as formatted markdown string
            "data": rca_data # Also returns raw data for possible use by the front end
            }
            
        except Exception as e:
            logging.error(f"Error generating RCA report: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error generating RCA report: {str(e)}")
    
    # The processing logic for non-final requests remains unchanged
    rca_request = ensure_complete_rca_request(rca_request)
    
    # **Initialize session_store**
    if session_id not in session_store:
        session_store[session_id] = {
            "is_first_request": True,
            "context": [  # **Store conversation history directly**
                {"role": "system", "content": PROMPT_TEMPLATE}  # **Only add system role once**
            ]
        }

    last_response_time = time.time()
    logging.info(f"Session store prepared. Time taken: {last_response_time - start_time:.3f}s")
    

    # **Optimize session_store size**# Only keep the last 10 messages
    if len(session_store[session_id]["context"]) > 10:
        session_store[session_id]["context"] = session_store[session_id]["context"][-10:]  

    current_session_data = session_store[session_id]["context"][-1]["content"]
    try:
        current_session_data = json.loads(current_session_data)
    except json.JSONDecodeError:
        logging.warning(f"Failed to decode JSON for session {session_id}, resetting session context.")
        session_store[session_id]["context"] = [{"role": "system", "content": PROMPT_TEMPLATE}]
        current_session_data = {}

    logging.info(f"Processing RCA data for session {session_id}")
    current_session_data = process_rca_data(current_session_data, rca_request.model_dump())


    # # **Create a RCA copy (get the last assistant response from `context`)**
    # last_assistant_response = (
    #     session_store[session_id]["context"][-1]["content"]
    #     if len(session_store[session_id]["context"]) > 1
    #     else "{}"  # **If there is no historical data, use an empty JSON**
    # )
    
    # current_session_data = json.loads(last_assistant_response)
    
    # logging.info(f"Processing RCA data for session {session_id}")

    # # **Merge & filter new request data**
    # current_session_data = process_rca_data(current_session_data, rca_request.model_dump())


    # **Construct OpenAI messages**
    session_store[session_id]["context"].append(
        {"role": "user", "content": json.dumps(current_session_data, indent=2)}
    )
    
    logging.info(f"Calling OpenAI API for session {session_id}")

    # **Call OpenAI API**
    openai.api_key = OPENAI_API_KEY
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",  
            messages=session_store[session_id]["context"],
            temperature=0.5,
            max_tokens=1000
        )
    except Exception as e:
        logging.error(f"OpenAI API error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OpenAI API error: {str(e)}")

    call_time = time.time()
    logging.info(f"OpenAI API call completed in {call_time - last_response_time:.3f}s")
    last_response_time = call_time

    # **Process OpenAI response**
    assistant_response = response.choices[0].message.content
    processed_text = extract_json_from_response(assistant_response)

    try:
        response_data = json.loads(processed_text.strip())
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse JSON response: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to parse response: {str(e)}")
    
    # **Save OpenAI response to session_store**
    session_store[session_id]["context"].append(
        {"role": "assistant", "content": json.dumps(response_data, indent=2)}
    )

    # **Record response time**
    logging.info(f"Total processing time: {time.time() - start_time:.3f}s")
    
    # **Return structured data**
    return response_data

class PredictionRequest(BaseModel):
    description: str
    historical_cases: List[dict]
    new_case: Optional[dict] = None

class PredictionResponse(BaseModel):
    similarCases: List[Dict[str, Any]]
    predictions: Dict[str, str]
    rcaSuggestion: str

    class Config:
        # 允许额外字段，避免验证错误
        extra = "allow"
        # 自动将蛇形命名转换为驼峰命名(snake_case -> camelCase)
        alias_generator = lambda string: ''.join(
            word.capitalize() if i > 0 else word
            for i, word in enumerate(string.split('_'))
        )

# Initialize vector retrieval system
vector_search = VectorSearch()

@app.post("/predict", response_model=PredictionResponse)
async def predict_fields(request: PredictionRequest):
    """Predict fields and return similar cases based on key ticket information"""
    try:
        # 记录请求信息
        description_preview = request.description[:100] + "..." if len(request.description) > 100 else request.description
        logging.info(f"收到prediction请求，描述: {description_preview}")
        logging.info(f"历史案例数量: {len(request.historical_cases)}")
        
        if request.new_case:
            subject = request.new_case.get('Subject', '无标题')
            logging.info(f"新案例信息: {subject}")
            
        # 确保至少有一个历史案例
        if not request.historical_cases:
            logging.error("没有提供历史案例")
            raise HTTPException(status_code=400, detail="At least one historical case is required to build the index")
        
        # 检查并清理历史案例数据
        cleaned_cases = []
        for case in request.historical_cases:
            if case is None:
                continue
                
            # 确保所有必要字段都有默认值
            cleaned_case = {
                'ID': case.get('ID', 'Unknown'),
                'CaseNumber': case.get('CaseNumber', case.get('ID', 'Unknown')),
                'Subject': case.get('Subject', ''),
                'Summary': case.get('Summary', case.get('Subject', '')),
                'Description': case.get('Description', ''),
                'Category': case.get('Category', ''),
                'CategoryName': case.get('CategoryName', case.get('Category', '')),
                'Task': case.get('Task', ''),
                'TaskName': case.get('TaskName', case.get('Task', '')),
                'Priority': case.get('Priority', ''),
                'DefectPhase': case.get('DefectPhase', ''),
                'RCAReport': case.get('RCAReport', '')
            }
            
            # 添加清理后的案例
            cleaned_cases.append(cleaned_case)
            
        # 检查历史案例中是否有RCAReport
        has_rca = any(bool(case.get('RCAReport')) for case in cleaned_cases)
        if not has_rca:
            logging.error("历史案例中没有含有RCAReport的案例")
            
        # 记录一些历史案例信息
        for i, case in enumerate(cleaned_cases[:3]):
            case_id = case.get('ID', 'Unknown')
            has_rca = bool(case.get('RCAReport'))
            rca_length = len(case.get('RCAReport', '')) if case.get('RCAReport') else 0
            logging.info(f"历史案例 {i+1}: ID={case_id}, 有RCA={has_rca}, RCA长度={rca_length}")
        
        # 使用历史案例构建索引(只处理包含RCAReport的案例)
        try:
            logging.info("开始构建向量索引")
            vector_search.build_index(cleaned_cases)
            logging.info("向量索引构建完成")
        except ValueError as e:
            logging.error(f"构建索引失败: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        
        # 构建查询字符串，专注于关键字段
        query_parts = []
        
        # 如果提供了完整的新案例对象，专注于关键字段
        if request.new_case:
            # 来自表单的关键字段
            priority_fields = ["Summary", "Description"]  # 最高优先级
            important_fields = ["Category", "Task", "Priority", "PREFERENCE", "DefectPhase"]
            
            # 首先添加高优先级字段
            for field in priority_fields:
                if field in request.new_case and request.new_case[field]:
                    query_parts.append(f"{field}: {request.new_case[field]}")
            
            # 添加其他重要字段
            for field in important_fields:
                if field in request.new_case and request.new_case[field]:
                    query_parts.append(f"{field}: {request.new_case[field]}")
        
        # 始终包含description字段(如果尚未添加)
        if not any(part.startswith("Description:") for part in query_parts):
            query_parts.append(f"Description: {request.description}")
        
        # 组合查询字符串
        query = " ".join(query_parts)
        query_preview = query[:100] + "..." if len(query) > 100 else query
        logging.info(f"生成查询字符串: {query_preview}")
        
        # 搜索相似案例
        logging.info("开始搜索相似案例")
        similar_cases = vector_search.search(query)
        logging.info(f"搜索完成，找到 {len(similar_cases)} 个相似案例")
        
        # 构建提示
        logging.info("开始构建GPT提示")
        prompt = "Based on the following similar historical cases, please analyze the new ticket:\n\n"
        
        # 防止列表为空
        if not similar_cases:
            logging.warning("没有找到相似案例，将生成基本推荐")
            prompt += "No similar cases found. Providing basic recommendation.\n\n"
        else:
            for i, (case, similarity) in enumerate(similar_cases[:3], 1):
                if not case:
                    logging.warning(f"案例 {i} 是None，跳过")
                    continue
                    
                # 添加CaseNumber作为标识符
                case_id = case.get('CaseNumber') or case.get('ID', 'Unknown')
                prompt += f"Case {i} (ID: {case_id}, Similarity: {(1-similarity)*100:.1f}%):\n"
                
                # 添加关键字段
                for field in ["Subject", "Description", "Category", "CategoryName", "Task", "TaskName", "Priority", "DefectPhase"]:
                    if field in case and case[field]:
                        # 截断描述以提高可读性
                        field_value = case[field]
                        if field == "Description" and field_value and len(field_value) > 200:
                            prompt += f"{field}: {field_value[:200]}...\n"
                        else:
                            prompt += f"{field}: {field_value}\n"
                
                # 提取RCA报告中的Root Causes部分
                if case.get('RCAReport'):
                    rca_text = case['RCAReport']
                    
                    # 尝试提取Root Causes部分，如果有的话
                    root_causes = re.search(r"Root Causes\s*[:\n]+(.*?)(?=(##|\Z|#\s+))", rca_text, re.DOTALL | re.IGNORECASE)
                    if root_causes:
                        root_causes_text = root_causes.group(1).strip()
                        # 尝试提取列表项
                        root_causes_items = re.findall(r'[-•*]\s*(.*?)(?=\n[-•*]|\n\n|\Z)', root_causes_text, re.DOTALL)
                        if root_causes_items:
                            prompt += "Root Causes:\n"
                            for item in root_causes_items:
                                prompt += f"- {item.strip()}\n"
                        else:
                            prompt += f"Root Causes: {root_causes_text}\n"
                
                prompt += "\n"
        
        # 添加新案例信息
        prompt += "New Ticket Information:\n"
        if request.new_case:
            # 添加新案例中的关键字段
            key_fields = ["Summary", "Description", "Category", "Task", "Priority", "DefectPhase"]
            for field in key_fields:
                if field in request.new_case and request.new_case[field]:
                    prompt += f"{field}: {request.new_case[field]}\n"
        else:
            prompt += f"Description: {request.description}\n"
        
        prompt += "\n"
        
        # 请求预测
        prompt += "Based on the above information, please predict the following fields of the new ticket:\n"
        prompt += "1. Module: (The module/category this issue belongs to)\n"
        prompt += "2. Priority: (The urgency of this issue - High, Medium, Low)\n"
        prompt += "3. Severity: (The impact level - 1-Critical, 2-Major, 3-Minor)\n"
        
        # 调用OpenAI进行预测
        logging.info("调用OpenAI生成预测")
        try:
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a professional IT issue analysis expert. Please reply in English to avoid coding issues."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            # 解析预测结果
            predictions_text = response.choices[0].message.content
            logging.info(f"收到OpenAI预测响应，长度: {len(predictions_text)}")
            predictions = {}
            for line in predictions_text.split('\n'):
                if ':' in line:
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        key, value = parts
                        # 清理键名
                        clean_key = key.strip()
                        # 删除数字和点
                        clean_key = ''.join([c for c in clean_key if not (c.isdigit() or c == '.')])
                        clean_key = clean_key.strip()
                        if clean_key and value.strip():
                            predictions[clean_key] = value.strip()
            
            logging.info(f"解析出的预测: {predictions}")
        except Exception as e:
            logging.error(f"预测生成失败: {str(e)}")
            predictions = {
                "Module": "Unable to predict",
                "Priority": "Unable to predict",
                "Severity": "Unable to predict"
            }
        
        # 构建RCA建议请求，专注于关键方面
        rca_prompt = "Based on the following similar cases, please provide a root cause analysis for the new ticket:\n\n"
        
        # 首先添加新工单信息，给予最高优先级
        rca_prompt += "New Ticket Information:\n"
        new_case_text = ""
        if request.new_case:
            # 突出关键字段：Summary和Description
            if request.new_case.get("Summary"):
                new_case_text += f"Summary: {request.new_case['Summary']}\n"
            
            if request.new_case.get("Description"):
                new_case_text += f"Description: {request.new_case['Description']}\n"
            
            # 添加其他有用字段
            for field in ["Category", "Task", "Priority", "DefectPhase"]:
                if field in request.new_case and request.new_case[field]:
                    new_case_text += f"{field}: {request.new_case[field]}\n"
        else:
            new_case_text += f"Description: {request.description}\n"
        
        rca_prompt += new_case_text + "\n"
        
        # 使用匹配的历史案例来增强分析
        rca_prompt += "Similar Historical Cases to the New Ticket:\n\n"
        
        if not similar_cases:
            rca_prompt += "No similar cases found. Providing general analysis.\n\n"
        else:
            for i, (case, similarity) in enumerate(similar_cases[:2], 1):
                if not case:
                    continue
                    
                # 添加案例标识符
                case_id = case.get('CaseNumber') or case.get('ID', 'Unknown')
                rca_prompt += f"Case {i} (ID: {case_id}, Similarity: {(1-similarity)*100:.1f}%):\n"
                
                # 添加关键字段
                if case.get('Subject'):
                    rca_prompt += f"Subject: {case['Subject']}\n"
                    
                if case.get('Description'):
                    # 添加简短描述
                    desc = case['Description']
                    desc_summary = desc[:100] + "..." if len(desc) > 100 else desc
                    rca_prompt += f"Brief Description: {desc_summary}\n"
                
                # 提取并包含RCA报告的关键部分
                if case.get('RCAReport'):
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
                    
                    # 优先展示Root Causes和Resolution部分
                    if key_sections['Root Causes']:
                        rca_prompt += f"Root Causes:\n{key_sections['Root Causes']}\n\n"
                        
                    if key_sections['Resolution']:
                        rca_prompt += f"Resolution:\n{key_sections['Resolution']}\n\n"
                    
                    # 展示Conclusion部分
                    if key_sections['Conclusion']:
                        rca_prompt += f"Conclusion:\n{key_sections['Conclusion']}\n\n"
                    
                    # 如果前面三个主要部分都没有，则展示所有找到的部分
                    if not (key_sections['Root Causes'] or key_sections['Resolution'] or key_sections['Conclusion']):
                        sections_found = 0
                        for section, content in key_sections.items():
                            if content:
                                sections_found += 1
                                clean_section = re.sub(r'^\d+\.\s*', '', section)
                                rca_prompt += f"{clean_section}:\n{content[:150]}...\n\n"
                                
                                # 限制展示的部分数量，避免过长
                                if sections_found >= 3:
                                    break
                    
                    # 如果没有找到任何部分，使用整个报告的摘要
                    if not any(key_sections.values()):
                        summary = rca_text[:300] + "..." if len(rca_text) > 300 else rca_text
                        rca_prompt += f"RCA Summary:\n{summary}\n\n"
                
                rca_prompt += "\n"
        
        rca_prompt += "Please provide a comprehensive root cause analysis for the new ticket, including:\n"
        rca_prompt += "1. Possible root causes\n"
        rca_prompt += "2. Suggested investigation steps\n"
        rca_prompt += "3. Potential solutions\n"
        rca_prompt += "Please use concise and clear English to answer, to avoid coding issues. Organize your answer according to the above three points and maintain professionalism."
        
        # 调用OpenAI生成RCA建议
        logging.info("调用OpenAI生成RCA建议")
        try:
            rca_response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional RCA analysis expert. Please reply in English to avoid coding issues."},
                    {"role": "user", "content": rca_prompt}
                ],
                temperature=0.5
            )
            rcaSuggestionText = rca_response.choices[0].message.content
            logging.info(f"RCA建议生成成功，长度: {len(rcaSuggestionText)}")
        except Exception as e:
            logging.error(f"OpenAI API调用失败: {str(e)}")
            rcaSuggestionText = "Failed to generate RCA suggestion due to an error."
        
        # 为前端准备案例数据，专注于关键字段
        frontend_cases = []
        for case, similarity in similar_cases[:3]:
            if not case:
                continue
                
            # 安全地获取字段值，并应用默认值
            description = case.get('Description', '')
            description_preview = description[:200] + '...' if description and len(description) > 200 else description
            
            frontend_case = {
                'id': case.get('ID', 'Unknown'),
                'caseNumber': case.get('CaseNumber', case.get('ID', 'Unknown')),
                'subject': case.get('Subject', ''),
                'summary': case.get('Summary', case.get('Subject', '')),
                'description': description_preview,
                'category': case.get('Category', ''),
                'categoryName': case.get('CategoryName', case.get('Category', '')), 
                'task': case.get('Task', ''),
                'taskName': case.get('TaskName', case.get('Task', '')),
                'priority': case.get('Priority', ''),
                'defectPhase': case.get('DefectPhase', ''),
                'similarity': (1-similarity)*100  # 转换为百分比
            }
            frontend_cases.append(frontend_case)
        
        # 构建最终响应
        logging.info("构建最终响应")
        
        # 用于调试:记录数据结构
        logging.info(f"相似案例数: {len(frontend_cases)}")
        logging.info(f"预测字段数: {len(predictions) if predictions else 0}")
        
        # 确保响应格式正确,检查frontend_cases是否为预期的对象数组
        if frontend_cases and isinstance(frontend_cases, list):
            sample_case = frontend_cases[0] if frontend_cases else None
            logging.info(f"样例案例类型: {type(sample_case)}")
            if sample_case:
                logging.info(f"样例案例键: {sample_case.keys() if hasattr(sample_case, 'keys') else 'No keys method'}")
        
        # 采用简单的字典结构返回数据,避免Pydantic模型序列化问题
        response_data = {
            "similarCases": frontend_cases,
            "predictions": predictions if predictions else {},
            "rcaSuggestion": rcaSuggestionText
        }
        
        # 记录整个响应结构
        logging.info(f"响应类型: {type(response_data)}")
        logging.info(f"响应结构: {str(response_data)[:500]}...")
        
        # 直接返回字典,让FastAPI自动序列化为JSON
        return response_data
        
    except Exception as e:
        logging.error(f"预测失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

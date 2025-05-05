from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Union
import openai
import os
import json
import copy
import re
from typing import Union
import logging,time
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv('.env')

# 读取 OpenAI API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Missing OpenAI API Key. Set OPENAI_API_KEY in .env file or as an environment variable.")

app = FastAPI()

# Load prompt from external file
def load_prompt():
    with open("prompt_template1.md", "r", encoding="utf-8") as file:
        return file.read()
PROMPT_TEMPLATE = load_prompt()

# 初始化 session_store 用于存储 RCA 轮询会话数据
session_store = {}
# session_store需要设置定时清理，更新还是清空？不然会内溢出？
# 如果项目有机会上线，我需要在每次session——store[session_id]清理之前/或者是session_store清空之前，保存到库中，用于上线之后的debug

# Define data model based on the prompt structure
class DynamicField(BaseModel):
    key: str
    type: str  # "string" or "array"
    value: Union[str, List[str]] = "TBD"  # Default placeholder value
    is_confirmed: bool = False

class ImpactAnalysis(BaseModel):
    affected_module: str = "Unknown"
    severity: str = "Severity 1"
    priority: str = "Medium"  # 更新默认值与前端保持一致
    defect_phase: str = "Unknown"  # 更新默认值与前端保持一致
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
    category: str  # 替换 issue_title
    task: str  # 新增字段
    summary: str  # 替换 issue_summary
    description: str  # 新增字段
    root_causes: List[str]
    conclusion: str
    impact_analysis: ImpactAnalysis
    resolution: Resolution
    preventive_measures: PreventiveMeasures
    supplementary_info: SupplementaryInfo
    additional_questions: AdditionalQuestions
    is_final: bool  # Determines if this is the final iteration

class RCAResponse(BaseModel):
    category: str  # 替换 issue_title
    task: str  # 新增字段
    summary: str  # 替换 issue_summary
    description: str  # 新增字段
    root_causes: List[str]
    conclusion: str
    impact_analysis: ImpactAnalysis
    resolution: Resolution
    supplementary_info: SupplementaryInfo
    preventive_measures: PreventiveMeasures
    additional_questions: AdditionalQuestions
    
def process_rca_data(session_data, new_data):
    """
    处理 RCA 数据：
    - 1️⃣ **合并 session_data 和 new_data**
    - 2️⃣ **过滤 dynamic_fields 只保留 is_confirmed=True**
    - 3️⃣ **确保所有字段符合 RCAResponse 结构**
    """
    required_keys = {
        "category": "",  # 替换 issue_title
        "task": "",  # 新增字段
        "summary": "",  # 替换 issue_summary
        "description": "",  # 新增字段
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
        # **确保 session_data 里所有 key 存在**
        if key not in session_data:
            session_data[key] = default_value

        # **获取新数据的值**
        new_value = new_data.get(key, default_value)

        # **如果 key 是 dynamic_fields，合并并过滤 is_confirmed=False 的项**
        if isinstance(new_value, dict) and "dynamic_fields" in new_value:
            existing_fields = session_data[key].get("dynamic_fields", [])
            new_fields = new_value["dynamic_fields"]
            field_dict = {field["key"]: field for field in existing_fields}

            for field in new_fields:
                if field["is_confirmed"]:
                    field_dict[field["key"]] = field  # **更新或新增字段**

            session_data[key]["dynamic_fields"] = list(field_dict.values())

        # **如果是列表，合并**
        elif isinstance(new_value, list):
            session_data[key].extend(new_value)

            # **确保 root_causes 只包含字符串**
            if key == "root_causes":
                session_data[key] = [str(item) if isinstance(item, dict) else item for item in session_data[key]]

        # **如果是字典，递归合并**
        elif isinstance(new_value, dict):
            session_data[key] = process_rca_data(session_data[key], new_value)

        # **普通字段（字符串、布尔值等），直接覆盖**
        else:
            session_data[key] = new_value

    return session_data


def ensure_complete_rca_request(rca_request: RCARequest) -> RCARequest:
    """
    确保 `RCARequest` 所有字段都有默认值，防止 KeyError
    """
    return RCARequest(
        session_id=rca_request.session_id,
        category=rca_request.category or "",  # 替换 issue_title
        task=rca_request.task or "",  # 新增字段
        summary=rca_request.summary or "",  # 替换 issue_summary
        description=rca_request.description or "",  # 新增字段
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
    解析 OpenAI 返回的 JSON，去除 Markdown 代码块，并确保格式正确。
    """
    json_match = re.search(r"```json\s*([\s\S]*?)\s*```", text)
    if json_match:
        return json_match.group(1)  # **提取 JSON 部分**
    return text  # **如果没有 Markdown 代码块，返回原始内容**

# 设置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

@app.post("/refine_rca", response_model=Union[RCAResponse, dict])
def refine_rca(rca_request: RCARequest) -> Union[RCAResponse, dict]:
    """Processes issue report and calls OpenAI to refine it."""
    session_id = rca_request.session_id
    
    logging.info(f"Received request for session_id: {session_id}")

    start_time = time.time()  # 记录开始时间
    
    # **如果 is_final=True，清空 session 并返回成功**
    if rca_request.is_final:
        if session_id in session_store:
            del session_store[session_id]  # **清空 session**
        logging.info(f"Session {session_id} cleared. Returning success.")

        return {"status": "success"}  # **只返回成功状态**
    
    rca_request = ensure_complete_rca_request(rca_request)

    
    # **初始化 session_store**
    if session_id not in session_store:
        session_store[session_id] = {
            "is_first_request": True,
            "context": [  # **直接存储对话历史**
                {"role": "system", "content": PROMPT_TEMPLATE}  # **只添加一次 system 角色**
            ]
        }

    last_response_time = time.time()
    logging.info(f"Session store prepared. Time taken: {last_response_time - start_time:.3f}s")
    

    # **优化 session_store 大小**
    if len(session_store[session_id]["context"]) > 10:
        session_store[session_id]["context"] = session_store[session_id]["context"][-10:]  # 只保留最近 10 条消息

    current_session_data = session_store[session_id]["context"][-1]["content"]
    try:
        current_session_data = json.loads(current_session_data)
    except json.JSONDecodeError:
        logging.warning(f"Failed to decode JSON for session {session_id}, resetting session context.")
        session_store[session_id]["context"] = [{"role": "system", "content": PROMPT_TEMPLATE}]
        current_session_data = {}

    logging.info(f"Processing RCA data for session {session_id}")
    current_session_data = process_rca_data(current_session_data, rca_request.model_dump())


    # # **创建 RCA 副本（从 `context` 里获取上次的 assistant 响应）**
    # last_assistant_response = (
    #     session_store[session_id]["context"][-1]["content"]
    #     if len(session_store[session_id]["context"]) > 1
    #     else "{}"  # **如果没有历史数据，使用空 JSON**
    # )
    
    # current_session_data = json.loads(last_assistant_response)
    
    # logging.info(f"Processing RCA data for session {session_id}")

    # # **合并 & 过滤新请求的数据**
    # current_session_data = process_rca_data(current_session_data, rca_request.model_dump())


    # **构造 OpenAI 消息**
    session_store[session_id]["context"].append(
        {"role": "user", "content": json.dumps(current_session_data, indent=2)}
    )
    
    logging.info(f"Calling OpenAI API for session {session_id}")

    # **调用 OpenAI API**
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

    # **处理 OpenAI 响应**
    assistant_response = response.choices[0].message.content
    processed_text = extract_json_from_response(assistant_response)

    try:
        response_data = json.loads(processed_text.strip())
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse JSON response: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to parse response: {str(e)}")
    
    # **将 OpenAI 响应保存到 session_store**
    session_store[session_id]["context"].append(
        {"role": "assistant", "content": json.dumps(response_data, indent=2)}
    )

    # **记录响应时间**
    logging.info(f"Total processing time: {time.time() - start_time:.3f}s")
    
    # **返回结构化数据**
    return response_data

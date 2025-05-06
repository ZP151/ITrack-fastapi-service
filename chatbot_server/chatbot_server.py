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
    """
    加载提示词模板。
    """
    try:
        with open("prompt_template1.md", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Error loading prompt template: {e}")
        return ""

# 加载最终RCA报告提示词模板        
def load_final_rca_template():
    """
    加载最终RCA报告提示词模板。
    """
    try:
        with open("final_rca_template.md", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Error loading final RCA template: {e}")
        return ""
        
PROMPT_TEMPLATE = load_prompt()
FINAL_RCA_TEMPLATE = load_final_rca_template()

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
    
    # **如果 is_final=True，生成最终RCA报告**
    if rca_request.is_final:
        logging.info(f"Final request received for session_id: {session_id}. Generating RCA report.")
        
        # 确保请求数据完整
        rca_request = ensure_complete_rca_request(rca_request)
        
        # 构造请求数据
        rca_data = rca_request.model_dump()
        
        # 不再严格过滤dynamic_fields，保留更多信息供AI分析
        # 只是标记哪些是已确认的，让AI自行决定如何使用这些数据
        for section in ["impact_analysis", "resolution", "preventive_measures", "supplementary_info"]:
            if section in rca_data and "dynamic_fields" in rca_data[section]:
                # 添加一个标记，表示该字段是否已被确认
                for field in rca_data[section]["dynamic_fields"]:
                    if not field.get("is_confirmed", False):
                        field["ai_note"] = "This field is not confirmed by user but may contain valuable information"
        
        # 调用OpenAI生成最终报告
        try:
            logging.info("Calling OpenAI API to generate final RCA report")
            openai.api_key = OPENAI_API_KEY
            
            # 构造消息
            messages = [
                {"role": "system", "content": FINAL_RCA_TEMPLATE},
                {"role": "user", "content": json.dumps(rca_data, indent=2)}
            ]
            
            # 调用API - 增加温度和最大token以允许更创造性和详细的内容生成
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.5,  # 提高温度以增加创造性
                max_tokens=3000   # 增加最大token数以允许更详细的报告
            )
            
            # 获取报告内容
            rca_report = response.choices[0].message.content.strip()
            
            # 明确替换任何中文字符，特别是"无"
            rca_report = rca_report.replace("无", "N/A")
            
            # 使用正则表达式替换任何其他中文字符
            rca_report = re.sub(r'[\u4e00-\u9fff]', 'N/A', rca_report)
            
            # 处理空结论情况 - 如果结论中只有"None"或"N/A"，添加生成新结论的提示
            if "## 7. Conclusion\nNone" in rca_report or "## 7. Conclusion\nN/A" in rca_report:
                # 提取报告内容作为上下文
                report_context = rca_report
                
                # 创建请求以生成完整结论
                conclusion_messages = [
                    {"role": "system", "content": "You are an AI that creates detailed conclusions for Root Cause Analysis reports. Given the RCA report content, generate a comprehensive conclusion that summarizes the findings, impact, root causes, resolutions, and preventive measures. The conclusion should be professional and actionable."},
                    {"role": "user", "content": f"Based on this Root Cause Analysis report, generate a comprehensive conclusion paragraph:\n\n{report_context}"}
                ]
                
                # 调用API生成结论
                conclusion_response = openai.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=conclusion_messages,
                    temperature=0.4,
                    max_tokens=500
                )
                
                # 获取结论内容并替换原结论
                new_conclusion = conclusion_response.choices[0].message.content.strip()
                rca_report = rca_report.replace("## 7. Conclusion\nNone", f"## 7. Conclusion\n{new_conclusion}")
                rca_report = rca_report.replace("## 7. Conclusion\nN/A", f"## 7. Conclusion\n{new_conclusion}")
            
            # 清空session
            if session_id in session_store:
                del session_store[session_id]
                
            logging.info(f"RCA report generated successfully for session {session_id}")
            
            # 返回包含完整报告的响应
            return {
                "status": "success",
                "rca_report": rca_report,
                "data": rca_data  # 同时返回原始数据供前端使用
            }
            
        except Exception as e:
            logging.error(f"Error generating RCA report: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error generating RCA report: {str(e)}")
    
    # 非最终请求的处理逻辑保持不变
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

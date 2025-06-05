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
import asyncio
from dotenv import load_dotenv
from vector_utils import VectorSearch
from openai import AsyncOpenAI

# Load the .env file
load_dotenv('.env')

# Read the OpenAI API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Missing OpenAI API Key. Set OPENAI_API_KEY in .env file or as an environment variable.")

# Creating an OpenAI Asynchronous Client
async_openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# FastAPI app with optimized settings for concurrent processing
app = FastAPI(
    title="ITrack AI Service",
    description="AI-powered ticket analysis and recommendation service",
    version="1.0.0"
)

# Configure logging to track concurrent requests
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - [%(name)s] - %(message)s"
)
logger = logging.getLogger("chatbot_server")

# Adding a request counter to track concurrency
concurrent_requests = {
    "predict": 0,
    "search": 0,
    "total": 0
}

# Load prompt from external file
def load_refine_desc_prompt():
    """
    Load the refine description prompt template.
    """
    try:
        with open("refine_desc_prompt_template.md", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Error loading refine description prompt template: {e}")
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
        
REFINE_DESC_PROMPT_TEMPLATE = load_refine_desc_prompt()
FINAL_RCA_TEMPLATE = load_final_rca_template()

# Initialize session_store to store RCA polling session data
session_store = {}
# session_store need to be set up to be cleaned up regularly, updated or emptied
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
    - 1️ **Merge session_data and new_data**
    - 2️ **Filter dynamic_fields to only keep is_confirmed=True**
    - 3️ **Ensure all fields conform to the RCAResponse structure**
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

@app.post("/refine_rca", response_model=Union[RCAResponse, dict])
async def refine_rca(rca_request: RCARequest) -> Union[RCAResponse, dict]:
    """Processes issue report and calls OpenAI to refine it."""
    session_id = rca_request.session_id
    
    logger.info(f"Received request for session_id: {session_id}")

    start_time = time.time()  # record start time
    
    # **If is_final=True, generate the final RCA report**
    if rca_request.is_final:
        logger.info(f"Final request received for session_id: {session_id}. Generating RCA report.")
        
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
            logger.info("Calling OpenAI API to generate final RCA report")
            
            # Construct messages
            messages = [
                {"role": "system", "content": FINAL_RCA_TEMPLATE},
                {"role": "user", "content": json.dumps(rca_data, indent=2)}
            ]
            
            # Call API - Increase temperature and maximum tokens to allow more creative and detailed content generation
            response = await async_openai_client.chat.completions.create(
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
                conclusion_response = await async_openai_client.chat.completions.create(
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
                
            logger.info(f"RCA report generated successfully for session {session_id}")
            
            # Returns a response containing a complete report
            return {
            "status": "success",
            "rca_report": rca_report,# Returns a complete RCA report as formatted markdown string
            "data": rca_data # Also returns raw data for possible use by the front end
            }
            
        except Exception as e:
            logger.error(f"Error generating RCA report: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error generating RCA report: {str(e)}")
    
    # The processing logic for non-final requests remains unchanged
    rca_request = ensure_complete_rca_request(rca_request)
    
    # **Initialize session_store**
    if session_id not in session_store:
        session_store[session_id] = {
            "is_first_request": True,
            "context": [  # **Store conversation history directly**
                {"role": "system", "content": REFINE_DESC_PROMPT_TEMPLATE}  # **Only add system role once**
            ]
        }

    last_response_time = time.time()
    logger.info(f"Session store prepared. Time taken: {last_response_time - start_time:.3f}s")
    

    # **Optimize session_store size**# Only keep the last 10 messages
    if len(session_store[session_id]["context"]) > 10:
        session_store[session_id]["context"] = session_store[session_id]["context"][-10:]  

    current_session_data = session_store[session_id]["context"][-1]["content"]
    try:
        current_session_data = json.loads(current_session_data)
    except json.JSONDecodeError:
        logger.warning(f"Failed to decode JSON for session {session_id}, resetting session context.")
        session_store[session_id]["context"] = [{"role": "system", "content": REFINE_DESC_PROMPT_TEMPLATE}]
        current_session_data = {}

    logger.info(f"Processing RCA data for session {session_id}")
    current_session_data = process_rca_data(current_session_data, rca_request.model_dump())

    # **Construct OpenAI messages**
    session_store[session_id]["context"].append(
        {"role": "user", "content": json.dumps(current_session_data, indent=2)}
    )
    
    logger.info(f"Calling OpenAI API for session {session_id}")

    # **Call OpenAI API**
    try:
        response = await async_openai_client.chat.completions.create(
            model="gpt-3.5-turbo",  
            messages=session_store[session_id]["context"],
            temperature=0.5,
            max_tokens=1000
        )
    except Exception as e:
        logger.error(f"OpenAI API error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OpenAI API error: {str(e)}")

    call_time = time.time()
    logger.info(f"OpenAI API call completed in {call_time - last_response_time:.3f}s")
    last_response_time = call_time

    # **Process OpenAI response**
    assistant_response = response.choices[0].message.content
    processed_text = extract_json_from_response(assistant_response)

    try:
        response_data = json.loads(processed_text.strip())
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to parse response: {str(e)}")
    
    # **Save OpenAI response to session_store**
    session_store[session_id]["context"].append(
        {"role": "assistant", "content": json.dumps(response_data, indent=2)}
    )

    # **Record response time**
    logger.info(f"Total processing time: {time.time() - start_time:.3f}s")
    
    # **Return structured data**
    return response_data

class PredictionRequest(BaseModel):
    description: str
    historical_cases: List[dict]
    new_case: Optional[dict] = None

class PredictionResponse(BaseModel):
    predictions: Dict[str, str]
    rcaSuggestion: str

class SearchResponse(BaseModel):
    similarCases: List[Dict[str, Any]]

# Initialize vector retrieval system
vector_search = VectorSearch()

@app.post("/predict")
async def predict(request: PredictionRequest):
    """Only predict fields and return RCA suggestions"""
    # Increase the concurrency counter
    concurrent_requests["predict"] += 1
    concurrent_requests["total"] += 1
    request_start_time = time.time()
    
    logger.info(f"[PREDICT] Starting request processing (concurrency: predict={concurrent_requests['predict']}, total={concurrent_requests['total']})")
    
    try:
        # Parse the request body
        description = request.description
        new_case = request.new_case
        historical_cases = request.historical_cases
        
        # Record request information
        description_preview = description[:100] + "..." if len(description) > 100 else description
        logger.info(f"[PREDICT] Received prediction request, description: {description_preview}")
        
        # Check and clean data
        if not historical_cases:
            logger.warning("[PREDICT] No historical cases provided")
        
        # Build the prompt
        prompt = "Based on the following information, please predict the fields of the new ticket:\n\n"
        
        # Add new case information
        prompt += "New Ticket Information:\n"
        if new_case:
            # Add key fields from the new case
            key_fields = ["Summary", "Description", "Category", "Task", "Priority", "DefectPhase"]
            for field in key_fields:
                if field in new_case and new_case[field]:
                    prompt += f"{field}: {new_case[field]}\n"
        else:
            prompt += f"Description: {description}\n"
        
        prompt += "\n"
        
        # Request prediction
        prompt += "Based on the above information, please predict the following fields of the new ticket:\n"
        prompt += "1. Module: (The module/category this issue belongs to)\n"
        prompt += "2. Priority: (The urgency of this issue - High, Medium, Low)\n"
        prompt += "3. Severity: (The impact level - Severity 1, Severity 2, Severity 3)\n"
        
        # Parallel call OpenAI API for prediction and RCA suggestion generation
        logger.info("[PREDICT] Parallel call OpenAI to generate prediction and RCA suggestion")
        try:
            # Create parallel tasks
            prediction_task = async_openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional IT issue analysis expert. Please reply in English to avoid coding issues."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            rca_prompt = "Based on the following information, please provide a root cause analysis for the new ticket:\n\n"
            
            # Add new ticket information
            rca_prompt += "New Ticket Information:\n"
            if new_case:
                if new_case.get("Summary"):
                    rca_prompt += f"Summary: {new_case['Summary']}\n"
                
                if new_case.get("Description"):
                    rca_prompt += f"Description: {new_case['Description']}\n"
                
                # Add other useful fields
                for field in ["Category", "Task", "Priority", "DefectPhase"]:
                    if field in new_case and new_case[field]:
                        rca_prompt += f"{field}: {new_case[field]}\n"
            else:
                rca_prompt += f"Description: {description}\n"
            
            rca_prompt += "\n"
            rca_prompt += "Please provide a comprehensive root cause analysis for this ticket, including:\n"
            rca_prompt += "1. Possible root causes\n"
            rca_prompt += "2. Suggested investigation steps\n"
            rca_prompt += "3. Potential solutions\n"
            
            rca_task = async_openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional RCA analysis expert. Please reply in English to avoid coding issues."},
                    {"role": "user", "content": rca_prompt}
                ],
                temperature=0.5
            )
            
            # Wait for two tasks to complete in parallel
            prediction_response, rca_response = await asyncio.gather(prediction_task, rca_task)
            
            # Parse the prediction results
            predictions_text = prediction_response.choices[0].message.content
            logger.info(f"[PREDICT] Received OpenAI prediction response, length: {len(predictions_text)}")
            predictions = {}
            for line in predictions_text.split('\n'):
                if ':' in line:
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        key, value = parts
                        # Clean the key name
                        clean_key = key.strip()
                        # Delete numbers and dots
                        clean_key = ''.join([c for c in clean_key if not (c.isdigit() or c == '.')])
                        clean_key = clean_key.strip()
                        if clean_key and value.strip():
                            predictions[clean_key] = value.strip()
            
            logger.info(f"[PREDICT] Parsed predictions: {predictions}")
            
            # Get RCA suggestion
            rcaSuggestion = rca_response.choices[0].message.content
            logger.info(f"[PREDICT] RCA suggestion generated successfully, length: {len(rcaSuggestion)}")
            
        except Exception as e:
            logger.error(f"[PREDICT] OpenAI API call failed: {str(e)}")
            predictions = {
                "Module": "Unable to predict",
                "Priority": "Unable to predict",
                "Severity": "Unable to predict"
            }
            rcaSuggestion = "Failed to generate RCA suggestion due to an error."
        
        # Build the prediction response - only contains prediction and RCA suggestion, no similar cases
        response_data = {
            "predictions": predictions,
            "rcaSuggestion": rcaSuggestion
        }
        
        request_duration = time.time() - request_start_time
        logger.info(f"[PREDICT] Processing completed, time taken: {request_duration:.3f}s")
        return response_data
        
    except Exception as e:
        request_duration = time.time() - request_start_time
        logger.error(f"[PREDICT] Prediction failed, time taken: {request_duration:.3f}s, error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Decrease the concurrency counter
        concurrent_requests["predict"] -= 1
        concurrent_requests["total"] -= 1
        logger.info(f"[PREDICT] Request ended (concurrency: predict={concurrent_requests['predict']}, total={concurrent_requests['total']})")

# Separate endpoint for similar case search
@app.post("/search_similar_cases")
async def search_similar_cases(request: PredictionRequest):
    """Only search and return similar cases"""
    # Increase the concurrency counter
    concurrent_requests["search"] += 1
    concurrent_requests["total"] += 1
    request_start_time = time.time()
    
    logger.info(f"[SEARCH] Starting request processing (concurrency: search={concurrent_requests['search']}, total={concurrent_requests['total']})")
    
    try:
        # Parse the request body
        description = request.description
        new_case = request.new_case
        historical_cases = request.historical_cases
        
        # Record request information
        logger.info(f"[SEARCH] Received similar case search request, historical case count: {len(historical_cases)}")
        
        # Ensure at least one historical case
        if not historical_cases:
            logger.error("[SEARCH] No historical cases provided")
            raise HTTPException(status_code=400, detail="At least one historical case is required to build the index")
        
        # Check and clean historical case data
        cleaned_cases = []
        for case in historical_cases:
            if case is None:
                continue
                
            # Ensure all necessary fields have default values
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
            
            # Add cleaned case
            cleaned_cases.append(cleaned_case)
        
        # Use historical cases to build the index (only process cases containing RCAReport)
        try:
            logger.info("[SEARCH] Starting to build vector index")
            # Move CPU-intensive indexing operations to the thread pool asynchronously
            await asyncio.to_thread(vector_search.build_index, cleaned_cases)
            logger.info("[SEARCH] Vector index built successfully")
        except ValueError as e:
            logger.error(f"[SEARCH] Failed to build index: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        
        # Build the query string
        query_parts = []
        
        # If new_case is provided, focus on key fields
        if new_case:
            # Key fields from the form
            priority_fields = ["Summary", "Description"]  # Highest priority
            important_fields = ["Category", "Task", "Priority", "PREFERENCE", "DefectPhase"]
            
            # Add high priority fields first
            for field in priority_fields:
                if field in new_case and new_case[field]:
                    query_parts.append(f"{field}: {new_case[field]}")
            
            # Add other important fields
            for field in important_fields:
                if field in new_case and new_case[field]:
                    query_parts.append(f"{field}: {new_case[field]}")
        
        # Always include the description field (if not already added)
        if not any(part.startswith("Description:") for part in query_parts):
            query_parts.append(f"Description: {description}")
        
        # Combine the query string
        query = " ".join(query_parts)
        
        # Search for similar cases
        logger.info("[SEARCH] Starting to search for similar cases")
        # Move the vector search operation to the thread pool asynchronously
        similar_cases = await asyncio.to_thread(vector_search.search, query)
        logger.info(f"[SEARCH] Search completed, found {len(similar_cases)} similar cases")
        
        # Prepare case data for the frontend
        frontend_cases = []
        for case, similarity in similar_cases[:5]:  # Limit to 5
            if not case:
                continue
                
            # Safely get field values and apply default values
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
                'severity': case.get('Severity', ''),
                'PREFERENCE': case.get('PREFERENCE', ''),
                'defectPhase': case.get('DefectPhase', ''),
                'similarity': (1-similarity)*100  # 转换为百分比
            }
            frontend_cases.append(frontend_case)
        
        # Build the response - only contains similar cases
        response_data = {
            "similarCases": frontend_cases
        }
        
        request_duration = time.time() - request_start_time
        logger.info(f"[SEARCH] Processing completed, time taken: {request_duration:.3f}s")
        return response_data
        
    except Exception as e:
        request_duration = time.time() - request_start_time
        logger.error(f"[SEARCH] Similar case search failed, time taken: {request_duration:.3f}s, error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Decrease the concurrency counter
        concurrent_requests["search"] -= 1
        concurrent_requests["total"] -= 1
        logger.info(f"[SEARCH] Request ended (concurrency: search={concurrent_requests['search']}, total={concurrent_requests['total']})")
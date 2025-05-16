using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.Http;
using System.Threading.Tasks;
using System.Web;
using System.Web.Mvc;
using ChatbotMvcForm4._6.Models;
using Newtonsoft.Json.Serialization;
using System.IO;
using System.Data.Entity;

namespace ChatbotMvcForm4._6.Controllers
{
    public class HomeController : Controller
    {
        private static readonly HttpClient client = new HttpClient();
        private readonly TeBSiTrackDbContext _db = new TeBSiTrackDbContext();

        

        public ActionResult Index()
        {
            return View();
        }
        
        public async Task<ActionResult> ChatbotOptimize()
        {
            // ✅ 读取请求体 JSON 数据
            string requestBody;
            using (var reader = new StreamReader(Request.InputStream))
            {
                requestBody = await reader.ReadToEndAsync();
            }

            // ✅ 解析 JSON
            dynamic requestData;
            try
            {
                requestData = JsonConvert.DeserializeObject<dynamic>(requestBody);
            }
            catch (Exception ex)
            {
                return Json(new { error = "Invalid JSON format", details = ex.Message });
            }

            if (requestData == null)
            {
                return Json(new { error = "Invalid request" });
            }

            // ✅ 生成或获取 Session ID
            string sessionId = Session["session_id"] as string;
            if (string.IsNullOrEmpty(sessionId))
            {
                sessionId = Guid.NewGuid().ToString();
                Session["session_id"] = sessionId;
            }
            bool isFinal = requestData.isFinal != null && ((bool)requestData.isFinal);

            if (isFinal)
            {
                // 创建完整的 ChatRequest 对象，从formData中获取数据
                ChatRequest chatRequestData;
                try
                {
                    // 从请求中的formData获取数据
                    chatRequestData = JsonConvert.DeserializeObject<ChatRequest>(JsonConvert.SerializeObject(requestData.formData));
                    
                    // 设置会话ID和isFinal标志
                    chatRequestData.SessionId = sessionId;
                    chatRequestData.IsFinal = true;
                }
                catch (Exception ex)
                {
                    // 如果解析失败，使用默认值
                    chatRequestData = new ChatRequest
                    {
                        SessionId = sessionId,
                        Category = "",
                        Task = "",
                        Summary = "",
                        Description = "",
                        RootCauses = new List<string>(),
                        Conclusion = "",
                        ImpactAnalysis = new ImpactAnalysis { 
                            AffectedModule = "Unknown",
                            Severity = "Severity 1",
                            Priority = "Medium",
                            DefectPhase = "Unknown"
                        },
                        Resolution = new Resolution { FixApplied = "Not provided" },
                        PreventiveMeasures = new PreventiveMeasures { GeneralMeasure = "TBD" },
                        SupplementaryInfo = new SupplementaryInfo(),
                        AdditionalQuestions = new AdditionalQuestions(),
                        IsFinal = true
                    };
                }

                var finalContent = new StringContent(
                    JsonConvert.SerializeObject(chatRequestData),
                    System.Text.Encoding.UTF8,
                    "application/json"
                );

                // 发送到 FastAPI
                //Original local address
                var finalResponse = await client.PostAsync("http://127.0.0.1:8000/refine_rca", finalContent);

                //LAN devices can access FastAPI through IIS.
                //var finalResponse = await client.PostAsync("http://192.168.68.153/refine_rca", finalContent);

                var finalResponseString = await finalResponse.Content.ReadAsStringAsync();

                // 尝试解析响应
                try {
                    // 尝试解析为包含RCA报告的响应
                    var finalResponseData = JsonConvert.DeserializeObject<dynamic>(finalResponseString);
                    
                    if (finalResponseData != null && finalResponseData.status != null && finalResponseData.status.ToString() == "success")
                    {
                        // 检查是否包含RCA报告
                        if (finalResponseData.rca_report != null)
                        {
                            string rcaReport = finalResponseData.rca_report.ToString();
                            return Json(new { 
                                status = "success", 
                                rca_report = rcaReport,
                                data = finalResponseData.data
                            });
                        }
                        else
                        {
                            // 未包含RCA报告，返回常规成功状态
                            return Json(new { status = "success" });
                        }
                    }
                    else
                    {
                        return Json(new { error = "FastAPI did not return success status", response = finalResponseString });
                    }
                }
                catch (Exception ex)
                {
                    // 旧的处理方式，尝试解析为简单的状态消息（兼容性目的）
                    try {
                        var simpleResponseData = JsonConvert.DeserializeObject<Dictionary<string, string>>(finalResponseString);
                        if (simpleResponseData != null && simpleResponseData.TryGetValue("status", out string status) && status == "success")
                        {
                            return Json(new { status = "success" });
                        }
                    }
                    catch {}
                    
                    // 两种解析方式都失败，返回错误
                    return Json(new { error = "Failed to parse FastAPI response", details = ex.Message, response = finalResponseString });
                }
            }
            // ✅ 解析 `formData`
            ChatRequest chatRequest;
            try
            {
                chatRequest = JsonConvert.DeserializeObject<ChatRequest>(JsonConvert.SerializeObject(requestData.formData));
            }
            catch (Exception ex)
            {
                return Json(new { error = "Invalid formData format", details = ex.Message });
            }
            chatRequest.SessionId = sessionId;
            chatRequest.IsFinal = isFinal;
            // 处理 `isFinal: false`，发送完整 `chatRequest`
            var content = new StringContent(JsonConvert.SerializeObject(chatRequest), System.Text.Encoding.UTF8, "application/json");

            // 发送 POST 请求到 FastAPI 服务
            var response = await client.PostAsync("http://127.0.0.1:8000/refine_rca", content);
            //var response = await client.PostAsync("http://192.168.68.153/refine_rca", content);

            // 如果响应失败，返回错误信息
            if (!response.IsSuccessStatusCode)
            {
                var errorMessage = await response.Content.ReadAsStringAsync();
                return Json(new { error = "FastAPI returned error: " + errorMessage }   );
            }

            // Parse the response from FastAPI
            var responseString = await response.Content.ReadAsStringAsync();
            var responseData = JsonConvert.DeserializeObject<ChatResponse>(responseString);

            return Json(responseData);
        }
        public ActionResult About()
        {
            ViewBag.Message = "Your application description page.";

            return View();
        }

        public ActionResult Contact()
        {
            ViewBag.Message = "Your contact page.";

            return View();
        }


        public class PredictionResponse
        {
            public List<Dictionary<string, object>> SimilarCases { get; set; }
            public Dictionary<string, string> Predictions { get; set; }
            public string RcaSuggestion { get; set; }
        }

        // 添加一个简化的DTO类用于接收前端数据
        public class AiRecommendationRequest 
        {
            public string Description { get; set; }
            public string Summary { get; set; }
            public string Category { get; set; }
            public string Severity { get; set; }  // 接收字符串类型的Severity
            public string Priority { get; set; }  // 接收字符串类型的Priority
            public string Task { get; set; }
            public string DefectPhase { get; set; }
        }

        [HttpPost]
        public async Task<ActionResult> GetAIRecommendation(AiRecommendationRequest request)
        {
            try
            {
                // 验证请求
                if (request == null || string.IsNullOrEmpty(request.Description))
                {
                    return Json(new { error = "Description is required" });
                }
                
                System.Diagnostics.Debug.WriteLine($"开始处理AI推荐请求: {request.Description.Substring(0, Math.Min(50, request.Description.Length))}...");
                
                // 创建新工单对象，直接保持字符串类型
                var newCase = new {
                    ID = "new", 
                    Summary = request.Summary,
                    Subject = request.Summary,
                    Description = request.Description, 
                    Priority = request.Severity,    // 直接使用字符串类型的Severity
                    PREFERENCE = request.Priority,  // 直接使用字符串类型的Priority
                    Category = request.Category,
                    Task = request.Task,
                    DefectPhase = request.DefectPhase
                };
                
                System.Diagnostics.Debug.WriteLine("开始查询历史案例...");
                
                // 先从数据库获取数据
                var casesQuery = (from c in _db.Cases
                             join cat in _db.CategoryMasters on c.CategoryIDFK equals cat.ID into cj
                             from cat in cj.DefaultIfEmpty()
                             join task in _db.TaskMasters on c.TaskID equals task.ID into tj
                             from task in tj.DefaultIfEmpty()
                             where !string.IsNullOrEmpty(c.RCAReport)
                             orderby c.CreatedDate descending
                             select new {
                                 Case = c,
                                 CategoryDescr = cat != null ? cat.Descr : null,
                                 TaskDescr = task != null ? task.TaskDescription : null
                             }).Take(100).ToList();
                
                // 在内存中进行投影
                var cases = casesQuery.Select(c => new {
                    ID = c.Case.ID.ToString(),
                    CaseNumber = c.Case.ID.ToString(),
                    Subject = c.Case.Subject,
                    Summary = c.Case.Subject,
                    Description = c.Case.Description,
                    Priority = c.Case.Priority != null ? c.Case.Priority.ToString() : null,
                    PREFERENCE = c.Case.PREFERENCE != null ? c.Case.PREFERENCE.ToString() : null,
                    Category = c.Case.Category,
                    CategoryName = c.CategoryDescr ?? c.Case.Category,
                    Task = c.Case.Task,
                    TaskName = c.TaskDescr ?? c.Case.Task,
                    DefectPhase = c.Case.DefectPhase,
                    RCAReport = c.Case.RCAReport
                }).ToList();
                
                System.Diagnostics.Debug.WriteLine($"查询到{cases.Count}个历史案例");
                
                // 检查RCAReport字段是否有内容
                int casesWithRCA = cases.Count(c => !string.IsNullOrEmpty(c.RCAReport));
                System.Diagnostics.Debug.WriteLine($"其中含有RCAReport内容的案例数: {casesWithRCA}");
                
                // 显示案例ID和RCAReport长度
                foreach (var c in cases.Take(5))
                {
                    string rcaInfo = c.RCAReport != null ? 
                        $"长度:{c.RCAReport.Length}" : "null";
                    System.Diagnostics.Debug.WriteLine($"案例ID:{c.ID}, RCAReport:{rcaInfo}");
                }
                
                // 如果没有找到任何案例，返回错误
                if (!cases.Any())
                {
                    return Json(new { error = "No historical cases with RCA reports found" });
                }
                
                // 创建发送到FastAPI服务的请求对象
                var apiRequest = new {
                    description = request.Description,
                    new_case = newCase,
                    historical_cases = cases
                };
                
                var jsonRequest = JsonConvert.SerializeObject(apiRequest);
                System.Diagnostics.Debug.WriteLine($"向FastAPI发送请求，包含{jsonRequest.Length}个字符");
                
                using (var client = new HttpClient())
                {
                    // 设置超时时间为2分钟
                    client.Timeout = TimeSpan.FromMinutes(2);
                    
                    var content = new StringContent(
                        jsonRequest,
                        System.Text.Encoding.UTF8,
                        "application/json"
                    );

                    System.Diagnostics.Debug.WriteLine("开始调用FastAPI服务...");
                    
                    // 发送到FastAPI服务
                    var response = await client.PostAsync("http://127.0.0.1:8000/predict", content);
                    
                    System.Diagnostics.Debug.WriteLine($"FastAPI服务响应状态: {response.StatusCode}");
                    
                    if (!response.IsSuccessStatusCode)
                    {
                        var errorMessage = await response.Content.ReadAsStringAsync();
                        System.Diagnostics.Debug.WriteLine($"FastAPI服务返回错误: {errorMessage}");
                        return Json(new { error = "Prediction service returned an error: " + errorMessage });
                    }

                    var responseString = await response.Content.ReadAsStringAsync();
                    System.Diagnostics.Debug.WriteLine($"FastAPI服务响应内容长度: {responseString.Length}");
                    System.Diagnostics.Debug.WriteLine($"FastAPI服务响应内容前500字符: {(responseString.Length > 500 ? responseString.Substring(0, 500) + "..." : responseString)}");
                    
                    try {
                        // 直接将原始响应传递给前端，避免反序列化和再序列化过程中的问题
                        return Content(responseString, "application/json");
                    }
                    catch (Exception parseEx) {
                        System.Diagnostics.Debug.WriteLine($"解析JSON响应失败: {parseEx.Message}");
                        return Json(new { 
                            error = "Failed to parse response from prediction service", 
                            details = parseEx.Message,
                            rawResponse = responseString.Length > 1000 ? responseString.Substring(0, 1000) + "..." : responseString
                        });
                    }
                }
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"获取AI推荐失败: {ex.Message}\n{ex.StackTrace}");
                return Json(new { error = "Failed to get AI recommendation", details = ex.Message });
            }
        }

        // NewTicket page with default values
        public ActionResult NewTicket()
        {
            var model = new Case
            {
                Project = "PL-IP MTS 2019",
                Category = "General",
                Priority = 1,  // 使用数值类型
                PREFERENCE = 3,  // 使用数值类型
                Task = "General",
                DefectPhase = "Coding",
                TicketOwner = "Anand Ashish",
                Email = "ashish.a@totalebizsolutions.com",
                ContactNo = "",
                AssignedTo = "UnAssigned",
                Summary = "test",
                Description = "test",
                // 添加对应的显示名称
                PriorityName = "Severity 1",
                SeverityName = "Low"
            };
            return View(model);
        }

        // Show recent 50 tickets (list)
        public ActionResult ViewCase()
        {
            var cases = _db.Cases
                .OrderByDescending(c => c.ID)
                .Take(50)
                .ToList();
            return View("ViewCase", cases);
        }

        // 新建工单提交
        [HttpPost]
        public ActionResult NewTicket(Case model)
        {
            if (ModelState.IsValid)
            {
                // 将字符串值转换为数值 - Priority处理
                int priorityValue = 2; // 默认值
                
                // 检查PriorityName字段
                if (!string.IsNullOrEmpty(model.PriorityName))
                {
                    var match = System.Text.RegularExpressions.Regex.Match(model.PriorityName, @"Severity\s*(\d+)");
                    if (match.Success && int.TryParse(match.Groups[1].Value, out int value))
                    {
                        priorityValue = value;
                    }
                }
                // 如果Priority是int类型
                else if (model.Priority.HasValue)
                {
                    priorityValue = model.Priority.Value;
                }
                
                // 将字符串值转换为数值 - PREFERENCE处理
                int preferenceValue = 2; // 默认中等优先级
                
                // 检查SeverityName字段
                if (!string.IsNullOrEmpty(model.SeverityName))
                {
                    string lowerPref = model.SeverityName.ToLower();
                    if (lowerPref == "high")
                        preferenceValue = 1;
                    else if (lowerPref == "low")
                        preferenceValue = 3;
                    else
                        preferenceValue = 2; // Medium
                }
                // 如果PREFERENCE是int类型
                else if (model.PREFERENCE.HasValue)
                {
                    preferenceValue = model.PREFERENCE.Value;
                }
                
                // 补齐所有需要ID的字段，给默认值
                model.DepartmentIDFK = model.DepartmentIDFK.HasValue ? model.DepartmentIDFK.Value : 518;
                model.CategoryIDFK = model.CategoryIDFK.HasValue ? model.CategoryIDFK.Value : 3160;
                model.Priority = priorityValue; // 设置转换后的数值
                model.AssignedToIDFK = model.AssignedToIDFK.HasValue ? model.AssignedToIDFK.Value : 0;
                model.StatusIDFK = model.StatusIDFK.HasValue ? model.StatusIDFK.Value : 2;
                model.CreatedBy = model.TicketOwner ?? "Anand Ashish";
                model.CreatedDate = DateTime.Now;
                model.UpdatedBy = model.TicketOwner ?? "Anand Ashish";
                model.UpdatedDate = DateTime.Now;
                model.IsPrivate = false;
                model.Name = model.TicketOwner ?? "Anand Ashish";
                model.Email = model.Email ?? "ashish.a@totalebizsolutions.com";
                model.ContactNo = model.ContactNo ?? "";
                model.Summary = model.Summary ?? "";
                model.ResolutionDate = model.ResolutionDate.HasValue ? model.ResolutionDate.Value : DateTime.Now.AddMonths(5);
                model.Environment = model.Environment.HasValue ? model.Environment.Value : 546;
                model.TaskID = model.TaskID.HasValue ? model.TaskID.Value : 14;
                model.PREFERENCE = preferenceValue; // 设置转换后的数值
                model.DefectPhaseID = model.DefectPhaseID.HasValue ? model.DefectPhaseID.Value : 27;
                model.RCAID = model.RCAID.HasValue ? model.RCAID.Value : 0;
                model.caselinked = model.LinkedTickets ?? "";
                model.RCAReport = model.RCAReport ?? "";
                model.CaseNumber = model.CaseNumber ?? ("T" + DateTime.Now.ToString("yyMMddHHmmss"));
                model.AdditionInformation = model.AdditionInformation ?? "";
                model.Subject = model.Summary ?? "";
                // 非数据库字段不参与保存
                _db.Cases.Add(model);
                _db.SaveChanges();
                return RedirectToAction("Index");
            }
            return View(model);
        }

        // 编辑工单页面
        public ActionResult EditCase(int id)
        {
            var model = _db.Cases.Find(id);
            if (model == null) return HttpNotFound();
            // 补齐默认值
            model.Project = model.Project ?? "PL-IP MTS 2019";
            model.Category = model.Category ?? "General";
            
            // 数值转换为字符串
            if (model.Priority.HasValue)
            {
                // 将int?转换为字符串格式
                int priorityVal = model.Priority.Value;
                model.PriorityName = $"Severity {priorityVal}";
            }
            else
            {
                model.PriorityName = "Severity 1";
            }
            
            if (model.PREFERENCE.HasValue)
            {
                // 将int?转换为字符串格式
                int prefValue = model.PREFERENCE.Value;
                
                if (prefValue == 1)
                    model.SeverityName = "High";
                else if (prefValue == 3)
                    model.SeverityName = "Low";
                else
                    model.SeverityName = "Medium";
            }
            else
            {
                model.SeverityName = "Medium";
            }
                
            model.Task = model.Task ?? "General";
            model.DefectPhase = model.DefectPhase ?? "Coding";
            model.TicketOwner = model.TicketOwner ?? "Anand Ashish";
            model.Email = model.Email ?? "ashish.a@totalebizsolutions.com";
            model.ContactNo = model.ContactNo ?? "";
            model.AssignedTo = model.AssignedTo ?? "UnAssigned";
            model.Summary = model.Summary ?? "";
            model.Description = model.Description ?? "";
            return View(model);
        }

        [HttpPost]
        public ActionResult EditCase(Case model)
        {
            // 先获取原始数据，避免覆盖一些未在表单中显示的字段
            var originalCase = _db.Cases.Find(model.ID);
            if (originalCase == null) return HttpNotFound();
            
            // 处理状态变更
            string changeStatusTo = Request.Form["ChangeStatusTo"];
            if (!string.IsNullOrEmpty(changeStatusTo))
            {
                model.StatusIDFK = ConvertStatusToId(changeStatusTo);
            }
            
            // 将字符串值转换为数值 - Priority处理
            int priorityValue = 2; // 默认值
            
            // 检查PriorityName字段
            if (!string.IsNullOrEmpty(model.PriorityName))
            {
                var match = System.Text.RegularExpressions.Regex.Match(model.PriorityName, @"Severity\s*(\d+)");
                if (match.Success && int.TryParse(match.Groups[1].Value, out int value))
                {
                    priorityValue = value;
                }
            }
            // 如果Priority是int类型
            else if (model.Priority.HasValue)
            {
                priorityValue = model.Priority.Value;
            }
            
            // 将字符串值转换为数值 - PREFERENCE处理
            int preferenceValue = 2; // 默认中等优先级
            
            // 检查SeverityName字段
            if (!string.IsNullOrEmpty(model.SeverityName))
            {
                string lowerPref = model.SeverityName.ToLower();
                if (lowerPref == "high")
                    preferenceValue = 1;
                else if (lowerPref == "low")
                    preferenceValue = 3;
                else
                    preferenceValue = 2; // Medium
            }
            // 如果PREFERENCE是int类型
            else if (model.PREFERENCE.HasValue)
            {
                preferenceValue = model.PREFERENCE.Value;
            }
            
            // 保留原始数据中的日期和创建者信息
            model.CreatedDate = originalCase.CreatedDate;
            model.CreatedBy = originalCase.CreatedBy;
            
            // 设置转换后的数值
            model.Priority = priorityValue;
            model.PREFERENCE = preferenceValue;
            
            // 自动补齐必须字段
            model.DepartmentIDFK = model.DepartmentIDFK.HasValue ? model.DepartmentIDFK.Value : 518;
            model.CategoryIDFK = model.CategoryIDFK.HasValue ? model.CategoryIDFK.Value : 3160;
            model.StatusIDFK = model.StatusIDFK.HasValue ? model.StatusIDFK.Value : 2; // Open
            model.TaskID = model.TaskID.HasValue ? model.TaskID.Value : 14; // General
            model.DefectPhaseID = model.DefectPhaseID.HasValue ? model.DefectPhaseID.Value : 27;
            model.Environment = model.Environment.HasValue ? model.Environment.Value : 546;
            model.RCAID = model.RCAID.HasValue ? model.RCAID.Value : 0;
            model.AssignedToIDFK = model.AssignedToIDFK.HasValue ? model.AssignedToIDFK.Value : 0;
            
            // 确保有更新时间
            model.UpdatedDate = DateTime.Now;
            model.UpdatedBy = model.TicketOwner ?? "System";

            // 非空字段赋默认值
            model.Subject = model.Summary ?? model.Subject ?? "";
            model.Name = model.TicketOwner ?? originalCase.Name ?? "Anonymous";
            model.IsPrivate = model.IsPrivate ?? false;
            
            // 关联字段的处理
            model.caselinked = model.LinkedTickets ?? originalCase.caselinked ?? "";
            
            // 如果选择状态为"Closed"时设置ResolutionDate
            if (model.StatusIDFK.HasValue && model.StatusIDFK.Value == 5) // 假设5是Closed状态
            {
                model.ResolutionDate = DateTime.Now;
            }
            else
            {
                model.ResolutionDate = originalCase.ResolutionDate;
            }
            
            // 确保不丢失RCAReport数据
            if (string.IsNullOrEmpty(model.RCAReport) && !string.IsNullOrEmpty(originalCase.RCAReport))
            {
                model.RCAReport = originalCase.RCAReport;
            }
            
            if (ModelState.IsValid)
            {
                _db.Entry(originalCase).State = EntityState.Detached; // 先分离原实体
                _db.Entry(model).State = EntityState.Modified;
                _db.SaveChanges();
                return RedirectToAction("Index");
            }
            return View(model);
        }
        
        // 将状态字符串转换为ID
        private int? ConvertStatusToId(string status)
        {
            if (status == null)
                return null;
            
            if (status == "Open")
                return 2;
            else if (status == "Closed")
                return 5;
            else if (status == "In Progress")
                return 37;
            else
                return null;
        }
    }
}
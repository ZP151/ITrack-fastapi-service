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
            [JsonProperty("predictions")]
            public Dictionary<string, string> Predictions { get; set; }

            [JsonProperty("rcaSuggestion")]
            public string RcaSuggestion { get; set; }
        }
        
        public class SearchResponse
        {
            [JsonProperty("similarCases")]
            public List<Dictionary<string, object>> SimilarCases { get; set; }
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
        public async Task<ActionResult> GetPredictions(AiRecommendationRequest request)
        {
            try
            {
                // 验证请求
                if (request == null || string.IsNullOrEmpty(request.Description))
                {
                    return Json(new { error = "Description is required" });
                }
                
                System.Diagnostics.Debug.WriteLine($"开始处理AI预测请求: {request.Description.Substring(0, Math.Min(50, request.Description.Length))}...");
                
                // 准备数据 - 复用原有逻辑
                var newCase = PrepareNewCaseData(request);
                var cases = GetHistoricalCases();
                
                var apiRequest = new {
                    description = request.Description,
                    new_case = newCase,
                    historical_cases = cases
                };
                
                // 配置序列化
                var jsonSettings = new JsonSerializerSettings
                {
                    NullValueHandling = NullValueHandling.Include,
                    DefaultValueHandling = DefaultValueHandling.Include,
                    Formatting = Formatting.None,
                    ContractResolver = new DefaultContractResolver { NamingStrategy = null }
                };
                
                var jsonRequest = JsonConvert.SerializeObject(apiRequest, jsonSettings);
                
                using (var client = new HttpClient())
                {
                    client.Timeout = TimeSpan.FromMinutes(2);
                    
                    var content = new StringContent(
                        jsonRequest,
                        System.Text.Encoding.UTF8,
                        "application/json"
                    );

                    System.Diagnostics.Debug.WriteLine("开始调用FastAPI预测服务...");
                    
                    var response = await client.PostAsync(
                        "http://localhost:8000/predict",
                        content
                    );
                    
                    if (!response.IsSuccessStatusCode)
                    {
                        var error = await response.Content.ReadAsStringAsync();
                        System.Diagnostics.Debug.WriteLine($"预测服务返回错误: {error}");
                        return Json(new { error = "Prediction service returned an error", details = error });
                    }

                    var responseString = await response.Content.ReadAsStringAsync();
                    System.Diagnostics.Debug.WriteLine($"预测服务响应内容长度: {responseString.Length}");
                    
                    try {
                        var data = JsonConvert.DeserializeObject<PredictionResponse>(responseString);
                        
                        // 返回使用驼峰命名法的数据
                        return Json(new {
                            predictions = data.Predictions,
                            rcaSuggestion = data.RcaSuggestion
                        });
                    }
                    catch (Exception parseEx) {
                        System.Diagnostics.Debug.WriteLine($"解析预测JSON响应失败: {parseEx.Message}");
                        return Json(new { 
                            error = "Failed to parse response from prediction service", 
                            details = parseEx.Message,
                            response = responseString.Length > 1000 ? responseString.Substring(0, 1000) + "..." : responseString
                        });
                    }
                }
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"获取AI预测失败: {ex.Message}\n{ex.StackTrace}");
                return Json(new { error = "Failed to get AI predictions", details = ex.Message });
            }
        }
        
        [HttpPost]
        public async Task<ActionResult> GetSimilarCases(AiRecommendationRequest request)
        {
            try
            {
                // 验证请求
                if (request == null || string.IsNullOrEmpty(request.Description))
                {
                    return Json(new { error = "Description is required" });
                }
                
                System.Diagnostics.Debug.WriteLine($"开始处理相似案例查询请求: {request.Description.Substring(0, Math.Min(50, request.Description.Length))}...");
                
                // 准备数据 - 复用原有逻辑
                var newCase = PrepareNewCaseData(request);
                var cases = GetHistoricalCases();
                
                var apiRequest = new {
                    description = request.Description,
                    new_case = newCase,
                    historical_cases = cases
                };
                
                // 配置序列化
                var jsonSettings = new JsonSerializerSettings
                {
                    NullValueHandling = NullValueHandling.Include,
                    DefaultValueHandling = DefaultValueHandling.Include,
                    Formatting = Formatting.None,
                    ContractResolver = new DefaultContractResolver { NamingStrategy = null }
                };
                
                var jsonRequest = JsonConvert.SerializeObject(apiRequest, jsonSettings);
                
                using (var client = new HttpClient())
                {
                    client.Timeout = TimeSpan.FromMinutes(2);
                    
                    var content = new StringContent(
                        jsonRequest,
                        System.Text.Encoding.UTF8,
                        "application/json"
                    );

                    System.Diagnostics.Debug.WriteLine("开始调用FastAPI相似案例查询服务...");
                    
                    var response = await client.PostAsync(
                        "http://localhost:8000/search_similar_cases",
                        content
                    );
                    
                    if (!response.IsSuccessStatusCode)
                    {
                        var error = await response.Content.ReadAsStringAsync();
                        System.Diagnostics.Debug.WriteLine($"相似案例查询服务返回错误: {error}");
                        return Json(new { error = "Similar cases service returned an error", details = error });
                    }

                    var responseString = await response.Content.ReadAsStringAsync();
                    System.Diagnostics.Debug.WriteLine($"相似案例查询服务响应内容长度: {responseString.Length}");
                    
                    try {
                        var data = JsonConvert.DeserializeObject<SearchResponse>(responseString);
                        
                        // 返回使用驼峰命名法的数据
                        return Json(new {
                            similarCases = data.SimilarCases
                        });
                    }
                    catch (Exception parseEx) {
                        System.Diagnostics.Debug.WriteLine($"解析相似案例JSON响应失败: {parseEx.Message}");
                        return Json(new { 
                            error = "Failed to parse response from similar cases service", 
                            details = parseEx.Message,
                            response = responseString.Length > 1000 ? responseString.Substring(0, 1000) + "..." : responseString
                        });
                    }
                }
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"获取相似案例失败: {ex.Message}\n{ex.StackTrace}");
                return Json(new { error = "Failed to get similar cases", details = ex.Message });
            }
        }
        
        // 辅助方法：准备新案例数据
        private Dictionary<string, object> PrepareNewCaseData(AiRecommendationRequest request)
        {
            // 处理Severity值
            string severityValue = request.Severity;
            int? priorityId = null;
            
            if (!string.IsNullOrEmpty(severityValue))
            {
                // 尝试从SeveritySLA表查找匹配项
                var severitySLA = _db.SeveritySLAs.FirstOrDefault(s => s.SeverityLevel == severityValue);
                if (severitySLA != null)
                {
                    priorityId = severitySLA.ID;
                }
                else
                {
                    // 尝试提取数字
                    var match = System.Text.RegularExpressions.Regex.Match(severityValue, @"Severity\s*(\d+)");
                    if (match.Success && int.TryParse(match.Groups[1].Value, out int value))
                    {
                        priorityId = value;
                    }
                }
            }
            
            // 处理PREFERENCE值
            string priorityName = request.Priority;
            int? preferenceValue = null;
            
            if (!string.IsNullOrEmpty(priorityName))
            {
                // 尝试从枚举描述中获取值
                var preference = EnumExtensions.GetEnumFromDescription<Preferences>(priorityName);
                if (preference != default)
                {
                    preferenceValue = (int)preference;
                }
                else
                {
                    // 使用默认映射
                    string lowerPref = priorityName.ToLower();
                    if (lowerPref == "high")
                        preferenceValue = (int)Preferences.High;
                    else if (lowerPref == "low")
                        preferenceValue = (int)Preferences.Low;
                    else if (lowerPref == "medium")
                        preferenceValue = (int)Preferences.Medium;
                }
            }
            
            return new Dictionary<string, object>
            {
                ["ID"] = "new",
                ["Summary"] = request.Summary,
                ["Subject"] = request.Summary,
                ["Description"] = request.Description,
                ["Priority"] = priorityId,
                ["PREFERENCE"] = preferenceValue,
                ["X_PREFERENCE"] = preferenceValue,
                ["x_preference"] = preferenceValue,
                ["PREFERENCE_STR"] = preferenceValue.HasValue ? preferenceValue.Value.ToString() : "3",
                ["PreferenceLevel"] = preferenceValue.HasValue
                    ? ((Preferences)preferenceValue.Value).GetDescription()
                    : Preferences.Low.GetDescription(),
                ["Category"] = request.Category,
                ["Task"] = request.Task,
                ["DefectPhase"] = request.DefectPhase,
                ["PriorityName"] = request.Severity,
                ["SeverityName"] = request.Priority
            };
        }
        
        // 辅助方法：获取历史案例数据
        private List<Dictionary<string, object>> GetHistoricalCases()
        {
            // 先从数据库获取数据
            var casesQuery = (from c in _db.Cases
                             join cat in _db.CategoryMasters on c.CategoryIDFK equals cat.ID into cj
                             from cat in cj.DefaultIfEmpty()
                             join task in _db.TaskMasters on c.TaskID equals task.ID into tj
                             from task in tj.DefaultIfEmpty()
                             join sev in _db.SeveritySLAs on c.Priority equals sev.ID into sj
                             from sev in sj.DefaultIfEmpty()
                             where !string.IsNullOrEmpty(c.RCAReport)
                             orderby c.CreatedDate descending
                             select new {
                                 Case = c,
                                 CategoryDescr = cat != null ? cat.Descr : null,
                                 TaskDescr = task != null ? task.TaskDescription : null,
                                 SeverityLevel = sev != null ? sev.SeverityLevel : null
                             }).Take(100).ToList();
            
            // 如果没有找到包含RCA报告的案例，尝试获取任何案例
            if (casesQuery.Count == 0)
            {
                casesQuery = (from c in _db.Cases
                           join cat in _db.CategoryMasters on c.CategoryIDFK equals cat.ID into cj
                           from cat in cj.DefaultIfEmpty()
                           join task in _db.TaskMasters on c.TaskID equals task.ID into tj
                           from task in tj.DefaultIfEmpty()
                           join sev in _db.SeveritySLAs on c.Priority equals sev.ID into sj
                           from sev in sj.DefaultIfEmpty()
                           orderby c.CreatedDate descending
                           select new {
                               Case = c,
                               CategoryDescr = cat != null ? cat.Descr : null,
                               TaskDescr = task != null ? task.TaskDescription : null,
                               SeverityLevel = sev != null ? sev.SeverityLevel : null
                           }).Take(100).ToList();
            }
            
            // 转换成字典列表
            return casesQuery.Select(c => new Dictionary<string, object>
            {
                ["ID"] = c.Case.ID.ToString(),
                ["CaseNumber"] = c.Case.ID.ToString(),
                ["Subject"] = c.Case.Subject ?? "",
                ["Summary"] = c.Case.Summary ?? c.Case.Subject ?? "",
                ["Description"] = c.Case.Description ?? "",
                ["Priority"] = c.SeverityLevel ?? (c.Case.Priority != null ? $"Severity {c.Case.Priority}" : "Severity 1"),
                ["PREFERENCE"] = c.Case.PREFERENCE.HasValue ? c.Case.PREFERENCE.Value : 3,
                ["X_PREFERENCE"] = c.Case.PREFERENCE.HasValue ? c.Case.PREFERENCE.Value : 3,
                ["x_preference"] = c.Case.PREFERENCE.HasValue ? c.Case.PREFERENCE.Value : 3,
                ["PREFERENCE_STR"] = c.Case.PREFERENCE.HasValue ? c.Case.PREFERENCE.Value.ToString() : "3",
                ["PreferenceLevel"] = c.Case.PREFERENCE.HasValue 
                    ? ((Preferences)c.Case.PREFERENCE.Value).GetDescription()
                    : Preferences.Low.GetDescription(),
                ["Category"] = c.Case.Category ?? "",
                ["CategoryName"] = c.CategoryDescr ?? c.Case.Category ?? "",
                ["Task"] = c.Case.Task ?? "",
                ["TaskName"] = c.TaskDescr ?? c.Case.Task ?? "",
                ["DefectPhase"] = c.Case.DefectPhase ?? "",
                ["RCAReport"] = c.Case.RCAReport ?? "This case has no RCA report"
            }).ToList();
        }

        // NewTicket page with default values
        public ActionResult NewTicket()
        {
            // 重新加载下拉选项以便在验证失败时显示
            ViewBag.SeverityOptions = _db.SeveritySLAs.Select(s => new SelectListItem
            {
                Value = s.ID.ToString(),
                Text = s.SeverityLevel
            }).ToList();
            
            ViewBag.PriorityOptions = Enum.GetValues(typeof(Preferences))
                .Cast<Preferences>()
                .Select(p => new SelectListItem
                {
                    Value = ((int)p).ToString(),
                    Text = p.GetDescription()
                }).ToList();
            
            // 加载Category选项
            ViewBag.CategoryOptions = _db.CategoryMasters
                .Select(c => new SelectListItem
                {
                    Value = c.Descr,
                    Text = c.Descr
                }).ToList();
                
            // 加载Task选项
            ViewBag.TaskOptions = _db.TaskMasters
                .Select(t => new SelectListItem
                {
                    Value = t.TaskDescription,
                    Text = t.TaskDescription
                }).ToList();
                
            // 加载DefectPhase选项
            var defectPhases = new List<SelectListItem>
            {
                new SelectListItem { Value = "Coding", Text = "Coding" },
                new SelectListItem { Value = "Design", Text = "Design" },
                new SelectListItem { Value = "Testing", Text = "Testing" },
                new SelectListItem { Value = "Deployment", Text = "Deployment" },
                new SelectListItem { Value = "Requirements", Text = "Requirements" }
            };
            ViewBag.DefectPhaseOptions = defectPhases;
            
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
                int priorityValue = 1; // 默认值
                
                // 检查PriorityName字段
                if (!string.IsNullOrEmpty(model.PriorityName))
                {
                    // 尝试从SeveritySLA表中查找匹配的ID
                    var severitySLA = _db.SeveritySLAs.FirstOrDefault(s => s.SeverityLevel == model.PriorityName);
                    if (severitySLA != null)
                    {
                        priorityValue = severitySLA.ID;
                    }
                    else
                    {
                        // 尝试提取数字
                        var match = System.Text.RegularExpressions.Regex.Match(model.PriorityName, @"Severity\s*(\d+)");
                        if (match.Success && int.TryParse(match.Groups[1].Value, out int value))
                        {
                            priorityValue = value;
                        }
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
                    // 尝试从枚举描述中获取值
                    var preference = EnumExtensions.GetEnumFromDescription<Preferences>(model.SeverityName);
                    if (preference != default)
                    {
                        preferenceValue = (int)preference;
                    }
                    else
                    {
                        // 使用默认映射
                        string lowerPref = model.SeverityName.ToLower();
                        if (lowerPref == "high")
                            preferenceValue = (int)Preferences.High;
                        else if (lowerPref == "low")
                            preferenceValue = (int)Preferences.Low;
                        else
                            preferenceValue = (int)Preferences.Medium;
                    }
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
                model.StatusIDFK = model.StatusIDFK.HasValue ? model.StatusIDFK.Value : (int)TicketStatus.Open;
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
            
            // 重新加载下拉选项以便在验证失败时显示
            ViewBag.SeverityOptions = _db.SeveritySLAs.Select(s => new SelectListItem
            {
                Value = s.ID.ToString(),
                Text = s.SeverityLevel
            }).ToList();
            
            ViewBag.PriorityOptions = Enum.GetValues(typeof(Preferences))
                .Cast<Preferences>()
                .Select(p => new SelectListItem
                {
                    Value = ((int)p).ToString(),
                    Text = p.GetDescription()
                }).ToList();
            
            // 加载Category选项
            ViewBag.CategoryOptions = _db.CategoryMasters
                .Select(c => new SelectListItem
                {
                    Value = c.Descr,
                    Text = c.Descr
                }).ToList();
                
            // 加载Task选项
            ViewBag.TaskOptions = _db.TaskMasters
                .Select(t => new SelectListItem
                {
                    Value = t.TaskDescription,
                    Text = t.TaskDescription
                }).ToList();
                
            // 加载DefectPhase选项
            var defectPhases = new List<SelectListItem>
            {
                new SelectListItem { Value = "Coding", Text = "Coding" },
                new SelectListItem { Value = "Design", Text = "Design" },
                new SelectListItem { Value = "Testing", Text = "Testing" },
                new SelectListItem { Value = "Deployment", Text = "Deployment" },
                new SelectListItem { Value = "Requirements", Text = "Requirements" }
            };
            ViewBag.DefectPhaseOptions = defectPhases;
            
            return View(model);
        }

        // 编辑工单页面
        public ActionResult EditCase(int id)
        {
            var model = _db.Cases.Find(id);
            if (model == null) return HttpNotFound();
            
            // 加载下拉选项数据
            ViewBag.SeverityOptions = _db.SeveritySLAs.Select(s => new SelectListItem
            {
                Value = s.ID.ToString(),
                Text = s.SeverityLevel,
                Selected = model.Priority.HasValue && s.ID == model.Priority.Value
            }).ToList();
            
            ViewBag.PriorityOptions = Enum.GetValues(typeof(Preferences))
                .Cast<Preferences>()
                .Select(p => new SelectListItem
                {
                    Value = ((int)p).ToString(),
                    Text = p.GetDescription(),
                    Selected = model.PREFERENCE.HasValue && (int)p == model.PREFERENCE.Value
                }).ToList();
                
            // 补齐默认值
            model.Project = model.Project ?? "PL-IP MTS 2019";
            model.Category = model.Category ?? "General";
            
            // 数值转换为字符串
            if (model.Priority.HasValue)
            {
                // 将int?转换为字符串格式
                int priorityVal = model.Priority.Value;
                var severitySLA = _db.SeveritySLAs.FirstOrDefault(s => s.ID == priorityVal);
                model.PriorityName = severitySLA?.SeverityLevel ?? $"Severity {priorityVal}";
            }
            else
            {
                model.PriorityName = "Severity 1";
            }
            
            if (model.PREFERENCE.HasValue)
            {
                // 将int?转换为枚举值并获取描述
                int prefValue = model.PREFERENCE.Value;
                if (Enum.IsDefined(typeof(Preferences), prefValue))
                {
                    var prefEnum = (Preferences)prefValue;
                    model.SeverityName = prefEnum.GetDescription();
                }
                else
                {
                    // 使用默认映射
                    if (prefValue == 1)
                        model.SeverityName = "High";
                    else if (prefValue == 3)
                        model.SeverityName = "Low";
                    else
                        model.SeverityName = "Medium";
                }
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
                // 使用枚举处理状态
                if (Enum.TryParse<TicketStatus>(changeStatusTo, out var status))
                {
                    model.StatusIDFK = (int)status;
                }
                else
                {
                    model.StatusIDFK = ConvertStatusToId(changeStatusTo);
                }
            }
            
            // 将字符串值转换为数值 - Priority处理
            int priorityValue = 1; // 默认值
            
            // 检查PriorityName字段
            if (!string.IsNullOrEmpty(model.PriorityName))
            {
                // 尝试从SeveritySLA表中查找匹配的ID
                var severitySLA = _db.SeveritySLAs.FirstOrDefault(s => s.SeverityLevel == model.PriorityName);
                if (severitySLA != null)
                {
                    priorityValue = severitySLA.ID;
                }
                else
                {
                    // 尝试提取数字
                    var match = System.Text.RegularExpressions.Regex.Match(model.PriorityName, @"Severity\s*(\d+)");
                    if (match.Success && int.TryParse(match.Groups[1].Value, out int value))
                    {
                        priorityValue = value;
                    }
                }
            }
            // 如果Priority是int类型
            else if (model.Priority.HasValue)
            {
                priorityValue = model.Priority.Value;
            }
            
            // 将字符串值转换为数值 - PREFERENCE处理
            int preferenceValue = (int)Preferences.Medium; // 默认中等优先级
            
            // 检查SeverityName字段
            if (!string.IsNullOrEmpty(model.SeverityName))
            {
                // 尝试从枚举描述中获取值
                var preference = EnumExtensions.GetEnumFromDescription<Preferences>(model.SeverityName);
                if (preference != default)
                {
                    preferenceValue = (int)preference;
                }
                else
                {
                    // 使用默认映射
                    string lowerPref = model.SeverityName.ToLower();
                    if (lowerPref == "high")
                        preferenceValue = (int)Preferences.High;
                    else if (lowerPref == "low")
                        preferenceValue = (int)Preferences.Low;
                    else
                        preferenceValue = (int)Preferences.Medium;
                }
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
            model.StatusIDFK = model.StatusIDFK.HasValue ? model.StatusIDFK.Value : (int)TicketStatus.Open;
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
            if (model.StatusIDFK.HasValue && model.StatusIDFK.Value == (int)TicketStatus.Closed)
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
            
            // 重新加载下拉选项以便在验证失败时显示
            ViewBag.SeverityOptions = _db.SeveritySLAs.Select(s => new SelectListItem
            {
                Value = s.ID.ToString(),
                Text = s.SeverityLevel,
                Selected = model.Priority.HasValue && s.ID == model.Priority.Value
            }).ToList();
            
            ViewBag.PriorityOptions = Enum.GetValues(typeof(Preferences))
                .Cast<Preferences>()
                .Select(p => new SelectListItem
                {
                    Value = ((int)p).ToString(),
                    Text = p.GetDescription(),
                    Selected = model.PREFERENCE.HasValue && (int)p == model.PREFERENCE.Value
                }).ToList();
            
            return View(model);
        }
        
        // 将状态字符串转换为ID
        private int? ConvertStatusToId(string status)
        {
            if (status == null)
                return null;
            
            // 使用枚举处理
            if (Enum.TryParse<TicketStatus>(status.Replace(" ", ""), out var ticketStatus))
            {
                return (int)ticketStatus;
            }
            
            // 使用默认映射
            if (status == "Open")
                return (int)TicketStatus.Open;
            else if (status == "Closed")
                return (int)TicketStatus.Closed;
            else if (status == "In Progress")
                return (int)TicketStatus.InProgress;
            else
                return null;
        }

        // 添加一个方法检查数据库字段映射
        [HttpGet]
        public ActionResult CheckDatabaseMapping()
        {
            var result = new List<object>();
            
            try
            {
                // 获取数据库元数据
                var metadataWorkspace = ((System.Data.Entity.Infrastructure.IObjectContextAdapter)_db).ObjectContext.MetadataWorkspace;
                var itemCollection = metadataWorkspace.GetItemCollection(System.Data.Entity.Core.Metadata.Edm.DataSpace.CSpace);
                var entityTypes = metadataWorkspace.GetItems<System.Data.Entity.Core.Metadata.Edm.EntityType>(System.Data.Entity.Core.Metadata.Edm.DataSpace.CSpace);
                
                // 检查Case实体的映射
                var caseEntity = entityTypes.FirstOrDefault(e => e.Name == "Case");
                if (caseEntity != null)
                {
                    // 获取所有属性
                    result.Add(new {
                        EntityName = caseEntity.Name,
                        Properties = caseEntity.Properties.Select(p => new {
                            Name = p.Name,
                            Type = p.TypeUsage.EdmType.Name,
                            Nullable = p.Nullable
                        }).ToList()
                    });
                }
                
                // 从数据库获取几个实际的案例记录
                var cases = _db.Cases
                               .Where(c => !string.IsNullOrEmpty(c.RCAReport))
                               .OrderByDescending(c => c.CreatedDate)
                               .Take(5)
                               .ToList();
                
                // 直接检查和记录PREFERENCE字段
                var caseData = cases.Select(c => new {
                    ID = c.ID,
                    PREFERENCE = c.PREFERENCE,
                    PREFERENCE_HasValue = c.PREFERENCE.HasValue,
                    PREFERENCE_Type = c.PREFERENCE != null ? c.PREFERENCE.GetType().FullName : "null"
                }).ToList();
                
                result.Add(new { CaseData = caseData });
                
                // 查看SQL查询
                var sql = "";
                try
                {
                    var query = _db.Cases.Where(c => c.ID > 0);
                    sql = query.ToString();
                }
                catch (Exception ex)
                {
                    sql = "Failed to get SQL: " + ex.Message;
                }
                
                result.Add(new { SQL = sql });
                
                return Json(result, JsonRequestBehavior.AllowGet);
            }
            catch (Exception ex)
            {
                return Json(new { Error = ex.Message, StackTrace = ex.StackTrace }, JsonRequestBehavior.AllowGet);
            }
        }

        // 添加专门的日志方法，直接写入文件
        private void LogToFile(string message)
        {
            try
            {
                // 尝试写入网站日志目录和用户Documents目录，提高成功率
                string[] logPaths = new string[]
                {
                    System.IO.Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "debug_log.txt"),
                    System.IO.Path.Combine(System.IO.Path.GetTempPath(), "TeBSiTrack_debug_log.txt"),
                    System.IO.Path.Combine(
                        Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                        "TeBSiTrack_debug_log.txt")
                };

                foreach (string logPath in logPaths)
                {
                    try
                    {
                        System.IO.File.AppendAllText(logPath, $"[{DateTime.Now}] {message}\n");
                        // 如果成功写入其中一个位置，就返回
                        return;
                    }
                    catch
                    {
                        // 尝试下一个路径
                        continue;
                    }
                }
            }
            catch
            {
                // 如果所有写入都失败，忽略异常，不影响主流程
            }
        }
    }
}
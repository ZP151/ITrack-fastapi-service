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

namespace ChatbotMvcForm4._6.Controllers
{
    public class HomeController : Controller
    {
        private static readonly HttpClient client = new HttpClient();

        public ActionResult Index()
        {
            return View();
        }
        public ActionResult EditCase()
        {
            return View();  // 返回 EditCase 视图
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
                
                // 创建完整的 ChatRequest 对象
                var chatRequestData = new ChatRequest
                {
                    SessionId = sessionId,
                    // 将其他必要字段初始化为空值或默认值
                    Category = "",
                    Task = "",
                    Summary = "",
                    Description = "", // 只将conclusion复制到description
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

                var finalContent = new StringContent(
                    JsonConvert.SerializeObject(chatRequestData),
                    System.Text.Encoding.UTF8,
                    "application/json"
                );

                // 发送到 FastAPI
                //Original local address
                //var finalResponse = await client.PostAsync("http://127.0.0.1:8000/refine_rca", finalContent);

                //LAN devices can access FastAPI through IIS.
                var finalResponse = await client.PostAsync("http://192.168.68.153/refine_rca", finalContent);

                var finalResponseString = await finalResponse.Content.ReadAsStringAsync();

                // 尝试解析响应
                var finalResponseData = JsonConvert.DeserializeObject<Dictionary<string, string>>(finalResponseString);
                if (finalResponseData != null && finalResponseData.TryGetValue("status", out string status) && status == "success")
                {
                    return Json(new { status = "success" });
                }
                else
                {
                    return Json(new { error = "FastAPI did not return success status", response = finalResponseString });
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
            //var response = await client.PostAsync("http://127.0.0.1:8000/refine_rca", content);
            var response = await client.PostAsync("http://192.168.68.153/refine_rca", content);

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
    }
}
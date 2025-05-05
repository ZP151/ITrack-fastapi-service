using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Web;

namespace ChatbotMvcForm4._6.Models
{
    /// <summary>
    /// 所有包含动态字段的类的基类
    /// </summary>
    public class BaseSection
    {
        [JsonProperty("dynamic_fields")]
        public List<DynamicField> DynamicFields { get; set; } = new List<DynamicField>();
    }

    /// <summary>
    /// 补充信息
    /// </summary>
    public class SupplementaryInfo : BaseSection
    {
        // 基类已包含DynamicFields属性
    }

    /// <summary>
    /// 附加问题
    /// </summary>
    public class AdditionalQuestions : BaseSection
    {
        // 基类已包含DynamicFields属性
    }

    /// <summary>
    /// 预防措施
    /// </summary>
    public class PreventiveMeasures : BaseSection
    {
        [JsonProperty("general_measure")]
        public string GeneralMeasure { get; set; } = "TBD";
    }

    /// <summary>
    /// 解决方案
    /// </summary>
    public class Resolution : BaseSection
    {
        [JsonProperty("fix_applied")]
        public string FixApplied { get; set; } = "Not provided";
    }

    /// <summary>
    /// 影响分析
    /// </summary>
    public class ImpactAnalysis : BaseSection
    {
        [JsonProperty("affected_module")]
        public string AffectedModule { get; set; } = "Unknown";

        [JsonProperty("severity")]
        public string Severity { get; set; } = "Severity 1";

        [JsonProperty("priority")]
        public string Priority { get; set; } = "Medium";

        [JsonProperty("defect_phase")]
        public string DefectPhase { get; set; } = "Unknown";
    }
} 
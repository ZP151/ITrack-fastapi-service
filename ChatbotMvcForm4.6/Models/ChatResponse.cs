using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Web;

namespace ChatbotMvcForm4._6.Models
{
    public class ChatResponse
    {
        [JsonProperty("category")]
        public string Category { get; set; }

        [JsonProperty("task")]
        public string Task { get; set; }

        [JsonProperty("summary")]
        public string Summary { get; set; }

        [JsonProperty("description")]
        public string Description { get; set; }

        [JsonProperty("root_causes")]
        public List<string> RootCauses { get; set; }

        [JsonProperty("conclusion")]
        public string Conclusion { get; set; }

        [JsonProperty("impact_analysis")]
        public ImpactAnalysis ImpactAnalysis { get; set; }

        [JsonProperty("resolution")]
        public Resolution Resolution { get; set; }

        [JsonProperty("supplementary_info")]
        public SupplementaryInfo SupplementaryInfo { get; set; }

        [JsonProperty("preventive_measures")]
        public PreventiveMeasures PreventiveMeasures { get; set; }

        [JsonProperty("additional_questions")]
        public AdditionalQuestions AdditionalQuestions { get; set; }
    }
}

using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Web;

namespace ChatbotMvcForm4._6.Models
{
    public class DynamicField
    {
        [JsonProperty("key")]

        public string Key { get; set; }
        [JsonProperty("type")]

        public string Type { get; set; }  // "string" or "array"
        [JsonProperty("value")]

        public object Value { get; set; } = "TBD";  // Default placeholder value
        [JsonProperty("is_confirmed")]

        public bool IsConfirmed { get; set; } = false;
    }
}
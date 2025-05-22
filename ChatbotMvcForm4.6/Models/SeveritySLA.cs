using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace ChatbotMvcForm4._6.Models
{
    [Table("SeveritySLA")]
    public class SeveritySLA
    {
        [Key]
        public int ID { get; set; }
        
        public string SeverityLevel { get; set; }
        
        // 可能的其他字段（根据实际数据库结构添加）
        public int? ResponceTimeHour { get; set; }
        
        public int? ResolutionDays { get; set; }
    }
} 
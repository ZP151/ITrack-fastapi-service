using System.ComponentModel;

namespace ChatbotMvcForm4._6.Models
{
    /// <summary>
    /// 优先级枚举，对应Case.PREFERENCE字段
    /// </summary>
    public enum Preferences
    {
        [Description("High")]
        High = 1,
        
        [Description("Medium")]
        Medium = 2,
        
        [Description("Low")]
        Low = 3
    }
    
    /// <summary>
    /// 工单状态枚举
    /// </summary>
    public enum TicketStatus
    {
        [Description("Open")]
        Open = 2,
        
        [Description("Closed")]
        Closed = 5,
        
        [Description("In Progress")]
        InProgress = 37
    }
} 
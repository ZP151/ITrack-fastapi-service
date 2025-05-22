using System;
using System.ComponentModel;
using System.Linq;
using System.Reflection;

namespace ChatbotMvcForm4._6.Models
{
    /// <summary>
    /// 枚举扩展方法类
    /// </summary>
    public static class EnumExtensions
    {
        /// <summary>
        /// 获取枚举值的描述属性
        /// </summary>
        public static string GetDescription(this Enum value)
        {
            FieldInfo field = value.GetType().GetField(value.ToString());
            if (field == null) return value.ToString();
            
            var attribute = (DescriptionAttribute)field.GetCustomAttributes(typeof(DescriptionAttribute), false).FirstOrDefault();
            return attribute?.Description ?? value.ToString();
        }
        
        /// <summary>
        /// 根据描述获取枚举值
        /// </summary>
        public static T GetEnumFromDescription<T>(string description) where T : struct, Enum
        {
            var type = typeof(T);
            foreach (var field in type.GetFields())
            {
                if (Attribute.GetCustomAttribute(field, typeof(DescriptionAttribute)) is DescriptionAttribute attribute)
                {
                    if (attribute.Description == description)
                        return (T)field.GetValue(null);
                }
                if (field.Name == description)
                    return (T)field.GetValue(null);
            }
            
            // 如果找不到匹配的描述，尝试直接转换
            if (Enum.TryParse<T>(description, out var result))
                return result;
                
            return default;
        }
        
        /// <summary>
        /// 将整数转换为对应的枚举值
        /// </summary>
        public static T ToEnum<T>(this int value) where T : struct, Enum
        {
            if (Enum.IsDefined(typeof(T), value))
                return (T)Enum.ToObject(typeof(T), value);
                
            return default;
        }
    }
} 
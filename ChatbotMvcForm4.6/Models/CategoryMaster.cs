using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace ChatbotMvcForm4._6.Models
{
    [Table("CategoryMaster")]
    public class CategoryMaster
    {
        [Key]
        public int ID { get; set; }
        public string Descr { get; set; }
        public int? DepartmentIDFK { get; set; }
    }
} 
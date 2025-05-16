using System;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace ChatbotMvcForm4._6.Models
{
    [Table("RCAMaster")]
    public class RCAMaster
    {
        [Key]
        public int ID { get; set; }
        public string RCAName { get; set; }
        public bool? isActive { get; set; }
        public DateTime? CreatedDate { get; set; }
        public string CreatedBy { get; set; }
        public DateTime? UpdatedDate { get; set; }
        public string UpdatedBy { get; set; }
        public int? DepartmentIDFK { get; set; }
    }
} 
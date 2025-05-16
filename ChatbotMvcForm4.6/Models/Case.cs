using System;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace ChatbotMvcForm4._6.Models
{
    [Table("Case")]
    public class Case
    {
        [Key]
        public int ID { get; set; }
        public string CaseNumber { get; set; }
        public int? DepartmentIDFK { get; set; }
        public int? CategoryIDFK { get; set; }
        public int? Priority { get; set; }
        public string Description { get; set; }
        public string AdditionInformation { get; set; }
        public int? AssignedToIDFK { get; set; }
        public int? StatusIDFK { get; set; }
        public string CreatedBy { get; set; }
        public DateTime? CreatedDate { get; set; }
        public string UpdatedBy { get; set; }
        public DateTime? UpdatedDate { get; set; }
        public bool? IsPrivate { get; set; }
        public string Subject { get; set; }
        public string Name { get; set; }
        public string Email { get; set; }
        public string ContactNo { get; set; }
        public string Summary { get; set; }
        public DateTime? ResolutionDate { get; set; }
        public string RootCause { get; set; }
        public int? Environment { get; set; }
        public int? TaskID { get; set; }
        public int? PREFERENCE { get; set; }
        public int? DefectPhaseID { get; set; }
        public int? RCAID { get; set; }
        public string caselinked { get; set; }
        public string RCAReport { get; set; }
        [NotMapped]
        public string Project { get; set; }
        [NotMapped]
        public string Category { get; set; }
        [NotMapped]
        public string Severity { get; set; }
        [NotMapped]
        public string Task { get; set; }
        [NotMapped]
        public string PriorityName { get; set; }
        [NotMapped]
        public string DefectPhase { get; set; }
        [NotMapped]
        public string TicketOwner { get; set; }
        [NotMapped]
        public string LinkedTickets { get; set; }
        [NotMapped]
        public string RCA { get; set; }
        [NotMapped]
        public string Status { get; set; }
        [NotMapped]
        public string AssignedTo { get; set; }
        [NotMapped]
        public string SeverityName { get; set; }
    }
} 
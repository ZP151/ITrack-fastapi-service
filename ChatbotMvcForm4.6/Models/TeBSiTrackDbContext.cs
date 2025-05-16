using System.Data.Entity;

namespace ChatbotMvcForm4._6.Models
{
    public class TeBSiTrackDbContext : DbContext
    {
        public TeBSiTrackDbContext() : base("DefaultConnection") { }

        public DbSet<Case> Cases { get; set; }
        public DbSet<CategoryMaster> CategoryMasters { get; set; }
        public DbSet<TaskMaster> TaskMasters { get; set; }
        public DbSet<RCAMaster> RCAMasters { get; set; }
    }
} 
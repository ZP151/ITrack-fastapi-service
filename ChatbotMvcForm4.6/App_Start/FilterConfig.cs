using System.Web;
using System.Web.Mvc;

namespace ChatbotMvcForm4._6
{
    public class FilterConfig
    {
        public static void RegisterGlobalFilters(GlobalFilterCollection filters)
        {
            filters.Add(new HandleErrorAttribute());
        }
    }
}

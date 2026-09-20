// Test tool only: operate on the explicitly supplied test process, never global input.
using System;
using System.Collections.Generic;
using System.Text;
using System.Windows.Automation;

class UiaProbe
{
    static int Main(string[] args)
    {
        try
        {
            int pid = int.Parse(args[0]);
            var windows = AutomationElement.RootElement.FindAll(TreeScope.Children,
                new PropertyCondition(AutomationElement.ProcessIdProperty, pid));
            var elements = new List<AutomationElement>();
            foreach (AutomationElement window in windows)
            {
                elements.Add(window);
                foreach (AutomationElement element in window.FindAll(TreeScope.Descendants, Condition.TrueCondition))
                    elements.Add(element);
            }
            if (args[1] == "dump")
            {
                for (int i = 0; i < elements.Count; i++)
                {
                    var e = elements[i]; var p = e.Current; var rect = p.BoundingRectangle;
                    var patterns = Array.ConvertAll(e.GetSupportedPatterns(), pattern => pattern.ProgrammaticName);
                    Console.WriteLine(string.Join("\t", new string[] {i.ToString(),
                        p.ControlType.ProgrammaticName, Convert.ToBase64String(Encoding.UTF8.GetBytes(p.Name)),
                        p.AutomationId, rect.ToString(System.Globalization.CultureInfo.InvariantCulture),
                        p.IsOffscreen.ToString(), string.Join(",", patterns)}));
                }
                return 0;
            }
            var target = elements[int.Parse(args[2])];
            if (args[1] == "value") ((ValuePattern)target.GetCurrentPattern(ValuePattern.Pattern)).SetValue(args[3]);
            else if (args[1] == "invoke") ((InvokePattern)target.GetCurrentPattern(InvokePattern.Pattern)).Invoke();
            else if (args[1] == "select") ((SelectionItemPattern)target.GetCurrentPattern(SelectionItemPattern.Pattern)).Select();
            else if (args[1] == "focus") target.SetFocus();
            else throw new ArgumentException("Unsupported action");
            return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error.ToString()); return 1; }
    }
}

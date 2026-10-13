Dim result
result = CreateObject("Wscript.Shell").Run("""C:\Users\esam\Desktop\Report Generation Automation\run_daily_report.bat""", 0, True)
WScript.Quit result

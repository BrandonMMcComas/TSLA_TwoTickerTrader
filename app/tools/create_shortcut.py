import os
def create_desktop_shortcut(target_cmd_path: str, shortcut_path: str, icon_path: str):
    try:
        import win32com.client  # pywin32
    except Exception as e:
        return False
    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.Targetpath = target_cmd_path
    shortcut.WorkingDirectory = os.path.dirname(target_cmd_path)
    if os.path.exists(icon_path):
        shortcut.IconLocation = icon_path
    shortcut.save()
    return True

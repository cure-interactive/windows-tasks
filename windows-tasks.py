"""
[🪟 Windows Tasks - Cure Interactive] [🧰 CustomTkinter GUI]
===============================================================================
A small CustomTkinter utility with a one-click button to clear Windows 11 icon +
thumbnail caches (and restart Explorer) to force icons to rebuild.

Notes
- This is WINDOWS-ONLY. On Linux/macOS the button is disabled.
- Clearing the Explorer cache typically requires admin privileges.
- The app will attempt self-elevation (UAC prompt) if not already elevated.

Buttons
- "Clear Icon Cache (Win11)": Kills explorer.exe, deletes iconcache*/thumbcache*,
  then restarts Explorer.
- "Uninstall ALL pip Packages": Uninstalls every package shown by `pip list`
  for the currently-running Python interpreter.

Requires
- customtkinter

Run
- python windows_tasks_cure_interactive.py
===============================================================================
"""

from __future__ import annotations

import os
import sys
import time
import ctypes
import subprocess
import threading
from dataclasses import dataclass

import customtkinter as ctk


# =============================================================================
# App Identity / Icons (Windows taskbar + window icon)
# =============================================================================

SCRIPT_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

APP_TITLE = "Windows Tasks - Cure Interactive"
APP_USER_MODEL_ID = "CureInteractive.WindowsTasks"  # unique per app/script


def set_windows_app_user_model_id(app_id: str) -> None:
  """
  Set an explicit Windows AppUserModelID for this process.

  Notes
  - Windows uses AppUserModelID for taskbar grouping and (often) which icon is shown.
  - Best called BEFORE creating the Tk/CTk window.
  - No-op on non-Windows.
  """
  try:
    if os.name != "nt":
      return
    import ctypes  # stdlib
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(str(app_id))
  except Exception:
    return


def set_window_icon(root, ico_path: str, png_path: str) -> None:
  """
  Set a title-bar icon with best-effort cross-platform behavior.

  Windows:
    - iconbitmap(.ico) works for title bar + taskbar in most cases.
  Linux/macOS:
    - iconphoto(.png) is the common path.

  Notes
  - We try both; failures are ignored (best effort).
  - Paths should be absolute for reliability.
  """
  ico_abs = os.path.abspath(ico_path) if ico_path else ""
  png_abs = os.path.abspath(png_path) if png_path else ""

  try:
    if ico_abs and os.path.isfile(ico_abs):
      root.iconbitmap(ico_abs)
  except Exception:
    pass

  try:
    if png_abs and os.path.isfile(png_abs):
      import tkinter as tk  # local import to avoid changing global imports
      img = tk.PhotoImage(file=png_abs)
      root.iconphoto(True, img)
      root._iconphoto_ref = img  # type: ignore[attr-defined]
  except Exception:
    pass


# =============================================================================
# [⚙️ Helpers]
# =============================================================================

def is_windows() -> bool:
  """Return True if running on Windows."""
  return os.name == "nt"


def is_admin_windows() -> bool:
  """
  Return True if current process has admin privileges on Windows.

  Returns
  -------
  bool
    True if admin, otherwise False.
  """
  if not is_windows():
    return False
  try:
    return bool(ctypes.windll.shell32.IsUserAnAdmin())
  except Exception:
    return False


def relaunch_as_admin_windows(extra_args: list[str] | None = None) -> None:
  """
  Relaunch the current script with elevated (admin) privileges on Windows.

  Parameters
  ----------
  extra_args : list[str] | None
    Additional args to append to sys.argv.

  Raises
  ------
  RuntimeError
    If elevation fails or the user cancels the UAC prompt.
  """
  if not is_windows():
    raise RuntimeError("Elevation is only supported on Windows.")

  exe = sys.executable
  script = os.path.abspath(sys.argv[0])

  args = [script] + sys.argv[1:]
  if extra_args:
    args += list(extra_args)

  # Quote each argument for CreateProcess-style parsing.
  arg_str = " ".join([f"\"{a}\"" for a in args])

  # ShellExecuteW returns value > 32 on success.
  r = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, arg_str, None, 1)
  if r <= 32:
    raise RuntimeError("UAC elevation failed or was cancelled.")
  # If we successfully started the elevated process, exit this one.
  raise SystemExit(0)


@dataclass
class CmdResult:
  """Result of running a command."""
  code: int
  out: str
  err: str


def run_cmd_capture(cmd: list[str], timeout_s: int = 60) -> CmdResult:
  """
  Run a command and capture stdout/stderr.

  Parameters
  ----------
  cmd : list[str]
    Command and args, e.g. ["cmd.exe", "/c", "dir"].
  timeout_s : int
    Timeout in seconds.

  Returns
  -------
  CmdResult
    The captured result.
  """
  p = subprocess.run(
    cmd,
    capture_output=True,
    text=True,
    timeout=timeout_s,
    shell=False
  )
  return CmdResult(code=int(p.returncode), out=p.stdout or "", err=p.stderr or "")


def clear_windows_icon_cache() -> list[str]:
  """
  Clear Windows icon + thumbnail caches and restart Explorer.

  This runs the exact sequence:
    taskkill /f /im explorer.exe
    del %LocalAppData%\\Microsoft\\Windows\\Explorer\\iconcache*
    del %LocalAppData%\\Microsoft\\Windows\\Explorer\\thumbcache*
    start explorer.exe

  Returns
  -------
  list[str]
    Human-readable log lines of what happened.

  Raises
  ------
  RuntimeError
    If not on Windows.
  """
  if not is_windows():
    raise RuntimeError("This task is Windows-only.")

  logs: list[str] = []

  logs.append("[🧹 Cache] Killing Explorer...")
  r1 = run_cmd_capture(["cmd.exe", "/c", "taskkill /f /im explorer.exe"])
  logs.append(f"  - exit={r1.code}")
  if r1.out.strip():
    logs.append(f"  - out: {r1.out.strip()}")
  if r1.err.strip():
    logs.append(f"  - err: {r1.err.strip()}")

  # Give Explorer a moment to fully exit and release file locks.
  time.sleep(0.7)

  explorer_cache_dir = os.path.join(
    os.environ.get("LocalAppData", ""),
    "Microsoft", "Windows", "Explorer"
  )

  logs.append(f"[🗑️ Cache] Deleting iconcache* and thumbcache* in:")
  logs.append(f"  - {explorer_cache_dir}")

  # Use cmd-del so wildcards behave as expected.
  del_icon = f'del /f /q "{explorer_cache_dir}\\iconcache*"'
  del_thumb = f'del /f /q "{explorer_cache_dir}\\thumbcache*"'

  r2 = run_cmd_capture(["cmd.exe", "/c", del_icon])
  logs.append(f"  - del iconcache*: exit={r2.code}")
  if r2.err.strip():
    logs.append(f"    err: {r2.err.strip()}")

  r3 = run_cmd_capture(["cmd.exe", "/c", del_thumb])
  logs.append(f"  - del thumbcache*: exit={r3.code}")
  if r3.err.strip():
    logs.append(f"    err: {r3.err.strip()}")

  logs.append("[🔁 Shell] Restarting Explorer...")
  r4 = run_cmd_capture(["cmd.exe", "/c", "start explorer.exe"])
  logs.append(f"  - exit={r4.code}")
  if r4.err.strip():
    logs.append(f"  - err: {r4.err.strip()}")

  logs.append("[✅ Done] Windows will rebuild icons as they are needed.")
  return logs


def build_pip_uninstall_all_cmd(python_exe: str) -> str:
  """
  Build the Windows CMD one-liner to uninstall ALL packages from a Python's pip
  EXCEPT `pip` itself.

  Notes
  -----
  - We intentionally keep `pip` installed so the interpreter can still manage packages.

  Equivalent shape to:
    for /f "skip=2 tokens=1" %i in ('python -m pip list') do if /i not "%i"=="pip" python -m pip uninstall -y %i

  Parameters
  ----------
  python_exe : str
    Absolute path to the Python executable to use.

  Returns
  -------
  str
    A command string suitable for: ["cmd.exe", "/c", <string>]
  """
  py = os.path.abspath(python_exe)
  pyq = f'"{py}"'
  return (
    'for /f "skip=2 tokens=1" %i in (\''
    f'{pyq} -m pip list'
    "\') do "
    f'if /i not "%i"=="pip" {pyq} -m pip uninstall -y %i'
  )


def uninstall_all_pip_packages_windows(timeout_s: int = 3600) -> list[str]:
  """
  Uninstall ALL pip packages for the currently-running Python (Windows-only).

  Notes
  -----
  - This is destructive and intended for "nuke site-packages" scenarios.
  - Typically requires Admin if Python lives in Program Files.

  Parameters
  ----------
  timeout_s : int
    Overall timeout for the full uninstall loop (seconds).

  Returns
  -------
  list[str]
    Human-readable log lines of what happened.
  """
  if not is_windows():
    raise RuntimeError("This task is Windows-only.")

  logs: list[str] = []
  cmd = build_pip_uninstall_all_cmd(sys.executable)

  logs.append("[💥 pip] Uninstall ALL packages (global) requested.")
  logs.append("[⚠️ DANGER] This will remove *everything* installed via pip for this Python (except `pip`).")
  logs.append("[🧾 CMD] Running:")
  logs.append(f"  {cmd}")

  r = run_cmd_capture(["cmd.exe", "/c", cmd], timeout_s=timeout_s)
  logs.append(f"[💻 CMD] exit={r.code}")

  if r.out.strip():
    logs.append("[📤 stdout]")
    logs += [f"  {line}" for line in r.out.splitlines()]

  if r.err.strip():
    logs.append("[📥 stderr]")
    logs += [f"  {line}" for line in r.err.splitlines()]

  logs.append("[✅ Done] pip uninstall loop finished.")
  return logs


# =============================================================================
# [🪟 GUI]
# =============================================================================

class WindowsTasksApp(ctk.CTk):
  """
  CustomTkinter app: "Windows Tasks - Cure Interactive"
  """

  def __init__(self) -> None:
    super().__init__()

    set_window_icon(
      self,
      os.path.join(SCRIPT_ROOT_DIR, "icon.ico"),
      os.path.join(SCRIPT_ROOT_DIR, "icon.png"),
    )

    self.title(APP_TITLE)
    self.geometry("820x520")
    self.minsize(780, 480)

    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    # Layout
    self.grid_columnconfigure(0, weight=1)
    self.grid_rowconfigure(2, weight=1)

    header = ctk.CTkLabel(
      self,
      text="Windows Tasks - Cure Interactive",
      font=ctk.CTkFont(size=22, weight="bold")
    )
    header.grid(row=0, column=0, sticky="w", padx=18, pady=(18, 8))

    sub = ctk.CTkLabel(
      self,
      text="Utilities for Windows maintenance. (Icon cache reset requires Admin.)",
      font=ctk.CTkFont(size=13)
    )
    sub.grid(row=1, column=0, sticky="w", padx=18, pady=(0, 10))

    # Button row
    self.btn_frame = ctk.CTkFrame(self)
    self.btn_frame.grid(row=2, column=0, sticky="nwe", padx=18, pady=(0, 10))
    self.btn_frame.grid_columnconfigure(0, weight=1)

    self.clear_icon_btn = ctk.CTkButton(
      self.btn_frame,
      text="Clear Icon Cache (Win11)  •  Restart Explorer",
      command=self.on_clear_icon_cache
    )
    self.clear_icon_btn.grid(row=0, column=0, sticky="we", padx=12, pady=12)

    self.uninstall_all_pip_btn = ctk.CTkButton(
      self.btn_frame,
      text="Uninstall ALL pip Packages (except pip) (Global)  •  DANGEROUS",
      command=self.on_uninstall_all_pip_packages
    )
    self.uninstall_all_pip_btn.grid(row=1, column=0, sticky="we", padx=12, pady=(0, 12))

    # Output log
    self.log_box = ctk.CTkTextbox(self, wrap="word")
    self.log_box.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 18))
    self.log_box.configure(state="disabled")

    self._apply_platform_state()

    self.append_log("[🧩 App] Ready.\n")

  def _apply_platform_state(self) -> None:
    if not is_windows():
      self.clear_icon_btn.configure(state="disabled")
      self.uninstall_all_pip_btn.configure(state="disabled")
      self.append_log("[⚠️ Platform] Non-Windows detected. Windows-only tasks disabled.\n")

  def append_log(self, text: str) -> None:
    self.log_box.configure(state="normal")
    self.log_box.insert("end", text)
    self.log_box.see("end")
    self.log_box.configure(state="disabled")

  def append_log_threadsafe(self, text: str) -> None:
    """Append to the log box from any thread."""
    self.after(0, lambda: self.append_log(text))

  def _run_task_in_thread(self, name: str, fn, on_finally=None) -> None:
    """Run a blocking task in a background thread and marshal UI updates safely."""

    def _worker() -> None:
      try:
        logs = fn()
        for line in logs:
          self.append_log_threadsafe(line + "\n")
      except Exception as e:
        self.append_log_threadsafe(f"[❌ Error] {name}: {e}\n")
      finally:
        self.append_log_threadsafe("\n")
        if on_finally:
          self.after(0, on_finally)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

  def on_clear_icon_cache(self) -> None:
    if not is_windows():
      self.append_log("[❌ Task] This task is Windows-only.\n")
      return

    # Ensure admin for a smoother experience.
    if not is_admin_windows():
      self.append_log("[🛡️ UAC] Admin required. Requesting elevation...\n")
      try:
        # Relaunch the same script elevated; current process exits.
        relaunch_as_admin_windows()
      except SystemExit:
        return
      except Exception as e:
        self.append_log(f"[❌ UAC] Elevation failed: {e}\n")
        return

    self.clear_icon_btn.configure(state="disabled")
    self.append_log("[🧹 Task] Clearing Windows icon + thumbnail cache...\n")

    try:
      logs = clear_windows_icon_cache()
      for line in logs:
        self.append_log(line + "\n")
    except Exception as e:
      self.append_log(f"[❌ Error] {e}\n")
    finally:
      self.append_log("\n")
      self.clear_icon_btn.configure(state="normal")

  def on_uninstall_all_pip_packages(self) -> None:
    if not is_windows():
      self.append_log("[❌ Task] This task is Windows-only.\n")
      return

    # Ensure admin for Program Files installs.
    if not is_admin_windows():
      self.append_log("[🛡️ UAC] Admin required. Requesting elevation...\n")
      try:
        relaunch_as_admin_windows()
      except SystemExit:
        return
      except Exception as e:
        self.append_log(f"[❌ UAC] Elevation failed: {e}\n")
        return

    self.uninstall_all_pip_btn.configure(state="disabled")
    self.append_log("[💥 Task] Uninstalling ALL pip packages for this Python...\n")

    self._run_task_in_thread(
      name="pip uninstall all",
      fn=lambda: uninstall_all_pip_packages_windows(timeout_s=3600),
      on_finally=lambda: self.uninstall_all_pip_btn.configure(state="normal"),
    )


def main() -> None:
  # Must happen early for best taskbar behavior on Windows.
  set_windows_app_user_model_id(APP_USER_MODEL_ID)

  app = WindowsTasksApp()
  app.mainloop()


if __name__ == "__main__":
  main()

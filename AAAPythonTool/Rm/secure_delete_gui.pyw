"""
secure_delete_gui.pyw
---------------------
Tkinter GUI wrapper around secure_delete.sh.

Features
- Add files AND folders (multiple at once)
- Drag & drop targets from Explorer onto the window (optional, falls back to buttons)
- Configurable overwrite passes
- Auto-locates Git Bash from env / PATH / common install dirs
- Streams the .sh script's stdout/stderr into a log area
- Per-target progress + overall progress bar
- Safe-by-default: requires typing DELETE to confirm

Run with no extra deps:
    pythonw secure_delete_gui.pyw
or just double-click the .pyw file.
"""

import os
import sys
import shutil
import threading
import subprocess
import queue
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox


SCRIPT_DIR = Path(__file__).resolve().parent
SH_SCRIPT = SCRIPT_DIR / "secure_delete.sh"


# ---------------------------------------------------------------------------
# Locate Git Bash
# ---------------------------------------------------------------------------
def find_git_bash():
    # 1) explicit override
    env_override = os.environ.get("BASH_EXE")
    if env_override and Path(env_override).is_file():
        return env_override

    # 2) PATH
    found = shutil.which("bash.exe") or shutil.which("bash")
    if found:
        # Skip WSL's bash (C:\Windows\System32\bash.exe) -- it can't see /c/ paths cleanly
        if "system32" not in found.lower():
            return found

    # 3) GIT_INSTALL_ROOT / GIT_HOME
    for var in ("GIT_INSTALL_ROOT", "GIT_HOME"):
        root = os.environ.get(var)
        if root:
            cand = Path(root) / "bin" / "bash.exe"
            if cand.is_file():
                return str(cand)

    # 4) Derive from `where git`
    git = shutil.which("git")
    if git:
        cand = Path(git).resolve().parent.parent / "bin" / "bash.exe"
        if cand.is_file():
            return str(cand)

    # 5) Well-known install locations
    candidates = [
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files (x86)\Git\bin\bash.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\bin\bash.exe"),
        os.path.expandvars(r"%ProgramW6432%\Git\bin\bash.exe"),
    ]
    for c in candidates:
        if c and Path(c).is_file():
            return c

    return None


# ---------------------------------------------------------------------------
# Worker: run secure_delete.sh per target, stream output back via a Queue
# ---------------------------------------------------------------------------
class ShredWorker(threading.Thread):
    def __init__(self, bash_exe, targets, passes, msg_q):
        super().__init__(daemon=True)
        self.bash_exe = bash_exe
        self.targets = list(targets)
        self.passes = int(passes)
        self.q = msg_q
        self._cancel = threading.Event()
        self.proc = None

    def cancel(self):
        self._cancel.set()
        try:
            if self.proc and self.proc.poll() is None:
                self.proc.terminate()
        except Exception:
            pass

    def run(self):
        total = len(self.targets)
        ok = 0
        for idx, tgt in enumerate(self.targets, 1):
            if self._cancel.is_set():
                self.q.put(("log", f"\n[CANCELLED] stopped before {tgt}\n"))
                break
            self.q.put(("status", f"[{idx}/{total}] {tgt}"))
            self.q.put(("log", f"\n========== ({idx}/{total}) {tgt} ==========\n"))
            rc = self._run_one(tgt)
            if rc == 0:
                ok += 1
                self.q.put(("log", f"[OK] {tgt}\n"))
            else:
                self.q.put(("log", f"[FAIL rc={rc}] {tgt}\n"))
            self.q.put(("progress", idx, total))
        self.q.put(("done", ok, total))

    def _run_one(self, target):
        env = os.environ.copy()
        env["PASSES"] = str(self.passes)
        # Force UTF-8 in MSYS
        env["LANG"] = "en_US.UTF-8"
        env["LC_ALL"] = "en_US.UTF-8"

        # Hide console window when launched from pythonw
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            self.proc = subprocess.Popen(
                [self.bash_exe, "--noprofile", "--norc", str(SH_SCRIPT), target],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
                startupinfo=startupinfo,
                creationflags=creationflags,
                bufsize=1,
                universal_newlines=True,
                encoding="utf-8",
                errors="replace",
            )
        except Exception as e:
            self.q.put(("log", f"[ERROR] failed to spawn bash: {e}\n"))
            return 99

        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            if self._cancel.is_set():
                break
            self.q.put(("log", line))
        self.proc.wait()
        return self.proc.returncode


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Secure Delete  -  anti-recovery shredder")
        self.geometry("760x560")
        self.minsize(640, 480)

        self.bash_exe = find_git_bash()
        self.worker = None
        self.msg_q = queue.Queue()

        self._build_ui()
        self._poll_queue()

        if not self.bash_exe:
            messagebox.showerror(
                "Git Bash not found",
                "Could not locate bash.exe.\n\n"
                "Install Git for Windows from https://git-scm.com/download/win\n"
                "or set the BASH_EXE environment variable to bash.exe's full path.",
            )

        if not SH_SCRIPT.is_file():
            messagebox.showerror(
                "Missing script",
                f"secure_delete.sh not found next to this program.\n\nExpected:\n{SH_SCRIPT}",
            )

    # ---------- UI ----------
    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        # Top bar: bash status + passes
        top = ttk.Frame(self)
        top.pack(fill=tk.X, **pad)

        bash_label = self.bash_exe if self.bash_exe else "[NOT FOUND]"
        ttk.Label(top, text="Git Bash:").pack(side=tk.LEFT)
        ttk.Label(top, text=bash_label, foreground="#0a7" if self.bash_exe else "#c00").pack(
            side=tk.LEFT, padx=(4, 16)
        )

        ttk.Label(top, text="Overwrite passes:").pack(side=tk.LEFT)
        self.passes_var = tk.IntVar(value=3)
        ttk.Spinbox(top, from_=1, to=35, width=4, textvariable=self.passes_var).pack(side=tk.LEFT)

        # Targets list + buttons
        mid = ttk.LabelFrame(self, text="Targets (files and folders)")
        mid.pack(fill=tk.BOTH, expand=False, **pad)

        list_frame = ttk.Frame(mid)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self.listbox = tk.Listbox(list_frame, height=8, selectmode=tk.EXTENDED, activestyle="dotbox")
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand=sb.set)

        btns = ttk.Frame(mid)
        btns.pack(fill=tk.X, padx=6, pady=(0, 6))
        ttk.Button(btns, text="Add files...", command=self.add_files).pack(side=tk.LEFT)
        ttk.Button(btns, text="Add folder...", command=self.add_folder).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Remove selected", command=self.remove_selected).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Clear", command=self.clear_all).pack(side=tk.LEFT)

        # Optional drag & drop via tkinterdnd2 if installed
        self._try_enable_dnd()

        # Progress + status
        prog = ttk.Frame(self)
        prog.pack(fill=tk.X, **pad)
        self.progress = ttk.Progressbar(prog, mode="determinate")
        self.progress.pack(fill=tk.X, side=tk.TOP)
        self.status_var = tk.StringVar(value="idle")
        ttk.Label(prog, textvariable=self.status_var).pack(anchor=tk.W, pady=(2, 0))

        # Log
        log_frame = ttk.LabelFrame(self, text="Log")
        log_frame.pack(fill=tk.BOTH, expand=True, **pad)
        self.log = tk.Text(log_frame, height=12, wrap="none", state="disabled",
                           background="#111", foreground="#ddd", insertbackground="#ddd")
        self.log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        lsb = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log.yview)
        lsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.log.config(yscrollcommand=lsb.set)

        # Action buttons
        action = ttk.Frame(self)
        action.pack(fill=tk.X, **pad)
        self.go_btn = ttk.Button(action, text="Securely delete", command=self.start_delete)
        self.go_btn.pack(side=tk.RIGHT)
        self.cancel_btn = ttk.Button(action, text="Cancel", command=self.cancel, state="disabled")
        self.cancel_btn.pack(side=tk.RIGHT, padx=6)

        # Warning footer
        warn = ("Warning: on SSD / USB / SD card, wear-leveling means user-space "
                "overwrite is NOT guaranteed. For SSDs, full-disk encryption + TRIM "
                "or vendor Secure Erase is the only reliable solution.")
        ttk.Label(self, text=warn, foreground="#a60", wraplength=720, justify=tk.LEFT).pack(
            fill=tk.X, padx=8, pady=(0, 8)
        )

    def _try_enable_dnd(self):
        """Enable drag & drop if tkinterdnd2 is installed; otherwise silently skip."""
        try:
            from tkinterdnd2 import DND_FILES, TkinterDnD  # noqa: F401
            # Re-init root as DnD-aware would require restructuring; instead bind on listbox.
            self.listbox.drop_target_register(DND_FILES)  # type: ignore[attr-defined]
            self.listbox.dnd_bind("<<Drop>>", self._on_drop)  # type: ignore[attr-defined]
        except Exception:
            pass  # DnD optional

    def _on_drop(self, event):
        # event.data may be like: {C:/a b/c} {D:/x}
        raw = event.data
        paths = self._split_dnd_paths(raw)
        for p in paths:
            self._add_path(p)

    @staticmethod
    def _split_dnd_paths(s):
        out, buf, in_brace = [], "", False
        for ch in s:
            if ch == "{":
                in_brace = True
            elif ch == "}":
                in_brace = False
                if buf:
                    out.append(buf); buf = ""
            elif ch == " " and not in_brace:
                if buf:
                    out.append(buf); buf = ""
            else:
                buf += ch
        if buf:
            out.append(buf)
        return out

    # ---------- target list ops ----------
    def _add_path(self, p):
        p = os.path.normpath(p)
        if not os.path.exists(p):
            return
        if p in self.listbox.get(0, tk.END):
            return
        self.listbox.insert(tk.END, p)

    def add_files(self):
        paths = filedialog.askopenfilenames(title="Select files to securely delete")
        for p in paths:
            self._add_path(p)

    def add_folder(self):
        p = filedialog.askdirectory(title="Select a folder to securely delete", mustexist=True)
        if p:
            self._add_path(p)

    def remove_selected(self):
        for i in reversed(self.listbox.curselection()):
            self.listbox.delete(i)

    def clear_all(self):
        self.listbox.delete(0, tk.END)

    # ---------- run ----------
    def start_delete(self):
        if self.worker and self.worker.is_alive():
            return
        if not self.bash_exe or not SH_SCRIPT.is_file():
            messagebox.showerror("Cannot run", "Git Bash or secure_delete.sh is missing.")
            return

        targets = list(self.listbox.get(0, tk.END))
        if not targets:
            messagebox.showinfo("Nothing to do", "Add some files or folders first.")
            return

        # Final confirmation
        preview = "\n".join(targets[:10]) + ("\n..." if len(targets) > 10 else "")
        confirm = ConfirmDialog(self, preview, len(targets))
        self.wait_window(confirm)
        if not confirm.confirmed:
            return

        self._set_log("")
        self.progress.config(value=0, maximum=len(targets))
        self.status_var.set("starting...")
        self.go_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")

        self.worker = ShredWorker(self.bash_exe, targets, self.passes_var.get(), self.msg_q)
        self.worker.start()

    def cancel(self):
        if self.worker and self.worker.is_alive():
            if messagebox.askyesno("Cancel", "Stop after the current file?"):
                self.worker.cancel()
                self.status_var.set("cancelling...")

    # ---------- queue pump ----------
    def _poll_queue(self):
        try:
            while True:
                msg = self.msg_q.get_nowait()
                kind = msg[0]
                if kind == "log":
                    self._append_log(msg[1])
                elif kind == "status":
                    self.status_var.set(msg[1])
                elif kind == "progress":
                    cur, total = msg[1], msg[2]
                    self.progress.config(value=cur, maximum=total)
                elif kind == "done":
                    ok, total = msg[1], msg[2]
                    self.status_var.set(f"done: {ok}/{total} succeeded")
                    self.go_btn.config(state="normal")
                    self.cancel_btn.config(state="disabled")
                    # Remove successfully processed items from the list
                    # (anything that still exists is left so the user can retry)
                    self._prune_deleted()
                    messagebox.showinfo("Finished", f"{ok} of {total} targets securely deleted.")
        except queue.Empty:
            pass
        self.after(80, self._poll_queue)

    def _prune_deleted(self):
        remaining = []
        for p in self.listbox.get(0, tk.END):
            if os.path.exists(p):
                remaining.append(p)
        self.listbox.delete(0, tk.END)
        for p in remaining:
            self.listbox.insert(tk.END, p)

    # ---------- log ----------
    def _set_log(self, text):
        self.log.config(state="normal")
        self.log.delete("1.0", tk.END)
        self.log.insert(tk.END, text)
        self.log.config(state="disabled")

    def _append_log(self, text):
        self.log.config(state="normal")
        self.log.insert(tk.END, text)
        self.log.see(tk.END)
        self.log.config(state="disabled")


class ConfirmDialog(tk.Toplevel):
    """Type-DELETE confirmation."""

    def __init__(self, parent, preview, count):
        super().__init__(parent)
        self.title("Confirm secure delete")
        self.resizable(False, False)
        self.confirmed = False
        self.transient(parent)
        self.grab_set()

        ttk.Label(
            self,
            text=f"You are about to PERMANENTLY destroy {count} target(s):",
            font=("Segoe UI", 10, "bold"),
        ).pack(padx=14, pady=(14, 6), anchor=tk.W)

        txt = tk.Text(self, height=8, width=70, wrap="none")
        txt.insert("1.0", preview)
        txt.config(state="disabled", background="#f5f5f5")
        txt.pack(padx=14)

        ttk.Label(self, text='Type DELETE to confirm:').pack(padx=14, pady=(10, 2), anchor=tk.W)
        self.entry = ttk.Entry(self, width=30)
        self.entry.pack(padx=14, anchor=tk.W)
        self.entry.focus_set()

        btns = ttk.Frame(self)
        btns.pack(fill=tk.X, padx=14, pady=12)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(btns, text="Delete", command=self._ok).pack(side=tk.RIGHT, padx=6)

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())

    def _ok(self):
        if self.entry.get().strip() == "DELETE":
            self.confirmed = True
            self.destroy()
        else:
            messagebox.showwarning("Not confirmed", 'Please type exactly: DELETE')


if __name__ == "__main__":
    try:
        # Better DPI on Windows
        if os.name == "nt":
            import ctypes
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                pass
        app = App()
        app.mainloop()
    except Exception as e:
        try:
            messagebox.showerror("Fatal", str(e))
        except Exception:
            print(e, file=sys.stderr)
            raise

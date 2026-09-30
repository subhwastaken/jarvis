"""Developer and File Intelligence Tools for J.A.R.V.I.S."""
import os
import subprocess
import re
from jarvis_memory import load_memory

def get_default_project_dirs():
    dirs = [
        os.path.expanduser("~/Developer"),
        os.path.expanduser("~/Projects"),
        os.path.expanduser("~/Documents"),
        os.getcwd()
    ]
    custom = os.getenv("JARVIS_PROJECT_DIRS", "")
    if custom:
        for p in custom.split(":"):
            clean = p.strip()
            if clean and os.path.exists(clean) and clean not in dirs:
                dirs.insert(0, os.path.abspath(clean))
    return [d for d in dirs if os.path.exists(d)]

DEFAULT_PROJECT_DIRS = get_default_project_dirs()


def get_active_repo(must_be_git=False):
    # 1. Smart Active Window Detection (Cursor, VS Code, Terminal)
    try:
        script = 'tell application "System Events" to get title of front window of (first application process whose frontmost is true)'
        res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=1)
        if res.returncode == 0:
            title = res.stdout.strip().lower()
            for d in DEFAULT_PROJECT_DIRS:
                bname = os.path.basename(d).lower()
                if bname in title and os.path.exists(d):
                    if not must_be_git or os.path.exists(os.path.join(d, ".git")):
                        return d
    except Exception:
        pass

    # 2. Check current working directory
    cwd = os.getcwd()
    if not must_be_git or os.path.exists(os.path.join(cwd, ".git")):
        return cwd

    # 3. Check memory preferences
    mem = load_memory()
    primary = mem.get("user_profile", {}).get("primary_projects", [])
    for p in primary:
        for d in DEFAULT_PROJECT_DIRS:
            if os.path.basename(d).lower() == p.lower() and os.path.exists(d):
                if not must_be_git or os.path.exists(os.path.join(d, ".git")):
                    return d
    for d in DEFAULT_PROJECT_DIRS:
        if os.path.exists(d):
            if not must_be_git or os.path.exists(os.path.join(d, ".git")):
                return d
    return os.path.dirname(os.path.abspath(__file__))


def get_git_summary(repo_path=None):
    path = repo_path or get_active_repo(must_be_git=True)
    try:
        branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=path, stderr=subprocess.DEVNULL).decode().strip() or "detached"
        status_out = subprocess.check_output(["git", "status", "--porcelain"], cwd=path, stderr=subprocess.DEVNULL).decode().strip()
        lines = [l for l in status_out.splitlines() if l.strip()]
        modified = len([l for l in lines if l.startswith(" M") or l.startswith("M ")])
        untracked = len([l for l in lines if l.startswith("??")])
        repo_name = os.path.basename(path)
        
        if not lines:
            return f"In the {repo_name} repository, you are on branch {branch}. Working tree is completely clean, sir."
        
        parts = []
        if modified:
            parts.append(f"{modified} modified file{'s' if modified > 1 else ''}")
        if untracked:
            parts.append(f"{untracked} untracked file{'s' if untracked > 1 else ''}")
        details = " and ".join(parts) if parts else "uncommitted changes"
        return f"In {repo_name}, you are currently on branch {branch} with {details}, sir."
    except Exception as e:
        return f"I was unable to retrieve git status for {os.path.basename(path)}: {e}"


def get_last_commit(repo_path=None):
    path = repo_path or get_active_repo(must_be_git=True)
    try:
        log_out = subprocess.check_output(["git", "log", "-1", "--pretty=format:%s (%cr) by %an"], cwd=path, stderr=subprocess.DEVNULL).decode().strip()
        repo_name = os.path.basename(path)
        return f"The latest commit in {repo_name} is: {log_out}, sir."
    except Exception as e:
        return f"Could not fetch latest commit: {e}"


IGNORE_DIRS = {'node_modules', '.git', '.venv', 'dist', 'build', '__pycache__', '.next', 'cache'}


def read_project_file(filename, repo_path=None):
    path = os.path.abspath(repo_path or get_active_repo())
    clean_name = filename.strip(" /'\"`")
    target_path = os.path.abspath(os.path.join(path, clean_name))

    # Path traversal protection
    try:
        if os.path.commonpath([path, target_path]) != path:
            return "Access denied: the requested path is outside the project boundaries, sir."
    except Exception:
        return "Access denied: the requested path is outside the project boundaries, sir."

    if not os.path.exists(target_path):
        found = None
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
            for f in files:
                if f.lower() == clean_name.lower():
                    found = os.path.join(root, f)
                    break
            if found:
                break
        if found:
            target_path = found
        else:
            return f"I could not locate {clean_name} in {os.path.basename(path)}, sir."

    try:
        with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        count = len(lines)
        head = " ".join(l.strip() for l in lines[:6] if l.strip())
        # Clean markdown symbols, HTML tags, and code delimiters for smooth speech
        head_clean = re.sub(r'<[^>]+>', '', head)
        head_clean = re.sub(r'[*#`_>|~-]', ' ', head_clean)
        head_clean = re.sub(r'\s+', ' ', head_clean).strip()[:180]
        return f"{os.path.basename(target_path)} contains {count} lines. It begins with: {head_clean}, sir."
    except Exception as e:
        return f"Failed to read file {clean_name}: {e}"


def list_project_files(repo_path=None):
    path = repo_path or get_active_repo()
    try:
        entries = [f for f in os.listdir(path) if not f.startswith(".")][:8]
        items = ", ".join(entries)
        return f"Top level items in {os.path.basename(path)} include: {items}, sir."
    except Exception as e:
        return f"Failed to list project files: {e}"

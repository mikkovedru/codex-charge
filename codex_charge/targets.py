"""Discover selectable Codex chats and desktop windows without changing them."""
from __future__ import annotations

import json
import os
import socket
import sqlite3
import stat
import sys
from contextlib import closing
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import quote


@dataclass(frozen=True)
class Target:
    kind: str
    id: str
    title: str
    instance: str = ""
    pid: int | None = None
    endpoint: str = ""
    deeplink: str = ""
    cwd: str = ""
    status: str = ""
    owner_id: str = ""
    task_status: str = "Unavailable"
    goal_status: str = "Unavailable"
    # None marks legacy selections; the GUI persists explicit booleans.
    send_prompt: bool | None = None
    send_goal: bool | None = None
    project_name: str = ""

    def signal_actions(self, legacy_goal=False):
        return (True if self.send_prompt is None else self.send_prompt,
                legacy_goal and self.kind == "thread" if self.send_goal is None else self.send_goal)

    @property
    def key(self):
        return json.dumps([self.kind, self.instance, self.id], separators=(",", ":"))

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        return cls(**{key: value[key] for key in cls.__dataclass_fields__ if key in value})


@dataclass
class Inventory:
    targets: list[Target] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def codex_home():
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))


def _thread_target(record, home, ipc):
    thread_id = record["id"]
    return Target("thread", thread_id, record.get("name") or record.get("title") or thread_id,
        instance=str(home), endpoint=ipc,
        deeplink=f"codex://threads/{quote(thread_id, safe='')}", cwd=record.get("cwd", ""),
        status="Saved chat", task_status=task_status(record.get("status")))


def task_status(value):
    if not isinstance(value, dict):
        return "Unavailable"
    kind = value.get("type")
    if kind == "active":
        flags = value.get("activeFlags") or []
        waiting = [label for flag, label in (("waitingOnApproval", "Waiting for approval"),
            ("waitingOnUserInput", "Waiting for input")) if flag in flags]
        return " / ".join(waiting) if waiting else "Running"
    return {"idle": "Idle", "notLoaded": "Not loaded", "systemError": "Error"}.get(kind, "Unavailable")


def goal_status(value):
    return {"active": "Active", "paused": "Paused", "blocked": "Blocked",
        "usageLimited": "Usage limited", "usage_limited": "Usage limited",
        "budgetLimited": "Budget limited", "budget_limited": "Budget limited",
        "complete": "Complete"}.get(value, "Unavailable")


def _saved_goals(home):
    """Read only persisted goal statuses. None means this schema is unavailable."""
    databases = sorted((p for p in home.glob("goals_*.sqlite")
        if p.stem.split("_")[-1].isdigit()),
        key=lambda p: int(p.stem.split("_")[-1]), reverse=True)
    for database in databases:
        with closing(sqlite3.connect(f"file:{quote(str(database))}?mode=ro", uri=True, timeout=1)) as db:
            columns = {r[1] for r in db.execute("PRAGMA table_info(thread_goals)")}
            if not {"thread_id", "status"} <= columns:
                continue
            return dict(db.execute("SELECT thread_id,status FROM thread_goals"))
    return None


class AppServer:
    """Read metadata from an existing daemon. Never launch a second server."""
    def __init__(self, path):
        self.path = path
        self.counter = 0
        self.connection = None

    def __enter__(self):
        import websocket
        info = Path(self.path).stat()
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
            raise OSError("Control socket is not owned by this user")
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(4)
        try:
            sock.connect(self.path)
            self.connection = websocket.create_connection("ws://localhost/", socket=sock,
                timeout=4, suppress_origin=True)
            init = self.call("initialize", {"clientInfo": {"name": "codex-charge", "version": "1.1.1"}})
            self.home = Path(init["codexHome"])
            self.connection.send(json.dumps({"method": "initialized"}))
        except Exception:
            sock.close()
            if self.connection:
                self.connection.close()
            raise
        return self

    def __exit__(self, *_):
        self.connection.close()

    def call(self, method, params):
        import time
        self.counter += 1
        self.connection.send(json.dumps({"id": self.counter, "method": method, "params": params}))
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            self.connection.settimeout(max(.01, deadline - time.monotonic()))
            response = json.loads(self.connection.recv())
            if response.get("id") == self.counter:
                if "error" in response:
                    raise RuntimeError(response["error"]["message"])
                return response["result"]
        raise TimeoutError("Codex metadata request timed out")

    def threads(self):
        cursor = None
        seen = set()
        records = []
        while True:
            response = self.call("thread/list", {"limit": 100, "cursor": cursor,
                "sortKey": "updated_at", "useStateDbOnly": True,
                "sourceKinds": ["cli", "vscode", "appServer", "exec", "unknown"]})
            records.extend(response["data"])
            cursor = response.get("nextCursor")
            if not cursor:
                return records
            if cursor in seen:
                raise RuntimeError("Codex returned a repeated pagination cursor")
            seen.add(cursor)


def _saved_threads(home):
    # SQLite is a read-only fallback, with column checks for schema changes.
    databases = sorted(home.glob("state_*.sqlite"),
        key=lambda p: int(p.stem.split("_")[-1]), reverse=True)
    for database in databases:
        with sqlite3.connect(f"file:{quote(str(database))}?mode=ro", uri=True, timeout=1) as db:
            db.row_factory = sqlite3.Row
            columns = {r[1] for r in db.execute("PRAGMA table_info(threads)")}
            if not {"id", "title", "archived"} <= columns:
                continue
            fields = [name for name in ("id", "name", "title", "cwd", "source") if name in columns]
            order = "updated_at DESC" if "updated_at" in columns else "id"
            records = [dict(row) for row in db.execute(
                f"SELECT {','.join(fields)} FROM threads WHERE archived=0 ORDER BY {order}")]
            return [r for r in records if not str(r.get("source", "")).startswith('{"subagent"')]
    return []


def _saved_project_names(home):
    """Read Codex's project labels and explicit memberships, never infer from cwd.

    Newer backends persist projects and thread membership in SQLite. Desktop
    releases also retain legacy assignments in their global state during the
    migration; those assignments are necessary even with a projects table.
    """
    names, memberships = None, {}
    databases = sorted((p for p in home.glob("state_*.sqlite")
        if p.stem.split("_")[-1].isdigit()),
        key=lambda p: int(p.stem.split("_")[-1]), reverse=True)
    for database in databases:
        with closing(sqlite3.connect(f"file:{quote(str(database))}?mode=ro", uri=True, timeout=1)) as db:
            projects = {r[1] for r in db.execute("PRAGMA table_info(projects)")}
            threads = {r[1] for r in db.execute("PRAGMA table_info(threads)")}
            if not {"id", "name"} <= projects:
                continue
            names = dict(db.execute("SELECT id,name FROM projects"))
            if {"id", "project_id"} <= threads:
                memberships = dict(db.execute("SELECT id,project_id FROM threads WHERE project_id IS NOT NULL"))
            break
    state_file = home / ".codex-global-state.json"
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
    if not isinstance(state, dict):
        raise ValueError("Unsupported Codex project state")
    def mapping(value):
        return value if isinstance(value, dict) else {}
    projects = mapping(state.get("local-projects"))
    assignments = mapping(state.get("thread-project-assignments"))
    hosts = mapping(state.get("thread-project-membership-host-ids"))
    migrations = mapping(mapping(state.get("app-server-project-id-by-legacy-project-id-by-host")).get(f"local:{home}"))
    result = {}
    for thread_id, assignment in assignments.items():
        if not isinstance(assignment, dict) or assignment.get("projectKind") != "local" or hosts.get(thread_id, "local") != "local":
            continue
        project_id = assignment.get("projectId")
        if not isinstance(project_id, str):
            continue
        if names is not None:
            name = names.get(migrations.get(project_id, project_id), "")
        else:
            name = mapping(projects.get(project_id)).get("name", "")
        if isinstance(name, str):
            result[thread_id] = name
    # Explicit projectless decisions override old desktop assignments. Native
    # memberships take precedence when a chat has since moved to a new project.
    projectless = state.get("projectless-thread-ids", [])
    if isinstance(projectless, list):
        for thread_id in projectless:
            if isinstance(thread_id, str):
                result[thread_id] = ""
    for thread_id, project_id in memberships.items():
        name = (names or {}).get(project_id, "")
        result[thread_id] = name if isinstance(name, str) else ""
    return result


def discover_windows():
    if sys.platform.startswith("linux"):
        from Xlib import display
        connection = display.Display()
        try:
            root = connection.screen().root
            prop = root.get_full_property(connection.intern_atom("_NET_CLIENT_LIST"), 0)
            windows = []
            for xid in ([] if prop is None else prop.value):
                try:
                    window = connection.create_resource_object("window", int(xid))
                    wmclass = " ".join(window.get_wm_class() or ())
                    # Match application identity, never generic title text (browsers etc.).
                    if not any(token in wmclass.lower() for token in ("chatgpt", "codex")) or "codex-charge" in wmclass.lower():
                        continue
                    pid_prop = window.get_full_property(connection.intern_atom("_NET_WM_PID"), 0)
                    pid = int(pid_prop.value[0]) if pid_prop is not None else None
                    name = window.get_full_property(connection.intern_atom("_NET_WM_NAME"), 0)
                    title = name.value.decode("utf-8", errors="replace") if name is not None else window.get_wm_name() or wmclass
                    windows.append(Target("window", str(int(xid)), title,
                        instance=f"{os.environ.get('DISPLAY', '')}:{pid}", pid=pid,
                        status="Current chat in this window"))
                except Exception:
                    continue  # A window can close while inventory is being read.
            return windows
        finally:
            connection.close()
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        windows = []
        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def callback(hwnd, _):
            if not user32.IsWindowVisible(hwnd):
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            # Query process executable to avoid matching a browser's page title.
            kernel32 = ctypes.windll.kernel32
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            process = kernel32.OpenProcess(0x1000, False, pid.value)
            if not process:
                return True
            try:
                buf = ctypes.create_unicode_buffer(32768)
                size = wintypes.DWORD(len(buf))
                if not kernel32.QueryFullProcessImageNameW(process, 0, buf, ctypes.byref(size)):
                    return True
                if Path(buf.value).stem.lower() not in {"codex", "chatgpt"}:
                    return True
            finally:
                kernel32.CloseHandle(process)
            title = ctypes.create_unicode_buffer(user32.GetWindowTextLengthW(hwnd) + 1)
            user32.GetWindowTextW(hwnd, title, len(title))
            windows.append(Target("window", str(hwnd), title.value,
                instance=f"windows:{pid.value}", pid=pid.value, status="Current chat in this window"))
            return True
        user32.EnumWindows(callback, 0)
        return windows
    raise RuntimeError("Window discovery supports Linux X11 and Windows")


def discover_homes():
    homes = {codex_home().resolve()}
    # Each Codex profile can have a different CODEX_HOME. Read only that field
    # from same-user Codex processes; do not collect credentials or other env.
    if sys.platform.startswith("linux"):
        for process in Path("/proc").iterdir():
            if not process.name.isdigit():
                continue
            try:
                if process.stat().st_uid != os.getuid():
                    continue
                if (process / "exe").resolve().name.lower() not in {"codex", "chatgpt"}:
                    continue
                values = (process / "environ").read_bytes().split(b"\0")
                value = next((v.split(b"=", 1)[1] for v in values if v.startswith(b"CODEX_HOME=")), None)
                if value:
                    homes.add(Path(os.fsdecode(value)).resolve())
            except OSError:
                continue
    return homes


def discover_targets():
    from dataclasses import replace
    from .codex_ipc import DesktopIPC
    inventory = Inventory()
    try:
        inventory.targets.extend(discover_windows())
    except Exception as exc:
        inventory.warnings.append(f"Window discovery: {exc}")
    homes = discover_homes()
    records_by_home = {}
    if sys.platform.startswith("linux"):
        directory = Path(f"/tmp/codex-daemon-{os.getuid()}")
        try:
            endpoints = list(directory.iterdir()) if directory.exists() else []
            for endpoint in endpoints:
                if not stat.S_ISSOCK(endpoint.stat().st_mode):
                    continue
                try:
                    with AppServer(str(endpoint)) as server:
                        home = server.home.resolve()
                        records_by_home[home] = server.threads()
                        homes.add(home)
                except Exception as exc:
                    inventory.warnings.append(f"Codex daemon metadata: {exc}")
        except OSError as exc:
            inventory.warnings.append(f"Control socket discovery: {exc}")
    for home in sorted(homes):
        ipc = str(home / "ipc/ipc.sock") if (home / "ipc/ipc.sock").exists() else ""
        records = records_by_home.get(home)
        if records is None:
            try:
                records = _saved_threads(home)
            except (OSError, sqlite3.Error, ValueError) as exc:
                records = []
                inventory.warnings.append(f"Saved chat discovery: {exc}")
        try:
            goals = _saved_goals(home)
        except (OSError, sqlite3.Error) as exc:
            goals = None
            inventory.warnings.append(f"Goal status unavailable: {exc}")
        try:
            project_names = _saved_project_names(home)
        except (OSError, sqlite3.Error, ValueError) as exc:
            project_names = {}
            inventory.warnings.append(f"Project names unavailable: {exc}")
        targets = [replace(_thread_target(r, home, ipc), project_name=project_names.get(r["id"], "")) for r in records]
        if goals is not None:
            targets = [replace(t, goal_status=goal_status(goals[t.id]) if t.id in goals else "No goal")
                       for t in targets]
        if ipc and targets and sys.platform.startswith("linux"):
            try:
                with DesktopIPC(ipc, timeout=3) as desktop:
                    for index, target in enumerate(targets):
                        try:
                            owner = desktop.owner(target.id)
                            targets[index] = replace(target, status="Open in desktop", owner_id=owner, task_status="Unavailable")
                        except RuntimeError as exc:
                            if str(exc) != "no-client-found":
                                inventory.warnings.append(f"Desktop owner discovery: {exc}")
                                break
                    for index, target in enumerate(targets):
                        if not target.owner_id:
                            continue
                        try:
                            snapshot = desktop.status_snapshot(target.id, target.owner_id)
                            current_goal = target.goal_status
                            if snapshot["goal"] is not None:
                                # A cached completed goal must not hide a newer
                                # goal that is persisted but not yet hydrated.
                                if snapshot.get("goal_current") or current_goal in {"No goal", "Unavailable", "Complete"}:
                                    current_goal = goal_status(snapshot["goal"])
                            elif goals is None and snapshot.get("goal_available"):
                                current_goal = "No goal"
                            targets[index] = replace(target,
                                task_status=task_status(snapshot["task"]), goal_status=current_goal)
                        except Exception as exc:
                            # A partial frame or timeout makes this connection unsafe
                            # to reuse. Preserve owner discovery and persisted goals.
                            inventory.warnings.append(f"Live task status unavailable: {exc}")
                            break
            except Exception as exc:
                inventory.warnings.append(f"Desktop routing: {exc}")
        # Native goal control from another connection updates shared persisted
        # state without notifying the desktop's cached goal immediately. Read
        # again after snapshots so that cache cannot hide the newer native state.
        try:
            fresh_goals = _saved_goals(home)
            if fresh_goals is not None:
                targets = [replace(target, goal_status=goal_status(fresh_goals[target.id]))
                           if target.id in fresh_goals else target for target in targets]
        except (OSError, sqlite3.Error) as exc:
            inventory.warnings.append(f"Latest goal status unavailable: {exc}")
        inventory.targets.extend(targets)
        if records and not ipc:
            inventory.warnings.append(f"Desktop routing unavailable for {home}; saved chats can be opened using their links.")
    return inventory

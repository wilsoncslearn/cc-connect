"""Release one desktop task through native archive/restore UI; never kill a writer."""
import argparse
import base64
import ctypes as C
from contextlib import closing, contextmanager
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import subprocess
import time


class Refused(Exception):
    pass


class NotRequested(Refused):
    """Desktop helper verified that it did not invoke any state-changing button."""


def require(ok, message):
    if not ok:
        raise Refused(message)


def filetime(t):
    return (t.dwHighDateTime << 32) | t.dwLowDateTime


class UniqueProcess(C.Structure):
    _fields_ = [('pid', W.DWORD), ('start', W.FILETIME)]


class ProcessInfo(C.Structure):
    _fields_ = [('process', UniqueProcess), ('app', W.WCHAR * 256),
                ('service', W.WCHAR * 64), ('kind', C.c_int), ('status', W.ULONG),
                ('session', W.DWORD), ('restartable', W.BOOL)]


class Overlapped(C.Structure):
    _fields_ = [('internal', C.c_size_t), ('internal_high', C.c_size_t),
                ('offset', W.DWORD), ('offset_high', W.DWORD), ('event', W.HANDLE)]


class Windows:
    def __init__(self):
        require(os.name == 'nt', '仅支持 Windows；没有执行任何解锁。')
        self.k = C.WinDLL('kernel32', use_last_error=True)
        self.r = C.WinDLL('Rstrtmgr', use_last_error=True)
        signatures = [
            (self.k, 'OpenProcess', [W.DWORD, W.BOOL, W.DWORD], W.HANDLE),
            (self.k, 'CloseHandle', [W.HANDLE], W.BOOL),
            (self.k, 'GetProcessTimes', [W.HANDLE] + [C.POINTER(W.FILETIME)] * 4, W.BOOL),
            (self.k, 'QueryFullProcessImageNameW', [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)], W.BOOL),
            (self.k, 'CreateFileW', [W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p, W.DWORD, W.DWORD, W.HANDLE], W.HANDLE),
            (self.k, 'LockFileEx', [W.HANDLE, W.DWORD, W.DWORD, W.DWORD, W.DWORD, C.POINTER(Overlapped)], W.BOOL),
            (self.r, 'RmStartSession', [C.POINTER(W.DWORD), W.DWORD, W.LPWSTR], W.DWORD),
            (self.r, 'RmRegisterResources', [W.DWORD, W.UINT, C.POINTER(W.LPCWSTR), W.UINT, C.POINTER(UniqueProcess), W.UINT, C.POINTER(W.LPCWSTR)], W.DWORD),
            (self.r, 'RmGetList', [W.DWORD, C.POINTER(W.UINT), C.POINTER(W.UINT), C.POINTER(ProcessInfo), C.POINTER(W.DWORD)], W.DWORD),
            (self.r, 'RmEndSession', [W.DWORD], W.DWORD),
        ]
        for dll, name, args, result in signatures:
            fn = getattr(dll, name)
            fn.argtypes, fn.restype = args, result

    def locked(self, path):
        # OPEN_EXISTING, never create/truncate; closing releases the probe lock.
        if not path.exists():
            return False
        h = self.k.CreateFileW(str(path), 0xC0000000, 7, None, 3, 0x00200000, None)
        if h == C.c_void_p(-1).value:
            raise C.WinError(C.get_last_error())
        try:
            ok = self.k.LockFileEx(h, 3, 0, 1, 0, C.byref(Overlapped()))
            if ok:
                return False
            error = C.get_last_error()
            if error == 33:  # ERROR_LOCK_VIOLATION, not a permissions error
                return True
            raise C.WinError(error)
        finally:
            self.k.CloseHandle(h)

    def owners(self, path):
        handle, key = W.DWORD(), C.create_unicode_buffer(33)
        err = self.r.RmStartSession(C.byref(handle), 0, key)
        require(err == 0, f'无法启动文件占用查询：{err}')
        try:
            files = (W.LPCWSTR * 1)(str(path))
            err = self.r.RmRegisterResources(handle, 1, files, 0, None, 0, None)
            require(err == 0, f'无法查询目标文件：{err}')
            for _ in range(3):
                needed, count, reason = W.UINT(), W.UINT(), W.DWORD()
                err = self.r.RmGetList(handle, C.byref(needed), C.byref(count), None, C.byref(reason))
                if err == 0:
                    return []
                require(err == 234, f'占用查询失败：{err}')
                items = (ProcessInfo * needed.value)()
                count.value = needed.value
                err = self.r.RmGetList(handle, C.byref(needed), C.byref(count), items, C.byref(reason))
                if err == 234:
                    continue
                require(err == 0, f'占用查询失败：{err}')
                return sorted((x.process.pid, filetime(x.process.start)) for x in items[:count.value])
            raise Refused('占用者正在变化，请稍后重新诊断。')
        finally:
            self.r.RmEndSession(handle)

    def open_process(self, pid):
        # Query-only access: this command cannot terminate the lock owner.
        h = self.k.OpenProcess(0x1000, False, pid)
        if not h:
            raise C.WinError(C.get_last_error())
        return h

    def identity(self, handle):
        times = [W.FILETIME() for _ in range(4)]
        if not self.k.GetProcessTimes(handle, *(C.byref(t) for t in times)):
            raise C.WinError(C.get_last_error())
        buf, size = C.create_unicode_buffer(32768), W.DWORD(32768)
        if not self.k.QueryFullProcessImageNameW(handle, 0, buf, C.byref(size)):
            raise C.WinError(C.get_last_error())
        return {'start': filetime(times[0]), 'exe': buf.value}

    def close(self, handle):
        self.k.CloseHandle(handle)


def thread_id(value):
    require(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', value),
            '需要完整的小写会话 ID；不接受路径或进程号。')
    return value


def resolved_path(path):
    # Codex stores Windows extended-length paths (\\?\); compare their normal form.
    value = str(path.resolve())
    if value.startswith('\\\\?\\UNC\\'):
        value = '\\\\' + value[8:]
    elif value.startswith('\\\\?\\'):
        value = value[4:]
    return Path(value)


def path_inside(path, parent):
    resolved, parent = resolved_path(path), resolved_path(parent)
    require(resolved.is_relative_to(parent) and resolved != parent, '路径越出允许的数据目录。')
    return resolved


def lock_path(home, tid):
    directory = home / 'thread-writer-locks'
    require(directory.resolve() == directory, '锁目录不能是目录链接。')
    path = directory / (thread_id(tid) + '.lock')
    require(path.resolve() == path, '拒绝操作重定向的锁文件。')
    return path


def thread_row(home, tid):
    database = path_inside(home / 'state_5.sqlite', home)
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=2)) as db:
        db.row_factory = sqlite3.Row
        row = db.execute('SELECT id, title, name, cwd, rollout_path, archived, is_pinned FROM threads WHERE id=?', (tid,)).fetchone()
    require(row is not None, '本机数据库中没有这个会话。')
    return dict(row)


def snapshot(api, home, workspace, tid):
    target = lock_path(home, tid)
    row = thread_row(home, tid)
    require(resolved_path(Path(row['cwd'])) == resolved_path(workspace), '目标会话不属于此命令配置的项目。')
    require(api.locked(target), '当前未检测到写入锁占用，可回原会话重试。')
    owners = api.owners(target)
    require(len(owners) == 1, '无法唯一确认占用者，未释放写入锁。')
    pid, started = owners[0]
    h = api.open_process(pid)
    try:
        identity = api.identity(h)
    finally:
        api.close(h)
    require(identity['start'] == started, '进程身份已变化，请重新诊断。')
    require(Path(identity['exe']).name.lower() == 'codex.exe', '占用者不是 Codex，未释放写入锁。')
    require(api.locked(target) and api.owners(target) == owners, '占用者已变化，请重新检查。')
    return {'thread': tid, 'pid': pid, **identity}


def authorise(request, store, tid=None):
    require(isinstance(request, dict), '请求格式错误。')
    args = request.get('args')
    if args is None:
        args = []
    require(isinstance(args, list) and len(args) <= 3 and all(isinstance(a, str) and len(a) <= 128 for a in args), '参数格式错误。')
    key, user = request.get('session_key'), request.get('user_id')
    require(isinstance(key, str) and key and isinstance(user, str) and user, '缺少可信的命令来源。')
    # Only threads already bound to this sender's chat, not arbitrary local IDs.
    allowed = set()
    for sid in store.get('user_sessions', {}).get(key, []):
        session = store['sessions'].get(sid, {})
        allowed.add(session.get('agent_session_id'))
    if tid is not None:
        require(tid in allowed, '这个会话没有绑定到当前聊天，拒绝操作。请先 /switch 到目标会话。')
    return args, {'session_key': key, 'user_id': user}


def audit(state, event, **fields):
    with (state / 'audit.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps({'time': time.time(), 'event': event, **fields}, ensure_ascii=False) + '\n')



def desktop_action(action, row, current=None):
    # No shell interpolation: all task data travels as JSON on stdin.
    script = Path(__file__).with_name('unlock-desktop.ps1')
    require(script.is_file(), '缺少桌面释放脚本，未执行操作。')
    command = [str(Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'),
               '-NoLogo', '-NoProfile', '-NonInteractive', '-File', str(script)]
    data = {'action': action, 'title': row['name'] or row['title'],
            'project': os.environ.get('CC_UNLOCK_DESKTOP_PROJECT', '').strip() or resolved_path(Path(row['cwd'])).name,
            'owner_pid': current['pid'] if current else None,
            'owner_start': current['start'] if current else None}
    result = subprocess.run(command, input=json.dumps(data, ensure_ascii=True),
                            text=True, encoding='utf-8', errors='replace', capture_output=True,
                            timeout=45, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        response = json.loads(result.stdout)
    except ValueError:
        raise Refused('桌面操作结果未知：' + (result.stderr or result.stdout)[-1800:].strip()) from None
    if result.returncode != 0:
        error = NotRequested if response.get('attempted') is False else Refused
        raise error('桌面操作失败：' + str(response.get('error', '未知错误')))
    require(response.get('action') == action, '桌面返回了不匹配的操作结果。')


def wait_archived(home, tid, expected):
    deadline = time.monotonic() + 8
    while True:
        if bool(thread_row(home, tid)['archived']) == expected:
            return
        require(time.monotonic() < deadline, '桌面归档状态未在期限内更新，不能确认操作完成。')
        time.sleep(0.1)


def desktop_title(home, row):
    title = row['name'] or row['title']
    require(isinstance(title, str) and title.strip(), '目标没有可精确定位的桌面名称。')
    with closing(sqlite3.connect((home / 'state_5.sqlite').as_uri() + '?mode=ro', uri=True)) as db:
        matches = db.execute("SELECT id FROM threads WHERE COALESCE(NULLIF(name,''),title)=?", (title,)).fetchall()
    require(matches == [(row['id'],)], '存在同名任务，拒绝按名称操作；请先为目标设置唯一名称。')
    return title


def restore_pending(home, state, row):
    pending = state / (row['id'] + '.pending.json')
    if not pending.exists():
        return False
    record = json.loads(pending.read_text(encoding='utf-8'))
    require(record == {'thread': row['id'], 'title': desktop_title(home, row), 'cwd': row['cwd']},
            '待恢复记录与任务身份不一致；未操作桌面。')
    require(row['archived'], '上次归档请求结果不确定，请先在桌面检查目标；不会重复归档。')
    desktop_action('restore', row)
    wait_archived(home, row['id'], False)
    pending.unlink()
    audit(state, 'restored_pending', thread=row['id'])
    return True


def release_desktop(api, home, state, row, current):
    title = desktop_title(home, row)
    require(not row['archived'], '目标原本已归档，不自动取消用户的归档。')
    require(not row['is_pinned'], '为保留置顶位置，请先取消目标任务置顶再 /unlock。')
    pending = state / (row['id'] + '.pending.json')
    # Durable recovery marker before the native action; never edit Codex history/DB.
    with pending.open('x', encoding='utf-8') as f:
        json.dump({'thread': row['id'], 'title': title, 'cwd': row['cwd']}, f, ensure_ascii=False)
    audit(state, 'release_requested', thread=row['id'], pid=current['pid'])
    try:
        desktop_action('archive', row, current)
        wait_archived(home, row['id'], True)
    except NotRequested:
        pending.unlink()
        audit(state, 'release_not_requested', thread=row['id'])
        raise
    finally:
        # Even if the archive helper fails after invoking its button, restore it.
        if pending.exists() and thread_row(home, row['id'])['archived']:
            desktop_action('restore', row)
            wait_archived(home, row['id'], False)
            pending.unlink()
    require(not pending.exists(), '释放流程未完成，已保留恢复记录；不会假报成功。')
    h = api.open_process(current['pid'])
    try:
        require(api.identity(h) == {k: current[k] for k in ('start', 'exe')},
                '桌面后端身份已变化，不能确认安全释放。')
    finally:
        api.close(h)
    # A successful UI action isn't proof of release; probe the actual writer lock.
    for _ in range(3):
        require(not api.locked(lock_path(home, row['id'])), '任务已恢复，但写入锁仍被占用；请勿同时在桌面打开它。')
        time.sleep(0.1)
    audit(state, 'released_verified', thread=row['id'], pid=current['pid'])


@contextmanager
def command_guard(state):
    import msvcrt
    # ponytail: serialize this small UI transaction globally; no background daemon.
    with (state / 'desktop-ui.lock').open('a+b') as f:
        if f.tell() == 0:
            f.write(b'0'); f.flush()
        f.seek(0)
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise Refused('另一个 /unlock 正在操作桌面，请稍后再试。') from None
        try:
            yield
        finally:
            f.seek(0); msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)

def handle_request(api, home, workspace, state, request, store):
    args, _ = authorise(request, store)
    require(not args or args[0] != 'confirm',
            '强制终止和旧确认码已停用；不会结束桌面后端。请使用 /unlock check 查看占用。')
    check_only = bool(args and args[0] == 'check')
    if check_only:
        args = args[1:]
    require(len(args) <= 1, '用法：/unlock [完整会话ID]；/unlock check [完整会话ID] 只诊断。')
    if args:
        tid = thread_id(args[0])
    else:
        sid = store.get('active_session', {}).get(request['session_key'])
        tid = thread_id(store.get('sessions', {}).get(sid, {}).get('agent_session_id'))
    authorise(request, store, tid)
    row = thread_row(home, tid)
    require(resolved_path(Path(row['cwd'])) == resolved_path(workspace), '目标会话不属于此命令配置的项目。')
    recovered = not check_only and restore_pending(home, state, row)
    if recovered:
        row = thread_row(home, tid)
    require(not row['archived'], '目标仍处于归档状态，未恢复手机任务。')
    if not api.locked(lock_path(home, tid)):
        audit(state, 'already_unlocked', thread=tid)
        if recovered:
            return '已恢复上次中断的任务，当前未检测到写入锁占用；请在手机原会话重发消息。'
        return '当前未检测到写入锁占用；没有执行释放操作，请在手机原会话重发消息。'
    current = snapshot(api, home, workspace, tid)
    details = f"目标：{tid}\n占用 PID：{current['pid']}\n程序：{current['exe']}"
    if check_only:
        audit(state, 'diagnosed', thread=tid, pid=current['pid'])
        return details + '\n仅检查，未释放写入锁，也未结束任何进程。'
    release_desktop(api, home, state, row, current)
    return f'已释放任务 {tid}：桌面已归档后恢复，写入锁验证通过。\n桌面后端保持运行；请在手机原会话重发消息。'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, default=Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')))
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--store', type=Path, required=True)
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--request-b64', required=True)
    options = parser.parse_args()
    try:
        require(len(options.request_b64) <= 8192, '请求过长。')
        request = json.loads(base64.b64decode(options.request_b64, validate=True))
        store = json.loads(options.store.read_text(encoding='utf-8-sig'))
        authorise(request, store)
        home, workspace, state = (resolved_path(p) for p in (options.home, options.workspace, options.state_dir))
        state.mkdir(parents=True, exist_ok=True)
        api = Windows()
        with command_guard(state):
            result = handle_request(api, home, workspace, state, request, store)
        print(result)
        return 0
    except (Refused, OSError, ValueError, KeyError, TypeError, sqlite3.Error, subprocess.SubprocessError) as e:
        print(f'拒绝执行或未完成：{e}\n没有结束任何进程；不会删除写入锁文件、改写聊天内容或强制接管。若提示待恢复，请勿删除 pending 记录。')
        return 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())

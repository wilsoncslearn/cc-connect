"""Run: python -m unittest discover -s deploy/personal -p test_unlock.py -v.
No processes are terminated. The native child releases its lock cooperatively.
"""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import unlock as u

TID = '00000000-0000-0000-0000-000000000001'
OTHER = '00000000-0000-0000-0000-000000000002'


class FakeWindows:
    def __init__(self):
        self.users = [(71, 900)]
        self.ident = {'start': 900, 'exe': 'C:/Codex/codex.exe'}
        self.busy = True
        self.kills = []

    def locked(self, path): return self.busy
    def owners(self, path): return self.users
    def open_process(self, pid): return pid
    def identity(self, handle): return dict(self.ident)
    def close(self, handle): pass
    def terminate(self, handle):
        raise AssertionError("Process termination must never be called")


class RecoveryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve()
        self.workspace = self.home / 'project'
        self.workspace.mkdir()
        self.state = self.home / 'tickets'
        self.state.mkdir()
        (self.home / 'thread-writer-locks').mkdir()
        (self.home / 'thread-writer-locks' / '.coordination.lock').touch()
        with closing(sqlite3.connect(self.home / 'state_5.sqlite')) as db, db:
            db.execute('CREATE TABLE threads (id TEXT, title TEXT, cwd TEXT, rollout_path TEXT, name TEXT, archived INTEGER DEFAULT 0, is_pinned INTEGER DEFAULT 0)')
        self.add_thread(TID)
        self.req = {'args': [], 'session_key': 'test:chat:owner', 'user_id': 'owner'}
        self.store = {'sessions': {'s1': {'agent_session_id': TID}},
                      'user_sessions': {self.req['session_key']: ['s1']},
                      'active_session': {self.req['session_key']: 's1'}}
        self.api = FakeWindows()

    def add_thread(self, tid):
        (self.home / 'thread-writer-locks' / (tid + '.lock')).touch()
        rollout = self.home / (tid + '.jsonl')
        rollout.write_text('{}\n', encoding='utf-8')
        with closing(sqlite3.connect(self.home / 'state_5.sqlite')) as db, db:
            db.execute('INSERT INTO threads (id,title,cwd,rollout_path) VALUES (?, ?, ?, ?)',
                       (tid, 'test task', str(self.workspace), str(rollout)))

    def run_command(self, args):
        return u.handle_request(self.api, self.home, self.workspace, self.state,
                                {**self.req, 'args': args}, self.store)

    def set_archived(self, value):
        with closing(sqlite3.connect(self.home / 'state_5.sqlite')) as db, db:
            db.execute('UPDATE threads SET archived=? WHERE id=?', (value, TID))

    def mock_desktop(self, action, row, current=None):
        self.set_archived(action == 'archive')
        if action == 'archive': self.api.busy = False

    def test_one_command_archives_restores_and_verifies_without_killing(self):
        with patch.object(u, 'desktop_action', side_effect=self.mock_desktop) as action:
            result = self.run_command([])
        self.assertIn('写入锁验证通过', result)
        self.assertEqual([c.args[0] for c in action.call_args_list], ['archive', 'restore'])
        self.assertFalse(u.thread_row(self.home, TID)['archived'])
        self.assertFalse(list(self.state.glob('*.pending.json')))
        self.assertFalse(hasattr(u.Windows, 'terminate'))
        self.assertFalse(hasattr(u, 'confirm'))

    def test_refusal_before_ui_action_allows_retry(self):
        with patch.object(u, 'desktop_action', side_effect=u.NotRequested('hidden or busy')):
            for _ in range(2):
                with self.assertRaisesRegex(u.Refused, 'hidden or busy'): self.run_command([])
        self.assertTrue(self.api.busy)
        self.assertFalse(list(self.state.glob('*.pending.json')))

    def test_restore_runs_even_if_archive_errors_after_changing_state(self):
        def action(mode, row, current=None):
            self.mock_desktop(mode, row, current)
            if mode == 'archive': raise u.Refused('late failure')
        with patch.object(u, 'desktop_action', side_effect=action) as actions:
            with self.assertRaisesRegex(u.Refused, 'late failure'): self.run_command([])
        self.assertEqual([c.args[0] for c in actions.call_args_list], ['archive', 'restore'])
        self.assertFalse(u.thread_row(self.home, TID)['archived'])

    def test_failed_restore_journal_is_recovered_on_next_unlock(self):
        def action(mode, row, current=None):
            if mode == 'restore': raise u.NotRequested('window unavailable')
            self.mock_desktop(mode, row, current)
        with patch.object(u, 'desktop_action', side_effect=action):
            with self.assertRaisesRegex(u.Refused, 'window unavailable'): self.run_command([])
        self.assertTrue(u.thread_row(self.home, TID)['archived'])
        self.assertTrue(list(self.state.glob('*.pending.json')))
        with patch.object(u, 'desktop_action', side_effect=self.mock_desktop) as actions:
            self.assertIn('已恢复上次中断的任务', self.run_command([]))
        self.assertEqual([c.args[0] for c in actions.call_args_list], ['restore'])
        self.assertFalse(u.thread_row(self.home, TID)['archived'])

    def test_buttons_succeed_but_lock_remains_must_not_report_success(self):
        def action(mode, row, current=None): self.set_archived(mode == 'archive')
        with patch.object(u, 'desktop_action', side_effect=action):
            with self.assertRaisesRegex(u.Refused, '写入锁仍被占用'): self.run_command([])
        events = [json.loads(line)['event'] for line in
                  (self.state / 'audit.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertNotIn('released_verified', events)

    def test_ambiguous_title_pinned_and_existing_archive_are_not_touched(self):
        with patch.object(u, 'desktop_action', side_effect=AssertionError('must not operate')):
            self.add_thread(OTHER)
            with self.assertRaisesRegex(u.Refused, '同名'): self.run_command([])
            with closing(sqlite3.connect(self.home / 'state_5.sqlite')) as db, db:
                db.execute('DELETE FROM threads WHERE id=?', (OTHER,))
                db.execute('UPDATE threads SET is_pinned=1')
            with self.assertRaisesRegex(u.Refused, '置顶'): self.run_command([])
            self.set_archived(True)
            with self.assertRaisesRegex(u.Refused, '归档状态'): self.run_command([])

    def test_check_only_and_no_lock(self):
        for args in [['check'], ['check', TID]]:
            self.assertIn('未释放写入锁', self.run_command(args))
        self.api.busy = False
        for args in [[], [TID], ['check']]:
            self.assertIn('没有执行释放操作', self.run_command(args))
        self.assertTrue((self.home / 'thread-writer-locks' / (TID + '.lock')).exists())

    def test_legacy_confirmation_cannot_terminate_even_with_ticket(self):
        token = 'a' * 32
        ticket = self.state / (token + '.json')
        ticket.write_text('{"legacy": true}', encoding='utf-8')
        with self.assertRaisesRegex(u.Refused, '旧确认码已停用'):
            self.run_command(['confirm', token])
        self.assertTrue(ticket.exists())
        self.assertTrue(self.api.busy)

    def test_authorization_precedes_any_lock_access(self):
        self.add_thread(OTHER)
        for args in [[OTHER], ['check', OTHER], ['check', TID, 'extra'], ['confirm']]:
            with patch.object(self.api, 'locked', side_effect=AssertionError('must authorize first')):
                with self.assertRaises(u.Refused): self.run_command(args)
        with closing(sqlite3.connect(self.home / 'state_5.sqlite')) as db, db:
            db.execute('UPDATE threads SET cwd=?', (str(self.home),))
        with patch.object(self.api, 'locked', side_effect=AssertionError('must authorize first')):
            with self.assertRaises(u.Refused): self.run_command([])

    def test_refuse_unknown_ambiguous_non_codex_or_reused_pid(self):
        for users, exe, started in [([], 'codex.exe', 900),
                ([(71, 900), (72, 901)], 'codex.exe', 900),
                ([(71, 900)], 'python.exe', 900), ([(71, 900)], 'codex.exe', 901)]:
            with self.subTest(users=users, exe=exe, started=started):
                self.api.users = users
                self.api.ident = {'start': started, 'exe': exe}
                with self.assertRaises(u.Refused): self.run_command([])
        self.assertTrue(self.api.busy)

    def test_invalid_requests(self):
        for args in ['', False, {}, 0, ['a'] * 4, [2]]:
            with self.assertRaises(u.Refused): u.authorise({**self.req, 'args': args}, self.store)
        for tid in ['../x', '71', 'AAAAAAAA-0000-0000-0000-000000000001']:
            with self.assertRaises(u.Refused): u.thread_id(tid)
        for request in [{}, {**self.req, 'session_key': ''}, {**self.req, 'user_id': ''}]:
            with self.assertRaises(u.Refused): u.authorise(request, self.store)

    @unittest.skipUnless(os.name == 'nt', 'Windows extended path regression')
    def test_codex_extended_length_paths(self):
        prefix = chr(92) * 2 + '?' + chr(92)
        with closing(sqlite3.connect(self.home / 'state_5.sqlite')) as db, db:
            db.execute('UPDATE threads SET cwd=?', (prefix + str(self.workspace),))
        self.assertIn(TID, self.run_command(['check']))


@unittest.skipUnless(os.name == 'nt', 'Windows API integration')
class NativeTest(unittest.TestCase):
    def test_child_releases_lock_without_termination(self):
        api = u.Windows()
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / 'child.lock'
            child_code = """
import msvcrt, sys
with open(sys.argv[1], 'w+b') as f:
    f.write(b'x'); f.flush(); f.seek(0)
    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    print('locked', flush=True)
    sys.stdin.readline()
"""
            child = subprocess.Popen([sys.executable, '-u', '-c', child_code, str(lock)],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True)
            try:
                self.assertEqual(child.stdout.readline().strip(), 'locked')
                self.assertTrue(api.locked(lock))
                handle = api.open_process(child.pid)
                try:
                    identity = api.identity(handle)
                    self.assertEqual(api.owners(lock), [(child.pid, identity['start'])])
                finally:
                    api.close(handle)
            finally:
                child.communicate(input='release\n', timeout=5)
            self.assertEqual(child.returncode, 0)
            self.assertFalse(api.locked(lock))
            self.assertTrue(lock.exists())

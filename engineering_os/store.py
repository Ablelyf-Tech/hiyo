from __future__ import annotations
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


class Store:
    def __init__(self, home: Path):
        self.home = home.resolve()
        self.home.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.home / 'state.sqlite3'
        with self.db() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, brief TEXT NOT NULL,
                workspace TEXT NOT NULL UNIQUE, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                title TEXT NOT NULL, spec TEXT NOT NULL, checks TEXT NOT NULL,
                dependencies TEXT NOT NULL, priority INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'queued', stage TEXT NOT NULL DEFAULT 'queued',
                attempts INTEGER NOT NULL DEFAULT 0, available REAL NOT NULL DEFAULT 0,
                error TEXT, checkpoint TEXT, created REAL NOT NULL, updated REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, role TEXT,
                kind TEXT NOT NULL, data TEXT NOT NULL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY, started REAL NOT NULL, finished REAL,
                status TEXT NOT NULL, reserved REAL NOT NULL DEFAULT 0);
            ''')

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def project(self, name, brief, workspace):
        pid = uuid.uuid4().hex[:12]
        with self.db() as db:
            db.execute('INSERT INTO projects VALUES (?,?,?,?,?)',
                       (pid, name, brief, str(Path(workspace).resolve()), time.time()))
        return pid

    def task(self, project_id, title, spec, checks, dependencies=None, priority=0):
        if not checks or any(not isinstance(c, list) or not c or
                             any(not isinstance(a, str) or not a for a in c) for c in checks):
            raise ValueError('Acceptance checks must be nonempty argv arrays')
        tid = uuid.uuid4().hex[:12]
        now = time.time()
        with self.db() as db:
            for dep in dependencies or []:
                if not db.execute('SELECT id FROM tasks WHERE id=? AND project_id=?',
                                  (dep, project_id)).fetchone():
                    raise ValueError('Dependencies must already exist in this project')
            db.execute('''INSERT INTO tasks
                (id,project_id,title,spec,checks,dependencies,priority,created,updated)
                VALUES (?,?,?,?,?,?,?,?,?)''',
                       (tid, project_id, title, spec, json.dumps(checks),
                        json.dumps(dependencies or []), priority, now, now))
        return tid

    def event(self, task_id, role, kind, **data):
        event = dict(task_id=task_id, role=role, kind=kind, data=data, created=time.time())
        with self.db() as db:
            db.execute('INSERT INTO events(task_id,role,kind,data,created) VALUES (?,?,?,?,?)',
                       (task_id, role, kind, json.dumps(data), event['created']))
        # SQL is authoritative; JSONL is an append-only operational mirror.
        with (self.home / 'events.jsonl').open('a', encoding='utf-8') as f:
            f.write(json.dumps(event) + '\n')

    def update(self, tid, **fields):
        allowed = {'status', 'stage', 'attempts', 'available', 'error', 'checkpoint'}
        if set(fields) - allowed:
            raise ValueError('Invalid task update')
        fields['updated'] = time.time()
        with self.db() as db:
            db.execute('UPDATE tasks SET ' + ','.join(f'{k}=?' for k in fields) + ' WHERE id=?',
                       (*fields.values(), tid))

    def claim(self):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            rows = db.execute('''SELECT * FROM tasks WHERE status IN ('queued','retry')
                AND available<=? ORDER BY priority DESC, created''', (time.time(),)).fetchall()
            for row in rows:
                dependencies = json.loads(row['dependencies'])
                if any(not db.execute("SELECT id FROM tasks WHERE id=? AND status='completed'",
                                      (dep,)).fetchone() for dep in dependencies):
                    continue
                db.execute("UPDATE tasks SET status='running', attempts=attempts+1, updated=? WHERE id=?",
                           (time.time(), row['id']))
                return dict(db.execute('SELECT * FROM tasks WHERE id=?', (row['id'],)).fetchone())
        return None

    def recover(self):
        with self.db() as db:
            db.execute("UPDATE tasks SET status='blocked', error='Controller interrupted; inspect workspace and explicitly retry', updated=? WHERE status='running'", (time.time(),))
            db.execute("UPDATE runs SET status='interrupted', finished=? WHERE status='running'", (time.time(),))

    def snapshot(self):
        with self.db() as db:
            result = {table: [dict(r) for r in db.execute(f'SELECT * FROM {table} ORDER BY {order}')]
                      for table, order in [('projects', 'created'), ('tasks', 'created'), ('runs', 'started')]}
            result['events'] = [dict(r) for r in db.execute('SELECT * FROM events ORDER BY seq DESC LIMIT 150')]
        for event in result['events']:
            event['data'] = json.loads(event['data'])
        for task in result['tasks']:
            task['checks'] = json.loads(task['checks'])
            task['dependencies'] = json.loads(task['dependencies'])
        return result

from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from .store import Store
from .controller import Controller, Limits


def main():
    parser = argparse.ArgumentParser(description='Hiyo Engineering OS')
    parser.add_argument('--home', type=Path, default=Path.home() / '.hiyo')
    sub = parser.add_subparsers(dest='command', required=True)
    serve = sub.add_parser('serve')
    serve.add_argument('--projects-root', type=Path, required=True)
    serve.add_argument('--port', type=int, default=8787)
    serve.add_argument('--dashboard', type=Path, default=Path(__file__).resolve().parents[1] / 'dashboard' / 'dist')
    run = sub.add_parser('run')
    run.add_argument('--approve-codex-usage', action='store_true')
    run.add_argument('--max-seconds', type=int, default=3600)
    run.add_argument('--max-calls', type=int, default=20)
    run.add_argument('--estimated-budget', type=float, default=5)
    imp = sub.add_parser('import-plan')
    imp.add_argument('plan', type=Path)
    imp.add_argument('--workspace', type=Path, required=True)
    proposal = sub.add_parser('propose-plan')
    proposal.add_argument('--workspace', type=Path, required=True)
    proposal.add_argument('--brief', type=Path, required=True)
    proposal.add_argument('--output', type=Path, required=True)
    proposal.add_argument('--approve-codex-usage', action='store_true')
    sub.add_parser('status')
    sub.add_parser('stop')
    sub.add_parser('clear-stop')
    args = parser.parse_args()
    store = Store(args.home)
    if args.command == 'serve':
        if not (args.dashboard / 'index.html').is_file():
            parser.error('Dashboard build missing; run npm ci and npm run build in dashboard/')
        import uvicorn
        from .api import create_app
        app = create_app(args.home, args.projects_root, args.dashboard)
        print(f'Private dashboard on loopback port {args.port}. Login token: {store.home / "dashboard-token"}')
        uvicorn.run(app, host='127.0.0.1', port=args.port)
    elif args.command == 'run':
        if not args.approve_codex_usage:
            parser.error('--approve-codex-usage is required; review plans and acceptance commands first')
        controller = Controller(store, Limits(max_seconds=args.max_seconds, max_calls=args.max_calls,
                                             estimated_budget=args.estimated_budget))
        import signal
        signal.signal(signal.SIGINT, lambda *_: controller.stop.set())
        signal.signal(signal.SIGTERM, lambda *_: controller.stop.set())
        print(controller.run())
    elif args.command == 'import-plan':
        plan = json.loads(args.plan.read_text(encoding='utf-8'))
        # Validate entire document before writing anything.
        from .plans import import_plan
        print(import_plan(store, plan, args.workspace))
    elif args.command == 'propose-plan':
        if not args.approve_codex_usage:
            parser.error('--approve-codex-usage is required')
        from .planner import propose
        print(propose(store, args.workspace, args.brief.read_text(encoding='utf-8'), args.output))
        print('Review the proposed backlog and acceptance commands before import-plan.')
    elif args.command == 'status':
        print(json.dumps(store.snapshot(), indent=2))
    elif args.command == 'stop':
        (store.home / 'STOP').touch()
    elif args.command == 'clear-stop':
        # File removal alone never starts a worker.
        (store.home / 'STOP').unlink(missing_ok=True)


if __name__ == '__main__':
    main()

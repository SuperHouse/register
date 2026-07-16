#!/usr/bin/env python3
"""
Driver for exercising the Testomatic Circuit Board Register web app with a
real headless browser. See SKILL.md in this directory for the full workflow.

Requires: pyproj/venv has `playwright` + browsers installed
  (pip install playwright && playwright install chromium)
and the dev server already running (see `up` subcommand).

Login uses a dedicated automation account (skill-agent@example.local) rather
than a real user's credentials. Its password is generated locally and never
committed — see "Test account" in SKILL.md for how it's created.
"""
import argparse
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
LOGIN_EMAIL = "skill-agent@example.local"
PASSWORD_FILE = Path(__file__).parent / ".test-account-password"
PIDFILE = "/tmp/register-dev-server.pid"
LOGFILE = "/tmp/register-dev-server.log"


def _login_password():
    try:
        return PASSWORD_FILE.read_text().strip()
    except FileNotFoundError:
        print(
            f"no test account password at {PASSWORD_FILE} — run the "
            "'Test account' setup step in SKILL.md first",
            file=sys.stderr,
        )
        sys.exit(1)


def _server_up():
    try:
        urllib.request.urlopen(BASE_URL, timeout=2)
        return True
    except Exception:
        # Django redirects unauthenticated / to login (302); urlopen follows
        # redirects and still raises on non-2xx from the final hop in some
        # cases, so also accept a plain connection succeeding at all.
        try:
            urllib.request.urlopen(BASE_URL + "/accounts/login/", timeout=2)
            return True
        except Exception:
            return False


def cmd_up(args):
    if _server_up():
        print("already up:", BASE_URL)
        return
    proj_dir = args.project_dir
    with open(LOGFILE, "w") as log:
        proc = subprocess.Popen(
            ["bash", "-c", f"source venv/bin/activate && python manage.py runserver 8000"],
            cwd=proj_dir,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    with open(PIDFILE, "w") as f:
        f.write(str(proc.pid))
    for _ in range(30):
        if _server_up():
            print("started, pid", proc.pid)
            return
        time.sleep(1)
    print("server did not come up in time, see", LOGFILE, file=sys.stderr)
    sys.exit(1)


def cmd_down(args):
    try:
        with open(PIDFILE) as f:
            pid = int(f.read().strip())
        subprocess.run(["kill", str(pid)])
        print("stopped pid", pid)
    except FileNotFoundError:
        print("no pidfile — nothing to stop (server may have been started outside this driver)")


def _login(page):
    page.goto(f"{BASE_URL}/accounts/login/")
    page.fill('input[name="username"]', LOGIN_EMAIL)
    page.fill('input[name="password"]', _login_password())
    page.click('input[type="submit"]')
    page.wait_for_load_state("networkidle")


def cmd_shot(args):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        errors = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

        if not args.no_login:
            _login(page)

        page.goto(f"{BASE_URL}{args.path}")
        if args.wait:
            page.wait_for_selector(args.wait, timeout=10000)
        if args.click:
            page.click(args.click)
            time.sleep(0.3)  # let any CSS transition / re-render settle
        page.screenshot(path=args.out, full_page=True)
        browser.close()

        print("saved", args.out)
        if errors:
            print("console errors:", errors, file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_up = sub.add_parser("up", help="start the dev server if not already running")
    p_up.add_argument("--project-dir", default=".")
    p_up.set_defaults(func=cmd_up)

    p_down = sub.add_parser("down", help="stop the dev server, if this driver started it")
    p_down.set_defaults(func=cmd_down)

    p_shot = sub.add_parser("shot", help="log in, navigate, optionally click, then screenshot")
    p_shot.add_argument("path", help="URL path to visit, e.g. /parts/")
    p_shot.add_argument("out", help="output PNG path")
    p_shot.add_argument("--click", help="CSS selector to click before the screenshot")
    p_shot.add_argument("--wait", help="CSS selector to wait for before acting")
    p_shot.add_argument("--no-login", action="store_true", help="skip the login step")
    p_shot.set_defaults(func=cmd_shot)

    args = parser.parse_args()
    args.func(args)

#!/usr/bin/env python3
"""Claude Usage Tracker - Minimal menu bar app"""

import rumps
import subprocess
import json
import urllib.request
from datetime import datetime

# Refresh intervals in seconds
INTERVALS = {
    "Every 1 minute": 60,
    "Every 5 minutes": 300,
    "Every 30 minutes": 1800,
    "Every hour": 3600,
}

def get_usage():
    """Fetch usage from OAuth endpoint."""
    try:
        r = subprocess.run(
            ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
            capture_output=True, text=True
        )
        if r.returncode != 0:
            return None

        token = json.loads(r.stdout.strip()).get("claudeAiOauth", {}).get("accessToken")
        if not token:
            return None

        req = urllib.request.Request(
            "https://api.anthropic.com/api/oauth/usage",
            headers={
                "Authorization": f"Bearer {token}",
                "anthropic-beta": "oauth-2025-04-20",
                "User-Agent": "claude-code/2.0.31",
            }
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except:
        return None

def fmt_reset(iso):
    """Format reset time."""
    try:
        dt = datetime.fromisoformat(iso.replace("+00:00", "+0000").split(".")[0] + "+0000")
        diff = dt - datetime.now(dt.tzinfo)
        if diff.days == 0:
            h, m = diff.seconds // 3600, (diff.seconds % 3600) // 60
            return f"{h}h {m}m" if h else f"{m}m"
        return dt.strftime("%b %d")
    except:
        return "?"

class App(rumps.App):
    def __init__(self):
        super().__init__("Claude", title="...", quit_button=None)
        self.interval = 300  # Default 5 minutes
        self.timer = None

        # Usage menu items
        self.m5h = rumps.MenuItem("5-hour: ...")
        self.m7d = rumps.MenuItem("Weekly: ...")
        self.mson = rumps.MenuItem("Sonnet: ...")
        self.mext = rumps.MenuItem("Extra: ...")
        self.mupd = rumps.MenuItem("Updated: --")

        # Interval menu items
        self.interval_items = {}
        interval_menu = rumps.MenuItem("Refresh Interval")
        for label, secs in INTERVALS.items():
            item = rumps.MenuItem(label, callback=self.set_interval)
            item._seconds = secs
            self.interval_items[secs] = item
            interval_menu.add(item)

        self.menu = [
            self.m5h, self.m7d, self.mson, None,
            self.mext, None, self.mupd,
            rumps.MenuItem("Refresh", callback=self.refresh),
            None, interval_menu, None,
            rumps.MenuItem("Quit", callback=rumps.quit_application)
        ]

        self.update_interval_menu()
        self.refresh(None)
        self.start_timer()

    def update_interval_menu(self):
        for secs, item in self.interval_items.items():
            item.state = 1 if secs == self.interval else 0

    def set_interval(self, sender):
        self.interval = sender._seconds
        self.update_interval_menu()
        self.start_timer()

    def start_timer(self):
        if self.timer:
            self.timer.stop()
        self.timer = rumps.Timer(self.auto_refresh, self.interval)
        self.timer.start()

    def auto_refresh(self, _):
        self.refresh(None)

    def refresh(self, _):
        self.title = "..."
        u = get_usage()
        if not u:
            self.title = "?"
            return

        if h := u.get("five_hour"):
            p = int(h.get("utilization", 0))
            self.title = f"{p}%"
            self.m5h.title = f"5-hour: {p}% (resets {fmt_reset(h.get('resets_at', ''))})"

        if d := u.get("seven_day"):
            self.m7d.title = f"Weekly: {int(d.get('utilization', 0))}% (resets {fmt_reset(d.get('resets_at', ''))})"

        if s := u.get("seven_day_sonnet"):
            self.mson.title = f"Sonnet: {int(s.get('utilization', 0))}% (resets {fmt_reset(s.get('resets_at', ''))})"
        else:
            self.mson.title = "Sonnet: --"

        if (e := u.get("extra_usage")) and e.get("is_enabled"):
            self.mext.title = f"Extra: ${e.get('used_credits',0)/100:.2f}/${e.get('monthly_limit',0)/100:.0f} ({int(e.get('utilization',0))}%)"
        else:
            self.mext.title = "Extra: --"

        self.mupd.title = f"Updated: {datetime.now().strftime('%H:%M')}"

if __name__ == "__main__":
    App().run()

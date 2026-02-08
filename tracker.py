#!/usr/bin/env python3
"""
Claude Usage Tracker - macOS Menu Bar App
"""

import rumps
from datetime import datetime

from config import get_api_key, set_keychain_key
from anthropic_api import get_oauth_usage, format_reset_time


class ClaudeUsageTracker(rumps.App):

    def __init__(self):
        super().__init__(name="Claude Usage", title="...", quit_button=None)
        self.usage = None
        self.last_refresh = None
        self._build_menu()
        self._refresh_data(None)

    def _build_menu(self):
        self.menu.clear()

        # Session limits
        self.menu_5hr = rumps.MenuItem("5-hour: ...")
        self.menu_7day = rumps.MenuItem("Weekly: ...")
        self.menu_sonnet = rumps.MenuItem("Sonnet: ...")
        self.menu_extra = rumps.MenuItem("Extra: ...")

        self.menu.add(self.menu_5hr)
        self.menu.add(self.menu_7day)
        self.menu.add(self.menu_sonnet)
        self.menu.add(None)
        self.menu.add(self.menu_extra)
        self.menu.add(None)

        # Refresh
        self.menu_updated = rumps.MenuItem("Updated: Never")
        self.menu.add(self.menu_updated)

        refresh_btn = rumps.MenuItem("Refresh")
        refresh_btn.set_callback(self._refresh_data)
        self.menu.add(refresh_btn)

        self.menu.add(None)

        quit_btn = rumps.MenuItem("Quit")
        quit_btn.set_callback(lambda _: rumps.quit_application())
        self.menu.add(quit_btn)

    @rumps.timer(60)  # Refresh every minute
    def _auto_refresh(self, _):
        self._refresh_data(None)

    def _refresh_data(self, _):
        self.title = "..."

        try:
            self.usage = get_oauth_usage()
            self.last_refresh = datetime.now()
            self._update_display()
        except Exception as e:
            self.title = "Err"
            print(f"Error: {e}")

    def _update_display(self):
        if not self.usage:
            self.title = "?"
            return

        # Menu bar title: show 5-hour percentage
        five_hr = self.usage.get("five_hour")
        if five_hr:
            pct = int(five_hr.get("utilization", 0))
            self.title = f"{pct}%"
        else:
            self.title = "0%"

        # 5-hour session
        if five_hr:
            pct = int(five_hr.get("utilization", 0))
            reset = format_reset_time(five_hr.get("resets_at", ""))
            self.menu_5hr.title = f"5-hour: {pct}% (resets {reset})"
        else:
            self.menu_5hr.title = "5-hour: --"

        # 7-day
        seven_day = self.usage.get("seven_day")
        if seven_day:
            pct = int(seven_day.get("utilization", 0))
            reset = format_reset_time(seven_day.get("resets_at", ""))
            self.menu_7day.title = f"Weekly: {pct}% (resets {reset})"
        else:
            self.menu_7day.title = "Weekly: --"

        # Sonnet weekly
        sonnet = self.usage.get("seven_day_sonnet")
        if sonnet:
            pct = int(sonnet.get("utilization", 0))
            reset = format_reset_time(sonnet.get("resets_at", ""))
            self.menu_sonnet.title = f"Sonnet: {pct}% (resets {reset})"
        else:
            self.menu_sonnet.title = "Sonnet: --"

        # Extra usage
        extra = self.usage.get("extra_usage")
        if extra and extra.get("is_enabled"):
            used = extra.get("used_credits", 0) / 100  # cents to dollars
            limit = extra.get("monthly_limit", 0) / 100
            pct = int(extra.get("utilization", 0))
            self.menu_extra.title = f"Extra: ${used:.2f}/${limit:.0f} ({pct}%)"
        else:
            self.menu_extra.title = "Extra: disabled"

        # Updated time
        if self.last_refresh:
            self.menu_updated.title = f"Updated: {self.last_refresh.strftime('%H:%M:%S')}"


if __name__ == "__main__":
    ClaudeUsageTracker().run()

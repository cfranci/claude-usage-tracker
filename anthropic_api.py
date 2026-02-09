"""
Anthropic Admin API client for usage and cost reporting.
"""

import requests
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict


BASE_URL = "https://api.anthropic.com/v1"


@dataclass
class UsageData:
    """Container for usage statistics."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0

    def __add__(self, other: "UsageData") -> "UsageData":
        return UsageData(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            cost_usd=self.cost_usd + other.cost_usd,
        )


@dataclass
class ModelUsage:
    """Usage breakdown by model."""
    model: str
    usage: UsageData


@dataclass
class ApiKeyUsage:
    """Usage breakdown by API key."""
    key_id: str
    key_hint: str
    usage: UsageData


class AnthropicAdminAPI:
    """Client for Anthropic Admin API."""

    def __init__(self, admin_api_key: str):
        self.api_key = admin_api_key
        self.session = requests.Session()
        self.session.headers.update({
            "x-api-key": admin_api_key,
            "anthropic-version": "2023-06-01",
        })

    def _get_date_range(self, timeframe: str) -> tuple[str, str]:
        """Get start and end dates for a timeframe in ISO 8601 format."""
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if timeframe == "today":
            start = today_start
            end = now
        elif timeframe == "7days":
            start = today_start - timedelta(days=6)
            end = now
        elif timeframe == "30days":
            start = today_start - timedelta(days=29)
            end = now
        else:
            start = today_start
            end = now

        return start.strftime("%Y-%m-%dT%H:%M:%SZ"), end.strftime("%Y-%m-%dT%H:%M:%SZ")

    def get_usage(self, timeframe: str = "today") -> Optional[dict]:
        """
        Fetch usage data from the Admin API.

        Returns dict with:
        - total: UsageData
        - by_model: list[ModelUsage]
        - by_key: list[ApiKeyUsage]
        """
        start_date, end_date = self._get_date_range(timeframe)

        try:
            # Fetch usage grouped by model
            model_usage = self._fetch_usage(start_date, end_date, group_by="model")

            # Fetch usage grouped by API key
            key_usage = self._fetch_usage(start_date, end_date, group_by="api_key_id")

            # Fetch cost data
            cost_data = self._fetch_cost(start_date, end_date)

            return self._combine_data(model_usage, key_usage, cost_data)

        except Exception as e:
            print(f"API request failed: {e}")
            return None

    def _fetch_usage(self, start_date: str, end_date: str, group_by: str = None) -> list:
        """Fetch usage from the messages usage report endpoint."""
        url = f"{BASE_URL}/organizations/usage_report/messages"

        params = {
            "starting_at": start_date,
            "ending_at": end_date,
            "bucket_width": "1d",
        }

        if group_by:
            params["group_by[]"] = group_by

        response = self.session.get(url, params=params)
        response.raise_for_status()

        data = response.json()
        return data.get("data", [])

    def _fetch_cost(self, start_date: str, end_date: str) -> list:
        """Fetch cost data from the cost report endpoint."""
        url = f"{BASE_URL}/organizations/cost_report"

        # Cost endpoint requires full day boundaries
        # Parse dates and adjust to full days
        start_dt = datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%SZ")
        end_dt = datetime.strptime(end_date, "%Y-%m-%dT%H:%M:%SZ")

        # Start at beginning of start day, end at end of end day
        start_day = start_dt.replace(hour=0, minute=0, second=0)
        end_day = (end_dt + timedelta(days=1)).replace(hour=0, minute=0, second=0)

        params = {
            "starting_at": start_day.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ending_at": end_day.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except Exception:
            # If cost fetch fails, return empty - usage still works
            return []

    def _combine_data(self, model_usage: list, key_usage: list, cost_data: list) -> dict:
        """Combine usage and cost data into a unified structure."""
        result = {
            "total": UsageData(),
            "by_model": [],
            "by_key": [],
        }

        # Aggregate model usage across all time buckets, grouping by friendly name
        model_totals = defaultdict(lambda: {"input": 0, "output": 0})
        for bucket in model_usage:
            for item in bucket.get("results", []):
                raw_model = item.get("model", "unknown")
                friendly_name = self._friendly_model_name(raw_model)
                input_tokens = item.get("uncached_input_tokens", 0) + item.get("cache_read_input_tokens", 0)
                cache_creation = item.get("cache_creation", {})
                input_tokens += cache_creation.get("ephemeral_1h_input_tokens", 0)
                input_tokens += cache_creation.get("ephemeral_5m_input_tokens", 0)
                output_tokens = item.get("output_tokens", 0)

                model_totals[friendly_name]["input"] += input_tokens
                model_totals[friendly_name]["output"] += output_tokens

        # Create ModelUsage objects
        for model, tokens in model_totals.items():
            usage = UsageData(
                input_tokens=tokens["input"],
                output_tokens=tokens["output"],
                total_tokens=tokens["input"] + tokens["output"],
            )
            result["by_model"].append(ModelUsage(model=model, usage=usage))
            result["total"] = result["total"] + usage

        # Sort by total tokens descending
        result["by_model"].sort(key=lambda x: x.usage.total_tokens, reverse=True)

        # Aggregate API key usage
        key_totals = defaultdict(lambda: {"input": 0, "output": 0})
        for bucket in key_usage:
            for item in bucket.get("results", []):
                key_id = item.get("api_key_id") or "workbench"
                input_tokens = item.get("uncached_input_tokens", 0) + item.get("cache_read_input_tokens", 0)
                output_tokens = item.get("output_tokens", 0)

                key_totals[key_id]["input"] += input_tokens
                key_totals[key_id]["output"] += output_tokens

        # Create ApiKeyUsage objects
        for key_id, tokens in key_totals.items():
            if key_id == "workbench":
                hint = "Workbench"
            else:
                hint = f"...{key_id[-6:]}" if len(key_id) > 6 else key_id
            usage = UsageData(
                input_tokens=tokens["input"],
                output_tokens=tokens["output"],
                total_tokens=tokens["input"] + tokens["output"],
            )
            result["by_key"].append(ApiKeyUsage(key_id=key_id, key_hint=hint, usage=usage))

        # Sort by total tokens descending
        result["by_key"].sort(key=lambda x: x.usage.total_tokens, reverse=True)

        # Calculate total cost from cost data
        total_cost = 0.0
        for bucket in cost_data:
            for item in bucket.get("results", []):
                amount = float(item.get("amount", 0))
                total_cost += amount

        result["total"].cost_usd = total_cost

        return result

    def _friendly_model_name(self, model: str) -> str:
        """Convert model ID to friendly name."""
        if "opus" in model.lower():
            return "Opus"
        elif "sonnet" in model.lower():
            return "Sonnet"
        elif "haiku" in model.lower():
            return "Haiku"
        return model

    def test_connection(self) -> tuple[bool, str]:
        """Test if the API key is valid."""
        try:
            now = datetime.utcnow()
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)

            response = self.session.get(
                f"{BASE_URL}/organizations/usage_report/messages",
                params={
                    "starting_at": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "ending_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "bucket_width": "1d",
                }
            )

            if response.status_code == 200:
                return True, "Connected successfully"
            elif response.status_code == 401:
                return False, "Invalid API key"
            elif response.status_code == 403:
                return False, "API key lacks admin permissions"
            else:
                return False, f"API error: {response.status_code}"

        except requests.exceptions.RequestException as e:
            return False, f"Connection error: {str(e)}"


def format_tokens(count: int) -> str:
    """Format token count for display."""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    elif count >= 1_000:
        return f"{count / 1_000:.1f}K"
    else:
        return str(count)


def format_cost(amount: float) -> str:
    """Format cost in USD."""
    if amount >= 1000:
        return f"${amount:,.0f}"
    return f"${amount:.2f}"


def get_oauth_usage() -> Optional[dict]:
    """
    Fetch usage limits from Claude Code OAuth endpoint.
    Returns session utilization percentages and reset times.
    """
    import subprocess
    import json

    try:
        # Get OAuth token from macOS Keychain
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return None

        creds = json.loads(result.stdout.strip())
        token = creds.get("claudeAiOauth", {}).get("accessToken")
        if not token:
            return None

        # Fetch usage from OAuth endpoint
        resp = requests.get(
            "https://api.anthropic.com/api/oauth/usage",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "anthropic-beta": "oauth-2025-04-20",
                "User-Agent": "claude-code/2.1.34",
            },
            timeout=10
        )

        if resp.status_code != 200:
            return None

        return resp.json()

    except Exception as e:
        print(f"OAuth usage fetch failed: {e}")
        return None


def format_reset_time(iso_time: str | None) -> str:
    """Format ISO timestamp to friendly reset time."""
    if not iso_time:
        return "--"

    from datetime import datetime
    import re

    try:
        # Parse ISO format with timezone
        clean = re.sub(r'\.\d+', '', iso_time)  # Remove microseconds
        dt = datetime.fromisoformat(clean.replace('+00:00', '+0000'))

        now = datetime.now(dt.tzinfo)
        diff = dt - now

        if diff.days == 0:
            hours = diff.seconds // 3600
            mins = (diff.seconds % 3600) // 60
            if hours > 0:
                return f"{hours}h {mins}m"
            return f"{mins}m"
        elif diff.days == 1:
            return "Tomorrow"
        else:
            return dt.strftime("%b %d")
    except:
        return "?"

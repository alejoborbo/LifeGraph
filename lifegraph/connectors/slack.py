"""Slack connector — fetches threads from channels, stores as documents."""

from collections import defaultdict
from datetime import datetime, timezone

import requests

from lifegraph.config import SLACK_TOKEN, SLACK_CHANNELS, SLACK_WORKSPACE_URL
from lifegraph.connectors.base import BaseConnector
from lifegraph.db import upsert_document
from lifegraph.models import Document

API = "https://slack.com/api"


class SlackConnector(BaseConnector):
    def __init__(self):
        self.token = SLACK_TOKEN
        self.channel_filter = [
            c.strip() for c in SLACK_CHANNELS.split(",") if c.strip()
        ]
        self.workspace_url = SLACK_WORKSPACE_URL.rstrip("/")
        self.session = None
        self._channel_cache = {}  # id -> {name, id}

    def authenticate(self):
        if not self.token:
            raise ValueError(
                "SLACK_TOKEN not set. Create a Slack app at https://api.slack.com/apps "
                "with scopes: channels:history, channels:read, groups:history, groups:read, "
                "users:read. Add the bot/user token to .env as SLACK_TOKEN."
            )
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {self.token}"

        resp = self._api("auth.test")
        return resp["user"]

    def list_documents(self) -> list[dict]:
        return []  # sync() handles everything

    def fetch_content(self, doc_id: str) -> str:
        return ""

    def sync(self) -> int:
        if not self.session:
            self.authenticate()

        channels = self._resolve_channels()
        if not channels:
            print("  No channels to sync. Set SLACK_CHANNELS in .env.")
            return 0

        count = 0
        for ch in channels:
            print(f"  #{ch['name']}...", end="", flush=True)
            n = self._sync_channel(ch)
            print(f" {n} threads")
            count += n
        return count

    # ── Internal ──────────────────────────────────────────────

    def _api(self, method: str, **params) -> dict:
        resp = self.session.get(f"{API}/{method}", params=params)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack API error: {data.get('error', data)}")
        return data

    def _resolve_channels(self) -> list[dict]:
        """Resolve channel names/IDs to [{id, name}]."""
        # Fetch all joined channels
        channels = []
        cursor = None
        while True:
            params = {"types": "public_channel,private_channel", "limit": 200}
            if cursor:
                params["cursor"] = cursor
            data = self._api("conversations.list", **params)
            for ch in data.get("channels", []):
                if ch.get("is_member"):
                    channels.append({"id": ch["id"], "name": ch["name"]})
            cursor = data.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        self._channel_cache = {ch["id"]: ch for ch in channels}

        if not self.channel_filter:
            return channels

        # Filter to requested channels (match by name or ID)
        filtered = []
        for ch in channels:
            if ch["name"] in self.channel_filter or ch["id"] in self.channel_filter:
                filtered.append(ch)
        return filtered

    def _sync_channel(self, channel: dict) -> int:
        """Fetch messages from a channel, group into threads, store as documents."""
        messages = self._fetch_messages(channel["id"])
        if not messages:
            return 0

        # Group into threads: thread_ts -> [messages]
        threads = defaultdict(list)
        for msg in messages:
            ts = msg.get("thread_ts", msg["ts"])
            threads[ts].append(msg)

        # For threads with replies, fetch full thread (history only gives parent)
        for thread_ts, msgs in list(threads.items()):
            parent = msgs[0]
            reply_count = parent.get("reply_count", 0)
            if reply_count > 0 and len(msgs) <= 1:
                thread_msgs = self._fetch_thread(channel["id"], thread_ts)
                threads[thread_ts] = thread_msgs

        # Store each thread (or standalone message) as a document
        count = 0
        for thread_ts, msgs in threads.items():
            msgs.sort(key=lambda m: float(m["ts"]))

            # Skip very short standalone messages (< 20 chars, no thread)
            if len(msgs) == 1 and len(msgs[0].get("text", "")) < 20:
                continue

            text = self._format_thread(msgs)
            if not text.strip():
                continue

            parent = msgs[0]
            title = self._make_title(parent, channel["name"])
            created = datetime.fromtimestamp(
                float(parent["ts"]), tz=timezone.utc
            ).isoformat()

            # Build permalink
            ts_for_url = thread_ts.replace(".", "")
            source_url = (
                f"{self.workspace_url}/archives/{channel['id']}/p{ts_for_url}"
                if self.workspace_url
                else ""
            )

            doc = Document(
                id=None,
                title=title,
                source="slack",
                source_id=f"{channel['id']}:{thread_ts}",
                source_url=source_url,
                created_at=created,
                fetched_at=datetime.now(timezone.utc).isoformat(),
                raw_text=text,
            )
            upsert_document(doc)
            count += 1

        return count

    def _fetch_messages(self, channel_id: str) -> list[dict]:
        """Fetch recent messages from a channel (last 90 days)."""
        ninety_days_ago = datetime.now(timezone.utc).timestamp() - (90 * 86400)
        messages = []
        cursor = None
        while True:
            params = {
                "channel": channel_id,
                "limit": 200,
                "oldest": str(ninety_days_ago),
            }
            if cursor:
                params["cursor"] = cursor
            data = self._api("conversations.history", **params)
            for msg in data.get("messages", []):
                if msg.get("subtype") in ("channel_join", "channel_leave", "bot_message"):
                    continue
                messages.append(msg)
            cursor = data.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        return messages

    def _fetch_thread(self, channel_id: str, thread_ts: str) -> list[dict]:
        """Fetch all replies in a thread."""
        messages = []
        cursor = None
        while True:
            params = {"channel": channel_id, "ts": thread_ts, "limit": 200}
            if cursor:
                params["cursor"] = cursor
            data = self._api("conversations.replies", **params)
            messages.extend(data.get("messages", []))
            cursor = data.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        return messages

    def _format_thread(self, messages: list[dict]) -> str:
        """Format a thread into readable plain text."""
        lines = []
        for msg in messages:
            user = msg.get("user", "unknown")
            text = msg.get("text", "")
            ts = datetime.fromtimestamp(float(msg["ts"]), tz=timezone.utc)
            date_str = ts.strftime("%Y-%m-%d %H:%M")
            lines.append(f"[{date_str}] {user}: {text}")
        return "\n".join(lines)

    def _make_title(self, parent_msg: dict, channel_name: str) -> str:
        """Generate a title from the first message of a thread."""
        text = parent_msg.get("text", "")
        # Use first line, truncated
        first_line = text.split("\n")[0][:80].strip()
        if not first_line:
            first_line = "(no text)"
        ts = datetime.fromtimestamp(float(parent_msg["ts"]), tz=timezone.utc)
        date_str = ts.strftime("%b %-d")
        return f"#{channel_name} — {first_line} ({date_str})"

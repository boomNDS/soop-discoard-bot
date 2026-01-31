import pytest

from soop_discord_bot.core.storage import Storage
from soop_discord_bot.soop.poller import SoopPoller


class FakeClient:
    def __init__(self, live_ids):
        self.live_ids = set(live_ids)

    async def fetch_live_user_ids(self, target_ids):
        return self.live_ids


class FakeChannel:
    def __init__(self):
        self.messages = []

    async def send(self, message: str):
        self.messages.append(message)


class FakeBot:
    def __init__(self, channel):
        self._channel = channel

    def get_channel(self, channel_id: int):
        if channel_id == 123:
            return self._channel
        return None

    def get_guild(self, guild_id: int):
        class Guild:
            name = "TestGuild"

        return Guild()


@pytest.mark.asyncio
async def test_poller_sends_only_on_live_transition(tmp_path):
    db_path = tmp_path / "soop.db"
    storage = Storage(f"sqlite:///{db_path}")
    storage.add_link(
        "guild-1",
        "streamer-1",
        "123",
        "Custom {soop_channel_id} in {guild} at {notify_channel}",
    )

    channel = FakeChannel()
    bot = FakeBot(channel)

    class FakeNotifier:
        def __init__(self):
            self.messages = []

        async def enqueue(self, channel_id: int, content: str):
            if channel_id == 123:
                self.messages.append(content)

    notifier = FakeNotifier()

    client = FakeClient({"streamer-1"})
    poller = SoopPoller(client, storage, notifier, interval_seconds=1)

    await poller._poll_once(bot)
    assert len(notifier.messages) == 1
    assert notifier.messages[0] == "Custom streamer-1 in TestGuild at <#123>"

    await poller._poll_once(bot)
    assert len(notifier.messages) == 1

    client.live_ids = set()
    await poller._poll_once(bot)
    assert len(notifier.messages) == 1

    client.live_ids = {"streamer-1"}
    await poller._poll_once(bot)
    assert len(notifier.messages) == 2

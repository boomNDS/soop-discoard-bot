import pytest

from soupnotify.core.storage import Storage
from soupnotify.core.metrics import BotMetrics
from soupnotify.soop.poller import SoopPoller


class FakeClient:
    def __init__(self, live_ids, broad_no="123"):
        self.live_ids = set(live_ids)
        self.broad_no = broad_no

    async def fetch_live_user_ids(self, target_ids):
        return self.live_ids

    async def fetch_broad_info(self, streamer_id):
        return {
            "broadTitle": "Test title",
            "categoryName": "Test",
            "currentSumViewer": 5,
            "broadNo": self.broad_no,
        }


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
        "Custom {soop_channel_id} in {guild} at {notify_channel} {soop_url}",
    )

    channel = FakeChannel()
    bot = FakeBot(channel)

    class FakeNotifier:
        def __init__(self):
            self.messages = []
            self.embeds = []

        async def enqueue(self, channel_id: int, content: str | None, embed=None, view=None):
            if channel_id == 123:
                self.messages.append(content)
                self.embeds.append(embed)

    notifier = FakeNotifier()

    client = FakeClient({"streamer-1"}, broad_no="123")
    metrics = BotMetrics()
    poller = SoopPoller(
        client,
        storage,
        notifier,
        "https://play.sooplive.co.kr",
        metrics,
        interval_seconds=1,
    )

    await poller._poll_once(bot)
    assert len(notifier.messages) == 1
    assert (
        notifier.messages[0]
        == "Custom streamer-1 in TestGuild at <#123> https://play.sooplive.co.kr/streamer-1"
    )
    assert notifier.embeds[0] is not None

    await poller._poll_once(bot)
    assert len(notifier.messages) == 1

    client.live_ids = set()
    await poller._poll_once(bot)
    assert len(notifier.messages) == 1

    client.live_ids = {"streamer-1"}
    client.broad_no = "124"
    await poller._poll_once(bot)
    assert len(notifier.messages) == 2

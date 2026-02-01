from soupnotify.core.storage import Storage

from tests.conftest import apply_migrations


def test_storage_add_get_remove(tmp_path):
    db_path = tmp_path / "soop.db"
    database_url = f"sqlite:///{db_path}"
    apply_migrations(database_url)
    storage = Storage(database_url)

    storage.add_link("guild-1", "streamer-1", "channel-1", "Live: {soop_channel_id}")
    storage.add_link("guild-1", "streamer-2", "channel-2")

    links = storage.get_links("guild-1")
    assert {item["soop_channel_id"] for item in links} == {"streamer-1", "streamer-2"}
    assert next(item for item in links if item["soop_channel_id"] == "streamer-1")[
        "message_template"
    ] == "Live: {soop_channel_id}"

    updated = storage.set_template("guild-1", "streamer-1", "Updated {soop_channel_id}")
    assert updated is True
    links = storage.get_links("guild-1")
    assert next(item for item in links if item["soop_channel_id"] == "streamer-1")[
        "message_template"
    ] == "Updated {soop_channel_id}"

    removed = storage.remove_link("guild-1", "streamer-1")
    assert removed == 1

    remaining = storage.get_links("guild-1")
    assert len(remaining) == 1
    assert remaining[0]["soop_channel_id"] == "streamer-2"

    removed_all = storage.remove_link("guild-1")
    assert removed_all == 1
    assert storage.get_links("guild-1") == []


def test_storage_defaults_and_live_status(tmp_path):
    db_path = tmp_path / "soop.db"
    database_url = f"sqlite:///{db_path}"
    apply_migrations(database_url)
    storage = Storage(database_url)

    assert storage.get_default_notify_channel("guild-1") is None
    storage.set_default_notify_channel("guild-1", "channel-9")
    assert storage.get_default_notify_channel("guild-1") == "channel-9"
    storage.set_default_notify_channel("guild-1", None)
    assert storage.get_default_notify_channel("guild-1") is None

    storage.set_live_status("guild-1", "streamer-1", True, "111")
    storage.set_live_status("guild-1", "streamer-2", False, None)
    live = storage.load_live_status()
    assert live["guild-1:streamer-1"]["is_live"] is True
    assert live["guild-1:streamer-1"]["broad_no"] == "111"
    assert live["guild-1:streamer-1"]["last_notified_at"] is None
    assert live["guild-1:streamer-2"]["is_live"] is False

    storage.set_embed_template("guild-1", "Title {guild}", "Desc {soop_channel_id}", "FF5500")
    embed = storage.get_embed_template("guild-1")
    assert embed["title"] == "Title {guild}"
    assert embed["description"] == "Desc {soop_channel_id}"
    assert embed["color"] == "FF5500"


def test_storage_mentions(tmp_path):
    db_path = tmp_path / "soop.db"
    database_url = f"sqlite:///{db_path}"
    apply_migrations(database_url)
    storage = Storage(database_url)

    assert storage.get_mention("guild-1") == {"type": None, "value": None}
    storage.set_mention("guild-1", "everyone", None)
    assert storage.get_mention("guild-1") == {"type": "everyone", "value": None}
    storage.set_mention("guild-1", "role", "123")
    assert storage.get_mention("guild-1") == {"type": "role", "value": "123"}
    storage.set_mention("guild-1", None, None)
    assert storage.get_mention("guild-1") == {"type": None, "value": None}

from soop_discord_bot.core.storage import Storage


def test_storage_add_get_remove(tmp_path):
    db_path = tmp_path / "soop.db"
    storage = Storage(f"sqlite:///{db_path}")

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

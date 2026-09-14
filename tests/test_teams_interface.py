#!/usr/bin/env python3
"""Which service URL a Teams call is addressed to, and that nothing else ever is.

Microsoft requires the `serviceUrl` of the conversation itself; a hardcoded region sends every
call on a detour. The bot's bearer token goes to whichever host is called, so the chooser must
refuse any host that is not one of Microsoft's.
"""
import importlib
import logging
from types import SimpleNamespace

import pytest

import config as config_module
import teams_interface
from teams_interface import DEFAULT_SERVICE_URL
from teams_interface import TeamsInterface


STORED = "https://smba.trafficmanager.net/fr/8445aa6a-b1ff-4969-8fb4-490c952d4953/"
FORCED = "https://smba.trafficmanager.net/amer/"
GOV = "https://smba.infra.gov.teams.microsoft.us/teams/"


class FakeConnectorClient:
    def __init__(self, credentials, base_url):
        self.base_url = base_url
        self.conversations = self
        self.calls: list[tuple[str, str]] = []

    async def send_to_conversation(self, conversation_id, activity):
        self.calls.append(("send", conversation_id))
        return SimpleNamespace(id="activity-1")

    async def update_activity(self, conversation_id, activity_id, activity):
        self.calls.append(("update", activity_id))
        return SimpleNamespace(id=activity_id)

    async def delete_activity(self, conversation_id, activity_id):
        self.calls.append(("delete", activity_id))


def make(monkeypatch, forced=""):
    monkeypatch.setattr(teams_interface, "ConnectorClient", FakeConnectorClient)
    cfg = config_module.DefaultConfig()
    cfg.TEAMS_SERVICE_URL = forced
    return TeamsInterface(cfg)


# --- which URL is chosen ---


def test_stored_home_region_is_used(monkeypatch):
    assert make(monkeypatch)._conversations(STORED).base_url == STORED


def test_operator_override_beats_the_stored_region(monkeypatch):
    assert make(monkeypatch, forced=FORCED)._conversations(STORED).base_url == FORCED


def test_documented_global_endpoint_when_nothing_is_stored(monkeypatch):
    ti = make(monkeypatch)
    assert ti._conversations(None).base_url == DEFAULT_SERVICE_URL
    assert ti._conversations("").base_url == DEFAULT_SERVICE_URL


def test_one_client_per_service_url(monkeypatch, caplog):
    ti = make(monkeypatch)
    with caplog.at_level(logging.INFO, logger="teams_interface"):
        first = ti._conversations(STORED)
        assert ti._conversations(STORED) is first
        assert ti._conversations(None) is not first
    created = [r.message for r in caplog.records if "teams connector created" in r.message]
    # one log per distinct URL, none for the repeated call
    assert len(created) == 2
    assert STORED in created[0] and "(stored)" in created[0]
    assert DEFAULT_SERVICE_URL in created[1] and "(fallback)" in created[1]


# --- which URL is refused: the bearer token must never leave Microsoft's hosts ---


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/",
        "http://smba.trafficmanager.net/fr/x/",
        "ftp://smba.trafficmanager.net/",
        "https://smba.trafficmanager.net.evil.example/",
        "https://user@evil.example/smba.trafficmanager.net/",
    ],
)
def test_non_teams_stored_url_is_refused(monkeypatch, caplog, url):
    ti = make(monkeypatch)
    with caplog.at_level(logging.WARNING, logger="teams_interface"):
        assert ti._conversations(url).base_url == DEFAULT_SERVICE_URL
    assert any("refusing non-Teams service url" in r.message for r in caplog.records)


def test_non_teams_override_is_refused_too(monkeypatch):
    ti = make(monkeypatch, forced="https://evil.example/")
    assert ti._conversations(STORED).base_url == DEFAULT_SERVICE_URL


def test_sovereign_cloud_host_is_accepted(monkeypatch):
    assert make(monkeypatch)._conversations(GOV).base_url == GOV


# --- the public methods hand the region through ---


async def test_send_goes_to_the_stored_region(monkeypatch):
    ti = make(monkeypatch)
    activity_id = await ti.send_to_conversation("19:abc@thread.v2", "hello", service_url=STORED)
    assert activity_id == "activity-1"
    assert ti._clients[STORED].calls == [("send", "19:abc@thread.v2")]


async def test_update_goes_to_the_stored_region(monkeypatch):
    ti = make(monkeypatch)
    await ti.update_activity("19:abc@thread.v2", "activity-1", "edited", service_url=STORED)
    assert ti._clients[STORED].calls == [("update", "activity-1")]


async def test_delete_goes_to_the_stored_region(monkeypatch):
    ti = make(monkeypatch)
    await ti.delete_activity("19:abc@thread.v2", "activity-1", service_url=STORED)
    assert ti._clients[STORED].calls == [("delete", "activity-1")]


# --- the env var really reaches the config ---


def test_teams_service_url_is_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("TEAMS_SERVICE_URL", FORCED)
    try:
        importlib.reload(config_module)
        assert config_module.DefaultConfig().TEAMS_SERVICE_URL == FORCED
    finally:
        monkeypatch.delenv("TEAMS_SERVICE_URL")
        importlib.reload(config_module)
        assert config_module.DefaultConfig().TEAMS_SERVICE_URL == ""

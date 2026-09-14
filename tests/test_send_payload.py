#!/usr/bin/env python3
"""Guards for the caller-chosen `message_id` contract.

The point of the contract is that a caller which never saw the answer to its create call still
holds a usable handle, so replaying an id must be safe and must never post a second card.
"""
import json
import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app import send_payload


CONVERSATION_TOKEN_ID = 42

HOME_REGION = "https://smba.trafficmanager.net/fr/8445aa6a-b1ff-4969-8fb4-490c952d4953/"

TOKEN_ROW = {
    "conversation_teams_id": "19:abc@thread.v2",
    "conversation_reference_id": 7,
    "conversation_token_id": CONVERSATION_TOKEN_ID,
    "service_url": HOME_REGION,
}


def body(response):
    return json.loads(bytes(response.body))


async def test_server_generates_the_id_when_none_is_supplied(connection, teams):
    connection.fetchrow.side_effect = [TOKEN_ROW, {"message_id": uuid.uuid4()}]

    response = await send_payload(uuid.uuid4(), "hello")

    assert response.status_code == 201
    assert teams.await_count == 1
    # The conversation's own home region travels with the call, never a hardcoded one.
    assert teams.await_args.kwargs["service_url"] == HOME_REGION
    connection.transaction.assert_not_called()
    insert_sql, supplied_id, *_ = connection.fetchrow.call_args[0]
    assert "INSERT INTO message" in insert_sql
    assert supplied_id is None


async def test_supplied_id_is_locked_then_inserted(connection, teams):
    message_id = uuid.uuid4()
    connection.fetchrow.side_effect = [TOKEN_ROW, None, {"message_id": message_id}]

    response = await send_payload(uuid.uuid4(), "hello", message_id=message_id)

    assert response.status_code == 201
    assert body(response)["message_id"] == str(message_id)

    lock_sql, lock_key = connection.execute.call_args[0]
    assert "pg_advisory_xact_lock" in lock_sql
    assert lock_key == int.from_bytes(message_id.bytes[:8], "big", signed=True)
    connection.transaction.assert_called_once()

    insert_sql, supplied_id, *_ = connection.fetchrow.call_args[0]
    assert "INSERT INTO message" in insert_sql
    assert supplied_id == message_id


async def test_replay_in_the_same_conversation_sends_nothing(connection, teams):
    message_id = uuid.uuid4()
    connection.fetchrow.side_effect = [
        TOKEN_ROW,
        {"conversation_token_id": CONVERSATION_TOKEN_ID, "deleted_at": None},
    ]

    response = await send_payload(uuid.uuid4(), "hello", message_id=message_id)

    assert response.status_code == 200
    assert body(response)["message_id"] == str(message_id)
    teams.assert_not_awaited()


async def test_id_owned_by_another_conversation_is_refused(connection, teams):
    connection.fetchrow.side_effect = [
        TOKEN_ROW,
        {"conversation_token_id": CONVERSATION_TOKEN_ID + 1, "deleted_at": None},
    ]

    with pytest.raises(HTTPException) as exc:
        await send_payload(uuid.uuid4(), "hello", message_id=uuid.uuid4())

    assert exc.value.status_code == 409
    teams.assert_not_awaited()


async def test_replaying_a_deleted_id_is_gone(connection, teams):
    connection.fetchrow.side_effect = [
        TOKEN_ROW,
        {"conversation_token_id": CONVERSATION_TOKEN_ID, "deleted_at": "2026-09-09"},
    ]

    with pytest.raises(HTTPException) as exc:
        await send_payload(uuid.uuid4(), "hello", message_id=uuid.uuid4())

    assert exc.value.status_code == 410
    teams.assert_not_awaited()


async def test_unknown_conversation_token_is_refused(connection, teams):
    connection.fetchrow.side_effect = [None]

    with pytest.raises(HTTPException) as exc:
        await send_payload(uuid.uuid4(), "hello")

    assert exc.value.status_code == 400
    teams.assert_not_awaited()


async def test_update_is_addressed_at_the_stored_home_region(connection, monkeypatch):
    from app import MessageIdAndMessageOfAnyType
    from app import patch_activity
    import app as app_module

    update = AsyncMock(return_value="activity-id-1")
    monkeypatch.setattr(app_module.ti, "update_activity", update)
    message_id = uuid.uuid4()
    connection.fetchrow.side_effect = [
        {
            "conversation_teams_id": TOKEN_ROW["conversation_teams_id"],
            "activity_id": "activity-id-1",
            "deleted_at": None,
            "service_url": HOME_REGION,
        },
        {"message_id": message_id, "updated_at": "2026-09-14"},
    ]

    response = await patch_activity(MessageIdAndMessageOfAnyType(message_id=message_id, text="edited"))

    assert response.status_code == 201
    assert update.await_args_list[0].kwargs["service_url"] == HOME_REGION


async def test_delete_is_addressed_at_the_stored_home_region(connection, monkeypatch):
    from app import MessageId
    from app import delete_message
    import app as app_module

    delete = AsyncMock()
    monkeypatch.setattr(app_module.ti, "delete_activity", delete)
    message_id = uuid.uuid4()
    connection.fetchrow.side_effect = [
        {
            "message_id": message_id,
            "conversation_teams_id": TOKEN_ROW["conversation_teams_id"],
            "activity_id": "activity-id-1",
            "deleted_at": None,
            "service_url": HOME_REGION,
        },
        {"message_id": message_id, "deleted_at": "2026-09-14"},
    ]

    response = await delete_message(MessageId(message_id=message_id))

    assert response.status_code == 200
    assert delete.await_args_list[0].kwargs["service_url"] == HOME_REGION

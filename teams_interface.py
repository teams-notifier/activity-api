#!/usr/bin/env python3
from botbuilder.schema import Activity
from botbuilder.schema import ActivityTypes
from botbuilder.schema import ChannelAccount
from botframework.connector.aio import ConnectorClient
from botframework.connector.auth import MicrosoftAppCredentials

from config import DefaultConfig

config = DefaultConfig()

SERVICE_URL = "https://smba.trafficmanager.net/amer/"
CHANNEL_ID = "msteams"


class TeamsInterface:
    def __init__(self, app_id: str, app_password: str) -> None:
        self._connector = ConnectorClient(
            MicrosoftAppCredentials(app_id, app_password),
            base_url=SERVICE_URL,
        )
        self._conv = self._connector.conversations
        self._chanacc = ChannelAccount(id=app_id)
        self.me = self._chanacc

    def str_to_activity(self, activity: Activity | str) -> Activity:
        if isinstance(activity, Activity):
            return activity
        return Activity(
            type=ActivityTypes.message,
            channel_id=CHANNEL_ID,
            from_property=self.me,
            text=activity,
        )

    async def send_to_conversation(
        self,
        conversation_teams_id: str,
        activity: Activity,
    ) -> str:
        result = await self._conv.send_to_conversation(
            conversation_id=conversation_teams_id,
            activity=activity,
        )
        return result.id  # type: ignore

    async def update_activity(
        self,
        conversation_teams_id: str,
        activity_id: str,
        activity: Activity,
    ) -> str:
        res = await self._conv.update_activity(
            conversation_id=conversation_teams_id,
            activity_id=activity_id,
            activity=activity,
        )
        return res.id  # type: ignore

    async def delete_activity(
        self,
        conversation_teams_id: str,
        activity_id: str,
    ):
        await self._conv.delete_activity(
            conversation_id=conversation_teams_id,
            activity_id=activity_id,
        )

#!/usr/bin/env python3
from botbuilder.schema import Activity
from botbuilder.schema import ActivityTypes
from botbuilder.schema import ChannelAccount
from botframework.connector.aio import ConnectorClient
from opentelemetry import trace

from config import DefaultConfig

config = DefaultConfig()
tracer = trace.get_tracer(__name__)

SERVICE_URL = "https://smba.trafficmanager.net/amer/"
CHANNEL_ID = "msteams"


class TeamsInterface:
    def __init__(self, config: DefaultConfig) -> None:
        self._connector = ConnectorClient(
            config.get_credentials(),
            base_url=SERVICE_URL,
        )
        self._conv = self._connector.conversations
        self._chanacc = ChannelAccount(id=config.APP_ID)
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

    @tracer.start_as_current_span("send_to_conversation")
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

    @tracer.start_as_current_span("update_activity")
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

    @tracer.start_as_current_span("delete_activity")
    async def delete_activity(
        self,
        conversation_teams_id: str,
        activity_id: str,
    ):
        await self._conv.delete_activity(
            conversation_id=conversation_teams_id,
            activity_id=activity_id,
        )

#!/usr/bin/env python3
import logging
from urllib.parse import urlparse

from botbuilder.schema import Activity
from botbuilder.schema import ActivityTypes
from botbuilder.schema import ChannelAccount
from botframework.connector.aio import ConnectorClient
from opentelemetry import trace

from config import DefaultConfig

config = DefaultConfig()
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

# Microsoft's documented global endpoint, only for a conversation whose home region is unknown.
DEFAULT_SERVICE_URL = "https://smba.trafficmanager.net/teams/"
# The bot's bearer token is sent to whichever host is called, so only Microsoft's documented
# Teams hosts may ever be addressed.
TEAMS_HOSTS = frozenset(
    {
        "smba.trafficmanager.net",
        "smba.infra.gcc.teams.microsoft.com",
        "smba.infra.gov.teams.microsoft.us",
        "smba.infra.dod.teams.microsoft.us",
    }
)
CHANNEL_ID = "msteams"


def is_teams_service_url(url: str) -> bool:
    parts = urlparse(url)
    return parts.scheme == "https" and parts.hostname in TEAMS_HOSTS


class TeamsInterface:
    def __init__(self, config: DefaultConfig) -> None:
        self._config = config
        self._credentials = config.get_credentials()
        self._clients: dict[str, ConnectorClient] = {}
        self._chanacc = ChannelAccount(id=config.APP_ID)
        self.me = self._chanacc

    def _conversations(self, service_url: str | None):
        # NULL and "" both mean no stored region.
        if self._config.TEAMS_SERVICE_URL:
            url, origin = self._config.TEAMS_SERVICE_URL, "override"
        elif service_url:
            url, origin = service_url, "stored"
        else:
            url, origin = DEFAULT_SERVICE_URL, "fallback"
        if not is_teams_service_url(url):
            logger.warning(
                "refusing non-Teams service url %s (%s), using %s", url, origin, DEFAULT_SERVICE_URL
            )
            url, origin = DEFAULT_SERVICE_URL, "fallback"
        client = self._clients.get(url)
        if client is None:
            logger.info("teams connector created for %s (%s)", url, origin)
            client = self._clients[url] = ConnectorClient(self._credentials, base_url=url)
        return client.conversations

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
        service_url: str | None = None,
    ) -> str:
        result = await self._conversations(service_url).send_to_conversation(
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
        service_url: str | None = None,
    ) -> str:
        res = await self._conversations(service_url).update_activity(
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
        service_url: str | None = None,
    ):
        await self._conversations(service_url).delete_activity(
            conversation_id=conversation_teams_id,
            activity_id=activity_id,
        )

#!/usr/bin/env python3
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Annotated
from typing import Any
from typing import Optional
from uuid import UUID

import asyncpg
import blibs
from asgi_logger.middleware import AccessLoggerMiddleware
from botbuilder.schema import ErrorResponseException
from fastapi import Body
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Response
from fastapi import status
from fastapi.middleware import Middleware
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from pydantic import Field
from pydantic import model_validator
from typing_extensions import Self

from card_helper import cards
from card_helper import Container_ContainerStyle
from card_helper import TextBlock_Color as TextBlock_Color
from config import DefaultConfig
from db import database
from teams_interface import TeamsInterface

# from fastapi.middleware.cors import CORSMiddleware

config = DefaultConfig()

# Configure logging
blibs.init_root_logger()
logger = logging.getLogger(__name__)
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("msrest").setLevel(logging.ERROR)
logging.getLogger("msal").setLevel(logging.ERROR)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting app version %s", app.version)
    await database.connect()
    yield
    await database.disconnect()


app: FastAPI = FastAPI(
    title="Teams Notifier activity-api",
    version=os.environ.get("VERSION", "v0.0.0-dev"),
    lifespan=lifespan,
    middleware=[
        Middleware(
            AccessLoggerMiddleware,  # type: ignore
            format='%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(L)ss',  # noqa # type: ignore
        )
    ],
)

# Configure CORS
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # Allows all origins
#     allow_credentials=True,
#     allow_methods=["*"],  # Allows all methods
#     allow_headers=["*"],  # Allows all headers
# )

ti = TeamsInterface(config)


@app.get("/", response_class=RedirectResponse, status_code=302)
async def root():
    return "/docs"


class MessageId(BaseModel):
    message_id: UUID


class MessagePatchResponse(MessageId):
    updated_at: str = Field(
        description="RFC 3339 [ISO 8601 with a space instead of a T]), ex: 2024-11-14 07:20:31.320543+00:00"
    )


class MessageDeleteResponse(MessageId):
    deleted_at: str = Field(
        description="RFC 3339 [ISO 8601 with a space instead of a T]), ex: 2024-11-14 07:20:31.320543+00:00"
    )


class TextMessage(BaseModel):
    title: str | None = Field(None)
    title_color: TextBlock_Color | None = Field(
        None,
        description="Color attribute in the AdaptiveCArd way: "
        "[card documentation for color](https://adaptivecards.io/explorer/TextBlock.html)\n\n"
        "/!\\ Not CSS nor RGB colors /!\\",
    )
    text: str = Field(
        description="Support Markdown (Commonmark subset);"
        " more info at https://learn.microsoft.com/en-us/adaptive-cards/authoring-cards/text-features"
        " and https://commonmark.org/help/ "
    )

    style: Container_ContainerStyle | None = Field(None, description="text container style")
    bleed: bool | None = Field(None, description="set the text container to bleed")
    title_style: Container_ContainerStyle | None = Field(None, description="title container style")
    title_bleed: bool | None = Field(None, description="set the title container to bleed")
    summary: str | None = Field(None, description="summary")


async def send_payload(conversation_token: UUID, payload, summary: str = "") -> Response:
    connection: asyncpg.pool.PoolConnectionProxy
    async with await database.acquire() as connection:
        handful_of_ids = await connection.fetchrow(
            """
            SELECT  conversation_teams_id,
                    cr.conversation_reference_id AS conversation_reference_id,
                    ct.conversation_token_id AS conversation_token_id
            FROM conversation_token ct
            JOIN conversation_reference cr USING (conversation_reference_id)
            WHERE conversation_token = $1""",
            conversation_token,
        )
        if handful_of_ids is None:
            raise HTTPException(
                status_code=400,
                detail="invalid conversation_token",
            )

        built_card = None
        if isinstance(payload, str):
            built_card = cards.simple_message(payload)
        elif isinstance(payload, TextMessage):
            built_card = cards.simple_message(
                payload.text,
                style=payload.style,
                bleed=payload.bleed,
                title=payload.title,
                title_color=payload.title_color,
                title_style=payload.title_style,
                title_bleed=payload.title_bleed,
            )
        else:
            built_card = cards.card(payload, summary)

        try:
            activity_id = await ti.send_to_conversation(
                handful_of_ids["conversation_teams_id"],
                built_card,
            )
        except ErrorResponseException as exc:
            raise HTTPException(
                status_code=400,
                detail={
                    "response": json.loads(exc.response.content.decode("utf-8")),
                    "args": exc.args,
                    "message": exc.message,
                },
            )

        result = await connection.fetchrow(
            """
            INSERT INTO message (conversation_token_id, conversation_reference_id, activity_id)
            VALUES ($1, $2, $3) RETURNING message_id
            """,
            handful_of_ids["conversation_token_id"],
            handful_of_ids["conversation_reference_id"],
            activity_id,
        )

    return JSONResponse(
        status_code=status.HTTP_201_CREATED, content={"message_id": str(result["message_id"])}
    )


class ConversationTokenAndMessageOfAnyType(BaseModel):
    """`conversation_token` with *one and only one* of `message`, `text`, or `card` *must* be filled

    `summary` will only be used for `card` payload as notification hint
    """

    conversation_token: UUID
    message: Optional[TextMessage] = None
    text: Optional[str] = None
    card: Optional[dict[str, Any]] = None
    summary: str = ""

    @model_validator(mode="after")
    def check_that_only_one_message_type_is_filled(self) -> Self:
        if sum([0 if x is None else 1 for x in [self.message, self.text, self.card]]) != 1:
            raise ValueError("One and only one of message, text, or card must be filled")
        return self


@app.post("/api/v1/message", response_model=MessageId)
async def post_message_of_any_type(
    post: Annotated[ConversationTokenAndMessageOfAnyType, Body()],
):
    """sends text, simple or card message to the token's related conversation returning `message_id`

    *one and only one* of `text`, `message` or `card` *must* be provided.

    `summary` will only be used for `card` payload as notification hint
    """
    return await send_payload(
        post.conversation_token,
        post.message or post.text or post.card,
        post.summary,
    )


@app.post("/api/v1/message/text", response_model=MessageId)
async def send_text_message(
    conversation_token: Annotated[UUID, Body()],
    text: Annotated[str, Body()],
):
    """sends text message to the token's related conversation returning `message_id`"""
    return await send_payload(conversation_token, text)


@app.post("/api/v1/message/simple", response_model=MessageId)
async def send_simple_message(
    conversation_token: Annotated[UUID, Body()],
    message: Annotated[TextMessage, Body()],
):
    """sends simple message to the token's related conversation returning `message_id`

    if `summary` is not provided then the title or, if missing, the message will be used as notification hint
    """
    return await send_payload(conversation_token, message)


@app.post("/api/v1/message/card", response_model=MessageId)
async def send_adaptivecard(
    conversation_token: Annotated[UUID, Body()],
    card: Annotated[dict[str, Any], Body()],
    summary: Annotated[str, Body()] = "",
):
    """sends card message to the token's related conversation returning `message_id`

    `summary` will be used as notification hint
    """
    return await send_payload(conversation_token, card, summary)


@app.delete("/api/v1/message", response_model=MessageDeleteResponse)
async def delete_message(
    message_id: Annotated[MessageId, Body()],
):
    connection: asyncpg.pool.PoolConnectionProxy
    async with await database.acquire() as connection:
        message = await connection.fetchrow(
            """
            SELECT message_id, conversation_teams_id, activity_id, deleted_at
            FROM message
            JOIN conversation_reference USING (conversation_reference_id)
            WHERE message_id = $1
            """,
            message_id.message_id,
        )
        if message is None:
            raise HTTPException(
                status_code=400,
                detail="invalid message_id",
            )

        if message["deleted_at"] is not None:
            raise HTTPException(
                status_code=410,
                detail="message_id already deleted",
            )

        await ti.delete_activity(
            message["conversation_teams_id"],
            message["activity_id"],
        )

        result = await connection.fetchrow(
            "UPDATE message SET deleted_at = NOW() WHERE message_id = $1 RETURNING message_id, deleted_at",
            message_id.message_id,
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "message_id": str(result["message_id"]),
            "deleted_at": str(result["deleted_at"]),
        },
    )


class MessageIdAndMessageOfAnyType(BaseModel):
    """`message_id` and *one and only one* of `message`, `text`, or `card` *must* be filled

    `summary` will only be used for `card` payload as notification hint
    """

    message_id: UUID
    message: Optional[TextMessage] = None
    text: Optional[str] = None
    card: Optional[dict[str, Any]] = None
    summary: str = ""

    @model_validator(mode="after")
    def check_that_only_one_message_type_is_filled(self) -> Self:
        if sum([0 if x is None else 1 for x in [self.message, self.text, self.card]]) != 1:
            raise ValueError("one and only one of message, text, or card must be filled")
        return self


@app.patch("/api/v1/message", response_model=MessagePatchResponse)
async def patch_activity(
    msg_to_patch: Annotated[MessageIdAndMessageOfAnyType, Body()],
):
    """updates an activity

    `message_id` with *one and only one* of `message`, `text`, or `card` *must* be filled

    `summary` will not be used and is kept only for payload coherence
    """

    connection: asyncpg.pool.PoolConnectionProxy
    async with await database.acquire() as connection:
        activity_details = await connection.fetchrow(
            """
            SELECT  conversation_teams_id,
                    activity_id,
                    deleted_at
            FROM message
            JOIN conversation_reference cr USING (conversation_reference_id)
            WHERE message_id = $1
            """,
            msg_to_patch.message_id,
        )
        if activity_details is None:
            raise HTTPException(
                status_code=400,
                detail="invalid message_id",
            )

        if activity_details["deleted_at"] is not None:
            raise HTTPException(
                status_code=400,
                detail="message deleted, can't be updated",
            )

        payload = msg_to_patch.message or msg_to_patch.text or msg_to_patch.card
        built_card = None
        if isinstance(payload, str):
            built_card = cards.simple_message(payload)
        elif isinstance(payload, TextMessage):
            built_card = cards.simple_message(
                payload.text,
                style=payload.style,
                bleed=payload.bleed,
                title=payload.title,
                title_color=payload.title_color,
                title_style=payload.title_style,
                title_bleed=payload.title_bleed,
            )
        elif isinstance(payload, dict):
            built_card = cards.card(payload, msg_to_patch.summary)
        else:
            raise HTTPException(
                status_code=400,
                detail="invalid payload, neither a text, a message nor a card",
            )

        try:
            await ti.update_activity(
                conversation_teams_id=activity_details["conversation_teams_id"],
                activity_id=activity_details["activity_id"],
                activity=built_card,
            )
        except ErrorResponseException as exc:
            raise HTTPException(
                status_code=400,
                detail={
                    "response": json.loads(exc.response.content.decode("utf-8")),
                    "args": exc.args,
                    "message": exc.message,
                },
            )

        result = await connection.fetchrow(
            """
            UPDATE message SET updated_at = NOW()
            WHERE message_id = $1 RETURNING message_id, updated_at
            """,
            msg_to_patch.message_id,
        )

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "message_id": str(result["message_id"]),
            "updated_at": str(result["updated_at"]),
        },
    )


@app.get("/healthz", include_in_schema=False)
async def healthcheck():
    try:
        connection: asyncpg.pool.PoolConnectionProxy
        async with await database.acquire() as connection:
            result = await connection.fetchval("SELECT true FROM conversation_reference")
            return {"ok": result}
    except Exception as e:
        logger.exception(f"health check failed with {type(e)}: {e}")
        raise HTTPException(status_code=500, detail=f"{type(e)}: {e}")


if __name__ == "__main__":
    import uvicorn

    uviconfig = None
    if os.environ.get("DEV", "") != "":
        uviconfig = uvicorn.Config(
            "app:app",
            host="0.0.0.0",
            port=int(config.PORT),
            reload=True,
        )
    else:
        uviconfig = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=int(config.PORT),
        )

    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("access").handlers = []

    server = uvicorn.Server(uviconfig)

    try:
        server.run()
    except Exception:  # pylint: disable=broad-except
        logging.exception("Error starting server")

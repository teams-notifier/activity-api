#!/usr/bin/env python3
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.connect()
    yield
    await database.disconnect()


app: FastAPI = FastAPI(
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

ti = TeamsInterface(config.APP_ID, config.APP_PASSWORD)


@app.get("/", response_class=RedirectResponse, status_code=302)
async def root():
    return "/docs"


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


class CardNotification(BaseModel):
    card: dict[str, Any]


async def send_payload(conversation_token: UUID, payload) -> Response:
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
            built_card = cards.simple_message(payload.text, payload.title, payload.title_color)
        else:
            built_card = cards.card(payload)

        activity_id = await ti.send_to_conversation(
            handful_of_ids["conversation_teams_id"],
            built_card,
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
    "conversation_token and one and only one of message, text, or card must be filled"
    conversation_token: UUID
    message: Optional[TextMessage] = None
    text: Optional[str] = None
    card: Optional[dict[str, Any]] = None

    @model_validator(mode="after")
    def check_that_only_one_message_type_is_filled(self) -> Self:
        if sum([0 if x is None else 1 for x in [self.message, self.text, self.card]]) != 1:
            raise ValueError("One and only one of message, text, or card must be filled")
        return self


@app.post("/api/v1/message")
async def post_message_of_any_type(
    post: Annotated[ConversationTokenAndMessageOfAnyType, Body()],
):
    """sends text, simple or card message to the token's related conversation returning `message_id`"""
    return await send_payload(post.conversation_token, post.message or post.text or post.card)


@app.post("/api/v1/message/text")
async def send_text_message(
    conversation_token: Annotated[UUID, Body()],
    text: Annotated[str, Body()],
):
    """sends text message to the token's related conversation returning `message_id`"""
    return await send_payload(conversation_token, text)


@app.post("/api/v1/message/simple")
async def send_simple_message(
    conversation_token: Annotated[UUID, Body()],
    message: Annotated[TextMessage, Body()],
):
    """sends simple message to the token's related conversation returning `message_id`"""
    return await send_payload(conversation_token, message)


@app.post("/api/v1/message/card")
async def send_adaptivecard(
    conversation_token: Annotated[UUID, Body()],
    card: Annotated[dict[str, Any], Body()],
):
    """sends card message to the token's related conversation returning `message_id`"""
    return await send_payload(conversation_token, card)


class MessageId(BaseModel):
    message_id: UUID


@app.delete("/api/v1/message")
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
    "message_id and one and only one of message, text, or card must be filled"
    message_id: UUID
    message: Optional[TextMessage] = None
    text: Optional[str] = None
    card: Optional[dict[str, Any]] = None

    @model_validator(mode="after")
    def check_that_only_one_message_type_is_filled(self) -> Self:
        if sum([0 if x is None else 1 for x in [self.message, self.text, self.card]]) != 1:
            raise ValueError("One and only one of message, text, or card must be filled")
        return self


@app.patch("/api/v1/message")
async def send_notification(
    msg_to_patch: Annotated[MessageIdAndMessageOfAnyType, Body()],
): ...


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

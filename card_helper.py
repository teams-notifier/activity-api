#!/usr/bin/env python3
import json
from abc import ABC
from abc import abstractmethod
from enum import Enum
from typing import Any
from typing import Optional

from botbuilder.core import CardFactory
from botbuilder.schema import Activity
from botbuilder.schema import ActivityTypes


class TextBlock_Color(Enum):
    DEFAULT = "default"
    DARK = "dark"
    LIGHT = "light"
    ACCENT = "accent"
    GOOD = "good"
    WARNING = "warning"
    ATTENTION = "attention"


class TextBlock_FontType(Enum):
    DEFAULT = "default"
    MONOSPACE = "monospace"


class TextBlock_Style(Enum):
    DEFAULT = "default"
    HEADING = "heading"


class TextBlock_FontSize(Enum):
    DEFAULT = "default"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    EXTRALARGE = "extraLarge"


class TextBlock_FontWeight(Enum):
    DEFAULT = "default"
    LIGHTER = "lighter"
    BOLDER = "bolder"


class TextBlock_Spacing(Enum):
    DEFAULT = "default"
    NONE = "none"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    EXTRALARGE = "extraLarge"
    PADDING = "padding"


class Container_ContainerStyle(Enum):
    DEFAULT = "default"
    EMPHASIS = "emphasis"
    GOOD = "good"
    ATTENTION = "attention"
    WARNING = "warning"
    ACCENT = "accent"


_BASIC_CARD = {
    "type": "AdaptiveCard",
    "$schema": "https://adaptivecards.io/schemas/adaptive-card.json",
    "version": "1.5",
    "body": [],
}

_TEXT_BLOC = {"type": "TextBlock", "text": "message", "wrap": True}


class ACBuildable(ABC):
    @abstractmethod
    def build(self) -> dict[str, Any]:
        pass


class BaseCardBuilder:
    def __init__(self) -> None:
        self._body: list[ACBuildable] = []

    def add(self, item: ACBuildable) -> "BaseCardBuilder":
        self._body.append(item)
        return self

    def build(
        self,
    ) -> dict[str, Any]:
        return {
            "type": "AdaptiveCard",
            "$schema": "https://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.5",
            "body": [element.build() for element in self._body],
        }

    def __str__(self) -> str:
        return json.dumps(self.build())


class TextBlock(ACBuildable):
    def __init__(
        self,
        text: str,
        style: Optional[TextBlock_Style] = None,
        color: Optional[TextBlock_Color] = None,
        weight: Optional[TextBlock_FontWeight] = None,
        size: Optional[TextBlock_FontSize] = None,
        spacing: Optional[TextBlock_Spacing] = None,
        font_type: Optional[TextBlock_FontType] = None,
    ) -> None:
        self._item = {"type": "TextBlock", "text": text, "wrap": True}
        if style is not None:
            self._item["style"] = style.value
        if color is not None:
            self._item["color"] = color.value
        if weight is not None:
            self._item["weight"] = weight.value
        if size is not None:
            self._item["size"] = size.value
        if spacing is not None:
            self._item["spacing"] = spacing.value
        if font_type is not None:
            self._item["fontType"] = font_type.value

    def build(self) -> dict[str, Any]:
        return self._item

    def __str__(self) -> str:
        return json.dumps(self.build())


class Container(ACBuildable):
    def __init__(
        self,
        style: Optional[Container_ContainerStyle] = None,
        bleed: Optional[bool] = None,
        items: list[ACBuildable] | None = None,
    ) -> None:
        if items is None:
            items = []
        self._items = items
        self._item: dict[str, Any] = {"type": "Container"}
        if style is not None:
            self._item["style"] = style.value
        if bleed is not None:
            self._item["bleed"] = bleed

    def build(self) -> dict[str, Any]:
        result = self._item.copy()
        result["items"] = [element.build() for element in self._items]
        return result

    def __str__(self) -> str:
        return json.dumps(self.build())


class CardHelper:

    def simple_message(
        self,
        text: str,
        *,
        style: Container_ContainerStyle | None = None,
        bleed: bool | None = None,
        title: str | None = None,
        title_color: TextBlock_Color | None = None,
        title_style: Container_ContainerStyle | None = None,
        title_bleed: bool | None = None,
        summary: str | None = None,
    ) -> Activity:
        msg = BaseCardBuilder()
        if title_style is None:
            title_style = Container_ContainerStyle.DEFAULT
        if title or style or bleed:
            if title:
                msg.add(
                    Container(
                        bleed=title_bleed,
                        style=title_style,
                        items=[
                            TextBlock(
                                title,
                                style=TextBlock_Style.HEADING,
                                color=title_color,
                                weight=TextBlock_FontWeight.BOLDER,
                            )
                        ],
                    )
                )

            if style is None:
                style = Container_ContainerStyle.DEFAULT
            text_element = Container(
                style=style,
                bleed=bleed,
                items=[TextBlock(text)],
            )
            msg.add(text_element)
            card = msg.build()
            print(card)
            return Activity(
                type=ActivityTypes.message,
                attachments=[CardFactory.adaptive_card(card=card)],
                summary=summary or title or text,
            )
        else:
            return Activity(
                type=ActivityTypes.message,
                text=text,
            )

    def card(
        self,
        card: dict[str, Any],
        summary: str = "",
    ) -> Activity:
        return Activity(
            type=ActivityTypes.message,
            attachments=[CardFactory.adaptive_card(card=card)],
            summary=summary,
        )


cards = CardHelper()

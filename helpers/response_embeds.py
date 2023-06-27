from discord import Embed, Color
from dataclasses import dataclass
from enum import Enum


@dataclass
class EmbedStyleData:
    color: Color
    icon: str
    title: str

    def embed(self, **kwargs):
        return Embed(color=self.color, title=self.title, **kwargs).set_thumbnail(url=f"https://img.icons8.com/color/{self.icon}.png")

class EmbedStyle(Enum):
    Ok = EmbedStyleData(Color.green, 'ok', 'Success')
    Error = EmbedStyleData(Color.red, 'cancel', 'Error')
    Warning = EmbedStyleData(Color.yellow, 'error', 'Warning')
    Question = EmbedStyleData(Color.blue, 'ask-question', 'Question')
    Reminder = EmbedStyleData(Color.yellow, 'alarm', 'Reminder')
    Info = EmbedStyleData(Color.blue, 'info', 'Info')
    Wait = EmbedStyleData(Color.yellow, 'hourglass', 'Please wait')
    AccessDenied = EmbedStyleData(Color.red, 'no-entry', 'Access denied')
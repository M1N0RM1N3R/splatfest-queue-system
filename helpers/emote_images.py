import discord


def url(emote: discord.Emoji | discord.PartialEmoji | str) -> str:
    if isinstance(emote, discord.Emoji | discord.PartialEmoji):
        return emote.url
    codepoint = "-".join([hex(ord(c))[2:] for c in emote])
    return f"https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/{codepoint}.png"

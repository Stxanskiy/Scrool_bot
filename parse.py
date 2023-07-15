import json

import pandas as pd
import asyncio

from aiogram.types import Message
from telethon import TelegramClient
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument, DocumentAttributeVideo
from PIL import Image
import os
from config.config import ADMINS
from config import config
from config.logging_config import logger
from create_bot import bot
from database.queries.get_queries import get_personal_channel, get_general_channel


async def download_media(client, msg):
    if not os.path.isdir("media"):
        os.mkdir("media")

    if msg.media and isinstance(msg.media, MessageMediaPhoto):
        filename = f'media/media_image_{msg.chat_id}_{msg.photo.id}.jpg'
        await client.download_media(msg.media, file=filename)
        return filename
        compressed_filename = f'media/{msg.chat_id}_{msg.document.id}.mp4'
        os.remove(filename)  # Удаление исходного файла после сжатия
        return compressed_filename

    elif msg.media and isinstance(msg.media, MessageMediaDocument):
        attrs = msg.media.document.attributes
        if any([isinstance(attr, DocumentAttributeVideo) for attr in attrs]):
            filename = f'media/media_video_{msg.chat_id}_{msg.document.id}.mp4'
            await client.download_media(msg.media, file=filename)


def compress_image(filename):
    image = Image.open(filename)
    compressed_filename = f'{filename}'
    image.save(compressed_filename, optimize=True, quality=30)
    return compressed_filename


async def parse(msg: Message, channel_name: str, limit=3) -> list[dict]:
    try:
        client = TelegramClient('user_session', config.API_ID, config.API_HASH)
        await client.start(config.PHONE_NUMBER)
        channel = channel_name.replace('@', '')

        channel_name = channel
        chat_id = msg.chat.id

        status_message = await bot.send_message(chat_id, f'Получаем посты из канала @{channel_name}...')
        status_message_id = status_message.message_id
        channel = await client.get_entity(channel_name)
        messages = await client.get_messages(channel, limit=limit)
        channel = await get_personal_channel(channel_name)
        channel_id = channel.id

        messages = list(reversed(messages))
        data = []
        tasks = []

        async for msg in client.iter_messages(channel_name, limit=limit):
            task = asyncio.create_task(download_media(client, msg))
            tasks.append(task)

        media_data = await asyncio.gather(*tasks)

        for message, md in zip(messages, media_data):
            data.append({
                'id': message.id,
                'text': f"{message.text}".replace("'", ""),
                'media_id': md,
                'channel_name': channel_name,
                'grouped_id': message.grouped_id if message.grouped_id is not None else -1,
                'channel_id': channel_id,
            })
            data.append({'chat_id': chat_id, 'status_message_id': status_message_id})
            df = pd.DataFrame(data)
        return data
    except Exception as err:
        logger.error(f'Ошибка при парсинге сообщений канала {channel_name}: {err}')

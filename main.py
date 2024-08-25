import logging
import asyncio
from pydantic_settings import BaseSettings

from pathlib import Path
from aiogram import Bot, Dispatcher, F
from aiogram.filters.command import Command
from aiogram.types import Message, FSInputFile

import openai


class BotSettings(BaseSettings):
    api_token: str
    bot_token: str


my_bot_settings = BotSettings(_env_file=".env")

client = openai.OpenAI(api_key=my_bot_settings.api_token)

assistant = client.beta.assistants.create(
  name="Ai-assistant",
  instructions="You are a assistant",
  model="gpt-4o",

)


logging.basicConfig(level=logging.INFO)
bot = Bot(my_bot_settings.bot_token)
dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Привет✋! Я интеллектуальный ассистент, пришли мне голосовое сообщение!")


@dp.message(F.voice)
async def voice_message_handler(message: Message):
    try:
        chat_id = message.chat.id
        msg = await bot.send_message(chat_id, "⏳ Ассистент обрабатывает ваш запрос. Пожалуйста, подождите")
        file = await bot.get_file(message.voice.file_id)
        file_path = file.file_path
        input_name = f"{chat_id}.mp3"
        output_name = f"answer_{chat_id}.mp3"
        await bot.download_file(file_path, input_name)
        audio_file = open(input_name, "rb")
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
        thread = client.beta.threads.create()
        message_bot = client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=f"{transcription.text}"
        )
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread.id,
            assistant_id=assistant.id,
        )
        if run.status == 'completed':
            messages = client.beta.threads.messages.list(
                thread_id=thread.id
            )
            answer = messages.data[0].content[0].text.value
            speech_file_path = Path(__file__).parent / output_name
            response = client.audio.speech.create(
                model="tts-1",
                voice="shimmer",
                input=answer
            )

            response.stream_to_file(speech_file_path)
            audio = FSInputFile(output_name)
            await bot.delete_message(chat_id, msg.message_id)
            await bot.send_voice(chat_id, audio)
        else:
            pass
            #print(run.status)
    except:
        await bot.send_message(chat_id, "Извините, возникла ошибка")


@dp.message()
async def text_message_handler(message: Message):
    await message.answer("Извините, я работаю только с голосовыми сообщениями")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

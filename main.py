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


my_bot_settings = BotSettings()


class AsyncAssistant:
    def __init__(self, api_key):
        self.client = openai.AsyncOpenAI(api_key=api_key)

    async def create_assistant(self, *args, **kwargs):
        return await self.client.beta.assistants.create(*args, **kwargs)

    async def create_transcriptions(self, *args, **kwargs):
        return await self.client.audio.transcriptions.create(*args, **kwargs)

    async def create_thread(self, *args, **kwargs):
        return await self.client.beta.threads.create(*args, **kwargs)

    async def create_audio(self, model, voice, input_text):
        return await self.client.audio.speech.create(model=model, voice=voice, input=input_text)

    async def create_message(self, thread_id, role, content):
        return await self.client.beta.threads.messages.create(thread_id=thread_id, role=role, content=content)

    async def create_run(self, thread_id, *args, **kwargs):
        return await self.client.beta.threads.runs.create(thread_id=thread_id, *args, **kwargs)

    async def retrieve_run(self, thread_id, run_id, *args, **kwargs):
        return await self.client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id, *args, **kwargs)

    async def retrieve_run_when_done(self, thread_id, run_id):
        while True:
            run = await self.retrieve_run(thread_id, run_id)
            if run.status in ['completed', 'failed']:
                return run
            await asyncio.sleep(5)

    async def list_messages(self, thread_id, *args, **kwargs):
        return await self.client.beta.threads.messages.list(thread_id, *args, **kwargs)


Assist = AsyncAssistant(my_bot_settings.api_token)
assistant = None
assistant_id = None
logging.basicConfig(level=logging.INFO)
bot = Bot(my_bot_settings.bot_token)
dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: Message):
    global assistant, assistant_id
    await message.answer("Привет✋! Я интеллектуальный ассистент, пришли мне голосовое сообщение!")
    assistant = await Assist.create_assistant(name="Ai-assistant",
                           instructions="You are an assistant",
                           model="gpt-4o")
    assistant_id = assistant.id


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

        with open(input_name, "rb") as audio_file:
            transcription = await Assist.create_transcriptions(model="whisper-1",
                                                               file=audio_file)

        thread = await Assist.create_thread()
        thread_id = thread.id
        message_bot = await Assist.create_message(thread_id=thread.id,
                                                  role="user",
                                                  content=f"{transcription.text}")

        run = await Assist.create_run(thread_id=thread_id, assistant_id=assistant_id)
        run_id = run.id
        completed_run = await Assist.retrieve_run_when_done(thread_id=thread_id, run_id=run_id)

        messages = await Assist.list_messages(thread_id)
        if completed_run:
            answer = messages.data[0].content[0].text.value
            speech_file_path = Path(__file__).parent / output_name

            response = await Assist.create_audio(model="tts-1",
                                                 voice="shimmer",
                                                 input_text=answer)
            response.stream_to_file(speech_file_path)

            audio = FSInputFile(output_name)
            await bot.delete_message(chat_id, msg.message_id)
            await bot.send_voice(chat_id, audio)

            Path(input_name).unlink(missing_ok=True)
            Path(output_name).unlink(missing_ok=True)
        else:
            await bot.send_message(chat_id, "Извините, возникла ошибка при обработке запроса.")
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await bot.send_message(chat_id, "Извините, возникла ошибка")


@dp.message()
async def text_message_handler(message: Message):
    await message.answer("Извините, я работаю только с голосовыми сообщениями")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
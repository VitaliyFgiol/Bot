import os
from dotenv import load_dotenv
from sheets_api import get_service, add_guidelines_from_file
from tg_bot import bot_init, start
import asyncio

def main():
    #dotenv_path = '.env'
    #load_dotenv(dotenv_path)
    #add_guidelines_from_file(
    #    get_service(),
    #    spreadsheet_id=os.getenv('SPREADSHEET_ID'),
    #    sheet_name='Лист1',
    #    topic='Тема 1',
    #    file_path='test.txt'
    #)
    bot, dp = bot_init()
    asyncio.run(start(bot,dp))

if __name__ == '__main__':
    main()
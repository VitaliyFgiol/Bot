from sheets_api import get_service, add_row_append, add_row_update, read_sheet, write_to_sheet
from tg_bot import bot_init, start
import asyncio

def main():
    bot, dp = bot_init()
    asyncio.run(start(bot,dp))

if __name__ == '__main__':
    main()
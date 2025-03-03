from tg_bot import bot_init, start
import asyncio

def main():
    bot, dp = bot_init()
    asyncio.run(start(bot,dp))

if __name__ == '__main__':
    main()
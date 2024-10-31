import discord
from discord.ext import commands, tasks
import requests
from datetime import datetime
import random
from dotenv import load_dotenv
import os
from table2ascii import table2ascii as t2a, PresetStyle
from keep_alive import keep_alive

# keep_alive()
load_dotenv()
intents = discord.Intents.default()
intents.message_content = True  # Enable the intent for message content

# Create the bot with the specified intents
bot = commands.Bot(intents=intents, command_prefix="!")

# the way 'servers' variable is used:

# {
#     guild_id: {
#         notifications_channel: channel_id,
#         game_number: game_number,
#         user_id[]: {
#             distance: distance,
#             hints: hints_used,
#             guesses_made: guesses_made,
#         },
#     },

servers = {}

# Constants
GAME_NUMBER = (
    770 + (datetime.now() - datetime(2024, 10, 30)).days
)  # Initial game number
MAX_HINTS = 3  # Maximum number of hints per day


@bot.event
async def on_guild_join(guild):
    servers[guild.id] = {"notifications_channel": None, "game_number": GAME_NUMBER}


# Event when the bot is ready
@bot.event
async def on_ready():
    global servers
    print(f"Bot {bot.user.name} is ready!")
    for guild in bot.guilds:
        servers[guild.id] = {"notifications_channel": None, "game_number": GAME_NUMBER}

    await daily_game_logic()


@bot.slash_command(name="set_channel", description="Set the notifications channel")
async def set_channel(ctx: discord.ApplicationContext, channel: discord.TextChannel):
    ## check if comamnd is being called from a guild
    if not ctx.guild:
        await ctx.interaction.response.send_message(
            content=f"This command can only be used in a server", ephemeral=True
        )
        return

    if not (ctx.author.guild_permissions.manage_channels):
        await ctx.interaction.response.send_message(
            content=f"You do not have access to this command", ephemeral=True
        )
        return

    global servers
    if ctx.guild.id not in servers:
        servers[ctx.guild.id] = {
            "notifications_channel": channel.id,
            "game_number": GAME_NUMBER,
        }
    else:
        servers[ctx.guild.id]["notifications_channel"] = channel.id

    await ctx.respond(f"Notifications channel set to {channel.mention}")


# Command to handle word guessing
@bot.slash_command(
    name="guess",
    description="Guess the world and get to know how close you are",
)
async def guess(
    ctx: discord.ApplicationContext,
    word: str,
):
    if not ctx.guild:
        await ctx.interaction.response.send_message(
            content=f"This command can only be used in a server", ephemeral=True
        )
        return

    global distance, hint, servers
    if ctx.guild_id not in servers:
        servers[ctx.guild_id] = {
            "notifications_channel": None,
            "game_number": GAME_NUMBER,
        }

    api_url = f"https://api.contexto.me/machado/en/game/{servers[ctx.guild_id]['game_number']}/{word}"

    # Fetch data from the Contexto API
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            servers[ctx.guild_id][ctx.author.id] = {
                "distance": data["distance"],
                "guesses_made": (
                    servers[ctx.guild_id][ctx.author.id]["guesses_made"] + 1
                    if ctx.author.id in servers[ctx.guild_id]
                    else 1
                ),
                "hints": 0,
            }
            await ctx.respond(
                f"You guessed: **{word}**\nDistance: {data['distance']}\n"
            )
            distance = data["distance"]
            if distance == 0 or distance == 1:
                await ctx.send(f"You won")

                ## send a proper stats report of the game
                tablestring = t2a(
                    header=["User", "Distance", "Hints", "Guesses Made"],
                    body=[
                        [
                            bot.get_user(user_id).name,
                            servers[ctx.guild_id][user_id]["distance"],
                            servers[ctx.guild_id][user_id]["hints"],
                            servers[ctx.guild_id][user_id]["guesses_made"],
                        ]
                        for user_id in filter(
                            lambda x: x != "notifications_channel"
                            and x != "game_number",
                            servers[ctx.guild_id],
                        )
                    ],
                    style=PresetStyle.thin_compact,
                )
                embed = discord.Embed(
                    title="Stats of the game",
                    description=tablestring,
                    color=discord.Color.green(),
                )
                await ctx.send(embed=embed)

                ## reset the distance value for all players in this guild
                for user_id in servers[ctx.guild_id]:
                    if user_id != "notifications_channel" and user_id != "game_number":
                        servers[ctx.guild_id][user_id]["distance"] = None
                        servers[ctx.guild_id][user_id]["hints"] = 0
                        servers[ctx.guild_id][user_id]["guesses_made"] = 0

                servers[ctx.guild_id]["game_number"] = random.randint(1, 300)
                hint = 0
                await ctx.send(
                    f"New word has been chosen. Hints are now available as well"
                )
        else:
            await ctx.respond(
                "Either u spelled it wrong or used foul word. very bad manners"
            )
    except Exception as e:
        await ctx.respond(f"An error occurred: {str(e)}")


# Command to request a hint
@bot.slash_command(name="hint", description="Get a hint to help you guess the word")
async def usehint(ctx: discord.ApplicationContext):
    if not ctx.guild:
        await ctx.interaction.response.send_message(
            content=f"This command can only be used in a server", ephemeral=True
        )
        return

    global servers
    user_id = ctx.author.id
    guild_id = ctx.guild_id
    guild_game_number = servers[guild_id]["game_number"]

    # Initialize hint usage for the user if not already done
    if user_id not in servers[guild_id]:
        servers[guild_id][user_id] = {"hints": 0, "distance": None, "guesses_made": 0}
    elif "hints" not in servers[guild_id][user_id]:
        servers[guild_id][user_id]["hints"] = 0

    # Check if the user has exceeded the maximum number of hints
    if servers[guild_id][user_id]["hints"] >= MAX_HINTS:
        await ctx.respond(
            f"Sorry {ctx.author.mention}, you have used all your hints for today!"
        )
        return

    distance = 0
    try:
        distance = servers[guild_id][ctx.author.id]["distance"]
    except Exception:
        pass

    # Check if distance is null - indicating the user has not guessed yet
    if distance is None or distance <= 0:
        await ctx.respond(
            f"Please make a guess first before requesting a hint, {ctx.author.mention}."
        )
        return

    # Calculate the hint distance based on the current distance
    if distance > 200:
        # Provides a hint that is between 198 and 110
        hint_distance = random.randint(110, 198)
    elif distance >= 150:
        # Provides a hint that is between 150 and 200
        hint_distance = random.randint(150, 200)
    elif distance >= 51:
        # Provides a hint that is between 51 and 109
        hint_distance = random.randint(51, 109)
    elif distance >= 10:
        # Provides a hint that is between 10 and 50
        hint_distance = random.randint(10, 50)
    else:
        await ctx.respond(
            f"You are too close to the answer, {ctx.author.mention}. No hint available."
        )
        return

    # Fetches hint from the API
    hint_api_url = (
        f"https://api.contexto.me/machado/en/tip/{guild_game_number}/{hint_distance}"
    )

    try:
        hint_response = requests.get(hint_api_url)
        if hint_response.status_code == 200:
            hint_data = hint_response.json()
            hint_word = hint_data["word"]  # the API returns a field 'word'
            await ctx.respond(
                f"Here is your hint: **{hint_word}**\nDistance from the target word is approximately **{hint_distance}**."
            )

            # Increment the hint usage count
            servers[guild_id][user_id]["hints"] += 1
        else:
            await ctx.send("Error fetching hint from Contexto API.")
    except Exception as e:
        await ctx.send(f"An error occurred while fetching the hint: {str(e)}")


# Function to handle daily game logic
async def daily_game_logic():
    global GAME_NUMBER, distance, servers

    ## The game number of 30th October 2024 is 770
    ## The game number increases by 1 each day
    GAME_NUMBER = 770 + (datetime.now() - datetime(2024, 10, 30)).days
    distance = 0

    # Informs users about the new game
    for guild_id in servers:
        ## change the game number for each server
        servers[guild_id]["game_number"] = GAME_NUMBER
        channel = servers[guild_id]["notifications_channel"]

        ## reset the hints for each user in the guild
        for user_id in servers[guild_id]:
            if user_id != "notifications_channel" and user_id != "game_number":
                servers[guild_id][user_id]["hints"] = 0
                servers[guild_id][user_id]["distance"] = None
                servers[guild_id][user_id]["guesses_made"] = 0

        if channel is not None:
            await bot.get_channel(channel).send(
                f"""
                Today is a new day! The game number has increased to **{GAME_NUMBER}**.
                You can now start guessing the new word!
                """
            )


# Command to provide help and tips
@bot.slash_command(name="guide", description="Get help and tips for playing the game")
async def guide(ctx: discord.ApplicationContext):
    help_message = """
        Welcome to the Guess the word Game!

        **How to Play:**
        1. The game starts with a secret word that you must guess.
        2. Use the `/guess <your_word>` command to make a guess.
        3. After each guess, you'll receive feedback on how far away your guess is from the secret word.
        4. You can also use the `/hint` command to receive a hint about the word.

        **Tips for Playing:**
        - Start with common words to get a sense of the distance.
        - Pay attention to the distance feedback to narrow down your guesses.
        - Use hints wisely; you have a limited number of hints available per day.
        - Keep track of your previous guesses to avoid repeating them.
        Have fun, and good luck guessing the word!
    """

    await ctx.respond(help_message)


@tasks.loop(hours=24)
async def daily_game():
    await daily_game_logic()


@bot.slash_command(name="god", description="Admin Command | Reveal the word")
async def god(ctx: discord.ApplicationContext):
    if not (ctx.guild):
        await ctx.interaction.response.send_message(
            content=f"This command can only be used in a server", ephemeral=True
        )
        return

    if not (ctx.author.guild_permissions.manage_channels):
        await ctx.interaction.response.send_message(
            content=f"You do not have access to this command", ephemeral=True
        )
        return

    answer = requests.get(
        f"https://api.contexto.me/machado/en/giveup/{servers[ctx.guild_id]['game_number']}"
    )
    text = answer.json()["word"]

    await ctx.interaction.response.send_message(f"The word was {text}", ephemeral=True)


@bot.slash_command(name="reset", description="Admin Command | Reset the game")
async def reset(ctx: discord.ApplicationContext):
    if not (ctx.guild):
        await ctx.interaction.response.send_message(
            content=f"This command can only be used in a server", ephemeral=True
        )
        return

    if not (ctx.author.guild_permissions.manage_channels):
        await ctx.interaction.response.send_message(
            content=f"You do not have access to this command", ephemeral=True
        )
        return

    await ctx.interaction.response.send_message(f"Game has been reset")
    await daily_game_logic()


daily_game.start()
# Run the bot with your token
bot.run(os.environ["discord_token"])

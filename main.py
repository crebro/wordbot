import discord
from discord.ext import commands
import requests
from datetime import datetime  
import random
from dotenv import load_dotenv
import os
from keep_alive import keep_alive

keep_alive()
load_dotenv()
intents = discord.Intents.default()
intents.message_content = True  # Enable the intent for message content

# Create the bot with the specified intents
bot = commands.Bot(command_prefix='!', intents=intents)

# Constants
GAME_NUMBER = 300  # Initial game number
MAX_HINTS = 3  # Maximum number of hints per day
hint_usage = {}  # Track hint usage by user
guesses_made = 0  # Track total guesses made
yesterdays_word = ''  # Store yesterday's word
distance = None

# Function to check if the day has changed
def check_new_day():
    current_date = datetime.now().date()  # Get the current date
    return current_date != bot.start_date  # Compare with the start date

# Event when the bot is ready
@bot.event
async def on_ready():
    bot.start_date = datetime.now().date()  # Initialize the start date
    print(f'Bot {bot.user.name} is ready!')
    
    
    await daily_game_logic()

# Command to handle word guessing
@bot.command()
async def guess(ctx, word):
    global guesses_made,distance,GAME_NUMBER,hint
    api_url = f'https://api.contexto.me/machado/en/game/{GAME_NUMBER}/{word}'
    
    # Fetch data from the Contexto API
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            distance = data['distance']
            guessed_word = data['word']
            guesses_made += 1  # Increment the guess counter
            if distance == 0 or distance == 1:
                await ctx.send(f'You won')
                GAME_NUMBER+= 1
                hint = 0
                await ctx.send(f'New word has been chosen. Hints are now available as well')
            # Send the response to the user
            await ctx.send(f'You guessed: **{guessed_word}**\nDistance: {distance}\n')
        else:
            await ctx.send('Either u spelled it wrong or used foul word. very bad manners')
    except Exception as e:
        await ctx.send(f'An error occurred: {str(e)}')

# Command to request a hint
@bot.command()
async def hint(ctx):
    global hint_usage 
    user_id = ctx.author.id
    
    # Initialize hint usage for the user if not already done
    if user_id not in hint_usage:
        hint_usage[user_id] = 0
    
    # Check if the user has exceeded the maximum number of hints
    if hint_usage[user_id] >= MAX_HINTS:
        await ctx.send(f'Sorry {ctx.author.mention}, you have used all your hints for today!')
        return

   
    
    # Check if distance is null - indicating the user has not guessed yet
    if distance is None or distance <= 0:
        await ctx.send(f'Please make a guess first before requesting a hint, {ctx.author.mention}.')
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
        await ctx.send(f'You are too close to the answer, {ctx.author.mention}. No hint available.')
        return
    
    # Fetches hint from the API
    hint_api_url = f'https://api.contexto.me/machado/en/tip/{GAME_NUMBER}/{hint_distance}'
    
    try:
        hint_response = requests.get(hint_api_url)
        if hint_response.status_code == 200:
            hint_data = hint_response.json()
            hint_word = hint_data['word']  # the API returns a field 'word'
            await ctx.send(f'Here is your hint: **{hint_word}**\nDistance from the target word is approximately **{hint_distance}**.')
            
            # Increment the hint usage count
            hint_usage[user_id] += 1
        else:
            await ctx.send('Error fetching hint from Contexto API.')
    except Exception as e:
        await ctx.send(f'An error occurred while fetching the hint: {str(e)}')

# Function to handle daily game logic
async def daily_game_logic():
    global GAME_NUMBER, guesses_made, hint_usage, yesterdays_word

    # Checks if a new day has started
    if check_new_day():
        yesterday_word = yesterdays_word  # Saves yesterday's word if needed
        
        # Increment the game number
        GAME_NUMBER += 1
        hint_usage.clear()  # Resets hint usage for all users
        guesses_made = 0  # Resets guesses for the new day
        distance = 0
        
        # Informs users about the new game
        await bot.get_channel(1296395828998701142).send(
            f'Today is a new day! The game number has increased to **{GAME_NUMBER}**.\n'
            f'Yesterday\'s word was **{yesterday_word}**.\n'
            f'Total guesses made: {guesses_made}.\n'
            f'You can now start guessing the new word!'
        )

# Command to provide help and tips
@bot.command()
async def guide(ctx):
    help_message = (
        "Welcome to the Guess the word Game!\n\n"
        "**How to Play:**\n"
        "1. The game starts with a secret word that you must guess.\n"
        "2. Use the `!guess <your_word>` command to make a guess.\n"
        "3. After each guess, you'll receive feedback on how far away your guess is from the secret word.\n"
        "4. You can also use the `!hint` command to receive a hint about the word.\n\n"
        "**Tips for Playing:**\n"
        "- Start with common words to get a sense of the distance.\n"
        "- Pay attention to the distance feedback to narrow down your guesses.\n"
        "- Use hints wisely; you have a limited number of hints available per day.\n"
        "- Keep track of your previous guesses to avoid repeating them.\n\n"
        "Have fun, and good luck guessing the word!"
    )
    
    await ctx.send(help_message)


# Run the bot with your token
bot.run(os.environ['discord_token'])

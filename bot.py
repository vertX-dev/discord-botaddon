import os
import discord
import zipfile
import tempfile
import shutil
import json
from dotenv import load_dotenv

# Load .env token
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

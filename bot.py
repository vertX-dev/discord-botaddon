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


def fix_tags_in_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return None  # Not a valid JSON

    item = data.get("minecraft:item")
    if not item:
        return None

    components = item.get("components", {})
    if not isinstance(components, dict):
        return None

    broken_tags = [k for k, v in components.items() if k.startswith("tag:") and v == {}]
    if not broken_tags:
        return None

    tag_list = [tag[4:] for tag in broken_tags]

    for tag in broken_tags:
        components.pop(tag)

    if "minecraft:tags" in components:
        existing_tags = components["minecraft:tags"].get("tags", [])
        if isinstance(existing_tags, list):
            components["minecraft:tags"]["tags"] = list(set(existing_tags + tag_list))
        else:
            components["minecraft:tags"]["tags"] = tag_list
    else:
        components["minecraft:tags"] = {"tags": tag_list}

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return {
            "file": os.path.basename(filepath),
            "tags_added": tag_list
        }
    except Exception:
        return None


def process_mcaddon(file_path):
    temp_dir = tempfile.mkdtemp()
    fixed_path = file_path.replace(".mcaddon", "_fixed.mcaddon")
    summaries = []

    try:
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        for root, _, files in os.walk(temp_dir):
            if "items" in root:
                for file in files:
                    if file.endswith(".json"):
                        result = fix_tags_in_file(os.path.join(root, file))
                        if result:
                            summaries.append(result)

        with zipfile.ZipFile(fixed_path, 'w', zipfile.ZIP_DEFLATED) as zip_out:
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    abs_path = os.path.join(root, file)
                    rel_path = os.path.relpath(abs_path, temp_dir)
                    zip_out.write(abs_path, rel_path)

        return fixed_path, summaries
    finally:
        shutil.rmtree(temp_dir)


@client.event
async def on_ready():
    print(f"[READY] Bot is logged in as {client.user}")


@client.event
async def on_message(message):
    if message.author.bot:
        return

    for attachment in message.attachments:
        if attachment.filename.endswith(".mcaddon"):
            await message.channel.send(f"🔧 Downloading `{attachment.filename}`...")
            temp_input = os.path.join(tempfile.gettempdir(), attachment.filename)
            await attachment.save(temp_input)

            await message.channel.send("🛠 Fixing broken tags...")
            fixed_path, summaries = process_mcaddon(temp_input)

            if os.path.exists(fixed_path):
                if summaries:
                    embed = discord.Embed(
                        title="✅ Addon Tags Fixed",
                        description=f"**File:** `{attachment.filename}`\n**Modified Files:** `{len(summaries)}`",
                        color=0x00ff80
                    )

                    total_chars = len(embed.description)
                    max_embed_chars = 5900  # leave room for Discord's limit
                    max_fields = 10  # Show at most 10 files
                    cutoff = False

                    for summary in summaries[:max_fields]:
                        tag_list = '\n'.join(f"• `{tag}`" for tag in summary["tags_added"])
                        if total_chars + len(summary["file"]) + len(tag_list) > max_embed_chars:
                            cutoff = True
                            break
                        embed.add_field(
                            name=f"🧩 `{summary['file']}` ({len(summary['tags_added'])} tag{'s' if len(summary['tags_added']) != 1 else ''})",
                            value=tag_list,
                            inline=False
                        )
                        total_chars += len(summary["file"]) + len(tag_list)

                    if cutoff or len(summaries) > max_fields:
                        embed.set_footer(text="⚠️ Truncated summary due to Discord embed limits.")

                    await message.channel.send(embed=embed)

                await message.channel.send("📦 Here's your fixed addon:",
                                         file=discord.File(fixed_path))
                os.remove(fixed_path)
            else:
                await message.channel.send("❌ Failed to fix the addon.")
                
client.run(TOKEN)

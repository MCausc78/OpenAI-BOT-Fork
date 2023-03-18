import aiosqlite
import asyncio
import atexit
import datetime
import discord
from discord.ext import commands
import dotenv
import openai
import os
import time
import signal
import struct
import sys
import traceback
import cpuid_native

dotenv.load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

role_ban = int(os.getenv('ROLE_BAN'))
role_admin = int(os.getenv('ROLE_ADMIN'))

role_lvl1 = int(os.getenv('ROLE_LVL1'))
role_lvl2 = int(os.getenv('ROLE_LVL2'))

channel_gpt = int(os.getenv('AI_CHANNEL'))

bot = discord.Bot(intents=discord.Intents.all())
start_time = time.time()

ask_group = bot.create_group("ask", "Ask different OpenAI models a question")
access_group = bot.create_group("member", "Access related commands")
image_group = bot.create_group("image", "Image generation related commands")

async def is_allowed(member: discord.Member) -> bool:
    async with db.execute(
        "SELECT id FROM allowed_users WHERE id = ?",
        (str(member.id), )
    ) as cursor:
        async for _ in cursor:
            return True
        return False

@bot.event
async def on_ready():
    global owners
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game('COC'))
    print("BOT IS UP")
    owners = {621611758141964298, *bot.owner_ids}
    if bot.owner_id is not None:
        owners.append(bot.owner_id)

@bot.event
async def on_application_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        return await ctx.respond(embed=discord.Embed(
            title="Ошибка",
            description=f"Попробуйте через {round(error.retry_after, 2)} секунд",
            color=0xff0000),
            ephemeral=True)
    elif isinstance(error, commands.MissingPermissions):
        return await ctx.respond(embed=discord.Embed(
            title="Ошибка",
            description="У тебя нет прав",
            color=0xff0000),
            ephemeral=True)
    traceback.print_exception(error)

@access_group.command(
    name="unblock",
    description="Unblock COCAI for member"
)
async def member_unblock(ctx, member: discord.Member):
    roles = [role.id for role in ctx.author.roles]
    if role_admin not in roles:
        await ctx.respond(
            "❌ У тебя недостаточно прав, чтобы разблокировать COCAI пользователям",
            ephemeral=True)
        return
    try:
        await member.remove_roles(ctx.guild.get_role(role_ban))
        await ctx.respond(
            f"✅ Участник {member.mention} ({member.name}) был успешно разблокирован",
            ephemeral=True)
    except:
        await ctx.respond(
            f"❌ Участник {member.mention} ({member.name}) не был заблокирован",
            ephemeral=True)

@access_group.command(
    name="block",
    description="Block COCAI for member"
)
async def member_block(ctx, member: discord.Member):
    author = ctx.user
    roles = [role.id for role in author.roles]
    if role_admin not in roles:
        await ctx.respond(
            "❌ У тебя недостаточно прав, чтобы блокировать COCAI пользователям",
            ephemeral=True)
        return
    await member.add_roles(ctx.guild.get_role(role_ban))
    await ctx.respond(
        f"✅ Участник {member.mention} ({member.name}) был успешно заблокирован",
        ephemeral=True)

# @bot.user_command(name="Implicitly allow")
@access_group.command(
    name="allow",
    description="Implicitly allow member ask without having required roles"
)
async def implicit_allow(ctx, member: discord.Member):
    roles = [role.id for role in ctx.author.roles]
    if role_admin not in roles:
        print('3')
        await ctx.respond(
            "У тебя недостаточно прав, чтобы разрешать COCAI пользователям без ролей",
            ephemeral=True)
        return
    if await is_allowed(member):
        await ctx.respond(
            f"❌ Участнику {member.mention} ({member.name}) и так разрешено",
            ephemeral=True)
        return
    await db.execute(
        "INSERT INTO allowed_users VALUES (?)",
        (str(member.id), )
    )
    await ctx.respond(
        f"✅ Участнику {member.mention} ({member.name}) теперь разрешено использовать COCAI без ролей",
        ephemeral=True)

@access_group.command(
    name="deny",
    description="Require member have required roles"
)
async def deny(ctx, member: discord.Member):
    roles = [role.id for role in ctx.author.roles]
    if role_admin not in roles:
        await ctx.respond(
            "У тебя недостаточно прав, чтобы запрещать COCAI пользователям без ролей",
            ephemeral=True)
        return
    if not await is_allowed(member):
        await ctx.respond(
            f"❌ Участнику {member.mention} ({member.name}) и так запрещено",
            ephemeral=True)
        return
    async with db.execute(
        "DELETE FROM allowed_users WHERE id = ?",
        (str(member.id),)
    ):
        await db.commit()
        await ctx.respond(
            f"✅ Участнику {member.mention} ({member.name}) теперь запрещено использовать COCAI без ролей",
            ephemeral=True)

@ask_group.command(name="babbage", description="Ask babbage model a question")
@commands.cooldown(1, 30, commands.BucketType.user)
async def ask_babbage(ctx, prompt: discord.Option(str)):
    if role_ban in [role.id for role in ctx.author.roles]:
        await ctx.respond("Тебе не доступен COCAI", ephemeral=True)
        return
    if ctx.channel.id != channel_gpt:
        await ctx.respond(
            "Я могу отвечать на ваши вопросы только в канале #gpt-chat",
            ephemeral=True)
        return
    await ctx.defer()
    computation_start = time.time()
    response = openai.Completion.create(engine="text-babbage-001",
                                        prompt=prompt,
                                        temperature=0.4,
                                        max_tokens=1024,
                                        top_p=0.1,
                                        frequency_penalty=0.1,
                                        presence_penalty=0.1)
    elapsed_time = int(round(time.time() - computation_start))
    embed = discord.Embed(title="Ответ:",
                          description=response["choices"][0]["text"],
                          color=0x5258bd)
    embed.add_field(name="Вопрос:", value=prompt, inline=False)
    embed.set_footer(
        text=f"Обработка заняла {str(datetime.timedelta(seconds=elapsed_time))}")
    await ctx.followup.send(embed=embed)

@ask_group.command(name="curie", description="Ask curie model a question")
@commands.cooldown(1, 30, commands.BucketType.user)
async def ask_curie(ctx, prompt: discord.Option(str)):
    roles = [role.id for role in ctx.author.roles]
    if role_ban in roles:
        await ctx.respond("Тебе не доступен COCAI", ephemeral=True)
        return
    if not await is_allowed(ctx.author) and role_lvl1 not in roles and role_lvl2 not in roles:
        await ctx.respond(
            "Тебе недоступна эта модель из-за слишком низкого уровня",
            ephemeral=True,
        )
        return
    if ctx.channel.id != channel_gpt:
        await ctx.respond(
            "Я могу отвечать на ваши вопросы только в канале #gpt-chat",
            ephemeral=True,
        )
        return
    await ctx.defer()
    computation_start = time.time()
    response = openai.Completion.create(engine="text-curie-001",
                                        prompt=prompt,
                                        temperature=0.4,
                                        max_tokens=1024,
                                        top_p=0.1,
                                        frequency_penalty=0.1,
                                        presence_penalty=0.1)
    elapsed_time = int(round(time.time() - computation_start))
    embed = discord.Embed(title="Ответ:",
                          description=response["choices"][0]["text"],
                          color=0x5258bd)
    embed.add_field(name="Вопрос:", value=prompt, inline=False)
    embed.set_footer(
        text=f"Обработка заняла {str(datetime.timedelta(seconds=elapsed_time))}")
    await ctx.followup.send(embed=embed)

@ask_group.command(name="davinci", description="Ask davinci model a question")
@commands.cooldown(1, 30, commands.BucketType.user)
async def ask_davinci(ctx, prompt: discord.Option(str)):
    roles = [role.id for role in ctx.author.roles]
    if role_ban in roles:
        await ctx.respond(
            "Тебе не доступен COCAI",
            ephemeral=True,
        )
        return
    if not await is_allowed(ctx.author) and role_lvl2 not in roles:
        await ctx.respond(
            "Тебе недоступна эта модель из-за слишком низкого уровня",
             ephemeral=True,
        )
        return
    if ctx.channel.id != channel_gpt:
        await ctx.respond(
            "Я могу отвечать на ваши вопросы только в канале #gpt-chat",
            ephemeral=True,
        )
        return
    await ctx.defer()
    computation_start = time.time()
    response = openai.Completion.create(engine="text-davinci-003",
                                        prompt=prompt,
                                        temperature=0.4,
                                        max_tokens=1024,
                                        top_p=0.1,
                                        frequency_penalty=0.1,
                                        presence_penalty=0.1)
    elapsed_time = int(round(time.time() - computation_start))
    embed = discord.Embed(title="Ответ:",
                          description=response["choices"][0]["text"],
                          color=0x5258bd)
    embed.add_field(name="Вопрос:", value=prompt, inline=False)
    embed.set_footer(
        text=f"Обработка заняла {str(datetime.timedelta(seconds=elapsed_time))}")
    await ctx.followup.send(embed=embed)

@image_group.command(name="generate", description="Generate image")
@commands.cooldown(1, 70, commands.BucketType.user)
async def image_generate(ctx, prompt: discord.Option(str)):
    roles = [role.id for role in ctx.author.roles]
    if role_ban in roles:
        await ctx.respond(
            "Тебе не доступен COCAI",
            ephemeral=True)
        return
    if ctx.channel.id != channel_gpt:
        await ctx.respond(
            "Я могу отвечать на ваши вопросы только в канале #gpt-chat",
            ephemeral=True,
        )
        return
    await ctx.defer()
    computation_start = time.time()
    response = openai.Image.create(prompt=prompt, n=1, size="1024x1024")
    image_url = response['data'][0]['url']
    elapsed_time = int(round(time.time() - computation_start))
    embed = discord.Embed(
        title="Сгенерированное изображение: " + prompt,
        color=0x5258bd
    )
    embed.set_image(url=image_url)
    embed.set_footer(
        text=f"Обработка заняла {str(datetime.timedelta(seconds=elapsed_time))}"
    )
    await ctx.followup.send(embed=embed)

@bot.command(name="ping", description="Measures latency")
@commands.cooldown(1, 15, commands.BucketType.user)
async def ping(ctx):
    return await ctx.respond(
        embed=discord.Embed(
            title="Пинг",
            description=f"Понг: {round(bot.latency * 1000)}ms",
            color=0x5258bd
        ),
        ephemeral=True
    )

@bot.command(name="uptime", description="Shows bot uptime")
@commands.cooldown(1, 15, commands.BucketType.user)
async def uptime(ctx):
    current_time = time.time()
    difference = int(round(current_time - start_time))
    text = str(datetime.timedelta(seconds=difference))
    embed = discord.Embed(color=0x5258bd)
    embed.add_field(name="Uptime", value=text)
    await ctx.respond(embed=embed, ephemeral=True)

@bot.command(name="shutdown", description="Shutdown the bot")
async def shutdown(ctx):
    print(ctx.author.id, bot.owner_id, bot.owner_ids)
    if ctx.author.id not in owners:
        await ctx.respond(
            "Тебе нельзя выключать бота",
            ephemeral=True,
        )
        return
    await ctx.respond(
        "Выключение бота...",
        ephemeral=True,
    )
    await shutdown_bot_async()

def get_processor_brand() -> str:
    result = struct.pack(
        'IIIIIIIIIIII',
        *cpuid_native.get_cpuid(0x80000002)[1:],
        *cpuid_native.get_cpuid(0x80000003)[1:],
        *cpuid_native.get_cpuid(0x80000004)[1:],
    )
    eos = result.find(b'\0')
    if eos != -1:
        result = result[:eos]
    return (result.decode('utf-8')
                  .strip())

REGISTER_EAX = 0x00000000
REGISTER_EBX = 0x00000001
REGISTER_ECX = 0x00000002
REGISTER_EDX = 0x00000003

def get_processor_vendor() -> str:
    parts = cpuid_native.get_cpuid(0x00000000)[1:]
    result = struct.pack(
        'III',
        parts[REGISTER_EBX],
        parts[REGISTER_EDX],
        parts[REGISTER_ECX],
    )
    return (result.decode('utf-8')
                  .strip())


@bot.command(name="botinfo", description="About bot")
async def botinfo(ctx):
    embed = discord.Embed(color=0x00878787,
                          title="COC AI")
    embed.add_field(name="Производитель процессора",
                    value=get_processor_vendor())
    embed.add_field(name="Бренд процессора",
                    value=get_processor_brand())
    embed.add_field(name="",
                    value="")
    await ctx.respond(
        embed=embed,
        ephemeral=True,
    )

async def shutdown_bot_async():
    shutdowned = True
    print('Shutdown')
    await db.commit()
    await db.close()
    await bot.close()
    print('Shutdown 2')
    sys.exit(0)

def shutdown_bot(*args, **kwargs):
    return asyncio.run(shutdown_bot_async())

async def initialize_database():
    global db
    db = await aiosqlite.connect('gpt.db')
    await db.execute("""\
CREATE TABLE IF NOT EXISTS allowed_users (
 id TEXT NOT NULL,
 UNIQUE(id)
)""")
    await db.commit()

try:
    asyncio.run(initialize_database())
    bot.run(os.getenv("DISCORD_BOT_TOKEN"), reconnect=True)
except Exception as err:
    print('Discord bot token error', file=sys.stderr)
    print(err, file=sys.stderr)
    traceback.print_exception(err)

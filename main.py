import discord
from discord.ext import commands, tasks
import twitch
import pickledb
import json
from datetime import timedelta

refresh_delay = 20
with open("config.json") as f:
    data = json.load(f)
    discord_token = data["discord_token"]
    twitch_token = data["twitch_token"]
bot = commands.Bot(command_prefix='&&')
helix = twitch.Helix(twitch_token, use_cache=True, cache_duration=timedelta(seconds=10.0))
config = pickledb.load('config.db', True)
live_tracker = pickledb.load('cache.db', True)


@bot.command()
async def add(ctx: commands.Context, user):
    if ctx.guild is None:
        await ctx.send("You can only use this bot in a server")
        return
    if helix.user(user) is not None:
        channel_id = str(ctx.channel.id)
        try:
            current_users = config.lgetall(channel_id)
        except KeyError:
            config.lcreate(channel_id)
            current_users = config.lgetall(channel_id)
        if user not in current_users:
            config.ladd(channel_id, user)
            await ctx.send(f"Added {user} to the list of streamers.")
        else:
            await ctx.send(f"That streamer is already enabled!")
    else:
        await ctx.send("Couldn't find that streamer!")


@bot.command()
async def remove(ctx: commands.Context, user):
    if ctx.guild is None:
        await ctx.send("You can only use this bot in a server")
        return
    channel_id = str(ctx.channel.id)
    try:
        current_users = config.lgetall(channel_id)
        if user in current_users:
            config.lremvalue(channel_id, user)
            await ctx.send(f"Removed {user} from the list of streamers!")
        else:
            await ctx.send(f"That user is not on the list of streamers!")
    except KeyError:
        await ctx.send(f"This channel does not have any streamers!")


@bot.command()
async def list(ctx: commands.Context):
    if ctx.guild is None:
        await ctx.send("You can only use this bot in a server")
        return
    channel_id = str(ctx.channel.id)
    try:
        current_users = config.lgetall(channel_id)
        await ctx.send(f"Current streamers: {', '.join(current_users)}")
    except KeyError:
        await ctx.send("No channels are configured here")


@tasks.loop(seconds=refresh_delay)
async def check_channels():
    print("Running announcements")
    # Loop over all channels in the config
    for discord_channel in config.getall():
        # Get the discord channel as object
        channel_object: discord.TextChannel = bot.get_channel(int(discord_channel))

        # Get and loop over all streamers for that channel
        streamers = helix.users(config.lgetall(discord_channel))
        streamer: twitch.helix.User

        for streamer in streamers:
            # If the streamers status is not saved yet, save it!
            if streamer.display_name not in live_tracker.getall():
                live_tracker.set(streamer.display_name, streamer.is_live)
            if streamer.is_live:
                previous_live = live_tracker.get(streamer.display_name)
                if not previous_live:
                    await channel_object.send(
                        f"**{streamer.display_name} just went live!** Check it out: https://twitch.tv/{streamer.display_name}")
    print("Updating cache")
    for discord_channel in config.getall():
        streamers = helix.users(config.lgetall(discord_channel))
        streamer: twitch.helix.User

        for streamer in streamers:
            live_tracker.set(streamer.display_name, streamer.is_live)

    # twitch.api.API.flush_cache()
    print("Cache complete")


@bot.event
async def on_ready():
    print("ready")
    check_channels.start()


bot.run(discord_token)

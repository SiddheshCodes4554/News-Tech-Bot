import os
import json
import re
import feedparser
from datetime import datetime, timedelta

import discord
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiohttp import ClientSession

# ------------------- Config from Environment -------------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
NEWS_CHANNEL_ID = int(os.getenv("NEWS_CHANNEL_ID", "0"))
MAX_ARTICLES = int(os.getenv("MAX_ARTICLES", "2"))

TECH_NEWS_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://www.wired.com/feed/rss",
    "https://www.techmeme.com/feed.xml",
    "https://news.ycombinator.com/rss",
    "https://feeds.arstechnica.com/arstechnica/index",
    "https://www.engadget.com/rss.xml",
    "https://mashable.com/feeds/rss/technology",
    "https://www.cnet.com/rss/news/",
    "https://www.zdnet.com/news/rss.xml",
    "https://gizmodo.com/rss",
    "https://www.digitaltrends.com/feed/",
    "https://www.androidauthority.com/feed/",
    "https://9to5mac.com/feed/",
    "https://9to5google.com/feed/",
    "https://venturebeat.com/feed/",
    "https://www.techradar.com/rss",
    "https://www.technologyreview.com/feed/",
    "https://futurism.com/feed",
    "https://www.nasa.gov/rss/dyn/breaking_news.rss",
    "https://www.reddit.com/r/technology/.rss",
    "https://lobste.rs/rss",
    "https://openai.com/blog/rss",
    "https://ai.googleblog.com/feeds/posts/default?alt=rss",
    "https://deepmind.com/blog/rss.xml",
    "https://www.csail.mit.edu/rss.xml",
    "https://venturebeat.com/category/ai/feed/",
    "https://krebsonsecurity.com/feed/",
    "https://feeds.feedburner.com/TheHackersNews",
    "https://www.darkreading.com/rss.xml",
    "https://www.bleepingcomputer.com/feed/",
    "https://aws.amazon.com/blogs/aws/feed/",
    "https://cloud.google.com/blog/topics/rss",
    "https://techcommunity.microsoft.com/gxcuf89792/rss/board?board.id=AzureBlog",
    "https://devops.com/feed/",
    "https://towardsdatascience.com/feed",
    "https://www.kdnuggets.com/feed",
    "https://analyticsindiamag.com/feed/"
]

SEEN_FILE = "seen.json"
if not os.path.exists(SEEN_FILE):
    with open(SEEN_FILE, "w") as f:
        json.dump({}, f)


def load_seen():
    with open(SEEN_FILE, "r") as f:
        return json.load(f)


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(seen, f)


def clean_html(raw_html: str) -> str:
    """Remove HTML tags from summaries."""
    clean = re.compile("<.*?>")
    return re.sub(clean, "", raw_html)


async def fetch_rss(url, session):
    try:
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                return feedparser.parse(await response.text())
    except Exception as e:
        print(f"⚠️ Error fetching {url}: {e}")
    return None


async def post_updates(bot):
    seen = load_seen()
    new_items = []

    async with ClientSession() as session:
        for url in TECH_NEWS_FEEDS:
            feed = await fetch_rss(url, session)
            if feed:
                for entry in feed.entries:
                    guid = entry.get("id") or entry.link
                    published = entry.get("published_parsed")

                    if not guid or not published:
                        continue

                    published_time = datetime(*published[:6])
                    if guid not in seen and published_time > datetime.now() - timedelta(hours=2):
                        summary = clean_html(entry.get("summary", "")).strip()
                        if not summary:
                            summary = "Click below to read the full article."
                        else:
                            summary = summary[:300] + "..." if len(summary) > 300 else summary

                        new_items.append({
                            "title": entry.title,
                            "link": entry.link,
                            "summary": summary,
                        })
                        seen[guid] = True

                        if len(new_items) >= MAX_ARTICLES:
                            break
            if len(new_items) >= MAX_ARTICLES:
                break

    save_seen(seen)

    if NEWS_CHANNEL_ID == 0:
        print("🚨 ERROR: NEWS_CHANNEL_ID not set in environment variables.")
        return

    channel = bot.get_channel(NEWS_CHANNEL_ID)

    if channel and new_items:
        embed = discord.Embed(
            title="📰 Latest Tech News",
            color=0x00ff00,
            timestamp=datetime.now(),
        )
        for item in new_items:
            embed.add_field(
                name=f"**{item['title']}**",
                value=f"{item['summary']}\n[Read more]({item['link']})",
                inline=False,
            )
        await channel.send(embed=embed)


# ------------------- Discord Bot Setup -------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"✅ Bot {bot.user} is online.")
    scheduler = AsyncIOScheduler()
    scheduler.add_job(post_updates, "interval", hours=2, args=(bot,))
    scheduler.start()
    await post_updates(bot)  # Run once on startup


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("🚨 ERROR: DISCORD_TOKEN not set in environment variables.")
    else:
        bot.run(DISCORD_TOKEN)

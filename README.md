# Discord Video Downloader
Self-host discord-bot for downloading videos from popular sites via a URL. 
Supports YouTube, TikTok, Instagram, Twitter (x.com), bilibili
and Twitch Clips.

This is meant to be an easy deployment for users who want to self-host
discord bots that can download videos from YouTube, TikTok, etc.

# Install and deploy
1. Create a discord bot and copy your discord bot token. Follow [this guide](/docs/discord-setup.md#token-generation)
2. Install docker desktop or other docker software.
   1. *[Windows](https://docs.docker.com/desktop/install/windows-install/)* • 
   *[Mac](https://docs.docker.com/desktop/install/mac-install/)* • 
   *[Linux](https://docs.docker.com/engine/install/)*
3. Run this command to run your discord bot 
```bash
docker run -d --name discord-video-downloader-0 \
  --restart unless-stopped \
  -e DISCORD_TOKEN=your_token_here \
  ghcr.io/interstella0/discord-video-downloader:latest
```
4. See your discord bot's output by
```bash
docker logs discord-video-downloader-0
```
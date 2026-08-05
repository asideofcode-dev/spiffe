# Ben Eater 6502 series transcripts

Auto-generated YouTube captions for Ben Eater’s playlist
[Build a 65c02-based computer from scratch](https://www.youtube.com/playlist?list=PLowKtXNTBypFbtuVMUVXNR0z1mu7dp7eH).

- Creator: [Ben Eater](https://eater.net/) / [eater.net/6502](https://eater.net/6502)
- Source video: [“Hello, world” from scratch on a 6502 — Part 1](https://youtu.be/LnzuMJLZRdU)
- Captions are YouTube auto-generated (not official human transcripts)

## Status

**28 of 29** playlist videos have transcript files.

| # | Video ID | Title | Notes |
|---|----------|-------|-------|
| 01 | LnzuMJLZRdU | “Hello, world” from scratch on a 6502 — Part 1 | EN |
| 02 | yl8vPW5hydQ | How do CPUs read machine code? — 6502 part 2 | EN |
| 03 | oO8_2JJV0B4 | Assembly language vs. machine code — 6502 part 3 | EN |
| 04 | FY3zTUaykVo | Connecting an LCD to our computer — 6502 part 4 | EN |
| 05 | xBjQVxVxOxc | What is a stack and how does it work? — 6502 part 5 | EN |
| 06 | i_wrxBdXTgM | RAM and bus timing — 6502 part 6 | **Missing** — caption text unavailable from this environment |
| 07 | omI0MrTWiMU | Subroutine calls, now with RAM — 6502 part 7 | EN |
| 08 | fCbAafKLqC8 | Why build an entire computer on breadboards? | EN |
| 09 | ZYJIakkcLYw | How assembly language loops work | EN |
| 10 | v3-a-zqKfgA | Binary to decimal can’t be that hard, right? | EN |
| 11 | DlEa8kd7n3Q | Hardware interrupts | EN |
| 12 | oOYA-jsWTmc | Interrupt handling | EN |
| 13 | 7aXbh9VUB3U | So how does a PS/2 keyboard interface work? | EN |
| 14 | w1SB9Ry8_Jg | Keyboard interface hardware | EN |
| 15 | dL0GO9SeBh0 | Keyboard interface software | EN |
| 16 | MCi7dCBhVpQ | SPI: The serial peripheral interface | EN |
| 17 | g_koa00MBLg | How do hardware timers work? | EN |
| 18 | AHYNxpqKqwo | The RS-232 protocol | EN |
| 19 | 4alV5LzHLE4 | Let's build a voltage multiplier! | EN |
| 20 | oLYLnb7kpLg | 6502 serial interface | EN |
| 21 | zsERDRM1oy8 | RS232 interface with the 6551 UART | EN |
| 22 | CnA8nG3zYHw | Fixing a hardware bug in software (65C51 UART) | EN |
| 23 | HlLCtjJzHVI | Running Apple 1 software on a breadboard computer (Wozmon) | EN |
| 24 | 7M8LvMtdcgY | Adapting WozMon for the breadboard 6502 | ES (auto-translated captions) |
| 25 | 0q6Ujn_zNH8 | A simple BIOS for my breadboard computer | ES (auto-translated captions) |
| 26 | XlbPnihCM0E | Running MSBASIC on my breadboard 6502 computer | EN |
| 27 | mpIFag8zSWo | How input buffering works | ES (auto-translated captions) |
| 28 | tIOR7kRevPU | Computer noises | EN |
| 29 | jJi5EAWgyEM | Sound synth with a 6502 | EN |

Missing part 6: https://www.youtube.com/watch?v=i_wrxBdXTgM

## File format

```
Title: …
Video ID: …
URL: https://www.youtube.com/watch?v=…
Playlist: Build a 65c02-based computer from scratch
Playlist URL: https://www.youtube.com/playlist?list=PLowKtXNTBypFbtuVMUVXNR0z1mu7dp7eH
Source: …
---

<caption text>
```

## Notes

YouTube blocks many automated caption APIs from cloud IPs. These files were collected from publicly available caption text exposed through page/transcript mirrors. Part 6 only returned the video description (no speech captions) via those paths.

To fill in part 6 (or replace Spanish auto-translations with English) from a residential network:

```bash
pip install youtube-transcript-api
python3 -c "
from youtube_transcript_api import YouTubeTranscriptApi
t = YouTubeTranscriptApi().fetch('i_wrxBdXTgM')
print('\\n'.join(x.text for x in t))
"
```

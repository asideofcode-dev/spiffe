# Ben Eater 6502 Computer Series - Transcripts

This directory contains transcripts from Ben Eater's educational YouTube series "Build a 65c02-based computer from scratch".

**Playlist URL:** https://www.youtube.com/playlist?list=PLowKtXNTBypFbtuVMUVXNR0z1mu7dp7eH

**Creator:** Ben Eater (https://eater.net/)

**Source:** YouTube auto-generated captions (publicly available)

---

## Collection Status

**Total Videos:** 29  
**Transcripts Available:** 11  
**Still Missing:** 18

### ✅ Available Transcripts (11/29)

| # | Video ID | Title | File |
|---|----------|-------|------|
| 01 | LnzuMJLZRdU | "Hello, world" from scratch on a 6502 — Part 1 | `01 - "Hello, world" from scratch on a 6502 — Part 1 [LnzuMJLZRdU].txt` |
| 02 | yl8vPW5hydQ | How do CPUs read machine code? — 6502 part 2 | `02 - How do CPUs read machine code — 6502 part 2 [yl8vPW5hydQ].txt` |
| 04 | FY3zTUaykVo | Connecting an LCD to our computer — 6502 part 4 | `04 - Connecting an LCD to our computer — 6502 part 4 [FY3zTUaykVo].txt` |
| 05 | xBjQVxVxOxc | What is a stack and how does it work? — 6502 part 5 | `05 - What is a stack and how does it work — 6502 part 5 [xBjQVxVxOxc].txt` |
| 08 | fCbAafKLqC8 | Why build an entire computer on breadboards? | `08 - Why build an entire computer on breadboards [fCbAafKLqC8].txt` |
| 09 | ZYJIakkcLYw | How assembly language loops work | `09 - How assembly language loops work [ZYJIakkcLYw].txt` |
| 10 | v3-a-zqKfgA | Binary to decimal can't be that hard, right? | `10 - Binary to decimal can't be that hard, right [v3-a-zqKfgA].txt` |
| 13 | 7aXbh9VUB3U | So how does a PS/2 keyboard interface work? | `13 - So how does a PS-2 keyboard interface work [7aXbh9VUB3U].txt` |
| 16 | MCi7dCBhVpQ | SPI: The serial peripheral interface | `16 - SPI The serial peripheral interface [MCi7dCBhVpQ].txt` |
| 17 | g_koa00MBLg | How do hardware timers work? | `17 - How do hardware timers work [g_koa00MBLg].txt` |
| 19 | 4alV5LzHLE4 | Let's build a voltage multiplier! | `19 - Let's build a voltage multiplier! [4alV5LzHLE4].txt` |

### ❌ Missing Transcripts (18/29)

| # | Video ID | Title | URL |
|---|----------|-------|-----|
| 03 | oO8_2JJV0B4 | Assembly language vs. machine code — 6502 part 3 | https://www.youtube.com/watch?v=oO8_2JJV0B4 |
| 06 | i_wrxBdXTgM | RAM and bus timing — 6502 part 6 | https://www.youtube.com/watch?v=i_wrxBdXTgM |
| 07 | omI0MrTWiMU | Subroutine calls, now with RAM — 6502 part 7 | https://www.youtube.com/watch?v=omI0MrTWiMU |
| 11 | DlEa8kd7n3Q | Hardware interrupts | https://www.youtube.com/watch?v=DlEa8kd7n3Q |
| 12 | oOYA-jsWTmc | Interrupt handling | https://www.youtube.com/watch?v=oOYA-jsWTmc |
| 14 | w1SB9Ry8_Jg | Keyboard interface hardware | https://www.youtube.com/watch?v=w1SB9Ry8_Jg |
| 15 | dL0GO9SeBh0 | Keyboard interface software | https://www.youtube.com/watch?v=dL0GO9SeBh0 |
| 18 | AHYNxpqKqwo | The RS-232 protocol | https://www.youtube.com/watch?v=AHYNxpqKqwo |
| 20 | oLYLnb7kpLg | 6502 serial interface | https://www.youtube.com/watch?v=oLYLnb7kpLg |
| 21 | zsERDRM1oy8 | RS232 interface with the 6551 UART | https://www.youtube.com/watch?v=zsERDRM1oy8 |
| 22 | CnA8nG3zYHw | Fixing a hardware bug in software (65C51 UART) | https://www.youtube.com/watch?v=CnA8nG3zYHw |
| 23 | HlLCtjJzHVI | Running Apple 1 software on a breadboard computer (Wozmon) | https://www.youtube.com/watch?v=HlLCtjJzHVI |
| 24 | 7M8LvMtdcgY | Adapting WozMon for the breadboard 6502 | https://www.youtube.com/watch?v=7M8LvMtdcgY |
| 25 | 0q6Ujn_zNH8 | A simple BIOS for my breadboard computer | https://www.youtube.com/watch?v=0q6Ujn_zNH8 |
| 26 | XlbPnihCM0E | Running MSBASIC on my breadboard 6502 computer | https://www.youtube.com/watch?v=XlbPnihCM0E |
| 27 | mpIFag8zSWo | How input buffering works | https://www.youtube.com/watch?v=mpIFag8zSWo |
| 28 | tIOR7kRevPU | Computer noises | https://www.youtube.com/watch?v=tIOR7kRevPU |
| 29 | jJi5EAWgyEM | Sound synth with a 6502 | https://www.youtube.com/watch?v=jJi5EAWgyEM |

---

## Technical Notes

**Issue Encountered:** YouTube actively blocks automated transcript requests from cloud provider IP addresses (AWS, GCP, Azure, etc.) as an anti-scraping measure. All automated download methods failed with IP blocking errors.

**Methods Attempted:**
- yt-dlp with subtitle download
- youtube-transcript-api Python library
- Direct YouTube API endpoints via curl/requests
- Third-party transcript services (videodb.org - rate limited)

**Limitation:** Cloud-based automation cannot bypass YouTube's datacenter IP blocks without using proxies or authenticated cookies (not recommended as it can result in account bans).

**To Complete Collection:**

The remaining 18 transcripts can be obtained by:

1. **Manual Download from Non-Cloud IP:**
   - Visit each video URL on YouTube from a residential IP address
   - Click the "..." menu under the video
   - Select "Show transcript"
   - Copy the transcript text
   - Save with the appropriate header format

2. **Use Local Machine with youtube-transcript-api:**
   ```bash
   pip install youtube-transcript-api
   python3 download_script.py  # Run from local machine, not cloud
   ```

3. **Browser Extension:**
   - Install a YouTube transcript downloader extension
   - Batch process the remaining video IDs

---

## File Format

Each transcript file contains:
- Header with metadata (title, video ID, URL, playlist info, source)
- `---` separator
- Full transcript text (auto-generated captions from YouTube)

## About the Series

Ben Eater's 6502 series is an educational project where he builds a complete computer from scratch using the WDC 65C02 microprocessor on breadboards. The series covers fundamental computer architecture concepts including:
- CPU operation and machine code
- Memory systems (RAM, ROM)
- Input/output interfaces (LCD, keyboard, serial)
- Interrupts and timing
- Assembly programming
- Running classic software (Wozmon, MSBASIC)

**More Information:** https://eater.net/6502

---

*Last Updated: 2026-08-05*

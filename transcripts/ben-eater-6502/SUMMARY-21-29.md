# Ben Eater 6502 — Videos 21–29 Technical Summary

Dense WHAT/HOW source material for synthesis. Addresses, registers, and software architecture as presented in the series (breadboard 65C02 computer, ~1 MHz).

**Memory map (recurring):**
| Range | Device |
|-------|--------|
| `$0000`–`$3FFF` | RAM (16 KiB; A15=A14=0) |
| `$4000`–`$7FFF` | I/O window (partial decode) |
| `$5000`–`$5003` | 6551 ACIA (A15=0, A14=1, A12=1; RS0/RS1 = A0/A1) |
| `$6000`–`$600F` | 6522 VIA (A15=0, A14=1, A13=1; RS0–3 = A0–A3) |
| `$7000`–`$7FFF` | **Forbidden** — both ACIA and VIA selected |
| `$8000`–`$FFFF` | ROM (32 KiB; A15=1) |
| `$FFFA`–`$FFFF` | IRQ/NMI/RESET vectors |

---

## 21 — 6551 ACIA / UART RS-232 interface

**What.** Replace bit-banged serial (Port A + exact 104 µs/bit loops at 9600 baud) with a 6551 Asynchronous Communications Interface Adapter (ACIA / UART). Hardware shifts bits at programmed baud; CPU moves whole bytes via programmed I/O (PIO). No DMA: CPU remains sole bus master.

**Hardware hookup.**
- Data bus D0–D7 to ACIA (pin order matters; reversed wiring bit-flips all commands/data).
- RS-232 levels still via MAX232 charge pump; ACIA TxD → MAX232 T1IN, MAX232 R1OUT → ACIA RxD. Handshake pins (RTS/CTS/DTR/DSR/DCD) unused initially.
- Baud crystal: **1.8432 MHz** across XTAL1/XTAL2 (pins 6–7), 1 MΩ parallel, ~30 pF from pin 6 to GND.
- Chip selects: CS1̅ from decode NAND (A15 low, A14 high); CS0 = A12. Register selects RS0/RS1 = A0/A1.
- R/W̅ from CPU pin 34 → ACIA pin 28; Φ2 system clock → ACIA pin 27; RES̅ tied to system reset.
- IRQ̅ left unwired (VIA already owns IRQ); open for later.

**Address decode trade-off.** Partial decode (few NANDs) maps ACIA at `$5000`–`$5003` but also aliases; `$7000`–`$7FFF` must never be used (VIA + ACIA both enabled).

**Registers:**
| Addr | Write | Read |
|------|-------|------|
| `$5000` | Transmit data | Receive data |
| `$5001` | Soft reset (any write) | Status |
| `$5002` | Command | Command |
| `$5003` | Control | Control |

**Software deferred to next video** after hardware verified.

---

## 22 — Hardware bug in 65C51 and software workaround

**What.** Program the ACIA for 19200 8N1, receive-to-LCD + echo, and string transmit. Discover WDC 65C51 transmitter-empty status bit is stuck; work around with a timed delay.

**Init sequence.**
1. Soft reset: `STA $5001` (value irrelevant).
2. Control `$5003` = `$1F`: 8-bit word, 1 stop, receiver clock = baud generator, **19200 baud** (bits all 1s in baud field).
3. Command `$5002` = `$0B`: no parity, no echo, Tx IRQ disabled, Rx IRQ disabled, DTR “ready” (handshake unused).

**Status bits used.**
- Bit 3 (`$08`): receive data register full — poll with `LDA status / AND #$08 / BEQ wait`.
- Bit 4 (`$10`): transmit data register empty — **broken on WDC**.

**Receive path.** Loop until bit 3 set → `LDA $5000` → print (LCD) and/or echo via send subroutine.

**Transmit path (intended).** `STA $5000` then poll bit 4 until empty before returning (preserve A on stack around status poll). Message loop: indexed null-terminated string via X.

**Bug.** WDC 65C51 bit 4 always reads “empty.” Burst transmit overwrites the shift register before the prior byte finishes → corrupted/no output. Single-character echo still “works” because human typing is slower than one byte time. Vintage AMI 6551 (e.g. date code 8134) behaves correctly (may need DCD grounded).

**Datasheet evolution.** Older errata omit this; 2021 datasheet documents bit 4 never goes to 0 and recommends a delay because Tx data + shift registers load together.

**Workaround.** After each transmit write, delay ~**520 CPU cycles** at 1 MHz = 10 bit times at 19200 (start+8data+stop). Example: X=100 loop of `DEX` (2) + `BNE` taken (3) ≈ 500 cycles + JSR/PHA/PLA/RTS ≈ 520. Delay is baud-rate dependent; still far simpler than bit-banging.

---

## 23 — Running Wozmon (Apple 1 monitor)

**What.** Port Steve Wozniak’s Apple I hex monitor (~248 bytes code + vectors in `$FF00`–`$FFFF`) to the breadboard machine using serial I/O instead of Apple keyboard/display.

**Capabilities demonstrated.**
- Examine: `FF00`, range `FF00.FF0F`, full ROM dump.
- Deposit: `0300:BE`, multi-byte deposit.
- Run: set address then `R`.
- Peek/poke I/O: VIA Port A/B at `$6001`, DDR `$6003`, LCD at `$6000` via pasted command sequences.
- Enter Apple I test program at `$0000` (calls `FFEF` echo); assemble host programs with `ORG $1000`, hexdump into Wozmon deposit lines, run, patch typos in RAM (e.g. ASCII `$75`→`$72`).

**Wozmon RAM.** Input buffer `IN` at `$0200`–`$027F`. Reset prompt is backslash.

**Adaptation size.** Serial changes added **+2 bytes**; original had 2 unused bytes → still fits last 256-byte ROM page at `$FF00`.

---

## 24 — Adapting WozMon (detail)

**What.** Line-by-line deltas from Apple I `$D010`–`$D013` KBD/DSP hardware to 6551 at `$5000`–`$5003`, while staying ≤256 bytes and keeping **ECHO at `$FFEF`** (Apple I manual test program embeds that address).

**GETKEY.** Replace bit-7-ready poll with: read status, `AND #$08`, `BEQ` wait; then `LDA $5000`. Adds 2-byte `AND #$08` (uses Woz’s spare bytes).

**ASCII bit 7.** Apple keyboard returns ASCII with bit 7 set; serial returns normal 7-bit ASCII. Prefer changing literals over OR-`$80` on every key (saves code):
| Symbol | Apple (bit7=1) | Serial |
|--------|----------------|--------|
| BS | `$DF` | `$08` |
| ESC | — | `$1B` |
| `\` | `$DC` | `$5C` |
| CR | `$8D` | `$0D` |
| `.` | `$AE` | `$2E` |
| `:` | `$BA` | `$3A` |
| `R` | `$D2` | `$52` |
| space | `$A0` | `$20` |

Hex parse: XOR mask `$B0`→`$30`. Hex print: OR `$B0`→`$30`; digit check `< $BA`→`< $3A`.

**ECHO.** Write A to `$5000`, then software delay (load A=`$FF`, decrement to 0) because TDRE is broken; PHA/PLA preserve A. Echo grew +2 bytes → net +4 before reclaiming elsewhere.

**RESET init.** Replace KBD/DSP setup with ACIA: `LDA #$1F / STA $5003`, command `$0B`→**`$8B`** via **Y** so Y left ≥`$7F`. Clever dependency: first `INY` after reset must overflow into ESC path (backslash + re-init). Bit 7 of command = PMC; datasheet allows any parity-mode combo when parity disabled → `$8B` safe. Net reset code **−3 bytes**.

**MODE variable.** Store/block-examine modes encoded in top bits of `.` / `:`. Colon already ASL’d into store mode. Dot needs **two** ASL to place `10` in top bits → extra ASL (+2 bytes), absorbed by original unused bytes. Resulting mode values differ from Apple (e.g. block examine `$B8`) but BIT tests on bits 6–7 still work.

---

## 25 — Simple BIOS (character in/out) + CC65 ROM layout

**What.** Introduce CC65 (`ca65`/`ld65`) as the ROM build system; factor a minimal BIOS (character in/out) so higher software (MSBASIC) need not know ACIA details.

**Build model.** Assembler emits relocatable `.o` with symbol metadata; linker places code per config. Drop `.org`; use `.segment` + memory map. `.setcpu "65C02"` for `DEA` etc.

**Example linker layout (final Wozmon-at-top form):**
- MEMORY: RAM `$0000` size `$4000` rw; ROM `$8000` size `$7F00` (or similar) ro fill; WOZMON `$FF00` size `$FA`; RESETVEC `$FFFA` size 6.
- SEGMENTS: BIOS → ROM; WOZMON → WOZMON; RESETVEC → RESETVEC.
- Reset vector little-endian fills automatically from `reset` label.

**BIOS.s as hub.** Defines ACIA register symbols; `char_in` / `char_out` (poll status / Tx with delay); `.include "wozmon.s"`; owns `.segment "RESETVEC"`. Debug info + `ld65 -Ln` symbol file → e.g. **char_in `$8000`**, **char_out `$8011`** (addresses depend on link order). External software JSR those addresses with char in A — classic BIOS contract.

---

## 26 — Porting MSBASIC (CC65, config, defines)

**What.** Fork mist64/msbasic (or equivalent); add `-D eater` port; link BIOS + Wozmon into one 32 KiB ROM image; run Microsoft BASIC 2A on the breadboard.

**Build plumbing.** `make.sh` loops versions: `ca65 -D <ver> msbasic.s` → `ld65 -C <ver>.cfg`. Add `eater` to list. `defines.s`: `IF .def(eater)` → include `defines_eater.s`. `extra.s`: include `bios.s` when eater.

**defines_eater.s (essentials).**
- `CONFIG = 2A` (Commodore-ish base).
- Zero-page orgs non-overlapping; leave room for input buffer (bump zp starts so buffer fits; eater puts buffer in ZP unlike CBM2).
- `CONFIG_SCRTCH_ORDER = 2` (required defined; behavior opaque).
- `RAMSTART2 = $0400`, `STACK_TOP`, `SPACE_FOR_GOSUB`, WIDTH constants kept from CBM until proven wrong.
- Monitor hooks: **do not hardcode Commodore `$FFD2`/`$FFE4`** — define `MONRDKEY`/`MONCOUT` as aliases on BIOS `char_in`/`char_out` (or labels at those routines). Stub `LOAD`/`SAVE`/`ISCNTC` as RTS initially.

**Linker cfg.** ROM base `$8000`, fill yes, size shrinks for Wozmon + vectors; WOZMON at `$FF00` (later `$FE00` when Wozmon grows); RESETVEC `$FFFA`; BIOS segment into ROM; dummy segments retained from upstream.

**Name clash.** Rename Wozmon `RUN` → `RUNPROGRAM`.

**Bring-up.** Cold start at symbol `COLD_START` (e.g. `$9F06` from `.lbl`); from Wozmon `9F06R`. Memory size / terminal width: Enter for autodetection → ~15359 bytes free. Easter egg: answer memory size with `A` → “Written by Weiland & Gates”.

**Fixes.**
- Extra blank lines: terminal was expanding CR→CRLF while BASIC emits CR+LF; teach Wozmon to emit CR+LF (grows past 250 bytes → move WOZMON to `$FE00`, size `$1FA`, ROM `$7E00`).
- Ctrl-C: platform `iscntc` include chain → `eater_iscntc.s`: JSR `MONRDKEY`; BCC not_ctrlc; CMP **`#3`** (immediate, not `$03` abs!); BNE not; else fall through to STOP. Bug was `CMP $03` (memory).
- Convenience entry: `header.s` under `eater`: `JMP COLD_START` at `$8000` → Wozmon `800R`.
- Line editing: `_` as backspace in BASIC input.

---

## 27 — Input buffering (circular buffer + IRQ)

**What.** Paste/type at full 19200 without dropping chars. ACIA Rx IRQ fills a 256-byte circular buffer; `char_in` drains it. Removes terminal “pacing.”

**Hardware.**
- Command register: clear bit 1 → `$8B` becomes **`$89`** (enable Rx IRQ).
- ACIA IRQ̅ (pin 26) → CPU IRQ (pin 4); disconnect VIA IRQ for now.
- Open-drain IRQ needs pull-up (~1 kΩ).
- Ground **DCD** and **DSR** (pins 16/17) or floating edges cause spurious IRQs (bits 5–6 also IRQ sources).

**Memory.**
- Read/write pointers: 1 byte each in ZP at new `ZP_START0 = $00` (shift other ZP_STARTs +2).
- Buffer: linker MEMORY `INPUT_BUF` at **`$0300`**, size `$0100`, rw, **not** written to ROM file; SEGMENT load there.

**Buffer API.**
- `init_buffer`: equalize read/write pointers (empty). Call early on reset, before CLI.
- `write_buffer`: X ← write_ptr; store A at buf,X; INC write_ptr. (wraps naturally at 256).
- `read_buffer`: X ← read_ptr; A ← buf,X; INC read_ptr.
- `buffer_size`: SEC; LDA write; SBC read → count of pending bytes (wrap-safe).

**IRQ handler.** PHA/PHX; **LDA ACIA_STATUS** (ack IRQ — mandatory or IRQ sticks low → infinite re-entry); optionally verify cause; LDA ACIA_DATA; JSR write_buffer; PLX/PLA; RTI. ~60 cycles vs ~520 µs/char at 19200 → ~10% CPU under continuous paste.

**char_in.** JSR buffer_size; BEQ no_key (carry clear); else JSR read_buffer (preserve X via stack). Wozmon GETKEY becomes JSR char_in / BCC wait; drop redundant echo (BIOS echoes).

**Limit.** 256-byte buffer; paste >256 unread bytes overruns (write lapping read). Flow control deferred.

---

## 28 — Computer noises (square wave via VIA Timer1 + LM386)

**What.** Generate tones by freerunning VIA Timer 1 toggling **PB7**, amplify with LM386 into 8 Ω speaker. Expose as BASIC `BEEP`.

**VIA Timer 1.** 16-bit counter counts down at Φ2 (1 MHz). Latches reload on zero. ACR bits 7–6 = **`11`**: continuous mode + PB7 enable → invert PB7 each underflow = square wave. PB0–6 used by LCD; PB7 free (pin 17).

**Registers (VIA base `$6000`):**
| Addr | Role |
|------|------|
| `$6004` / `$6005` | T1 counter low/high — write low latches then high starts countdown and loads both |
| `$6006` / `$6007` | T1 latches (optional; writing counter also fills them) |
| `$600B` | ACR; `$C0` enables T1 continuous + PB7 |

**Frequency.** Half-period = N µs (N clock cycles). Full period = 2N → f = 1e6/(2N). A440: N ≈ **1136** (not 2273 — that gives ~220 Hz).

**BASIC `BEEP` (sound.s, `#ifdef eater`).**
1. `FRMNUM` + `GETADR`/`MAKE_INT` → FAC+3/+4 as 16-bit period.
2. If period == 0 → silent path (no ACR enable) but still honor duration.
3. Else STA `$6004`/`$6005`, LDA `#$C0` / STA `$600B`.
4. Optional 2nd param (0–255) via `CHKCOM` + `GETBYT` → nested delay (Y=`$FF` inner) then clear ACR to stop.
5. Duration 0 → leave tone running (skip delay/stop).

**Analog.** LM386 min parts: VCC pin 6, GND 4, −IN (2) GND, +IN (3) via 10 kΩ pot from PB7; out pin 5 → 0.05 µF + 10 Ω to GND, and 250 µF series to speaker to GND. Pot = volume.

**Demo.** Arrays of note periods + durations; `DATA`/`READ`/`BEEP N(I),D(I)` play tunes.

---

## 29 — Sound synth extensions (duty cycle, dual IRQ, filter)

**What.** Variable pulse-width square waves by alternating two half-periods on each T1 IRQ; diode-OR VIA + ACIA onto CPU IRQ; optional RC low-pass toward triangle-like tones. Teaser for SID.

**Hardware IRQ sharing.** CPU IRQ active-low with pull-up. WDC **65C22S** IRQ is totem-pole (not open-drain like older N). Series **diodes** from each chip’s IRQ̅ into the shared line isolate highs so either device can pull IRQ low. Datasheet recommends this for totem-pole IRQ.

**IRQ dispatch upgrade.**
1. Read ACIA status (acks UART IRQ). **BPL** skip Rx path if bit 7 clear (not ACIA).
2. Else read data → write_buffer as before.
3. LDA **IFR `$600D`**; BPL exit if VIA not requesting.
4. Else timer-half-cycle work; exit.

**Duty-cycle mechanism.** Zero-page `sound1`/`sound2` (2 bytes each). On T1 IRQ: read Port B; BMI → load T1 latches from sound2, else from sound1 (or vice versa). Writing **T1 latch high (`$6007`)** clears T1 interrupt (also reading T1C-L works). Next half-cycle uses the other interval → arbitrary on/off times at same fundamental frequency.

**BEEP API extension.** `BEEP half1, half2, duration` — store both halves into sound1/sound2 and into T1 counters; enable ACR `$C0` **and** IER: write **`$C0`** to `$600E` (bit7=1 set-enable, bit6=T1). On silence: IER **`$40`** (bit7=0 clear-enable for T1) and ACR 0.

**Examples.** `BEEP 1136,1136,100` → 50% 440 Hz. `BEEP 2022,250,100` → same pitch, different timbre.

**Analog shaping.** 10 µF from amp input to GND with the volume pot ≈ low-pass → 50% square becomes near-triangle (mellower). Asymmetric duty + same RC ≠ clean sawtooth without diode/asymmetric R; still audible variety. Next planned step: Commodore **SID**.

---

## Software architecture arc (21→29)

```
Host terminal (RS-232)
        ↕ MAX232
     6551 ACIA @ $5000   ──IRQ──┐
        ↕ PIO bytes              │ diode-OR → 6502 IRQ
     BIOS char_in/out            │
        ↕                        │
  circular buf @ $0300 ◄── IRQ handler (Rx + later T1)
        ↕
  Wozmon @ $FE00/$FF00  /  MSBASIC @ $8000 (JMP COLD_START)
        ↕
  VIA @ $6000 ── LCD, Timer1→PB7 → LM386 → speaker
ROM $8000–$FFFF; vectors @ $FFFA; RAM $0000–$3FFF
```

**Init chain (mature system):** RESET → Wozmon reset → ACIA control `$1F`, command `$89` (IRQ Rx) → `init_buffer` → … CLI. BASIC entered via `$8000` jump. Sound optional: ACR/IER programmed only while `BEEP` active.

**Key constants checklist.** ACIA `$5000`–`$5003`; VIA `$6000`–`$600F` (T1C `$6004`/`05`, T1L `$6006`/`07`, ACR `$600B`, IFR `$600D`, IER `$600E`, PB7); ROM `$8000`; Wozmon `$FF00` then `$FE00`; RESET `$FFFC`; input buffer `$0300`; crystal 1.8432 MHz; CPU 1 MHz; default serial 19200 8N1; Tx delay ~520 cycles; Rx IRQ handler ~60 cycles.

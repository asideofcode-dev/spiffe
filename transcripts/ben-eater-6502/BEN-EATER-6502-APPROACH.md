# Building a Computer from Scratch: Ben Eater’s 6502 Approach

A synthesis of Ben Eater’s YouTube series *[Build a 65c02-based computer from scratch](https://www.youtube.com/playlist?list=PLowKtXNTBypFbtuVMUVXNR0z1mu7dp7eH)*, drawn from the series’ auto-generated captions. It walks through **what** he builds and **how**—chips, address maps, bus timing, protocols, and software architecture—as one continuous path from a bare microprocessor to BASIC, a keyboard, serial I/O, and sound.

Companion materials: [eater.net/6502](https://eater.net/6502). Source video that starts the series: [“Hello, world” from scratch on a 6502 — Part 1](https://youtu.be/LnzuMJLZRdU).

---

## 1. The goal and the method

Ben’s stated goal is deliberately extreme: print `Hello, world` **without** standing on an operating system, a language runtime, or even a finished computer. He starts with a single microprocessor and asks what it takes—electrically and programmatically—to get from that chip to text on a display, then keeps going until the breadboard machine can run Microsoft BASIC, talk over RS-232, accept a PS/2 keyboard, and make tones through a speaker.

The method is consistent throughout:

1. **Make one thing observable.** Prefer a slow or single-steppable clock and an Arduino Mega as a bus monitor over guessing.
2. **Add the minimum hardware that unlocks the next behavior.** ROM before RAM; VIA before LCD; UART before Wozmon; BIOS before BASIC.
3. **Decode addresses sparsely.** Waste address space to save logic gates; document the forbidden aliases.
4. **When software gets ugly, introduce the missing abstraction** (subroutines → stack/RAM; busy flag; IRQ; circular buffer; BIOS entry points).
5. **When the clock gets fast, respect datasheets.** Timing that “worked” at a few hertz fails at 1 MHz.

Settled coarse memory map by the middle of the series (and largely unchanged thereafter):

| Range | Device |
|-------|--------|
| `$0000`–`$3FFF` | RAM (stack lives in `$0100`–`$01FF`) |
| `$4000`–`$4FFF` | Unused / future |
| `$5000`–`$5003` | 6551 ACIA (UART) — added later |
| `$6000`–`$600F` | 6522 VIA (ports, timers, keyboard CA1) |
| `$7000`–`$7FFF` | **Forbidden** once ACIA exists (partial decode alias) |
| `$8000`–`$FFFF` | 32 KiB EEPROM (program + vectors at top) |

---

## 2. Bringing up the CPU with nothing but NOPs

### 2.1 Why the W65C02

Ben uses the modern **W65C02** (static CMOS), not the 1970s NMOS part. The datasheet is short (~30 pages). Critically, **PHI2 may be held high or low** without losing internal register state, so an adjustable 555-based clock module can halt and single-step the machine. An original 6502 would simply fail if the clock stopped or ran too slowly.

Power: **VDD pin 8** → +5 V, **VSS pin 21** → ground. Inputs that must not float are tied high so the CPU actually runs: **RDY**, **BE** (bus enable), **IRQB**, **NMIB**, and **SOB** per datasheet advice. **Reset (pin 40)** is pulled up through 1 kΩ and can be pulsed low with a button. **PHI2 (pin 37)** is the system clock.

### 2.2 Seeing the bus

With a few address LEDs the chip “does something,” but the pattern is opaque. At these speeds a logic analyzer is overkill. Ben wires an **Arduino Mega** as a cycle logger:

- Address A15…A0 on Mega digital pins  
- Data D7…D0 on more pins  
- **RWB** (read/write) sampled  
- **PHI2** on an interrupt pin so each rising edge prints one line: address, data, R/W  

Without anything driving the data bus, reads return noise and the CPU wanders randomly. He then ties each data line through 1 kΩ to a fixed pattern **`$EA`**. Soft resistors still allow the CPU to drive writes later. Behavior collapses into something readable: endless reads, address counting.

### 2.3 Reset, vectors, and the first “program”

The datasheet’s **seven-clock reset sequence** appears on the monitor, then two reads at **`$FFFC` / `$FFFD`**—the **reset vector**. With the bus hardwired to `$EA`, those bytes load the program counter with **`$EAEA`**. The next fetch is again `$EA`, which the opcode matrix defines as **NOP** (implied addressing, two clocks). The machine then walks forever doing nothing—but it is unmistakably **fetching and executing**. That is the conceptual bridge to ROM: give different addresses different bytes, and you have a program.

---

## 3. ROM, a memory map, and memory-mapped I/O

### 3.1 EEPROM in the upper half

An **AT28C256** (32 KiB) is programmed offline (e.g. TL866 / MiniPro). The CPU has 16 address bits (64 KiB space); the EEPROM has A0–A14. Ben maps ROM into the **upper half** so the reset vector addresses still land in silicon:

- Invert **A15** into the EEPROM’s active-low **/CE** (one gate of a **74HC00** NAND wired as an inverter).  
- **/OE** tied low, **/WE** tied high (read-only in-circuit).  

CPU `$8000` is EEPROM offset 0; CPU `$FFFF` is the last ROM byte. Reset vector bytes at EEPROM `$7FFC`/`$7FFD` appear at CPU `$FFFC`/`$FFFD`.

ROM images are assembled as exactly **32768-byte** binaries (Python first, later assemblers). A first hand-written program:

```text
A9 42        ; LDA #$42
8D 00 60     ; STA $6000
```

with reset vector `$8000`. The monitor shows the write of `$42` at `$6000`—but nothing lives there yet. Insight Ben leans on for the whole series: the 6502 has **no separate I/O instructions**; peripherals are devices that decode addresses and participate on the same data bus for one cycle.

### 3.2 The 6522 VIA as the first peripheral

He adds a **W65C22 VIA**, sharing D0–D7, PHI2, RWB, and reset. Chip-select decode for “around `$6000`” uses only high bits **A15=0, A14=1, A13=1**, ignoring lower bits. That **wastes ~8 KiB** of address space (`$6000`–`$7FFF`) for sixteen registers—but costs almost no gates (reuse the A15 inverter, one more NAND, wire A13 to CS1). Register selects RS0–RS3 = A0–A3:

| Address | Register |
|---------|----------|
| `$6000` | Port B data |
| `$6001` | Port A data |
| `$6002` | DDRB |
| `$6003` | DDRA |

First demo: set DDRB to `$FF`, alternate `$55` / `$AA` on Port B into LEDs, `JMP` forever. Machine code becomes unbearable; next comes assembly.

### 3.3 Assembly with vasm

**vasm** (6502, old-style syntax, binary output) replaces hand hex. Conventions that matter:

- Instructions must be indented (unindented tokens are labels).  
- **`$`** means hex; **`#`** means immediate—without `#`, `LDA $FF` becomes zero-page `A5`, not immediate `A9`.  
- `.org $8000` aligns assembled addresses with the CPU’s view of ROM.  
- `.org $FFFC` / `.word reset` places the vector; pad to 32 KiB.  
- Labels remove fragile absolute jump targets.

A rotating-bit LED demo (`ROR`, carry as a ninth bit) proves the toolchain before any display.

---

## 4. An LCD, then the stack crisis

### 4.1 HD44780 on the VIA

A 16×2 HD44780-compatible LCD replaces the LEDs:

- **D0–D7 → Port B**  
- **E, R/W, RS → Port A** (top bits)  
- Contrast via pot on V0; 8-bit mode for simplicity  

Initialization follows the datasheet (function set, display on, entry mode). Protocol: put a byte on Port B, set RS/RW, pulse E. Commands with RS=0; character data with RS=1. The first “Hello, world” is copy-pasted blocks of setup-and-strobe—works, ~300+ bytes, and deliberately ugly. Subroutines are the obvious cleanup.

### 4.2 JSR/RTS without RAM

`JSR lcd_instruction` / `JSR print_char` shrink the source and clarify intent—then the machine fails after programming. Single-stepping shows:

1. Opcode `$20` (JSR) writes the return address at **`$01xx`**.  
2. The subroutine runs.  
3. **RTS (`$60`)** tries to pull that address back and gets bus noise, jumping into garbage.

The 6502 **hardware stack is fixed in page `$0100`–`$01FF`**, indexed by the 8-bit **S** register. JSR pushes and decrements S; RTS pulls. Nested calls and `PHA`/`PLA` need the same page. S powers up arbitrary; Ben recommends **`LDX #$FF` / `TXS`** at startup so the stack grows down from `$01FF`.

Root cause: **there is still no RAM** at `$0100`. Pushes vanish; pulls are noise. Subroutines are not a software luxury—they are a **hardware dependency**.

---

## 5. RAM, bus timing, and a working stack

*(Part 6’s caption body was unavailable in this archive; the following matches Ben’s own recap in part 7 and the finished decode.)*

A **32K SRAM** (HM62256-class) gets A0–A14, D0–D7, and **/WE ← RWB**. Intended window: **`$0000`–`$3FFF`** (A15=0, A14=0)—zero page, stack, and general RAM.

Naive chip-select from address bits alone is unsafe. Addresses and R/W are not stable for the entire clock period; asserting **/CS** (or write enable) while the bus is still settling causes **spurious writes**. The 6502 guarantees a clean access window while **PHI2 is high**. Solution: **qualify RAM chip select with the clock**.

Finished glue logic (74HC00):

- **A14 → RAM /OE** (outputs only when A14 low).  
- Existing A15 inverter shared with ROM decode.  
- **NAND(inverted A15, PHI2) → RAM /CS** so /CS is low only when the address is in the low half **and** PHI2 is high.  
- Unused NAND inputs tied high.

With that wired, the same JSR/RTS hello-world ROM works. The Mega shows pushes to `$01FF`/`$01FE` and correct pulls on RTS. Software polish: send LCD **clear display** (`$01`) before printing. Next pressure: replace the slow 555 clock with a real **1 MHz** oscillator.

---

## 6. Real speed: breadboard physics and the busy flag

### 6.1 Why 1 MHz on a breadboard is nontrivial

Breadboards add capacitance and inductance; contacts are imperfect. Decoupling (**0.1 µF** across rails, ideally per chip) matters. Square clocks are rich in harmonics; the W65C02 wants **rise/fall ≤ ~5 ns**. A canned 1 MHz oscillator, wired short to CPU and VIA, meets that; the old 555 module did not, but was “fine” when everything was slow.

### 6.2 Hello world breaks at speed

After the clock upgrade, LCD init still happens but the message vanishes. The datasheet had warned: check the **busy flag** before issuing the next command. At hertz-scale clocks, every command finished “for free.” At 1 MHz the CPU outruns the controller.

NOP padding to wait ~1.5 ms needs hundreds of NOPs—absurd. Proper fix: subroutine **`lcd_wait`**:

1. `PHA` (save caller’s byte).  
2. DDRB = inputs; set RS=0, R/W=1; pulse E; read Port B.  
3. Mask bit 7; loop while busy.  
4. Restore DDRB; `PLA`; `RTS`.  

Call it from every LCD instruction and print routine. Scope traces on E show a long busy-poll burst for clear, then crisp character strobes.

### 6.3 Indexed strings

Message text becomes `.asciiz "Hello, world!"` with:

```text
LDX #0
loop:  LDA message,X
       BEQ done
       JSR print_char
       INX
       JMP loop
```

Ben calls hello world “done”—then immediately opens harder problems: numbers, interrupts, keyboards, serial, classic software.

### 6.4 Binary to decimal without DIV

To print a 16-bit value (e.g. 1729) he implements repeated divide-by-10 using **rotate-left and trial subtract 10** over a 32-bit workspace in RAM—sixteen iterations per digit, remainder → ASCII via `ADC #'0'`. Digits emerge least-significant-first; a small RAM buffer inserts each new digit at the front before printing. No divide opcode required—only shifts, add/sub, and patience.

---

## 7. Interrupts: from a raw button to the VIA

### 7.1 IRQ vs NMI

Vectors at the top of ROM:

| Vector | Address |
|--------|---------|
| NMI | `$FFFA` |
| Reset | `$FFFC` |
| IRQ/BRK | `$FFFE` |

**/IRQ (pin 4)** is **level-sensitive** and maskable (`CLI`/`SEI`). Holding it low retriggers forever after each `RTI` if the source isn’t cleared—disastrous for a raw button at 1 MHz. **/NMI (pin 6)** is **edge-sensitive** and unmaskable—better for “highest priority,” worse for everyday peripherals. Ben’s teaching point: peripherals should **latch** an event and release `/IRQ` only when software acknowledges.

### 7.2 VIA as interrupt controller

Wire VIA **/IRQ → CPU /IRQ**. Button → VIA **CA1**. Configure:

- **IER `$600E`**: enable CA1 (write with bit7=1 to set enables).  
- **PCR `$600C`**: CA1 negative active edge.  
- Clear CA1 by **reading/writing Port A** (`$6001`)—the ACK.

Handler: do work (e.g. increment a counter), ACK, `RTI`. Prefer `BIT $6001` when you must not clobber A. Software debounce loops are possible but laggy; hardware debounce is preferred.

This pattern—**peripheral owns the latch; CPU owns the vector; software ACKs the source**—repeats for keyboard frames, UART receive, and timer ticks.

---

## 8. PS/2 keyboard: protocol, hardware, software

### 8.1 Protocol

PS/2 uses open-collector clock and data, idle high. Each packet is **11 bits**: start 0, 8 data **LSB first**, odd parity, stop 1, clocked by the keyboard on falling edges. Scan codes (Set 2): make codes, break as `$F0` + code, extended `$E0` prefix. Shift is just another key; the host tracks modifiers.

### 8.2 One interrupt per byte, not per clock

Clocking ~every 85 µs would flood a 1 MHz CPU. Ben builds a **frame detector**: invert clock → diode/RC envelope that stays high during the 11-pulse burst and decays afterward → **74HC14 Schmitt** for clean thresholds → rising edge = “byte complete.” That edge:

1. Latches eight data bits from cascaded **74HC595** shift registers into VIA Port A.  
2. Fires VIA **CA1** (PCR set for the positive/completion edge).

### 8.3 Software

ISR reads Port A (scan code + ACK), maps through ROM tables (unshifted / shifted), and writes ASCII into a **256-byte ring buffer** (`$0200`–`$02FF`) with write/read pointers. Main loop drains the buffer to the LCD under brief `SEI`/`CLI` when comparing pointers. Flags track release (`$F0`) and shift state. Result: typed characters appear; Shift yields capitals—without the CPU bit-banging every clock edge.

---

## 9. SPI as bit-banged generality

SPI is presented as the contrast class to UART: **controller-driven clock**, full duplex, mode bits CPOL/CPHA, chip-select per device. Ben bit-bangs SCLK/MOSI/MISO/CS on VIA Port A to a BME280-class sensor: assert CS, shift address+R/W, clock data, deassert CS. Chip ID `$D0` → `$60` is the smoke test; temperature reads follow. Lesson: when the peripheral doesn’t generate the clock, software owns timing—and slow 6502 loops are still fine.

---

## 10. Hardware timers: stop burning NOPs

VIA **Timer 1** (`$6004`/`$6005`, latches `$6006`/`$6007`, ACR `$600B`, IFR/IER):

- **One-shot**: precise delays without nested DEX loops.  
- **Free-run**: reload from latches; IRQ every N+2 Φ2 cycles → system tick (e.g. 10 ms).  

Main code becomes cooperative: compare a 32-bit `ticks` counter to per-task deadlines (blink LED, refresh LCD). The CPU is free between ticks. This foreshadows sound, where Timer 1’s PB7 toggle mode becomes an audio square wave.

---

## 11. RS-232: levels, soft UART, then a real ACIA

### 11.1 Protocol and voltages

Idle **mark** = negative voltage = logical 1; **space** = positive = 0. Framing is asynchronous: shared baud rate, **start bit** resyncs, then data (LSB first), optional parity, stop bits. At 9600 baud, ~104 µs/bit; 8N1 → 10 bit times per character.

A discrete NPN level shifter turns RS-232 into 5 V logic on a VIA pin for experiments. Soft-UART receive: wait for start, sample mid-bit with timed loops, shift into a byte, print on LCD. Soft transmit uses similar timing. It works—and burns the CPU.

### 11.2 MAX232 and the 6551

A **MAX232** charge-pump transceiver (1 µF caps) produces proper ±RS-232 from 5 V. Then a **6551 ACIA** takes over shifting:

| Addr | Role |
|------|------|
| `$5000` | Data (Tx write / Rx read) |
| `$5001` | Soft reset (write) / Status (read) |
| `$5002` | Command |
| `$5003` | Control |

Decode: A15=0, A14=1, A12=1 → base `$5000`, with **`$7000`–`$7FFF` forbidden** (VIA+ACIA both selected under partial decode). Baud crystal **1.8432 MHz**. Typical init: Control `$1F` (19200 8N1), Command `$0B` (no parity, IRQs off initially).

### 11.3 The WDC 65C51 transmitter bug

Receive-data-full (status bit 3) works. **Transmitter-empty (bit 4) sticks “empty” on WDC parts**—burst sends overwrite the shift register. Vintage AMI 6551 behaves; modern silicon needs a **software delay** (~520 cycles at 1 MHz ≈ 10 bit times at 19200) after each Tx write. Echo-as-you-type still looked fine because humans are slower than one byte time—the bug appears under string transmit. Datasheets eventually document the erratum; Ben’s fix is the delay.

---

## 12. Wozmon, BIOS, and Microsoft BASIC

### 12.1 Porting Apple I’s monitor

Steve Wozniak’s monitor (~248 bytes) lives in `$FF00`–`$FFFF` on the Apple I: examine memory, deposit bytes, run programs. Ben keeps that contract but swaps keyboard/display hardware for the ACIA:

- Poll Rx full (`AND #$08`) instead of Apple’s bit7-ready keyboard.  
- Rewrite ASCII literals (Apple set bit 7 on keys; serial does not).  
- Echo via ACIA + Tx delay (because TDRE is broken).  
- Init ACIA in reset; leave **Y ≥ `$7F`** so Woz’s clever `INY` overflow into the escape/backslash path still works (command `$8B`).  
- Keep **ECHO at `$FFEF`** so Apple’s sample program that JSRs `$FFEF` still runs.  

Still fits in 256 bytes (using Woz’s two unused bytes as slack).

### 12.2 A tiny BIOS

With **ca65/ld65**, ROM layout becomes linker memory blocks and `.segment`s instead of scattered `.org`s. A **BIOS** layer exports `char_in` / `char_out` at stable linked addresses; Wozmon and later BASIC call those instead of touching `$5000` directly. Reset vector segment sits at `$FFFA`. Symbol files from the linker tell higher software where the entry points landed.

### 12.3 MSBASIC on the breadboard

Fork of the multi-target Microsoft BASIC tree: add `-D eater`, platform defines (ZP layout, `RAMSTART`, monitor hooks pointing at BIOS), and a linker config that packs BIOS + BASIC + Wozmon + vectors into one 32 KiB image. Cold start via a JMP at `$8000` or a Wozmon `R` at the `COLD_START` symbol. Fixes along the way: CR/LF vs terminal expansion, Ctrl-C detection (`CMP #3` immediate—not `CMP $03` absolute), backspace as `_`. Memory size prompt → tens of KB free. The breadboard is now a 1970s-style microcomputer you can type on.

---

## 13. Keeping up with the terminal: IRQ + ring buffer

Pasting BASIC listings at 19200 drops characters when `char_in` polls slower than the wire. Fix:

1. ACIA command **`$89`**: enable receive IRQ.  
2. ACIA `/IRQ` → CPU `/IRQ` (pull-up; ground **DCD/DSR** or they spuriously interrupt).  
3. 256-byte buffer at **`$0300`**; ZP read/write pointers.  
4. ISR (~60 cycles): read status (ACK), read data, `write_buffer`, `RTI`.  
5. `char_in` becomes “if buffer nonempty, pop”—Wozmon and BASIC automatically benefit.  

At 19200, a character lasts ~520 µs; the ISR is ~60 µs → ~10% CPU under continuous paste. Limit: 256 unread bytes before overrun (flow control left for later).

---

## 14. Sound: Timer 1, an amplifier, then timbre

### 14.1 Square waves on PB7

VIA Timer 1 in **continuous mode with PB7 enabled** (ACR `$C0`) toggles **PB7** each underflow—hardware square wave. Period count N at 1 MHz → frequency `1e6 / (2N)` Hz (A440 ≈ **N = 1136**). An **LM386** minimum circuit (pot for volume, coupling cap, 8 Ω speaker) turns that pin into audible tone. BASIC gains **`BEEP period[,duration]`**.

### 14.2 Synth tricks

- Diode-OR VIA and ACIA IRQs onto one CPU line (WDC VIA IRQ is totem-pole; diodes isolate).  
- On each T1 IRQ, alternate two half-periods (`sound1` / `sound2`) for **variable duty cycle** at the same pitch.  
- Optional RC low-pass toward mellower, near-triangle tones.  
- Tease of a SID as the next rabbit hole.

---

## 15. The architecture as one picture

```text
                 PS/2 keyboard
                      │
              frame detect + 74HC595
                      │ CA1 + Port A
                      ▼
 Host USB-serial ◄─► MAX232 ◄─► 6551 ACIA @$5000 ──┐
                                                   │ IRQ (diode-OR)
              ┌────────────────────────────────────┼──────────────┐
              │            W65C02 @ 1 MHz          │              │
              │         PHI2, RWB, A[15:0], D[7:0] │              │
              └──────┬───────────────┬─────────────┴──────┬───────┘
                     │               │                    │
              AT28C256 ROM      HM62256 RAM          W65C22 VIA @$6000
              @$8000–$FFFF     @$0000–$3FFF         │
              (+ vectors)      (stack $0100)        ├─ LCD (PB + PA ctrl)
                                                    ├─ Timer1 → PB7 → LM386 → speaker
                                                    └─ SPI bit-bang / other pins

 Software layers (ROM):
   RESET → ACIA init → buffer init → …
        → BIOS char_in/out
        → Wozmon (debug/monitor)
        → MSBASIC (JMP COLD_START @ $8000)
        → optional BEEP / IRQ handlers
```

---

## 16. Design principles distilled

1. **Observe before you abstract.** The Arduino bus monitor turns “the chip is broken” into “the vector is wrong” or “the stack pull failed.”  
2. **Static silicon and a controllable clock** make education possible; speed comes last.  
3. **Memory map is a product of decode cost.** Partial decode is fine if you document aliases (`$7000`–`$7FFF`).  
4. **Qualify asynchronous RAMs with PHI2** (or equivalent) so writes cannot land during bus turnaround.  
5. **The stack is hardware.** Subroutines, interrupts, and nested `PHA` all presuppose RAM in page `$01`.  
6. **Acknowledge interrupt sources explicitly**—level-sensitive `/IRQ` will otherwise loop forever.  
7. **Move bit-shifting off the CPU** when rates climb (UART, later timers for audio); keep bit-bang when the peripheral is slow or educational (SPI sensor, soft UART demo).  
8. **Hardware bugs are part of the curriculum.** The 65C51 TDRE erratum is fixed with a cycle-counted delay and honesty in the datasheet trail.  
9. **Layer a BIOS early** so monitors and high-level languages share one I/O contract.  
10. **Buffers absorb rate mismatch.** Keyboard and serial both converge on ISR producer / main-loop consumer rings.

---

## 17. What “hello world” actually meant

In part 1, hello world meant: *prove a microprocessor fetches instructions.*  
By part 9 it meant: *LCD text with busy-flag correctness at 1 MHz.*  
By part 26 it meant: *type `PRINT "HELLO"` in Microsoft BASIC on a machine whose every gate you can point to.*

Ben’s approach is not a race to a finished product. It is a deliberate sequence of **dependencies made visible**—reset vectors before ROM contents, ROM before I/O, I/O before subroutines, RAM before subroutines that work, timing before speed, interrupts before keyboards, UART before classic software, IRQ buffers before comfortable typing, timers before sound. Each video answers one “why didn’t this work?” with a concrete schematic change or a few dozen lines of assembly—and then asks the next question.

---

*Synthesized from series captions in this directory. Part 6 (RAM and bus timing) caption text was unavailable here; that section is reconstructed from parts 5 and 7 and the finished address decode. Videos 24, 25, and 27 captions in this archive were Spanish auto-translations; technical content was preserved.*

# Ben Eater 6502 Parts 01–10 — Technical Narrative Summary

Source material distilled from auto-generated YouTube captions in this directory (parts 01–05, 07–10) plus reconstruction of part 06 from adjacent videos and established address-decode/timing practice. Dense chronological account of *what* Ben builds and *how*.

---

## Part 01 — “Hello, world” from scratch: bringing up the W65C02

Ben starts with a bare **W65C02** (modern static CMOS 6502, datasheet ~30 pages) on a breadboard—not the NMOS original—so the clock can be stopped and single-stepped without losing register state. Power: **VDD pin 8** to +5 V, **VSS pin 21** to ground.

Input pins that must be defined for the CPU to run are tied high (or otherwise safely): **RDY (pin 2)** high so the CPU runs; **IRQB (pin 4)** and **NMIB (pin 6)** high so interrupts are not asserted; **BE (pin 36)** high so the address and data buses are enabled; **SOB (pin 38)** high per datasheet recommendation. Outputs (VPB, PHI1O, MLB, SYNC, etc.) are left open. The bidirectional data bus **D0–D7** and the **RWB (pin 34)** read/write output are initially unconnected; RWB high means the CPU is reading (data pins as inputs), low means writing (data pins as outputs). **NC** is left unconnected.

**Reset (pin 40)** is pulled high through a **1 kΩ** resistor and can be shorted to ground with a pushbutton. **PHI2 (pin 37)** is the system clock. A crystal oscillator (e.g. 10 MHz) could drive it—the W65C02 is rated up to ~14–17 MHz—but Ben uses his adjustable **555-based clock module** (astable/monostable/bistable) so he can slow, halt, and single-step. That choice is possible only because the W65C02 is fully static: “phi2 can be held in either the high or low state and it’ll preserve the contents of internal registers,” unlike the original 6502.

With only A0–A4 on LEDs the CPU “does something” but the pattern is opaque. A logic analyzer is overkill at these speeds; instead Ben builds an **Arduino Mega bus monitor**: 16 address lines to Mega pins (A15 on digital 22 … A0 on 52), later D7–D0 on odd pins 39–53, RWB on pin 3, PHI2 on pin 2 with a **rising-edge interrupt** so each sample is one clock. Serial at 57600 prints address (4 hex digits), data (2 hex), and R/W. Without anything driving the data bus, reads return garbage and behavior looks random.

He then ties each data line through **1 kΩ** to a fixed pattern **EA hex** (`11101010`)—chosen because **EA is NOP**. Soft pull-ups/pull-downs let the CPU still drive writes later. Behavior becomes deterministic: always reading, address counting. Stepping through reset shows the datasheet’s **seven-cycle reset sequence**, then reads of **$FFFC / $FFFD** (reset vector). With hardwired EA, those bytes yield start PC **$EAEA**. Next fetch at $EAEA is also EA → NOP (implied mode, **2 clocks**), so the CPU walks forever executing NOPs every two clocks. Quote of intent: he has a microprocessor “initializing and … trying to fetch and execute instructions,” but only via hardwired NOPs—next step is programmable ROM.

---

## Part 02 — ROM, address map, machine code, and the 65C22 VIA

He installs an **AT28C256 EEPROM** (256 Kibit = **32 KiB**), programmed offline (TL866 / MiniPro). The CPU has **16 address lines** (64 KiB space); the EEPROM has **A0–A14**. Mapping choice: enable ROM only in the **upper half** so **$FFFC/$FFFD** live in ROM. **A15** is inverted into the EEPROM’s active-low **/CE (pin 20)** using one gate of a **74HC00 NAND** with both inputs tied (as inverter)—“you’ll see later why I’m using the NAND gate.” **/OE (pin 22)** tied low; **/WE (pin 27)** tied high (read-only in-system). Resulting map:

| Region | Decoding | Role |
|--------|----------|------|
| `$8000`–`$FFFF` | A15=1 → /CE asserted | 32K ROM (CPU `$8000` = EEPROM offset 0) |
| `$0000`–`$7FFF` | A15=0 → ROM off | Free for RAM / I/O later |

ROM images are built in Python as 32768-byte files. Filling with EA and setting EEPROM offsets **$7FFC/$7FFD** to `$00 $80` (little-endian) places reset vector **$8000** at CPU `$FFFC/$FFFD`. First real program (hand opcodes): `A9 42` (LDA #$42), `8D 00 60` (STA $6000). Bus monitor shows the write of `$42` at `$6000` with RWB low—but nothing is mapped there yet (“yelling into the void”). Insight: the 6502 has **no separate I/O bus**; peripherals are memory-mapped devices that decode addresses and latch data for one cycle.

He adds a **W65C22 VIA**. Shared bus: D0–D7, PHI2, RWB, RESET (same button circuit). Chip selects: **CS1** active high, **CS2B** active low. Decode for “around `$6000`” uses only high bits **A15=0, A14=1, A13=1**—ignoring lower bits. Trade-off speech: wasting ~8K of address space (`$6000`–`$7FFF`) for the VIA saves gates; reusing the existing A15 NAND plus one more NAND (A15_inv NAND A14 → CS2B) and wiring A13→CS1 means “really … only adding a single NAND gate.” RS0–RS3 tied to **A0–A3**, so sixteen registers appear at `$6000`–`$600F`:

| Address | Register (typical use in series) |
|---------|----------------------------------|
| `$6000` | ORB / Port B data |
| `$6001` | ORA / Port A data |
| `$6002` | DDRB |
| `$6003` | DDRA |

Program sequence: LDA #$FF; STA $6002 (all Port B outputs); then alternate STA of `$55` / `$AA` to `$6000` with LEDs on PB0–PB7; JMP `$8005` loop. Confirmed on LEDs and by single-stepping with the Mega.

---

## Part 03 — Assembly language vs machine code (vasm)

Hand-hex is abandoned for **vasm** (6502, oldstyle/“hold 8-bit” syntax, `-Fbin -dotdir`). Critical assembler conventions: **leading whitespace** before instructions (else treated as labels); **`$`** for hex; **`#`** for immediate—without `#`, `lda $ff` becomes zero-page opcode `A5` not `A9`. Directives: `.org $8000` so assembled addresses match CPU view of ROM; `.org $fffc` / `.word reset` for the vector; padding to exactly 32768 bytes. Labels (`loop:`, `reset:`) replace fragile absolute JMP targets. Demo evolves to ROR of a `$50` pattern on Port B—carry participates as a ninth bit in the rotate.

---

## Part 04 — HD44780 LCD on the VIA

LEDs replaced by a **16×2 HD44780-compatible LCD**. Pins: VSS/GND, VDD/+5, **V0** contrast via **10 kΩ** pot to ground, backlight A/K (module has its own series resistor). **D0–D7 → Port B**; **E, R/W, RS → Port A** top three bits (symbols: E = bit7, RW = bit6, RS = bit5). 8-bit mode chosen for simplicity (4-bit left as exercise).

Initialization from datasheet example: function set (`00111000` → 8-bit, 2-line, 5×8); display on/cursor on/blink off; entry mode increment, no display shift. Protocol: put byte on Port B; clear control; pulse E high then low. For data, keep **RS=1** while pulsing E. First “Hello, world” is **copy-pasted blocks** (~177 lines asm → ~333 bytes)—works, but Ben is “not particularly proud”; next videos add hardware so software can share subroutines.

Symbols clarified: `PORTB=$6000`, `PORTA=$6001`, `DDRB=$6002`, `DDRA=$6003`; DDRA only top three bits set as outputs.

---

## Part 05 — Stack, JSR/RTS, and why RAM is mandatory

Subroutines `lcd_instruction` / `print_char` with **JSR / RTS** shrink the program and clarify intent, but the machine fails after programming. Arduino single-step reveals: after opcode `20` (JSR), the CPU briefly writes at **`$0124` / `$0123`** (high then low byte of return address), then jumps to the subroutine; on **RTS (`60`)**, it tries to read those locations back—and gets garbage (`$8D`), jumping to `$8D8D`.

Why `$01xx`: the 6502 **hardware stack** is fixed in **page `$0100`–`$01FF`**, indexed by the 8-bit **S** register. JSR pushes the return address (address of last byte of the JSR instruction; RTS returns to address+1) and decrements S; nested calls and PHA/PLA for saving A are possible if push/pull order is balanced. Stack overflow wraps S and silently corrupts older frames—“very difficult to troubleshoot.” S powers up arbitrary (here `$24`); Ben recommends **`LDX #$FF` / `TXS`** at startup so the stack grows down from `$01FF`.

Root cause: **no RAM** exists at `$0100`–`$01FF`, so pushes are void and pulls are bus noise. Next video must add RAM covering that page (and more).

---

## Part 06 — RAM and bus timing *(transcript missing; reconstructed)*

**Note:** Caption body unavailable; content inferred from part 05’s promise, part 07’s “last video” recap, and the completed decode in part 07.

Ben wires a **32K SRAM** (kit part: typically **HM62256**-class): A0–A14 to the address bus, D0–D7 to the data bus, **/WE** to CPU **RWB**. Intended region: **`$0000`–`$3FFF`** (A15=0 and A14=0)—includes zero page and the hardware stack.

Naive decode (A15/A14 straight to /CS and /OE) fails timing analysis. Address and R/W are not guaranteed stable for the whole cycle; if /CS (or write strobe) is asserted while addresses are still changing, **spurious writes** corrupt RAM. The 6502 synchronous bus guarantees a valid access window while **PHI2 is high**. Solution: qualify chip select with the clock.

Final glue (completed in part 07, designed in part 06):

- **A14 → RAM /OE** (active-low): outputs only when A14 is low (within `$0000`–`$3FFF` when combined with CS).
- **A15** already inverted by the existing NAND (ROM /CE path).
- That inverted A15 and **PHI2** feed a second NAND whose output drives **RAM /CS**: /CS is low only when A15 is low *and* PHI2 is high—i.e. address decode valid during the active clock phase.
- Unused NAND inputs tied high to avoid float/noise.

Address map after this step:

| Range | Device |
|-------|--------|
| `$0000`–`$3FFF` | RAM (16K of the 32K chip used; stack at `$0100`–`$01FF`) |
| `$4000`–`$5FFF` | Unused / future |
| `$6000`–`$7FFF` | VIA (coarse decode) |
| `$8000`–`$FFFF` | EEPROM |

---

## Part 07 — Subroutine calls with working RAM; stack on the bus monitor

He finishes the PHI2-qualified NAND wiring; with the same ROM (JSR/RTS hello world) the LCD works. Single-stepping with S initialized to `$FF` shows JSR pushing return address to **`$01FF`/`$01FE`**, then RTS pulling `$8011` correctly—where before the pull failed. Bus-monitor caveat: some JSR/RTS cycles put addresses on the bus that are **internal dead cycles**, not real memory ops; coincidence of leftover `$80` at `$01FF` briefly confused the reading.

Software polish: add LCD **clear display** (`00000001`) via another JSR before printing. Teases replacing the 555 clock with a **1 MHz crystal oscillator** so real timing constraints matter.

---

## Part 08 — Breadboard physics and the 1 MHz clock

Pedagogy: breadboards force pin-level understanding; cheap boards have weak spring contacts. Parasitic **capacitance** (parallel conductors) and **inductance** (changing current → opposing voltage) degrade edges at high frequency. Decoupling: **0.1 µF** across power rails (ideally one per chip). Frequency-response experiment: sine through messy wiring stays clean near 1 MHz but phase-shifts and attenuates toward 20 MHz.

Square clocks are Fourier sums of odd harmonics; steep edges need tens of MHz of content. W65C02 datasheet **rise/fall ≤ 5 ns** is hard on breadboards; the 555 module was out of spec but worked slowly. A **1 MHz canned oscillator** (power, ground, output; short clock runs to CPU and VIA) measures ~2.5–3 ns rise at the can and still acceptable at the CPU pin if wiring is short.

After switching clocks, hello world **breaks**: LCD initializes (function set / two-line mode visible) but no message. Datasheet had warned: check the **busy flag** before the next command; at ~Hz clocks it was irrelevant, at 1 MHz the CPU outruns the controller. Fix deferred to software in part 09.

---

## Part 09 — Busy-flag wait loops and indexed string print

NOP-padding to delay between LCD ops needs absurd counts (~**750 NOPs** ≈ 1.5 ms)—matching **clear display**’s long internal time when busy isn’t polled. Proper fix: subroutine **`lcd_wait`**:

1. `PHA` (preserve A—caller’s instruction/data byte).
2. Set **DDRB = $00** (Port B inputs) to read LCD data.
3. Port A: RS=0, R/W=1; pulse E; `LDA PORTB`.
4. `AND #%10000000` to isolate busy; **`BNE`** loop while busy (zero flag clear when busy bit set).
5. Drop E; restore **DDRB = $FF**; `PLA`; `RTS`.

Called from `lcd_instruction` and `print_char` before each transfer. Scope on E shows clear-display as a long busy-poll burst, then character strobes—faster and correct vs fixed 1.5 ms gaps.

Message printing: `.asciiz "Hello, world!"` in ROM; **`LDX #0` / `LDA message,X` / `BEQ done` / `JSR print_char` / `INX` / `JMP print`**. LCD DDRAM is 40 chars/line internally; padding past 40 places text on line 2. Ben declares hello world “done.”

---

## Part 10 — Binary to decimal without a divide instruction

Goal: display a 16-bit value (example **1729**) as ASCII digits. CPU has add/subtract/shift, not divide. Repeated divide-by-10 via remainder extraction is done as a **16-iteration rotate-left / trial-subtract-10** algorithm on a 32-bit workspace (value || mod10) plus carry:

- Allocate RAM: `value` at `$0200` (2 bytes), `mod10` at `$0202` (2 bytes).
- Copy ROM `.word 1729` into `value`; clear `mod10` and carry.
- Loop X=16: ROL through all four bytes; SEC; SBC #10 from low mod10 into Y; SBC #0 from high; if **BCC**, ignore result (couldn’t subtract); else store A/Y back to mod10 (successful “digit 1” in quotient path). Carry-outs during successful subtracts rotate into the quotient side.
- After 16 steps, low byte of mod10 is remainder 0–9; one more ROL brings final quotient bit into `value`; print/store digit as `ADC #'0'` (CLC first).
- Clear mod10; if `value` OR’d halves ≠ 0, repeat for next digit.

Digits emerge **least-significant first** (`9271` instead of `1729`). Fix: **`push_char`** builds a null-terminated string in RAM (`message` at `$0204`, up to 6 bytes) by inserting each new digit at the front (shift existing chars right via stack/Y index). Finally reuse the indexed print loop from part 09. ~164 lines of assembly for “how hard could binary to decimal be?”

---

## Cross-cutting toolkit and address map (end of part 10)

**Chips:** W65C02; AT28C256 EEPROM; HM62256-class 32K RAM; W65C22 VIA; 74HC00 (4× NAND) for ROM /CE invert, VIA CS2B decode, and PHI2-qualified RAM /CS; HD44780 LCD; 555 clock then 1 MHz oscillator; Arduino Mega as cycle-accurate bus logger.

**Final coarse map:**

```
$0000–$3FFF  RAM (stack $0100–$01FF; program vars e.g. $0200+)
$6000–$7FFF  VIA (ORB/ORA/DDRB/DDRA at $6000–$6003; RS = A0–A3)
$8000–$FFFF  EEPROM (reset vector $FFFC/$FFFD → $8000)
```

**Software arc:** hardwired NOP → Python ROM images → vasm with `.org`/labels → memory-mapped LED/VIA I/O → LCD init/data protocol → JSR/RTS needing RAM stack → PHI2-qualified RAM decode → 1 MHz clock exposing LCD busy timing → flag-polled wait loops and indexed strings → shift/subtract decimal conversion into a RAM string.

**Debugging method:** slow/static clock + Mega interrupt-on-PHI2 dump of address/data/RWB is the primary tool through the stack and RAM bring-up; later, oscilloscope on LCD E validates busy-wait vs NOP delay.

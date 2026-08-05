# Ben Eater 6502 — Technical Summary (Videos 11–20)

Dense chronological notes from YouTube auto-captions. Addresses, pins, and circuit details are as Ben describes them on the breadboard 65C02 system (VIA mapped at `$6000`–`$600F`, ~1 MHz Φ2).

---

## 11 — Hardware interrupts

**What:** Demonstrates 6502 IRQ and NMI with a button, a 16-bit interrupt counter in RAM, and continuous LCD reprint of that counter.

**How — vectors and pins**

- Interrupt entry mirrors reset: dedicated vectors in ROM at the top of address space.
  - NMI vector: `$FFFA`/`$FFFB`
  - Reset vector: `$FFFC`/`$FFFD`
  - IRQ/BRK vector: `$FFFE`/`$FFFF`
- Hardware pins (active-low, bar notation):
  - Pin 4 = `/IRQ` (interrupt request)
  - Pin 6 = `/NMI` (non-maskable interrupt)
- Both normally tied high; interrupt by pulling low.
- Handler ends with `RTI` (return from interrupt). On IRQ entry the CPU pushes PC and processor status, then **sets the I (interrupt disable) flag**; `RTI` restores prior state.

**Demo circuit**

- Button on IRQ: pin 4 pulled up through ~1 kΩ to +5 V; switch to ground asserts IRQ.
- Counter at `$020A`/`$020B` (after prior video’s value buffer ending near `$020A`). IRQ handler increments low byte, then high byte on rollover.
- Main loop homes LCD cursor (not full clear), loads counter into the binary→decimal path, reprints forever. Counter initialized to 0 at startup.

**IRQ vs NMI behavior**

- **IRQ is level-sensitive.** While `/IRQ` stays low, after each `RTI` the CPU re-enters the handler if I is clear. A held button at 1 MHz produces thousands of increments per press. Datasheet: hold IRQ low until the **handler clears the interrupt source**.
- IRQ can be masked: I bit in status; enable with `CLI`, disable with `SEI`. Without `CLI`, button IRQ does nothing.
- **NMI is edge-sensitive** (negative transition). One falling edge → one entry (unless another edge arrives while servicing). Holding NMI low does not retrigger. Button bounce can still produce multiple edges.
- Why prefer IRQ for peripherals: multiple devices can wire-OR `/IRQ` and hold it until acknowledged; CPU can briefly `SEI` around critical sections (e.g. reading both bytes of a shared 16-bit counter without tearing). NMI cannot be masked—use for highest priority events (e.g. impending power loss with residual capacitance). Timing-sensitive code is unsafe under NMI.
- Direct button→IRQ is the wrong model; the 6522 VIA can latch edges and negotiate acknowledge with the CPU (next video).

---

## 12 — Interrupt handling (via 6522 VIA)

**What:** Routes the button interrupt through the 6522 so one edge produces one serviced IRQ that software can clear.

**VIA map (unchanged decode)**

| Reg | Addr   | Role |
|-----|--------|------|
| ORB/IRB | `$6000` | Port B |
| ORA/IRA | `$6001` | Port A |
| DDRB | `$6002` | DDR B |
| DDRA | `$6003` | DDR A |
| … | `$6004`–`$600B` | timers / shift / ACR / PCR (used later) |
| IFR | `$600D` | Interrupt Flag Register |
| IER | `$600E` | Interrupt Enable Register |
| PCR | `$600C` | Peripheral Control Register |

**Wiring**

- VIA pin 21 (`/IRQ`) → 6502 pin 4 (`/IRQ`).
- Button (pull-up to +5 V, switch to GND) → VIA **CA1**.

**Configuration**

- IER write `$82`: bit 7 = set/clear sense (**1 = set/enable**), bit 1 = CA1 enable. (Clearing uses bit 7 = 0 with target bits = 1.)
- PCR write `$00`: CA1 control bit 0 = **0 → negative active edge** (press = high→low). CA2/CB2 have richer modes (handshake, output); CA1/CB1 are edge-only.
- IFR bits include T1/T2, SR, CB1/CB2, CA1/CA2, and bit 7 = any enabled IRQ pending. Useful when polling multiple VIAs: `BIT IFR` copies bit 7 into N.

**Clearing CA1**

- CA1 flag clears by **reading or writing Port A** (ORA/IRA). Design intent: many lines ORed into CA1 while Port A holds per-line state; read Port A both identifies source and ACKs.
- Handler: increment counter, then clear IRQ before `RTI`. Prefer `BIT $6001` over `LDA $6001` so A is preserved (flags are already stacked/restored around IRQ).

**Software debounce (demo)**

- Nested X/Y countdown loops (~255×255) before clearing Port A so bounce settles while IRQ remains asserted. Must save/restore A,X,Y via stack (`PHA` / `TXA`/`PHA` / `TYA`/`PHA`, reverse on exit). Laggy; hardware debounce preferred.

**Multi-source note**

- With only CA1 enabled, IFR need not be decoded. With timers/shift/CA2/etc., or multiple VIAs wired to one `/IRQ`, read IFR (and per-chip bit 7) to dispatch.

---

## 13 — PS/2 keyboard protocol (theory + shift-register probe)

**What:** Explains PS/2 electrical/protocol behavior; builds cascaded 74HC595 shift registers + LEDs to visualize scan-code packets.

**Connector / wiring (Ben’s cable colors)**

- Six-pin mini-DIN; four used: +5 V, GND, Clock, Data (plus shield→GND).
- His breakout: orange = GND (+ shield), black = +5 V, brown = Clock, red = Data. (Colors are cable-specific—verify with continuity.)

**Signaling**

- Open-collector-style clock/data; idle high. Keyboard clocks bits on **falling** clock edges (~11 pulses per packet).
- Packet (11 bits): **start (0)**, **8 data LSB-first**, **odd parity**, **stop (1)**. Sanity: start=0, stop=1, odd parity over data+parity.

**Scan codes (Set 2 style as shown)**

- Make: key code (e.g. A = `$1C`, Space = `$29`, numpad 7/Home related `$6C`).
- Break: `$F0` then key code.
- Extended: `$E0` prefix (e.g. Home make `$E0 $6C`, break `$E0 $F0 $6C`).
- Hold → typematic repeat of make code.
- Shift/Caps/Num Lock are just keys; host tracks modifiers and LED state (host→keyboard path exists for LEDs; not implemented here).
- Oddities: Pause = long make, no break; Print Screen = multi-byte make/break.

**Shift-register visualization**

- 74HC595: serial data → pin 14 (DS); QA–QH outputs; `/OE` low; `/SRCLR` high; QH' (pin 9) cascades to next DS.
- Keyboard clock is falling-edge; 595 shifts on **rising** edge → invert clock with 74HC04.
- Latch clock slightly delayed vs shift clock (two extra inverter delays) so data settles before latch—or latch on “frame done” edge in the real interface (video 14).
- Cascade enough 595s for 11/22/33… bits to show multi-byte sequences.

**Interface options sketched**

- Parallel dump of last 8 data bits into VIA inputs; interrupt per bit; interrupt per completed packet; or smarter MCU translating to ASCII.

---

## 14 — Keyboard interface hardware

**What:** Produces one VIA CA1 interrupt per completed 11-bit PS/2 packet; latches 8 data bits onto Port A for the ISR to read.

**Why not IRQ-per-clock**

- Clock period ~85 µs → interrupt every ~85 cycles at 1 MHz; too heavy, and framing is ambiguous without detecting gaps between packets.

**Frame-detect RC + Schmitt**

1. Invert keyboard clock (74HC04/14) → active-high pulses.
2. Diode + resistor + capacitor envelope:
   - Diode oriented so **charge is fast** (through diode), **discharge is slow** (through resistor, e.g. ~33 kΩ) into ~0.01 µF to GND.
   - During the 11-pulse burst the node stays high; after the burst it decays.
3. Feed envelope into another inverter → digital pulse: low during burst, **rising edge after last bit** = “byte ready.”
4. Plain 74HC04 chattered in the analog mid-band (VIH/VIL gap ~1.35–3.15 V). Replace with **74HC14 Schmitt-trigger** inverter (separate rising/falling thresholds, typ. ~2.7 V / ~1.8 V) for clean edges.
5. That rising edge → VIA CA1 (and later 595 latch clock).

**Shift register path**

- Separate inverter for clean rising shift clock into both 74HC595s (not the RC node).
- Keyboard data → first 595 DS; cascade 11 bits; **only 8 data bits** wired to VIA Port A (start/parity/stop ignored for now).
- Latch clock = same “frame complete” edge as CA1 → outputs stable when ISR runs.
- `/SRCLR` high, `/OE` low; unused gate inputs tied.

**Software/PCR change**

- PCR CA1 edge = **positive** (active edge when frame completes / line goes high).
- ISR: `LDA $6001` → store as displayed “counter”; reading Port A also clears CA1. Observed: Space → 41 decimal (`$29`); release path shows `$F0` (240) then key code.

---

## 15 — Keyboard interface software

**What:** Circular keyboard buffer, scan-code→ASCII maps (unshifted/shifted), release and shift-state machine in the ISR; main loop drains buffer to LCD.

**Buffer**

- Ring buffer `$0200`–`$02FF` (256 bytes).
- `write_ptr`, `read_ptr` (8-bit, wrap naturally). Empty when equal; producer = ISR, consumer = main.
- Main: briefly `SEI`/`CLI` around comparing pointers; if unequal, index with read_ptr, `print_char`, increment read_ptr.

**ISR pattern**

- Save X (and A as needed) on stack.
- `LDA $6001` (scan code + clear CA1).
- Map through ROM tables then `STA kb_buffer,X` with X = write_ptr; `INC write_ptr`.

**Keymap**

- 256-byte tables in ROM (e.g. keymap at `$FE00`, shifted at `$FD00`): index = scan code, value = ASCII or `'?'`.
- After loading scan code: `TAX` / `LDA keymap,X` (or shifted table).

**Release / shift state (`keyboard_flags` at `$0002`)**

- Bit “release”: set on seeing `$F0`; next code ignored as make (unless it is shift—see below), then clear release.
- Bits for left/right shift down: set on make of left (`$12`) / right shift; clear on break of those codes (while in release path, still inspect the following code).
- On normal make: if shift flag set, use `keymap_shifted` (A→`A`, `1`→`!`, etc.); else unshifted map. Push ASCII into buffer.
- Init write/read ptrs and flags to 0. Bug fixed live: release code is `$F0`, not `$0F`.

**Result:** typing prints characters; Shift yields capitals/symbols. Enter/Escape/etc. left as exercises.

---

## 16 — SPI (Serial Peripheral Interface)

**What:** SPI theory; bit-banged SPI on VIA Port A to a BME280-class temp/humidity/pressure sensor (5 V board with 3.3 V level shift); read chip ID and temperature with optional compensation.

**Bus**

- Four wires, controller-driven: **SCLK**, **MOSI** (master out / SDO on MCU side), **MISO** (master in), **CS** (active low). Naming: MOSI/MISO vs SDI/SDO (peripheral-relative)—connect out→in.
- Full duplex: every clock exchanges one bit each way; unused direction ignored.
- No single official standard: **CPOL/CPHA** (modes 0–3). Sensor example: modes 0 and 3 (sample on rising edge). Check datasheet.
- Multi-drop: share SCLK/MOSI/MISO; separate CS per device (or 74LS138 decode for many CS).

**Device protocol (register example)**

- First byte on MOSI: R/W bit + 7-bit register address (read=1, write=0).
- Then write payload or continue clocking to read. Multi-byte read auto-increments (handy for pressure/temp/humidity blocks).
- Chip ID register `$D0` always returns `$60` as smoke test.
- Humidity 16-bit; temperature/pressure 20-bit (+ padding); config/ctrl registers writable; calibration constants in ROM for float/fixed compensation.

**6502 implementation**

- Map CS, MOSI, SCLK as Port A outputs; MISO input (DDRA). Bit-bang: explicit store sequences for each clock edge, or a `transceive` loop: shift out MOSI bit, toggle clock, shift in MISO into a receive buffer, 8 times; returns received byte in A.
- Assert CS low for whole transaction; CS high when done. Controller owns timing—slow loops and gaps between bytes are fine.
- Demo: write config registers (`$75`, `$74` + params), then periodic read from `$FA` (temp MSB) with continued clocks for `$FB` (and later 20-bit path); `print_num` raw value; hand/ice cube sanity. Full °C needs calibration read + ported compensation math (~25 °C matching a thermocouple).

---

## 17 — Hardware timers (6522 Timer 1)

**What:** Replaces NOP delay loops with VIA Timer 1; one-shot then free-run IRQ tick counter; cooperative LED/LCD updates from a shared time base.

**Registers**

| Name | Addr | Notes |
|------|------|-------|
| T1C-L | `$6004` | Timer 1 counter low (write also loads latch low) |
| T1C-H | `$6005` | Timer 1 counter high; **write starts countdown** |
| T1L-L / T1L-H | `$6006`/`$6007` | Latches (reload value in free-run) |
| T2C-L / T2C-H | `$6008`/`$6009` | Timer 2 |
| ACR | `$600B` | Aux control; bits 7–6 = T1 mode |
| IFR | `$600D` | bit 6 = T1 timeout |
| IER | `$600E` | enable T1 IRQ |

**ACR T1 modes (bits 7–6)**

- `00` — **one-shot**: count down once; set IFR.T1 at zero.
- `01` — **free-run**: at zero, set IFR.T1 and reload from latches (interval timer). Continuous interrupts every **N+2** Φ2 cycles (use N = desired_period − 2).

**One-shot delay recipe**

1. ACR = `$00`.
2. Write low count to T1C-L, high to T1C-H (starts). Example 50 ms @ 1 MHz: `$C350` → low `$50`, high `$C3` (max ~65535 µs ≈ 65.5 ms).
3. Poll: `BIT IFR` / `BVC` loop until overflow flag set (bit 6 → V).
4. Clear: read T1C-L.

**Free-run system tick**

- Init: ACR T1 = `01`; load interval (e.g. 10 ms → N = 9998 = `$270E` → low `$0E`, high `$27`); IER = enable T1 (set bit + T1 bit, e.g. bits for “set” and timer1); `CLI`.
- IRQ: `BIT T1C-L` to ACK; increment 32-bit `ticks` at `$0000`–`$0003` (10 ms ticks → ~500 days range).
- Main: compare `ticks` to per-task timestamps (`toggle_time`, `lcd_time`); e.g. XOR Port A bit0 every 25 ticks (250 ms LED), print low 16 bits of ticks every 100 ticks (1 s). `SEI`/`CLI` when reading multi-byte `ticks`. Refactor to `update_led` / `update_lcd` called from a polled main loop—CPU free between ticks.

**Contrast with software delay**

- Nested X/Y NOP loops burn 100% CPU, depend on exact cycle counts and clock rate; hardware timer is precise and allows concurrent work (especially with IRQ ticks).

---

## 18 — RS-232 protocol + soft UART receive

**What:** Explains TIA-232 / RS-232 framing and voltage levels; level-shifts RX with a BJT; bit-bangs 9600 8N1 receive on VIA Port A bit 6 into LCD characters.

**Protocol / connector**

- Historical DB-25 (TIA-232); common DE-9 as TIA-574. DTE vs DCE defines pin direction; names from DTE view.
- Ben: USB–serial adapter = DTE; breadboard = DCE. **DE-9 pin 3 = TD** (DTE transmit → into breadboard RX), pin 5 = GND. (Pin 2 = RD toward DTE.)
- Idle = **mark** = negative voltage (binary 1); **space** = positive (binary 0). Spec: mark &lt; −3 V, space &gt; +3 V; ±3 V transition band undefined; magnitude ≤ 25 V. Measured idle ~−6 to −7 V.
- Asynchronous: **no clock wire**. Both ends agree baud. 9600 → ~104.16 µs/bit.
- Frame: **start bit** (space/0) resyncs receiver; then data (often 8, LSB first); optional parity; ≥1 **stop** (mark/1). Example 8N1 = 10 bit times/char → 960 chars/s at 9600.
- Captured capital `B` = `$42` on the wire.

**5 V RX level shift (NPN)**

- RS-232 TD → 10 kΩ → base; emitter GND; collector = logic out pulled up 10 kΩ to +5 V.
- Negative RS-232 → transistor off → out = 5 V (idle/mark as logic high).
- Positive RS-232 → transistor on → out = 0 V (space as logic low).
- Into **Port A bit 6** so `BIT $6001` copies PA6 → **V** (overflow); `BVS`/`BVC` poll without destroying A’s data path awkwardly.

**Soft-UART RX algorithm @ 1 MHz / 9600**

1. Loop `BIT PA` / `BVS wait` until start (line goes low / V clear).
2. **Half-bit delay**, then for each of 8 bits: **full-bit delay**, sample mid-bit, map V → C (`BVS`→`SEC` else `CLC`), `ROR A` (LSB-first rebuild), balance path lengths with NOPs so 0/1 branches match cycles.
3. Optional stop-bit delay; `print_char`; repeat.
4. Cycle budget: ~39–40 cycles fixed + 5×loop_count ≈ 104 → **loop_count = 13** in bit-delay (push/pull X on 65C02). Half-bit delay ≈ half that.

**Limits:** RX only; CPU blocked during character; timing brittle across baud rates.

---

## 19 — Voltage multiplier (charge pump)

**What:** Discrete charge-pump voltage doubler/tripler from a 0–Vswing clock (555), motivating RS-232 TX levels from a single supply.

**Core idea**

- Charge capacitor to Vsupply; switch in series with Vsupply → ~2×V; hold with a second capacitor so output doesn’t collapse while the flying cap recharges.
- Manual DPDT demo → “charge pump.” Faster switching → smoother DC.

**Diode–capacitor doubler from 0/V clock**

- Clock low: flying cap charges toward V through diode.
- Clock high: flying cap stacks on clock’s V → node ~2V; series diode fills reservoir to GND; diode blocks back-discharge when clock returns low.
- Real diode drops and non-ideal clocks → ~15 V from ~9 V battery, not perfect 18 V; AC ripple on reservoir small if lightly loaded.

**Extra stages**

- Need complementary 0/V clocks (555 + MOSFET inverter). Alternate clocks into successive flying caps → ~3× (then 4×…) with diode–reservoir at the end.
- Many stages → high open-circuit voltage (demo ~110 V) but **tiny energy**; skin load collapses voltage—useless as a “taser,” fine for **signaling**.
- Motivation: RS-232 wants roughly ±10–15 V marks/spaces from a 5 V-only digital system.

---

## 20 — 6502 serial interface start (MAX232 + soft TX)

**What:** Replaces discrete RX FET with **MAX232**; adds TX path; bit-bangs full duplex-capable pins but software still half-duplex character at a time; tees up 6551 UART.

**MAX232**

- Dual driver/receiver; on-chip oscillator + diode network; **external 1 µF charge-pump caps** per datasheet:
  - C1 between pins 1–3
  - C2 between pins 4–5
  - V+ reservoir pin 2–GND
  - V− reservoir pin 6–GND
  - VCC pin 16, GND pin 15 (single +5 V)
- Typical drive ~±7 V (min about ±5 V)—conservative vs ±3 V thresholds (Postel: be conservative in what you send, liberal in what you accept). Bad “TTL RS-232” gadgets abuse liberal receivers with 0/5 V.
- RX: R1IN (pin 13) ← RS-232 from DTE TD; R1OUT (pin 12) → VIA (logic).
- TX: VIA → T1IN (pin 11); T1OUT → RS-232 **pin 2** (DCE transmit / DTE receive). Second channel unused.

**Logic polarity**

- Idle: VIA TX bit **high** (5 V) → MAX232 outputs **negative** mark.
- Start/space: VIA bit **low** → MAX232 **positive** voltage.

**Soft TX (65C02)**

- Character in RAM (e.g. `$0200`). Port A bit 0 = TX (example).
- Use `TSB` / `TRB` with A = `$01` to set/clear TX without clobbering other Port A bits (LCD, etc.).
- Sequence: idle high; `TRB` start; for 8 bits: delay, `ROR` memory into C, `BCS`→`TSB` else `TRB`; delay; `TSB` stop; delay. Reuse ~13-iteration bit delay from RX (~104 µs).
- Demo: on reset send `*`; still receive typed characters to LCD. Scope: ±~7 V on line, 5 V logic on VIA side.

**Limits → next step**

- CPU-bound; hard to change baud; cannot truly full-duplex in software. Next: hardware **UART** (6551/65C51) for independent TX/RX shift engines.

---

## Cross-cutting address / pin cheat sheet

| Item | Value |
|------|--------|
| VIA base | `$6000` |
| Port B / A | `$6000` / `$6001` |
| DDR B / A | `$6002` / `$6003` |
| T1C-L/H | `$6004` / `$6005` |
| ACR / PCR | `$600B` / `$600C` |
| IFR / IER | `$600D` / `$600E` |
| 6502 `/IRQ` / `/NMI` | pins 4 / 6 |
| VIA `/IRQ` | pin 21 → CPU `/IRQ` |
| Vectors | NMI `$FFFA`, RES `$FFFC`, IRQ `$FFFE` |
| KB buffer | `$0200`–`$02FF` |
| Clock (series) | ~1 MHz → 1 cycle ≈ 1 µs |

## Chronological arc

1. Raw IRQ/NMI semantics and why peripherals need latching ACK (11).
2. VIA CA1 edge + IER/IFR/PCR + Port A clear (12).
3. PS/2 11-bit frames and scan-code language (13).
4. RC+Schmitt frame detect, 595 latch, CA1 per keycode (14).
5. ISR state machine → ASCII ring buffer (15).
6. SPI bit-bang sensor bus (16).
7. T1 one-shot / free-run system ticks (17).
8. RS-232 async framing + soft RX (18).
9. Charge-pump intuition for ±line voltages (19).
10. MAX232 + soft TX/RX; UART as the escape hatch (20).

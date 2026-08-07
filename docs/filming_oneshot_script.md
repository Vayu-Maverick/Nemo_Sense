# NEMO_SENSE: ONE SHOT
### Film Direction Script — Revised for Real Conditions
**Runtime Target:** 7–10 minutes  
**Equipment:** GoPro (Hero 10/11/12) + Boya Mic Mini  
**Style:** Multi-shot, edited to feel like a continuous world (1917-inspired pacing, NOT a literal single take)  
**Shoot Time:** 9:30 AM  
**Weather:** Cloudy — excellent diffused light, zero harsh shadows. Do not reschedule for sun.  
**Location:** Sanskardham Campus  

---

> **DIRECTOR'S NOTE — Read this first:**
> 
> This film is not about a finished product. It is about the people building
> something that matters, and the intelligence behind it. 
>
> **Filming strategy:** The AI pipeline and dashboard run live on the PC. 
> The chassis is a physical proof of concept — we film it as a component, 
> not a finished autonomous robot. The screens, the code, the logic — THAT 
> is what we show running. Nobody expects a student project to be shipping 
> firmware. They expect to see that you understand the problem and solved 
> it in software. So that's what we show.
>
> **GoPro note:** Wide angle is your friend, not your enemy. Get low. Get close.
> The GoPro's native wide lens makes small things look significant — use that.
> Boya Mic Mini clips on the shirt collar. Record a 30-second test before every
> monologue section and play it back in earphones to check levels.

---

## GOPRO SETTINGS — Lock these in before you start

| Setting | Value | Why |
|---|---|---|
| Mode | Video 4K/30fps or 2.7K/60fps | 60fps gives smoother motion when slowed in edit |
| HyperSmooth | ON (Boost mode) | Kills all handheld shake |
| Protune | ON | More colour data for grading |
| ISO | 100–400 (cloudy = plenty of light, keep it clean) |
| Colour | Flat / Log | Gives you more in post |
| Sharpness | Low | Looks more cinematic, less "action cam" |
| White Balance | Cloudy preset, NOT Auto | Prevents colour shifting between shots |
| Audio | Disable GoPro internal mic — rely entirely on Boya |
| Boya Mic | Clip to shirt collar, cable hidden under clothing, gain at 75% |

> **Sync tip:** At the start of every new clip, clap once loudly on camera.
> This gives you a sync point when matching Boya audio to GoPro video in the edit.

---

## SHOT BREAKDOWN

---

### SECTION A — `00:00 to 01:15` | THE B-ROLL OPENING (1917 STYLE)

**This is your most important section. It sets the entire tone.**

The 1917 opening works because it is quiet. Two soldiers asleep in a field of tall grass — the world doesn't know what's coming yet. You need that same feeling.

**Do NOT start with the bot. Do NOT start with code. Start with the campus.**

---

**SHOT A1 — Wide establishing. Camera low, tilted up slightly.**

Shoot the Sanskardham campus path early in the morning quiet. Cloudy sky above, footpath ahead. 

GoPro placed on the ground (use the flat adhesive mount) pointing slightly upward. Nobody in frame for 5 full seconds. Just the path, trees, sky.

*This is your 1917 grass field. Empty world. Before anything begins.*

---

**SHOT A2 — Close ground-level: shoes on concrete.**

GoPro pointed down and forward, held at ankle height. We see a pair of shoes walking — slow, deliberate pace. Shot lasts 8 seconds.

*We follow someone but don't know who yet.*

---

**SHOT A3 — A corner of the campus — a person with a cane navigating a step.**

Filmed from a distance, slightly telephoto if you have an attachment, otherwise medium wide. This person does not need to be visually impaired — they just need to be someone navigating the physical world with something in their hand.

Hold for 6 seconds. They move through frame and exit. Camera stays on the empty space they just left.

*The problem — shown wordlessly.*

---

**SHOT A4 — Slow reveal of the NEMO chassis.**

GoPro on ground level. The chassis is placed on a flat surface — workbench, bench outside, campus step. Camera starts tight on the wheel, then slowly tilts up to show the whole chassis.

The chassis should be clean. Wired neatly. If there are exposed components, that's fine — it looks technical, not broken.

**Hold for 5 seconds. No movement. No voice. Just the object.**

*This is your match cut from the empty path to the thing being built for it.*

---

**SHOT A5 — The PC screen. The AI running.**

GoPro pointing at laptop screen running `nemo_demo.py --sim`. We see the dashboard — bounding boxes, zone bars, the ARDUINO UNO Q branding. The simulation is live and moving.

Camera slowly drifts in closer toward the screen.

*The brain. Before the body.*

---

### SECTION B — `01:15 to 03:15` | CREATOR 1 — THE LOGIC

**[LOCATION: Outdoor bench or campus wall — seated or standing]**

Creator 1 is sitting with the laptop open showing the running demo. Boya Mic on. The GoPro is handheld, held close — about 60cm from their face, slightly below eye level (slightly looking up at them). 

Cloudy light = their face is perfectly lit from above with no harsh shadows. Use this.

**They do NOT look at the camera.** They look at the laptop, at the bot chassis, at the middle distance. They are thinking out loud.

---

**CREATOR 1 MONOLOGUE — "The Problem We Actually Solved"**

> *(looking at the screen — casual, like explaining to a friend)*
>
> "The navigation systems that exist for visually impaired people work.
> But they're expensive. They require maintenance contracts.
> They require the person using them to have access to the right service center.
>
> What we built is designed around a different assumption:
> that the person using this might not be in a city with a service center.
> That they might need to open it up and fix it themselves.
> Or hand it to someone nearby who can.
>
> *(taps the chassis)*
>
> Off-the-shelf parts. Open source model. Everything documented.
> That's the design decision underneath every other design decision."

---

**SHOT B-INSERT: Screen close-up while Creator 1 talks (cutaway)**

GoPro pointed at the laptop screen showing zone detection live. Can be filmed separately and cut in during the monologue in edit. This gives the editor a tool to breathe the speech — show the screen for 3 seconds, cut back to face, let them continue.

---

**CREATOR 1 continues:**

> "The AI side — we're running YOLOv5n. Nano. Deliberately small.
> Not because we couldn't use a bigger model. Because on the target hardware,
> smaller means faster, and faster means safer.
>
> *(points at the three zones on screen)*
>
> Left, center, right. Three zones. The model decides which is clear.
> The motor controller gets one of four commands: forward, stop, steer left, steer right.
> That's the whole navigation logic.
>
> Simple is not a weakness here. Simple is the point."

---

### SECTION C — `03:15 to 04:45` | THE BUILD — B-ROLL MONTAGE

**[NO DIALOGUE — let the ambient campus audio breathe here]**

This section is pure visual. No talking. Let the images do the work. Cloud-diffused light at Sanskardham will make everything look considered and clean.

Shoot all of these and choose the best 4–5 in the edit:

---

**SHOT C1 — Hands and the PCB / wiring.**
GoPro extreme close-up on hands adjusting wires on the board. 8 seconds.

**SHOT C2 — The screen from the creator's POV.**
GoPro held at creator's eye level looking at the screen. We see them reflected faintly in the screen. 6 seconds.

**SHOT C3 — Arduino UNO Q board — static close-up.**
Just the board on a table. The camera doesn't move. Let the components speak.

**SHOT C4 — The chassis from the front, camera low.**
GoPro on ground. Camera looking up at the front of the chassis as if the chassis is much larger than it is. The wide lens exaggerates the scale. This is the shot that makes a POC look significant.

**SHOT C5 — Creator 2 typing, mid-focus on hands.**
Slightly out of focus on the face, sharp on the keyboard. Terminal output scrolling.

**SHOT C6 — Wide campus shot. Creators in background. Chassis in foreground.**
GoPro on a flat surface, chassis in the near foreground (blurry), creators at a bench in the background. Establishes the relationship between the object and the people.

---

### SECTION D — `04:45 to 06:30` | CREATOR 2 — THE ENGINEERING

**[LOCATION: Different spot on campus — near a wall, or standing]**

Creator 2 now. Same approach — Boya Mic, GoPro close and slightly low, no eye contact with camera.

Creator 2 is holding a component — the Arduino board, or a battery — while they talk. Their hands are always doing something. This is important.

---

**CREATOR 2 MONOLOGUE — "Why the Hardware Works the Way It Does"**

> *(examining the board in their hands)*
>
> "People ask why three batteries. It sounds like overkill.
>
> *(looks up — not at camera, at the middle distance)*
>
> BAT-1 and BAT-2 are identical. Same cells, same capacity.
> When BAT-1 runs down, BAT-2 cuts in instantly — the switchover is a Schottky diode,
> it happens in microseconds. The user doesn't feel it. The system doesn't hiccup.
>
> BAT-3 is completely isolated. It only powers the compute — the AI, the decision logic.
> Even if both motor batteries fail completely,
> the brain is still alive, still processing, still sending alerts.
>
> *(sets the board down)*
>
> That's not a feature. That's a safety requirement.
> When the person using this is navigating a road,
> the system has to be more reliable than the road."

---

**CREATOR 2 continues:**

> "We spent a long time on the safety testing.
> Before anything went near a real environment,
> we ran the system through 200 hours of simulation and hardware testing.
>
> Because you can't build something for someone who trusts it with their safety
> and cut corners on the testing. That's not a tradeoff that exists.
>
> *(small pause)*
>
> So we didn't."

---

**SHOT D-INSERT: Battery setup close-up (cutaway)**
GoPro on the three-battery layout. Can be labelled BAT-1, BAT-2, BAT-3 with simple tape labels for clarity on camera. Filmed separately, cut in during edit at the battery explanation.

---

### SECTION E — `06:30 to 07:45` | BOTH CREATORS — THE WHY

**[LOCATION: Side by side — campus path or bench. Cloudy sky behind them.]**

This is the only section where both creators are in frame together. It is not a formal interview pose. They are side by side, slightly turned toward each other, talking naturally. The GoPro is wide enough to hold both in frame from a metre away.

This section should feel like a conversation that just happens to be on camera.

---

**CREATOR 1:**
> "What we want people to take away from this —
> it's not the specific technology choices.
> It's the idea that this kind of system can be built from accessible parts.
>
> The AI model is open source. The hardware is standard.
> The decision architecture is documented. Any engineer, anywhere,
> can read the codebase and understand it. And build on it."

**CREATOR 2:**
> "And that matters because — the organisations doing this work at scale
> are building things that cost thousands of dollars per unit.
>
> *(turns slightly toward Creator 1)*
>
> We're not trying to compete with that. We're trying to show
> that the approach works at a fraction of that cost,
> so that someone who wants to actually deploy this
> in a context where that cost matters — has a starting point."

**CREATOR 1:** *(nodding)*
> "This is a proof of concept. That's what it is and we're clear about that.
> The point is that the concept is proven.
> The navigation logic works. The AI pipeline works.
> The safety architecture works.
> What comes after that is engineering and resources. Not a question mark."

---

### SECTION F — `07:45 to 09:00` | THE CLOSING B-ROLL

**[BACK TO CAMPUS — same footpath as the opening]**

Return to the footpath from SHOT A1. Camera back low on the ground. Same angle as the opening.

No dialogue in this section. All ambient sound.

---

**SHOT F1 — The chassis on the path.**

The chassis is placed on the same footpath from the opening. Someone places it and steps back. GoPro ground level. We look at the chassis on the path — the same path a person with a cane was navigating in the opening shots.

Hold for 8 seconds.

*The connection completes without a word.*

---

**SHOT F2 — Screen + path in one frame.**

Creator holds the laptop showing the live simulation. Background is the actual path. The bounding boxes on screen are detecting what the real camera on the chassis would detect if it were running live.

*What the world looks like through NEMO's eyes.*

---

**SHOT F3 — Wide: Creators standing, chassis between them, campus behind.**

The final image of them together. They're looking at the campus, not the camera. The bot chassis is in front of them at ground level. The GoPro is low, wide, with sky above.

Hold 6 seconds.

---

**SHOT F4 — Slow tilt up from the chassis wheel to sky.**

GoPro handheld, starting ground level at the wheel, slowly tilts all the way up to the cloudy sky. This is your final shot.

**Fade to black in edit — slow, not sudden.**

---

### SECTION G — `09:00 to 09:30` | TITLE CARDS

**[OVER BLACK — in edit]**

```
NEMO_SENSE

An AI-powered navigation aid for the visually impaired.
```

Then:
```
Built by: [Creator Names]
[Institution / Program]
```

A final line, held for 8 seconds:

```
"Open source. Reproducible. Built to be improved."
```

**Minimal ambient sound or silence. No dramatic music.**

---

## PRACTICAL SHOT SCHEDULE FOR 9:30 AM SANSKARDHAM

Cloudy morning is ideal — light is consistent and will not change dramatically between shots.

| Order | Shot | Minutes to Shoot |
|---|---|---|
| 1st | A1, A2 — Empty campus B-roll while it's freshest and quietest | 15 min |
| 2nd | A3 — Person on campus path (recruit a friend or batchmate) | 10 min |
| 3rd | A4, A5 — Chassis and screen reveals | 10 min |
| 4th | B — Creator 1 monologue (do 3 takes, vary slightly each time) | 20 min |
| 5th | C — Hands, PCB, board close-ups (B-roll batch) | 20 min |
| 6th | D — Creator 2 monologue (3 takes) | 20 min |
| 7th | E — Both creators together | 15 min |
| 8th | F — Closing footpath shots | 15 min |
| 9th | Pickups — anything that felt uncertain | 15 min |

**Total on campus: ~2.5 hours. Do not rush.**

---

## MONOLOGUE DELIVERY NOTES

These are written as guides. **Know the ideas. Don't memorise the sentences.**

The camera will know if you're reciting. Speak to the concept, not the script.

**Things that make monologues feel real on a GoPro:**
- Slight pauses while thinking are good — don't fill them
- Looking at the object you're discussing (screen, chassis, board) while speaking is better than looking at camera
- Incomplete sentences feel more honest than perfectly finished ones
- If you lose the thread: say "actually — let me put it differently:" and continue. Keep it in.

**Things that kill it:**
- Speaking too fast (nervous energy — slow down)
- Perfect elocution (sounds like a script)
- Eyes going to the camera to check if it's running

---

## EDIT GUIDANCE

The raw footage will be cut into a flowing sequence. The "1917 feel" comes from:

- **Long takes within each section** — don't cut every 3 seconds
- **Ambient campus sound under everything** — wind, distant campus noise, not silence
- **No background music until the title cards** — let the words carry
- **Colour grade:** Slightly desaturated, cooled shadows, warm highlights (can be done in CapCut, DaVinci, or even GoPro's own Quik app with the "Matte" preset)
- **Titles:** Simple white text on black. No animated graphics. No drop shadows.

**Recommended CapCut colour settings for the cloudy morning footage:**
- Brightness: -5
- Contrast: +10  
- Saturation: -15
- Vignette: 20%
- Colour Temperature: -5 (slightly cooler)

---

## CHECKLIST — BEFORE YOU START ROLLING

- [ ] Boya Mic Minis charged and clipped
- [ ] GoPro settings locked (Protune ON, HyperSmooth Boost, White Balance: Cloudy)
- [ ] Spare GoPro battery and SD card
- [ ] nemo_demo.py running on laptop in sim mode (`python nemo_demo.py --sim`)
- [ ] Chassis cleaned up, wires tucked, nothing visibly broken on camera side
- [ ] Campus path relatively clear of unrelated pedestrians for opening shots
- [ ] Someone to help with the "person walking on path" shot (Shot A3)
- [ ] Do a Boya audio check — play back 30 seconds before any monologue

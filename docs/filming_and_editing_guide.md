# NEMO_SENSE — Complete Video Production Guide
### Filming + Editing. Everything you need start to finish.

---

## Before you pick up the phone

Read this whole doc once before filming anything. The most common mistake is going out to shoot without knowing what you need, then coming back and realising you're missing the one shot that holds the video together.

**What you need:**
- iPhone (any recent model, 13+ is ideal) on a gimbal (Hohem iSteady, DJI OM5, or similar)
- One person to operate the camera, one person to walk with the robot, one person to handle the robot/RC if needed
- 4–5 hours across two sessions (outdoor + indoor)
- CapCut on your phone for editing (free)

---

## PART 1 — FILMING

---

### Session 1: Outdoor (golden hour — 30–45 mins before sunset)

This is the session that makes or breaks your video. Go out when the light is good. Do not film outdoors at noon. The shadows are harsh and everything looks flat and overexposed.

Set your iPhone to: **Settings → Camera → Record Video → 4K at 30fps** (or 4K 24fps for a more cinematic feel). Lock exposure manually — tap and hold your subject until "AE/AF Lock" appears at the top of the screen. Do this every time you move to a new location.

---

**SHOT 1 — "Walking with the robot" (your most important shot)**

This is the shot that goes in the middle of the video and carries the emotional weight. Get it right.

Setup:
- Find a walkway, street, or corridor that looks like a real environment. It doesn't need to look fancy — a school corridor or a street near your house is fine as long as there's some activity in the background.
- Person A: walks normally, wearing the earphones (connected to the Android app), slight relaxed expression. Not acting nervous, not acting happy. Just walking.
- Person B: operates camera on gimbal at waist height, walks alongside or slightly ahead.
- Robot: moving just ahead of or alongside the walking person.

Angles to get (film each 3–4 times, pick the best in edit):
1. **Front-facing** — Camera is in front, walking toward it. Shows the person and robot approaching. Keep going for at least 15 steps after you feel you have the shot.
2. **Side tracking** — Camera moves with the person from the side, robot visible in frame. Gimbal smooths the walk.
3. **Low angle side** — Camera at knee height tracking alongside. Makes the robot look bigger and more purposeful.
4. **Behind** — Camera follows from behind. Person and robot visible, city/environment in background.

> **Tip:** If the full robot is awkward to control smoothly on a real street, you can do this shot with just the person walking and the robot stationary at intervals — cut between them in editing. Nobody will know.

---

**SHOT 2 — "Hesitation at the edge" (emotional beat)**

Find a step, curb, or threshold — somewhere a person might pause before stepping off.

- Person A stops just at the edge, pauses for a beat.
- Camera is LOW — phone nearly at ground level, gimbal tilted slightly upward, person's legs and the edge of the step visible.
- Hold the shot for 8–10 seconds before and after the pause. Don't rush it.
- The robot detects the step and stops. Let that happen naturally if possible.

> Do not over-direct the person. Tell them: "stand at the edge, pause, then step down." That's it. Slightly uncertain body language reads as real.

---

**SHOT 3 — "Arrived somewhere"**

Find a gate, archway, door, or any kind of entrance.

- Person walks through it, robot following.
- Camera position: slightly elevated above and to the side, angled down. If you're on a campus, a landing or low wall works.
- After walking through, person can briefly stop and relax — shoulders drop, slight exhale. Tell them: "you just got to where you were going. Show that." Don't tell them to smile.
- Optionally trigger the buzzer sound here — it's a satisfying audio cue.

---

**SHOT 4 — Wide establishing shot**

Get a wide shot of the environment — street, campus, or market — with the person and robot visible but small in the frame. This is your "world" shot that gives context.

- Camera should be elevated if possible (stand on something, get height).
- Let the person and robot walk through the frame from one side to the other.
- Shoot this 2–3 times.

---

### Session 2: Indoor / Table (any time, 1–2 hours)

These are your technical "proof" shots. They don't need perfect golden hour light — just controlled, interesting light.

---

**SHOT 5 — Arduino UNO Q close-up**

This is your most satisfying macro shot if you do it right.

- Lay a dark cloth (or even a dark T-shirt) on a table.
- Place the Arduino UNO Q on it.
- Use the phone's flashlight — or a desk lamp — from the SIDE (not directly above). This creates shadows that make the PCB traces, chips, and ports look dramatic.
- Slowly push the camera toward the board in a straight line. Use the gimbal's slow translation mode if it has one. If not, move your arms very slowly and let the gimbal smooth it out.
- Film for 20–30 seconds. You'll use 3–4 seconds of it.
- Also get a static shot with the camera locked off, board just sitting there, light from the side. 10 seconds.

---

**SHOT 6 — Relay module clicking**

This is a detail shot that makes the video feel technical and real.

- Film the relay module from 10–15cm away.
- Start a motor command sequence — `FORWARD`, then `STOP`, then `BACKWARD`.
- Each relay click is audible and visible (the small LED on the relay board turns on/off).
- Film this in slow motion if your phone supports it: **Settings → Camera → Slo-mo → 120fps or 240fps**.
- The relay click in slow motion looks and sounds impressive.
- Record the audio too — it's a satisfying mechanical sound.

---

**SHOT 7 — Android app screen**

Screen record the app while actively doing things.

How to screen record on iPhone: Swipe down Control Centre → tap the Screen Record button.

Capture:
1. Opening the app, seeing the "Disconnected" state
2. Tapping Connect, watching it find the robot
3. The status screen updating (obstacle zones, battery indicators)
4. Pressing the voice command button, saying "stop"
5. The robot responding (cut to the motor stopping)

This becomes an insert shot — a small window in the corner of the screen during the "technical" section of the video.

---

**SHOT 8 — Robot on a simple turntable**

Put the robot on a slowly rotating platform. An office chair seat (turned by hand) or a kitchen lazy susan works.

- Light from one side only (lamp or flashlight from 45° angle).
- Camera locked off on a tripod or stacked books — not moving, just watching.
- Rotate slowly. One full rotation takes about 30 seconds.
- You'll use maybe 5–8 seconds of this. It's your "product" shot.

---

**SHOT 9 — Sensor wire and board detail shots**

Quick macro shots of:
- The HC-SR04 ultrasonic sensor face-on (the two circles look like eyes — good visual)
- The relay module wire connections
- The LM393 encoder disc spinning slowly (hold by hand or tape a motor test command)
- The voltage divider resistors (if visible)

These are cutaway shots for the editing section. Film each for 5–10 seconds.

---

## PART 2 — EDITING IN CAPCUT

*Total editing time: 2–3 hours. Don't rush it.*

---

### Step 1 — Import and organize

Open CapCut. Create a new project. Import ALL your footage in one go.

Before you start cutting, watch everything once. For each clip, either:
- Keep it as-is (good shot)
- Mark the good section (drag in/out points)
- Delete it if it's clearly unusable (blurry, wrong angle, person looking at camera awkwardly)

---

### Step 2 — Build the rough cut (no music yet)

Arrange clips in this rough order (adjust once you have music):

```
[0:00 – 0:06]  Wide establishing shot (Shot 4) or hesitation shot (Shot 2)
               No music. Just ambient sound or silence.

[0:06 – 0:12]  The walking shot, front angle (Shot 1, front-facing)
               Keep it wide, let it breathe.

[0:12 – 0:18]  Arduino close-up (Shot 5) + relay clicking (Shot 6)
               Quick cut between the two.

[0:18 – 0:40]  Walking shots, multiple angles (Shot 1, all angles)
               App insert in corner (Shot 7, shrunk to 25% size, top right corner)

[0:40 – 0:52]  Detail shots (Shot 9 — sensor, encoder, etc.)
               Cut fast, 2–3 seconds each.

[0:52 – 1:05]  "Arrived" shot (Shot 3). Slow it down here.
               Robot turntable (Shot 8) at the end.

[1:05 – 1:20]  Name + GitHub link + logo
               Robot turntable or static board shot.
```

This is a guide, not a rule. If a shot feels right somewhere else, move it.

---

### Step 3 — Add music

Go to **CapCut → Audio → Sounds → Search: "cinematic"** — or use one from YouTube Audio Library (download on PC, import into CapCut via phone).

Music structure:
- Starts quiet/atmospheric at the beginning
- Builds through the middle section (walking shots)
- Drops to something softer for the "arrived" moment
- Fades out over the closing card

**Do not use a song with lyrics.** It distracts from the voiceover.

**Cut to the beat.** Listen to where the music has a beat or a drum hit. Put your edit cuts there. This is the single biggest thing that makes a video feel professional vs. amateur.

In CapCut: tap the audio track → you'll see the waveform. Each spike in the waveform is roughly where a beat is. Zoom in on it and place your cuts on the spikes.

---

### Step 4 — Add voiceover

Record the voiceover on your phone in a quiet room. Hold the phone 15–20cm from your mouth. If there's echo, sit inside a wardrobe or hang a blanket around yourself.

**What to say** (adapt to your own voice, don't read it robotically):

> *"285 million people worldwide are visually impaired. In India, it's nearly five crore. For most of them, navigating a busy street means relying on a white cane that can only detect things at ground level. NEMO_SENSE uses the Arduino UNO Q's AI chip to see obstacles in real time, steer around them, and guide you through your phone — with no internet, no PC, and no screen to look at. Built for under six thousand rupees."*

Keep it natural. If you stumble on a word, just pause and say it again. You can cut in editing. Don't try to sound like an announcer.

In CapCut: **Audio → Voice Recording** — record directly in the app and place it over the middle-to-end section of the video.

---

### Step 5 — Add text

Use text sparingly. Three or four cards maximum in the whole video.

Recommended:

| Time | Text |
|---|---|
| Start (first 3 sec) | **"285 million people are visually impaired"** — white, simple font, bottom third |
| First tech shot | **"NEMO_SENSE"** — large, centre, 2 seconds |
| Walking section | **"AI obstacle detection. No internet."** — small, bottom third |
| End card | **"github.com/Vayu-Maverick/Nemo_Sense"** — white, bottom, stays for 10 seconds |

**Font to use in CapCut:** Search "Montserrat" or use the clean sans-serif fonts under "Other" → "Modern". Avoid anything decorative.

**Text style:** White text. No outline. Slight fade-in (0.3s). Keep it on screen for 2–3 seconds minimum so it's actually readable.

---

### Step 6 — Color grading

In CapCut: select the full video, tap **Adjust → Filters → Cinematic**.

Then fine-tune manually (tap Adjust → Effect):
- **Brightness:** -5 to -10 (slightly darker looks more cinematic)
- **Contrast:** +10 to +15
- **Saturation:** -10 (slightly desaturate — avoids it looking cartoon-y)
- **Highlights:** -15 (bring down harsh highlights)
- **Shadows:** +10 (lift the dark areas slightly so they're not crushed)
- **Color Temperature:** -5 to -10 (slightly cooler/bluer tone looks modern)

For the close-up tech shots (Arduino, relay), you can do a separate adjustment:
- Bring **contrast** up to +20
- Bring **shadows** down to -5 (let the dark areas go darker — it looks more dramatic)

---

### Step 7 — Sound effects

Add these as separate audio layers (CapCut → Audio → Effects or import from your recordings):

| Moment | Sound |
|---|---|
| Robot starts moving | Subtle motor hum (record from the actual robot) |
| Obstacle detected | Your relay click recording (Shot 6) |
| Robot stops | Soft "stop" audio from the buzzer |
| App connecting | Short BT connect sound |

Keep all SFX at 30–40% volume below the music track. They should be felt, not heard.

---

### Step 8 — Export

**CapCut → Export → 4K → H.265 → 60fps** if your footage was 60fps. If you shot in 30fps, export at 30fps.

File size will be 400–600MB. That's fine.

If uploading to YouTube: title the video as **"NEMO_SENSE — AI Navigation Robot for the Visually Impaired | Arduino UNO Q"** and put the GitHub link in the description.

---

## Common mistakes — don't do these

| Don't | Do Instead |
|---|---|
| Film at noon (harsh overhead light) | Film at golden hour or near a window |
| Shoot everything from the same height | Mix high, low, and eye-level angles |
| Add too many cuts (under 1 second each) | Hold shots for at least 2–3 seconds |
| Let the music be too loud | Music should be background, not foreground |
| Put text in the centre of the frame | Keep text in the bottom third |
| Use a lens that's dirty | Wipe your phone camera before every session |
| Let the person look at the camera | Direct them to look where they're walking |
| Add effects/filters to the relay close-up | The raw shot already looks good |

---

## Final checklist before upload

- [ ] First 3 seconds are visually striking (people decide in 3 seconds whether to keep watching)
- [ ] Video is under 90 seconds
- [ ] "NEMO_SENSE" appears at least once as text
- [ ] GitHub link shown clearly at the end (minimum 8 seconds on screen)
- [ ] Audio doesn't distort or clip at any point
- [ ] Voiceover is clear and understandable
- [ ] Color grading applied consistently (not just on some clips)
- [ ] Subtitles/captions added (YouTube auto-captions work fine)
- [ ] Watch the whole thing once with the volume off — if it still makes visual sense, you're done
- [ ] Watch it once on a phone screen (most viewers watch on phone) — text must be readable

---

*Total shoot time: 4–5 hours across 2 sessions. Editing: 2–3 hours. Export and upload: 30 minutes. Total: one good weekend.*

*Don't wait for perfect conditions. Go film.*

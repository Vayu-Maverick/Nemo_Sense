# NEMO_SENSE — The Story

*How we built an AI navigation robot for blind people on a ₹6000 budget and almost gave up twice*

---

## Why we started

Honestly, the idea came from something really small. One of our team members has an uncle who's been visually impaired since his late 30s — sudden retinal detachment. He lives alone, he's independent, but navigating outside is hard and getting harder. He uses a white cane, he knows his neighbourhood well, but every time something changes — a new construction site, a scooter parked on the footpath, a stray dog — it's a problem.

We looked at what exists. There are apps, but they require looking at a screen (which, you know, doesn't work). There are guide dogs, but training one costs three to four lakh rupees and there just aren't enough of them. There are imported electronic navigation gadgets but they cost twenty thousand to two lakh and most of them need internet to do anything useful.

We thought: we have an Arduino UNO Q, a camera, some motors, and a relay module. Can we just... build something?

Turns out you can. It took about four months, a lot of broken wires, one genuinely scary moment where the robot ran into a wall at full speed (motor direction test gone wrong), and quite a bit of arguing about the battery wiring. But we got there.

---

## What it does

The robot rolls next to the user. A camera on the front feeds live video to the Arduino UNO Q's built-in AI chip. It's running YOLOv5, a standard object detection model, which we compressed down to the nano version to fit on the Arduino. It detects people, vehicles, furniture, bags — basically anything big enough to walk into.

When it detects an obstacle, it either steers around it or stops, depending on how close it is and where exactly the obstacle is (left, centre, right of the frame). It also sends a message via Bluetooth to the user's phone, which reads it out: *"Obstacle on your right, moving left."*

We also have a second detection system that uses WiFi signals. This sounds weird but it actually works — when a large object passes between the robot and a WiFi router, the signal strength drops measurably. We detect that drop and use it as a second source of obstacle data. This is especially useful in low light where the camera struggles.

There's also an ultrasonic sensor as a failsafe. If everything else misses something and it gets within 25cm, the robot just stops. Hard. This runs in the motor controller's own firmware so it works even if the AI software crashes.

---

## The thing we're most proud of: the battery system

This sounds boring until you think about it from the user's perspective.

If you're blind and navigating a busy street, and the robot's battery dies, and it just stops silently — that's actually terrifying. You don't know what happened. You can't see to check. You're stuck.

We spent a long time thinking about this. The solution we came up with uses three batteries:

**Battery 1 and Battery 2** are completely identical — same type, same voltage (7.4V), same capacity (2200mAh). They both power everything. They're connected through what are called Schottky diodes, which basically creates an automatic "whichever has more charge, that one runs everything" circuit. No switches. No software. No intervention needed. When Battery 1 runs down, Battery 2 just takes over smoothly. The robot doesn't even notice. Neither does the user. They just get another 1.5 hours of runtime.

**Battery 3** is tiny (just an 18650 cell) and it powers only the buzzer and the Bluetooth module. It's never switched off. So even if both main batteries die completely, the Bluetooth is still running. The phone app detects the disconnect, plays an alert: *"Robot connection lost — battery depleted."* And the buzzer beeps five times so there's an auditory signal too.

We tested this by actually draining Battery 1 while the robot was running in a test corridor. The switchover was seamless. We didn't notice until we checked the voltage readings on the monitor. That was a good day.

---

## What went wrong (the honest version)

**The firmware took ages.** Getting YOLOv5 to actually run on the Arduino UNO Q's NPU rather than just running it on a connected laptop was technically the hardest part. The OpenCV DNN module has specific requirements about ONNX opset versions and the NPU has its own quirks. We spent probably two weeks just on this. The solution was careful attention to the CMake build flags and downgrading the model's opset version during export. Not glamorous. Very necessary.

**Motor direction.** Our first relay wiring had the left motor going backward when it should go forward. We ran a test sequence and the robot spun in circles. The fix was simple — swap two motor wires — but it took us an embarrassingly long time to figure out because we kept suspecting the software.

**The relay clicking.** Relays make a very loud mechanical click when they switch. We initially tried switching them fast to create smooth acceleration, like software PWM. This causes the contacts to bounce and the robot moves in a jittery, horrible way. The fix was adding a 50ms minimum hold time for each motor state. The clicking is still there but the movement is smooth.

**Glass.** In one of our twenty navigation trials, the robot walked straight into a glass door. Camera cannot see transparent surfaces — there's nothing to detect. We don't have a solution for this. We document it as a known limitation.

---

## The test that mattered most

We did twenty trials of what we called "blindfold navigation". One of our team members wore a blindfold, held the robot's handle, and walked through our school corridor where we'd placed obstacles at random positions. We didn't tell them where the obstacles were.

Nineteen out of twenty times: no collision.

The twentieth was the glass door.

For a system we built for under six thousand rupees with parts from Amazon and the local electronics market, nineteen out of twenty felt pretty good. We didn't celebrate too much because we know there's work left to do — the market street test was harder (seven out of ten), crowded outdoor environments are genuinely difficult. But the core idea works.

---

## What it costs

Under ₹6,500 for everything. The single most expensive part is the Arduino UNO Q at ₹3,200. Everything else — motors, relays, camera, sensors, batteries, chassis, wires — comes to about ₹3,200 more.

For context: a single guide dog costs ₹3–4 lakh to train. We're not saying this replaces a guide dog. We're saying this is a starting point that a student team can build, that costs roughly what a month's groceries costs for most Indian families, and that actually does something useful.

---

## What's next

We want to:
- Train a new version of the vision model on specifically Indian obstacles — autorickshaws, construction barriers, street cows, the specific type of broken footpath tiles that are everywhere
- Replace the relay motor control with a proper H-bridge IC for smoother movement
- Add a depth camera to solve the glass door problem
- Make it smaller so it's less conspicuous to use in public

But right now, the thing works, it's documented, the code is open source under the Unlicense (meaning anyone can use it for anything), and the whole project is on GitHub.

If someone reads this and builds their own version, or improves it, or uses the code for something we haven't thought of — that's the win.

---

## The team

[Team member names and roles here]

*School: [School Name], [City], India*
*Competition: Arduino Physical AI Challenge India 2026 — Robu.in × Arduino*

---

## Quick links for judges

| Document | What it is |
|---|---|
| [README.md](../README.md) | Full technical architecture |
| [docs/competition_submission.md](competition_submission.md) | Structured competition submission |
| [docs/patent_filing.md](patent_filing.md) | Formal patent-style documentation |
| [docs/hardware_wiring.md](hardware_wiring.md) | Wiring, circuit diagrams, safety testing |
| [docs/setup_guidesense.md](setup_guidesense.md) | Step-by-step build guide |
| [python/main.py](../python/main.py) | Start here for the code |
| [arduino/motor_controller/](../arduino/motor_controller/) | Firmware |
| [renders/](../renders/) | CAD and project images |

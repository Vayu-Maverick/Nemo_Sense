PATENT APPLICATION

APPLICATION NUMBER: [To be assigned]
FILING DATE: August 2026
TITLE: AUTONOMOUS OBSTACLE-DETECTING NAVIGATION SYSTEM FOR VISUALLY IMPAIRED PERSONS USING ON-DEVICE NEURAL PROCESSING AND MULTI-SENSOR REDUNDANCY

APPLICANT(S): [Team Members], [School Name], [City], [State], India
AGENT/REPRESENTATIVE: [If applicable]
PRIORITY: Domestic — Arduino Physical AI Challenge India 2026

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FIELD OF THE INVENTION

The present invention relates to assistive navigation technology for visually impaired persons, and more specifically to a standalone mobile robotic system incorporating on-device artificial intelligence inference, multi-modal sensor fusion, redundant power systems, and wireless audio guidance without dependence on external computing infrastructure, cloud services, or internet connectivity.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BACKGROUND OF THE INVENTION

1. Approximately 285 million persons worldwide are estimated to have some degree of visual impairment, of whom approximately 39 million are classified as totally blind (World Health Organisation, 2023). In India, national surveillance data from the National Programme for Control of Blindness estimates approximately 50 million persons with significant visual impairment.

2. Navigation of urban environments presents particular hazards for visually impaired individuals including, but not limited to: obstacles at torso and head height not detectable by a conventional white cane; sudden introduction of mobile obstacles such as pedestrians, cyclists, and animals; open excavations and infrastructure discontinuities in pedestrian zones; and dense crowd conditions that render conventional auditory and tactile cues insufficient.

3. Existing assistive navigation technology falls into several categories, each with identified limitations:

   (a) White Cane (Conventional): Detection radius limited to approximately 1–2 metres at ground level only. Provides no information regarding obstacle type, height, or recommended avoidance direction. Requires continuous active sweeping motion resulting in user fatigue.

   (b) GPS-Based Mobile Applications: Require visual interaction with a display device. Do not detect physical obstacles. Performance degraded in urban canyon environments due to signal multipath. Require continuous internet connectivity.

   (c) Guide Dogs: Availability limited by lengthy training periods (12–18 months) and associated costs (estimated ₹3,00,000–₹4,00,000 per animal in India). Cannot provide verbal directional guidance.

   (d) Commercial Electronic Travel Aids: Available products in the ₹20,000–₹2,00,000 price range typically require internet connectivity for AI inference, proprietary hardware not serviceable by local technicians, and in several cases require a companion device operated by a sighted person.

4. There therefore exists a need for an autonomous navigation assistance system that: operates without internet connectivity or external computing; detects obstacles at multiple heights and distances; communicates guidance information through audio output requiring no visual interaction; is constructable from commercially available components at a total material cost accessible to the general public; and incorporates sufficient redundancy to ensure reliable operation in the context of a safety-critical assistive application.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SUMMARY OF THE INVENTION

5. The present invention provides an autonomous mobile robotic navigation assistance system, hereinafter referred to as NEMO_SENSE, comprising:

   (a) A differential-drive mobile platform carrying all computational, sensory, and power subsystems;

   (b) An on-device neural processing unit executing a compressed convolutional neural network (YOLOv5 nano, ONNX format) for real-time obstacle detection via a connected USB camera, without transmission of image data to any external system;

   (c) A supplementary passive radio-frequency obstacle detection subsystem utilising WiFi Received Signal Strength Indicator (RSSI) shadow-fading analysis;

   (d) A proximity hard-stop subsystem comprising an ultrasonic time-of-flight sensor with firmware-level interrupt, operating independently of the primary AI inference pipeline;

   (e) A dead-reckoning odometry subsystem comprising dual optical wheel encoders with a proportional heading controller;

   (f) A triple-redundant power supply architecture comprising two identical primary batteries with passive Schottky diode automatic failover, and an independent emergency subsystem battery maintaining wireless communication functionality even upon total depletion of primary power supplies;

   (g) Multiple hardware safety mechanisms including a series normally-closed emergency stop switch, flyback suppression diodes on all inductive relay coils, and a series blade fuse on the motor power supply line;

   (h) A wireless Bluetooth audio guidance interface transmitting navigation instructions to a companion Android application which renders them as audible text-to-speech output, requiring no visual interaction by the user.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DETAILED DESCRIPTION OF PREFERRED EMBODIMENTS

EMBODIMENT 1 — PRIMARY OBSTACLE DETECTION SUBSYSTEM

6. The primary obstacle detection subsystem comprises a standard USB Video Class (UVC) camera module connected to the USB Type-A host port of the Arduino UNO Q microcontroller board (ABX00087). The Arduino UNO Q incorporates a Renesas RA4M1 Cortex-M4 processor operating at 48 MHz, with an integrated Neural Processing Unit (NPU) capable of accelerating ONNX format neural network inference.

7. Camera frames are captured at a resolution of 640×480 pixels. Each frame is pre-processed as follows:
   (a) Spatial resizing to 640×640 pixels using bilinear interpolation;
   (b) Channel normalisation: each pixel value divided by 255.0 to produce a floating-point tensor in the range [0.0, 1.0];
   (c) Construction of a four-dimensional NCHW blob tensor suitable for OpenCV DNN module inference.

8. The pre-processed tensor is submitted to inference through a YOLOv5 nano (YOLOv5n) model, comprising approximately 1.9 million parameters, stored in ONNX interchange format (7.2 MB), resident in onboard flash storage.

9. Inference outputs are filtered by a confidence threshold of 0.45. Each retained detection is assigned to a lateral zone based on the horizontal centre coordinate of the bounding box:
   (a) LEFT zone: centre x-coordinate < 213 pixels;
   (b) CENTER zone: centre x-coordinate ≥ 213 and ≤ 426 pixels;
   (c) RIGHT zone: centre x-coordinate > 426 pixels.

10. A proximity estimate is derived from the ratio of bounding box area to total frame area, providing an approximation of relative distance without requiring stereo vision or depth sensors.

EMBODIMENT 2 — SUPPLEMENTARY WIFI RSSI SHADOW-FADING DETECTION SUBSYSTEM

11. The supplementary obstacle detection subsystem operates in a dedicated background execution thread and performs periodic scanning of available IEEE 802.11 (WiFi) access points at intervals of 500 milliseconds.

12. For each tracked access point identified by its Basic Service Set Identifier (BSSID), an exponential moving average (EMA) baseline RSSI is maintained according to:
    B(t) = α · R(t) + (1 − α) · B(t−1)
    where R(t) is the current RSSI measurement, B(t) is the updated baseline, and α = 0.1 is the smoothing coefficient.

13. Shadow-fading detection is triggered when: R(t) < B(t) − 6.0 dBm. This threshold of 6 dBm corresponds to the approximate signal attenuation caused by a human body at indoor distances, as established in prior literature on passive WiFi radar sensing.

14. Obstacle confidence for each lateral zone is derived from the count of access points simultaneously exhibiting shadow-fading events, normalised by total tracked access point count, with a distribution weighting of 0.6 to the CENTER zone and 0.3 to each of LEFT and RIGHT zones in the absence of directional antenna data.

EMBODIMENT 3 — ULTRASONIC PROXIMITY HARD-STOP SUBSYSTEM

15. An HC-SR04 ultrasonic time-of-flight sensor is connected to the motor controller microcontroller unit with TRIG signal on digital pin D12 and ECHO signal on digital pin D11. The sensor emits a 40 kHz ultrasonic pulse train triggered by a 10 microsecond TTL pulse, and measures the return echo duration.

16. Distance is computed as: d (cm) = pulse_duration (μs) / 58.

17. Critically, the proximity hard-stop threshold of 25 cm is enforced at the firmware level within the motor controller microcontroller, which operates independently of the primary AI inference pipeline executing on the main Arduino UNO Q. Should the AI brain software experience a software fault, deadlock, or unexpected termination, the proximity hard-stop continues to function without interruption.

EMBODIMENT 4 — DEAD-RECKONING ODOMETRY AND HEADING CONTROL

18. Two LM393-type optical wheel encoders are mounted on the motor shafts, each equipped with a 20-slot encoding disc. Encoder pulses are counted via hardware interrupt on digital pins D6 (left) and D7 (right).

19. Per-tick linear displacement is computed as:
    d_tick = C_wheel / N_slots = (π × 65mm) / 20 = 10.2 mm/tick
    where C_wheel is wheel circumference and N_slots is the number of encoder disc slots.

20. Robot pose (x, y, θ) is updated on each encoder event pair using differential drive kinematics:
    d_L = Δticks_L × d_tick
    d_R = Δticks_R × d_tick
    d_c = (d_L + d_R) / 2
    Δθ = (d_R − d_L) / L_base   [L_base = 150 mm wheelbase]
    x ← x + d_c · cos(θ + Δθ/2)
    y ← y + d_c · sin(θ + Δθ/2)
    θ ← θ + Δθ

21. A proportional (P) heading controller generates differential motor speed commands:
    e = θ_target − θ
    turn = K_p · e   [K_p = 100, empirically tuned]
    v_L = clamp(v_base − turn, 0, 255)
    v_R = clamp(v_base + turn, 0, 255)

EMBODIMENT 5 — TRIPLE-REDUNDANT POWER SUPPLY ARCHITECTURE

22. The power supply architecture comprises three independent battery units designated BAT-1, BAT-2, and BAT-3.

23. BAT-1 and BAT-2 are identical in chemistry, nominal voltage, and capacity: both are lithium polymer (LiPo) cells, 7.4V nominal (2S configuration), 2200 mAh capacity. Both cells power the identical set of electrical loads.

24. Automatic failover between BAT-1 and BAT-2 is achieved by connecting each cell's positive terminal to the shared main power rail through an individual 1N5822 Schottky barrier diode (cathode toward the rail). The forward voltage drop of this device type is approximately 0.3V. The passive diode OR circuit ensures that whichever battery maintains the higher terminal voltage supplies the load current. As BAT-1 discharges and its terminal voltage decreases below that of BAT-2, load current smoothly transfers to BAT-2. No active switching, relay, or software intervention is required.

25. BAT-3 is a lithium-ion cell (3.7V nominal, 800 mAh capacity) connected directly and permanently to the buzzer transducer and Bluetooth communication module, without any switching element in series. This ensures that upon total depletion of BAT-1 and BAT-2, resulting in cessation of all motor and computational functions, the Bluetooth module remains powered and the companion Android application receives a connection-lost notification, triggering an audible alert to the user.

26. All three battery terminal voltages are monitored continuously via resistive voltage dividers connected to Arduino analog inputs A0 (BAT-1), A1 (BAT-2), and A2 (BAT-3). Voice guidance alerts are triggered at defined depletion thresholds.

EMBODIMENT 6 — MOTOR CONTROL VIA RELAY SWITCHING

27. Motor direction is controlled by a four-channel electromechanical relay module (5V coil, 10A contact rating) operating in active-LOW logic: a logic LOW signal on an input pin energises the corresponding relay coil, closing the normally-open contact.

28. Two relay channels are allocated per drive motor, enabling bidirectional current flow through H-bridge-equivalent switching:
    FORWARD:  relay pair A closed, B open → current flows motor terminal A → B
    BACKWARD: relay pair A open, B closed → current flows motor terminal B → A
    STOP:     both relays open → motor freewheels

29. Inductive kickback suppression diodes (1N4007, rated 1A, 1000V reverse) are placed in antiparallel across each relay coil to suppress voltage transients upon deenergisation.

30. A 5A rated automotive blade fuse is placed in series with the motor power supply line between BAT-1/BAT-2 and the relay common contacts, providing overcurrent protection in the event of motor stall.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CLAIMS

1. An autonomous navigation assistance system for visually impaired persons, comprising: a mobile robotic platform; an on-device neural processing unit executing obstacle detection inference without external computing; a multi-modal sensor fusion subsystem combining camera-based detection, radio-frequency shadow-fading detection, and ultrasonic proximity sensing; and an audio guidance interface transmitting navigation instructions to a user-worn or user-carried audio output device.

2. The system of claim 1, wherein the on-device neural processing unit executes a YOLOv5 nano convolutional neural network in ONNX interchange format via an OpenCV DNN inference pipeline, classifying detected obstacles into three lateral zones: LEFT, CENTER, and RIGHT.

3. The system of claim 1, wherein the radio-frequency shadow-fading subsystem monitors RSSI variations across multiple IEEE 802.11 access points and detects obstacles by identifying RSSI drops exceeding 6 dBm below an exponential moving average baseline.

4. The system of claim 1, further comprising a proximity hard-stop subsystem operating at firmware level independently of the primary AI inference pipeline, enforcing a minimum safe distance of 25 cm via ultrasonic time-of-flight measurement.

5. The system of claim 1, further comprising a dead-reckoning odometry subsystem using dual optical wheel encoders and differential drive kinematics to maintain a real-time pose estimate, combined with a proportional heading controller for autonomous navigation toward a target heading.

6. The system of claim 1, wherein the power supply architecture comprises two identical primary batteries connected to a shared power rail via Schottky barrier diodes in an OR configuration providing passive automatic failover, and a third independent emergency battery maintaining wireless communication functionality upon depletion of both primary batteries.

7. The system of claim 6, wherein the Schottky barrier diodes are of type 1N5822 with a forward voltage drop of approximately 0.3V, ensuring minimal power loss during failover.

8. The system of claim 1, further comprising hardware safety mechanisms comprising: a normally-closed series emergency stop switch in the motor power rail; inductive kickback suppression diodes in antiparallel across all relay coils; and a series blade fuse rated 5A in the motor power supply line.

9. The system of claim 1, wherein the audio guidance interface communicates via Bluetooth RFCOMM protocol, transmitting JSON-encoded status and guidance messages to a companion Android application which renders navigation instructions as text-to-speech audio output, requiring no visual interaction by the user.

10. The system of any preceding claim, wherein the entire system operates without internet connectivity, cloud computing services, or external computer hardware during normal navigation operation.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ABSTRACT

An autonomous mobile navigation assistance system for visually impaired persons comprising a differential-drive robotic platform integrating on-device AI inference (YOLOv5 nano via Arduino UNO Q NPU), WiFi RSSI shadow-fading obstacle detection, ultrasonic proximity hard-stop, dead-reckoning odometry, and Bluetooth audio guidance. The system operates entirely without internet connectivity or external computing. A novel triple-redundant power architecture employs two identical primary batteries with passive Schottky diode automatic failover and an independent emergency battery maintaining wireless communication upon primary power depletion. Hardware safety features include series emergency stop, relay coil flyback suppression, and motor supply fusing. Total material cost is below USD 80, enabling broad accessibility in developing market contexts.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DRAWINGS REFERENCED

FIG. 1 — System architecture block diagram
FIG. 2 — Circuit schematic: Arduino UNO Q pin assignments and relay module
FIG. 3 — Power distribution diagram: triple battery Schottky OR architecture
FIG. 4 — Data flow pipeline: camera → inference → fusion → motor control
FIG. 5 — Dead-reckoning odometry: differential drive kinematics
FIG. 6 — Obstacle zone classification: LEFT / CENTER / RIGHT

[Figures correspond to diagrams in docs/hardware_wiring.md and README.md]

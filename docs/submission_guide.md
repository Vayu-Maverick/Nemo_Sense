# Submission Checklist — Arduino Physical AI Challenge India 2026

> Use this before submitting. Tick each box.

---

## Code submission

- [ ] All code pushed to GitHub repository
- [ ] Repository is PUBLIC (not private) — judges need to access it
- [ ] `main` branch has the complete project
- [ ] `production` branch has only the robot-running code (clean for judges)
- [ ] No API keys or passwords committed anywhere (check with `git log --all -p | grep -i "key\|password\|secret"`)
- [ ] README.md is clear, explains what the project does in the first 3 lines
- [ ] UNLICENSE file is present
- [ ] `.gitignore` excludes `__pycache__/`, `.env`, large model files if applicable

---

## Required files check

- [ ] `q_brain.py` — main AI brain
- [ ] `arduino/motor_controller/motor_controller.ino` — motor firmware
- [ ] `requirements.txt` — Python dependencies
- [ ] `yolov5n.onnx` — AI model file (7MB, check file size matches)
- [ ] `docs/hardware_wiring.md` — wiring documentation
- [ ] `docs/competition_report.md` — project report
- [ ] `docs/setup_guidesense.md` — how to build and run it

---

## Hardware documentation

- [ ] Wiring diagram is complete and correct
- [ ] Pin map matches the actual firmware (`D2-D5` for relays, etc.)
- [ ] Bill of Materials with costs is in the report
- [ ] Photos of physical robot are attached (to the form, or linked in README)

---

## Video

- [ ] Video is uploaded to YouTube (or Google Drive if YouTube not available)
- [ ] Video shows the robot actually working — not just a presentation
- [ ] Video is under 3 minutes
- [ ] Link is added to README or submission form

---

## Final checks

- [ ] Team name and school are filled in at the top of `competition_report.md`
- [ ] GitHub repo URL matches exactly what you submitted on the form
- [ ] Test that someone else can clone the repo and run it with just the README instructions
- [ ] All team members' names are in the submission form

---

## Submission form

Submit at: https://www.robu.in/arduino-physical-ai-challenge (check contest website for current link)

Deadline: As per contest announcement — don't miss it!

---

*If you've ticked everything above — you're done. Good luck!*

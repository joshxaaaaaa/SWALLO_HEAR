# SWALLOHear mobile app: feature walkthrough

A captioned walkthrough of **every feature of the mobile app**, one by one, with a finger indicator showing each tap,
swipe and drag.

<img src="highlights.gif" width="300" alt="Highlights: timeline, event card and stress test">

**▶ [Full walkthrough video](walkthrough.mp4)** (4:32). Each feature also has its own short clip in the table below.

> **How this was recorded.** These videos come from the app's own code (its web build, the same screens and features)
> shown at iPhone size (390 × 844) inside an iPhone frame, driven automatically by
> [`scripts/record_mobile_demo.py`](../../scripts/record_mobile_demo.py). On a real iPhone or Android phone the same
> screens run natively through Expo Go (see the [mobile app guide](../MOBILE_GUIDE.md)). In the *Record* step the
> browser's test tone stands in for a throat recording. Demo audio: Khalifa et al. (2021), CC BY 4.0.
> Research prototype, not a diagnostic device.

| # | Snapshot | Feature | Starts at | Clip |
|---|---|---|---|---|
| 1 | <img src="snapshots/01_welcome.png" width="150" alt="Welcome"> | **Welcome**<br>The header has the light/dark switch and ⚙ for detector settings. The yellow banner is always there: SWALLOHear is a research prototype, not a diagnostic device. | 0:03 | [▶ clip](clips/01_welcome.mp4) |
| 2 | <img src="snapshots/02_clip_picker.png" width="150" alt="Pick a recording"> | **Pick a recording**<br>Four sources: demo clips from held-out test participants, upload, the phone microphone, or synthetic test signals. Here: demo clip ns027d_1. | 0:12 | [▶ clip](clips/02_demo_clip.mp4) |
| 3 | <img src="snapshots/03_verdict.png" width="150" alt="Verdict and summary"> | **Verdict and summary**<br>First the quality gate, then the verdict: events detected. The cards show confident and low-confidence events, event rate, estimated SNR against the gate, and processing time. | 0:21 | [▶ clip](clips/03_verdict.mp4) |
| 4 | <img src="snapshots/04_timeline.png" width="150" alt="Timeline"> | **Timeline**<br>Waveform, spectrogram and detector score on one time axis. Teal = Confident, amber = Low-confidence, dotted green = expert labels. Zoom up to 8× and swipe sideways. | 0:30 | [▶ clip](clips/04_timeline.mp4) |
| 5 | <img src="snapshots/05_event_card.png" width="150" alt="Event card"> | **Event card**<br>Tap a numbered marker to inspect an event: listen to just that sound, see its reliability against the threshold and what raised or lowered it, then record your own call. | 0:40 | [▶ clip](clips/05_event_card.mp4) |
| 6 | <img src="snapshots/06_why_this_score.png" width="150" alt="Events and “Why this score?”"> | **Events and “Why this score?”**<br>A table of every event, then an exact breakdown of the reliability score: it starts from an average event and each measurement pushes it up (teal) or down (amber). | 0:53 | [▶ clip](clips/06_why.mp4) |
| 7 | <img src="snapshots/07_rhythm.png" width="150" alt="Rhythm"> | **Rhythm**<br>How swallowing is spread over time: rate, mean interval, regularity and the longest pause, with events-over-time and interval charts. Shown here on clip s007a_2, which has six events. | 1:09 | [▶ clip](clips/07_rhythm.mp4) |
| 8 | <img src="snapshots/08_robustness.png" width="150" alt="Robustness lab"> | **Robustness lab**<br>Re-runs the analysis at seven noise levels. Watch the events thin out and the quality gate start withholding results once the estimated SNR falls below the red line. | 1:27 | [▶ clip](clips/08_robustness.mp4) |
| 9 | <img src="snapshots/09_quality.png" width="150" alt="Signal quality"> | **Signal quality**<br>Every quality-gate check with its value and limit, how the SNR is estimated (noise floor vs peaks) and the average spectrum, where mains hum would show as spikes. | 1:37 | [▶ clip](clips/09_quality.mp4) |
| 10 | <img src="snapshots/10_expert.png" width="150" alt="Expert comparison"> | **Expert comparison**<br>For labelled clips: matched events, false detections, misses, precision, recall and F1, and Expert vs System lanes (green = matched, red = unmatched). | 1:46 | [▶ clip](clips/10_expert.mp4) |
| 11 | <img src="snapshots/11_session.png" width="150" alt="Session log"> | **Session log**<br>Every analysis run in this session, with exports of the log and of all your calls on events. | 1:55 | [▶ clip](clips/11_session.mp4) |
| 12 | <img src="snapshots/12_stress_withheld.png" width="150" alt="Stress test"> | **Stress test**<br>Add white, pink or 60 Hz mains-hum noise, or simulate clipping. At 10 dB of white noise the estimated SNR drops below the gate and the result is withheld instead of guessed. | 2:04 | [▶ clip](clips/12_stress.mp4) |
| 13 | <img src="snapshots/13_settings.png" width="150" alt="Detector settings"> | **Detector settings**<br>All five thresholds, live. Raising the reliability threshold makes fewer events Confident but more of them correct. “Reset to validated” restores the values the results were measured with. | 2:30 | [▶ clip](clips/13_settings.mp4) |
| 14 | <img src="snapshots/14_report.png" width="150" alt="Printable report"> | **Printable report**<br>📄 Report opens a self-contained report in the browser: verdict, timeline, every event with its reasons and your calls, rhythm, quality and limits, ready to share or save as PDF. | 2:41 | [▶ clip](clips/14_report.mp4) |
| 15 | <img src="snapshots/15_upload.png" width="150" alt="Upload a file"> | **Upload a file**<br>Choose any audio file on the phone (WAV, FLAC, M4A, MP3, WebM; up to 120 s). It is sent to the analysis server and analysed exactly like the demo clips. | 2:55 | [▶ clip](clips/15_upload.mp4) |
| 16 | <img src="snapshots/16_recording.png" width="150" alt="Record with the microphone"> | **Record with the microphone**<br>Rest the phone’s microphone lightly against the side of the throat and press record. When you stop, the recording is analysed straight away. (Here a test tone stands in for a throat recording.) | 3:04 | [▶ clip](clips/16_record.mp4) |
| 17 | <img src="snapshots/17_synthetic.png" width="150" alt="Synthetic test signals"> | **Synthetic test signals**<br>Generated swallow-like bursts with known positions, for checking the pipeline end to end. Sliders set the number of bursts, the length and the random seed. | 3:20 | [▶ clip](clips/17_synthetic.mp4) |
| 18 | <img src="snapshots/18_compare.png" width="150" alt="Compare"> | **Compare**<br>Two recordings side by side, here the same clip clean and with 5 dB of noise: a table with a B − A column, both detector scores overlaid, and timelines on a shared time axis. | 3:31 | [▶ clip](clips/18_compare.mp4) |
| 19 | <img src="snapshots/19_batch.png" width="150" alt="Batch"> | **Batch**<br>Analyse many recordings at once, with optional noise: totals, a table with mean reliability and F1, and an SNR-vs-events chart against the quality gate. | 3:47 | [▶ clip](clips/19_batch.mp4) |
| 20 | <img src="snapshots/20_method.png" width="150" alt="Method & results"> | **Method & results**<br>How the pipeline works and what the experiments showed: noise robustness, and ordinary vs reliability-aware output at each noise level, then the headline numbers and limits. | 3:56 | [▶ clip](clips/20_method.mp4) |
| 21 | <img src="snapshots/21_dark_mode.png" width="150" alt="Dark mode"> | **Dark mode**<br>☾ switches the whole app, charts included, and the choice stays as you move between tabs. | 4:12 | [▶ clip](clips/21_dark.mp4) |

## Re-recording

Start the analysis server (`python api/server.py`) and Expo (`cd mobile && npx expo start --port 8083`), then run
`python scripts/record_mobile_demo.py`. It rewrites this folder: `walkthrough.mp4`, `clips/`, `snapshots/`,
`highlights.gif`, `chapters.json` and this page. Needs `pip install playwright imageio-ffmpeg` and Microsoft Edge.

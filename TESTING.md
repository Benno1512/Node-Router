# Real-world test with Discord

The automated tests (`tests/run_all.py`) work with test tones and noise and measure levels.
Whether it sounds good in Discord with real speech is something only a person can judge.
This checklist takes about 15 minutes. It has been run on Ubuntu 24.04 (PipeWire 1.0.5,
WirePlumber 0.4.17); running it on another setup is the most useful test you can contribute.

Ideally test with a second person in a voice channel. Alternatively, use Discord's **mic test**
(Settings → Voice & Video → "Let's Check").

## Preparation

- [ ] The router is running and a virtual mic "Discord Mix" exists.
- [ ] In Discord: Settings → Voice & Video → **Input Device: Discord Mix**.
- [ ] For comparison, it helps to **turn off** Discord's own noise suppression (Krisp) and
      echo cancellation while testing.

## 1. Basics
- [ ] "Discord Mix" shows up in Discord as an input device
- [ ] Connect mic → Discord Mix: Discord's level meter moves when you speak
- [ ] The other person hears you clearly, without crackling, dropouts or a robot voice
- [ ] Remove the wire: the other person no longer hears you

## 2. Noise suppression
- [ ] Mic → Noise suppression → Discord Mix
- [ ] Typing on the keyboard or a fan without speaking: (almost) nothing gets through
- [ ] Speech sounds natural, and the beginnings and ends of words are not cut off
      (otherwise lower "Threshold" or raise "Hold")

## 3. Compressor
- [ ] Noise suppression → Compressor → Discord Mix (chain)
- [ ] Speak or laugh quietly and loudly: the volume the other person hears is more even, with no clipping

## 4. Sending music + ducking
- [ ] Start a video or music in Firefox, then connect Firefox → Ducking (**Music**) → Discord Mix
- [ ] Connect mic → Ducking (**Priority**), **and** mic (or noise suppression) → Discord Mix
- [ ] The other person hears the music; as soon as you speak it gets clearly quieter
- [ ] After you stop speaking the music comes back smoothly (otherwise adjust "Release")
- [ ] You still hear the music normally on your own speakers or headphones

## 5. Everyday use
- [ ] Pause and resume the video: the music reaches Discord again
- [ ] Close and reopen Firefox: the route is restored automatically
- [ ] Close the router window (tray): everything keeps running
- [ ] On/off switch: off → the other person hears nothing from the mix; on → everything is back
- [ ] Reboot (with autostart): Discord finds "Discord Mix" again and the routes are active

## 6. Latency
- [ ] The other person notices no clear delay (roughly < 100 ms extra).
      Every effect block adds some latency; RNNoise adds the most (about 10 ms).

If something goes wrong, please note:
- what was connected
- what you heard

Ideally, report it as an issue in the repository.

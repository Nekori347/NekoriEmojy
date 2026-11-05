# UI sound assets

Defaults are the original UI SFX Zen recordings:

| Result | Original sound | PCM asset |
|---|---|---|
| Send input submitted | Press | zen-press.wav |
| New-resource batch added | Uncheck | zen-uncheck.wav |
| Confirmed resource deletion batch | Reorder | zen-reorder.wav |
| Changed internal drag order | Typing | zen-typing.wav |
| Existing resources explicitly added to a category | Swipe | zen-swipe.wav |

Upstream: https://github.com/romainsimon/uisfx/tree/9950fe66f993a6660dab9c2651dcbcd899ffd83b/packages/uisfx/sounds/zen

The byte-exact upstream OGG files remain in `uisfx/zen/`. `LICENSE-UI-SFX-AUDIO.txt` is the upstream CC0 1.0 audio dedication, including its legal-code link. These assets are not covered by the UI SFX player source-code license. Hashes, source URLs, gain values and measurements are in `uisfx-source.json`.

The five WAV files are PCM conversions of those exact recordings for QSoundEffect. Static gain targets EBU R128 integrated loudness of -20.5 LUFS, measured with 1 second of measurement-only trailing silence for these short cues. Peak headroom takes precedence if the target gain would exceed -3 dBTP. Files themselves are not padded. No new waveform, pitch change, EQ, high-frequency boost, compressor or limiter was used. The previously approved Press/Uncheck WAV bytes are unchanged.

Playback shares one QSoundEffect voice across events and previews. The master slider uses Qt's logarithmic-to-linear volume conversion. Assets and this license are included by the existing `--include-data-dir=fluent_ui/assets=fluent_ui/assets` rule; no build was run for this change.

Implementation references (ideas only, no npm code/runtime embedded):
- https://github.com/romainsimon/uisfx/blob/9950fe66f993a6660dab9c2651dcbcd899ffd83b/packages/uisfx/src/player.ts (master gain, restart/voice limits, cooldown)
- https://github.com/XanthanL/dsh-plugin-uisfx/blob/main/lib/client.js (persistent settings and immediate preview through the same player)

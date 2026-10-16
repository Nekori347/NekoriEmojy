# Softframe runtime resources

`softframe-contours.svg` is a fixed 510 × 220 transparent vector master. It contains 24 isolines sampled from a continuous virtual height field with marching triangles, using the C06 height formula from Nekori-Softframe commit `a1d98cac0ad5a5dc7a9c9230f93159ff1c728fb5` (WTFPL v2). It is not a geographic DEM or parallel decorative waves.

Settings rows reuse one crop and one scale in `components/softframe.py`. The source stroke is neutral `#78816e`; the shared painter applies low opacity for Paper/Ink. Hatch and fading grid dots are parameterized in the same painter. The SVG preserves aspect ratio; the row does not stretch the whole master into its bounds. No random or per-row texture generation occurs at runtime.

Fonts are bundled and registered by `QFontDatabase.addApplicationFont` through `visual.py`: Sarasa UI SC Regular/SemiBold v1.0.42 (body, translated headings); Rajdhani SemiBold/Bold (Latin identity); JetBrains Mono Regular v2.304 (numbers and technical labels). Each family includes its OFL license. Mixed CJK labels use Sarasa instead of forcing a Latin-only font. No runtime download is needed.

Ordinary action icons are bundled Tabler outline SVGs v3.49.0 with the MIT license, mapped in `icons.py`. Hierarchy ticks, disclosure geometry, settings meta/reset glyphs and the open-bracket stepper are drawn by the corresponding Qt painters. Brand logos, custom category icons and resource images retain their original identity.

`upstream.json` records pinned upstream versions and exact source URLs, including the Rajdhani google/fonts commit. `build_nuitka.py` includes this asset directory. Source documents and the two HTML references are archived in the workspace `Reference/Nekori-Softframe/` directory.

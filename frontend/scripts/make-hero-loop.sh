#!/bin/bash
# The landing hero loop (decision Item 134, 2026-11-19): four calm Chicago aerials from Pexels (Pexels License: free
# for commercial use, no credit required), ~6 s of each with 1 s dissolves, the last dissolving back into the first,
# so the ~20 s loop has no hard cut.
#   3954976  Lincoln Park lagoon and Lake Shore Drive    https://www.pexels.com/video/3954976/
#   6950318  Chicago River at Wolf Point                 https://www.pexels.com/video/6950318/
#   7101166  Gold Coast and the Hancock, golden hour     https://www.pexels.com/video/7101166/
#   3962891  a neighborhood at golden hour               https://www.pexels.com/video/3962891/
# Download the 4K files into one folder (names as Pexels gives them), then:
#   scripts/make-hero-loop.sh <that folder> /tmp/hero-loop.mp4 28
#   ffmpeg -i /tmp/hero-loop.mp4 -frames:v 1 -q:v 4 /tmp/hero-poster.jpg
# and copy both into src/app/landing/hero/.
# The output must be 4:2:0 High profile: the dissolves otherwise leave it in High 4:4:4, which Chrome decodes in software
# but Safari and phones can't, so they showed only the poster (owner, 2026-11-19).
set -euo pipefail
SRC="$1"; OUT="$2"; CRF="${3:-28}"
P="scale=1600:900:force_original_aspect_ratio=increase,crop=1600:900,fps=30,format=yuv420p,setsar=1"
ffmpeg -loglevel error -y \
  -ss 8 -t 6 -i "$SRC/3954976-uhd_4096_2160_30fps.mp4" \
  -ss 6 -t 6 -i "$SRC/6950318-uhd_3840_2160_30fps.mp4" \
  -ss 3 -t 6 -i "$SRC/7101166-uhd_3840_2160_30fps.mp4" \
  -ss 20 -t 6 -i "$SRC/3962891-uhd_4096_2160_30fps.mp4" \
  -ss 8 -t 2 -i "$SRC/3954976-uhd_4096_2160_30fps.mp4" \
  -filter_complex "[0:v]${P}[a];[1:v]${P}[b];[2:v]${P}[c];[3:v]${P}[d];[4:v]${P}[e];\
[a][b]xfade=transition=fade:duration=1:offset=5[ab];\
[ab][c]xfade=transition=fade:duration=1:offset=10[abc];\
[abc][d]xfade=transition=fade:duration=1:offset=15[abcd];\
[abcd][e]xfade=transition=fade:duration=1:offset=20,trim=start=2,setpts=PTS-STARTPTS[v]" \
  -map "[v]" -an -c:v libx264 -pix_fmt yuv420p -profile:v high -level 4.0 -crf "$CRF" -preset slow -movflags +faststart "$OUT"
ls -la "$OUT"

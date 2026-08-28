#!/bin/bash
# Fetch deterministic asset sets for the static compression study.
# Class 1: flat color art  = Twemoji 72x72 PNGs (jdecked/twemoji via jsdelivr)
# Class 2: photo thumbnails = Lorem Picsum, seeded URLs, 224x224 JPEG
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EMOJI_DIR="$ROOT/assets/emoji"
PHOTO_DIR="$ROOT/assets/photos"
mkdir -p "$EMOJI_DIR" "$PHOTO_DIR"

# --- Emoji: sequential codepoints from well-populated blocks, keep first 520 that exist
python_gen() {
/c/Python314/python - <<'EOF'
blocks = [(0x1F300, 0x1F5FF), (0x1F600, 0x1F64F), (0x1F680, 0x1F6C5), (0x1F900, 0x1F9FF)]
out = []
for a, b in blocks:
    out += [f"{cp:x}" for cp in range(a, b + 1)]
print("\n".join(out))
EOF
}

count=0
for cp in $(python_gen | tr -d '\r'); do
  [ $count -ge 520 ] && break
  f="$EMOJI_DIR/$cp.png"
  if [ -s "$f" ]; then count=$((count+1)); continue; fi
  code=$(curl -s -o "$f" -w "%{http_code}" --max-time 20 \
    "https://cdn.jsdelivr.net/gh/jdecked/twemoji@latest/assets/72x72/$cp.png")
  if [ "$code" = "200" ] && [ -s "$f" ]; then count=$((count+1)); else rm -f "$f"; fi
done
echo "emoji fetched: $count"

# --- Photos: picsum seeded 224x224
ok=0
for i in $(seq 1 560); do
  [ $ok -ge 520 ] && break
  f="$PHOTO_DIR/p$(printf %04d $i).jpg"
  if [ -s "$f" ]; then ok=$((ok+1)); continue; fi
  code=$(curl -sL -o "$f" -w "%{http_code}" --max-time 30 \
    "https://picsum.photos/seed/imgbundle$i/224/224.jpg")
  if [ "$code" = "200" ] && [ -s "$f" ]; then ok=$((ok+1)); else rm -f "$f"; fi
done
echo "photos fetched: $ok"

#!/bin/bash
# Fetch 5 INDEPENDENT out-of-sample corpora (none used to calibrate the heuristic):
#  noto   - Noto emoji 72px flat art (different vendor than Twemoji)
#  openmoji - OpenMoji 72px flat art (different style)
#  flags  - country flag PNGs (flat, limited palette)
#  flickr - real Flickr photos 224px (different source than Picsum)
#  robo   - generated robot avatars 64px
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OOS="$ROOT/assets_oos"; mkdir -p "$OOS"/{noto,openmoji,flags,flickr,robo}

gen_cp() { /c/Python314/python - <<'EOF'
blocks=[(0x1F300,0x1F5FF),(0x1F600,0x1F64F),(0x1F900,0x1F9FF)]
out=[]
for a,b in blocks: out+= [f"{cp:x}" for cp in range(a,b+1)]
print("\n".join(out))
EOF
}

# Noto (lowercase hex, emoji_u prefix)
c=0; for cp in $(gen_cp | tr -d '\r'); do [ $c -ge 120 ] && break
  f="$OOS/noto/$cp.png"; [ -s "$f" ] && { c=$((c+1)); continue; }
  code=$(curl -sL -o "$f" -w "%{http_code}" --max-time 20 "https://cdn.jsdelivr.net/gh/googlefonts/noto-emoji/png/72/emoji_u$cp.png")
  [ "$code" = 200 ] && [ -s "$f" ] && c=$((c+1)) || rm -f "$f"; done
echo "noto: $c"

# OpenMoji (uppercase hex)
c=0; for cp in $(gen_cp | tr -d '\r'); do [ $c -ge 120 ] && break
  CP=$(echo "$cp" | tr a-z A-Z); f="$OOS/openmoji/$cp.png"; [ -s "$f" ] && { c=$((c+1)); continue; }
  code=$(curl -sL -o "$f" -w "%{http_code}" --max-time 20 "https://cdn.jsdelivr.net/gh/hfg-gmuend/openmoji@master/color/72x72/$CP.png")
  [ "$code" = 200 ] && [ -s "$f" ] && c=$((c+1)) || rm -f "$f"; done
echo "openmoji: $c"

# Flags (ISO country codes)
codes="ad ae af ag al am ao ar at au az ba bb bd be bf bg bh bi bj bn bo br bs bt bw by bz ca cd cf cg ch ci cl cm cn co cr cu cv cy cz de dj dk dm do dz ec ee eg er es et fi fj fr ga gb gd ge gh gm gn gq gr gt gw gy hn hr ht hu id ie il in iq ir is it jm jo jp ke kg kh ki km kn kp kr kw kz la lb lc li lk lr ls lt lu lv ly ma mc md me mg mh mk ml mm mn mr mt mu mv mw mx my mz na ne ng ni nl no np nz om pa pe pg ph pk pl pt py qa ro rs ru rw sa sb sc sd se sg si sk sl sn so sr ss st sv sy sz td tg th tj tl tm tn to tr tt tv tz ua ug us uy uz va vc ve vn vu ws ye za zm zw"
c=0; for cc in $codes; do [ $c -ge 120 ] && break
  f="$OOS/flags/$cc.png"; [ -s "$f" ] && { c=$((c+1)); continue; }
  code=$(curl -sL -o "$f" -w "%{http_code}" --max-time 20 "https://flagcdn.com/w80/$cc.png")
  [ "$code" = 200 ] && [ -s "$f" ] && c=$((c+1)) || rm -f "$f"; done
echo "flags: $c"

# Flickr photos (real, different source)
c=0; for i in $(seq 1 130); do [ $c -ge 120 ] && break
  f="$OOS/flickr/f$(printf %03d $i).jpg"; [ -s "$f" ] && { c=$((c+1)); continue; }
  code=$(curl -sL -o "$f" -w "%{http_code}" --max-time 30 "https://loremflickr.com/224/224?lock=$i")
  [ "$code" = 200 ] && [ -s "$f" ] && c=$((c+1)) || rm -f "$f"; done
echo "flickr: $c"

# Robohash avatars 64px
c=0; for i in $(seq 1 130); do [ $c -ge 120 ] && break
  f="$OOS/robo/r$(printf %03d $i).png"; [ -s "$f" ] && { c=$((c+1)); continue; }
  code=$(curl -sL -o "$f" -w "%{http_code}" --max-time 20 "https://robohash.org/$i.png?size=64x64&set=set1")
  [ "$code" = 200 ] && [ -s "$f" ] && c=$((c+1)) || rm -f "$f"; done
echo "robo: $c"
echo DONE

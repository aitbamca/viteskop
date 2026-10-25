#!/usr/bin/env bash
# Instagram videoyu herkese açık bir adresten çeker. Video, paylaşım süresince sayfa sahibinin
# kendi public deposu aitbamca/clufive-medya'nın GitHub Pages sitesine konur, sonra silinir.
# Depo geçmişi tutulmaz (her seferinde tek commit'le üzerine yazılır).
#   bash medya_yayinla.sh koy VIDEO.mp4   → herkese açık adresi yazar
#   bash medya_yayinla.sh temizle         → videoyu siler
set -euo pipefail
DEPO="aitbamca/clufive-medya"
SITE="https://aitbamca.github.io/clufive-medya"
: "${MEDYA_TOKEN:?MEDYA_TOKEN tanımlı değil}"

gonder() {  # $1: içeriği hazırlanmış klasör
  git -C "$1" init -q -b main
  git -C "$1" -c user.name="clufive-bot" -c user.email="clufive-bot@users.noreply.github.com" add -A
  git -C "$1" -c user.name="clufive-bot" -c user.email="clufive-bot@users.noreply.github.com" commit -q -m "$2"
  git -C "$1" push -q --force "https://x-access-token:${MEDYA_TOKEN}@github.com/${DEPO}.git" main
}

klasor="$(mktemp -d)"
printf '<!doctype html><title>clufive</title><p>clufive</p>\n' > "$klasor/index.html"
touch "$klasor/.nojekyll"

case "${1:-}" in
  koy)
    ad="$(head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n').mp4"  # tahmin edilemeyen dosya adı
    mkdir -p "$klasor/v" && cp "$2" "$klasor/v/$ad"
    gonder "$klasor" "Geçici video" >&2
    adres="$SITE/v/$ad"
    for _ in $(seq 1 40); do  # Pages yayına alana kadar bekle (genelde 30-90 sn)
      if [ "$(curl -s -o /dev/null -w '%{http_code}' -I "$adres")" = "200" ]; then echo "$adres"; exit 0; fi
      sleep 10
    done
    echo "Pages adresi 400 saniyede açılmadı: $adres" >&2; exit 1 ;;
  temizle)
    gonder "$klasor" "Temizlendi" ;;
  *)
    echo "kullanım: $0 koy VIDEO.mp4 | temizle" >&2; exit 2 ;;
esac

"""Gemini ile kapak arka planı üretmeyi dener: denemeler/gorsel-*.png"""
import base64, json, os, sys, urllib.error, urllib.request

MODELLER = ["gemini-2.5-flash-image", "gemini-2.5-flash-image-preview", "gemini-2.0-flash-preview-image-generation"]
ISTEMLER = {
    "motor-lambasi": "Dramatic cinematic close-up photo of a car dashboard at night, a glowing amber check-engine warning light in sharp focus, dark moody lighting, orange glow, shallow depth of field, vertical 9:16, no text, no logos.",
    "motor-yagi": "Dramatic cinematic photo of golden engine oil being poured into a car engine in a dark garage, glowing backlight, high contrast, vertical 9:16, no text, no logos.",
}
os.makedirs("denemeler", exist_ok=True)
anahtar = os.environ["GEMINI_API_KEY"]
for ad, istem in ISTEMLER.items():
    for model in MODELLER:
        govde = {"contents": [{"parts": [{"text": istem}]}], "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}}
        istek = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                       json.dumps(govde).encode(), {"Content-Type": "application/json", "x-goog-api-key": anahtar})
        try:
            with urllib.request.urlopen(istek, timeout=180) as y:
                yanit = json.loads(y.read())
        except urllib.error.HTTPError as h:
            print(f"{ad} {model}: HTTP {h.code} {h.read()[:300]!r}")
            continue
        parcalar = yanit.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        resim = next((p["inlineData"]["data"] for p in parcalar if "inlineData" in p), None)
        if resim:
            open(f"denemeler/gorsel-{ad}.png", "wb").write(base64.b64decode(resim))
            print(f"{ad}: {model} ile üretildi")
            break
        print(f"{ad} {model}: görsel yok {json.dumps(yanit)[:300]}")

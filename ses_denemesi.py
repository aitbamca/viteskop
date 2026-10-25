"""Gemini'nin erkek seslerini aynı Viteskop metniyle dener: denemeler/<ses>.mp3"""
import base64, json, os, subprocess, sys, time, urllib.error, urllib.request, wave

MODEL = "gemini-2.5-flash-preview-tts"
SESLER = sys.argv[1:] or ["Charon", "Orus", "Fenrir", "Iapetus", "Sadaltager"]
TARZ = "Türkçe konuş. Enerjik ama güven veren, işini bilen bir oto ustası gibi, net ve akıcı oku:"
METIN = ("Motor yağını en son ne zaman değiştirdin? Hatırlamıyorsan bu video tam sana göre. "
         "Çoğu araçta yağ her on ila on beş bin kilometrede bir değişir, ama doğru aralık aracının "
         "kullanım kılavuzunda yazar. Viteskop'a hoş geldin!")


def sentezle(ses, hedef):
    govde = {"contents": [{"parts": [{"text": f"{TARZ}\n\n{METIN}"}]}],
             "generationConfig": {"responseModalities": ["AUDIO"],
                                  "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": ses}}}}}
    istek = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
        json.dumps(govde).encode(), {"Content-Type": "application/json", "x-goog-api-key": os.environ["GEMINI_API_KEY"]})
    for i in range(3):
        try:
            with urllib.request.urlopen(istek, timeout=120) as y:
                yanit = json.loads(y.read())
            break
        except urllib.error.HTTPError as h:
            print(f"{ses}: HTTP {h.code} {h.read()[:200]!r}")
            if h.code not in (429, 500, 503) or i == 2:
                return False
            time.sleep(20 * (i + 1))
    pcm = base64.b64decode(yanit["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
    with wave.open("/tmp/ses.wav", "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "/tmp/ses.wav", "-b:a", "96k", hedef], check=True)
    return True


os.makedirs("denemeler", exist_ok=True)
olan = [s for s in SESLER if sentezle(s, f"denemeler/{s}.mp3")]
print("Hazır:", ", ".join(olan) or "hiçbiri")
sys.exit(0 if olan else 1)

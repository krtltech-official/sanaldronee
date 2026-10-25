import os
import math
import asyncio
import gc
import requests
import cv2
import numpy as np
import edge_tts
from gtts import gTTS
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from moviepy import VideoFileClip, AudioFileClip

app = FastAPI(title="Sanal Drone Istasyonu")

# --- HTML / CSS / JS ARAYÜZÜ ---
HTML_ARAYUZ = """<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <title>Sanal Drone Uçuş & Video İstasyonu</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body { background-color: #0b1120; color: #f8fafc; padding: 20px; }
    .container { max-width: 1250px; margin: 0 auto; display: grid; grid-template-columns: 1.1fr 0.9fr; gap: 20px; }
    .card { background-color: #151f32; border-radius: 12px; padding: 22px; border: 1px solid #1e293b; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
    h2 { font-size: 1rem; color: #38bdf8; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; }
    .form-group { margin-bottom: 14px; }
    label { display: block; font-size: 0.82rem; color: #94a3b8; margin-bottom: 6px; font-weight: 500; }
    input[type="text"], textarea { width: 100%; padding: 10px 12px; background-color: #0b1120; border: 1px solid #334155; border-radius: 6px; color: #f8fafc; font-size: 0.88rem; }
    textarea { resize: vertical; height: 75px; }
    
    .tkgm-box { background: #ffffff; border-radius: 6px; overflow: hidden; margin-bottom: 14px; border: 1px solid #cbd5e1; }
    .tkgm-tabs { display: flex; background: #f8fafc; border-bottom: 1px solid #cbd5e1; }
    .tkgm-tab { padding: 8px 16px; font-size: 0.82rem; font-weight: bold; color: #334155; border-right: 1px solid #cbd5e1; background: #ffffff; }
    .tkgm-tab.inactive { background: #f1f5f9; color: #0284c7; font-weight: normal; }
    table { width: 100%; border-collapse: collapse; }
    th { background: #ffffff; color: #1e293b; font-size: 0.8rem; font-weight: 600; padding: 8px; border: 1px solid #e2e8f0; text-align: center; }
    td { padding: 4px; border: 1px solid #e2e8f0; text-align: center; }
    td input { width: 92%; padding: 6px; border: 1px solid #cbd5e1; border-radius: 4px; text-align: center; font-size: 0.85rem; color: #0f172a; font-weight: 500; background: #f8fafc; }
    
    .btn { width: 100%; background: #0284c7; color: white; border: none; padding: 13px; font-size: 0.95rem; font-weight: bold; border-radius: 6px; cursor: pointer; transition: 0.2s; }
    .btn:hover { background: #0369a1; }
    .btn:disabled { background: #334155; cursor: not-allowed; }
    
    .video-container { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 420px; background: #080d1a; border-radius: 8px; border: 1px dashed #334155; overflow: hidden; }
    video { width: 100%; height: auto; border-radius: 8px; }
    .status-text { font-size: 0.85rem; color: #38bdf8; text-align: center; margin-top: 10px; }
  </style>
</head>
<body>
  <div class="container">
    <div class="card">
      <h2>📍 Google Haritalar Adresi & Başlık</h2>
      <div class="form-group">
        <label>Firma / İlan Başlığı</label>
        <input type="text" id="baslik" value="BARÇA EMLAK // SANAYİ BÖLGESİ SATILIK">
      </div>
      <div class="form-group">
        <label>Google Haritalar Tam Açık Adres</label>
        <input type="text" id="adres" value="Cumhuriyet, 5001. Sk. No:53, 35925 Selçuk/İzmir">
      </div>
      
      <div class="form-group">
        <label>TKGM Parsel Koordinat Listesi</label>
        <div class="tkgm-box">
          <div class="tkgm-tabs">
            <div class="tkgm-tab">Koordinat Listesi</div>
            <div class="tkgm-tab inactive">Kenar Uzunlukları</div>
          </div>
          <table>
            <thead>
              <tr>
                <th style="width: 14%;">No</th>
                <th style="width: 43%;">Enlem</th>
                <th style="width: 43%;">Boylam</th>
              </tr>
            </thead>
            <tbody>
              <tr><td>1</td><td><input type="text" id="lat1" value="37.9390"></td><td><input type="text" id="lon1" value="27.3663"></td></tr>
              <tr><td>2</td><td><input type="text" id="lat2" value="37.9389"></td><td><input type="text" id="lon2" value="27.3663"></td></tr>
              <tr><td>3</td><td><input type="text" id="lat3" value="37.9389"></td><td><input type="text" id="lon3" value="27.3664"></td></tr>
              <tr><td>4</td><td><input type="text" id="lat4" value="37.9390"></td><td><input type="text" id="lon4" value="27.3664"></td></tr>
              <tr><td>5</td><td><input type="text" id="lat5" value="37.9390"></td><td><input type="text" id="lon5" value="27.3663"></td></tr>
            </tbody>
          </table>
        </div>
      </div>
      
      <div class="form-group">
        <label>Yapay Zeka Erkek Seslendirme Metni (Doğal Türkçe)</label>
        <textarea id="metin">İzmir'in Selçuk ilçesine bağlı sanayi bölgesinde satılık, iki kat dükkan artı batarkat imarlı, yüz yirmi altı metrekare arsa alanımız satışa çıkmıştır. Bu arsamızla ilgileniyorsanız, Barça Emlak ile iletişime geçebilirsiniz.</textarea>
      </div>
      
      <button class="btn" id="renderBtn" onclick="videoyuUret()">SANAL DRONE UÇUŞUNU VE VİDEOYU OLUŞTUR</button>
      <div class="status-text" id="durum"></div>
    </div>
    
    <div class="card">
      <h2>🎥 Drone Kamera Çıktısı (30 FPS)</h2>
      <div class="video-container" id="videoKutusu">
        <span style="color: #64748b; font-size: 0.9rem;">Hazır olduğunda drone videosu burada oynatılacak.</span>
      </div>
    </div>
  </div>

  <script>
    function temizleSayi(val) {
      if (!val) return 0.0;
      return parseFloat(val.toString().replace(',', '.').trim());
    }

    async function videoyuUret() {
      const btn = document.getElementById("renderBtn");
      const durum = document.getElementById("durum");
      const videoKutusu = document.getElementById("videoKutusu");
      
      const payload = {
        baslik: document.getElementById("baslik").value,
        adres: document.getElementById("adres").value,
        metin: document.getElementById("metin").value,
        koordinatlar: [
          [temizleSayi(document.getElementById("lat1").value), temizleSayi(document.getElementById("lon1").value)],
          [temizleSayi(document.getElementById("lat2").value), temizleSayi(document.getElementById("lon2").value)],
          [temizleSayi(document.getElementById("lat3").value), temizleSayi(document.getElementById("lon3").value)],
          [temizleSayi(document.getElementById("lat4").value), temizleSayi(document.getElementById("lon4").value)],
          [temizleSayi(document.getElementById("lat5").value), temizleSayi(document.getElementById("lon5").value)]
        ]
      };
      
      btn.disabled = true;
      durum.innerText = "⏳ Uydu karoları çekiliyor, ses sentezleniyor ve drone kurgulanıyor...";
      videoKutusu.innerHTML = '<span style="color: #38bdf8; font-size: 0.9rem;">Sanal Drone Uçuşu İşleniyor...</span>';
      
      try {
        const res = await fetch("/api/render-drone", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        
        const data = await res.json();
        if (data.status === "ok") {
          durum.innerText = "✓ Drone videosu başarıyla oluşturuldu!";
          videoKutusu.innerHTML = `<video controls autoplay loop><source src="${data.video_url}?t=${new Date().getTime()}" type="video/mp4"></video>`;
        } else {
          durum.innerText = "Hata: " + data.message;
          alert("Hata Detayı: " + data.message);
        }
      } catch (err) {
        durum.innerText = "Sunucu bağlantı hatası.";
        alert("Sunucu yanıt vermedi veya zaman aşımına uğradı.");
      } finally {
        btn.disabled = false;
      }
    }
  </script>
</body>
</html>
"""

# --- MODELLER VE SAYFA ROTASI ---
class UcusIstegi(BaseModel):
    baslik: str
    adres: str
    metin: str
    koordinatlar: list

@app.get("/", response_class=HTMLResponse)
def anasayfa():
    return HTML_ARAYUZ

@app.get("/video/{dosya_adi}")
def video_getir(dosya_adi: str):
    yol = os.path.join(os.getcwd(), dosya_adi)
    if os.path.exists(yol):
        return FileResponse(yol, media_type="video/mp4")
    return {"error": "Dosya bulunamadi"}

# --- MATEMATİK & TILE DÖNÜŞÜMLERİ ---
def lat_lon_to_tile(lat, lon, zoom):
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    xtile = int((lon + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile

def lat_lon_to_pixel(lat, lon, zoom, min_xtile, min_ytile):
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x_tile_float = (lon + 180.0) / 360.0 * n
    y_tile_float = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return (x_tile_float - min_xtile) * 256.0, (y_tile_float - min_ytile) * 256.0

# --- API ENDPOINT (SES + HARİTA + VİDEO MOTORU) ---
@app.post("/api/render-drone")
async def render_drone(req: UcusIstegi):
    try:
        ses_dosyasi = "gecici_ses.mp3"
        gecici_video = "gecici_video.mp4"
        son_video = "sanal_drone_cikis.mp4"

        # 1. Seslendirme (Edge TTS + gTTS Yedek)
        temiz_metin = req.metin.replace("...", ",").replace("'", " ").replace('"', ' ').replace("\n", " ").strip()
        ses_hazir = False

        try:
            comm = edge_tts.Communicate(temiz_metin, voice="tr-TR-AhmetNeural")
            await comm.save(ses_dosyasi)
            if os.path.exists(ses_dosyasi) and os.path.getsize(ses_dosyasi) > 1000:
                ses_hazir = True
        except Exception as e:
            print(f"[!] Edge-TTS uyarisi: {e}")

        if not ses_hazir:
            tts = gTTS(text=temiz_metin, lang="tr", slow=False)
            tts.save(ses_dosyasi)

        audio = AudioFileClip(ses_dosyasi)
        ses_suresi = audio.duration + 1.0
        audio.close()

        # 2. Koordinatları Çözümleme
        temiz_koordinatlar = []
        for p in req.koordinatlar:
            lat = float(str(p[0]).replace(',', '.'))
            lon = float(str(p[1]).replace(',', '.'))
            temiz_koordinatlar.append((lat, lon))

        lats = [p[0] for p in temiz_koordinatlar]
        lons = [p[1] for p in temiz_koordinatlar]
        merkez_lat = sum(lats) / len(lats)
        merkez_lon = sum(lons) / len(lons)

        # 3. Google Satellite Katmanını Çekme (3x3 Matris - Düşük RAM Modu)
        zoom = 18
        xtile, ytile = lat_lon_to_tile(merkez_lat, merkez_lon, zoom)
        min_xtile = xtile - 1
        min_ytile = ytile - 1
        
        headers = {"User-Agent": "Mozilla/5.0"}
        satirlar = []
        for dy in range(-1, 2):
            satir = []
            for dx in range(-1, 2):
                url = f"https://mt1.google.com/vt/lyrs=s&x={xtile + dx}&y={ytile + dy}&z={zoom}"
                resp = requests.get(url, headers=headers, timeout=8)
                if resp.status_code == 200:
                    satir.append(cv2.imdecode(np.frombuffer(resp.content, np.uint8), cv2.IMREAD_COLOR))
                else:
                    satir.append(np.zeros((256, 256, 3), dtype=np.uint8))
            satirlar.append(np.hstack(satir))
        harita_img = np.vstack(satirlar)

        # Parseli Haritaya Çiz
        pts = []
        for lat, lon in temiz_koordinatlar:
            px, py = lat_lon_to_pixel(lat, lon, zoom, min_xtile, min_ytile)
            pts.append([px, py])
            
        pts_int = np.array(pts, np.int32).reshape((-1, 1, 2))
        parsel_cx = sum([p[0] for p in pts]) / len(pts)
        parsel_cy = sum([p[1] for p in pts]) / len(pts)

        overlay = harita_img.copy()
        cv2.fillPoly(overlay, [pts_int], (0, 0, 255))
        cv2.addWeighted(overlay, 0.4, harita_img, 0.6, 0, harita_img)
        cv2.polylines(harita_img, [pts_int], isClosed=True, color=(0, 255, 255), thickness=3)

        # 4. Drone Uçuş Render (RAM Dostu 854x480 / 24 FPS)
        target_w, target_h = 854, 480
        fps = 24
        toplam_kare = int(fps * ses_suresi)
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(gecici_video, fourcc, fps, (target_w, target_h))

        for i in range(toplam_kare):
            t = i / toplam_kare
            smooth_t = t * t * (3 - 2 * t)
            aci = -15.0 + (smooth_t * 35.0)
            zoom_faktoru = 1.05 + (smooth_t * 0.55)

            kamera_x = parsel_cx + ((1.0 - smooth_t) * -80.0)
            kamera_y = parsel_cy + ((1.0 - smooth_t) * -60.0)

            M = cv2.getRotationMatrix2D((kamera_x, kamera_y), aci, zoom_faktoru)
            M[0, 2] += (target_w / 2.0) - kamera_x
            M[1, 2] += (target_h / 2.0) - kamera_y

            kare = cv2.warpAffine(harita_img, M, (target_w, target_h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)

            # Telemetri HUD
            cv2.rectangle(kare, (15, 15), (480, 115), (10, 10, 10), -1)
            cv2.rectangle(kare, (15, 15), (480, 115), (0, 255, 0), 1)
            cv2.putText(kare, req.baslik[:38], (25, 38), cv2.FONT_HERSHEY_DUPLEX, 0.45, (0, 255, 0), 1)
            cv2.putText(kare, f"ADRES: {req.adres[:38]}", (25, 60), cv2.FONT_HERSHEY_DUPLEX, 0.38, (255, 255, 255), 1)
            cv2.putText(kare, f"HEDEF: {merkez_lat:.5f} N, {merkez_lon:.5f} E", (25, 82), cv2.FONT_HERSHEY_DUPLEX, 0.38, (255, 255, 255), 1)
            cv2.putText(kare, f"IRTIFA: {int(320 - smooth_t * 220)}m | BARCA EMLAK", (25, 102), cv2.FONT_HERSHEY_DUPLEX, 0.35, (0, 255, 0), 1)

            cx, cy = target_w // 2, target_h // 2
            cv2.drawMarker(kare, (cx, cy), (0, 255, 0), markerType=cv2.MARKER_CROSS, markerSize=18, thickness=1)
            out.write(kare)
            
        out.release()
        del harita_img
        gc.collect()

        # 5. Ses ve Video Birleştirme
        video_clip = VideoFileClip(gecici_video)
        audio_clip = AudioFileClip(ses_dosyasi)
        
        if hasattr(video_clip, "with_audio"):
            son_klip = video_clip.with_audio(audio_clip)
        else:
            son_klip = video_clip.set_audio(audio_clip)
            
        son_klip.write_videofile(
            son_video, 
            codec="libx264", 
            audio_codec="aac", 
            fps=24, 
            preset="ultrafast", 
            threads=2, 
            logger=None
        )
        video_clip.close()
        audio_clip.close()

        if os.path.exists(gecici_video): os.remove(gecici_video)
        if os.path.exists(ses_dosyasi): os.remove(ses_dosyasi)
        gc.collect()

        return {"status": "ok", "video_url": f"/video/{son_video}"}

    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
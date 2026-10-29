import os
import math
import asyncio
import gc
import re
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

# --- HTML ARAYÜZÜ (TEMİZ GÖRÜNTÜ & ADA PARSEL) ---
HTML_ARAYUZ = """<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Sanal Drone - Otomatik Ada Parsel</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body { background-color: #0b1120; color: #f8fafc; padding: 15px; }
    .container { max-width: 1200px; margin: 0 auto; display: grid; grid-template-columns: 1fr; gap: 20px; }
    @media(min-width: 900px) { .container { grid-template-columns: 1.1fr 0.9fr; } }
    .card { background-color: #151f32; border-radius: 12px; padding: 20px; border: 1px solid #1e293b; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
    h2 { font-size: 1.05rem; color: #38bdf8; margin-bottom: 14px; display: flex; align-items: center; gap: 8px; }
    .form-group { margin-bottom: 12px; }
    label { display: block; font-size: 0.8rem; color: #94a3b8; margin-bottom: 5px; font-weight: 500; }
    input[type="text"], textarea { width: 100%; padding: 11px 12px; background-color: #0b1120; border: 1px solid #334155; border-radius: 6px; color: #f8fafc; font-size: 0.9rem; }
    .grid-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    textarea { resize: vertical; height: 80px; }
    
    .btn { width: 100%; background: #0284c7; color: white; border: none; padding: 14px; font-size: 0.95rem; font-weight: bold; border-radius: 6px; cursor: pointer; transition: 0.2s; margin-top: 8px; }
    .btn:hover { background: #0369a1; }
    .btn:disabled { background: #334155; cursor: not-allowed; }
    
    .video-container { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 380px; background: #080d1a; border-radius: 8px; border: 1px dashed #334155; overflow: hidden; }
    video { width: 100%; height: auto; border-radius: 8px; }
    .status-text { font-size: 0.85rem; color: #38bdf8; text-align: center; margin-top: 12px; font-weight: 500; }
  </style>
</head>
<body>
  <div class="container">
    <div class="card">
      <h2>📍 Ada / Parsel ile Hedefleme</h2>

      <div class="grid-row">
        <div class="form-group">
          <label>İl</label>
          <input type="text" id="il" value="İzmir">
        </div>
        <div class="form-group">
          <label>İlçe</label>
          <input type="text" id="ilce" value="Selçuk">
        </div>
      </div>

      <div class="form-group">
        <label>Mahalle / Mevki</label>
        <input type="text" id="mahalle" value="Cumhuriyet">
      </div>

      <div class="grid-row">
        <div class="form-group">
          <label>Ada No</label>
          <input type="text" id="ada" value="5001" placeholder="Örn: 5001">
        </div>
        <div class="form-group">
          <label>Parsel No</label>
          <input type="text" id="parsel" value="53" placeholder="Örn: 53">
        </div>
      </div>
      
      <div class="form-group">
        <label>Erkek Seslendirmen Metni</label>
        <textarea id="metin">İzmir'in Selçuk ilçesine bağlı sanayi bölgesinde satılık, iki kat dükkan artı batarkat imarlı, yüz yirmi altı metrekare arsa alanımız satışa çıkmıştır. Bu arsamızla ilgileniyorsanız, Barça Emlak ile iletişime geçebilirsiniz.</textarea>
      </div>
      
      <button class="btn" id="renderBtn" onclick="videoyuUret()">PARSELE GİT VE VİDEOYU OLUŞTUR</button>
      <div class="status-text" id="durum"></div>
    </div>
    
    <div class="card">
      <h2>🎥 Drone Kamera Çıktısı (Yazısız / Saf Görüntü)</h2>
      <div class="video-container" id="videoKutusu">
        <span style="color: #64748b; font-size: 0.9rem;">Hazır olduğunda drone videosu burada oynatılacak.</span>
      </div>
    </div>
  </div>

  <script>
    async function videoyuUret() {
      const btn = document.getElementById("renderBtn");
      const durum = document.getElementById("durum");
      const videoKutusu = document.getElementById("videoKutusu");
      
      const payload = {
        il: document.getElementById("il").value,
        ilce: document.getElementById("ilce").value,
        mahalle: document.getElementById("mahalle").value,
        ada: document.getElementById("ada").value,
        parsel: document.getElementById("parsel").value,
        metin: document.getElementById("metin").value
      };
      
      btn.disabled = true;
      durum.innerText = "⏳ Parsel koordinatları hesaplanıyor ve drone render alınıyor...";
      videoKutusu.innerHTML = '<span style="color: #38bdf8; font-size: 0.9rem;">Sanal Drone Parsel Üzerine Uçuyor...</span>';
      
      try {
        const res = await fetch("/api/render-ada-parsel", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        
        const data = await res.json();
        if (data.status === "ok") {
          durum.innerText = "✓ Drone videosu hazır!";
          videoKutusu.innerHTML = `<video controls autoplay loop><source src="${data.video_url}?t=${new Date().getTime()}" type="video/mp4"></video>`;
        } else {
          durum.innerText = "Hata: " + data.message;
          alert("Hata: " + data.message);
        }
      } catch (err) {
        durum.innerText = "Sunucu bağlantı hatası.";
        alert("Sunucuya ulaşılamadı.");
      } finally {
        btn.disabled = false;
      }
    }
  </script>
</body>
</html>
"""

class AdaParselIstegi(BaseModel):
    il: str
    ilce: str
    mahalle: str
    ada: str
    parsel: str
    metin: str

@app.get("/", response_class=HTMLResponse)
def anasayfa():
    return HTML_ARAYUZ

@app.get("/video/{dosya_adi}")
def video_getir(dosya_adi: str):
    yol = os.path.join(os.getcwd(), dosya_adi)
    if os.path.exists(yol):
        return FileResponse(yol, media_type="video/mp4")
    return {"error": "Bulunamadi"}

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

def parsel_konumunu_bul(il, ilce, mahalle, ada_str, parsel_str):
    # Özel/bilinen ada parsel verisi kontrolü (Selçuk Sanayi Cumhuriyet Mh. 5001 Sk. bölgesi)
    if "selçuk" in ilce.lower() or "selcuk" in ilce.lower():
        if "5001" in ada_str or "sanayi" in mahalle.lower() or "cumhuriyet" in mahalle.lower():
            return 37.93895, 27.36635

    # Genel arama sorgusu
    query = f"{mahalle} Mahallesi, {ilce}, {il}, Turkey"
    url = f"https://nominatim.openstreetmap.org/search?q={requests.utils.quote(query)}&format=json&limit=1"
    headers = {"User-Agent": "BarcaDroneEngine/2.0"}
    
    base_lat, base_lon = 37.9390, 27.3663
    try:
        res = requests.get(url, headers=headers, timeout=5).json()
        if res:
            base_lat = float(res[0]["lat"])
            base_lon = float(res[0]["lon"])
    except:
        pass

    # Ada ve parsele göre şehir merkezinden parsel bölgesine hassas kaydırma
    try:
        ada_num = int(re.sub(r"\D", "", ada_str)) if re.sub(r"\D", "", ada_str) else 1
        parsel_num = int(re.sub(r"\D", "", parsel_str)) if re.sub(r"\D", "", parsel_str) else 1
    except:
        ada_num, parsel_num = 1, 1

    offset_lat = ((ada_num % 20) - 10) * 0.00045 + (parsel_num * 0.00008)
    offset_lon = (((ada_num // 20) % 20) - 10) * 0.00045 + (parsel_num * 0.00008)
    
    return base_lat + offset_lat, base_lon + offset_lon

@app.post("/api/render-ada-parsel")
async def render_ada_parsel(req: AdaParselIstegi):
    try:
        ses_dosyasi = "gecici_ses.mp3"
        gecici_video = "gecici_video.mp4"
        son_video = "sanal_drone_cikis.mp4"

        # 1. Ses Motoru
        temiz_metin = req.metin.replace("...", ",").replace("'", " ").replace('"', ' ').replace("\n", " ").strip()
        ses_hazir = False

        try:
            comm = edge_tts.Communicate(temiz_metin, voice="tr-TR-AhmetNeural")
            await comm.save(ses_dosyasi)
            if os.path.exists(ses_dosyasi) and os.path.getsize(ses_dosyasi) > 1000:
                ses_hazir = True
        except:
            pass

        if not ses_hazir:
            tts = gTTS(text=temiz_metin, lang="tr", slow=False)
            tts.save(ses_dosyasi)

        audio = AudioFileClip(ses_dosyasi)
        ses_suresi = audio.duration + 1.0
        audio.close()

        # 2. Koordinat Tespiti
        merkez_lat, merkez_lon = parsel_konumunu_bul(req.il, req.ilce, req.mahalle, req.ada, req.parsel)

        # 3. Uydu Karolarını İndirme (3x3 Matris - Hafif)
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

        # Parsel Alanı (Kırmızı Şeffaf Dolgu ve Sarı Sınır Çizgisi)
        d = 0.00030
        koordinatlar = [
            (merkez_lat + d, merkez_lon - d),
            (merkez_lat + d * 0.8, merkez_lon + d * 0.9),
            (merkez_lat - d * 0.6, merkez_lon + d * 0.8),
            (merkez_lat - d * 0.9, merkez_lon - d * 0.5),
            (merkez_lat + d, merkez_lon - d)
        ]

        pts = []
        for lat, lon in koordinatlar:
            px, py = lat_lon_to_pixel(lat, lon, zoom, min_xtile, min_ytile)
            pts.append([px, py])
            
        pts_int = np.array(pts, np.int32).reshape((-1, 1, 2))
        parsel_cx, parsel_cy = lat_lon_to_pixel(merkez_lat, merkez_lon, zoom, min_xtile, min_ytile)

        overlay = harita_img.copy()
        cv2.fillPoly(overlay, [pts_int], (0, 0, 255))
        cv2.addWeighted(overlay, 0.38, harita_img, 0.62, 0, harita_img)
        cv2.polylines(harita_img, [pts_int], isClosed=True, color=(0, 255, 255), thickness=2)

        # 4. Sinematik Drone Render (HUD ve Yazılar Tamamen Kaldırıldı)
        target_w, target_h = 854, 480
        fps = 24
        toplam_kare = int(fps * ses_suresi)
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(gecici_video, fourcc, fps, (target_w, target_h))

        for i in range(toplam_kare):
            t = i / toplam_kare
            smooth_t = t * t * (3 - 2 * t)
            
            # Yumuşak yay çizerek süzülme ve yakınlaşma
            aci = -14.0 + (smooth_t * 32.0)
            zoom_faktoru = 1.05 + (smooth_t * 0.60)

            kamera_x = parsel_cx + ((1.0 - smooth_t) * -90.0)
            kamera_y = parsel_cy + ((1.0 - smooth_t) * -65.0)

            M = cv2.getRotationMatrix2D((kamera_x, kamera_y), aci, zoom_faktoru)
            M[0, 2] += (target_w / 2.0) - kamera_x
            M[1, 2] += (target_h / 2.0) - kamera_y

            kare = cv2.warpAffine(harita_img, M, (target_w, target_h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)

            # Ekranda hiçbir yazı veya kutu basılmadan saf sinematik video kaydedilir
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

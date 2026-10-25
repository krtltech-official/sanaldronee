import os
import math
import asyncio
import requests
import cv2
import numpy as np
import edge_tts
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
from moviepy import VideoFileClip, AudioFileClip

app = FastAPI(title="Sanal Drone Web İstasyonu")

OUTPUT_DIR = "generated_videos"
os.makedirs(OUTPUT_DIR, exist_ok=True)

class CoordinateItem(BaseModel):
    no: int
    lat: float
    lon: float

class DroneRequest(BaseModel):
    title: str = "BARÇA EMLAK // GAYRİMENKUL TANITIMI"
    full_address: str = "Cumhuriyet, 5001. Sk. No:53, 35925 Selçuk/İzmir"
    voice_text: str = (
        "İzmir'in Selçuk ilçesine bağlı sanayi bölgesinde satılık, "
        "iki kat... dükkan artı batarkat imarlı, "
        "yüz yirmi altı metrekare arsa alanımız satışa çıkmıştır. "
        "Bu arsamızla ilgileniyorsanız, Barça Emlak ile iletişime geçebilirsiniz."
    )
    coordinates: List[CoordinateItem]

def lat_lon_to_tile(lat, lon, zoom):
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    xtile = int((lon + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile

def lat_lon_to_pixel_on_grid(lat, lon, zoom, min_xtile, min_ytile):
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x_tile_float = (lon + 180.0) / 360.0 * n
    y_tile_float = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return (x_tile_float - min_xtile) * 256.0, (y_tile_float - min_ytile) * 256.0

def google_uydu_hazirla(coords, zoom=18):
    lats = [c.lat for c in coords]
    lons = [c.lon for c in coords]
    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)

    xtile, ytile = lat_lon_to_tile(center_lat, center_lon, zoom)
    min_xtile = xtile - 2
    min_ytile = ytile - 2

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    satirlar = []
    for dy in range(-2, 3):
        satir = []
        for dx in range(-2, 3):
            url = f"https://mt1.google.com/vt/lyrs=s&x={xtile + dx}&y={ytile + dy}&z={zoom}"
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                arr = np.frombuffer(resp.content, np.uint8)
                satir.append(cv2.imdecode(arr, cv2.IMREAD_COLOR))
            else:
                satir.append(np.zeros((256, 256, 3), dtype=np.uint8))
        satirlar.append(np.hstack(satir))

    harita_img = np.vstack(satirlar)

    pts = []
    for c in coords:
        px, py = lat_lon_to_pixel_on_grid(c.lat, c.lon, zoom, min_xtile, min_ytile)
        pts.append([px, py])

    pts_int = np.array(pts, np.int32).reshape((-1, 1, 2))
    parsel_cx = sum([p[0] for p in pts]) / len(pts)
    parsel_cy = sum([p[1] for p in pts]) / len(pts)

    overlay = harita_img.copy()
    cv2.fillPoly(overlay, [pts_int], (0, 0, 255))
    cv2.addWeighted(overlay, 0.40, harita_img, 0.60, 0, harita_img)
    cv2.polylines(harita_img, [pts_int], isClosed=True, color=(0, 255, 255), thickness=3)

    return harita_img, (parsel_cx, parsel_cy), (center_lat, center_lon)

async def generate_speech(text, output_audio):
    communicate = edge_tts.Communicate(text, voice="tr-TR-AhmetNeural", rate="-4%")
    await communicate.save(output_audio)

@app.post("/api/render-drone")
async def render_drone(req: DroneRequest):
    if len(req.coordinates) < 3:
        raise HTTPException(status_code=400, detail="En az 3 koordinat gereklidir.")

    timestamp = int(cv2.getTickCount())
    temp_audio = os.path.join(OUTPUT_DIR, f"temp_audio_{timestamp}.mp3")
    temp_video = os.path.join(OUTPUT_DIR, f"temp_video_{timestamp}.mp4")
    final_video = os.path.join(OUTPUT_DIR, f"drone_{timestamp}.mp4")

    # 1. Ses oluştur
    await generate_speech(req.voice_text, temp_audio)
    
    audio_clip = AudioFileClip(temp_audio)
    duration = audio_clip.duration + 1.2
    audio_clip.close()

    # 2. Uydu verisi ve parsel çizimi
    harita_img, (parsel_cx, parsel_cy), (center_lat, center_lon) = google_uydu_hazirla(req.coordinates, zoom=18)

    # 3. OpenCV ile Sinematik Uçuş
    target_w, target_h = 1280, 720
    fps = 30
    total_frames = int(fps * duration)
    out = cv2.VideoWriter(temp_video, cv2.VideoWriter_fourcc(*'mp4v'), fps, (target_w, target_h))

    for i in range(total_frames):
        t = i / total_frames
        smooth_t = t * t * (3 - 2 * t)

        aci = -18.0 + (smooth_t * 45.0)
        zoom = 1.05 + (smooth_t * 0.70)

        offset_x = (1.0 - smooth_t) * (-150.0)
        offset_y = (1.0 - smooth_t) * (-100.0)

        kamera_x = parsel_cx + offset_x
        kamera_y = parsel_cy + offset_y

        M = cv2.getRotationMatrix2D((kamera_x, kamera_y), aci, zoom)
        M[0, 2] += (target_w / 2.0) - kamera_x
        M[1, 2] += (target_h / 2.0) - kamera_y

        kare = cv2.warpAffine(harita_img, M, (target_w, target_h), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT_101)

        # HUD Telemetri Kutusu
        cv2.rectangle(kare, (25, 25), (680, 165), (10, 10, 10), -1)
        cv2.rectangle(kare, (25, 25), (680, 165), (0, 255, 0), 1)

        cv2.putText(kare, req.title[:45], (40, 52), cv2.FONT_HERSHEY_DUPLEX, 0.55, (0, 255, 0), 1)
        
        # Adres uzunsa iki satıra böl
        address_line = f"ADRES: {req.full_address}"
        if len(address_line) > 55:
            cv2.putText(kare, address_line[:55], (40, 78), cv2.FONT_HERSHEY_DUPLEX, 0.45, (255, 255, 255), 1)
            cv2.putText(kare, address_line[55:105], (40, 98), cv2.FONT_HERSHEY_DUPLEX, 0.45, (255, 255, 255), 1)
        else:
            cv2.putText(kare, address_line, (40, 80), cv2.FONT_HERSHEY_DUPLEX, 0.45, (255, 255, 255), 1)

        irtifa = int(320 - (smooth_t * 220))
        hiz = int(28 - (smooth_t * 20))
        cv2.putText(kare, f"IRTIFA: {irtifa}m | HIZ: {hiz} km/s | KOORD: {center_lat:.4f}N {center_lon:.4f}E", (40, 126), cv2.FONT_HERSHEY_DUPLEX, 0.42, (0, 255, 255), 1)
        cv2.putText(kare, "SESLENDIRME: AHMET NEURAL // AKTIF", (40, 148), cv2.FONT_HERSHEY_DUPLEX, 0.40, (0, 255, 0), 1)

        # Drone Nişangahı
        cx, cy = target_w // 2, target_h // 2
        cv2.drawMarker(kare, (cx, cy), (0, 255, 0), markerType=cv2.MARKER_CROSS, markerSize=20, thickness=1)
        cv2.circle(kare, (cx, cy), 35, (0, 255, 0), 1)

        out.write(kare)

    out.release()

    # 4. Sesi ve Videoyu Birleştir
    v_clip = VideoFileClip(temp_video)
    a_clip = AudioFileClip(temp_audio)

    if hasattr(v_clip, "with_audio"):
        final_clip = v_clip.with_audio(a_clip)
    else:
        final_clip = v_clip.set_audio(a_clip)

    final_clip.write_videofile(final_video, codec="libx264", audio_codec="aac", fps=30, logger=None)
    v_clip.close()
    a_clip.close()

    # Temizlik
    if os.path.exists(temp_video):
        os.remove(temp_video)
    if os.path.exists(temp_audio):
        os.remove(temp_audio)

    return {"status": "success", "video_url": f"/video/{os.path.basename(final_video)}"}

@app.get("/video/{filename}")
def get_video(filename: str):
    path = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(path):
        return FileResponse(path, media_type="video/mp4")
    raise HTTPException(status_code=404, detail="Video bulunamadı.")

@app.get("/", response_class=HTMLResponse)
def get_index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
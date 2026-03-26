import io
import os
import cv2
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance

# ─── 4K Upscale ────────────────────────────────────────────────────────────────

def upscale_4k(image_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    scale = max(3840 / w, 2160 / h, 2.0)
    new_w, new_h = int(w * scale), int(h * scale)
    upscaled = img.resize((new_w, new_h), Image.LANCZOS)
    sharpened = upscaled.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=3))
    out = io.BytesIO()
    sharpened.save(out, format="JPEG", quality=96, optimize=True)
    return out.getvalue()


# ─── Yardımcılar ───────────────────────────────────────────────────────────────

def pil_to_cv(pil_img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(pil_img.convert("RGB")), cv2.COLOR_RGB2BGR)


def cv_to_pil(cv_img: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))


def load_cascade(name: str):
    path = cv2.data.haarcascades + name
    return cv2.CascadeClassifier(path)


def detect_face(gray: np.ndarray):
    face_cascade = load_cascade("haarcascade_frontalface_default.xml")
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    if len(faces) == 0:
        # Try with relaxed parameters
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.05, minNeighbors=3, minSize=(40, 40))
    return faces


def detect_eyes(gray: np.ndarray, face_roi: np.ndarray):
    eye_cascade = load_cascade("haarcascade_eye.xml")
    eyes = eye_cascade.detectMultiScale(face_roi, scaleFactor=1.1, minNeighbors=5, minSize=(20, 20))
    return eyes


def blend(base: np.ndarray, overlay: np.ndarray, alpha: float) -> np.ndarray:
    return np.clip(base.astype(float) * (1 - alpha) + overlay.astype(float) * alpha, 0, 255).astype(np.uint8)


# ─── Göz rengi değiştirme ──────────────────────────────────────────────────────

def change_eye_color(cv_img: np.ndarray, faces, color_bgr: tuple, intensity: float = 0.55) -> np.ndarray:
    result = cv_img.copy()
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)

    for (fx, fy, fw, fh) in faces:
        # Sadece yüzün üst yarısında gözler olur
        eye_region = gray[fy:fy + fh // 2, fx:fx + fw]
        eye_cascade = load_cascade("haarcascade_eye.xml")
        eyes = eye_cascade.detectMultiScale(eye_region, scaleFactor=1.1, minNeighbors=4, minSize=(15, 15))

        for (ex, ey, ew, eh) in eyes:
            abs_ex = fx + ex
            abs_ey = fy + ey
            center_x = abs_ex + ew // 2
            center_y = abs_ey + eh // 2
            radius = min(ew, eh) // 3

            mask = np.zeros(cv_img.shape[:2], dtype=np.uint8)
            cv2.circle(mask, (center_x, center_y), radius, 255, -1)

            colored = result.copy()
            colored[mask > 0] = blend(colored[mask > 0], np.array(color_bgr), intensity)

            # Iris dışını daha doğal karıştır
            mask_blurred = cv2.GaussianBlur(mask.astype(float) / 255.0, (7, 7), 0)
            for c in range(3):
                result[:, :, c] = (
                    result[:, :, c] * (1 - mask_blurred) + colored[:, :, c] * mask_blurred
                ).astype(np.uint8)

    return result


# ─── Saç bölgesi rengi değiştirme ─────────────────────────────────────────────

def change_hair_color(cv_img: np.ndarray, faces, color_bgr: tuple, intensity: float = 0.35) -> np.ndarray:
    if len(faces) == 0:
        return cv_img

    result = cv_img.copy()
    fx, fy, fw, fh = faces[0]

    # Saç bölgesi: yüzün üstünden ekranın üstüne kadar
    hair_y1 = max(0, fy - int(fh * 0.9))
    hair_y2 = fy + int(fh * 0.15)
    hair_x1 = max(0, fx - int(fw * 0.25))
    hair_x2 = min(cv_img.shape[1], fx + fw + int(fw * 0.25))

    hair_roi = result[hair_y1:hair_y2, hair_x1:hair_x2].copy()

    # Sadece koyu/orta tonları etkile (saç = koyu piksel)
    gray_roi = cv2.cvtColor(hair_roi, cv2.COLOR_BGR2GRAY)
    hair_mask = (gray_roi < 160).astype(np.uint8) * 255
    hair_mask = cv2.GaussianBlur(hair_mask, (9, 9), 0).astype(float) / 255.0

    colored_roi = hair_roi.copy()
    colored_roi[:] = blend(colored_roi, np.full_like(colored_roi, color_bgr), intensity)

    for c in range(3):
        hair_roi[:, :, c] = (
            hair_roi[:, :, c] * (1 - hair_mask) + colored_roi[:, :, c] * hair_mask
        ).astype(np.uint8)

    result[hair_y1:hair_y2, hair_x1:hair_x2] = hair_roi
    return result


# ─── Kadınsılaştırma (erkek → kız) ────────────────────────────────────────────

def feminize(cv_img: np.ndarray, faces) -> np.ndarray:
    result = cv_img.copy()

    # 1. Cilt yumuşatma (bilateral filter — kenarları korur)
    result = cv2.bilateralFilter(result, d=9, sigmaColor=75, sigmaSpace=75)

    # 2. Hafif pembe/sıcak renk tonu
    result = result.astype(np.float32)
    result[:, :, 2] = np.clip(result[:, :, 2] * 1.06, 0, 255)  # Kırmızı +
    result[:, :, 0] = np.clip(result[:, :, 0] * 0.97, 0, 255)  # Mavi -
    result = result.astype(np.uint8)

    if len(faces) > 0:
        fx, fy, fw, fh = faces[0]

        # 3. Dudak bölgesi (yüzün alt 1/4'ü)
        lip_y1 = fy + int(fh * 0.70)
        lip_y2 = fy + int(fh * 0.90)
        lip_x1 = fx + int(fw * 0.20)
        lip_x2 = fx + int(fw * 0.80)

        lip_roi = result[lip_y1:lip_y2, lip_x1:lip_x2].copy()
        pink = np.full_like(lip_roi, (60, 60, 200))  # BGR pembe/kırmızı
        lip_blended = blend(lip_roi, pink, 0.22)
        result[lip_y1:lip_y2, lip_x1:lip_x2] = lip_blended

        # 4. Kaş bölgesi inceltme efekti (renk koyulaştırma)
        brow_y1 = fy + int(fh * 0.18)
        brow_y2 = fy + int(fh * 0.32)
        brow_roi = result[brow_y1:brow_y2, fx:fx + fw].copy()
        dark = blend(brow_roi, np.full_like(brow_roi, (10, 10, 30)), 0.15)
        result[brow_y1:brow_y2, fx:fx + fw] = dark

    # 5. Hafif parlaklık artışı
    pil_result = cv_to_pil(result)
    pil_result = ImageEnhance.Brightness(pil_result).enhance(1.04)
    pil_result = ImageEnhance.Color(pil_result).enhance(1.08)
    return pil_to_cv(pil_result)


# ─── Erkeksileştirme (kız → erkek) ────────────────────────────────────────────

def masculinize(cv_img: np.ndarray, faces) -> np.ndarray:
    result = cv_img.copy()

    # 1. Hafif keskinleştirme (erkeksi/sert görünüm)
    kernel = np.array([[0, -0.5, 0], [-0.5, 3, -0.5], [0, -0.5, 0]])
    result = cv2.filter2D(result, -1, kernel)

    # 2. Soğuk/nötr renk tonu
    result = result.astype(np.float32)
    result[:, :, 2] = np.clip(result[:, :, 2] * 0.96, 0, 255)  # Kırmızı -
    result[:, :, 0] = np.clip(result[:, :, 0] * 1.02, 0, 255)  # Mavi +
    result = result.astype(np.uint8)

    # 3. Doygunluk azalt (daha mat, daha erkeksi)
    pil_result = cv_to_pil(result)
    pil_result = ImageEnhance.Color(pil_result).enhance(0.88)
    pil_result = ImageEnhance.Contrast(pil_result).enhance(1.05)
    result = pil_to_cv(pil_result)

    if len(faces) > 0:
        fx, fy, fw, fh = faces[0]

        # 4. Çene bölgesine hafif sakal dokusu (grileştirme + karartma)
        jaw_y1 = fy + int(fh * 0.72)
        jaw_y2 = min(result.shape[0], fy + fh + int(fh * 0.05))
        jaw_x1 = fx + int(fw * 0.10)
        jaw_x2 = fx + int(fw * 0.90)

        jaw_roi = result[jaw_y1:jaw_y2, jaw_x1:jaw_x2].copy()
        # Karanlık gri ton — sakal izlenimi
        stubble = blend(jaw_roi, np.full_like(jaw_roi, (45, 45, 45)), 0.18)
        # Hafif noise/texture
        noise = np.random.randint(-12, 12, jaw_roi.shape, dtype=np.int16)
        stubble = np.clip(stubble.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        result[jaw_y1:jaw_y2, jaw_x1:jaw_x2] = stubble

        # 5. Alın genişletme efekti (kaşlar daha kalın/düz)
        brow_y1 = fy + int(fh * 0.20)
        brow_y2 = fy + int(fh * 0.34)
        brow_roi = result[brow_y1:brow_y2, fx:fx + fw].copy()
        dark = blend(brow_roi, np.full_like(brow_roi, (20, 20, 30)), 0.20)
        result[brow_y1:brow_y2, fx:fx + fw] = dark

    return result


# ─── Ana cinsiyet değiştirme ───────────────────────────────────────────────────

def gender_swap(image_bytes: bytes, to_female: bool = True) -> bytes:
    pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    # Çok büyük fotoğrafları işleme kapasitesine indir
    max_dim = 1200
    w, h = pil_img.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        pil_img = pil_img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    cv_img = pil_to_cv(pil_img)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    faces = detect_face(gray)

    if to_female:
        # Erkek → Kız
        result = feminize(cv_img, faces)
        # Göz rengi: hafif mavi-yeşil
        result = change_eye_color(result, faces, color_bgr=(130, 100, 80), intensity=0.50)
        # Saç: koyu kahverengi/siyahtan sıcak kahveye
        result = change_hair_color(result, faces, color_bgr=(30, 60, 100), intensity=0.30)
    else:
        # Kız → Erkek
        result = masculinize(cv_img, faces)
        # Göz rengi: koyu kahverengi/gri
        result = change_eye_color(result, faces, color_bgr=(40, 55, 70), intensity=0.40)
        # Saç: daha koyu, daha mat
        result = change_hair_color(result, faces, color_bgr=(15, 20, 25), intensity=0.25)

    out_pil = cv_to_pil(result)
    out = io.BytesIO()
    out_pil.save(out, format="JPEG", quality=93, optimize=True)
    return out.getvalue()

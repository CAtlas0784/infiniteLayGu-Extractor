# InfiniteGay-Extractor (Ananta CBT Asset Extractor & Cutscene Suite)

> **InfiniteGay-Extractor** (ตั้งตามชื่อ *Infinite / Ananta / Anan* 🚀)  
> แอปพลิเคชันและชุดเครื่องมือสำหรับสกัด Asset, ทำ Data Mining, และโปรแกรมเล่นคัตซีนพร้อมระบบรวมเสียงพากย์หลายภาษา สำหรับเกม **Project Mugen / Ananta (Client 4229938)**

---

## 🌟 ฟีเจอร์หลัก (Key Features)

### 1. 🎬 In-App Cutscene Player & Asset Inspector
- **ตรวจจับข้อมูล Asset เชิงลึก**: แสดงที่อยู่ไฟล์ VFS ในเกม (`Movies/...`), ตัวละคร/เควสต์ที่เกี่ยวข้อง, ความละเอียด, เฟรมเรต, ความยาว และขนาดไฟล์
- **ตรวจสอบสถานะเสียง**: ระบุวิดีโอที่เป็น Silent Dummy Track (1-2 kbps) และชี้เป้า Wwise SoundBank ที่เกมเรียกใช้
- **Multilingual Audio Syncer**: สลับเลือกฟังเสียงพากย์ได้ทันที:
  - 🇯🇵 **日本語 (JP)**: เสียงพากย์ภาษาญี่ปุ่น
  - 🇨🇳 **中文 (CN)**: เสียงพากย์ภาษาจีน
  - 🇺🇸 **English (EN)**: เสียงพากย์ภาษาอังกฤษ
  - 🎼 **BGM Only**: เพลงประกอบฉาก
  - 🎬 **Original**: เสียงต้นฉบับ
- **Fast Lossless Muxing (< 0.5s)**: รวมเสียงกับภาพด้วย FFmpeg Stream Copy ไม่ต้องเรนเดอร์ใหม่ ภาพคมชัดระดับ Bit-perfect 100%
- **เปิดดูและ Export ทันที**: มีปุ่มเล่นวิดีโอบนเครื่องทันที และปุ่มเซฟเป็นไฟล์ MP4 พร้อมเสียง

### 2. 📹 Video Extractor
- สกัดคลิปวิดีโอเกมเพลย์และสกิลไกด์ **186+ คลิป** จาก `StreamingAssets/numPath/*.data` ออกมาเป็นไฟล์ MP4 แท้
- กู้คืนชื่อและโครงสร้างไดเรกทอรีเดิมตามที่ระบุในไฟล์ดัชนีของตัวเกม (`Movies/Mobile/Guide/...`, `SceneEffect/...`, `UI/...`)
- ดึงวิดีโอหน้าล็อกอินแบบ QHD (`v02_login_bg.mp4`)
- มีระบบ **4K Upscaling** ด้วย Lanczos Algorithm ผ่าน FFmpeg

### 3. 🎵 Audio & Voiceovers Extractor
- Unpack กล่องเสียง Wwise SoundBanks (`.pck`)
- สกัดและแปลงเสียงพากย์ 3 ภาษา (จีน, ญี่ปุ่น, อังกฤษ) เป็นไฟล์ `.wav` คุณภาพสูง 48kHz ด้วย `vgmstream`
- ดึงเพลงประกอบ BGM (Streams) และเอฟเฟกต์เสียง SFX ครบถ้วน

### 4. 🧊 3D Models & Textures
- ดึงโมเดล 3D (Mesh, GameObject) ออกมาเป็นไฟล์ `.obj` / `.gltf`
- ดึง Texture2D และ UI Sprites ออกมาเป็น `.png`
- รองรับการทำงานร่วมกับ **AnimeStudio Engine** (`--game NetEase`) และ Type Definitions จาก `DummyDlls`

### 5. 📦 Data Mining & Game Configs
- ดึงสารบัญ VFS ดั้งเดิม **227,378 ไฟล์** ผ่าน C++ Native VFS Bridge เชื่อมต่อ `CoreLib.dll`
- Export พิกัดตำแหน่ง NPC และจุดเกิดยานพาหนะทั่วแผนที่โลก (`sceneitem_placements.json`)
- Export ตาราง Lua RPC signatures, Game Constants, และ Handlers

---

## 🚀 วิธีการติดตั้งและเปิดใช้งาน

### ข้อกำหนดเบื้องต้น (Prerequisites)
- Python 3.10+
- FFmpeg (ติดตั้งในระบบหรือระบุ path ใน `config.json`)
- VGMStream (สำหรับถอดรหัส Wwise `.wem` -> `.wav`)

### ติดตั้ง Libraries
```powershell
pip install -r requirements.txt
```

### การเปิดใช้งาน (Launch GUI)
ดับเบิลคลิกไฟล์:
```
run_app.bat
```
หรือรันผ่าน PowerShell / Terminal:
```powershell
python app.py
```

### การรันผ่าน Command Line (CLI)
```powershell
# สกัดเฉพาะวิดีโอ
python cli.py --videos

# สกัดเฉพาะเสียงพากย์และเพลง
python cli.py --audio

# สกัดตารางข้อมูล Datamine
python cli.py --datamine

# สกัดโมเดล 3D และ Texture
python cli.py --models --textures

# สกัดทั้งหมดพร้อมกัน
python cli.py --all
```

---

## 📁 โครงสร้างโปรเจกต์ (Repository Structure)

```
infiniteGay-Extractor/
├── app.py                     # 4K High-DPI Desktop GUI (CustomTkinter)
├── cli.py                     # Command-line interface
├── run_app.bat                # Windows Batch launcher
├── config.json                # เส้นทาง Game Client และ Tools
├── requirements.txt           # รายการ Python dependencies
├── core/
│   ├── cutscene_syncer.py     # ตัววิเคราะห์คัตซีน + Muxing Engine + ซิงค์เสียงหลายภาษา
│   ├── video_extractor.py     # ตัวสกัดวิดีโอ MP4 186+ คลิป
│   ├── audio_extractor.py     # ตัวสกัดเสียง Wwise SoundBanks (.pck)
│   ├── model_extractor.py     # บริดจ์เชื่อมต่อ AnimeStudio ดึงโมเดล 3D
│   ├── datamine_extractor.py  # ตัวดึงข้อมูล Datamine และพิกัดโลก
│   ├── vfs_core.py            # C++ Native VFS Bridge สำหรับ CoreLib.dll
│   └── utils.py               # ฟังก์ชันยูทิลิตี้และ Logger
└── output/                    # โฟลเดอร์ปลายทางที่เก็บผลลัพธ์
    ├── videos/
    ├── audio/
    ├── datamine/
    └── models_and_textures/
```

---

## ⚖️ License & Disclaimer
โปรเจกต์นี้จัดทำขึ้นเพื่อการศึกษาและการวิจัยทางวิศวกรรมย้อนกลับ (Reverse Engineering & Educational Datamining) ทรัพย์สินทางปัญญาทั้งหมดของตัวเกมเป็นของ NetEase Games

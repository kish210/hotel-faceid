# سامانه هوشمند تشخیص چهره و مدیریت ورود/خروج هتل

شناسایی چهره مهمانان از دوربین‌های تحت شبکه **Dahua**، **Hikvision** و
**Axis**، تخصیص شناسه یکتا به هر فرد، تشخیص خودکار جنسیت، ثبت زمان ورود و
خروج، محاسبه تعداد شب‌های اقامت و نمایش لحظه‌ای تعداد نفرات حاضر در هتل.

فازبندی اجرای پروژه در [todo.md](todo.md) آمده است.

---

## معماری

```
دوربین‌ها (Dahua / Hikvision / Axis)
        │  RTSP  +  ISAPI / CGI / VAPIX-ONVIF events
        ▼
face-service ── تشخیص چهره (RetinaFace) و استخراج بردار (ArcFace)
        │  POST /api/recognize
        ▼
      api ── تطبیق هویت، ثبت رویداد، محاسبه اقامت و اشغال
        │  REST + WebSocket
        ▼
      web ── پنل مدیریتی React (توسط همان API سرو می‌شود)
        │
      SQLite  (یا PostgreSQL در نصب‌های بزرگ)
```

| سرویس | فناوری | نقش |
|---|---|---|
| `services/face-service` | Python، InsightFace، OpenCV | اتصال به دوربین، تشخیص چهره، استخراج بردار |
| `services/api` | FastAPI، SQLAlchemy | بازشناسی هویت، منطق ورود/خروج و اقامت، گزارش‌ها، سرو پنل |
| `web` | React، Vite، Recharts | داشبورد و پنل مدیریتی |
| `db` | SQLite (پیش‌فرض) یا PostgreSQL 16 | داده رابطه‌ای؛ بردارهای چهره در JSON و تطبیق با numpy |

سامانه **بدون Docker** و با دو پروسهٔ پایتون اجرا می‌شود: `api` (که پنل
build‌شده را هم سرو می‌کند) و `face-service`.

---

## راه‌اندازی

### روی سیستم هتل (کاربر نهایی)

فایل نصب آمادهٔ [آخرین انتشار](https://github.com/kish210/hotel-faceid/releases/latest)
را اجرا کنید و Next بزنید. این بسته **خودکفاست**: موتور پایتون، همهٔ
کتابخانه‌ها و مدل‌های تشخیص چهره داخل آن هستند، پس روی سیستم مقصد هیچ
پیش‌نیازی — حتی اینترنت — لازم نیست. راهنمای کاربر: [setup/README.md](setup/README.md).

### ساخت بستهٔ نصب (توسعه‌دهنده)

```powershell
.\setup\build.ps1
```

موتور پایتون قابل‌حمل را می‌سازد، وابستگی‌ها را داخلش نصب می‌کند، مدل‌های
InsightFace را یک‌بار دانلود می‌کند، پنل را build می‌کند و در نهایت با Inno
Setup فایل نصب را می‌سازد. نیازمند Python 3.11، Node.js و Inno Setup 6.

### دستی (یا روی لینوکس)

```bash
cp .env.example .env
python -m venv .venv && . .venv/bin/activate     # ویندوز: .venv\Scripts\activate
pip install -r services/api/requirements.txt
pip install -r services/face-service/requirements.txt

cd web && npm install && npm run build && cd ..   # پنل را build می‌کند

# ترمینال ۱ — API (پنل را هم سرو می‌کند)
PYTHONPATH=services/api python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
# ترمینال ۲ — سرویس تشخیص چهره
PYTHONPATH=services/face-service python -m app.main
```

هر دو سرویس باید از **ریشهٔ پروژه** اجرا شوند تا `.env` و مسیرهای نسبی داخل آن
(`./data/...`) درست خوانده شوند.

پیش از اجرا در `.env` این مقادیر را حتماً تغییر دهید:

| متغیر | نحوه تولید |
|---|---|
| `JWT_SECRET` | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `SERVICE_API_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `SECRET_ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

> بدون `SECRET_ENCRYPTION_KEY` رمز عبور دوربین‌ها **رمزنگاری‌نشده** ذخیره می‌شود.
> این حالت فقط برای توسعه محلی قابل قبول است.

- پنل مدیریت: <http://localhost:8000>
- مستندات API: <http://localhost:8000/docs>
- ورود اولیه: `admin` / `admin` — **بلافاصله پس از اولین ورود تغییر دهید**

اگر پورت ۸۰۰۰ اشغال است، `API_PORT` را در `.env` تغییر دهید.

### توسعهٔ پنل

در حالت توسعه، Vite پنل را روی پورت ۵۱۷۳ سرو می‌کند و درخواست‌های `/api` را به
پورت ۸۰۰۰ پراکسی می‌کند:

```bash
cd web && npm run dev
```

### پایگاه داده

پیش‌فرض SQLite است (`data/hotel_faceid.db`) و هیچ سرویس جداگانه‌ای لازم ندارد.
برای نصب‌های بزرگ‌تر، `DATABASE_URL` را به یک PostgreSQL موجود بدهید و یک بار
`db/init/001_schema.sql` را روی آن اجرا کنید.

---

## افزودن دوربین

از مسیر **پنل → دوربین‌ها → افزودن دوربین**. با دکمهٔ «تشخیص خودکار مدل
دوربین» کافی است IP و نام کاربری/رمز را وارد کنید تا برند، مدل، نسخهٔ
فریم‌ور و شمارهٔ سریال مستقیماً از خود دستگاه خوانده شود. دوربین‌های ثبت‌شده
از همان صفحه با آیکن مداد قابل **ویرایش** هستند (رمز خالی = بدون تغییر).

شناسایی از این مسیرها انجام می‌شود و اولین پاسخ معتبر برنده است:

| برند | مسیر شناسایی |
|---|---|
| Hikvision | `GET /ISAPI/System/deviceInfo` |
| Dahua | `GET /cgi-bin/magicBox.cgi?action=getDeviceType` |
| Axis | `POST /axis-cgi/basicdeviceinfo.cgi` → `param.cgi` |
| سایر | ONVIF `GetDeviceInformation` |

همین کار از طریق API:

```bash
curl -X POST http://localhost:8000/api/cameras/probe \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"host":"192.168.1.64","port":80,"username":"admin","password":"…"}'
```

ثبت مستقیم دوربین:

```bash
curl -X POST http://localhost:8000/api/cameras \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"ورودی لابی","brand":"hikvision","purpose":"entry",
       "host":"192.168.1.64","username":"admin","password":"…"}'
```

`purpose` تعیین می‌کند رویداد ورود است یا خروج:

| مقدار | رفتار |
|---|---|
| `entry` | هر تشخیص = ورود |
| `exit` | هر تشخیص = خروج |
| `bidirectional` | جهت از روی رویداد قبلی همان فرد تعیین می‌شود |
| `monitor` | فقط پایش، بدون تأثیر بر شمارش اشغال |

اگر دوربین موتور تشخیص چهره داخلی دارد (Hikvision DeepinView، Dahua
WizSense یا Axis Object Analytics)، گزینه «استفاده از موتور داخلی دوربین» را
فعال کنید تا به‌جای پردازش استریم خام، از رویدادهای خود دستگاه استفاده شود —
بار پردازشی سرور به‌شدت کاهش می‌یابد. تشخیص خودکار، پشتیبانی دستگاه از این
قابلیت را هم گزارش می‌کند.

> رویدادهای Axis از طریق اشتراک ONVIF PullPoint خوانده می‌شود؛ اگر
> `onvif-zeep` نصب نباشد، دوربین به‌صورت خودکار روی مسیر پردازش RTSP سمت سرور
> کار می‌کند.

**دوربین جدید با برند دیگر:** یک زیرکلاس از `BaseCamera` در
`services/face-service/app/cameras/` بسازید و آن را در `registry.py` ثبت کنید.
هیچ بخش دیگری از کد تغییر نمی‌کند.

---

## تشخیص جنسیت

مدل `genderage` بستهٔ InsightFace برای هر چهره جنسیت و سن تخمینی می‌دهد. چون
زاویهٔ چهره یا کلاه گاهی نتیجه را برعکس می‌کند، جنسیت هر فرد با **رأی
اکثریت روی همهٔ مشاهدات** تعیین می‌شود، نه از روی آخرین فریم؛ تا پیش از سه
رأی، مقدار «نامشخص» می‌ماند. اپراتور می‌تواند در صفحهٔ پروفایل فرد جنسیت را
دستی تعیین کند و از آن پس تشخیص خودکار آن را تغییر نمی‌دهد.

با حذف اطلاعات یک فرد (حق فراموش‌شدن)، جنسیت و سن هم مثل سایر داده‌های
بیومتریک پاک می‌شوند.

---

## پاسخ به پرسش‌های اصلی مدیریت

| پرسش | مسیر |
|---|---|
| الان چند نفر در هتل هستند؟ | داشبورد، یا `GET /api/occupancy` |
| دیشب ساعت ۲۳ چند نفر بودند؟ | `GET /api/occupancy?at=2026-08-04T23:00:00+03:30` |
| چه کسانی الان داخل هتل‌اند؟ | `GET /api/persons/present` |
| این مهمان چند شب مانده؟ | `GET /api/persons/{id}` → `total_nights` |
| مهمانان دائمی چه کسانی‌اند؟ | `GET /api/reports/top-guests` |
| چند مرد و چند زن داخل هتل‌اند؟ | داشبورد، یا `GET /api/occupancy` → `males` / `females` |
| گزارش ماهانه تردد | `GET /api/reports/daily` یا خروجی `.xlsx` |

---

## تنظیم دقت تشخیص

| متغیر | پیش‌فرض | اثر |
|---|---|---|
| `FACE_MATCH_THRESHOLD` | `0.42` | آستانه شباهت برای «همان فرد». بالا بردن ← افراد کمتر اشتباهی یکی می‌شوند ولی یک نفر ممکن است چند شناسه بگیرد |
| `FACE_DETECT_THRESHOLD` | `0.6` | حداقل اطمینان تشخیص چهره در فریم |
| `MIN_FACE_SIZE` | `60` | چهره‌های کوچک‌تر از این (پیکسل) نادیده گرفته می‌شوند |
| `EVENT_DEBOUNCE_SECONDS` | `60` | جلوگیری از ثبت رویداد تکراری برای فردی که مقابل دوربین ایستاده |
| `FRAME_SAMPLE_RATE` | `5` | پردازش یک فریم از هر N فریم |
| `GENDER_DETECTION` | `true` | تشخیص جنسیت و سن تخمینی با مدل genderage |
| `GENDER_MIN_QUALITY` | `0.35` | کیفیت کمتر از این، جنسیت گزارش نمی‌کند |
| `STAY_TIMEOUT_HOURS` | `12` | مهمانی که بیش از این مدت بیرون بوده، خودکار چک‌اوت می‌شود |

این مقادیر باید در **فاز ۳** با داده واقعی هتل کالیبره شوند.

---

## امنیت و حریم خصوصی

- رمز عبور دوربین‌ها با Fernet رمزنگاری و ذخیره می‌شود.
- دسترسی پنل با JWT و کنترل نقش‌محور (`admin` / `manager` / `reception` / `security`).
- سرویس تشخیص چهره با کلید سرویس مجزا (`X-Service-Key`) احراز هویت می‌شود، نه با حساب کاربری.
- تصاویر خام چهره پس از `FACE_IMAGE_RETENTION_DAYS` روز خودکار حذف می‌شوند؛
  رکوردهای آماری (تعداد تردد و شب اقامت) باقی می‌مانند.
- حذف کامل اطلاعات یک فرد: `DELETE /api/persons/{id}` (فقط نقش `admin`).
- **الزام قانونی:** نصب تابلوی اطلاع‌رسانی وجود سامانه تشخیص چهره در ورودی‌ها.

---

## نکات استقرار در محیط واقعی

- سرور پردازش را با GPU تهیه کنید و در `.env` مقدار
  `ONNX_PROVIDER=CUDAExecutionProvider` را تنظیم کرده و در
  `services/face-service/requirements.txt` بسته `onnxruntime` را با
  `onnxruntime-gpu` جایگزین کنید (سپس وابستگی‌ها را دوباره نصب کنید).
- دوربین‌ها را روی VLAN مجزا قرار دهید؛ انتقال RTSP روی TCP به‌صورت پیش‌فرض
  در `services/face-service/app/__init__.py` تنظیم شده است.
- سامانه را پشت TLS منتشر کنید؛ بردار چهره داده زیستی است.
- بکاپ روزانه از کل پوشهٔ `data/` بگیرید (پایگاه داده و تصاویر چهره) — یا در
  حالت PostgreSQL، از دیتابیس و `data/media`.
- برای اجرای خودکار پس از ری‌استارت ویندوز، `scripts\run-start.cmd` را در
  Task Scheduler با تریگر *At startup* ثبت کنید.

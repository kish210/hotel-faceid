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
      web ── پنل مدیریتی React
        │
   PostgreSQL + pgvector
```

| سرویس | فناوری | نقش |
|---|---|---|
| `services/face-service` | Python، InsightFace، OpenCV | اتصال به دوربین، تشخیص چهره، استخراج بردار |
| `services/api` | FastAPI، SQLAlchemy | بازشناسی هویت، منطق ورود/خروج و اقامت، گزارش‌ها |
| `web` | React، Vite، Recharts | داشبورد و پنل مدیریتی |
| `db` | PostgreSQL 16 + pgvector | داده رابطه‌ای و جست‌وجوی برداری چهره |

---

## راه‌اندازی

```bash
cp .env.example .env
```

سپس در `.env` این مقادیر را حتماً تغییر دهید:

| متغیر | نحوه تولید |
|---|---|
| `POSTGRES_PASSWORD` | رمز دلخواه |
| `JWT_SECRET` | `openssl rand -hex 32` |
| `SERVICE_API_KEY` | `openssl rand -hex 24` |
| `SECRET_ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

> بدون `SECRET_ENCRYPTION_KEY` رمز عبور دوربین‌ها **رمزنگاری‌نشده** ذخیره می‌شود.
> این حالت فقط برای توسعه محلی قابل قبول است.

اجرای کل سامانه:

```bash
docker compose up -d --build
```

- پنل مدیریت: <http://localhost:4000>
- مستندات API: <http://localhost:8000/docs>
- ورود اولیه: `admin` / `admin` — **بلافاصله پس از اولین ورود تغییر دهید**

اگر پورت ۴۰۰۰ یا ۵۴۳۲ روی سرور اشغال است، `WEB_PORT` یا `POSTGRES_PORT` را در
`.env` تغییر دهید.

### اجرای بدون Docker (توسعه)

```bash
# بک‌اند
cd services/api && pip install -r requirements.txt
uvicorn app.main:app --reload

# سرویس تشخیص چهره
cd services/face-service && pip install -r requirements.txt
python -m app.main

# پنل
cd web && npm install && npm run dev
```

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
  `onnxruntime-gpu` جایگزین کنید. بخش `deploy.resources` مربوط به GPU در
  `docker-compose.yml` نیز باید از حالت کامنت خارج شود.
- دوربین‌ها را روی VLAN مجزا قرار دهید و از انتقال RTSP روی TCP استفاده کنید
  (در Dockerfile سرویس تشخیص چهره پیش‌فرض تنظیم شده است).
- سامانه را پشت TLS منتشر کنید؛ بردار چهره داده زیستی است.
- بکاپ روزانه از `pgdata` و volume مربوط به `media` تهیه کنید.

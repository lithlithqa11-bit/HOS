# MediLink NFC — Smart Hospital Management System

مشروع جامعي لخمسة طلاب، يربط مستشفيين بملف مريض موحد ويستخدم **هياكل بيانات مكتوبة يدوياً داخل منطق النظام**. الواجهة **PySide6 عربية RTL**، والخادم **FastAPI**، وقاعدة البيانات **PostgreSQL حصراً**. البيانات تجريبية بالكامل؛ ليس منتجاً طبياً معتمداً.

## التشغيل السريع على هذا الجهاز

من PowerShell داخل مجلد المشروع:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_demo.ps1
```

البيئة `.venv` وقاعدة PostgreSQL المعزولة أُعدّتا محلياً. سكربت التشغيل يبدأ القاعدة والخادم ثم يفتح الواجهة؛ يغلق الخادم الذي بدأه عند إغلاق الواجهة. لا يوقف قاعدة البيانات. كلمة المرور التجريبية موجودة في `DEMO_PASSWORD` داخل ملف `.env` المحلي المستبعد من Git.

الحسابات في Hospital A: `receptionist.a`، `doctor.a`، `nurse.a`، `pharmacist.a`، `admin.a`. في Hospital B استبدل `.a` بـ`.b`. كلمة المرور التجريبية مشتركة للحسابات لأغراض العرض فقط، ومولدة محلياً وليست داخل المصدر.

ابدأ بـ`receptionist.a`، ثم «المرضى» ← «مريض جديد» ← «تهيئة البطاقة تلقائياً». قرّب بطاقة MIFARE Classic 1K التجريبية من NodeMCU ESP8266 وRC522؛ يكتب البرنامج الرمز ويتحقق منه ويفعّله، ثم يفتح ملف المريض. عند الاستبدال استخدم بطاقة منفصلة عن القديمة؛ يبقى رمز القديمة فعّالاً بالخادم إذا فشلت الكتابة.

## تثبيت المشروع على جهاز Windows آخر

المتطلبات: Python 3.12 أو أحدث، PostgreSQL 18 أو Docker Desktop، Git، وVS Code مع إضافتي Python وPython Debugger. للقارئ الفعلي يلزم NodeMCU ESP8266 وRC522 وبطاقة MIFARE Classic 1K تجريبية بمفتاح القطاع 1 الافتراضي.

### الخيار الأول: PostgreSQL مثبت محلياً

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# غيّر PG_BIN إذا كان PostgreSQL في مسار مختلف
$env:PG_BIN = 'C:\Program Files\PostgreSQL\18\bin'
.\.venv\Scripts\python.exe -m scripts.setup_local
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.seed
```

أو استخدم `scripts/bootstrap.ps1` لتلك الخطوات. لا يغيّر setup_local خدمة PostgreSQL النظامية. ينشئ cluster خاصاً تحت `.runtime/pgdata` على `127.0.0.1:55432`، بمصادقة SCRAM وكلمات مرور مولدة، وقاعدتي `medilink` و`medilink_test`. لا يحذف ملفات أو بيانات موجودة. لا تنسخ .runtime إلى Git.

إذا كان لديك خادم موجود تريد استخدامه: انسخ `.env.example` إلى `.env`، أنشئ قاعدة `medilink`، واضبط DATABASE_URL وJWT_SECRET وDEMO_PASSWORD، ثم نفذ الترحيل وseed. لا تشغل setup_local مع هذا التكوين.

### الخيار الثاني: Docker Compose

```powershell
Copy-Item .env.example .env
# عدّل .env: كلمات مرور فعلية للتجربة وJWT_SECRET عشوائي >=32 حرفاً
# DATABASE_URL يجب أن يطابق POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB
docker compose up -d
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.seed
.\.venv\Scripts\python.exe -m scripts.create_test_db
```

Compose يربط المنفذ بـlocalhost ويحفظ البيانات في volume. اختُبر PostgreSQL المحلي في هذا المشروع؛ لم يُشغّل Compose في بيئة التطوير لأن Docker غير مثبت. لا تستبدل PostgreSQL بـSQLite.

لتوليد قيمة عشوائية دون إضافتها إلى المصدر:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

## تشغيل الخادم والواجهة منفصلين

النافذة الأولى:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

النافذة الثانية:

```powershell
.\.venv\Scripts\python.exe -m desktop.main
```

Health: [localhost:8000/health](http://127.0.0.1:8000/health). توثيق API التفاعلي: [localhost:8000/docs](http://127.0.0.1:8000/docs). في VS Code افتح المجلد، اختر interpreter `.venv`، ثم شغّل إعدادَي `MediLink API` و`MediLink Desktop` من Run and Debug.

## المنفذ فعلياً

### اختصار EXE على سطح المكتب

بعد تثبيت MinGW الموجود في `C:\msys64\ucrt64`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_app.ps1
```

ينشئ `dist\MediLink-NFC.exe` والاختصار `MediLink NFC.lnk` على سطح المكتب بأيقونة MediLink. التفاصيل في `docs/desktop_shortcut.md`. هذا مشغّل Windows محلي؛ يطلق تهيئة المشروع والخادم والواجهة من مجلد المشروع، لذلك يلزم إبقاء مجلد المشروع و`.venv`.

- الدخول بـArgon2 وJWT؛ أدوار متعددة وقيود المستشفى في الخادم، وتفعيل/تعطيل الموظفين وإدارة المنح.
- مرضى موحدون وبحث وتعديل وحساسية وأمراض مزمنة وزيارات وتشخيصات، مع إسقاط حقول الاستجابة بحسب الدور.
- إصدار وإلغاء واستبدال بطاقات برموز عشوائية، وقارئ ESP8266/RC522 تسلسلي، وCache تعيد التحقق من القاعدة، وسجل قراءة الموظف والمستشفى والوقت.
- حجز وتعديل وإلغاء وحضور، وQueue مترابطة حقيقية؛ PostgreSQL يمنع تداخل الطبيب والمريض حتى مع التزامن.
- طوارئ بهيكل Min-Heap يدوي وتحديث أولوية وتعادل زمني واستعادة من القاعدة.
- وصفات بأدوية وجرعات وتعليمات، صرف مرة واحدة وتصحيح إداري بسبب موثق؛ لا مخزون معقد.
- فواتير استقبال متعددة البنود والدفعات، Decimal/NUMERIC وrow locks ومفاتيح إعادة المحاولة، وتصدير إيصال PDF.
- Graph بقوائم تجاور وBFS، إحالات وقبولها في الوجهة، مشاركة السجلات المسموح بها وتدقيق الوصول العابر.
- واجهات الأدوار في QStackedWidget، مع طلبات شبكة وNFC في QThreadPool ورسائل عربية واضحة.
- برنامج ESP8266 يُبنى عبر PlatformIO. نجحت قراءة وكتابة بطاقة MIFARE Classic 1K تجريبية فعلياً؛ انظر دليل NFC.

## الاختبارات والعرض

```powershell
.\.venv\Scripts\python.exe -m scripts.create_test_db
.\.venv\Scripts\python.exe -m pytest tests -q --junitxml=docs/test-results.xml
.\.venv\Scripts\python.exe -m ruff check backend desktop scripts tests
.\.venv\Scripts\python.exe -m scripts.benchmark --size 10000
# أثناء تشغيل الخادم: تنفيذ سيناريو القبول وإضافة بيانات عرض فعلية
.\.venv\Scripts\python.exe -m scripts.demo_workflow
```

اختبارات التكامل تمسح **قاعدة *_test فقط** وتعيد seed. لا توجه TEST_DATABASE_URL إلى بيانات مهمة حتى لو انتهى الاسم بـ_test. اختبارات Qt تستخدم offscreen دون إظهار نوافذ، لكنها تشغل PySide6 الفعلية وخادم HTTP فعلياً. نتائج التشغيل والأوامر في `docs/testing.md` وXML؛ الأجزاء غير المختبرة موثقة صراحةً. تصدير الإيصال يستخدم QPdfWriter ولا يحتاج طابعة مثبتة.

`demo_workflow` يضيف مريضاً وهمياً وسجلات جديدة دون حذف البيانات. يكتب أرقامها في `.runtime/demo-run.json` ورمز البطاقة التجريبية في `.runtime/demo-card-token.txt`، وكلاهما مستبعد من Git. يستخدم هذا السكربت API مباشرةً؛ الواجهة تستخدم قارئ ESP8266/RC522. استخدم الدليل التفصيلي `docs/demo.md` للعرض على خمسة حسابات.

## بناء برنامج القارئ

```powershell
.\.venv\Scripts\python.exe -m pip install platformio
.\.venv\Scripts\python.exe -m platformio run -d nfc_esp8266
# تحقق من منفذ اللوحة قبل الرفع:
.\.venv\Scripts\python.exe -m platformio run -d nfc_esp8266 -t upload
```

اضبط `NFC_PORT` في `.env` على منفذ اللوحة الفعلي؛ `COM6` هو الافتراضي فقط. تعليمات التوصيل ونوع البطاقة وحدود الاختبار في `docs/nfc.md`.

## ملفات التوثيق

- `docs/architecture.md`: مخطط المعمارية والحدود والصلاحيات والتزامن.
- `docs/database.md`: ERD Mermaid والقيود والتطبيع والترحيلات.
- `docs/api.md` و`docs/openapi.json`: عقود API.
- `docs/data_structures.md`: التنفيذ والاستخدام والتعقيد وbenchmark.
- `docs/team_tasks.md`: توزيع المهام وعقود الربط بين الأعضاء الخمسة.
- `docs/demo.md`: خطوات العرض الجامعي.
- `docs/testing.md`: نتائج التحقق وحدوده.

## ملاحظات التشغيل

عند 503 تحقق من PostgreSQL. عند 401 أعد الدخول. عند 403 استخدم الدور الصحيح ومنحة المستشفى. عند 409 راجع التداخل أو الحالة أو الرصيد. لا تستخدم UID بدلاً من الرمز. لا تستعمل بطاقة حقيقية مهمة في التجارب؛ الكتابة مخصصة لبطاقة MIFARE Classic 1K تجريبية متوافقة.

لا تُحفظ كلمات المرور أو JWT أو الأسرار في المصدر. لا يصل Desktop إلى قاعدة البيانات. سيناريو العرض النصي يستخدم API وPostgreSQL، لكن الواجهة تستخدم قارئ ESP8266/RC522. الإصدارات المستخدمة فعلياً محفوظة في `requirements-lock.txt` لإعادة بناء البيئة على Windows/Python 3.12.

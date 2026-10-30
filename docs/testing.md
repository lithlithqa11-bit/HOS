# نتائج التحقق الفعلية

أُنتج هذا الملخص من `docs/test-results.xml`، وليس من عدد اختبارات متوقع.

- النتيجة: **48 نجح من 48**؛ فشل 0، أخطاء 0، متخطى 0.
- مدة pytest: 62.936 ثانية.
- وقت التقرير كما سجله pytest: 2026-10-30T23:26:58.529896+03:00.
- بيئة التشغيل: Windows، Python 3.12.3، PostgreSQL 18 محلي على 55432.

## الأوامر المنفذة

```powershell
.\.venv\Scripts\python.exe -m scripts.setup_local
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.seed
.\.venv\Scripts\python.exe -m pytest tests -q --junitxml=docs/test-results.xml
.\.venv\Scripts\python.exe -m ruff check backend desktop scripts tests
.\.venv\Scripts\python.exe -m compileall -q backend desktop scripts tests
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m scripts.benchmark --size 10000
.\.venv\Scripts\python.exe -m scripts.build_nfc
.\.venv\Scripts\python.exe -m scripts.verify_demo
.\.venv\Scripts\python.exe -m scripts.export_openapi
```

ruff: All checks passed. compileall: exit 0. Alembic: No new upgrade operations detected. CMake/Ninja: بناء C++17 نجح مع GNU 16.2.0 وربط winscard. أُنشئ nfc_reader.exe فعلياً.

اختُبر كذلك `scripts/run_demo.ps1`: أعاد استخدام قاعدة البيانات والـseed دون حذف، وشغّل الخادم وواجهة Desktop. أعاد `/health` القيمة `status=ok, database=postgresql`. فحص ملفات التسليم لم يجد JWT_SECRET أو DEMO_PASSWORD أو كلمة مرور PostgreSQL ضمنها؛ .env و.runtime وملفات البناء مستبعدة من Git.

## ما اختُبر

- تسجيل الدخول الصحيح والخاطئ، الرموز المزورة والمنتهية وتعطيل الموظف، وأدوار الإدارة والطبيب والتمريض والصيدلية والاستقبال.
- إنشاء وتعديل وبحث المرضى، حقول الاستجابة بحسب الدور، المنح بين المستشفيات والسجلات الخاصة والمشتركة، وسحب الوصول من جميع قوائم العمل.
- بطاقات صحيحة وملغاة ومجهولة، الاستبدال، cache hit، ومحاكاة إلغاء من عملية أخرى بإعادة التحقق من PostgreSQL.
- تداخل المواعيد والتعديل والإلغاء والحضور وQueue، والسباق بين طلبَي حجز متزامنين.
- ترتيب Heap والتعادل وتحديث الأولوية والتحويل إلى العلاج، وأخذ حالتين مختلفتين بالتزامن.
- صرف الوصفة وتصحيحها وصرف متزامن يمنع التكرار، وعدم تسريب الملاحظات إلى الصيدلية.
- Decimal ودفعات متعددة ورفض تجاوز الرصيد وإعادة المحاولة idempotency، ودفعات متزامنة.
- إحالة A→B وقبولها وإتاحة السجل المشترك وتسجيل زيارة في B والتدقيق العابر.
- استعادة Queue/Heap/Graph في **عملية Python جديدة**، وإعادة إنشاء تطبيق API مع نفس البيانات.
- رفض اتصال PostgreSQL حقيقي على منفذ غير متاح وإرجاع 503؛ انقطاع شبكة العميل باختبار transport محاكى.
- HashTable مع تصادمات إجبارية وعمليات عشوائية، Queue، Heap مقارنةً بمرجع مرتب، Graph مع دورات ومسارات مفقودة.
- تشغيل PySide6 الحقيقي بخادم HTTP فعلي في وضع offscreen: الدخول، إنشاء مريض، إصدار/قراءة بطاقة، عرض الملف، تحميل صفحات جميع الأدوار، إنشاء فاتورة متعددة البنود ودفعها وتصدير PDF، وإنشاء وتحديث حالة طوارئ.
- البرنامج C++ المبني: JSON عند مدخلات غير صالحة؛ واستدعاء read أعاد pcsc_service_unavailable في بيئة الفحص. ليس اختبار بطاقة فعلية.

اختبار العرض الإضافي `verify_demo` شغّل FastAPI كعملية مستقلة ونفذ سيناريو القبول عبر HTTP على قاعدة العرض medilink؛ نجح وترك سجلات وهمية قابلة للمراجعة. ملخصها في `.runtime/demo-run.json` والرمز في `.runtime/mock-card.txt` المستبعدين من Git.

## ملاحظات وحدود صريحة

- ظهر تحذير واحد من Starlette عن استخدام httpx في TestClient؛ الاختبارات نجحت. لم نغير مكتبات مستقرة أثناء التسليم لإخفاء التحذير.
- توقفت عملية PostgreSQL خلال انقطاع الجلسة؛ أُعيد تشغيل cluster نفسه دون حذف البيانات، ثم أُعيدت المجموعة النهائية بنجاح.
- فشل بناء MinGW الأول بسبب مسار عربي؛ سكربت build_nfc يستخدم المسار القصير وNinja وتم البناء بعدها.
- اختبار الواجهة الأول احتاج تحديد الخلية الحالية بدلاً من selectRow في Qt؛ أضيفت حماية اختيار الصف وحدود الفهرس. التصدير يستخدم QPdfWriter لتجنب اعتماد تعريفات طابعات Windows.
- **لم يُختبر Docker Compose** لأن Docker غير مثبت هنا. الملف متاح، والتحقق الفعلي كان على PostgreSQL 18 المحلي.
- **لم يُختبر قارئ ACR1552U ولا قراءة/كتابة بطاقة فعلية**. أوامر PC/SC مقيدة بـType 2 وأجهزة تدعمها. قائمة الاختبارات الميدانية في docs/nfc.md.
- لا اختبار حمل سريري ولا مراجعة اعتماد طبي. بيانات وهمية فقط، ولا مخزون أو أسرة أو توقع طبي.

## الإصدارات

- FastAPI: 0.162.0
- SQLAlchemy: 2.0.55
- alembic: 1.20.1
- psycopg: 3.3.6
- pydantic: 2.14.2
- PySide6: 6.12.0
- pytest: 9.2.0

القائمة الكاملة المجمّدة في `requirements-lock.txt`. القياس الفعلي في `docs/benchmark_results.json`، ولقطات Qt في `docs/screenshots`.

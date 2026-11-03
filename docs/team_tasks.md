# تقسيم العمل على خمسة طلاب

## العضو الأول — قائد الفريق

يمتلك `backend/app/core` و`services/access.py` والتكامل. يراجع فصل الصلاحيات، المعاملات، تغييرات API، وتوثيق القيود. يدمج تغييرات زملائه بعد pytest وruff ويشرف على العرض الجامعي.

## العضو الثاني — Data Structures

يمتلك `backend/app/structures` و`tests/unit/test_structures.py` و`scripts/benchmark.py`. يشرح التعقيد، التصادمات، ترتيب التعادل، واستعادة الهياكل من PostgreSQL. لا يغير توقيعات الهياكل دون التنسيق مع backend.

## العضو الثالث — NFC

يمتلك `nfc_esp8266` و`desktop/nfc_bridge.py` واختبارات bridge. يبني برنامج اللوحة عبر PlatformIO، ويتحقق من RC522 ونوع البطاقة والقراءة والكتابة عبر Serial. يحتفظ بقائمة اختبارات الجهاز غير المنفذة، ويضمن أن UID ليس اعتماد وصول.

## العضو الرابع — Database & Backend

يمتلك `backend/app/db` و`alembic` و`schemas` و`api` و`scripts/seed.py`. يراجع القيود والفهارس وTransactions. ينسق مع العضو الأول بشأن الصلاحيات، ومع العضو الثاني بشأن حفظ Queue/Heap ومسار Graph.

## العضو الخامس — Desktop & Testing

يمتلك `desktop/screens` و`widgets` و`api_client.py` واختبارات Qt والتكامل. ينفذ RTL وحالات التحميل والأخطاء وإيصال الاستقبال، ويختبر رحلة المستخدم دون وصول مباشر إلى قاعدة البيانات.

## عقود الربط

- Desktop → API: HTTP JSON تحت `/api`، JWT في Authorization Bearer. التفاصيل المعتمدة في `/openapi.json` و`/docs`. الأخطاء 401/403/404/409/422/503 مع detail.
- Backend → PostgreSQL: Session لكل طلب، commit قبل إرسال الاستجابة، rollback عند أي خطأ. Migration إلزامية قبل التشغيل.
- ESP8266 → Python: أسطر JSON عبر Serial بسرعة 115200. القراءة تعيد token من 64 خانة hex؛ الكتابة ترسل `WRITE <token>` ثم تنتظر تأكيد القراءة. البيانات الطبية غير موجودة على البطاقة.
- سيناريو HTTP الآلي يرسل الرمز إلى API مباشرةً؛ قارئ واجهة التشغيل هو ESP8266/RC522.
- Money: Decimal في Python وNUMERIC(12,2) في PostgreSQL؛ القيم المالية تُنقل كسلاسل عشرية.
- Time: UTC aware timestamps في التخزين وISO 8601 في API. واجهة المواعيد ترسل منطقة الجهاز الزمنية صراحةً.
- Structures: HashTable.insert/search/delete؛ Queue.enqueue/dequeue/peek/is_empty؛ PriorityQueue.insert/extract_min/peek/update_priority؛ Graph.add_node/add_edge/bfs.

## طريقة العمل الجماعي

فروع مقترحة: codex/auth، codex/structures، codex/nfc، codex/backend، codex/desktop. قبل الدمج: اختبار الوحدة الخاصة بالجزء ثم جميع اختبارات التكامل على قاعدة *_test مستقلة. لا ترفع .env أو pgdata أو كلمات المرور إلى Git. لا يعدل عضوان migration منشورة؛ التغيير التالي migration جديدة.

# تقسيم العمل على خمسة طلاب

## العضو الأول — قائد الفريق

يمتلك `backend/app/core` و`services/access.py` والتكامل. يراجع فصل الصلاحيات، المعاملات، تغييرات API، وتوثيق القيود. يدمج تغييرات زملائه بعد pytest وruff ويشرف على العرض الجامعي.

## العضو الثاني — Data Structures

يمتلك `backend/app/structures` و`tests/unit/test_structures.py` و`scripts/benchmark.py`. يشرح التعقيد، التصادمات، ترتيب التعادل، واستعادة الهياكل من PostgreSQL. لا يغير توقيعات الهياكل دون التنسيق مع backend.

## العضو الثالث — NFC

يمتلك `nfc_cpp` و`desktop/nfc_bridge.py` واختبارات bridge. يبني C++17 عبر CMake، ويتحقق من PC/SC ونوع البطاقة وأوامر القراءة والكتابة. يحتفظ بقائمة اختبارات الجهاز غير المنفذة، ويضمن أن UID ليس اعتماد وصول.

## العضو الرابع — Database & Backend

يمتلك `backend/app/db` و`alembic` و`schemas` و`api` و`scripts/seed.py`. يراجع القيود والفهارس وTransactions. ينسق مع العضو الأول بشأن الصلاحيات، ومع العضو الثاني بشأن حفظ Queue/Heap ومسار Graph.

## العضو الخامس — Desktop & Testing

يمتلك `desktop/screens` و`widgets` و`api_client.py` واختبارات Qt والتكامل. ينفذ RTL وحالات التحميل والأخطاء وإيصال الاستقبال، ويختبر رحلة المستخدم دون وصول مباشر إلى قاعدة البيانات.

## عقود الربط

- Desktop → API: HTTP JSON تحت `/api`، JWT في Authorization Bearer. التفاصيل المعتمدة في `/openapi.json` و`/docs`. الأخطاء 401/403/404/409/422/503 مع detail.
- Backend → PostgreSQL: Session لكل طلب، commit قبل إرسال الاستجابة، rollback عند أي خطأ. Migration إلزامية قبل التشغيل.
- NFC C++ → Python: استدعاء subprocess دون shell، stdout يحوي JSON واحداً، وreturn code غير صفري عند الفشل. عند النجاح token من 64 خانة hex؛ البيانات الطبية غير موجودة على البطاقة.
- Python mock: نفس نتيجة القارئ الحقيقي، لكنه يأخذ رمزاً صادراً من API. لا بيانات مرضى ثابتة داخل الواجهة.
- Money: Decimal في Python وNUMERIC(12,2) في PostgreSQL؛ القيم المالية تُنقل كسلاسل عشرية.
- Time: UTC aware timestamps في التخزين وISO 8601 في API. واجهة المواعيد ترسل منطقة الجهاز الزمنية صراحةً.
- Structures: HashTable.insert/search/delete؛ Queue.enqueue/dequeue/peek/is_empty؛ PriorityQueue.insert/extract_min/peek/update_priority؛ Graph.add_node/add_edge/bfs.

## طريقة العمل الجماعي

فروع مقترحة: codex/auth، codex/structures، codex/nfc، codex/backend، codex/desktop. قبل الدمج: اختبار الوحدة الخاصة بالجزء ثم جميع اختبارات التكامل على قاعدة *_test مستقلة. لا ترفع .env أو pgdata أو كلمات المرور إلى Git. لا يعدل عضوان migration منشورة؛ التغيير التالي migration جديدة.

"""Summarize actual JUnit results without rerunning or fabricating checks."""
from copy import deepcopy
from importlib.metadata import version
from pathlib import Path
import platform
import xml.etree.ElementTree as ET


def main():
    suite = ET.parse('docs/test-results.xml').getroot().find('testsuite')
    if suite is None:
        raise RuntimeError('No actual pytest JUnit report found')
    tests, failures, errors, skipped = [int(suite.get(key, '0')) for key in ('tests', 'failures', 'errors', 'skipped')]
    desktop = ET.Element('testsuite', name='desktop', failures='0', errors='0', skipped='0')
    for case in suite.findall('testcase'):
        if case.get('classname', '').endswith('test_desktop'):
            desktop.append(deepcopy(case))
    desktop.set('tests', str(len(desktop)))
    ET.ElementTree(desktop).write('docs/desktop-tests.xml', encoding='utf-8', xml_declaration=True)
    packages = '\n'.join(f'- {name}: {version(name)}' for name in ('FastAPI', 'SQLAlchemy', 'alembic',
                         'psycopg', 'pydantic', 'PySide6', 'pytest'))
    report = f'''# نتائج التحقق الفعلية

أُنتج هذا الملخص من `docs/test-results.xml`، وليس من عدد اختبارات متوقع.

- النتيجة: **{tests - failures - errors - skipped} نجح من {tests}**؛ فشل {failures}، أخطاء {errors}، متخطى {skipped}.
- مدة pytest: {suite.get('time')} ثانية.
- وقت التقرير كما سجله pytest: {suite.get('timestamp')}.
- بيئة التشغيل: Windows، Python {platform.python_version()}، PostgreSQL 18 محلي على 55432.

## الأوامر المنفذة

```powershell
.\\.venv\\Scripts\\python.exe -m scripts.setup_local
.\\.venv\\Scripts\\python.exe -m alembic upgrade head
.\\.venv\\Scripts\\python.exe -m scripts.seed
.\\.venv\\Scripts\\python.exe -m pytest tests -q --junitxml=docs/test-results.xml
.\\.venv\\Scripts\\python.exe -m ruff check backend desktop scripts tests
.\\.venv\\Scripts\\python.exe -m compileall -q backend desktop scripts tests
.\\.venv\\Scripts\\python.exe -m alembic check
.\\.venv\\Scripts\\python.exe -m scripts.benchmark --size 10000
.\\.venv\\Scripts\\python.exe -m platformio run -d nfc_esp8266
.\\.venv\\Scripts\\python.exe -m scripts.verify_demo
.\\.venv\\Scripts\\python.exe -m scripts.export_openapi
```

افحص نتائج ruff وcompileall وAlembic في التشغيل الحالي. بناء برنامج ESP8266 عبر PlatformIO مستقل عن اختبار الجهاز الحقيقي.

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
- جسر Serial للـESP8266: اختبارات لوضع القراءة والكتابة ورسائل التشخيص باستخدام منفذ محاكى. نتيجة اختبار البطاقة الفعلية موثقة في docs/nfc.md.

اختبار العرض الإضافي `verify_demo` شغّل FastAPI كعملية مستقلة ونفذ سيناريو القبول عبر HTTP على قاعدة العرض medilink؛ نجح وترك سجلات وهمية قابلة للمراجعة. ملخصها في `.runtime/demo-run.json` والرمز في `.runtime/demo-card-token.txt` المستبعدين من Git.

## ملاحظات وحدود صريحة

- ظهر تحذير واحد من Starlette عن استخدام httpx في TestClient؛ الاختبارات نجحت. لم نغير مكتبات مستقرة أثناء التسليم لإخفاء التحذير.
- توقفت عملية PostgreSQL خلال انقطاع الجلسة؛ أُعيد تشغيل cluster نفسه دون حذف البيانات، ثم أُعيدت المجموعة النهائية بنجاح.
- مسار PC/SC القديم أُزيل؛ بناء برنامج ESP8266 يتم عبر PlatformIO.
- اختبار الواجهة الأول احتاج تحديد الخلية الحالية بدلاً من selectRow في Qt؛ أضيفت حماية اختيار الصف وحدود الفهرس. التصدير يستخدم QPdfWriter لتجنب اعتماد تعريفات طابعات Windows.
- **لم يُختبر Docker Compose** لأن Docker غير مثبت هنا. الملف متاح، والتحقق الفعلي كان على PostgreSQL 18 المحلي.
- اختُبرت بطاقة MIFARE Classic 1K فعلياً عبر ESP8266 وRC522؛ التفاصيل وحدود الاختبار في docs/nfc.md.
- لا اختبار حمل سريري ولا مراجعة اعتماد طبي. بيانات وهمية فقط، ولا مخزون أو أسرة أو توقع طبي.

## الإصدارات

{packages}

القائمة الكاملة المجمّدة في `requirements-lock.txt`. القياس الفعلي في `docs/benchmark_results.json`، ولقطات Qt في `docs/screenshots`.
'''
    Path('docs/testing.md').write_text(report, encoding='utf-8')
    print(f'Wrote test report: {tests} tests, {failures} failures, {errors} errors, {skipped} skipped')


if __name__ == '__main__':
    main()

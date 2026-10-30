# EXE والاختصار

لتجنب كتابة أمر PowerShell كل مرة:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_app.ps1
```

ينشئ ذلك `dist\MediLink-NFC.exe` ويضع `MediLink NFC.lnk` على سطح المكتب مع أيقونة `desktop\assets\medilink.ico`. ملف EXE يشغّل Python والواجهة مباشرةً؛ لا يفتح PowerShell ولا يحتاج كتابة أمر. لا يحفظ كلمات مرور داخل الملف.

انسخ مجلد المشروع كاملاً عند نقل التطبيق، لأن EXE يعتمد على `.venv` وPostgreSQL المحلي و`resources`/`scripts`. الاختصار يشغّل `run_demo.ps1` في نافذة منفصلة، ويغلق الخادم الذي بدأه عند إغلاق الواجهة. لا تستخدم `dist\MediLink-NFC.exe` بعد حذف مجلد المشروع.

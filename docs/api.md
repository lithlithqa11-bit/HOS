# عقود REST API

الخادم المحلي `http://127.0.0.1:8000`. المرجع الآلي النهائي هو `openapi.json`، ويعرض Swagger `/docs` كل الحقول والأنواع. جميع المسارات التالية تبدأ بـ`/api` باستثناء `/health`.

## المصادقة والأخطاء

`POST /auth/login` يستقبل username وpassword ويرجع access_token وemployee. أرسل `Authorization: Bearer <token>` في كل طلب لاحق. `GET /auth/me` يعيد هوية الموظف الحالية وأدواره ومستشفاه. تنتهي الجلسة افتراضياً بعد ساعة. تسجيل الخروج يمسح الرمز من ذاكرة Desktop؛ تعطيل الحساب في الإدارة يرفض الرموز القائمة فوراً.

الأخطاء: 401 دخول، 403 صلاحية، 404 غير موجود/بطاقة غير معروفة أو ملغاة، 409 تعارض أو حالة غير مسموحة، 422 مدخلات، 503 قاعدة غير متاحة. لا ترسل استجابات الخطأ نص SQL أو أسرار الاتصال. نجاح الإنشاء 201، ونجاح القراءة والتعديل غالباً 200. تواريخ الموعد يجب أن تحتوي timezone؛ الأموال سلاسل عشرية مثل `"12500.00"`.

## المرضى والسجل الطبي

- `POST /patients`: استقبال؛ full_name، birth_date، sex (male/female/other)، phone.
- `GET /patients?q=`: بحث في المرضى الممنوحين للمستشفى فقط، حتى 100 نتيجة؛ الاسم أو الرقم.
- `GET /patients/{id}`: بيانات تعريفية، والطبيب يرى visits والتشخيصات؛ الطبيب والممرض يريان allergies وchronic_conditions. غيرهما لا يتلقى تلك الحقول إطلاقاً.
- `PUT /patients/{id}`: استقبال؛ تعديل الحقول التعريفية كاملة.
- `POST /patients/{id}/facts`: طبيب/ممرض؛ kind=allergy/chronic، description، shared.
- `POST /visits`: طبيب؛ patient_id، notes، diagnosis، shared.
- `PATCH /visits/{id}/sharing`: طبيب من المصدر؛ shared=true/false.

## NFC

- `POST /patients/{id}/cards`: استقبال؛ يصدر رمزاً جديداً ويلغي كل بطاقة فعالة سابقة ضمن معاملة. يعيد card_id وtoken وpatient_id. token هو 64 خانة hex عشوائية ويظهر مرة واحدة.
- `DELETE /patients/{id}/cards`: إلغاء البطاقة الفعالة.
- `POST /nfc/scan`: كل موظف مسجل؛ body فيه token فقط. يعيد نفس إسقاط الصلاحيات الخاص بملف المريض. لا يقبل UID.

## المواعيد وQueue

- `GET /doctors`: الأطباء الفعالون في مستشفى الموظف.
- `GET /appointments`: استقبال/طبيب/ممرض؛ حتى 300 موعد محلي.
- `POST /appointments` و`PUT /appointments/{id}`: استقبال؛ patient_id وdoctor_id وstarts_at وends_at. التعديل لموعد booked فقط وبنفس المريض. المدة من دقيقة إلى ثماني ساعات، ولا يسمح بالتداخل مع موعد غير ملغى للطبيب أو المريض.
- `POST /appointments/{id}/cancel` أو `/check-in`: استقبال.
- `GET /waiting-queue`: استقبال/طبيب/ممرض؛ FIFO بحسب الحضور وid.
- `POST /waiting-queue/next`: نفس الأدوار؛ يسحب أول مراجع ويحوّل الموعد إلى completed. في هذا النموذج «التالي» يعني إنهاء دور الانتظار، وليس توثيق زيارة طبية تلقائياً.

## الطوارئ وHeap

طبيب/ممرض فقط: `GET /emergencies`، `POST /emergencies` بحقول patient_id وpriority (1–5) وnotes، و`PUT /emergencies/{id}` بحقلي priority وstatus. الحالات waiting/treating/discharged؛ الحالة المغلقة لا يعاد فتحها، ولا تعاد treating إلى waiting. `POST /emergencies/next` يسحب أعلى أولوية ويحولها إلى treating. تعادل الأولوية يحسمه arrived_at ثم id.

## الصيدلية

- `GET /medications`: طبيب/صيدلي؛ أدوية مرجعية تعليمية دون مخزون.
- `POST /prescriptions`: طبيب؛ visit_id وitems، كل بند medication_id وdose وinstructions.
- `GET /prescriptions?patient_id=`: طبيب/صيدلي؛ وصفات الزيارات المحلية أو المشتركة المسموح بها، دون ملاحظات وتشخيصات الزيارة.
- `POST /prescriptions/{id}/dispense`: صيدلي؛ انتقال Pending إلى Dispensed مرة واحدة، وتسجيل الموظف والوقت.
- `POST /prescriptions/{id}/correct`: مدير المستشفى المصدر؛ reason من خمسة أحرف على الأقل، يعيد Pending ويوثق الصرف السابق وسبب التصحيح.

## فواتير الاستقبال

استقبال فقط:

- `POST /invoices`: patient_id، visit_id اختياري، discount، items (description، quantity، unit_price).
- `GET /invoices?patient_id=` و`GET /invoices/{id}`: سجل فواتير المستشفى الحالي، مشتقات subtotal/total/paid/remaining ومصفوفتا items/payments.
- `POST /invoices/{id}/items`: إضافة بند قبل بدء الدفع. بعد أول دفعة تصبح البنود ثابتة؛ أنشئ فاتورة خدمة أخرى عند الحاجة.
- `POST /invoices/{id}/payments`: amount موجب وrequest_key فريد من 16–64 حرفاً. إعادة نفس المفتاح والمبلغ والفاتورة ترجع النتيجة دون دفعة ثانية. مفتاح مستخدم لقيم مختلفة يرفض بـ409. لا توجد مبالغ سالبة أو استردادات ضمن النطاق.

الإيصال يصدّر من Desktop عبر Qt QPdfWriter بعد تحديث الفاتورة من API، دون الحاجة إلى طابعة مثبتة. العملة التجريبية IQD.

## شبكة المستشفيات والإحالات

- `GET /hospitals` و`GET /connections`: بيانات شبكة المستشفيات للموظف.
- `GET /hospital-path/{destination_id}`: BFS من مستشفى الموظف إلى الوجهة؛ يعيد path من المعرفات وhospitals من الأسماء.
- `POST /referrals`: طبيب؛ patient_id، destination_id، reason. يجب وجود مسار.
- `GET /referrals`: طبيب/ممرض/استقبال؛ إحالات المصدر أو الوجهة فقط. reason محجوب عن الاستقبال.
- `PUT /referrals/{id}`: طبيب؛ accepted/rejected من الوجهة وcancelled من المصدر. pending فقط قابلة للتحديث. القبول ينشئ/يفعّل منحة الوصول؛ لا يشارك الزيارات الخاصة.

## الإدارة

- `GET/POST /admin/employees`: عرض وإضافة؛ username، full_name، hospital_id، password (12 حرفاً على الأقل)، roles.
- `PUT /admin/employees/{id}`: active وroles، ولا يمكن للمدير تعديل أدوار حسابه الحالي.
- `POST /admin/hospitals`: name، city.
- `POST /admin/connections`: source_id، destination_id؛ رابط موجه.
- `PUT /admin/patients/{id}/access`: hospital_id، active؛ المنحة منفصلة عن shared في السجل.
- `GET /admin/audit`: آخر 500 حدث، مع هوية الموظف والمستشفى والمريض والوقت والتفاصيل الإدارية.

الحساب الإداري لا يحصل تلقائياً على الصلاحيات السريرية. يمكن إسناد أكثر من دور صراحةً. كل hospital_id حساس في عمليات الأعمال يستمده الخادم من الموظف؛ extra fields غير المسموح بها ترفضها Pydantic.

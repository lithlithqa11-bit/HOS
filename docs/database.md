# قاعدة البيانات

PostgreSQL حصراً، SQLAlchemy 2.0 وAlembic. المريض صف موحد؛ لا يُكرر لكل مستشفى. العملات التجريبية بالدينار العراقي مع دقة منزلتين؛ جميع المبالغ NUMERIC(12,2). المجموع والرصيد مشتقان من البنود والمدفوعات، وليسا حقولاً مكررة قابلة للانحراف.

```mermaid
erDiagram
    hospitals ||--o{ departments : contains
    hospitals ||--o{ employees : employs
    employees ||--o{ employee_roles : has
    roles ||--o{ employee_roles : assigns
    patients ||--o{ nfc_cards : carries
    patients ||--o{ patient_hospital_access : grants
    hospitals ||--o{ patient_hospital_access : receives
    employees ||--o{ patient_hospital_access : authorizes
    patients ||--o{ visits : attends
    hospitals ||--o{ visits : hosts
    employees ||--o{ visits : documents
    visits ||--o{ diagnoses : records
    patients ||--o{ allergies : has
    hospitals ||--o{ allergies : owns
    patients ||--o{ chronic_conditions : has
    hospitals ||--o{ chronic_conditions : owns
    visits ||--o{ prescriptions : produces
    prescriptions ||--|{ prescription_items : contains
    medications ||--o{ prescription_items : references
    employees ||--o{ prescriptions : dispenses
    patients ||--o{ appointments : books
    employees ||--o{ appointments : receives
    hospitals ||--o{ appointments : schedules
    patients ||--o{ emergency_cases : enters
    hospitals ||--o{ emergency_cases : handles
    employees ||--o{ emergency_cases : triages
    hospitals ||--o{ hospital_connections : source
    hospitals ||--o{ hospital_connections : destination
    hospitals ||--o{ referrals : source
    hospitals ||--o{ referrals : destination
    patients ||--o{ referrals : referred
    employees ||--o{ referrals : requests
    patients ||--o{ invoices : owes
    hospitals ||--o{ invoices : issues
    visits |o--o{ invoices : optionally_bills
    invoices ||--|{ invoice_items : contains
    invoices ||--o{ payments : receives
    employees ||--o{ payments : collects
    employees |o--o{ audit_logs : acts
    hospitals |o--o{ audit_logs : context
    patients |o--o{ audit_logs : subject

    patients {
        int id PK
        varchar full_name
        date birth_date
        varchar sex
        varchar phone
    }
    visits {
        int id PK
        int patient_id FK
        int hospital_id FK
        int doctor_id FK
        boolean shared
        timestamptz created_at
        text notes
    }
    nfc_cards {
        int id PK
        int patient_id FK
        varchar token_hash UK
        boolean active
        timestamptz issued_at
        timestamptz revoked_at
    }
    invoices {
        int id PK
        int patient_id FK
        int hospital_id FK
        int visit_id FK
        numeric discount
    }
    payments {
        int id PK
        int invoice_id FK
        numeric amount
        varchar request_key UK
        int received_by FK
        timestamptz paid_at
    }
```

## التطبيع والقيود

الموظف له مستشفى واحد وأدوار متعددة عبر employee_roles. الزيارة تحمل الطبيب والمستشفى، والتشخيصات في جدول مستقل. الوصفة مرتبطة بزيارة، وبنودها بالأدوية المرجعية؛ لا مخزون أو مورّدون. سجلات الحساسية والأمراض لها مصدر وقرار مشاركة مستقلان. hospital_connections حواف موجهة بمفتاح مركب. الإحالة لا تكرر مسار الرسم؛ يحسب المسار الحالي عند العرض، وتُحفظ نسخة الطريق عند الإنشاء في سجل التدقيق.

مفاتيح أجنبية تمنع المراجع المفقودة. Unique لاسم المستشفى/المستخدم/الدواء/الدور، وhash البطاقة ومفتاح الدفع. Check للنطاقات المالية وحالات الوصفة والموعد والطوارئ ومستويات الأولوية، واتساق بيانات الصرف. فهارس patient_id وhospital_id ومفاتيح الترتيب والبحث. يمنع partial unique index وجود بطاقتين فعالتين للمريض. EXCLUDE يمنع تقاطع المواعيد للطبيب أو للمريض في المستشفيات كافة.

السياسة المحافظة للحذف هي عدم إتاحة حذف السجلات الطبية من API؛ تستخدم حالات إلغاء/تعطيل. لا تزال بيانات العرض فقط، والسياسات القانونية الفعلية خارج النطاق.

## Migration والبيانات التجريبية

`python -m alembic upgrade head` لإنشاء الجداول والقيود. Migration أولية ثابتة؛ لا تستدعي metadata.create_all وقت التشغيل. يحتاج حساب الترحيل صلاحية إنشاء extension btree_gist. `python -m scripts.seed` ينشئ مستشفيين و10 موظفين وثلاثة مرضى وأدوية تعليمية وروابط الإحالة. تُقرأ كلمة المرور من DEMO_PASSWORD ولا تُكتب في المصدر.

اختبارات التكامل ترفض أي اسم قاعدة لا ينتهي بـ `_test`. إعادة بناء بيانات الاختبار لا تمس `medilink`. بيانات البيئة المحلية الفعلية تحت `.runtime` ومستبعدة من Git.

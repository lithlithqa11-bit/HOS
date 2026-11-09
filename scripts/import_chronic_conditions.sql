-- Import only chronic_diseases from patients_core_import.
-- Uses id + name to match existing canonical patients; no visits, billing,
-- diagnoses, notes, or demographics are modified.
DO $$
DECLARE
    v_admin_id integer;
    v_hospital_id integer;
    v_source_rows integer;
    v_distinct_ids integer;
    v_exact_matches integer;
    v_long_descriptions integer;
    v_new_conditions integer;
    v_shared_conditions integer;
BEGIN
    SELECT e.id, e.hospital_id
      INTO v_admin_id, v_hospital_id
      FROM public.employees e
      JOIN public.employee_roles er ON er.employee_id = e.id
      JOIN public.roles r ON r.id = er.role_id
     WHERE e.username = 'admin.a'
       AND e.active = true
       AND r.name = 'admin'
     LIMIT 1;

    IF v_admin_id IS NULL OR v_hospital_id IS NULL THEN
        RAISE EXCEPTION 'No active admin.a account found; no changes applied.';
    END IF;

    SELECT count(*), count(DISTINCT id)
      INTO v_source_rows, v_distinct_ids
      FROM public.patients_core_import;

    SELECT count(*)
      INTO v_exact_matches
      FROM public.patients_core_import s
      JOIN public.patients p
        ON p.id = s.id
       AND lower(trim(p.full_name)) = lower(trim(s.name));

    IF v_source_rows <> 30 OR v_distinct_ids <> v_source_rows
       OR v_exact_matches <> v_source_rows THEN
        RAISE EXCEPTION 'Stopped: source rows did not all match canonical patients exactly.';
    END IF;

    SELECT count(*)
      INTO v_long_descriptions
      FROM public.patients_core_import s
     WHERE nullif(trim(s.chronic_diseases), '') IS NOT NULL
       AND length(trim(s.chronic_diseases)) > 500;

    IF v_long_descriptions > 0 THEN
        RAISE EXCEPTION 'Stopped: a chronic disease description exceeds 500 characters.';
    END IF;

    WITH source_conditions AS (
        SELECT p.id AS patient_id, trim(s.chronic_diseases) AS description
          FROM public.patients_core_import s
          JOIN public.patients p
            ON p.id = s.id
           AND lower(trim(p.full_name)) = lower(trim(s.name))
         WHERE nullif(trim(s.chronic_diseases), '') IS NOT NULL
           AND lower(trim(s.chronic_diseases)) NOT IN
               ('لا توجد', 'لا يوجد', 'لاتوجد', 'لايوجد', 'لا توجد أمراض مزمنة',
                'لا توجد امراض مزمنة', 'none', 'n/a', '-')
    ), changed AS (
        UPDATE public.chronic_conditions cc
           SET shared = true
          FROM source_conditions s
         WHERE cc.patient_id = s.patient_id
           AND cc.hospital_id = v_hospital_id
           AND lower(trim(cc.description)) = lower(trim(s.description))
           AND cc.shared IS DISTINCT FROM true
        RETURNING cc.id, cc.patient_id, cc.hospital_id
    )
    INSERT INTO public.audit_logs
        (actor_id, hospital_id, patient_id, action, detail, created_at)
    SELECT v_admin_id, c.hospital_id, c.patient_id, 'chronic.sharing',
           format('condition:%s;shared:true;source:patients_core_import', c.id), now()
      FROM changed c;
    GET DIAGNOSTICS v_shared_conditions = ROW_COUNT;

    WITH source_conditions AS (
        SELECT p.id AS patient_id, trim(s.chronic_diseases) AS description
          FROM public.patients_core_import s
          JOIN public.patients p
            ON p.id = s.id
           AND lower(trim(p.full_name)) = lower(trim(s.name))
         WHERE nullif(trim(s.chronic_diseases), '') IS NOT NULL
           AND lower(trim(s.chronic_diseases)) NOT IN
               ('لا توجد', 'لا يوجد', 'لاتوجد', 'لايوجد', 'لا توجد أمراض مزمنة',
                'لا توجد امراض مزمنة', 'none', 'n/a', '-')
    ), inserted AS (
        INSERT INTO public.chronic_conditions
            (patient_id, hospital_id, description, shared)
        SELECT s.patient_id, v_hospital_id, s.description, true
          FROM source_conditions s
         WHERE NOT EXISTS (
             SELECT 1
               FROM public.chronic_conditions cc
              WHERE cc.patient_id = s.patient_id
                AND cc.hospital_id = v_hospital_id
                AND lower(trim(cc.description)) = lower(trim(s.description))
         )
        RETURNING id, patient_id, hospital_id
    )
    INSERT INTO public.audit_logs
        (actor_id, hospital_id, patient_id, action, detail, created_at)
    SELECT v_admin_id, i.hospital_id, i.patient_id, 'chronic.create',
           format('condition:%s;source:patients_core_import;shared:true', i.id), now()
      FROM inserted i;
    GET DIAGNOSTICS v_new_conditions = ROW_COUNT;

    RAISE NOTICE 'New chronic conditions: %, existing conditions newly shared: %',
                 v_new_conditions, v_shared_conditions;
END $$;

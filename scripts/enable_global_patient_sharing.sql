-- One-time backfill for the current Supabase database.
-- Grants patient-directory access to every hospital and shares existing
-- visits, allergies, and chronic conditions across the hospital network.
-- Writes a matching audit event for each changed grant or clinical record.
DO $$
DECLARE
    v_admin_id integer;
BEGIN
    SELECT e.id
      INTO v_admin_id
      FROM public.employees e
      JOIN public.employee_roles er ON er.employee_id = e.id
      JOIN public.roles r ON r.id = er.role_id
     WHERE e.username = 'admin.a'
       AND e.active = true
       AND r.name = 'admin'
     LIMIT 1;

    IF v_admin_id IS NULL THEN
        RAISE EXCEPTION 'No active admin.a account found; no changes applied.';
    END IF;

    WITH changed AS (
        INSERT INTO public.patient_hospital_access
            (patient_id, hospital_id, active, granted_by)
        SELECT p.id, h.id, true, v_admin_id
          FROM public.patients p
         CROSS JOIN public.hospitals h
        ON CONFLICT (patient_id, hospital_id)
        DO UPDATE SET active = true, granted_by = EXCLUDED.granted_by
        WHERE public.patient_hospital_access.active IS DISTINCT FROM true
        RETURNING patient_id, hospital_id
    )
    INSERT INTO public.audit_logs
        (actor_id, hospital_id, patient_id, action, detail, created_at)
    SELECT v_admin_id, c.hospital_id, c.patient_id, 'access.change',
           format('hospital:%s;active:true;source:auto_global_sharing', c.hospital_id),
           now()
      FROM changed c;

    WITH changed AS (
        UPDATE public.visits v
           SET shared = true
         WHERE v.shared IS DISTINCT FROM true
        RETURNING v.id, v.patient_id, v.hospital_id
    )
    INSERT INTO public.audit_logs
        (actor_id, hospital_id, patient_id, action, detail, created_at)
    SELECT v_admin_id, c.hospital_id, c.patient_id, 'visit.sharing',
           format('visit:%s;shared:true;source:auto_global_sharing', c.id),
           now()
      FROM changed c;

    WITH changed AS (
        UPDATE public.allergies a
           SET shared = true
         WHERE a.shared IS DISTINCT FROM true
        RETURNING a.id, a.patient_id, a.hospital_id
    )
    INSERT INTO public.audit_logs
        (actor_id, hospital_id, patient_id, action, detail, created_at)
    SELECT v_admin_id, c.hospital_id, c.patient_id, 'allergy.sharing',
           format('allergy:%s;shared:true;source:auto_global_sharing', c.id),
           now()
      FROM changed c;

    WITH changed AS (
        UPDATE public.chronic_conditions cc
           SET shared = true
         WHERE cc.shared IS DISTINCT FROM true
        RETURNING cc.id, cc.patient_id, cc.hospital_id
    )
    INSERT INTO public.audit_logs
        (actor_id, hospital_id, patient_id, action, detail, created_at)
    SELECT v_admin_id, c.hospital_id, c.patient_id, 'chronic.sharing',
           format('chronic_condition:%s;shared:true;source:auto_global_sharing', c.id),
           now()
      FROM changed c;
END $$;

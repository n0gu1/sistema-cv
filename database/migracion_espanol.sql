-- Traduce al espanol todos los identificadores fisicos y catalogos del esquema.
-- PostgreSQL 17. Ejecutar como una unica transaccion.

BEGIN;

DO $$
DECLARE
    m RECORD;
BEGIN
    FOR m IN
        SELECT * FROM (VALUES
            ('roles', 'roles_usuario'),
            ('countries', 'paises'),
            ('regions', 'regiones'),
            ('cities', 'ciudades'),
            ('departments', 'departamentos'),
            ('occupations', 'profesiones'),
            ('education_levels', 'niveles_educativos'),
            ('fields_of_study', 'areas_estudio'),
            ('institutions', 'instituciones'),
            ('skill_categories', 'categorias_habilidades'),
            ('skills', 'habilidades'),
            ('skill_levels', 'niveles_habilidad'),
            ('languages', 'idiomas'),
            ('language_levels', 'niveles_idioma'),
            ('certifications', 'certificaciones'),
            ('employment_types', 'tipos_empleo'),
            ('work_modes', 'modalidades_trabajo'),
            ('salary_periods', 'periodos_salariales'),
            ('storage_providers', 'proveedores_almacenamiento'),
            ('users', 'usuarios'),
            ('user_roles', 'usuarios_roles'),
            ('candidate_profiles', 'perfiles_aspirantes'),
            ('staff_profiles', 'perfiles_personal'),
            ('candidate_experiences', 'experiencias_laborales'),
            ('candidate_educations', 'formaciones_academicas'),
            ('candidate_skills', 'habilidades_aspirantes'),
            ('candidate_languages', 'idiomas_aspirantes'),
            ('candidate_certifications', 'certificaciones_aspirantes'),
            ('vacancy_statuses', 'estados_plaza'),
            ('vacancies', 'plazas'),
            ('vacancy_status_history', 'historial_estados_plaza'),
            ('requirement_kinds', 'tipos_requisito'),
            ('vacancy_requirements', 'requisitos_plaza'),
            ('vacancy_skill_requirements', 'requisitos_habilidad'),
            ('vacancy_language_requirements', 'requisitos_idioma'),
            ('vacancy_certification_requirements', 'requisitos_certificacion'),
            ('vacancy_education_requirements', 'requisitos_educacion'),
            ('vacancy_experience_requirements', 'requisitos_experiencia'),
            ('vacancy_availability_requirements', 'requisitos_disponibilidad'),
            ('curricula', 'curriculos'),
            ('ai_models', 'modelos_ia'),
            ('analysis_engines', 'motores_analisis'),
            ('processing_statuses', 'estados_procesamiento'),
            ('cv_analyses', 'analisis_cv'),
            ('cv_analysis_personal_data', 'datos_personales_analisis_cv'),
            ('cv_analysis_experiences', 'experiencias_analisis_cv'),
            ('cv_analysis_educations', 'educaciones_analisis_cv'),
            ('cv_analysis_skills', 'habilidades_analisis_cv'),
            ('cv_analysis_languages', 'idiomas_analisis_cv'),
            ('cv_analysis_certifications', 'certificaciones_analisis_cv'),
            ('application_statuses', 'estados_postulacion'),
            ('applications', 'postulaciones'),
            ('application_status_history', 'historial_estados_postulacion'),
            ('application_evaluations', 'evaluaciones_postulacion'),
            ('evaluation_requirement_results', 'resultados_requisitos_evaluacion'),
            ('interview_statuses', 'estados_entrevista'),
            ('interviews', 'entrevistas'),
            ('notification_types', 'tipos_notificacion'),
            ('notification_channels', 'canales_notificacion'),
            ('delivery_statuses', 'estados_entrega'),
            ('notifications', 'notificaciones'),
            ('notification_deliveries', 'entregas_notificacion'),
            ('notification_delivery_attempts', 'intentos_entrega_notificacion')
        ) AS nombres(anterior, nuevo)
    LOOP
        EXECUTE format('ALTER TABLE public.%I RENAME TO %I', m.anterior, m.nuevo);
    END LOOP;
END $$;

DO $$
DECLARE
    m RECORD;
    t RECORD;
BEGIN
    FOR m IN
        SELECT * FROM (VALUES
            ('code', 'codigo'),
            ('name', 'nombre'),
            ('iso_code', 'codigo_iso'),
            ('country_id', 'pais_id'),
            ('city_id', 'ciudad_id'),
            ('description', 'descripcion'),
            ('is_active', 'activo'),
            ('rank_order', 'orden_nivel'),
            ('category_id', 'categoria_id'),
            ('issuing_organization', 'organizacion_emisora'),
            ('email', 'correo'),
            ('password_hash', 'hash_contrasena'),
            ('first_name', 'nombres'),
            ('last_name', 'apellidos'),
            ('is_verified', 'verificado'),
            ('last_login_at', 'ultimo_acceso_en'),
            ('created_at', 'creado_en'),
            ('updated_at', 'actualizado_en'),
            ('user_id', 'usuario_id'),
            ('role_id', 'rol_id'),
            ('assigned_at', 'asignado_en'),
            ('occupation_id', 'profesion_id'),
            ('phone', 'telefono'),
            ('address_line', 'direccion'),
            ('professional_summary', 'resumen_profesional'),
            ('available_from', 'disponible_desde'),
            ('willing_to_relocate', 'acepta_reubicacion'),
            ('willing_to_travel', 'acepta_viajar'),
            ('department_id', 'departamento_id'),
            ('job_title', 'cargo'),
            ('candidate_id', 'aspirante_id'),
            ('company_name', 'empresa'),
            ('position_title', 'puesto'),
            ('start_date', 'fecha_inicio'),
            ('end_date', 'fecha_fin'),
            ('institution_id', 'institucion_id'),
            ('education_level_id', 'nivel_educativo_id'),
            ('field_of_study_id', 'area_estudio_id'),
            ('degree_name', 'titulo_obtenido'),
            ('skill_id', 'habilidad_id'),
            ('skill_level_id', 'nivel_habilidad_id'),
            ('years_experience', 'anios_experiencia'),
            ('language_id', 'idioma_id'),
            ('language_level_id', 'nivel_idioma_id'),
            ('certification_id', 'certificacion_id'),
            ('credential_code', 'codigo_credencial'),
            ('credential_url', 'url_credencial'),
            ('issued_on', 'emitida_en'),
            ('expires_on', 'vence_en'),
            ('is_terminal', 'es_final'),
            ('created_by_id', 'creado_por_id'),
            ('employment_type_id', 'tipo_empleo_id'),
            ('work_mode_id', 'modalidad_trabajo_id'),
            ('salary_period_id', 'periodo_salarial_id'),
            ('status_code', 'codigo_estado'),
            ('title', 'titulo'),
            ('location_detail', 'detalle_ubicacion'),
            ('salary_min', 'salario_minimo'),
            ('salary_max', 'salario_maximo'),
            ('currency_code', 'codigo_moneda'),
            ('openings_count', 'cantidad_vacantes'),
            ('published_at', 'publicado_en'),
            ('closes_at', 'cierra_en'),
            ('vacancy_id', 'plaza_id'),
            ('previous_status_code', 'codigo_estado_anterior'),
            ('new_status_code', 'codigo_estado_nuevo'),
            ('changed_by_id', 'cambiado_por_id'),
            ('reason', 'motivo'),
            ('changed_at', 'cambiado_en'),
            ('kind_code', 'codigo_tipo'),
            ('is_mandatory', 'obligatorio'),
            ('weight', 'peso'),
            ('display_order', 'orden_visualizacion'),
            ('requirement_id', 'requisito_id'),
            ('min_skill_level_id', 'nivel_habilidad_minimo_id'),
            ('min_years', 'anios_minimos'),
            ('min_language_level_id', 'nivel_idioma_minimo_id'),
            ('must_be_valid', 'debe_estar_vigente'),
            ('min_education_level_id', 'nivel_educativo_minimo_id'),
            ('min_months', 'meses_minimos'),
            ('required_from', 'requerido_desde'),
            ('relocation_required', 'requiere_reubicacion'),
            ('travel_required', 'requiere_viajar'),
            ('schedule_description', 'descripcion_horario'),
            ('storage_provider_id', 'proveedor_almacenamiento_id'),
            ('object_key', 'clave_objeto'),
            ('original_filename', 'nombre_archivo_original'),
            ('mime_type', 'tipo_mime'),
            ('size_bytes', 'tamano_bytes'),
            ('checksum_sha256', 'suma_sha256'),
            ('duplicate_of_id', 'duplicado_de_id'),
            ('uploaded_at', 'cargado_en'),
            ('provider', 'proveedor'),
            ('version', 'version'),
            ('ai_model_id', 'modelo_ia_id'),
            ('prompt_version', 'version_instruccion'),
            ('curriculum_id', 'curriculo_id'),
            ('analysis_engine_id', 'motor_analisis_id'),
            ('extracted_text', 'texto_extraido'),
            ('calculated_experience_months', 'meses_experiencia_calculados'),
            ('started_at', 'iniciado_en'),
            ('completed_at', 'completado_en'),
            ('error_message', 'mensaje_error'),
            ('is_current', 'vigente'),
            ('analysis_id', 'analisis_id'),
            ('full_name', 'nombre_completo'),
            ('occupation_text', 'profesion_texto'),
            ('city_text', 'ciudad_texto'),
            ('confidence', 'confianza'),
            ('institution_text', 'institucion_texto'),
            ('detected_name', 'nombre_detectado'),
            ('evidence', 'evidencia'),
            ('application_id', 'postulacion_id'),
            ('cover_letter', 'carta_presentacion'),
            ('applied_at', 'postulado_en'),
            ('withdrawn_at', 'retirado_en'),
            ('compatibility_percentage', 'porcentaje_compatibilidad'),
            ('strengths', 'fortalezas'),
            ('improvement_recommendations', 'recomendaciones_mejora'),
            ('evaluation_id', 'evaluacion_id'),
            ('is_met', 'cumplido'),
            ('score_percentage', 'porcentaje_puntuacion'),
            ('explanation', 'explicacion'),
            ('starts_at', 'inicia_en'),
            ('ends_at', 'termina_en'),
            ('timezone_name', 'zona_horaria'),
            ('meeting_url', 'url_reunion'),
            ('notes', 'notas'),
            ('recipient_user_id', 'usuario_destinatario_id'),
            ('type_code', 'codigo_tipo'),
            ('interview_id', 'entrevista_id'),
            ('message', 'mensaje'),
            ('read_at', 'leido_en'),
            ('notification_id', 'notificacion_id'),
            ('channel_code', 'codigo_canal'),
            ('recipient_address', 'direccion_destino'),
            ('scheduled_at', 'programado_en'),
            ('sent_at', 'enviado_en'),
            ('provider_message_id', 'id_mensaje_proveedor'),
            ('delivery_id', 'entrega_id'),
            ('attempted_at', 'intentado_en'),
            ('succeeded', 'exitoso')
        ) AS columnas(anterior, nuevo)
    LOOP
        FOR t IN
            SELECT table_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND column_name = m.anterior
        LOOP
            EXECUTE format(
                'ALTER TABLE public.%I RENAME COLUMN %I TO %I',
                t.table_name, m.anterior, m.nuevo
            );
        END LOOP;
    END LOOP;
END $$;

-- Codigos de catalogo sin relaciones por codigo.
UPDATE roles_usuario SET codigo = CASE codigo
    WHEN 'CANDIDATE' THEN 'ASPIRANTE'
    WHEN 'HR' THEN 'RRHH'
    WHEN 'ADMIN' THEN 'ADMINISTRADOR'
END;
UPDATE proveedores_almacenamiento SET codigo = CASE codigo
    WHEN 'S3' THEN 'AMAZON_S3'
    WHEN 'AZURE_BLOB' THEN 'BLOB_AZURE'
    ELSE codigo
END;
UPDATE niveles_habilidad SET codigo = CASE codigo
    WHEN 'BASIC' THEN 'BASICO'
    WHEN 'INTERMEDIATE' THEN 'INTERMEDIO'
    WHEN 'ADVANCED' THEN 'AVANZADO'
    WHEN 'EXPERT' THEN 'EXPERTO'
END;
UPDATE niveles_idioma SET codigo = 'NATIVO' WHERE codigo = 'NATIVE';

-- Estados de plaza.
UPDATE estados_plaza SET nombre = nombre || ' (anterior)';
INSERT INTO estados_plaza (codigo, nombre, es_final) VALUES
    ('BORRADOR', 'Pendiente', FALSE),
    ('PUBLICADA', 'Activa', FALSE),
    ('PAUSADA', 'Pausada', FALSE),
    ('CERRADA', 'Cerrada', TRUE);
UPDATE plazas SET codigo_estado = CASE codigo_estado
    WHEN 'DRAFT' THEN 'BORRADOR' WHEN 'PUBLISHED' THEN 'PUBLICADA'
    WHEN 'PAUSED' THEN 'PAUSADA' WHEN 'CLOSED' THEN 'CERRADA' END;
UPDATE historial_estados_plaza SET codigo_estado_anterior = CASE codigo_estado_anterior
    WHEN 'DRAFT' THEN 'BORRADOR' WHEN 'PUBLISHED' THEN 'PUBLICADA'
    WHEN 'PAUSED' THEN 'PAUSADA' WHEN 'CLOSED' THEN 'CERRADA' END
WHERE codigo_estado_anterior IS NOT NULL;
UPDATE historial_estados_plaza SET codigo_estado_nuevo = CASE codigo_estado_nuevo
    WHEN 'DRAFT' THEN 'BORRADOR' WHEN 'PUBLISHED' THEN 'PUBLICADA'
    WHEN 'PAUSED' THEN 'PAUSADA' WHEN 'CLOSED' THEN 'CERRADA' END;
ALTER TABLE plazas ALTER COLUMN codigo_estado SET DEFAULT 'BORRADOR';
DELETE FROM estados_plaza WHERE codigo IN ('DRAFT', 'PUBLISHED', 'PAUSED', 'CLOSED');
DROP INDEX public.idx_vacancies_published_closing;
CREATE INDEX indice_plazas_publicadas_cierre
    ON plazas(cierra_en, publicado_en DESC)
    WHERE codigo_estado = 'PUBLICADA';

-- Estados de postulacion.
UPDATE estados_postulacion SET nombre = nombre || ' (anterior)';
INSERT INTO estados_postulacion (codigo, nombre, es_final) VALUES
    ('ENVIADA', 'Enviada', FALSE),
    ('EN_REVISION', 'En revisión', FALSE),
    ('PRESELECCIONADA', 'Preseleccionada', FALSE),
    ('ENTREVISTA', 'Entrevista', FALSE),
    ('OFERTA_ENVIADA', 'Oferta enviada', FALSE),
    ('CONTRATADA', 'Contratada', TRUE),
    ('RECHAZADA', 'Rechazada', TRUE),
    ('RETIRADA', 'Retirada', TRUE);
UPDATE postulaciones SET codigo_estado = CASE codigo_estado
    WHEN 'SUBMITTED' THEN 'ENVIADA' WHEN 'UNDER_REVIEW' THEN 'EN_REVISION'
    WHEN 'SHORTLISTED' THEN 'PRESELECCIONADA' WHEN 'INTERVIEW' THEN 'ENTREVISTA'
    WHEN 'OFFERED' THEN 'OFERTA_ENVIADA' WHEN 'HIRED' THEN 'CONTRATADA'
    WHEN 'REJECTED' THEN 'RECHAZADA' WHEN 'WITHDRAWN' THEN 'RETIRADA' END;
UPDATE historial_estados_postulacion SET codigo_estado_anterior = CASE codigo_estado_anterior
    WHEN 'SUBMITTED' THEN 'ENVIADA' WHEN 'UNDER_REVIEW' THEN 'EN_REVISION'
    WHEN 'SHORTLISTED' THEN 'PRESELECCIONADA' WHEN 'INTERVIEW' THEN 'ENTREVISTA'
    WHEN 'OFFERED' THEN 'OFERTA_ENVIADA' WHEN 'HIRED' THEN 'CONTRATADA'
    WHEN 'REJECTED' THEN 'RECHAZADA' WHEN 'WITHDRAWN' THEN 'RETIRADA' END
WHERE codigo_estado_anterior IS NOT NULL;
UPDATE historial_estados_postulacion SET codigo_estado_nuevo = CASE codigo_estado_nuevo
    WHEN 'SUBMITTED' THEN 'ENVIADA' WHEN 'UNDER_REVIEW' THEN 'EN_REVISION'
    WHEN 'SHORTLISTED' THEN 'PRESELECCIONADA' WHEN 'INTERVIEW' THEN 'ENTREVISTA'
    WHEN 'OFFERED' THEN 'OFERTA_ENVIADA' WHEN 'HIRED' THEN 'CONTRATADA'
    WHEN 'REJECTED' THEN 'RECHAZADA' WHEN 'WITHDRAWN' THEN 'RETIRADA' END;
ALTER TABLE postulaciones ALTER COLUMN codigo_estado SET DEFAULT 'ENVIADA';
DELETE FROM estados_postulacion WHERE codigo IN (
    'SUBMITTED', 'UNDER_REVIEW', 'SHORTLISTED', 'INTERVIEW',
    'OFFERED', 'HIRED', 'REJECTED', 'WITHDRAWN'
);

-- Estados compartidos de procesamiento.
UPDATE estados_procesamiento SET nombre = nombre || ' (anterior)';
INSERT INTO estados_procesamiento (codigo, nombre, es_final) VALUES
    ('PENDIENTE', 'Pendiente', FALSE),
    ('PROCESANDO', 'Procesando', FALSE),
    ('COMPLETADO', 'Completado', TRUE),
    ('FALLIDO', 'Fallido', TRUE);
UPDATE analisis_cv SET codigo_estado = CASE codigo_estado
    WHEN 'PENDING' THEN 'PENDIENTE' WHEN 'PROCESSING' THEN 'PROCESANDO'
    WHEN 'COMPLETED' THEN 'COMPLETADO' WHEN 'FAILED' THEN 'FALLIDO' END;
UPDATE evaluaciones_postulacion SET codigo_estado = CASE codigo_estado
    WHEN 'PENDING' THEN 'PENDIENTE' WHEN 'PROCESSING' THEN 'PROCESANDO'
    WHEN 'COMPLETED' THEN 'COMPLETADO' WHEN 'FAILED' THEN 'FALLIDO' END;
ALTER TABLE analisis_cv ALTER COLUMN codigo_estado SET DEFAULT 'PENDIENTE';
ALTER TABLE evaluaciones_postulacion ALTER COLUMN codigo_estado SET DEFAULT 'PENDIENTE';
DELETE FROM estados_procesamiento WHERE codigo IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED');

-- Tipos de requisito.
UPDATE tipos_requisito SET nombre = nombre || ' (anterior)';
INSERT INTO tipos_requisito (codigo, nombre) VALUES
    ('HABILIDAD', 'Habilidad'), ('IDIOMA', 'Idioma'),
    ('CERTIFICACION', 'Certificación'), ('EDUCACION', 'Educación'),
    ('EXPERIENCIA', 'Experiencia'), ('DISPONIBILIDAD', 'Disponibilidad');
UPDATE requisitos_plaza SET codigo_tipo = CASE codigo_tipo
    WHEN 'SKILL' THEN 'HABILIDAD' WHEN 'LANGUAGE' THEN 'IDIOMA'
    WHEN 'CERTIFICATION' THEN 'CERTIFICACION' WHEN 'EDUCATION' THEN 'EDUCACION'
    WHEN 'EXPERIENCE' THEN 'EXPERIENCIA' WHEN 'AVAILABILITY' THEN 'DISPONIBILIDAD' END;
DELETE FROM tipos_requisito WHERE codigo IN (
    'SKILL', 'LANGUAGE', 'CERTIFICATION', 'EDUCATION', 'EXPERIENCE', 'AVAILABILITY'
);

-- Estados de entrevista.
UPDATE estados_entrevista SET nombre = nombre || ' (anterior)';
INSERT INTO estados_entrevista (codigo, nombre, es_final) VALUES
    ('PROGRAMADA', 'Programada', FALSE), ('CONFIRMADA', 'Confirmada', FALSE),
    ('COMPLETADA', 'Completada', TRUE), ('CANCELADA', 'Cancelada', TRUE),
    ('NO_ASISTIO', 'No asistió', TRUE);
UPDATE entrevistas SET codigo_estado = CASE codigo_estado
    WHEN 'SCHEDULED' THEN 'PROGRAMADA' WHEN 'CONFIRMED' THEN 'CONFIRMADA'
    WHEN 'COMPLETED' THEN 'COMPLETADA' WHEN 'CANCELLED' THEN 'CANCELADA'
    WHEN 'NO_SHOW' THEN 'NO_ASISTIO' END;
ALTER TABLE entrevistas ALTER COLUMN codigo_estado SET DEFAULT 'PROGRAMADA';
DELETE FROM estados_entrevista WHERE codigo IN (
    'SCHEDULED', 'CONFIRMED', 'COMPLETED', 'CANCELLED', 'NO_SHOW'
);

-- Tipos y canales de notificacion.
UPDATE tipos_notificacion SET nombre = nombre || ' (anterior)';
INSERT INTO tipos_notificacion (codigo, nombre) VALUES
    ('CONFIRMACION_POSTULACION', 'Confirmación de postulación'),
    ('CAMBIO_ESTADO', 'Cambio de estado'),
    ('INVITACION_ENTREVISTA', 'Invitación a entrevista');
UPDATE notificaciones SET codigo_tipo = CASE codigo_tipo
    WHEN 'APPLICATION_CONFIRMATION' THEN 'CONFIRMACION_POSTULACION'
    WHEN 'STATUS_CHANGED' THEN 'CAMBIO_ESTADO'
    WHEN 'INTERVIEW_INVITATION' THEN 'INVITACION_ENTREVISTA' END;
DELETE FROM tipos_notificacion WHERE codigo IN (
    'APPLICATION_CONFIRMATION', 'STATUS_CHANGED', 'INTERVIEW_INVITATION'
);

UPDATE canales_notificacion SET nombre = nombre || ' (anterior)';
INSERT INTO canales_notificacion (codigo, nombre) VALUES
    ('APLICACION', 'Aplicación'), ('CORREO', 'Correo electrónico');
UPDATE entregas_notificacion SET codigo_canal = CASE codigo_canal
    WHEN 'IN_APP' THEN 'APLICACION' WHEN 'EMAIL' THEN 'CORREO' END;
DELETE FROM canales_notificacion WHERE codigo IN ('IN_APP', 'EMAIL');

-- Estados de entrega.
UPDATE estados_entrega SET nombre = nombre || ' (anterior)';
INSERT INTO estados_entrega (codigo, nombre, es_final) VALUES
    ('PENDIENTE', 'Pendiente', FALSE), ('PROCESANDO', 'Procesando', FALSE),
    ('ENVIADO', 'Enviado', TRUE), ('FALLIDO', 'Fallido', TRUE);
UPDATE entregas_notificacion SET codigo_estado = CASE codigo_estado
    WHEN 'PENDING' THEN 'PENDIENTE' WHEN 'PROCESSING' THEN 'PROCESANDO'
    WHEN 'SENT' THEN 'ENVIADO' WHEN 'FAILED' THEN 'FALLIDO' END;
ALTER TABLE entregas_notificacion ALTER COLUMN codigo_estado SET DEFAULT 'PENDIENTE';
DELETE FROM estados_entrega WHERE codigo IN ('PENDING', 'PROCESSING', 'SENT', 'FAILED');

-- El indice parcial depende de un valor de catalogo traducido.
DROP INDEX public.idx_current_evaluation_compatibility;
CREATE INDEX indice_evaluaciones_compatibilidad_vigente
    ON evaluaciones_postulacion(porcentaje_compatibilidad DESC)
    WHERE vigente AND codigo_estado = 'COMPLETADO';

-- Renombra restricciones, incluidos los indices que las respaldan.
DO $$
DECLARE
    r RECORD;
    prefijo TEXT;
    nuevo_nombre TEXT;
BEGIN
    FOR r IN
        SELECT c.oid, c.conname, c.contype, t.relname AS tabla,
               row_number() OVER (PARTITION BY t.relname, c.contype ORDER BY c.conname) AS numero
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'public'
        ORDER BY t.relname, c.contype, c.conname
    LOOP
        prefijo := CASE r.contype
            WHEN 'p' THEN 'pk' WHEN 'f' THEN 'fk' WHEN 'u' THEN 'unico'
            WHEN 'c' THEN 'verifica' WHEN 'x' THEN 'excluye' ELSE 'restriccion'
        END;
        nuevo_nombre := left(prefijo || '_' || r.tabla || '_' || r.numero, 63);
        EXECUTE format(
            'ALTER TABLE public.%I RENAME CONSTRAINT %I TO %I',
            r.tabla, r.conname, nuevo_nombre
        );
    END LOOP;
END $$;

-- Renombra los indices no asociados a restricciones.
DO $$
DECLARE
    r RECORD;
    nuevo_nombre TEXT;
BEGIN
    FOR r IN
        SELECT i.indexrelid, ci.relname AS indice, ct.relname AS tabla,
               i.indisunique,
               row_number() OVER (PARTITION BY ct.relname, i.indisunique ORDER BY ci.relname) AS numero
        FROM pg_index i
        JOIN pg_class ci ON ci.oid = i.indexrelid
        JOIN pg_class ct ON ct.oid = i.indrelid
        JOIN pg_namespace n ON n.oid = ct.relnamespace
        LEFT JOIN pg_constraint c ON c.conindid = i.indexrelid
        WHERE n.nspname = 'public' AND c.oid IS NULL
        ORDER BY ct.relname, i.indisunique, ci.relname
    LOOP
        nuevo_nombre := left(
            CASE WHEN r.indisunique THEN 'indice_unico_' ELSE 'indice_' END
            || r.tabla || '_' || r.numero,
            63
        );
        IF r.indice <> nuevo_nombre THEN
            EXECUTE format('ALTER INDEX public.%I RENAME TO %I', r.indice, nuevo_nombre);
        END IF;
    END LOOP;
END $$;

-- Renombra las secuencias de identidad segun su tabla y columna propietarias.
DO $$
DECLARE
    r RECORD;
    nuevo_nombre TEXT;
BEGIN
    FOR r IN
        SELECT s.relname AS secuencia, t.relname AS tabla, a.attname AS columna
        FROM pg_class s
        JOIN pg_namespace ns ON ns.oid = s.relnamespace
        JOIN pg_depend d ON d.objid = s.oid AND d.deptype IN ('a', 'i')
        JOIN pg_class t ON t.oid = d.refobjid
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = d.refobjsubid
        WHERE s.relkind = 'S' AND ns.nspname = 'public'
        ORDER BY s.relname
    LOOP
        nuevo_nombre := left('secuencia_' || r.tabla || '_' || r.columna, 63);
        IF r.secuencia <> nuevo_nombre THEN
            EXECUTE format('ALTER SEQUENCE public.%I RENAME TO %I', r.secuencia, nuevo_nombre);
        END IF;
    END LOOP;
END $$;

COMMIT;

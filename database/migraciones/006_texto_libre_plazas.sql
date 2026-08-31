ALTER TABLE plazas
    ADD COLUMN IF NOT EXISTS departamento_texto VARCHAR(120),
    ADD COLUMN IF NOT EXISTS profesion_texto VARCHAR(150),
    ADD COLUMN IF NOT EXISTS ciudad_texto VARCHAR(120),
    ADD COLUMN IF NOT EXISTS tipo_empleo_texto VARCHAR(80),
    ADD COLUMN IF NOT EXISTS modalidad_trabajo_texto VARCHAR(80),
    ADD COLUMN IF NOT EXISTS periodo_salarial_texto VARCHAR(80);

ALTER TABLE requisitos_experiencia
    ADD COLUMN IF NOT EXISTS profesion_texto VARCHAR(150);

ALTER TABLE requisitos_educacion
    ADD COLUMN IF NOT EXISTS nivel_educativo_texto VARCHAR(100),
    ADD COLUMN IF NOT EXISTS area_estudio_texto VARCHAR(150);

ALTER TABLE requisitos_habilidad
    ADD COLUMN IF NOT EXISTS habilidad_texto VARCHAR(150),
    ADD COLUMN IF NOT EXISTS nivel_habilidad_minimo_texto VARCHAR(80);

ALTER TABLE requisitos_idioma
    ADD COLUMN IF NOT EXISTS idioma_texto VARCHAR(80),
    ADD COLUMN IF NOT EXISTS nivel_idioma_minimo_texto VARCHAR(80);

ALTER TABLE requisitos_certificacion
    ADD COLUMN IF NOT EXISTS certificacion_texto VARCHAR(180);

UPDATE plazas AS plaza
SET departamento_texto = departamento.nombre
FROM departamentos AS departamento
WHERE plaza.departamento_id = departamento.id
  AND NULLIF(BTRIM(plaza.departamento_texto), '') IS NULL;

UPDATE plazas AS plaza
SET profesion_texto = profesion.nombre
FROM profesiones AS profesion
WHERE plaza.profesion_id = profesion.id
  AND NULLIF(BTRIM(plaza.profesion_texto), '') IS NULL;

UPDATE plazas AS plaza
SET ciudad_texto = ciudad.nombre
FROM ciudades AS ciudad
WHERE plaza.ciudad_id = ciudad.id
  AND NULLIF(BTRIM(plaza.ciudad_texto), '') IS NULL;

UPDATE plazas AS plaza
SET tipo_empleo_texto = tipo_empleo.nombre
FROM tipos_empleo AS tipo_empleo
WHERE plaza.tipo_empleo_id = tipo_empleo.id
  AND NULLIF(BTRIM(plaza.tipo_empleo_texto), '') IS NULL;

UPDATE plazas AS plaza
SET modalidad_trabajo_texto = modalidad.nombre
FROM modalidades_trabajo AS modalidad
WHERE plaza.modalidad_trabajo_id = modalidad.id
  AND NULLIF(BTRIM(plaza.modalidad_trabajo_texto), '') IS NULL;

UPDATE plazas AS plaza
SET periodo_salarial_texto = periodo.nombre
FROM periodos_salariales AS periodo
WHERE plaza.periodo_salarial_id = periodo.id
  AND NULLIF(BTRIM(plaza.periodo_salarial_texto), '') IS NULL;

UPDATE requisitos_experiencia AS requisito
SET profesion_texto = profesion.nombre
FROM profesiones AS profesion
WHERE requisito.profesion_id = profesion.id
  AND NULLIF(BTRIM(requisito.profesion_texto), '') IS NULL;

UPDATE requisitos_educacion AS requisito
SET nivel_educativo_texto = nivel.nombre
FROM niveles_educativos AS nivel
WHERE requisito.nivel_educativo_minimo_id = nivel.id
  AND NULLIF(BTRIM(requisito.nivel_educativo_texto), '') IS NULL;

UPDATE requisitos_educacion AS requisito
SET area_estudio_texto = area.nombre
FROM areas_estudio AS area
WHERE requisito.area_estudio_id = area.id
  AND NULLIF(BTRIM(requisito.area_estudio_texto), '') IS NULL;

UPDATE requisitos_habilidad AS requisito
SET habilidad_texto = habilidad.nombre
FROM habilidades AS habilidad
WHERE requisito.habilidad_id = habilidad.id
  AND NULLIF(BTRIM(requisito.habilidad_texto), '') IS NULL;

UPDATE requisitos_habilidad AS requisito
SET nivel_habilidad_minimo_texto = nivel.nombre
FROM niveles_habilidad AS nivel
WHERE requisito.nivel_habilidad_minimo_id = nivel.id
  AND NULLIF(BTRIM(requisito.nivel_habilidad_minimo_texto), '') IS NULL;

UPDATE requisitos_idioma AS requisito
SET idioma_texto = idioma.nombre
FROM idiomas AS idioma
WHERE requisito.idioma_id = idioma.id
  AND NULLIF(BTRIM(requisito.idioma_texto), '') IS NULL;

UPDATE requisitos_idioma AS requisito
SET nivel_idioma_minimo_texto = nivel.nombre
FROM niveles_idioma AS nivel
WHERE requisito.nivel_idioma_minimo_id = nivel.id
  AND NULLIF(BTRIM(requisito.nivel_idioma_minimo_texto), '') IS NULL;

UPDATE requisitos_certificacion AS requisito
SET certificacion_texto = certificacion.nombre
FROM certificaciones AS certificacion
WHERE requisito.certificacion_id = certificacion.id
  AND NULLIF(BTRIM(requisito.certificacion_texto), '') IS NULL;

ALTER TABLE plazas
    ALTER COLUMN departamento_id DROP NOT NULL,
    ALTER COLUMN tipo_empleo_id DROP NOT NULL,
    ALTER COLUMN modalidad_trabajo_id DROP NOT NULL;

ALTER TABLE requisitos_educacion
    ALTER COLUMN nivel_educativo_minimo_id DROP NOT NULL;

ALTER TABLE requisitos_habilidad
    ALTER COLUMN habilidad_id DROP NOT NULL;

ALTER TABLE requisitos_idioma
    ALTER COLUMN idioma_id DROP NOT NULL,
    ALTER COLUMN nivel_idioma_minimo_id DROP NOT NULL;

ALTER TABLE requisitos_certificacion
    ALTER COLUMN certificacion_id DROP NOT NULL;

CREATE INDEX IF NOT EXISTS indice_plazas_departamento_texto
    ON plazas(departamento_texto);

CREATE INDEX IF NOT EXISTS indice_plazas_profesion_texto
    ON plazas(profesion_texto);

CREATE INDEX IF NOT EXISTS indice_plazas_ciudad_texto
    ON plazas(ciudad_texto);

CREATE INDEX IF NOT EXISTS indice_plazas_tipo_empleo_texto
    ON plazas(tipo_empleo_texto);

CREATE INDEX IF NOT EXISTS indice_plazas_modalidad_trabajo_texto
    ON plazas(modalidad_trabajo_texto);

CREATE INDEX IF NOT EXISTS indice_plazas_periodo_salarial_texto
    ON plazas(periodo_salarial_texto);

CREATE INDEX IF NOT EXISTS indice_requisitos_experiencia_profesion_texto
    ON requisitos_experiencia(profesion_texto);

CREATE INDEX IF NOT EXISTS indice_requisitos_educacion_nivel_texto
    ON requisitos_educacion(nivel_educativo_texto);

CREATE INDEX IF NOT EXISTS indice_requisitos_educacion_area_texto
    ON requisitos_educacion(area_estudio_texto);

CREATE INDEX IF NOT EXISTS indice_requisitos_habilidad_texto
    ON requisitos_habilidad(habilidad_texto);

CREATE INDEX IF NOT EXISTS indice_requisitos_idioma_texto
    ON requisitos_idioma(idioma_texto);

CREATE INDEX IF NOT EXISTS indice_requisitos_certificacion_texto
    ON requisitos_certificacion(certificacion_texto);

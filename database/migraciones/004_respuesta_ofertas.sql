-- Conserva la respuesta original aunque una oferta aceptada sea cancelada después.

ALTER TABLE ofertas_laborales
    ADD COLUMN IF NOT EXISTS respuesta VARCHAR(20);

UPDATE ofertas_laborales
SET respuesta = codigo_estado
WHERE codigo_estado IN ('ACEPTADA', 'RECHAZADA')
  AND respuesta IS NULL;

ALTER TABLE ofertas_laborales
    DROP CONSTRAINT IF EXISTS verifica_oferta_estado_respuesta;

ALTER TABLE ofertas_laborales
    ADD CONSTRAINT verifica_oferta_estado_respuesta
    CHECK (
        (codigo_estado = 'ACEPTADA' AND respuesta = 'ACEPTADA' AND respondida_en IS NOT NULL)
        OR
        (codigo_estado = 'RECHAZADA' AND respuesta = 'RECHAZADA' AND respondida_en IS NOT NULL)
        OR
        (codigo_estado IN ('ENVIADA', 'VENCIDA') AND respuesta IS NULL AND respondida_en IS NULL)
        OR
        (
            codigo_estado = 'CANCELADA'
            AND (
                (respuesta IS NULL AND respondida_en IS NULL)
                OR
                (respuesta IN ('ACEPTADA', 'RECHAZADA') AND respondida_en IS NOT NULL)
            )
        )
    );

ALTER TABLE plazas
    DROP CONSTRAINT IF EXISTS verifica_plazas_2;

ALTER TABLE plazas
    ADD CONSTRAINT verifica_plazas_2 CHECK (
        (
            salario_minimo IS NULL
            AND salario_maximo IS NULL
            AND codigo_moneda IS NULL
            AND periodo_salarial_id IS NULL
            AND NULLIF(BTRIM(periodo_salarial_texto), '') IS NULL
        )
        OR (
            codigo_moneda IS NOT NULL
            AND (
                periodo_salarial_id IS NOT NULL
                OR NULLIF(BTRIM(periodo_salarial_texto), '') IS NOT NULL
            )
        )
    );

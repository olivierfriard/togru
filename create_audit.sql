
CREATE TABLE IF NOT EXISTS inventario_audit (
    id SERIAL PRIMARY KEY,
    operation_type TEXT NOT NULL, -- 'INSERT', 'UPDATE', 'DELETE'
    table_name TEXT NOT NULL,
    record_id INTEGER, -- il campo id della tabella inventario
    old_data JSONB,                                                   
    new_data JSONB,                                       
    executed_by TEXT,
    executed_at TIMESTAMP DEFAULT now()
);




CREATE OR REPLACE FUNCTION log_inventario_changes()
RETURNS TRIGGER AS $$
DECLARE
    username TEXT;
BEGIN
    -- Recupera il nome utente dalla variabile di sessione
    username := current_setting('application_name', true);

    -- Log INSERT
    IF (TG_OP = 'INSERT') THEN
        INSERT INTO inventario_audit (
            operation_type, table_name, record_id, new_data, executed_by
        ) VALUES (
            'INSERT', TG_TABLE_NAME, NEW.id, to_jsonb(NEW), username
        );
        RETURN NEW;
    END IF;

    -- Log UPDATE
    IF (TG_OP = 'UPDATE') THEN
        INSERT INTO inventario_audit (
            operation_type, table_name, record_id, old_data, new_data, executed_by
        ) VALUES (
            'UPDATE', TG_TABLE_NAME, NEW.id, to_jsonb(OLD), to_jsonb(NEW), username
        );
        RETURN NEW;
    END IF;

    -- Log DELETE
    IF (TG_OP = 'DELETE') THEN
        INSERT INTO inventario_audit (
            operation_type, table_name, record_id, old_data, executed_by
        ) VALUES (
            'DELETE', TG_TABLE_NAME, OLD.id, to_jsonb(OLD), username
        );
        RETURN OLD;
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;



DROP TRIGGER IF EXISTS inventario_audit_trigger ON inventario;

CREATE TRIGGER inventario_audit_trigger
AFTER INSERT OR UPDATE OR DELETE ON inventario
FOR EACH ROW
EXECUTE FUNCTION log_inventario_changes();


select unique_id
from {{ info_schema('models') }}
where original_file_path like 'models/intermediate/%'
    and not regexp_matches(name, '^int_[a-z0-9_]+$')

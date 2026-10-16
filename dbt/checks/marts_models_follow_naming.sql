select unique_id
from {{ info_schema('models') }}
where original_file_path like 'models/marts/%'
    and not regexp_matches(name, '^(fct|dim)_[a-z0-9_]+$')

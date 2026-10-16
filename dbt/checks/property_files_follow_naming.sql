select unique_id
from {{ info_schema('models') }}
where not regexp_matches(
    properties_yml_file_path,
    '/_[a-z0-9_]+__models\.yml$'
)

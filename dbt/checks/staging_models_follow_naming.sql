with

staging_models as (

    select
        unique_id,
        name,
        original_file_path,
        regexp_extract(
            original_file_path,
            '^models/staging/([a-z0-9_]+)/',
            1
        ) as source_name
    from {{ info_schema('models') }}
    where original_file_path like 'models/staging/%'

)

select unique_id
from staging_models
where source_name = ''
    or not (
        starts_with(name, 'stg_' || source_name || '__')
        or (
            original_file_path like '%/base/%'
            and starts_with(name, 'base_' || source_name || '__')
        )
    )

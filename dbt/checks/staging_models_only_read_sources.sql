select
    child.unique_id,
    edges.parent_unique_id
from {{ info_schema('edges') }} as edges
inner join {{ info_schema('models') }} as child
    on edges.child_unique_id = child.unique_id
inner join {{ info_schema('models') }} as parent
    on edges.parent_unique_id = parent.unique_id
where child.original_file_path like 'models/staging/%'
    and child.original_file_path not like '%/base/%'
    and parent.original_file_path not like '%/base/%'

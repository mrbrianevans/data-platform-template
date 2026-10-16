select
    child.unique_id,
    edges.parent_unique_id
from {{ info_schema('edges') }} as edges
inner join {{ info_schema('models') }} as child
    on edges.child_unique_id = child.unique_id
where edges.parent_unique_id like 'source.%'
    and child.original_file_path not like 'models/staging/%'

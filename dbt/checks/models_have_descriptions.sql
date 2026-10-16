select unique_id
from {{ info_schema('models') }}
where description is null or trim(description) = ''

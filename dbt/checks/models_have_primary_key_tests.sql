select unique_id
from {{ info_schema('models') }}
where primary_key is null or len(primary_key) = 0

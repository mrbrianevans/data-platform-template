{% macro json_string(column, field) -%}
    {{ return(adapter.dispatch('json_string', 'data_platform')(column, field)) }}
{%- endmacro %}

{% macro default__json_string(column, field) -%}
    json_extract_string({{ column }}, '$.{{ field }}')
{%- endmacro %}

{% macro bigquery__json_string(column, field) -%}
    json_value({{ column }}, '$.{{ field }}')
{%- endmacro %}

{% macro duckdb__json_string(column, field) -%}
    json_extract_string({{ column }}, '$.{{ field }}')
{%- endmacro %}

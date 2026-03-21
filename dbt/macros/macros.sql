-- dbt macros for reusable SQL functions
-- ecommerce_analytics/dbt/macros/macros.sql

{% macro generate_surrogate_key(field_list) %}
    {% for field in field_list %}
        {{ dbt_utils.generate_surrogate_key([field]) }}
    {% endfor %}
{% endmacro %}


{% macro calculate_recency(last_purchase_date, snapshot_date) %}
    datediff(day, {{ last_purchase_date }}, {{ snapshot_date }})
{% endmacro %}


{% macro assign_rfm_segment(r_score, f_score, m_score) %}
    case
        when {{ r_score }} >= 4 and {{ f_score }} >= 4 then 'Champions'
        when {{ r_score }} >= 3 and {{ f_score }} >= 3 then 'Loyal Customers'
        when {{ r_score }} >= 4 and {{ f_score }} <= 2 then 'Potential Loyalists'
        when {{ r_score }} <= 2 and {{ f_score }} >= 3 then 'At Risk'
        when {{ r_score }} <= 2 and {{ f_score }} <= 2 then 'Hibernating'
        when {{ r_score }} = 1 then 'Lost'
        else 'Regular'
    end
{% endmacro %}


{% macro calculate_clv(aov, frequency, margin, retention_months) %}
    {{ aov }} * {{ frequency }} * {{ margin }} * ({{ retention_months }} / 12.0)
{% endmacro %}


{% macro test_positive_values(model, column_name) %}
    select *
    from {{ model }}
    where {{ column_name }} <= 0
{% endmacro %}


{% macro test_valid_date_range(model, column_name, min_date, max_date) %}
    select *
    from {{ model }}
    where {{ column_name }} < {{ min_date }}
       or {{ column_name }} > {{ max_date }}
{% endmacro %}


{% macro get_segment_metrics(segment_name) %}
    {% set metrics = {
        'Champions': {'multiplier': 1.5, 'priority': 1},
        'Loyal Customers': {'multiplier': 1.2, 'priority': 2},
        'Potential Loyalists': {'multiplier': 1.0, 'priority': 3},
        'At Risk': {'multiplier': 0.5, 'priority': 4},
        'Hibernating': {'multiplier': 0.3, 'priority': 5},
        'Lost': {'multiplier': 0.1, 'priority': 6},
        'Regular': {'multiplier': 0.7, 'priority': 3}
    } %}
    
    {% if segment_name in metrics %}
        {{ return(metrics[segment_name]) }}
    {% else %}
        {{ return({'multiplier': 0.7, 'priority': 3}) }}
    {% endif %}
{% endmacro %}

"""
title: myToolName
author: myName
funding_url: [any link here will be shown behind a `Heart` button for users to show their support to you]
version: 1.0.0
# the version is displayed in the UI to help users keep track of updates.
license: GPLv3
description: a tool which will help to generate redshift sql queries based on user input and run them against a redshift database
requirements: sqlalchemy-redshift,psycopg2-binary
"""

import logging
from pydantic import Field
from sqlalchemy import create_engine, text
import re

# --------------------------
# Logging
# --------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OpenWebUI_Tools")
logger.setLevel(logging.DEBUG)

# --------------------------
# Table schemas
# --------------------------
schemas = {
    "api__intermediate__orders": {
        "description": """
            The `api__intermediate__orders` table provides intermediate order-level data,
            including identifiers, timestamps, delivery times, status, payment information,
            customer details, and system metadata. This model is a staging layer designed
            to standardize order information before further analytics transformations.
        """,
        "config": {
            "tags": ["api", "analytics"],
            "meta": {"dagster": {"group": "analytics"}},
        },
        "columns": [
            {
                "name": "order_id",
                "type": "bigint",
                "description": "Unique order ID",
                "tests": ["unique", "not_null"],
            },
            {
                "name": "order_created_at_date",
                "type": "date",
                "description": "Date when order was created",
            },
            {
                "name": "order_delivered_in_days",
                "type": "bigint",
                "description": "Days taken for delivery",
            },
            {
                "name": "order_delivered_in_hours",
                "type": "bigint",
                "description": "Hours taken for delivery",
            },
            {
                "name": "order_delivered_at_date",
                "type": "date",
                "description": "Date when order was delivered",
            },
            {
                "name": "order_canceled_returned_at_date",
                "type": "date",
                "description": "Date when order was canceled or returned",
            },
            {
                "name": "store_id",
                "type": "integer",
                "description": "Unique identifier of the store",
            },
            {
                "name": "customer_id",
                "type": "integer",
                "description": "Unique identifier of the customer",
            },
            {
                "name": "customer_name",
                "type": "varchar(765)",
                "description": "Name of the customer",
            },
            {
                "name": "order_status_name",
                "type": "varchar(17)",
                "description": "Order status (English)",
            },
            {
                "name": "order_total_value",
                "type": "numeric(25,14)",
                "description": "Total value of the order",
            },
            {
                "name": "order_total_value_converted",
                "type": "numeric(25,14)",
                "description": "Converted total order value in store currency",
            },
            {
                "name": "payment_option_name",
                "type": "varchar(20)",
                "description": "Payment option name (English)",
            },
            {
                "name": "last_updated_at_utc",
                "type": "timestamp",
                "description": "Last updated timestamp (UTC)",
            },
            {
                "name": "refreshed_at_utc",
                "type": "timestamp",
                "description": "Data refreshed timestamp (UTC)",
            },
            {
                "name": "run_started_at_utc",
                "type": "timestamp",
                "description": "ETL run started timestamp (UTC)",
            },
        ],
    },
    "api__analytics__abandoned_carts": {
        "description": """
            The `api__analytics__abandoned_carts` tracks information about shopping carts
            that were not converted into completed orders. This helps in understanding
            potential revenue loss, identifying points of friction in the checkout process,
            and informing re-engagement strategies.
        """,
        "config": {
            "tags": ["api", "analytics"],
            "meta": {"dagster": {"group": "analytics"}},
        },
        "tests": [
            {
                "dbt_expectations.expect_compound_columns_to_be_unique": {
                    "column_list": ["cart_id", "cart_phase"],
                    "ignore_row_if": "any_value_is_missing",
                }
            }
        ],
        "columns": [
            {
                "name": "cart_id",
                "type": "character varying",
                "description": "The unique identifier for the abandoned cart.",
            },
            {
                "name": "store_id",
                "type": "bigint",
                "description": "The unique identifier for the store where the cart was created.",
            },
            {
                "name": "cart_phase",
                "type": "character varying",
                "description": "The current phase of the cart (e.g., 'initiated', 'shipping_info', 'payment_info', 'abandoned').",
            },
            {
                "name": "converted_cart",
                "type": "integer",
                "description": "A flag indicating whether the abandoned cart was eventually converted into an order (1 for converted, 0 for not converted).",
            },
            {
                "name": "cart_created_at",
                "type": "date",
                "description": "The date when the cart was created.",
            },
            {
                "name": "cart_total_value",
                "type": "numeric",
                "description": "The total value of the items in the cart in its original currency.",
            },
            {
                "name": "cart_total_value_converted",
                "type": "numeric",
                "description": "The total value of the items in the cart converted to a standard currency.",
            },
            {
                "name": "last_updated_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the record was last updated.",
            },
            {
                "name": "refreshed_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the data was last refreshed.",
            },
            {
                "name": "run_started_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the data processing run for this record started.",
            },
            {
                "name": "invocation_id",
                "type": "character varying",
                "description": "A unique identifier for the data processing invocation.",
            },
        ],
    },
    "api__analytics__coupons": {
        "description": """
            The `api__analytics__coupons` table provides detailed insights into the performance
            and usage of discount coupons within the Zid platform.
        """,
        "config": {
            "tags": ["api", "analytics"],
            "meta": {"dagster": {"group": "analytics"}},
        },
        "tests": [
            {
                "dbt_expectations.expect_compound_columns_to_be_unique": {
                    "column_list": ["store_id", "coupon_usage_date", "coupon_id"],
                    "ignore_row_if": "any_value_is_missing",
                }
            }
        ],
        "columns": [
            {
                "name": "store_id",
                "type": "integer",
                "description": "The unique identifier for the store where the coupon was created or used.",
            },
            {
                "name": "coupon_id",
                "type": "bigint",
                "description": "The unique identifier for the coupon.",
            },
            {
                "name": "coupon_code",
                "type": "character varying",
                "description": "The unique code associated with the coupon.",
            },
            {
                "name": "coupon_name",
                "type": "character varying",
                "description": "The name or description of the coupon.",
            },
            {
                "name": "discount_type",
                "type": "character varying",
                "description": "The type of discount offered by the coupon (percentage or fixed_amount).",
            },
            {
                "name": "discount_amount",
                "type": "numeric",
                "description": "The amount of discount offered.",
            },
            {
                "name": "coupon_status",
                "type": "character varying",
                "description": "The current status of the coupon (active, expired, inactive).",
            },
            {
                "name": "is_coupon_active",
                "type": "boolean",
                "description": "A boolean flag indicating if the coupon is currently active.",
            },
            {
                "name": "coupon_new_status",
                "type": "character varying",
                "description": "The updated or refined status of the coupon, if applicable.",
            },
            {
                "name": "coupon_apply_to",
                "type": "character varying",
                "description": "Indicates what the coupon applies to (e.g., 'all_products').",
            },
            {
                "name": "coupon_usage_limit",
                "type": "integer",
                "description": "The maximum number of times the coupon can be used in total.",
            },
            {
                "name": "coupon_usage_limit_per_customer",
                "type": "character varying",
                "description": "The maximum number of times a single customer can use the coupon.",
            },
            {
                "name": "minimum_order_total",
                "type": "numeric",
                "description": "The minimum order total required for the coupon to be applicable.",
            },
            {
                "name": "is_coupon_free_cod",
                "type": "boolean",
                "description": "A boolean flag indicating if the coupon offers free Cash on Delivery (COD).",
            },
            {
                "name": "is_coupon_shipping",
                "type": "boolean",
                "description": "A boolean flag indicating if the coupon offers a discount on shipping.",
            },
            {
                "name": "coupon_created_at",
                "type": "date",
                "description": "The date when the coupon was created.",
            },
            {
                "name": "coupon_start_date",
                "type": "date",
                "description": "The date from which the coupon becomes active.",
            },
            {
                "name": "coupon_end_date",
                "type": "date",
                "description": "The date when the coupon expires.",
            },
            {
                "name": "coupon_usage_date",
                "type": "date",
                "description": "The date when the coupon was last used.",
            },
            {
                "name": "coupon_usage_count",
                "type": "bigint",
                "description": "The total number of times the coupon has been used across all customers.",
            },
            {
                "name": "customers_count",
                "type": "bigint",
                "description": "The number of unique customers who have used the coupon.",
            },
            {
                "name": "discounted_amount",
                "type": "numeric",
                "description": "The total monetary value discounted by this coupon in its original currency.",
            },
            {
                "name": "discounted_amount_converted",
                "type": "numeric",
                "description": "The total monetary value discounted by this coupon converted to a standard currency.",
            },
            {
                "name": "total_value_after_discount",
                "type": "numeric",
                "description": "The total value of orders after applying this coupon's discount in its original currency.",
            },
            {
                "name": "total_value_after_discount_converted",
                "type": "numeric",
                "description": "The total value of orders after applying this coupon's discount converted to a standard currency.",
            },
            {
                "name": "last_updated_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the record was last updated.",
            },
            {
                "name": "refreshed_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the data was last refreshed.",
            },
            {
                "name": "run_started_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the data processing run for this record started.",
            },
            {
                "name": "invocation_id",
                "type": "character varying",
                "description": "A unique identifier for the data processing invocation.",
            },
        ],
    },
    "api__analytics__customers": {
        "description": """
            The `api__analytics__customers` table provides a detailed view of customer data,
            focusing on their demographics, purchasing behavior, and geographical information.
        """,
        "config": {
            "tags": ["api", "analytics"],
            "meta": {"dagster": {"group": "analytics"}},
        },
        "tests": [
            {
                "dbt_expectations.expect_compound_columns_to_be_unique": {
                    "column_list": [
                        "store_id",
                        "customer_id",
                        "shipping_address_city_id",
                        "shipping_address_country_id",
                    ],
                    "ignore_row_if": "any_value_is_missing",
                }
            }
        ],
        "columns": [
            {
                "name": "customer_id",
                "type": "bigint",
                "description": "The unique identifier for the customer.",
            },
            {
                "name": "store_id",
                "type": "bigint",
                "description": "The unique identifier for the store the customer is associated with.",
            },
            {
                "name": "customer_name",
                "type": "character varying",
                "description": "The name of the customer.",
            },
            {
                "name": "customer_joined_store_date",
                "type": "date",
                "description": "The date when the customer first joined or became associated with the store.",
            },
            {
                "name": "shipping_address_city_id",
                "type": "bigint",
                "description": "The unique identifier for the city in the customer's primary shipping address.",
            },
            {
                "name": "shipping_address_country_id",
                "type": "bigint",
                "description": "The unique identifier for the country in the customer's primary shipping address.",
            },
            {
                "name": "customer_type",
                "type": "character varying",
                "description": "The type or category of the customer.",
            },
            {
                "name": "customer_gender",
                "type": "character varying",
                "description": "The gender of the customer.",
            },
            {
                "name": "customer_city_name",
                "type": "character varying",
                "description": "The name of the customer's city in English.",
            },
            {
                "name": "customer_city_name_ar",
                "type": "character varying",
                "description": "The name of the customer's city in Arabic.",
            },
            {
                "name": "customer_country_name",
                "type": "character varying",
                "description": "The name of the customer's country in English.",
            },
            {
                "name": "customer_country_name_ar",
                "type": "character varying",
                "description": "The name of the customer's country in Arabic.",
            },
            {
                "name": "city_lon",
                "type": "double precision",
                "description": "The longitude of the customer's primary city.",
            },
            {
                "name": "city_lat",
                "type": "double precision",
                "description": "The latitude of the customer's primary city.",
            },
            {
                "name": "first_order_date",
                "type": "date",
                "description": "The date of the customer's first order.",
            },
            {
                "name": "last_order_date",
                "type": "date",
                "description": "The date of the customer's most recent order.",
            },
            {
                "name": "days_since_last_order",
                "type": "bigint",
                "description": "The number of days since the customer's last order.",
            },
            {
                "name": "customer_lifetime_days",
                "type": "bigint",
                "description": "The total number of days the customer has been active since joining the store.",
            },
            {
                "name": "orders_count",
                "type": "bigint",
                "description": "The total number of orders placed by the customer.",
            },
            {
                "name": "orders_total_value",
                "type": "numeric",
                "description": "The total monetary value of all orders placed by the customer in its original currency.",
            },
            {
                "name": "orders_total_value_converted",
                "type": "numeric",
                "description": "The total monetary value of all orders placed by the customer converted to a standard currency.",
            },
            {
                "name": "delivered_orders_count",
                "type": "bigint",
                "description": "The total number of orders successfully delivered to the customer.",
            },
            {
                "name": "delivered_orders_total_value_converted",
                "type": "numeric",
                "description": "The total monetary value of delivered orders to the customer converted to a standard currency.",
            },
            {
                "name": "avg_basket_size",
                "type": "numeric",
                "description": "The average value of items in the customer's orders.",
            },
            {
                "name": "last_updated_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the record was last updated.",
            },
            {
                "name": "refreshed_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the data was last refreshed.",
            },
            {
                "name": "run_started_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the data processing run for this record started.",
            },
            {
                "name": "invocation_id",
                "type": "character varying",
                "description": "A unique identifier for the data processing invocation.",
            },
        ],
    },
    "api__analytics__discount_rules": {
        "description": """
            The `api__analytics__discount_rules` table provides comprehensive data on the performance
            and impact of automated discount rules applied within the Zid platform.
        """,
        "config": {
            "tags": ["api", "analytics", "discount_rules"],
            "meta": {"dagster": {"group": "analytics"}},
        },
        "tests": [
            {
                "dbt_expectations.expect_compound_columns_to_be_unique": {
                    "column_list": [
                        "store_id",
                        "discount_rule_usage_date",
                        "discount_rule_id",
                    ],
                    "ignore_row_if": "any_value_is_missing",
                }
            }
        ],
        "columns": [
            {
                "name": "discount_rule_id",
                "type": "character varying",
                "description": "The unique identifier for the discount rule.",
            },
            {
                "name": "store_id",
                "type": "integer",
                "description": "The unique identifier for the store where the discount rule was applied.",
            },
            {
                "name": "discount_rule_name",
                "type": "character varying",
                "description": "The name of the discount rule in English.",
            },
            {
                "name": "discount_rule_name_ar",
                "type": "character varying",
                "description": "The name of the discount rule in Arabic.",
            },
            {
                "name": "discount_type",
                "type": "character varying",
                "description": "The type of discount applied by the rule (percentage, fixed_amount, free_shipping, buy_x_get_y).",
            },
            {
                "name": "discount_rule_usage_date",
                "type": "date",
                "description": "The date when the discount rule was applied.",
            },
            {
                "name": "discount_rule_usage_count",
                "type": "bigint",
                "description": "The total number of times the discount rule has been used.",
            },
            {
                "name": "customers_count",
                "type": "bigint",
                "description": "The number of unique customers who benefited from this discount rule.",
            },
            {
                "name": "total_value_after_discount",
                "type": "numeric",
                "description": "The total value of orders after the discount rule was applied, in its original currency.",
            },
            {
                "name": "total_value_after_discount_converted",
                "type": "numeric",
                "description": "The total value of orders after the discount rule was applied, converted to a standard currency.",
            },
            {
                "name": "total_discount_value",
                "type": "numeric",
                "description": "The total monetary value of the discount applied by this rule in its original currency.",
            },
            {
                "name": "total_discount_value_converted",
                "type": "numeric",
                "description": "The total monetary value of the discount applied by this rule converted to a standard currency.",
            },
            {
                "name": "last_updated_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the record was last updated.",
            },
            {
                "name": "refreshed_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the data was last refreshed.",
            },
            {
                "name": "run_started_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the data processing run for this record started.",
            },
            {
                "name": "invocation_id",
                "type": "character varying",
                "description": "A unique identifier for the data processing invocation.",
            },
        ],
    },
    "api__analytics__inventories": {
        "description": """
            The `api__analytics__inventories` table provides analytical data on inventory locations
            and their association with order performance within the Zid platform.
        """,
        "config": {
            "tags": ["api", "analytics", "inventories"],
            "meta": {"dagster": {"group": "analytics"}},
        },
        "tests": [
            {
                "dbt_expectations.expect_compound_columns_to_be_unique": {
                    "column_list": ["store_id", "order_date", "inventory_location_id"],
                    "ignore_row_if": "any_value_is_missing",
                }
            }
        ],
        "columns": [
            {
                "name": "inventory_location_id",
                "type": "character varying",
                "description": "The unique identifier for the inventory location.",
            },
            {
                "name": "store_id",
                "type": "integer",
                "description": "The unique identifier for the store associated with this inventory location.",
            },
            {
                "name": "order_date",
                "type": "date",
                "description": "The date on which orders associated with this inventory location were placed.",
            },
            {
                "name": "inventory_name",
                "type": "character varying",
                "description": "The name of the inventory location.",
            },
            {
                "name": "full_address",
                "type": "character varying",
                "description": "The complete address of the inventory location.",
            },
            {
                "name": "city_name",
                "type": "character varying",
                "description": "The name of the city where the inventory location is situated, in English.",
            },
            {
                "name": "city_name_ar",
                "type": "character varying",
                "description": "The name of the city where the inventory location is situated, in Arabic.",
            },
            {
                "name": "country_name",
                "type": "character varying",
                "description": "The name of the country where the inventory location is situated, in English.",
            },
            {
                "name": "country_name_ar",
                "type": "character varying",
                "description": "The name of the country where the inventory location is situated, in Arabic.",
            },
            {
                "name": "orders_count",
                "type": "bigint",
                "description": "The total number of orders associated with this inventory location on the given date.",
            },
            {
                "name": "orders_total_value",
                "type": "numeric",
                "description": "The total monetary value of orders associated with this inventory location on the given date, in its original currency.",
            },
            {
                "name": "orders_total_value_converted",
                "type": "numeric",
                "description": "The total monetary value of orders associated with this inventory location on the given date, converted to a standard currency.",
            },
            {
                "name": "last_updated_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the record was last updated.",
            },
            {
                "name": "refreshed_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the data was last refreshed.",
            },
            {
                "name": "run_started_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the data processing run for this record started.",
            },
            {
                "name": "invocation_id",
                "type": "character varying",
                "description": "A unique identifier for the data processing invocation.",
            },
        ],
    },
    "api__analytics__orders_status_dates": {
        "description": """
            The `api__analytics__orders_status_dates` table provides analytical insights into
            the lifecycle and duration of orders at various status changes.
        """,
        "config": {
            "tags": ["api", "analytics", "order_status_dates"],
            "meta": {"dagster": {"group": "analytics"}},
        },
        "tests": [
            {
                "dbt_expectations.expect_compound_columns_to_be_unique": {
                    "column_list": ["store_id", "order_created_at"],
                    "ignore_row_if": "any_value_is_missing",
                }
            }
        ],
        "columns": [
            {
                "name": "store_id",
                "type": "integer",
                "description": "The unique identifier for the store to which the orders belong.",
            },
            {
                "name": "order_created_at",
                "type": "timestamp without time zone",
                "description": "The timestamp when the order was created. This serves as the reference point for status tracking.",
            },
            {
                "name": "number_of_orders_cd",
                "type": "bigint",
                "description": "The number of orders that have reached 'Created' status.",
            },
            {
                "name": "number_of_orders_cp",
                "type": "bigint",
                "description": "The number of orders currently in 'Confirmed/Processing' status.",
            },
            {
                "name": "number_of_orders_pr",
                "type": "bigint",
                "description": "The number of orders currently in 'Preparing' status.",
            },
            {
                "name": "number_of_orders_ip",
                "type": "bigint",
                "description": "The number of orders currently in 'In Progress' status.",
            },
            {
                "name": "number_of_orders_ri",
                "type": "bigint",
                "description": "The number of orders currently in 'Ready for In-delivery' status.",
            },
            {
                "name": "number_of_orders_id",
                "type": "bigint",
                "description": "The number of orders currently in 'In Delivery' status.",
            },
            {
                "name": "number_of_orders_rr",
                "type": "bigint",
                "description": "The number of orders currently in 'Returned/Reversed' status.",
            },
            {
                "name": "sum_created_at_to_delivered_mins",
                "type": "double precision",
                "description": "The total sum of minutes from order creation to delivery for all relevant orders.",
            },
            {
                "name": "sum_created_at_to_preparing_mins",
                "type": "double precision",
                "description": "The total sum of minutes from order creation to the 'Preparing' status.",
            },
            {
                "name": "sum_preparing_to_ready_mins",
                "type": "double precision",
                "description": "The total sum of minutes from 'Preparing' status to 'Ready for Delivery' status.",
            },
            {
                "name": "sum_preparing_to_in_delivery_mins",
                "type": "double precision",
                "description": "The total sum of minutes from 'Preparing' status to 'In Delivery' status.",
            },
            {
                "name": "sum_ready_to_in_delivery_mins",
                "type": "double precision",
                "description": "The total sum of minutes from 'Ready for Delivery' status to 'In Delivery' status.",
            },
            {
                "name": "sum_in_delivery_to_delivered_mins",
                "type": "double precision",
                "description": "The total sum of minutes from 'In Delivery' status to 'Delivered' status.",
            },
            {
                "name": "sum_processing_reverse_to_reversed_mins",
                "type": "double precision",
                "description": "The total sum of minutes from 'Processing Reverse' status to 'Reversed' status.",
            },
            {
                "name": "last_updated_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the record was last updated.",
            },
            {
                "name": "refreshed_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the data was last refreshed.",
            },
            {
                "name": "run_started_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the data processing run for this record started.",
            },
            {
                "name": "invocation_id",
                "type": "character varying",
                "description": "A unique identifier for the data processing invocation.",
            },
        ],
    },
    "api__analytics__orders": {
        "description": """
            The `api__analytics__orders` model provides a comprehensive view of order-related data,
            essential for analyzing sales performance, customer behavior, and operational efficiency.
        """,
        "config": {
            "tags": ["api", "analytics", "orders"],
            "meta": {"dagster": {"group": "analytics"}},
            "grants": {"select": ["qubit"]},
        },
        "columns": [
            {
                "name": "order_id",
                "type": "bigint",
                "description": "The unique identifier for the order.",
                "tests": ["unique", "not_null"],
            },
            {
                "name": "order_created_at_date",
                "type": "date",
                "description": "The date when the order was created.",
            },
            {
                "name": "order_delivered_in_days",
                "type": "bigint",
                "description": "The number of days it took for the order to be delivered.",
            },
            {
                "name": "order_delivered_in_hours",
                "type": "bigint",
                "description": "The number of hours it took for the order to be delivered.",
            },
            {
                "name": "store_id",
                "type": "integer",
                "description": "The unique identifier for the store where the order was placed.",
            },
            {
                "name": "customer_id",
                "type": "integer",
                "description": "The unique identifier for the customer who placed the order.",
            },
            {
                "name": "customer_name",
                "type": "character varying",
                "description": "The name of the customer who placed the order.",
            },
            {
                "name": "customer_joined_store_date",
                "type": "date",
                "description": "The date when the customer joined the store.",
            },
            {
                "name": "order_status_id",
                "type": "integer",
                "description": "The unique identifier for the status of the order.",
            },
            {
                "name": "order_status_name",
                "type": "character varying",
                "description": "The name of the order status in English.",
            },
            {
                "name": "order_status_name_ar",
                "type": "character varying",
                "description": "The name of the order status in Arabic.",
            },
            {
                "name": "payment_method_code",
                "type": "character varying",
                "description": "The code for the payment method used for the order.",
            },
            {
                "name": "payment_method_name",
                "type": "character varying",
                "description": "The name of the payment method in English.",
            },
            {
                "name": "payment_method_name_ar",
                "type": "character varying",
                "description": "The name of the payment method in Arabic.",
            },
            {
                "name": "payment_option_code",
                "type": "character varying",
                "description": "The code for the specific payment option used.",
            },
            {
                "name": "payment_option_name",
                "type": "character varying",
                "description": "The name of the payment option in English.",
            },
            {
                "name": "payment_option_name_ar",
                "type": "character varying",
                "description": "The name of the payment option in Arabic.",
            },
            {
                "name": "shipping_method_code",
                "type": "character varying",
                "description": "The code for the shipping method used for the order.",
            },
            {
                "name": "shipping_method_name",
                "type": "character varying",
                "description": "The name of the shipping method in English.",
            },
            {
                "name": "shipping_method_name_ar",
                "type": "character varying",
                "description": "The name of the shipping method in Arabic.",
            },
            {
                "name": "pickup_option_city_id",
                "type": "integer",
                "description": "The unique identifier for the city if the order was picked up.",
            },
            {
                "name": "pickup_option_city_name",
                "type": "character varying",
                "description": "The name of the city if the order was picked up, in English.",
            },
            {
                "name": "pickup_option_city_name_ar",
                "type": "character varying",
                "description": "The name of the city if the order was picked up, in Arabic.",
            },
            {
                "name": "shipping_address_city_id",
                "type": "bigint",
                "description": "The unique identifier for the city in the shipping address.",
            },
            {
                "name": "shipping_address_city_name",
                "type": "character varying",
                "description": "The name of the city in the shipping address, in English.",
            },
            {
                "name": "shipping_address_city_name_ar",
                "type": "character varying",
                "description": "The name of the city in the shipping address, in Arabic.",
            },
            {
                "name": "shipping_address_city_lon",
                "type": "double precision",
                "description": "The longitude of the city in the shipping address.",
            },
            {
                "name": "shipping_address_city_lat",
                "type": "double precision",
                "description": "The latitude of the city in the shipping address.",
            },
            {
                "name": "shipping_address_country_id",
                "type": "bigint",
                "description": "The unique identifier for the country in the shipping address.",
            },
            {
                "name": "shipping_address_country_name",
                "type": "character varying",
                "description": "The name of the country in the shipping address, in English.",
            },
            {
                "name": "shipping_address_country_name_ar",
                "type": "character varying",
                "description": "The name of the country in the shipping address, in Arabic.",
            },
            {
                "name": "order_products_count",
                "type": "integer",
                "description": "The total number of products in the order.",
            },
            {
                "name": "order_currency_code",
                "type": "character varying",
                "description": "The currency code used for the order.",
            },
            {
                "name": "store_currency_code",
                "type": "character varying",
                "description": "The currency code used by the store.",
            },
            {
                "name": "order_total_value",
                "type": "numeric",
                "description": "The total value of the order in its original currency.",
            },
            {
                "name": "order_total_value_converted",
                "type": "numeric",
                "description": "The total value of the order converted to a standard currency.",
            },
            {
                "name": "order_vat_value",
                "type": "numeric",
                "description": "The value of Value Added Tax (VAT) applied to the order in its original currency.",
            },
            {
                "name": "order_vat_value_converted",
                "type": "numeric",
                "description": "The value of Value Added Tax (VAT) applied to the order converted to a standard currency.",
            },
            {
                "name": "order_shipping_fees",
                "type": "numeric",
                "description": "The shipping fees for the order in its original currency.",
            },
            {
                "name": "order_shipping_fees_converted",
                "type": "numeric",
                "description": "The shipping fees for the order converted to a standard currency.",
            },
            {
                "name": "order_coupon_value",
                "type": "numeric",
                "description": "The value of the coupon applied to the order in its original currency.",
            },
            {
                "name": "order_coupon_value_converted",
                "type": "numeric",
                "description": "The value of the coupon applied to the order converted to a standard currency.",
            },
            {
                "name": "order_shipping_discount_value",
                "type": "numeric",
                "description": "The value of the shipping discount applied to the order in its original currency.",
            },
            {
                "name": "order_shipping_discount_value_converted",
                "type": "numeric",
                "description": "The value of the shipping discount applied to the order converted to a standard currency.",
            },
            {
                "name": "order_sub_total_value",
                "type": "numeric",
                "description": "The sub-total value of the order in its original currency.",
            },
            {
                "name": "order_sub_total_value_converted",
                "type": "numeric",
                "description": "The sub-total value of the order converted to a standard currency.",
            },
            {
                "name": "order_sub_totals_value",
                "type": "numeric",
                "description": "The sub-totals value of the order in its original currency (potentially including VAT).",
            },
            {
                "name": "order_sub_totals_value_converted",
                "type": "numeric",
                "description": "The sub-totals value of the order converted to a standard currency (potentially including VAT).",
            },
            {
                "name": "order_products_discount_value",
                "type": "numeric",
                "description": "The total discount value applied to products in the order in its original currency.",
            },
            {
                "name": "order_products_discount_value_converted",
                "type": "numeric",
                "description": "The total discount value applied to products in the order converted to a standard currency.",
            },
            {
                "name": "order_sub_totals_before_vat_value",
                "type": "numeric",
                "description": "The sub-totals value of the order before VAT in its original currency.",
            },
            {
                "name": "order_sub_totals_before_vat_value_converted",
                "type": "numeric",
                "description": "The sub-totals value of the order before VAT converted to a standard currency.",
            },
            {
                "name": "order_coupon_cod_discount_value",
                "type": "numeric",
                "description": "The discount value from cash on delivery (COD) coupons in its original currency.",
            },
            {
                "name": "order_coupon_cod_discount_value_converted",
                "type": "numeric",
                "description": "The discount value from cash on delivery (COD) coupons converted to a standard currency.",
            },
            {
                "name": "order_free_shipping_coupon_value",
                "type": "numeric",
                "description": "The value of free shipping coupons applied to the order in its original currency.",
            },
            {
                "name": "order_free_shipping_coupon_value_converted",
                "type": "numeric",
                "description": "The value of free shipping coupons applied to the order converted to a standard currency.",
            },
            {
                "name": "order_sub_totals_after_coupon_discount_value",
                "type": "numeric",
                "description": "The sub-totals value of the order after applying coupon discounts in its original currency.",
            },
            {
                "name": "order_sub_totals_after_coupon_discount_value_converted",
                "type": "numeric",
                "description": "The sub-totals value of the order after applying coupon discounts converted to a standard currency.",
            },
            {
                "name": "order_sub_totals_after_products_discount_value",
                "type": "numeric",
                "description": "The sub-totals value of the order after applying product discounts in its original currency.",
            },
            {
                "name": "order_sub_totals_after_products_discount_value_converted",
                "type": "numeric",
                "description": "The sub-totals value of the order after applying product discounts converted to a standard currency.",
            },
            {
                "name": "order_sub_totals_after_vat_value",
                "type": "numeric",
                "description": "The sub-totals value of the order after applying VAT in its original currency.",
            },
            {
                "name": "order_sub_totals_after_vat_value_converted",
                "type": "numeric",
                "description": "The sub-totals value of the order after applying VAT converted to a standard currency.",
            },
            {
                "name": "order_zid_cod_value",
                "type": "numeric",
                "description": "The Zid Cash on Delivery (COD) value for the order in its original currency.",
            },
            {
                "name": "order_zid_cod_value_converted",
                "type": "numeric",
                "description": "The Zid Cash on Delivery (COD) value for the order converted to a standard currency.",
            },
            {
                "name": "order_total_before_vat_value",
                "type": "numeric",
                "description": "The total value of the order before VAT in its original currency.",
            },
            {
                "name": "order_total_before_vat_value_converted",
                "type": "numeric",
                "description": "The total value of the order before VAT converted to a standard currency.",
            },
            {
                "name": "order_source_code",
                "type": "character varying",
                "description": "The code identifying the source of the order (e.g., direct, referral).",
            },
            {
                "name": "order_source_name",
                "type": "character varying",
                "description": "The name of the order source in English.",
            },
            {
                "name": "order_source_name_ar",
                "type": "character varying",
                "description": "The name of the order source in Arabic.",
            },
            {
                "name": "order_utm_source",
                "type": "character varying",
                "description": "The UTM source parameter associated with the order.",
            },
            {
                "name": "order_utm_medium",
                "type": "character varying",
                "description": "The UTM medium parameter associated with the order.",
            },
            {
                "name": "order_utm_campaign",
                "type": "character varying",
                "description": "The UTM campaign parameter associated with the order.",
            },
            {
                "name": "last_updated_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the record was last updated.",
            },
            {
                "name": "refreshed_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the data was last refreshed.",
            },
            {
                "name": "run_started_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the data processing run for this record started.",
            },
            {
                "name": "invocation_id",
                "type": "character varying",
                "description": "A unique identifier for the data processing invocation.",
            },
        ],
    },
    "api__analytics__products": {
        "description": """
            The `api__analytics__products` table provides comprehensive analytical data on products,
            including their details, inventory, sales performance, and customer engagement metrics.
        """,
        "config": {
            "tags": ["api", "analytics", "products"],
            "meta": {"dagster": {"group": "analytics"}},
        },
        "tests": [
            {
                "dbt_expectations.expect_compound_columns_to_be_unique": {
                    "column_list": ["product_id", "product_order_date"],
                    "ignore_row_if": "any_value_is_missing",
                }
            }
        ],
        "columns": [
            {
                "name": "product_id",
                "type": "character varying",
                "description": "The unique identifier for the product.",
            },
            {
                "name": "store_id",
                "type": "integer",
                "description": "The unique identifier for the store that offers this product.",
            },
            {
                "name": "product_name",
                "type": "character varying",
                "description": "The name of the product in English.",
            },
            {
                "name": "product_name_ar",
                "type": "character varying",
                "description": "The name of the product in Arabic.",
            },
            {
                "name": "product_sku",
                "type": "character varying",
                "description": "The Stock Keeping Unit (SKU) for the product.",
            },
            {
                "name": "product_structure",
                "type": "character varying",
                "description": "Describes the product's structure, e.g., 'parent' or 'variant'.",
            },
            {
                "name": "product_parent_id",
                "type": "character varying",
                "description": "The identifier of the parent product if this product is a variant.",
            },
            {
                "name": "product_cost",
                "type": "numeric",
                "description": "The cost of the product to the seller.",
            },
            {
                "name": "product_price",
                "type": "numeric",
                "description": "The listed selling price of the product.",
            },
            {
                "name": "product_sale_price",
                "type": "numeric",
                "description": "The discounted or sale price of the product, if applicable.",
            },
            {
                "name": "product_available_quantity",
                "type": "numeric",
                "description": "The current quantity of the product available in inventory.",
            },
            {
                "name": "is_infinite",
                "type": "smallint",
                "description": "A flag indicating if the product has infinite stock (1 for infinite, 0 for finite).",
            },
            {
                "name": "product_image",
                "type": "character varying",
                "description": "The URL or identifier for the product's main image.",
            },
            {
                "name": "product_order_date",
                "type": "date",
                "description": "The date when the product was last ordered.",
            },
            {
                "name": "product_orders_count",
                "type": "bigint",
                "description": "The total number of orders in which this product was included.",
            },
            {
                "name": "product_sold_quantity",
                "type": "bigint",
                "description": "The total quantity of this product that has been sold.",
            },
            {
                "name": "product_total_tax_amount",
                "type": "numeric",
                "description": "The total tax amount collected for sales of this product in its original currency.",
            },
            {
                "name": "product_total_tax_amount_converted",
                "type": "numeric",
                "description": "The total tax amount collected for sales of this product converted to a standard currency.",
            },
            {
                "name": "product_total_sales_value",
                "type": "numeric",
                "description": "The total revenue generated from sales of this product in its original currency.",
            },
            {
                "name": "product_total_sales_value_converted",
                "type": "numeric",
                "description": "The total revenue generated from sales of this product converted to a standard currency.",
            },
            {
                "name": "product_added_to_cart_count",
                "type": "bigint",
                "description": "The total number of times the product has been added to shopping carts.",
            },
            {
                "name": "product_notifications_count",
                "type": "bigint",
                "description": "The number of notifications related to this product.",
            },
            {
                "name": "product_avg_rating",
                "type": "numeric",
                "description": "The average customer rating for the product.",
            },
            {
                "name": "last_updated_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the record was last updated.",
            },
            {
                "name": "refreshed_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the data was last refreshed.",
            },
            {
                "name": "run_started_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the data processing run for this record started.",
            },
            {
                "name": "invocation_id",
                "type": "character varying",
                "description": "A unique identifier for the data processing invocation.",
            },
        ],
    },
    "api__analytics__store_token": {
        "description": " ",
        "config": {
            "tags": ["api", "analytics"],
            "meta": {"dagster": {"group": "analytics"}},
        },
        "columns": [
            {"name": "store_id", "description": "", "tests": ["unique", "not_null"]},
        ],
    },
    "api__analytics__visits": {
        "description": """
            The `api__analytics__visits` table provides aggregated daily data on website
            visits and user interactions within stores.
        """,
        "config": {
            "tags": ["api", "analytics", "visits"],
            "meta": {"dagster": {"group": "analytics"}},
        },
        "columns": [
            {
                "name": "id",
                "type": "character varying",
                "description": "The unique identifier for the daily visit aggregate record.",
                "tests": ["unique", "not_null"],
            },
            {
                "name": "store_id",
                "type": "bigint",
                "description": "The unique identifier for the store being visited.",
            },
            {
                "name": "activity_date",
                "type": "date",
                "description": "The date for which the visit metrics are reported.",
            },
            {
                "name": "visits_count",
                "type": "bigint",
                "description": "The total number of unique visits to the store on this date.",
            },
            {
                "name": "product_views",
                "type": "bigint",
                "description": "The total number of product page views on this date.",
            },
            {
                "name": "add_to_cart",
                "type": "bigint",
                "description": "The total number of times products were added to carts on this date.",
            },
            {
                "name": "initial_checkout",
                "type": "bigint",
                "description": "The total number of times users initiated the checkout process on this date.",
            },
            {
                "name": "orders_completed",
                "type": "bigint",
                "description": "The total number of orders completed on this date.",
            },
            {
                "name": "utm_source",
                "type": "character varying",
                "description": "The UTM source parameter.",
            },
            {
                "name": "utm_medium",
                "type": "character varying",
                "description": "The UTM medium parameter.",
            },
            {
                "name": "utm_campaign",
                "type": "character varying",
                "description": "The UTM campaign parameter.",
            },
            {
                "name": "created_at_gmt",
                "type": "timestamp without time zone",
                "description": "The GMT timestamp when this visit record was created.",
            },
            {
                "name": "visits_source",
                "type": "character varying",
                "description": "A general category or name for the source of the visits.",
            },
            {
                "name": "last_updated_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the record was last updated.",
            },
            {
                "name": "refreshed_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the data was last refreshed.",
            },
            {
                "name": "run_started_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the data processing run for this record started.",
            },
            {
                "name": "invocation_id",
                "type": "character varying",
                "description": "A unique identifier for the data processing invocation.",
            },
        ],
    },
    "api__analytics__zidpay_analytics": {
        "description": """
            The `api__analytics__zidpay_analytics` table provides in-depth analytical data
            on payment transactions processed through ZidPay.
        """,
        "config": {
            "tags": ["api", "analytics", "zidpay"],
            "meta": {"dagster": {"group": "analytics"}},
        },
        "columns": [
            {
                "name": "merchant_id",
                "type": "integer",
                "description": "The unique identifier for the merchant associated with the ZidPay transaction.",
            },
            {
                "name": "store_id",
                "type": "character varying",
                "description": "The unique identifier for the store where the ZidPay transaction occurred.",
            },
            {
                "name": "payment_id",
                "type": "bigint",
                "description": "The unique identifier for the ZidPay payment transaction.",
                "tests": ["unique", "not_null"],
            },
            {
                "name": "payment_status_name",
                "type": "character varying",
                "description": "The status of the payment (e.g., 'completed', 'failed', 'pending').",
            },
            {
                "name": "payment_amount",
                "type": "numeric",
                "description": "The total monetary amount of the payment.",
            },
            {
                "name": "merchant_share",
                "type": "numeric",
                "description": "The portion of the payment amount retained by the merchant.",
            },
            {
                "name": "payment_fees_value",
                "type": "numeric",
                "description": "The fees associated with processing the payment.",
            },
            {
                "name": "network_name",
                "type": "character varying",
                "description": "The name of the payment network in English.",
            },
            {
                "name": "network_name_ar",
                "type": "character varying",
                "description": "The name of the payment network in Arabic.",
            },
            {
                "name": "payment_failure_reason",
                "type": "character varying",
                "description": "The reason for payment failure, if applicable.",
            },
            {
                "name": "payment_error_name",
                "type": "character varying",
                "description": "The name of the payment error in English.",
            },
            {
                "name": "payment_error_name_ar",
                "type": "character varying",
                "description": "The name of the payment error in Arabic.",
            },
            {
                "name": "deposit_status_name",
                "type": "character varying",
                "description": "The status of the deposit related to the payment.",
            },
            {
                "name": "deposit_status_name_ar",
                "type": "character varying",
                "description": "The status of the deposit related to the payment in Arabic.",
            },
            {
                "name": "refund_status_name",
                "type": "character varying",
                "description": "The status of any refund initiated for this payment.",
            },
            {
                "name": "refund_status_name_ar",
                "type": "character varying",
                "description": "The status of any refund initiated for this payment in Arabic.",
            },
            {
                "name": "refund_type_name",
                "type": "character varying",
                "description": "The type of refund (e.g., 'full', 'partial').",
            },
            {
                "name": "refund_type_name_ar",
                "type": "character varying",
                "description": "The type of refund in Arabic.",
            },
            {
                "name": "refund_amount",
                "type": "numeric",
                "description": "The monetary amount that was refunded, if applicable.",
            },
            {
                "name": "refunds_count",
                "type": "bigint",
                "description": "The number of refunds associated with this payment.",
            },
            {
                "name": "payment_created_at_date",
                "type": "date",
                "description": "The date when the ZidPay payment was created.",
            },
            {
                "name": "order_country_name",
                "type": "character varying",
                "description": "The name of the country where the associated order was placed, in English.",
            },
            {
                "name": "order_country_name_ar",
                "type": "character varying",
                "description": "The name of the country where the associated order was placed, in Arabic.",
            },
            {
                "name": "order_status_name",
                "type": "character varying",
                "description": "The status of the order associated with this payment, in English.",
            },
            {
                "name": "order_status_name_ar",
                "type": "character varying",
                "description": "The status of the order associated with this payment, in Arabic.",
            },
            {
                "name": "last_updated_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the record was last updated.",
            },
            {
                "name": "refreshed_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the data was last refreshed.",
            },
            {
                "name": "run_started_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the data processing run for this record started.",
            },
            {
                "name": "invocation_id",
                "type": "character varying",
                "description": "A unique identifier for the data processing invocation.",
            },
        ],
    },
    "api__analytics__zidpay_deposits": {
        "description": """
            The `api__analytics__zidpay_deposits` table tracks the details of deposits made
            through ZidPay to merchants.
        """,
        "config": {
            "tags": ["api", "analytics", "zidpay", "deposits"],
            "meta": {"dagster": {"group": "analytics"}},
        },
        "columns": [
            {
                "name": "store_id",
                "type": "character varying",
                "description": "The unique identifier for the store to which the deposit was made.",
            },
            {
                "name": "deposit_id",
                "type": "integer",
                "description": "The unique identifier for the ZidPay deposit.",
                "tests": ["unique", "not_null"],
            },
            {
                "name": "provider_total_amount",
                "type": "numeric",
                "description": "The total amount of money deposited by the payment provider to the merchant.",
            },
            {
                "name": "deposit_fees_value",
                "type": "numeric",
                "description": "The fees deducted or associated with this deposit.",
            },
            {
                "name": "deposit_status_name",
                "type": "character varying",
                "description": "The current status of the deposit (e.g., 'settled', 'pending', 'failed').",
            },
            {
                "name": "deposit_type_name",
                "type": "character varying",
                "description": "The type of deposit (e.g., 'daily_payout', 'weekly_payout', 'manual_deposit').",
            },
            {
                "name": "deposited_at_date",
                "type": "date",
                "description": "The date when the deposit was made.",
            },
            {
                "name": "last_updated_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the record was last updated.",
            },
            {
                "name": "refreshed_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the data was last refreshed.",
            },
            {
                "name": "run_started_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the data processing run for this record started.",
            },
            {
                "name": "invocation_id",
                "type": "character varying",
                "description": "A unique identifier for the data processing invocation.",
            },
        ],
    },
    "api__analytics__zidpay_stores": {
        "description": """
            The `api__analytics__zidpay_stores` table provides key information about stores
            that are integrated with and utilize ZidPay for payment processing.
        """,
        "config": {
            "tags": ["api", "analytics", "zidpay", "stores"],
            "meta": {"dagster": {"group": "analytics"}},
        },
        "columns": [
            {
                "name": "store_id",
                "type": "bigint",
                "description": "The unique identifier for the store.",
                "tests": ["unique", "not_null"],
            },
            {
                "name": "store_name",
                "type": "character varying",
                "description": "The name of the store.",
            },
            {
                "name": "store_url",
                "type": "character varying",
                "description": "The URL or domain of the store.",
            },
            {
                "name": "is_zidpay_active",
                "type": "boolean",
                "description": "A boolean flag indicating whether ZidPay is active for this store.",
            },
            {
                "name": "is_ngo_store",
                "type": "boolean",
                "description": "A boolean flag indicating if the store is registered as an NGO.",
            },
            {
                "name": "refreshed_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the data was last refreshed.",
            },
            {
                "name": "run_started_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the data processing run for this record started.",
            },
            {
                "name": "invocation_id",
                "type": "character varying",
                "description": "A unique identifier for the data processing invocation.",
            },
        ],
    },
    "api__analytics__store_currency": {
        "description": " ",
        "config": {
            "tags": ["api", "analytics"],
            "meta": {"dagster": {"group": "analytics"}},
        },
        "columns": [
            {"name": "store_id", "description": "", "tests": ["unique", "not_null"]},
        ],
    },
    "api__analytics__ratings": {
        "description": """
            The `api__analytics__ratings` table captures detailed information about customer ratings
            and reviews for various items within a store.
        """,
        "config": {
            "tags": ["api", "analytics", "ratings"],
            "meta": {"dagster": {"group": "analytics"}},
        },
        "columns": [
            {
                "name": "id",
                "type": "character varying",
                "description": "The unique identifier for the rating entry.",
                "tests": ["unique", "not_null"],
            },
            {
                "name": "store_id",
                "type": "bigint",
                "description": "The unique identifier for the store where the rating was submitted.",
            },
            {
                "name": "customer_id",
                "type": "bigint",
                "description": "The unique identifier for the customer who submitted the rating.",
            },
            {
                "name": "item_id",
                "type": "character varying",
                "description": "The unique identifier of the item that was rated.",
            },
            {
                "name": "item_type",
                "type": "character varying",
                "description": "The type of item being rated (e.g., 'product').",
            },
            {
                "name": "optional_reference_id",
                "type": "character varying",
                "description": "An optional additional identifier for referencing the item.",
            },
            {
                "name": "status_value",
                "type": "character varying",
                "description": "The current status of the rating (e.g., 'published').",
            },
            {
                "name": "rating_value",
                "type": "integer",
                "description": "The numerical value of the rating (e.g., 1 to 5 stars).",
            },
            {
                "name": "comment",
                "type": "character varying",
                "description": "Any textual comment or review provided by the customer.",
            },
            {
                "name": "is_anonymous",
                "type": "boolean",
                "description": "A boolean flag indicating if the rating was submitted anonymously.",
            },
            {
                "name": "is_notified",
                "type": "boolean",
                "description": "A boolean flag indicating if the customer has been notified about their rating status.",
            },
            {
                "name": "meta",
                "type": "character varying",
                "description": "Additional unstructured metadata related to the rating.",
            },
            {
                "name": "rating_created_at_date",
                "type": "date",
                "description": "The date when the rating was created.",
            },
            {
                "name": "last_updated_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the record was last updated.",
            },
            {
                "name": "refreshed_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the data was last refreshed.",
            },
            {
                "name": "run_started_at_utc",
                "type": "character varying",
                "description": "The UTC timestamp when the data processing run for this record started.",
            },
            {
                "name": "invocation_id",
                "type": "character varying",
                "description": "A unique identifier for the data processing invocation.",
            },
        ],
    },
    "api__analytics__products_order_products": {
        "description": " ",
        "config": {
            "tags": ["api", "analytics", "inactive"],
            "meta": {"dagster": {"group": "analytics"}},
        },
        "tests": [
            {
                "dbt_expectations.expect_compound_columns_to_be_unique": {
                    "column_list": ["product_id", "product_order_date"],
                    "ignore_row_if": "any_value_is_missing",
                }
            }
        ],
    },
    "api__analytics__products_order_products_parent": {
        "description": " ",
        "config": {
            "tags": ["api", "analytics", "inactive"],
            "meta": {"dagster": {"group": "analytics"}},
        },
        "tests": [
            {
                "dbt_expectations.expect_compound_columns_to_be_unique": {
                    "column_list": ["product_id", "product_order_date"],
                    "ignore_row_if": "any_value_is_missing",
                }
            }
        ],
    },
    "api__analytics__products_order_products_all": {
        "description": " ",
        "config": {
            "tags": ["api", "analytics", "inactive"],
            "meta": {"dagster": {"group": "analytics"}},
        },
        "tests": [
            {
                "dbt_expectations.expect_compound_columns_to_be_unique": {
                    "column_list": ["product_id", "product_order_date"],
                    "ignore_row_if": "any_value_is_missing",
                }
            }
        ],
    },
    "api__analytics__products_order_products_sales": {
        "description": " ",
        "config": {
            "tags": ["api", "analytics"],
            "meta": {"dagster": {"group": "analytics"}},
        },
        "tests": [
            {
                "dbt_expectations.expect_compound_columns_to_be_unique": {
                    "column_list": ["product_id", "product_order_date"],
                    "ignore_row_if": "any_value_is_missing",
                }
            }
        ],
    },
    "api__analytics__affiliates": {
        "description": " ",
        "config": {
            "tags": ["api", "inactive"],
            "meta": {"dagster": {"group": "inactive"}},
        },
    },
    "api__analytics__store_currency_changes": {
        "description": " ",
        "config": {
            "tags": ["api", "analytics"],
            "meta": {"dagster": {"group": "analytics"}},
        },
    },
    "api__analytics__marketplace_orders": {
        "description": """
            The `api__analytics__marketplace_orders` table provides a comprehensive and detailed
            record of orders placed through the Zid marketplace.
        """,
        "config": {
            "tags": ["api", "analytics", "marketplace"],
            "meta": {"dagster": {"group": "analytics"}},
        },
        "columns": [
            {
                "name": "order_id",
                "type": "bigint",
                "description": "The unique identifier for the marketplace order.",
                "tests": ["unique", "not_null"],
            },
            {
                "name": "order_created_at_date",
                "type": "date",
                "description": "The date when the marketplace order was created.",
            },
            {
                "name": "order_delivered_in_days",
                "type": "bigint",
                "description": "The number of days it took for the order to be delivered.",
            },
            {
                "name": "order_delivered_in_hours",
                "type": "bigint",
                "description": "The number of hours it took for the order to be delivered.",
            },
            {
                "name": "order_delivered_at_date",
                "type": "date",
                "description": "The date when the marketplace order was delivered.",
            },
            {
                "name": "order_canceled_returned_at_date",
                "type": "date",
                "description": "The date when the marketplace order was canceled or returned.",
            },
            {
                "name": "store_id",
                "type": "integer",
                "description": "The unique identifier for the store involved in the marketplace order.",
            },
            {
                "name": "customer_id",
                "type": "integer",
                "description": "The unique identifier for the customer who placed the marketplace order.",
            },
            {
                "name": "customer_name",
                "type": "character varying",
                "description": "The name of the customer who placed the marketplace order.",
            },
            {
                "name": "customer_joined_store_date",
                "type": "date",
                "description": "The date when the customer first joined the store associated with the marketplace order.",
            },
            {
                "name": "order_status_id",
                "type": "integer",
                "description": "The unique identifier for the status of the marketplace order.",
            },
            {
                "name": "order_status_name",
                "type": "character varying",
                "description": "The name of the order status in English.",
            },
            {
                "name": "order_status_name_ar",
                "type": "character varying",
                "description": "The name of the order status in Arabic.",
            },
            {
                "name": "payment_method_code",
                "type": "character varying",
                "description": "The code for the payment method used for the marketplace order.",
            },
            {
                "name": "payment_method_name",
                "type": "character varying",
                "description": "The name of the payment method in English.",
            },
            {
                "name": "payment_method_name_ar",
                "type": "character varying",
                "description": "The name of the payment method in Arabic.",
            },
            {
                "name": "payment_option_code",
                "type": "character varying",
                "description": "The code for the specific payment option used for the marketplace order.",
            },
            {
                "name": "payment_option_name",
                "type": "character varying",
                "description": "The name of the payment option in English.",
            },
            {
                "name": "payment_option_name_ar",
                "type": "character varying",
                "description": "The name of the payment option in Arabic.",
            },
            {
                "name": "shipping_method_code",
                "type": "character varying",
                "description": "The code for the shipping method used for the marketplace order.",
            },
            {
                "name": "shipping_method_name",
                "type": "character varying",
                "description": "The name of the shipping method in English.",
            },
            {
                "name": "shipping_method_name_ar",
                "type": "character varying",
                "description": "The name of the shipping method in Arabic.",
            },
            {
                "name": "pickup_option_city_id",
                "type": "integer",
                "description": "The unique identifier for the city if the marketplace order was picked up.",
            },
            {
                "name": "pickup_option_city_name",
                "type": "character varying",
                "description": "The name of the city if the marketplace order was picked up, in English.",
            },
            {
                "name": "pickup_option_city_name_ar",
                "type": "character varying",
                "description": "The name of the city if the marketplace order was picked up, in Arabic.",
            },
            {
                "name": "shipping_address_city_id",
                "type": "bigint",
                "description": "The unique identifier for the city in the shipping address of the marketplace order.",
            },
            {
                "name": "shipping_address_city_name",
                "type": "character varying",
                "description": "The name of the city in the shipping address, in English.",
            },
            {
                "name": "shipping_address_city_name_ar",
                "type": "character varying",
                "description": "The name of the city in the shipping address, in Arabic.",
            },
            {
                "name": "shipping_address_city_lon",
                "type": "double precision",
                "description": "The longitude of the city in the shipping address.",
            },
            {
                "name": "shipping_address_city_lat",
                "type": "double precision",
                "description": "The latitude of the city in the shipping address.",
            },
            {
                "name": "shipping_address_country_id",
                "type": "bigint",
                "description": "The unique identifier for the country in the shipping address.",
            },
            {
                "name": "shipping_address_country_name",
                "type": "character varying",
                "description": "The name of the country in the shipping address, in English.",
            },
            {
                "name": "shipping_address_country_name_ar",
                "type": "character varying",
                "description": "The name of the country in the shipping address, in Arabic.",
            },
            {
                "name": "order_products_count",
                "type": "integer",
                "description": "The total number of products in the marketplace order.",
            },
            {
                "name": "order_products_cost",
                "type": "numeric",
                "description": "The total cost of products in the marketplace order.",
            },
            {
                "name": "order_currency_code",
                "type": "character varying",
                "description": "The currency code used for the marketplace order.",
            },
            {
                "name": "store_currency_code",
                "type": "character varying",
                "description": "The currency code used by the store associated with the marketplace order.",
            },
            {
                "name": "current_store_currency_code",
                "type": "character varying",
                "description": "The current currency code of the store at the time of data processing.",
            },
            {
                "name": "currency_exchange_rate",
                "type": "character varying",
                "description": "The exchange rate between the order currency and a base currency (string).",
            },
            {
                "name": "store_currency_exchange_rate",
                "type": "character varying",
                "description": "The exchange rate between the store's original currency and a base currency (string).",
            },
            {
                "name": "current_currency_exchange_rate",
                "type": "double precision",
                "description": "The current exchange rate used for conversions.",
            },
            {
                "name": "order_total_value",
                "type": "numeric",
                "description": "The total value of the marketplace order in its original currency.",
            },
            {
                "name": "order_total_value_converted",
                "type": "numeric",
                "description": "The total value of the marketplace order converted to a standard currency.",
            },
            {
                "name": "order_vat_value",
                "type": "numeric",
                "description": "The value of Value Added Tax (VAT) applied to the marketplace order in its original currency.",
            },
            {
                "name": "order_vat_value_converted",
                "type": "numeric",
                "description": "The value of Value Added Tax (VAT) applied to the marketplace order converted to a standard currency.",
            },
            {
                "name": "order_shipping_fees",
                "type": "numeric",
                "description": "The shipping fees for the marketplace order in its original currency.",
            },
            {
                "name": "order_shipping_fees_converted",
                "type": "numeric",
                "description": "The shipping fees for the marketplace order converted to a standard currency.",
            },
            {
                "name": "order_coupon_value",
                "type": "numeric",
                "description": "The value of the coupon applied to the marketplace order in its original currency.",
            },
            {
                "name": "order_coupon_value_converted",
                "type": "numeric",
                "description": "The value of the coupon applied to the marketplace order converted to a standard currency.",
            },
            {
                "name": "order_shipping_discount_value",
                "type": "numeric",
                "description": "The value of the shipping discount applied to the marketplace order in its original currency.",
            },
            {
                "name": "order_shipping_discount_value_converted",
                "type": "numeric",
                "description": "The value of the shipping discount applied to the marketplace order converted to a standard currency.",
            },
            {
                "name": "order_sub_total_value",
                "type": "numeric",
                "description": "The sub-total value of the marketplace order in its original currency.",
            },
            {
                "name": "order_sub_total_value_converted",
                "type": "numeric",
                "description": "The sub-total value of the marketplace order converted to a standard currency.",
            },
            {
                "name": "order_sub_totals_value",
                "type": "numeric",
                "description": "The sub-totals value of the marketplace order (potentially including VAT) in its original currency.",
            },
            {
                "name": "order_sub_totals_value_converted",
                "type": "numeric",
                "description": "The sub-totals value of the marketplace order converted to a standard currency.",
            },
            {
                "name": "order_products_discount_value",
                "type": "numeric",
                "description": "The total discount value applied to products in the marketplace order in its original currency.",
            },
            {
                "name": "order_products_discount_value_converted",
                "type": "numeric",
                "description": "The total discount value applied to products in the marketplace order converted to a standard currency.",
            },
            {
                "name": "order_sub_totals_before_vat_value",
                "type": "numeric",
                "description": "The sub-totals value of the marketplace order before VAT in its original currency.",
            },
            {
                "name": "order_sub_totals_before_vat_value_converted",
                "type": "numeric",
                "description": "The sub-totals value of the marketplace order before VAT converted to a standard currency.",
            },
            {
                "name": "order_coupon_cod_discount_value",
                "type": "numeric",
                "description": "The discount value from cash on delivery (COD) coupons in its original currency.",
            },
            {
                "name": "order_coupon_cod_discount_value_converted",
                "type": "numeric",
                "description": "The discount value from cash on delivery (COD) coupons converted to a standard currency.",
            },
            {
                "name": "order_free_shipping_coupon_value",
                "type": "numeric",
                "description": "The value of free shipping coupons applied to the marketplace order in its original currency.",
            },
            {
                "name": "order_free_shipping_coupon_value_converted",
                "type": "numeric",
                "description": "The value of free shipping coupons applied to the marketplace order converted to a standard currency.",
            },
            {
                "name": "order_sub_totals_after_coupon_discount_value",
                "type": "numeric",
                "description": "The sub-totals value of the marketplace order after applying coupon discounts in its original currency.",
            },
            {
                "name": "order_sub_totals_after_coupon_discount_value_converted",
                "type": "numeric",
                "description": "The sub-totals value of the marketplace order after applying coupon discounts converted to a standard currency.",
            },
            {
                "name": "order_sub_totals_after_products_discount_value",
                "type": "numeric",
                "description": "The sub-totals value of the marketplace order after applying product discounts in its original currency.",
            },
            {
                "name": "order_sub_totals_after_products_discount_value_converted",
                "type": "numeric",
                "description": "The sub-totals value of the marketplace order after applying product discounts converted to a standard currency.",
            },
            {
                "name": "order_sub_totals_after_vat_value",
                "type": "numeric",
                "description": "The sub-totals value of the marketplace order after applying VAT in its original currency.",
            },
            {
                "name": "order_sub_totals_after_vat_value_converted",
                "type": "numeric",
                "description": "The sub-totals value of the marketplace order after applying VAT converted to a standard currency.",
            },
            {
                "name": "order_zid_cod_value",
                "type": "numeric",
                "description": "The Zid Cash on Delivery (COD) value for the marketplace order in its original currency.",
            },
            {
                "name": "order_zid_cod_value_converted",
                "type": "numeric",
                "description": "The Zid Cash on Delivery (COD) value for the marketplace order converted to a standard currency.",
            },
            {
                "name": "order_total_before_vat_value",
                "type": "numeric",
                "description": "The total value of the marketplace order before VAT in its original currency.",
            },
            {
                "name": "order_total_before_vat_value_converted",
                "type": "numeric",
                "description": "The total value of the marketplace order before VAT converted to a standard currency.",
            },
            {
                "name": "order_source_code",
                "type": "character varying",
                "description": "The code identifying the source of the marketplace order.",
            },
            {
                "name": "order_source_name",
                "type": "character varying",
                "description": "The name of the marketplace order source in English.",
            },
            {
                "name": "order_source_name_ar",
                "type": "character varying",
                "description": "The name of the marketplace order source in Arabic.",
            },
            {
                "name": "order_utm_source",
                "type": "character varying",
                "description": "The UTM source parameter associated with the marketplace order.",
            },
            {
                "name": "order_utm_medium",
                "type": "character varying",
                "description": "The UTM medium parameter associated with the marketplace order.",
            },
            {
                "name": "order_utm_campaign",
                "type": "character varying",
                "description": "The UTM campaign parameter associated with the marketplace order.",
            },
            {
                "name": "inventory_location_id",
                "type": "character varying",
                "description": "The unique identifier for the inventory location from which the order was fulfilled.",
            },
            {
                "name": "order_extra_data",
                "type": "character varying",
                "description": "Additional unstructured data related to the order.",
            },
            {
                "name": "last_updated_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the record was last updated.",
            },
            {
                "name": "run_started_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the data processing run for this record started.",
            },
            {
                "name": "invocation_id",
                "type": "character varying",
                "description": "A unique identifier for the data processing invocation.",
            },
        ],
    },
    "api__analytics__currencies": {
        "description": " ",
        "config": {
            "tags": ["api", "analytics"],
            "meta": {"dagster": {"group": "analytics"}},
        },
    },
    "api__analytics__orders_marketplace_stores": {
        "description": """
            The `api__analytics__orders_marketplace_stores` table provides analytical insights
            into orders originating from marketplace stores.
        """,
        "config": {
            "tags": ["api", "analytics", "marketplace_stores"],
            "meta": {"dagster": {"group": "analytics"}},
        },
        "columns": [
            {
                "name": "order_id",
                "type": "bigint",
                "description": "The unique identifier for the order placed through a marketplace store.",
                "tests": ["unique", "not_null"],
            },
            {
                "name": "order_created_at_date",
                "type": "date",
                "description": "The date when the order was created.",
            },
            {
                "name": "order_delivered_in_days",
                "type": "bigint",
                "description": "The number of days it took for the order to be delivered.",
            },
            {
                "name": "order_delivered_in_hours",
                "type": "bigint",
                "description": "The number of hours it took for the order to be delivered.",
            },
            {
                "name": "store_id",
                "type": "integer",
                "description": "The unique identifier for the marketplace store where the order was placed.",
            },
            {
                "name": "customer_id",
                "type": "integer",
                "description": "The unique identifier for the customer who placed the order.",
            },
            {
                "name": "customer_name",
                "type": "character varying",
                "description": "The name of the customer who placed the order.",
            },
            {
                "name": "customer_joined_store_date",
                "type": "date",
                "description": "The date when the customer joined the marketplace store.",
            },
            {
                "name": "order_status_id",
                "type": "integer",
                "description": "The unique identifier for the status of the order.",
            },
            {
                "name": "order_status_name",
                "type": "character varying",
                "description": "The name of the order status in English.",
            },
            {
                "name": "order_status_name_ar",
                "type": "character varying",
                "description": "The name of the order status in Arabic.",
            },
            {
                "name": "payment_method_code",
                "type": "character varying",
                "description": "The code for the payment method used for the order.",
            },
            {
                "name": "payment_method_name",
                "type": "character varying",
                "description": "The name of the payment method in English.",
            },
            {
                "name": "payment_method_name_ar",
                "type": "character varying",
                "description": "The name of the payment method in Arabic.",
            },
            {
                "name": "payment_option_code",
                "type": "character varying",
                "description": "The code for the specific payment option used.",
            },
            {
                "name": "payment_option_name",
                "type": "character varying",
                "description": "The name of the payment option in English.",
            },
            {
                "name": "payment_option_name_ar",
                "type": "character varying",
                "description": "The name of the payment option in Arabic.",
            },
            {
                "name": "shipping_method_code",
                "type": "character varying",
                "description": "The code for the shipping method used for the order.",
            },
            {
                "name": "shipping_method_name",
                "type": "character varying",
                "description": "The name of the shipping method in English.",
            },
            {
                "name": "shipping_method_name_ar",
                "type": "character varying",
                "description": "The name of the shipping method in Arabic.",
            },
            {
                "name": "pickup_option_city_id",
                "type": "integer",
                "description": "The unique identifier for the city if the order was picked up.",
            },
            {
                "name": "pickup_option_city_name",
                "type": "character varying",
                "description": "The name of the city if the order was picked up, in English.",
            },
            {
                "name": "pickup_option_city_name_ar",
                "type": "character varying",
                "description": "The name of the city if the order was picked up, in Arabic.",
            },
            {
                "name": "shipping_address_city_id",
                "type": "bigint",
                "description": "The unique identifier for the city in the shipping address.",
            },
            {
                "name": "shipping_address_city_name",
                "type": "character varying",
                "description": "The name of the city in the shipping address, in English.",
            },
            {
                "name": "shipping_address_city_name_ar",
                "type": "character varying",
                "description": "The name of the city in the shipping address, in Arabic.",
            },
            {
                "name": "shipping_address_city_lon",
                "type": "double precision",
                "description": "The longitude of the city in the shipping address.",
            },
            {
                "name": "shipping_address_city_lat",
                "type": "double precision",
                "description": "The latitude of the city in the shipping address.",
            },
            {
                "name": "shipping_address_country_id",
                "type": "bigint",
                "description": "The unique identifier for the country in the shipping address.",
            },
            {
                "name": "shipping_address_country_name",
                "type": "character varying",
                "description": "The name of the country in the shipping address, in English.",
            },
            {
                "name": "shipping_address_country_name_ar",
                "type": "character varying",
                "description": "The name of the country in the shipping address, in Arabic.",
            },
            {
                "name": "order_products_count",
                "type": "integer",
                "description": "The total number of products in the order.",
            },
            {
                "name": "order_currency_code",
                "type": "character varying",
                "description": "The currency code used for the order.",
            },
            {
                "name": "store_currency_code",
                "type": "character varying",
                "description": "The currency code used by the marketplace store.",
            },
            {
                "name": "order_total_value",
                "type": "numeric",
                "description": "The total value of the order in its original currency.",
            },
            {
                "name": "order_total_value_converted",
                "type": "numeric",
                "description": "The total value of the order converted to a standard currency.",
            },
            {
                "name": "order_vat_value",
                "type": "numeric",
                "description": "The value of Value Added Tax (VAT) applied to the order in its original currency.",
            },
            {
                "name": "order_vat_value_converted",
                "type": "numeric",
                "description": "The value of Value Added Tax (VAT) applied to the order converted to a standard currency.",
            },
            {
                "name": "order_shipping_fees",
                "type": "numeric",
                "description": "The shipping fees for the order in its original currency.",
            },
            {
                "name": "order_shipping_fees_converted",
                "type": "numeric",
                "description": "The shipping fees for the order converted to a standard currency.",
            },
            {
                "name": "order_coupon_value",
                "type": "numeric",
                "description": "The value of the coupon applied to the order in its original currency.",
            },
            {
                "name": "order_coupon_value_converted",
                "type": "numeric",
                "description": "The value of the coupon applied to the order converted to a standard currency.",
            },
            {
                "name": "order_shipping_discount_value",
                "type": "numeric",
                "description": "The value of the shipping discount applied to the order in its original currency.",
            },
            {
                "name": "order_shipping_discount_value_converted",
                "type": "numeric",
                "description": "The value of the shipping discount applied to the order converted to a standard currency.",
            },
            {
                "name": "order_sub_total_value",
                "type": "numeric",
                "description": "The sub-total value of the order in its original currency.",
            },
            {
                "name": "order_sub_total_value_converted",
                "type": "numeric",
                "description": "The sub-total value of the order converted to a standard currency.",
            },
            {
                "name": "order_sub_totals_value",
                "type": "numeric",
                "description": "The sub-totals value of the order in its original currency.",
            },
            {
                "name": "order_sub_totals_value_converted",
                "type": "numeric",
                "description": "The sub-totals value of the order converted to a standard currency.",
            },
            {
                "name": "order_products_discount_value",
                "type": "numeric",
                "description": "The total discount value applied to products in the order in its original currency.",
            },
            {
                "name": "order_products_discount_value_converted",
                "type": "numeric",
                "description": "The total discount value applied to products in the order converted to a standard currency.",
            },
            {
                "name": "order_sub_totals_before_vat_value",
                "type": "numeric",
                "description": "The sub-totals value of the order before VAT in its original currency.",
            },
            {
                "name": "order_sub_totals_before_vat_value_converted",
                "type": "numeric",
                "description": "The sub-totals value of the order before VAT converted to a standard currency.",
            },
            {
                "name": "order_coupon_cod_discount_value",
                "type": "numeric",
                "description": "The discount value from cash on delivery (COD) coupons in its original currency.",
            },
            {
                "name": "order_coupon_cod_discount_value_converted",
                "type": "numeric",
                "description": "The discount value from cash on delivery (COD) coupons converted to a standard currency.",
            },
            {
                "name": "order_free_shipping_coupon_value",
                "type": "numeric",
                "description": "The value of free shipping coupons applied to the order in its original currency.",
            },
            {
                "name": "order_free_shipping_coupon_value_converted",
                "type": "numeric",
                "description": "The value of free shipping coupons applied to the order converted to a standard currency.",
            },
            {
                "name": "order_sub_totals_after_coupon_discount_value",
                "type": "numeric",
                "description": "The sub-totals value of the order after applying coupon discounts in its original currency.",
            },
            {
                "name": "order_sub_totals_after_coupon_discount_value_converted",
                "type": "numeric",
                "description": "The sub-totals value of the order after applying coupon discounts converted to a standard currency.",
            },
            {
                "name": "order_sub_totals_after_products_discount_value",
                "type": "numeric",
                "description": "The sub-totals value of the order after applying product discounts in its original currency.",
            },
            {
                "name": "order_sub_totals_after_products_discount_value_converted",
                "type": "numeric",
                "description": "The sub-totals value of the order after applying product discounts converted to a standard currency.",
            },
            {
                "name": "order_sub_totals_after_vat_value",
                "type": "numeric",
                "description": "The sub-totals value of the order after applying VAT in its original currency.",
            },
            {
                "name": "order_sub_totals_after_vat_value_converted",
                "type": "numeric",
                "description": "The sub-totals value of the order after applying VAT converted to a standard currency.",
            },
            {
                "name": "order_zid_cod_value",
                "type": "numeric",
                "description": "The Zid Cash on Delivery (COD) value for the order in its original currency.",
            },
            {
                "name": "order_zid_cod_value_converted",
                "type": "numeric",
                "description": "The Zid Cash on Delivery (COD) value for the order converted to a standard currency.",
            },
            {
                "name": "order_total_before_vat_value",
                "type": "numeric",
                "description": "The total value of the order before VAT in its original currency.",
            },
            {
                "name": "order_total_before_vat_value_converted",
                "type": "numeric",
                "description": "The total value of the order before VAT converted to a standard currency.",
            },
            {
                "name": "order_source_code",
                "type": "character varying",
                "description": "The code identifying the source of the order.",
            },
            {
                "name": "order_source_name",
                "type": "character varying",
                "description": "The name of the order source in English.",
            },
            {
                "name": "order_source_name_ar",
                "type": "character varying",
                "description": "The name of the order source in Arabic.",
            },
            {
                "name": "order_utm_source",
                "type": "character varying",
                "description": "The UTM source parameter associated with the order.",
            },
            {
                "name": "order_utm_medium",
                "type": "character varying",
                "description": "The UTM medium parameter associated with the order.",
            },
            {
                "name": "order_utm_campaign",
                "type": "character varying",
                "description": "The UTM campaign parameter associated with the order.",
            },
            {
                "name": "last_updated_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the record was last updated.",
            },
            {
                "name": "run_started_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the data processing run for this record started.",
            },
            {
                "name": "invocation_id",
                "type": "character varying",
                "description": "A unique identifier for the data processing invocation.",
            },
        ],
    },
    "api__analytics__summery": {
        "description": """
            The `api__analytics__summery` table provides a daily aggregated summary of key
            performance indicators (KPIs) across various operational areas for each store.
        """,
        "config": {
            "tags": ["api", "analytics", "summary"],
            "meta": {"dagster": {"group": "analytics"}},
        },
        "tests": [
            {
                "dbt_expectations.expect_compound_columns_to_be_unique": {
                    "column_list": ["store_id", "activity_date"],
                    "ignore_row_if": "any_value_is_missing",
                }
            }
        ],
        "columns": [
            {
                "name": "store_id",
                "type": "bigint",
                "description": "The unique identifier for the store.",
            },
            {
                "name": "activity_date",
                "type": "date",
                "description": "The date for which the summary metrics are reported.",
            },
            {
                "name": "total_orders_value",
                "type": "numeric",
                "description": "The total monetary value of all orders on this date.",
            },
            {
                "name": "total_order_count",
                "type": "bigint",
                "description": "The total number of orders on this date.",
            },
            {
                "name": "new_orders_count",
                "type": "bigint",
                "description": "The number of newly created orders on this date.",
            },
            {
                "name": "visits_count",
                "type": "bigint",
                "description": "The total number of store visits on this date.",
            },
            {
                "name": "orders_completed",
                "type": "bigint",
                "description": "The number of orders that reached a completed status on this date.",
            },
            {
                "name": "store_rating_count",
                "type": "bigint",
                "description": "The total count of ratings received for the store on this date.",
            },
            {
                "name": "new_store_rating",
                "type": "bigint",
                "description": "The number of new store ratings submitted on this date.",
            },
            {
                "name": "customer_order_count",
                "type": "bigint",
                "description": "The count of distinct customer orders on this date.",
            },
            {
                "name": "customer_orders_total_value_converted",
                "type": "numeric",
                "description": "The total monetary value of customer orders on this date, converted to a standard currency.",
            },
            {
                "name": "total_order_products_count",
                "type": "bigint",
                "description": "The total number of individual products included in all orders on this date.",
            },
            {
                "name": "num_of_usage",
                "type": "bigint",
                "description": "Generic count of usage events, specific context may vary.",
            },
            {
                "name": "discounted_price",
                "type": "numeric",
                "description": "The total monetary amount discounted from product prices on this date.",
            },
            {
                "name": "total_coupons_revenue",
                "type": "numeric",
                "description": "The total revenue generated from coupon redemptions on this date.",
            },
            {
                "name": "count_customers",
                "type": "bigint",
                "description": "The total count of distinct customers who placed orders or interacted on this date.",
            },
            {
                "name": "discount_sale",
                "type": "numeric",
                "description": "The total sales value influenced by discounts on this date.",
            },
            {
                "name": "orders_from_automated_discounts_count",
                "type": "bigint",
                "description": "The number of orders where automated discount rules were applied on this date.",
            },
            {
                "name": "count_cart",
                "type": "bigint",
                "description": "The total number of shopping carts created on this date.",
            },
            {
                "name": "num_of_completed_carts",
                "type": "bigint",
                "description": "The number of shopping carts that were completed on this date.",
            },
            {
                "name": "carts_value",
                "type": "numeric",
                "description": "The total monetary value of all shopping carts on this date.",
            },
            {
                "name": "completed_carts_sale",
                "type": "numeric",
                "description": "The sales value generated from completed carts on this date.",
            },
            {
                "name": "total_discount_revenue",
                "type": "numeric",
                "description": "The total revenue reduction due to all types of discounts on this date.",
            },
            {
                "name": "count_cancelled_orders",
                "type": "bigint",
                "description": "The number of orders that were cancelled on this date.",
            },
            {
                "name": "total_cancelled_orders",
                "type": "numeric",
                "description": "The total monetary value of orders that were cancelled on this date.",
            },
            {
                "name": "count_reversed_orders",
                "type": "bigint",
                "description": "The number of orders that were reversed on this date.",
            },
            {
                "name": "total_reversed_orders",
                "type": "numeric",
                "description": "The total monetary value of orders that were reversed on this date.",
            },
            {
                "name": "coupon_discount",
                "type": "numeric",
                "description": "The total monetary value of discounts applied via coupons on this date.",
            },
            {
                "name": "product_discount",
                "type": "numeric",
                "description": "The total monetary value of discounts applied directly to products on this date.",
            },
            {
                "name": "coupon_cod_discount",
                "type": "numeric",
                "description": "The total monetary value of COD discounts applied via coupons on this date.",
            },
            {
                "name": "shipping_discount",
                "type": "numeric",
                "description": "The total monetary value of discounts applied to shipping fees on this date.",
            },
            {
                "name": "free_shipping_coupon",
                "type": "numeric",
                "description": "The total monetary value of free shipping offered via coupons on this date.",
            },
            {
                "name": "shipping_fees",
                "type": "numeric",
                "description": "The total shipping fees collected on this date.",
            },
            {
                "name": "total_vat",
                "type": "numeric",
                "description": "The total Value Added Tax (VAT) collected on this date.",
            },
            {
                "name": "pos_sale",
                "type": "numeric",
                "description": "The total sales value generated from POS transactions on this date.",
            },
            {
                "name": "pos_orders",
                "type": "bigint",
                "description": "The number of orders placed via POS on this date.",
            },
            {
                "name": "number_of_orders_cd",
                "type": "bigint",
                "description": "The number of orders whose status changed to 'Created' on this date.",
            },
            {
                "name": "number_of_orders_pr",
                "type": "bigint",
                "description": "The number of orders whose status changed to 'Preparing' on this date.",
            },
            {
                "name": "number_of_orders_ip",
                "type": "bigint",
                "description": "The number of orders whose status changed to 'In Progress' on this date.",
            },
            {
                "name": "number_of_orders_id",
                "type": "bigint",
                "description": "The number of orders whose status changed to 'In Delivery' on this date.",
            },
            {
                "name": "number_of_orders_rr",
                "type": "bigint",
                "description": "The number of orders whose status changed to 'Returned/Reversed' on this date.",
            },
            {
                "name": "sum_created_at_to_delivered_mins",
                "type": "double precision",
                "description": "The total sum of minutes from order creation to delivery for orders delivered on this date.",
            },
            {
                "name": "sum_preparing_to_ready_mins",
                "type": "double precision",
                "description": "The total sum of minutes from 'Preparing' to 'Ready for Delivery' for orders processed on this date.",
            },
            {
                "name": "sum_preparing_to_in_delivery_mins",
                "type": "double precision",
                "description": "The total sum of minutes from 'Preparing' to 'In Delivery' for orders processed on this date.",
            },
            {
                "name": "sum_in_delivery_to_delivered_mins",
                "type": "double precision",
                "description": "The total sum of minutes from 'In Delivery' to 'Delivered' for orders delivered on this date.",
            },
            {
                "name": "sum_processing_reverse_to_reversed_mins",
                "type": "double precision",
                "description": "The total sum of minutes from 'Processing Reverse' to 'Reversed' for orders reversed on this date.",
            },
            {
                "name": "product_sale",
                "type": "numeric",
                "description": "The total sales value of products (before discounts or VAT) on this date.",
            },
            {
                "name": "total_discount",
                "type": "numeric",
                "description": "The overall total monetary value of all discounts applied on this date.",
            },
            {
                "name": "total_shipping",
                "type": "numeric",
                "description": "The overall total monetary value of all shipping charges on this date.",
            },
            {
                "name": "total_cod",
                "type": "numeric",
                "description": "The overall total monetary value of all COD amounts on this date.",
            },
            {
                "name": "non_pos_sale",
                "type": "numeric",
                "description": "The total sales value generated from non-POS transactions on this date.",
            },
            {
                "name": "non_pos_orders",
                "type": "bigint",
                "description": "The number of orders placed via non-POS channels on this date.",
            },
            {
                "name": "settled_transaction_volume",
                "type": "numeric",
                "description": "The total monetary volume of transactions that have been settled on this date.",
            },
            {
                "name": "unsettled_transactions_counts",
                "type": "bigint",
                "description": "The count of transactions that are currently unsettled on this date.",
            },
            {
                "name": "successful_transaction",
                "type": "bigint",
                "description": "The count of successful transactions on this date.",
            },
            {
                "name": "refunded_sales_volume",
                "type": "numeric",
                "description": "The total monetary volume of sales that were refunded on this date.",
            },
            {
                "name": "successful_sales_volume",
                "type": "numeric",
                "description": "The total monetary volume of successful sales on this date.",
            },
            {
                "name": "successful_transaction_count",
                "type": "bigint",
                "description": "The total count of successful transactions on this date.",
            },
            {
                "name": "failed_transaction_count",
                "type": "bigint",
                "description": "The total count of failed transactions on this date.",
            },
            {
                "name": "refunded_transaction_count",
                "type": "bigint",
                "description": "The total count of refunded transactions on this date.",
            },
            {
                "name": "settled_transactions_count",
                "type": "bigint",
                "description": "The total count of transactions that have been settled on this date.",
            },
            {
                "name": "total_settled_amount",
                "type": "numeric",
                "description": "The total monetary amount from all settled transactions on this date.",
            },
            {
                "name": "last_updated_at_utc",
                "type": "timestamp without time zone",
                "description": "The UTC timestamp when the record was last updated.",
            },
        ],
    },
}


# --------------------------
# DB connection
# --------------------------
def get_db_connection():
    """
    Create and return a SQLAlchemy engine for the Redshift database.
    """
    db_url = "redshift+psycopg2://analytics_api:2WTdwC0LyMTr76d6jP@host.docker.internal:5439/dev?sslmode=require"
    logger.info(
        "Creating DB engine for URL: %s", db_url.split("@")[-1]
    )  # Hide credentials
    return create_engine(db_url)


# --------------------------
# Normalize output
# --------------------------
def normalize_output(res):
    logger.debug("Normalizing output: %s", type(res))
    if isinstance(res, list):
        if len(res) == 0:
            logger.warning("Empty list returned")
            return {"error": "Empty list returned"}
        if isinstance(res[0], dict):
            return res[0]
        return {"error": "List returned but does not contain dict"}
    elif isinstance(res, dict):
        return res
    else:
        logger.error("Unexpected output type: %s", type(res))
        return {"error": f"Unexpected output type: {type(res)}"}


import json

def database_permitted_tables() -> dict:
    """ Return the list of permitted tables in the database.
    :param: None
    :returns: A dictionary with database, schema, and list of permitted tables."""

    tables = list(schemas.keys())
    logger.info("Permitted tables: %s", tables)
    return {"database": "dev", "schema": "platinum", "tables": tables}

# --------------------------
# Tools class
# --------------------------
class Tools:
    def __init__(self):
        self.schemas = schemas
        logger.info("Tools initialized with %d schemas", len(schemas))

    def get_tables_schema(self, tables: list) -> dict:
        """ Return the schema for the specified tables.
        :params tables: List of table names to get the schema for.
        :returns: A dictionary with table names as keys and their schema as values."""

        logger.info("Fetching schema for tables: %s", tables)
        result = {}
        for t in tables:
            key = t.split(".")[-1]
            if key in self.schemas:
                result[key] = self.schemas[key]
        if not result:
            logger.info("No matching schemas found for: %s", tables)
            return {"error": "No matching tables found"}
        logger.info("Schema for tables: %s", result)
        return result

    def run_sql_query(self, query: str)->{str, dict}:
        """ Run a SQL query against the database with safety checks.
        :params query: The SQL query to run.
        :returns: The query result as a JSON string or an error message.
        """

        logger.info(f"Generated SQL query: {query}")
        blacklisted_keywords = ["INSERT", "DROP", "DELETE", "TRUNCATE", "ALTER"]
        upper_sql = query.upper()
        for keyword in blacklisted_keywords:
            if keyword in upper_sql and not upper_sql.startswith("SELECT"):
                logger.warning("Blocked query due to keyword: %s", keyword)
                return {"error": f"Query contains blacklisted keyword: {keyword}"}

        permitted = database_permitted_tables()
        permitted_schema = permitted["schema"]
        permitted_tables = [t.lower() for t in permitted["tables"]]

        if "FROM" in upper_sql:
            after_from = query.split("FROM", 1)[1].strip()
            table_name = after_from.split()[0].replace(";", "")
            if "." not in table_name:
                if table_name.lower() in permitted_tables:
                    query = query.replace(
                        after_from.split()[0], f"{permitted_schema}.{table_name}"
                    )
                    logger.info("Rewrote query with schema prefix: %s", query)
                else:
                    logger.error("Table %s is not permitted", table_name)
                    return {"error": f"Table {table_name} is not permitted."}

        engine = get_db_connection()
        try:
            with engine.connect() as conn:
                result = conn.execute(text(query))
                rows = [dict(row._mapping) for row in result.fetchall()]
            logger.info(f"Query result {rows}")
            logger.info("Query executed successfully, %d rows returned", len(rows))
            return {"rows": rows}
        except Exception as e:
            logger.exception("Error executing query")
            return {"error": "could not connect to server"}


# --------------------------
# Natural Language -> SQL (Safe)
# --------------------------
def nlp_to_sql(structured_input: dict, tools: Tools):
    logger.info("Converting structured input to SQL: %s", structured_input)
    table = structured_input.get("table")
    columns = structured_input.get("columns", ["*"])
    limit = structured_input.get("limit", 10)
    filters = structured_input.get("filters", {})

    if not table:
        return {"error": "Table is missing."}
    if not columns or columns == ["*"]:
        return {"error": "Columns cannot be empty."}

    full_table = f"platinum.{table}"

    where_clause = ""
    if filters:
        where_parts = [f"{col} = '{val}'" for col, val in filters.items()]
        where_clause = " WHERE " + " AND ".join(where_parts)
        logger.debug("Filters applied: %s", where_parts)

    sql = f"SELECT {', '.join(columns)} FROM {full_table}{where_clause} LIMIT {limit};"
    logger.info("Generated SQL: %s", sql)

    schema_cols = [c["name"] for c in tools.schemas.get(table, {}).get("columns", [])]
    for col in columns:
        if col not in schema_cols:
            logger.error("Invalid column '%s' for table '%s'", col, table)
            return {"error": f"Invalid column '{col}' for table '{table}'"}

    return tools.run_sql_query(sql)


# --------------------------
# Safe NL wrapper
# --------------------------
def safe_nl_query(user_prompt: str, tools: Tools, default_limit: int = 10):
    logger.info("Processing NL query: %s", user_prompt)

    permitted_tables = database_permitted_tables()["tables"]
    table_found = next(
        (t for t in permitted_tables if t.lower() in user_prompt.lower()), None
    )
    if not table_found:
        logger.error("No permitted table found in prompt")
        return {"error": "No permitted table found in prompt."}

    schema_cols = [
        col["name"] for col in tools.schemas.get(table_found, {}).get("columns", [])
    ]
    if not schema_cols:
        logger.error("No schema found for table %s", table_found)
        return {"error": f"No schema found for table {table_found}."}

    requested_columns = [
        col for col in schema_cols if col.lower() in user_prompt.lower()
    ]
    if not requested_columns:
        logger.warning("No valid columns found in prompt")
        return {
            "error": "No valid columns found in prompt. Please specify valid columns."
        }

    limit_match = re.search(r"\blimit\s+(\d+)\b", user_prompt.lower())
    limit = int(limit_match.group(1)) if limit_match else default_limit

    structured_input = {
        "table": table_found,
        "columns": requested_columns,
        "limit": limit,
        "filters": {},
    }

    logger.info("Structured input built: %s", structured_input)
    return nlp_to_sql(structured_input, tools)

# --------------------------
# Example usage
# --------------------------
if __name__ == "__main__":
    tools = Tools()
    user_prompt = (
        "Help me to get 3 unique order_id names from api__intermediate__orders"
    )
    safe_result = safe_nl_query(user_prompt, tools)
    print(safe_result)

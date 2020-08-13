import logging
from typing import List

from sqlalchemy import inspect

logger = logging.getLogger(__name__)


def has_column(columns: List, searchname: str) -> bool:
    return len(list(filter(lambda x: x["name"] == searchname, columns))) == 1


def get_column_def(columns: List, column: str, default: str) -> str:
    return default if not has_column(columns, column) else column


def check_migrate(engine, decl_base) -> None:
    """
    Checks if migration is necessary and migrates if necessary
    """
    inspector = inspect(engine)

    cols = inspector.get_columns('trades')
    tabs = inspector.get_table_names()
    table_back_name = 'trades_bak'
    for i, table_back_name in enumerate(tabs):
        table_back_name = f'trades_bak{i}'
        logger.debug(f'trying {table_back_name}')

    # Check for latest column
    if not has_column(cols, 'amount_requested'):
        logger.info(f'Running database migration - backup available as {table_back_name}')

        fee_open = get_column_def(cols, 'fee_open', 'fee')
        fee_open_cost = get_column_def(cols, 'fee_open_cost', 'null')
        fee_open_currency = get_column_def(cols, 'fee_open_currency', 'null')
        fee_close = get_column_def(cols, 'fee_close', 'fee')
        fee_close_cost = get_column_def(cols, 'fee_close_cost', 'null')
        fee_close_currency = get_column_def(cols, 'fee_close_currency', 'null')
        open_rate_requested = get_column_def(cols, 'open_rate_requested', 'null')
        close_rate_requested = get_column_def(cols, 'close_rate_requested', 'null')
        stop_loss = get_column_def(cols, 'stop_loss', '0.0')
        stop_loss_pct = get_column_def(cols, 'stop_loss_pct', 'null')
        initial_stop_loss = get_column_def(cols, 'initial_stop_loss', '0.0')
        initial_stop_loss_pct = get_column_def(cols, 'initial_stop_loss_pct', 'null')
        stoploss_order_id = get_column_def(cols, 'stoploss_order_id', 'null')
        stoploss_last_update = get_column_def(cols, 'stoploss_last_update', 'null')
        max_rate = get_column_def(cols, 'max_rate', '0.0')
        min_rate = get_column_def(cols, 'min_rate', 'null')
        sell_reason = get_column_def(cols, 'sell_reason', 'null')
        strategy = get_column_def(cols, 'strategy', 'null')
        # If ticker-interval existed use that, else null.
        if has_column(cols, 'ticker_interval'):
            timeframe = get_column_def(cols, 'timeframe', 'ticker_interval')
        else:
            timeframe = get_column_def(cols, 'timeframe', 'null')

        open_trade_price = get_column_def(cols, 'open_trade_price',
                                          f'amount * open_rate * (1 + {fee_open})')
        close_profit_abs = get_column_def(
            cols, 'close_profit_abs',
            f"(amount * close_rate * (1 - {fee_close})) - {open_trade_price}")
        sell_order_status = get_column_def(cols, 'sell_order_status', 'null')
        amount_requested = get_column_def(cols, 'amount_requested', 'amount')

        # Schema migration necessary
        engine.execute(f"alter table trades rename to {table_back_name}")
        # drop indexes on backup table
        for index in inspector.get_indexes(table_back_name):
            engine.execute(f"drop index {index['name']}")
        # let SQLAlchemy create the schema as required
        decl_base.metadata.create_all(engine)

        # Copy data back - following the correct schema
        engine.execute(f"""insert into trades
                (id, exchange, pair, is_open,
                fee_open, fee_open_cost, fee_open_currency,
                fee_close, fee_close_cost, fee_open_currency, open_rate,
                open_rate_requested, close_rate, close_rate_requested, close_profit,
                stake_amount, amount, amount_requested, open_date, close_date, open_order_id,
                stop_loss, stop_loss_pct, initial_stop_loss, initial_stop_loss_pct,
                stoploss_order_id, stoploss_last_update,
                max_rate, min_rate, sell_reason, sell_order_status, strategy,
                timeframe, open_trade_price, close_profit_abs
                )
            select id, lower(exchange),
                case
                    when instr(pair, '_') != 0 then
                    substr(pair,    instr(pair, '_') + 1) || '/' ||
                    substr(pair, 1, instr(pair, '_') - 1)
                    else pair
                    end
                pair,
                is_open, {fee_open} fee_open, {fee_open_cost} fee_open_cost,
                {fee_open_currency} fee_open_currency, {fee_close} fee_close,
                {fee_close_cost} fee_close_cost, {fee_close_currency} fee_close_currency,
                open_rate, {open_rate_requested} open_rate_requested, close_rate,
                {close_rate_requested} close_rate_requested, close_profit,
                stake_amount, amount, {amount_requested}, open_date, close_date, open_order_id,
                {stop_loss} stop_loss, {stop_loss_pct} stop_loss_pct,
                {initial_stop_loss} initial_stop_loss,
                {initial_stop_loss_pct} initial_stop_loss_pct,
                {stoploss_order_id} stoploss_order_id, {stoploss_last_update} stoploss_last_update,
                {max_rate} max_rate, {min_rate} min_rate, {sell_reason} sell_reason,
                {sell_order_status} sell_order_status,
                {strategy} strategy, {timeframe} timeframe,
                {open_trade_price} open_trade_price, {close_profit_abs} close_profit_abs
                from {table_back_name}
             """)

        # Reread columns - the above recreated the table!
        inspector = inspect(engine)
        cols = inspector.get_columns('trades')

import logging
import traceback
from configparser import RawConfigParser
from pathlib import Path

import pandas as pd
import dateparser
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.WARN)


def get_sqlalchemy_url():
    """
    Returns an SQLAlchemy connection string, using the the Snowflake credentials
    stored in the .credentials file in the parent folder.
    """
    cred_path = Path(__file__).parent / ".credentials"
    config = RawConfigParser()
    config.read(str(cred_path))
    if "connections" not in config:
        logging.error(f"The [connections] property group is missing from the credentials file {cred_path}")
    if "username" not in config["connections"]:
        logging.error(
            f"The 'user' property is missing from the [connections] property group in the credentials file {cred_path}")
    username = config["connections"]["username"]
    if "password" not in config["connections"]:
        logging.error(
            f"The 'password' property is missing from the [connections] property group in the credentials file {cred_path}")
    password = config["connections"]["password"]
    accountname = "alphacruncher.eu-central-1"
    if "accountname" in config["connections"]:
        accountname = config["connections"]["accountname"]
    warehouse = "USI_SS"
    if "warehouse" in config["connections"]:
        warehouse = config["connections"]["warehouse"]
    database = "CRSP_STOCK_AND_INDEXES"
    if "database" in config["connections"]:
        database = config["connections"]["database"]
    schema = "V20181231"
    if "schema" in config["connections"]:
        schema = config["connections"]["schema"]
    return f"snowflake://{username}:{password}@{accountname}/{database}/{schema}?warehouse={warehouse}&role={username}"


def list_tickers(start_date=None, end_date=None):
    """
    Lists the traded ticker for a given period.
    :param start_date: Lists tickers valid from the given date. If None, lists all tickers available in CRSP.
    :param start_date: Lists tickers valid until the given date.
    :return: A pandas dataframe containing the list of tickers in alphabetical order.
    """
    if isinstance(start_date, str):
        start_date = dateparser.parse(start_date,settings={'TIMEZONE': 'UTC'}).date()
    if isinstance(end_date, str):
        end_date = dateparser.parse(end_date,settings={'TIMEZONE': 'UTC'}).date()
    if start_date is not None and end_date is not None and end_date < start_date:
        raise ValueError(f"Specified end date {end_date} is before the specified start date {start_date}.")
    where_cond = ""
    params = None
    if start_date is None:
        logging.info("Querying all tickers...")
    else:
        if end_date is not None:
            logging.info(f"Querying tickers between {start_date} and {end_date} ...")
            where_cond = r"WHERE NAMEDT <= %(sd)s AND IFNULL(NAMEENDDT, '2099-12-31') >= %(ed)s"
            params = {"sd" : start_date, "ed" : end_date}
        else:
            logging.info(f"Querying tickers from {start_date} ...")
            where_cond = r"WHERE NAMEDT <= %(sd)s"
            params = {"sd": start_date}
    query = f"SELECT DISTINCT TICKER FROM CRSP_STOCK_AND_INDEXES.V20181231.NAME_HISTORY {where_cond} ORDER BY TICKER;"
    engine = create_engine(get_sqlalchemy_url())
    try:
        return pd.read_sql(query, engine, params=params)
    except SQLAlchemyError as e:
        logging.exception(f"Failed to retrieve the list of tickers:\n{traceback.format_exc()}")
    finally:
        if engine is not None:
            engine.dispose()


def get_daily_data(tickers="IBM", start_date=None, end_date=None):
    """
    Retrieves daily price and return data for the given ticker or a list of tickers, for a given date or for all available dates.
    :param tickers: A single ticker or a list of tickers for which to query daily data.
    :param start_date: A trade date starting from which to query data for. Returns all trade data for the tickers if None.
    :param end_date: The end date up to which to query the trade data.
    :return: A pandas dataframe with columns of: TICKER, DATE, PRC, RET, RETX
    """
    """
        Lists the traded ticker for a given date.
        :param trade_date: A given date for which to list tickers for. Lists all tickers if None.
        :return: A pandas dataframe containing the list of tickers in alphabetical order.
        """
    if tickers is None:
        raise ValueError("List of tickers is not specified.")
    if isinstance(start_date, str):
        start_date = dateparser.parse(start_date,settings={'TIMEZONE': 'UTC'}).date()
    if isinstance(end_date, str):
        end_date = dateparser.parse(end_date,settings={'TIMEZONE': 'UTC'}).date()
    if start_date is not None and end_date is not None and end_date < start_date:
        raise ValueError(f"Specified end date {end_date} is before the specified start date {start_date}.")
    if isinstance(tickers, str):
        tickers = [tickers]
    tickers_str = ','.join(tickers)
    engine = create_engine(get_sqlalchemy_url())
    try:
        if start_date is None:

            logging.info(f"Querying daily data for tickers: [{tickers_str}] ...")
            query = """WITH IDS AS ( SELECT DISTINCT
                            KYPERMNO, TICKER
                        FROM CRSP_STOCK_AND_INDEXES.V20181231.NAME_HISTORY
                        WHERE TICKER IN ( %(t)s )
                        ) SELECT
                            TS.CALDT AS DATE,
                            I.TICKER,
                            TS.PRC,
                            TS.RET,
                            TS.RETX
                        FROM CRSP_STOCK_AND_INDEXES.V20181231.TIME_SERIES_DAILY_PRIMARY AS TS
                        INNER JOIN IDS AS I
                            ON I.KYPERMNO = TS.KYPERMNO
                        ORDER BY TICKER, DATE"""
            return pd.read_sql(query, engine, params={"t": tickers})
        else:
            if end_date is None:
                logging.info(f"Querying daily data for tickers: [{tickers_str}] from trade date {start_date}...")
                query = """WITH IDS AS ( SELECT DISTINCT
                                KYPERMNO, TICKER
                            FROM CRSP_STOCK_AND_INDEXES.V20181231.NAME_HISTORY
                            WHERE TICKER IN ( %(t)s )
                            AND NAMEDT <= %(td)s AND IFNULL(NAMEENDDT, '2099-12-31') >= %(td)s
                            ) SELECT
                                TS.CALDT AS DATE,
                                I.TICKER,
                                TS.PRC,
                                TS.RET,
                                TS.RETX
                            FROM CRSP_STOCK_AND_INDEXES.V20181231.TIME_SERIES_DAILY_PRIMARY AS TS
                            INNER JOIN IDS AS I
                                ON I.KYPERMNO = TS.KYPERMNO
                            WHERE DATE >= %(td)s
                            ORDER BY TICKER, DATE"""
                return pd.read_sql(query, engine, params={"t": tickers, "td": start_date})
            else:
                logging.info(
                    f"Querying daily data for ticker: [{tickers_str}] for between {start_date} and {end_date}...")
                query = """WITH IDS AS ( SELECT DISTINCT
                                KYPERMNO, TICKER
                            FROM CRSP_STOCK_AND_INDEXES.V20181231.NAME_HISTORY
                            WHERE TICKER IN ( %(t)s )
                            AND NAMEDT <= %(td)s AND IFNULL(NAMEENDDT, '2099-12-31') >= %(tde)s
                            ) SELECT
                                TS.CALDT AS DATE,
                                I.TICKER,
                                TS.PRC,
                                TS.RET,
                                TS.RETX
                            FROM CRSP_STOCK_AND_INDEXES.V20181231.TIME_SERIES_DAILY_PRIMARY AS TS
                            INNER JOIN IDS AS I
                                ON I.KYPERMNO = TS.KYPERMNO
                            WHERE DATE >= %(td)s AND DATE <= %(tde)s
                            ORDER BY TICKER, DATE"""
                return pd.read_sql(query, engine, params={"t": tickers, "td": start_date, "tde": end_date})

    except SQLAlchemyError as e:
        logging.exception(f"Failed to query time series data:\n{traceback.format_exc()}")
    except Exception as ex:
        logging.exception(f"Failed to query time series data:\n{traceback.format_exc()}")
    finally:
        if engine is not None:
            engine.dispose()


def get_monthly_data(tickers="IBM", start_date=None, end_date=None):
    """
    Retrieves monthly price and return data for the given ticker or a list of tickers, for a given date or for all available dates.
    :param tickers: A single ticker or a list of tickers for which to query daily data.
    :param start_date: A trade date starting from which to query data for. Returns all trade data for the tickers if None.
    :param end_date: The end date up to which to query the trade data.
    :return: A pandas dataframe with columns of: TICKER, DATE, PRC, RET, RETX
    """
    """
        Lists the traded ticker for a given date.
        :param trade_date: A given date for which to list tickers for. Lists all tickers if None.
        :return: A pandas dataframe containing the list of tickers in alphabetical order.
        """
    if tickers is None:
        raise ValueError("List of tickers is not specified.")
    if isinstance(start_date, str):
        start_date = dateparser.parse(start_date,settings={'TIMEZONE': 'UTC'}).date()
    if isinstance(end_date, str):
        end_date = dateparser.parse(end_date,settings={'TIMEZONE': 'UTC'}).date()
    if start_date is not None and end_date is not None and end_date < start_date:
        raise ValueError(f"Specified end date {end_date} is before the specified start date {start_date}.")
    if isinstance(tickers, str):
        tickers = [tickers]
    tickers_str = ','.join(tickers)
    engine = create_engine(get_sqlalchemy_url())
    try:
        if start_date is None:

            logging.info(f"Querying monthly data for tickers: [{tickers_str}] ...")
            query = """WITH IDS AS ( SELECT DISTINCT
                            KYPERMNO, TICKER
                        FROM CRSP_STOCK_AND_INDEXES.V20181231.NAME_HISTORY
                        WHERE TICKER IN ( %(t)s )
                        ) SELECT
                            TS.MCALDT AS DATE,
                            I.TICKER,
                            TS.MPRC AS PRC,
                            TS.MRET AS RET,
                            TS.MRETX AS RETX
                        FROM CRSP_STOCK_AND_INDEXES.V20181231.TIME_SERIES_MONTHLY AS TS
                        INNER JOIN IDS AS I
                            ON I.KYPERMNO = TS.KYPERMNO
                        ORDER BY TICKER, DATE"""
            return pd.read_sql(query, engine, params={"t": tickers})
        else:
            if end_date is None:
                logging.info(f"Querying monthly data for tickers: [{tickers_str}] from trade date {start_date}...")
                query = """WITH IDS AS ( SELECT DISTINCT
                                KYPERMNO, TICKER
                            FROM CRSP_STOCK_AND_INDEXES.V20181231.NAME_HISTORY
                            WHERE TICKER IN ( %(t)s )
                            AND NAMEDT <= %(td)s AND IFNULL(NAMEENDDT, '2099-12-31') >= %(td)s
                            ) SELECT
                                TS.MCALDT AS DATE,
                                I.TICKER,
                                TS.MPRC AS PRC,
                                TS.MRET AS RET,
                                TS.MRETX AS RETX
                            FROM CRSP_STOCK_AND_INDEXES.V20181231.TIME_SERIES_MONTHLY AS TS
                            INNER JOIN IDS AS I
                                ON I.KYPERMNO = TS.KYPERMNO
                            WHERE DATE >= %(td)s
                            ORDER BY TICKER, DATE"""
                return pd.read_sql(query, engine, params={"t": tickers, "td": start_date})
            else:
                logging.info(
                    f"Querying daily monthly for ticker: [{tickers_str}] for between {start_date} and {end_date}...")
                query = """WITH IDS AS ( SELECT DISTINCT
                                KYPERMNO, TICKER
                            FROM CRSP_STOCK_AND_INDEXES.V20181231.NAME_HISTORY
                            WHERE TICKER IN ( %(t)s )
                            AND NAMEDT <= %(td)s AND IFNULL(NAMEENDDT, '2099-12-31') >= %(tde)s
                            ) SELECT
                                TS.MCALDT AS DATE,
                                I.TICKER,
                                TS.MPRC AS PRC,
                                TS.MRET AS RET,
                                TS.MRETX AS RETX
                            FROM CRSP_STOCK_AND_INDEXES.V20181231.TIME_SERIES_MONTHLY AS TS
                            INNER JOIN IDS AS I
                                ON I.KYPERMNO = TS.KYPERMNO
                            WHERE DATE >= %(td)s AND DATE <= %(tde)s
                            ORDER BY TICKER, DATE"""
                return pd.read_sql(query, engine, params={"t": tickers, "td": start_date, "tde": end_date})

    except SQLAlchemyError as e:
        logging.exception(f"Failed to query time series data:\n{traceback.format_exc()}")
    except Exception as ex:
        logging.exception(f"Failed to query time series data:\n{traceback.format_exc()}")
    finally:
        if engine is not None:
            engine.dispose()


def get_fixed_term_treasury_indices(start_date=None, end_date=None):
    """
    Retrieves the CRSP Fixed Term Indexes with 1Y, 2Y, 5Y, 10Y, 20Y and 30Y periods.
    :param start_date: The date from which to return data. If None, all data will be returned.
    :param end_date: The date until which to return data.
    :return: A pandas dataframe with a DATE column and RETADJ_#Y and NOMPRC_#Y columns.
    """
    if isinstance(start_date, str):
        start_date = dateparser.parse(start_date,settings={'TIMEZONE': 'UTC'}).date()
    if isinstance(end_date, str):
        end_date = dateparser.parse(end_date,settings={'TIMEZONE': 'UTC'}).date()
    if start_date is not None and end_date is not None and end_date < start_date:
        raise ValueError(f"Specified end date {end_date} is before the specified start date {start_date}.")
    where_cond = ""
    params = None
    if start_date is not None:
        if end_date is not None:
            logging.info(f"Querying CRSP Fixed Term Indexes from between {start_date} and {end_date} ...")
            where_cond = r"WHERE TO_DATE(DATES.DATE::VARCHAR, 'YYYYMMDD') BETWEEN %(sd)s AND %(ed)s"
            params = {"sd": start_date, "ed": end_date}
        else:
            logging.info(f"Querying CRSP Fixed Term Indexes from {start_date} ...")
            where_cond = r"WHERE TO_DATE(DATES.DATE::VARCHAR, 'YYYYMMDD') >= %(sd)s"
            params = {"sd": start_date}
    else:
        logging.info(f"Querying CRSP Fixed Term Indexes from {start_date} ...")
    query = f"""WITH DATES AS (SELECT
    DISTINCT CALDT AS DATE
    FROM CRSP_TREASURIES.V20181231.DAILY_FIXED_TERM_INDEXES
), M1Y AS (SELECT
    CALDT AS DATE,
    TDRETADJ AS RETADJ,
    TDNOMPRC AS NOMPRC
    FROM CRSP_TREASURIES.V20181231.DAILY_FIXED_TERM_INDEXES
    WHERE TREASNOX=2000003
), M2Y AS (SELECT
    CALDT AS DATE,
    TDRETADJ AS RETADJ,
    TDNOMPRC AS NOMPRC
    FROM CRSP_TREASURIES.V20181231.DAILY_FIXED_TERM_INDEXES
    WHERE TREASNOX=2000004
), M5Y AS (SELECT
    CALDT AS DATE,
    TDRETADJ AS RETADJ,
    TDNOMPRC AS NOMPRC
    FROM CRSP_TREASURIES.V20181231.DAILY_FIXED_TERM_INDEXES
    WHERE TREASNOX=2000005
), M7Y AS (SELECT
    CALDT AS DATE,
    TDRETADJ AS RETADJ,
    TDNOMPRC AS NOMPRC
    FROM CRSP_TREASURIES.V20181231.DAILY_FIXED_TERM_INDEXES
    WHERE TREASNOX=2000006
), M10Y AS (SELECT
    CALDT AS DATE,
    TDRETADJ AS RETADJ,
    TDNOMPRC AS NOMPRC
    FROM CRSP_TREASURIES.V20181231.DAILY_FIXED_TERM_INDEXES
    WHERE TREASNOX=2000007
), M20Y AS (SELECT
    CALDT AS DATE,
    TDRETADJ AS RETADJ,
    TDNOMPRC AS NOMPRC
    FROM CRSP_TREASURIES.V20181231.DAILY_FIXED_TERM_INDEXES
    WHERE TREASNOX=2000008
), M30Y AS (SELECT
    CALDT AS DATE,
    TDRETADJ AS RETADJ,
    TDNOMPRC AS NOMPRC
    FROM CRSP_TREASURIES.V20181231.DAILY_FIXED_TERM_INDEXES
    WHERE TREASNOX=2000009
) SELECT
    TO_DATE(DATES.DATE::VARCHAR, 'YYYYMMDD') AS DATE,
    M1Y.RETADJ AS RETADJ_1Y,
    M1Y.NOMPRC AS NOMPRC_1Y,
    M2Y.RETADJ AS RETADJ_2Y,
    M2Y.NOMPRC AS NOMPRC_2Y,
    M5Y.RETADJ AS RETADJ_5Y,
    M5Y.NOMPRC AS NOMPRC_5Y,
    M7Y.RETADJ AS RETADJ_7Y,
    M7Y.NOMPRC AS NOMPRC_7Y,
    M10Y.RETADJ AS RETADJ_10Y,
    M10Y.NOMPRC AS NOMPRC_10Y,
    M20Y.RETADJ AS RETADJ_20Y,
    M20Y.NOMPRC AS NOMPRC_20Y,
    M30Y.RETADJ AS RETADJ_30Y,
    M30Y.NOMPRC AS NOMPRC_30Y
FROM DATES
LEFT JOIN M1Y ON DATES.DATE = M1Y.DATE
LEFT JOIN M2Y ON DATES.DATE = M2Y.DATE
LEFT JOIN M5Y ON DATES.DATE = M5Y.DATE
LEFT JOIN M7Y ON DATES.DATE = M7Y.DATE
LEFT JOIN M10Y ON DATES.DATE = M10Y.DATE
LEFT JOIN M20Y ON DATES.DATE = M20Y.DATE
LEFT JOIN M30Y ON DATES.DATE = M30Y.DATE
{where_cond}
ORDER BY DATE;"""
    engine = create_engine(get_sqlalchemy_url())
    try:
        return pd.read_sql(query, engine, params=params)
    except SQLAlchemyError as e:
        logging.exception(f"Failed to retrieve CRSP Fixed Term Indices:\n{traceback.format_exc()}")
    finally:
        if engine is not None:
            engine.dispose()

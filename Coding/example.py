from datetime import date
from db import *


if __name__ == '__main__':
    all_tickers = list_tickers()
    logging.info(f"Retrieved {len(all_tickers.index)} tickers.")
    logging.info(all_tickers.head())

    tickers_df = list_tickers(start_date='2017-01-01')
    logging.info(tickers_df.head())

    tickers_df2 = list_tickers(start_date='2015-01-01', end_date=date(2016,1,1))
    logging.info(tickers_df2.head())

    aapl_df = get_daily_data(tickers='AAPL', start_date=date(2018, 12, 1))
    logging.info(aapl_df.head())

    ibm_df = get_daily_data(tickers=['IBM', 'GOOG'], start_date=date(2018, 1, 1), end_date=date(2018,12,31))
    logging.info(ibm_df.head())

    m_aapl_df = get_monthly_data(tickers='AAPL', start_date=date(2018, 12, 1))
    logging.info(m_aapl_df.head())

    m_ibm_df = get_monthly_data(tickers=['IBM', 'GOOG'], start_date=date(2018, 1, 1), end_date=date(2018, 12, 31))
    logging.info(m_ibm_df.head())

    trs_all_df = get_fixed_term_treasury_indices(start_date=None, end_date=None)
    logging.info(trs_all_df.head())

    trs_sd_df = get_fixed_term_treasury_indices(start_date=date(2018, 1, 1), end_date=None)
    logging.info(trs_sd_df.head())

    trs_sd_df = get_fixed_term_treasury_indices(start_date=date(2018, 1, 1), end_date=date(2018, 2, 1))
    logging.info(trs_sd_df.head())
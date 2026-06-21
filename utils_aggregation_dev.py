import pandas as pd
import numpy as np
import streamlit as st
from datetime import timedelta


# ponytail: shared helper replaces 4 duplicated period-bucketing blocks
def _bucket_period(df, date_col, granularity):
    """Assign a 'Period' column based on granularity. Mutates df in-place."""
    if granularity == 'Daily':
        df['Period'] = df[date_col].dt.normalize()
    elif granularity == 'Weekly':
        df['Period'] = df[date_col].dt.to_period('W').apply(lambda r: r.start_time)
    elif granularity == 'Monthly':
        df['Period'] = df[date_col].dt.to_period('M').dt.to_timestamp()
    else:
        df['Period'] = df[date_col]


# ponytail: shared helper replaces 2 duplicated coerce loops
def _coerce_numeric(df, cols):
    """Convert columns to numeric in-place, coercing errors."""
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')


def aggregate_side(df, date_col, granularity, csat_col):
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    _coerce_numeric(df, ['Total Responden', 'Total Rating', 'CSAT [Before]', 'CSAT [After]'])

    if granularity == 'Daily':
        df['Period'] = df[date_col].dt.date
        grouped = (
            df.groupby('Period')
            .agg({csat_col: 'mean'})
            .reset_index()
            .rename(columns={'Period': 'Date'})
        )
        return grouped[['Date', csat_col]]

    _bucket_period(df, date_col, granularity)

    # ponytail: weighted average inline — replaces inner function + pd.Series
    def _weighted_mean(g):
        if 'Total Responden' in g.columns and g['Total Responden'].sum() > 0:
            return (g[csat_col] * g['Total Responden']).sum() / g['Total Responden'].sum()
        return g[csat_col].mean() if csat_col in g.columns else np.nan

    grouped = (
        df.groupby('Period')[csat_col]
        .apply(lambda g: _weighted_mean(df.loc[g.index]))
        .reset_index()
        .rename(columns={'Period': 'Date', csat_col: csat_col})
    )

    return grouped[['Date', csat_col]]


def aggregate_csat_dual(df_before, df_after, date_col, granularity):
    if 'CSAT [Before]' not in df_before.columns:
        raise ValueError("df_before must contain 'CSAT [Before]' column")
    if 'CSAT [After]' not in df_after.columns:
        raise ValueError("df_after must contain 'CSAT [After]' column")

    before_g = aggregate_side(df_before, date_col, granularity, 'CSAT [Before]')
    after_g = aggregate_side(df_after, date_col, granularity, 'CSAT [After]')

    combined = (
        pd.merge(before_g, after_g, on='Date', how='outer')
        .sort_values('Date')
        .reset_index(drop=True)
    )
    return combined[['Date', 'CSAT [Before]', 'CSAT [After]']]


def aggregation_ratio(df, date_col, granularity):
    if df is None or df.empty:
        return pd.DataFrame(columns=['Date', 'Robot Success ratio'])

    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    _coerce_numeric(df, ['Connected to robot', 'Number of exit queues', 'Total handle robot'])
    df[['Connected to robot', 'Number of exit queues', 'Total handle robot']] = (
        df[['Connected to robot', 'Number of exit queues', 'Total handle robot']].fillna(0)
    )

    _bucket_period(df, date_col, granularity)

    grouped = df.groupby('Period').agg({
        'Connected to robot': 'sum',
        'Number of exit queues': 'sum',
        'Total handle robot': 'sum'
    }).reset_index()

    # ponytail: vectorized ratio — replaces slow row-by-row .apply(axis=1)
    grouped['Robot Success ratio'] = np.where(
        grouped['Connected to robot'] > 0,
        (grouped['Total handle robot'] - grouped['Number of exit queues'])
            / grouped['Connected to robot'] * 100,
        np.nan
    )

    grouped = grouped.sort_values('Period').reset_index(drop=True)
    return grouped[['Period', 'Robot Success ratio']].rename(columns={'Period': 'Date'})


def aggregate_sum(df, date_col, granularity, agg_dict):
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    _bucket_period(df, date_col, granularity)

    result = df.groupby('Period').agg(agg_dict).reset_index()
    return result.rename(columns={'Period': 'Date'})


# ============ Function to show Weeks and Months ============
def aggregate_table_with_granularity(
        df, category_col, value_col=None, date_col=None, granularity=None, start_date=None, end_date=None
):
    df = df.copy()

    if start_date is not None and end_date is not None:
        df = df[(df[date_col] >= start_date) & (df[date_col] <= end_date)]

    if df.empty:
        return pd.DataFrame(columns=[category_col])

    df[date_col] = pd.to_datetime(df[date_col])

    if granularity == 'Weekly':
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)

        week_starts = []
        current_start = start_date
        while current_start <= end_date:
            current_end = min(current_start + timedelta(days=6), end_date)
            week_starts.append((current_start, current_end))
            current_start = current_end + timedelta(days=1)

        def get_week_label(d):
            for ws, we in week_starts:
                if ws <= d <= we:
                    if ws.month == we.month:
                        return f"{ws.day:02d}-{we.day:02d} {ws.strftime('%b')}"
                    else:
                        return f"{ws.day:02d} {ws.strftime('%b')} - {we.day:02d} {we.strftime('%b')}"
            return None

        df['PeriodRaw'] = df[date_col].apply(lambda d: next(ws for ws, we in week_starts if ws <= d <= we))
        df['Period'] = df[date_col].apply(get_week_label)

    elif granularity == 'Monthly':
        df['PeriodRaw'] = df[date_col].dt.to_period('M').dt.to_timestamp()
        df['Period'] = df['PeriodRaw'].dt.strftime('%b %Y')
    else:
        df['PeriodRaw'] = df[date_col].dt.normalize()
        df['Period'] = df['PeriodRaw'].dt.strftime('%Y-%m-%d')

    if value_col is not None and value_col in df.columns:
        df[value_col] = pd.to_numeric(df[value_col], errors='coerce').fillna(0)

    if isinstance(category_col, str):
        group_cols = [category_col, 'PeriodRaw', 'Period']
    elif isinstance(category_col, list):
        group_cols = category_col + ['PeriodRaw', 'Period']
    else:
        raise ValueError("category_col should be a string or a list of strings")

    if value_col is None:
        agg_df = df.groupby(group_cols).size().reset_index(name='Total Sample')
    else:
        agg_df = df.groupby(group_cols)[value_col].sum().reset_index(name='Total Sample')

    pivot = agg_df.pivot_table(
        index=category_col,
        columns='Period',
        values='Total Sample',
        aggfunc='sum',
        fill_value=0
    )

    period_order = agg_df[['PeriodRaw', 'Period']].drop_duplicates().sort_values('PeriodRaw')
    ordered_cols = [c for c in period_order['Period'] if c in pivot.columns]
    pivot = pivot[ordered_cols]

    pivot['Total'] = pivot.select_dtypes(include=[np.number]).sum(axis=1)
    pivot = pivot.sort_values('Total', ascending=False).reset_index()

    pivot.columns = pd.Index(pivot.columns).map(str)
    pivot = pivot.loc[:, ~pivot.columns.duplicated()]

    return pivot


def calculate_checker_accuracy(df):
    df = df.copy()  # ponytail: prevent mutating caller's DataFrame
    count_cols = [col for col in df.columns if col.startswith("Count")]
    df["Total_Kesalahan"] = df[count_cols].sum(axis=1)

    result = (
        df.groupby("Checker")
        .agg(
            Total_Tagging=("Checker", "count"),
            Kesalahan=("Total_Kesalahan", "sum")
        )
        .reset_index()
    )
    result["Accuracy"] = (result["Total_Tagging"] - result["Kesalahan"]) / result["Total_Tagging"] * 100
    return result


def aggregate_checker_errors(df):
    count_cols = [
        'Count Hasil ASR',
        'Count Hasil Pemeriksaan Kualitas',
        'Count Efektif',
        'Count Kejelasan Suara',
        'Count Kelengkapan Rekaman',
        'Count Revisi Text'
    ]
    df_checker = df.groupby('Checker')[count_cols].sum().reset_index()
    return df_checker, count_cols


# ponytail: shrunk from 24 to 12 lines — same behavior
def default_range_ratio_CSAT(df, date_col, granularity, daily_days=14, weekly_periods=4, monthly_periods=4):
    if df is None or df.empty:
        return df

    df = df.sort_values(date_col).copy()

    if granularity == 'Daily':
        cutoff = df[date_col].max() - pd.Timedelta(days=daily_days - 1)
        filtered = df[df[date_col] >= cutoff]
    elif granularity == 'Weekly':
        filtered = df.tail(weekly_periods)
    elif granularity == 'Monthly':
        filtered = df.tail(monthly_periods)
    else:
        filtered = df

    return filtered if not filtered.empty else df
"""Preserve the academic model specification and expose reviewable evidence."""
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.holtwinters import SimpleExpSmoothing
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.stattools import adfuller, ccf
import statsmodels.formula.api as smf

TEMPERATURE = 'Air Temperature Means Daily Maximum (Degree Celsius)'
RAINFALL = 'Total Rainfall (Millimetre)'

def load_data(path):
    """Read the supplied SingStat export without changing any observations."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError('Supply the original annual SingStat CSV with --data PATH. See data/README.md.')
    raw = pd.read_csv(path, skiprows=9).set_index('Data Series').T
    data = raw[[TEMPERATURE, RAINFALL]].copy()
    data.columns = ['temperature_c', 'rainfall_mm']
    data.index = pd.to_datetime(data.index, format='mixed')
    data = data.apply(pd.to_numeric, errors='coerce').sort_index()
    data.index.name = 'year'
    if data.index.has_duplicates or data.isna().any().any() or not np.isfinite(data.to_numpy()).all():
        raise ValueError('Duplicate years, missing values or nonfinite observations; investigate the input.')
    if list(data.index.year) != list(range(1960, 2025)):
        raise ValueError('Expected one annual observation for each year from 1960 through 2024.')
    if (data < 0).any().any():
        raise ValueError('Negative observations require investigation.')
    data.index = pd.DatetimeIndex(data.index, freq='YS', name='year')
    return data

def metrics(actual, predicted, model, name):
    """Calculate holdout errors in original units; MAPE matches the baseline."""
    actual, predicted = np.asarray(actual), np.asarray(predicted)
    if actual.shape != predicted.shape or not np.isfinite(predicted).all():
        raise ValueError('Forecast length or finite-value check failed.')
    error = predicted - actual
    mse = np.mean(error ** 2)
    return {'model': name, 'MAPE_pct': np.mean(np.abs(error) / (actual + 1e-10))*100,
            'MAE_c': np.mean(np.abs(error)), 'MSE_c2': mse, 'RMSE_c': np.sqrt(mse),
            'R2': 1 - np.sum(error**2)/np.sum((actual-actual.mean())**2), 'AIC': model.aic}

def fit_analysis(data, refit_future=False):
    """Run original candidates and selected models; future refit is explicit."""
    train, test = data.loc['1960':'2014'], data.loc['2015':'2024']
    y, actual = train.temperature_c, test.temperature_c
    ses = SimpleExpSmoothing(y, initialization_method='estimated').fit(optimized=True)
    np.random.seed(64)
    ses_simulation = ses.simulate(len(test), repetitions=1000, error='add')
    ses_interval = pd.DataFrame({'lower_c': ses_simulation.quantile(.025, axis=1).values,
                                 'upper_c': ses_simulation.quantile(.975, axis=1).values}, index=test.index)
    arima_candidates = []
    for order in [(1,1,1), (0,1,0), (1,1,0), (0,1,1)]:
        for trend in ['n', 't']:
            model = ARIMA(y, order=order, trend=trend).fit()
            arima_candidates.append({'model': f'ARIMA{order}', 'trend': trend, 'AIC': model.aic,
                                     'converged': bool(model.mle_retvals['converged'])})
    # Original selected specification; selection changes require a separate review.
    arima = ARIMA(y, order=(0,1,1), trend='n').fit()
    dynreg = pd.DataFrame({'yt': y, 'xt0': train.rainfall_mm})
    ols = smf.ols('yt ~ xt0 - 1', data=dynreg).fit()
    arimax_candidates = []
    for order in [(0,0,0), (1,0,0), (0,0,1), (1,0,1)]:
        for trend in ['n', 'c', 't']:
            model = ARIMA(y, exog=dynreg[['xt0']], order=order, trend=trend).fit()
            arimax_candidates.append({'model': f'ARIMAX{order}', 'trend': trend, 'AIC': model.aic,
                                      'converged': bool(model.mle_retvals['converged'])})
    arimax = ARIMA(y, exog=dynreg[['xt0']], order=(1,0,0), trend='c').fit()
    arima_fc = arima.get_forecast(len(test))
    future_exog = pd.DataFrame({'xt0': test.rainfall_mm}, index=test.index)
    arimax_fc = arimax.get_forecast(len(test), exog=future_exog)
    forecasts = pd.DataFrame({'actual_c': actual, 'SES': np.asarray(ses.forecast(len(test))),
                              'ARIMA': np.asarray(arima_fc.predicted_mean),
                              'ARIMAX': np.asarray(arimax_fc.predicted_mean)}, index=test.index)
    models = {'SES': ses, 'ARIMA': arima, 'ARIMAX': arimax}
    scores = pd.DataFrame([metrics(actual, forecasts[name], model, name)
                           for name, model in models.items()])
    stations = []
    for name, values in [('full_level', data.temperature_c), ('train_difference_1', y.diff().dropna()),
                         ('train_difference_2', y.diff().diff().dropna())]:
        result = adfuller(values, autolag='AIC')
        stations.append({'series': name, 'ADF_statistic': result[0], 'p_value': result[1],
                         'lags': result[2], 'observations': result[3]})
    quality = []
    for col in data:
        q1, q3 = data[col].quantile([.25, .75])
        low, high = q1-1.5*(q3-q1), q3+1.5*(q3-q1)
        quality.append({'field': col, 'observations': len(data), 'missing': int(data[col].isna().sum()),
                        'iqr_lower': low, 'iqr_upper': high,
                        'iqr_flags': int(((data[col]<low)|(data[col]>high)).sum())})
    decomposition = seasonal_decompose(data.temperature_c, model='additive', period=2)
    ccf_values = ccf(data.temperature_c, data.rainfall_mm, nlags=15)
    if refit_future:
        future_model = ARIMA(data.temperature_c, order=(0,1,1), trend='n').fit()
        future = future_model.get_forecast(6).summary_frame()
        origin = 2024
    else:
        future_model = arima
        future = arima.get_forecast(16).summary_frame().loc['2025':'2030']
        origin = 2014
    diagnostics = []
    for name, model in [('ARIMA', arima), ('ARIMAX', arimax)]:
        resid = model.resid.iloc[1:] if name=='ARIMA' else model.resid
        shapiro = stats.shapiro(resid)
        diagnostics.append({'model': name, 'residual_observations': len(resid),
                            'Shapiro_W': shapiro.statistic, 'Shapiro_p': shapiro.pvalue})
    return dict(data=data, train=train, test=test, models=models, forecasts=forecasts, metrics=scores,
                arima_candidates=pd.DataFrame(arima_candidates).sort_values('AIC'),
                arimax_candidates=pd.DataFrame(arimax_candidates).sort_values('AIC'),
                stationarity=pd.DataFrame(stations), quality=pd.DataFrame(quality),
                decomposition=decomposition, ols=ols,
                cross_correlation=pd.DataFrame({'lag_years': range(15), 'CCF': ccf_values,
                                                'approx_95_bound': 1.96/np.sqrt(len(data))}),
                diagnostics=pd.DataFrame(diagnostics), future=future, future_model=future_model,
                future_origin=origin, arima_fc=arima_fc, arimax_fc=arimax_fc,
                ses_interval=ses_interval,
                trend_c_per_year=np.polyfit(np.arange(len(data)), data.temperature_c, 1)[0],
                correlation=data.temperature_c.corr(data.rainfall_mm))

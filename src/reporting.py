"""Export model evidence and English figures."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf

def render_overview(data, forecasts, trend_c_per_year, figures):
    """Draw overview charts from existing measurements and model predictions."""
    figures = Path(figures)
    figures.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.size': 11, 'axes.spines.top': False, 'axes.spines.right': False})
    def save(fig, name):
        fig.tight_layout()
        fig.savefig(figures / name, dpi=160, bbox_inches='tight')
        plt.close(fig)
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(data.index.year, data.temperature_c, color='#175878', label='Annual mean of daily maximum temperature')
    trend = np.polyval(np.polyfit(np.arange(len(data)), data.temperature_c, 1), np.arange(len(data)))
    ax.plot(data.index.year, trend, '--', color='#c07128', label=f'Descriptive trend: +{trend_c_per_year:.4f} °C/year')
    ax.axvline(2015, color='#a64b68', linestyle='--', linewidth=1.5, label='Forecast Start (2015)')
    ax.set(title='Singapore temperature: 1960–2024', xlabel='Year', ylabel='Temperature (°C)')
    ax.legend(fontsize=9)
    save(fig, 'temperature_trend.png')
    fig, ax = plt.subplots(figsize=(11, 4.5))
    f = forecasts
    ax.plot(f.index.year, f.actual_c, '-o', color='#175878', label='Actual')
    for name, color in [('SES','#c07128'),('ARIMA','#33845b'),('ARIMAX','#985e95')]:
        ax.plot(f.index.year, f[name], '--', color=color, label=name)
    ax.axvline(2015, color='#a64b68', linestyle='--', linewidth=1.5, label='Forecast Start (2015)')
    ax.set(title='Ten-year holdout: forecasts issued after 2014', xlabel='Year', ylabel='Temperature (°C)')
    ax.set_xlim(2014.5, 2024.5)
    ax.set_xticks([2015, 2016, 2018, 2020, 2022, 2024])
    ax.text(.01,.02,'ARIMAX is conditional on observed holdout rainfall.',transform=ax.transAxes,fontsize=9)
    ax.legend(fontsize=9)
    save(fig, 'holdout_comparison.png')

def export_results(result, destination):
    destination = Path(destination)
    tables, figures = destination / 'tables', destination / 'figures'
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    for key in ['metrics', 'arima_candidates', 'arimax_candidates', 'stationarity', 'quality',
                'cross_correlation', 'diagnostics']:
        result[key].to_csv(tables / f'{key}.csv', index=False)
    result['future'].to_csv(tables / 'future_forecast.csv', index_label='year')
    result['ses_interval'].to_csv(tables / 'ses_prediction_interval.csv', index_label='year')
    for name in ['ARIMA', 'ARIMAX']:
        result[name.lower()+'_fc'].conf_int().to_csv(tables / f'{name.lower()}_prediction_interval.csv', index_label='year')
    # Export annual holdout predictions, not the original source observations.
    result['forecasts'].drop(columns='actual_c').to_csv(tables / 'holdout_predictions.csv')
    result['data'].describe().to_csv(tables / 'descriptive_statistics.csv', index_label='statistic')
    params = []
    for name in ['ARIMA', 'ARIMAX']:
        m = result['models'][name]
        for term in m.params.index:
            params.append({'model': name, 'term': term, 'coefficient': m.params[term], 'p_value': m.pvalues[term]})
    pd.DataFrame(params).to_csv(tables / 'model_parameters.csv', index=False)
    summary = {'observations': len(result['data']), 'train_observations': len(result['train']),
               'test_observations': len(result['test']), 'trend_c_per_year': result['trend_c_per_year'],
               'pearson_r': result['correlation'], 'future_information_cutoff': result['future_origin']}
    (destination / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    plt.rcParams.update({'font.size': 11, 'axes.spines.top': False, 'axes.spines.right': False})
    data = result['data']
    def save(fig, name):
        fig.tight_layout()
        fig.savefig(figures / name, dpi=160, bbox_inches='tight')
        plt.close(fig)
    render_overview(data, result['forecasts'], result['trend_c_per_year'], figures)
    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    for row, name in enumerate(['ARIMA','ARIMAX']):
        resid=result['models'][name].resid
        if name=='ARIMA':
            resid=resid.iloc[1:]
        title = f'{name}: residual ACF' + (' (initial value omitted)' if name=='ARIMA' else '')
        plot_acf(resid, lags=15, ax=axes[row,0], title=title)
        stats.probplot(resid, plot=axes[row,1])
        axes[row,1].set_title(f'{name}: normal Q–Q plot')
    save(fig, 'residual_diagnostics.png')
    fig, axes = plt.subplots(3, 2, figsize=(11, 9))
    y=result['train'].temperature_c
    for row,(values,label) in enumerate([(y,'Training levels'),(y.diff().dropna(),'First difference'),(y.diff().diff().dropna(),'Second difference')]):
        plot_acf(values,lags=20,ax=axes[row,0],title=f'{label}: ACF')
        plot_pacf(values,lags=20,ax=axes[row,1],method='ywm',title=f'{label}: PACF')
    save(fig, 'stationarity_diagnostics.png')
    fig, axes=plt.subplots(4,1,figsize=(11,8),sharex=True)
    decomp=result['decomposition']
    for ax, component in zip(axes,['observed','trend','seasonal','resid']):
        values=getattr(decomp,component)
        ax.plot(values.index.year,values)
        ax.set_ylabel(component+' (°C)')
    axes[0].set_title('Exploratory additive decomposition: imposed two-year period')
    axes[-1].set_xlabel('Year; annual data cannot identify within-year seasonality')
    save(fig,'exploratory_decomposition.png')
    fig, axes=plt.subplots(1,2,figsize=(11,4))
    axes[0].scatter(data.rainfall_mm,data.temperature_c,color='#175878',s=22)
    axes[0].set(xlabel='Annual rainfall (mm)',ylabel='Temperature (°C)',title=f'Full-sample association: r={result["correlation"]:.3f}')
    cc=result['cross_correlation']
    axes[1].stem(cc.lag_years,cc.CCF)
    for sign in [-1,1]:
        axes[1].axhline(sign*cc.approx_95_bound.iloc[0],ls='--',color='#c07128')
    axes[1].set(xlabel='Lag (years); rainfall leads temperature',ylabel='Cross-correlation',title='Exploratory full-sample CCF')
    save(fig,'rainfall_association.png')
    fig,ax=plt.subplots(figsize=(11,4.5))
    future=result['future']
    ax.plot(data.index.year[-15:],data.temperature_c.iloc[-15:],color='#175878',label='Observed')
    ax.plot(future.index.year,future['mean'],color='#c07128',label='ARIMA point forecast')
    ax.fill_between(future.index.year,future.mean_ci_lower,future.mean_ci_upper,color='#c07128',alpha=.2,label='95% model prediction interval')
    ax.set(title=f'2025–2030 scenario | information cutoff: {result["future_origin"]}',xlabel='Year',ylabel='Temperature (°C)')
    ax.legend(fontsize=9)
    save(fig,'future_scenario.png')
    return destination

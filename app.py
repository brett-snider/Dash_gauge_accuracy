import dash
from dash import dcc, html, Output, Input
import plotly.express as px
import pandas as pd
import pickle
from pathlib import Path
import matplotlib.pyplot as plt
import base64
import io
import requests

def download_pickle_from_gdrive(file_id):
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    response = requests.get(url)
    response.raise_for_status()
    return pickle.load(io.BytesIO(response.content))

# === Load data ===
MERGED_DF_FILE_ID = '15yUqZt8pRJsGbSMrrbzH8Sb2Uuvb6Qic'
RESULTS_FILE_ID = '19lQfRwfSkouvhMfq9ZLF3Wtxc4Gnfw_Y'

# Load the merged DataFrame
merged_df = download_pickle_from_gdrive(MERGED_DF_FILE_ID)

# Load the results dict
results = download_pickle_from_gdrive(RESULTS_FILE_ID)

# Add NSE category for discrete map
merged_df['NSE'] = 'Not Satisfactory: NSE < 0.5'
merged_df.loc[(merged_df['casr_daymet_era5_NSE'] > 0.5) & (merged_df['casr_daymet_era5_NSE'] <= 0.7),'NSE'] = 'Satisfactory: NSE = 0.5-0.7'
merged_df.loc[(merged_df['casr_daymet_era5_NSE'] > 0.7) & (merged_df['casr_daymet_era5_NSE'] <= 0.8),'NSE'] = 'Good: NSE = 0.7-0.8'
merged_df.loc[merged_df['casr_daymet_era5_NSE'] > 0.8,'NSE'] = 'Very Good: NSE > 0.8'

# === Setup Dash App ===
app = dash.Dash(__name__)
app.title = "Streamflow Explorer"

fig = px.scatter_mapbox(
    merged_df,
    lat='lat',
    lon='long',
    color='NSE',
    hover_data=['gauge_id', 'casr_daymet_era5_NSE'],
    color_discrete_map={
        'Not Satisfactory: NSE < 0.5': 'red',
        'Satisfactory: NSE = 0.5-0.7': 'yellow',
        'Good: NSE = 0.7-0.8': 'lightgreen',
        'Very Good: NSE > 0.8': 'green'
    },
    zoom=3
)

fig.update_layout(
    mapbox_style="open-street-map",
    mapbox_center={"lat": merged_df['latitude'].mean(), "lon": merged_df['longitude'].mean()},
    autosize=True,
    margin={"r":0,"t":30,"l":0,"b":0}
)

fig.update_layout(
    legend=dict(
        yanchor="bottom",
        y=0.01,
        xanchor="left",
        x=0.01,
        #bgcolor='rgba(255,255,255,0.8)',  # Optional: white background with transparency
        #bordercolor='black',
        #borderwidth=1
    )
)

fig.update_traces(marker=dict(size=10))

# === App Layout ===
app.layout = html.Div([
    html.H1("Click a Gauge to View Streamflow", style={'textAlign': 'center'}),

    html.Div([
        html.Div([
            dcc.Graph(id='map', figure=fig, style={'height': '90vh'})
        ], style={'width': '60%', 'padding': '10px'}),

        html.Div([
            html.Div(id='gauge-plot-output')
        ], style={'width': '40%', 'padding': '10px', 'overflow': 'auto', 'height': '90vh'})
    ], style={'display': 'flex', 'flexDirection': 'row', 'height': '90vh'})
])

# === Callback ===
@app.callback(
    Output('gauge-plot-output', 'children'),
    Input('map', 'clickData')
)
def update_plot(clickData):
    if not clickData:
        return html.Div("Click a gauge on the map to view the streamflow.")

    gauge_id = clickData['points'][0]['customdata'][0]

    try:
        ds = results[gauge_id]['1D']['xr']
        obs = ds['flow_mm_d_obs'].isel(time_step=-1)
        sim = ds['flow_mm_d_sim'].isel(time_step=-1)

        df = pd.DataFrame({
            'date': obs['date'].values,
            'Observed Flow (mm/d)': obs.values,
            'Simulated Flow (mm/d)': sim.values
        })

        fig_, ax = plt.subplots(figsize=(8, 8))
        ax.plot(df['date'], df['Observed Flow (mm/d)'], label='Observed', color='black')
        ax.plot(df['date'], df['Simulated Flow (mm/d)'], label='Simulated', color='blue', alpha=0.7)
        ax.set_title(f'Streamflow at Gauge {gauge_id}')
        ax.set_xlabel('Date')
        ax.set_ylabel('Flow (mm/day)')
        ax.legend()
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png")
        plt.close(fig_)
        encoded = base64.b64encode(buf.getbuffer()).decode("utf-8")
        return html.Img(src=f"data:image/png;base64,{encoded}")

    except Exception as e:
        return html.Div(f"Error loading streamflow for gauge {gauge_id}: {e}")

# === Run Server ===
if __name__ == '__main__':
    app.run_server(debug=False, host='0.0.0.0', port=10000)

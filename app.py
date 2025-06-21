import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from dashboard_utils import (
    load_and_preprocess_griegas,
    load_and_preprocess_inusual,
    calculate_put_call_ratio,
    calculate_money_at_risk,
    calculate_max_pain,
    calculate_gex,
    calculate_vega_exposure,
    calculate_theta_exposure
)

# --- Configuración de la Página ---
st.set_page_config(
    page_title="Análisis Interactivo de Opciones",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="📊"
)

# --- Tema Oscuro de Plotly ---
# Más adelante, al crear figuras: template="plotly_dark"

# --- Carga y Cacheo de Datos ---
@st.cache_data # Cachear para mejorar rendimiento
def load_data():
    df_griegas = load_and_preprocess_griegas(filepath='Griegas.csv')
    df_inusual = load_and_preprocess_inusual(filepath='Inusual.csv')

    # Asegurarse de que las columnas clave para cálculos no tengan NaNs o manejarlos
    if df_griegas is not None:
        cols_to_check_griegas = ['Strike', 'Type', 'OpenInterest', 'Gamma', 'Vega', 'Theta', 'MidPrice', 'Volume']
        for col in cols_to_check_griegas:
            if col not in df_griegas.columns:
                st.error(f"Columna requerida '{col}' no encontrada en Griegas.csv después del preprocesamiento.")
                return None, None
        # No eliminar NaNs globalmente aquí, se hará selectivamente en las funciones de cálculo si es necesario
        # o se manejarán en los cálculos (e.g. fillna(0) para MidPrice en MoneyAtRisk)

    if df_inusual is not None:
        cols_to_check_inusual = ['Strike', 'Type', 'Premium', 'Size', 'Trade', 'Volume', 'OpenInterest', 'IV', 'Delta']
        for col in cols_to_check_inusual:
            if col not in df_inusual.columns:
                st.error(f"Columna requerida '{col}' no encontrada en Inusual.csv después del preprocesamiento.")
                return None, None

    return df_griegas, df_inusual

df_griegas, df_inusual = load_data()

# --- Barra Lateral de Filtros (Opcional por ahora, se puede añadir después) ---
st.sidebar.header("Filtros")
# --- Barra Lateral de Filtros ---
st.sidebar.header("Filtros")
df_griegas_display = df_griegas # df_griegas es el cargado globalmente

if df_griegas is not None and not df_griegas.empty and 'ExpirationDate' in df_griegas.columns:
    # Convertir ExpirationDate a datetime si no lo está ya (aunque el preproc debería hacerlo)
    if not pd.api.types.is_datetime64_any_dtype(df_griegas['ExpirationDate']):
        df_griegas['ExpirationDate'] = pd.to_datetime(df_griegas['ExpirationDate'], errors='coerce')

    exp_dates = sorted(df_griegas['ExpirationDate'].dropna().unique())

    if exp_dates:
        formatted_exp_dates = [pd.to_datetime(d).strftime('%Y-%m-%d') for d in exp_dates]

        if len(exp_dates) > 1:
            selected_exp_date_str = st.sidebar.selectbox(
                "Seleccionar Vencimiento (Cadena Principal):",
                formatted_exp_dates,
                index=len(formatted_exp_dates) - 1
            )
            selected_exp_date = pd.to_datetime(selected_exp_date_str)
            df_griegas_display = df_griegas[df_griegas['ExpirationDate'] == selected_exp_date].copy()
        elif exp_dates: # Solo una fecha de expiración
            df_griegas_display = df_griegas.copy()
            # st.sidebar.info(f"Datos para vencimiento: {formatted_exp_dates[0]}") # Opcional: no mostrar si solo hay uno
        else: # No hay fechas de expiración válidas
             df_griegas_display = pd.DataFrame() # DataFrame vacío para evitar errores downstream
             st.sidebar.warning("No se encontraron fechas de expiración válidas.")

    else:
         df_griegas_display = pd.DataFrame()
         st.sidebar.warning("No hay fechas de expiración en los datos de Griegas.csv.")
else:
    df_griegas_display = pd.DataFrame() # Si df_griegas es None o está vacío
    # st.sidebar.info("No hay datos de la cadena de opciones para filtrar por vencimiento.")


# --- Título Principal ---
st.title("📊 Dashboard Interactivo de Análisis de Opciones")
st.markdown("Análisis basado en `Griegas.csv` y `Inusual.csv`.")

# --- Cuerpo Principal del Dashboard ---
if df_griegas_display.empty:
    st.warning("No hay datos de la cadena de opciones para mostrar según los filtros seleccionados o los datos cargados. Por favor, verifique los archivos CSV o los filtros.")
else:
    # --- Métricas Clave (KPIs) ---
    st.header("Métricas Clave del Mercado de Opciones")

    # Calcular métricas generales
    underlying_price = df_griegas_display['UnderlyingPrice'].iloc[0] if not df_griegas_display.empty and 'UnderlyingPrice' in df_griegas_display.columns and pd.notna(df_griegas_display['UnderlyingPrice'].iloc[0]) else "N/A"
    total_volume = df_griegas_display['Volume'].sum() if not df_griegas_display.empty and 'Volume' in df_griegas_display.columns else 0
    total_oi = df_griegas_display['OpenInterest'].sum() if not df_griegas_display.empty and 'OpenInterest' in df_griegas_display.columns else 0

    # PC Ratios totales
    pc_ratios_total_df = calculate_put_call_ratio(df_griegas_display, group_by_strike=False) if not df_griegas_display.empty else pd.DataFrame()
    pc_volume_total = pc_ratios_total_df['PC_Volume_Ratio'].iloc[0] if not pc_ratios_total_df.empty else np.nan
    pc_oi_total = pc_ratios_total_df['PC_OI_Ratio'].iloc[0] if not pc_ratios_total_df.empty else np.nan

    # Max Pain
    max_pain_strike = calculate_max_pain(df_griegas_display.copy().dropna(subset=['Strike', 'Type', 'OpenInterest']))

    # Gamma Flip
    gex_df, gamma_flip_point = calculate_gex(df_griegas_display.copy().dropna(subset=['Strike', 'Gamma', 'OpenInterest']))


    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Precio Subyacente", f"${underlying_price:,.2f}" if isinstance(underlying_price, (int,float)) else underlying_price,
                help="Precio del activo subyacente para la fecha de expiración seleccionada.")
    col2.metric("Volumen Total Opciones", f"{total_volume:,.0f}",
                help="Suma del volumen de todas las opciones (Calls y Puts) para el vencimiento seleccionado.")
    col3.metric("Open Interest Total", f"{total_oi:,.0f}",
                help="Suma del Open Interest de todas las opciones (Calls y Puts) para el vencimiento seleccionado.")
    col4.metric("P/C Ratio (Volumen)", f"{pc_volume_total:.2f}" if pd.notna(pc_volume_total) else "N/A",
                help="Ratio Put/Call basado en el volumen total para el vencimiento seleccionado.")
    col5.metric("P/C Ratio (OI)", f"{pc_oi_total:.2f}" if pd.notna(pc_oi_total) else "N/A",
                help="Ratio Put/Call basado en el Open Interest total para el vencimiento seleccionado.")

    st.markdown("---")
    kpi_col1, kpi_col2 = st.columns(2)
    with kpi_col1:
        st.metric(label="Max Pain Strike", value=f"${max_pain_strike:,.2f}" if max_pain_strike is not None else "N/A",
                  help="Strike teórico donde la mayor cantidad de compradores de opciones perderían su inversión al vencimiento.")
    with kpi_col2:
        st.metric(label="Gamma Flip Point", value=f"${gamma_flip_point:,.2f}" if gamma_flip_point is not None else "N/A",
                  help="Nivel de precio (strike) donde la Exposición a Gamma (GEX) neta del dealer podría cambiar de signo o es mínima.")
    st.markdown("---")


    # --- Sección 1: Cadena de Opciones y Griegas Principales ---
    st.header("Visión General de la Cadena de Opciones")

    if df_griegas_display.empty:
        st.warning("No hay datos de la cadena de opciones para mostrar con el vencimiento seleccionado.")
    else:
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Gráficos Agregados", "📈 Perfil de Volatilidad", "📋 Tabla Cadena Completa", "⚙️ Put/Call Ratios por Strike"])

        with tab1:
            st.subheader("Volumen y Open Interest por Strike")
            try:
                if 'Type' not in df_griegas_display.columns or 'Volume' not in df_griegas_display.columns or 'OpenInterest' not in df_griegas_display.columns:
                    st.error("Columnas requeridas (Type, Volume, OpenInterest) no encontradas para el gráfico de Volumen/OI.")
                else:
                    strike_analysis = df_griegas_display.groupby('Strike').agg(
                        CallVolume=('Volume', lambda x: x[df_griegas_display.loc[x.index, 'Type'] == 'call'].sum()),
                        PutVolume=('Volume', lambda x: x[df_griegas_display.loc[x.index, 'Type'] == 'put'].sum()),
                        CallOI=('OpenInterest', lambda x: x[df_griegas_display.loc[x.index, 'Type'] == 'call'].sum()),
                        PutOI=('OpenInterest', lambda x: x[df_griegas_display.loc[x.index, 'Type'] == 'put'].sum())
                    ).reset_index()

                    if strike_analysis.empty:
                        st.info("No hay datos agregados de Volumen/OI por strike para mostrar.")
                    else:
                        fig_oi_vol = make_subplots(rows=1, cols=2, subplot_titles=("Volumen por Strike", "Open Interest por Strike"))

                    fig_oi_vol.add_trace(go.Bar(x=strike_analysis['Strike'], y=strike_analysis['CallVolume'], name='Call Volume', marker_color='green', hovertemplate='Strike: %{x}<br>Call Volume: %{y:,.0f}<extra></extra>'), row=1, col=1)
                    fig_oi_vol.add_trace(go.Bar(x=strike_analysis['Strike'], y=strike_analysis['PutVolume'], name='Put Volume', marker_color='red', hovertemplate='Strike: %{x}<br>Put Volume: %{y:,.0f}<extra></extra>'), row=1, col=1)

                    fig_oi_vol.add_trace(go.Bar(x=strike_analysis['Strike'], y=strike_analysis['CallOI'], name='Call OI', marker_color='lightgreen', opacity=0.7, hovertemplate='Strike: %{x}<br>Call OI: %{y:,.0f}<extra></extra>'), row=1, col=2)
                    fig_oi_vol.add_trace(go.Bar(x=strike_analysis['Strike'], y=strike_analysis['PutOI'], name='Put OI', marker_color='salmon', opacity=0.7, hovertemplate='Strike: %{x}<br>Put OI: %{y:,.0f}<extra></extra>'), row=1, col=2)

                    fig_oi_vol.update_layout(barmode='stack', height=400, template="plotly_dark", title_text="Volumen y Open Interest Agregado por Strike", xaxis_title="Strike")
                    st.plotly_chart(fig_oi_vol, use_container_width=True)
            except Exception as e:
                st.error(f"Error al generar gráfico de Volumen/OI: {e}")


        with tab2:
            st.subheader("Perfil de Volatilidad Implícita (IV Smile/Skew)")
            try:
                if 'Type' not in df_griegas_display.columns or 'IV' not in df_griegas_display.columns:
                    st.error("Columnas 'Type' o 'IV' no encontradas para el gráfico de volatilidad.")
                else:
                    iv_calls = df_griegas_display[df_griegas_display['Type'] == 'call'].groupby('Strike', as_index=False)['IV'].mean()
                    iv_puts = df_griegas_display[df_griegas_display['Type'] == 'put'].groupby('Strike', as_index=False)['IV'].mean()

                    fig_iv = go.Figure()
                    if not iv_calls.empty:
                        fig_iv.add_trace(go.Scatter(x=iv_calls['Strike'], y=iv_calls['IV'], mode='lines+markers', name='IV Calls', line=dict(color='green'), hovertemplate='Strike: %{x}<br>IV Call: %{y:.2%}<extra></extra>'))
                    if not iv_puts.empty:
                        fig_iv.add_trace(go.Scatter(x=iv_puts['Strike'], y=iv_puts['IV'], mode='lines+markers', name='IV Puts', line=dict(color='red'), hovertemplate='Strike: %{x}<br>IV Put: %{y:.2%}<extra></extra>'))

                    if underlying_price != "N/A" and isinstance(underlying_price, (int, float)):
                         fig_iv.add_vline(x=underlying_price, line_width=2, line_dash="dash", line_color="grey", annotation_text="Precio Subyacente")

                    fig_iv.update_layout(title='Volatilidad Implícita Promedio por Strike', xaxis_title='Strike', yaxis_title='Volatilidad Implícita',
                                         height=400, template="plotly_dark", yaxis_tickformat=".2%")
                    if not iv_calls.empty or not iv_puts.empty:
                        st.plotly_chart(fig_iv, use_container_width=True)
                    else:
                        st.info("No hay datos de IV para mostrar.")
            except Exception as e:
                st.error(f"Error al generar gráfico de IV: {e}")

        with tab3:
            st.subheader("Tabla Completa de la Cadena de Opciones")
            try:
                cols_to_display_griegas = ['Symbol', 'Type', 'Strike', 'ExpirationDate', 'UnderlyingPrice',
                                           'Bid', 'Ask', 'MidPrice', 'Volume', 'OpenInterest', 'IV',
                                           'Delta', 'Gamma', 'Theta', 'Vega', 'LastTradeDate']
                display_df_griegas_table = df_griegas_display[[col for col in cols_to_display_griegas if col in df_griegas_display.columns]]

                column_config_griegas = {
                    "Strike": st.column_config.NumberColumn(format="%.2f"),
                    "UnderlyingPrice": st.column_config.NumberColumn(format="$%.2f"),
                    "Bid": st.column_config.NumberColumn(format="$%.2f"),
                    "Ask": st.column_config.NumberColumn(format="$%.2f"),
                    "MidPrice": st.column_config.NumberColumn(format="$%.2f"),
                    "Volume": st.column_config.NumberColumn(format="%d"),
                    "OpenInterest": st.column_config.NumberColumn(format="%d"),
                    "IV": st.column_config.NumberColumn(format="%.2f%%"),
                    "Delta": st.column_config.NumberColumn(format="%.4f"),
                    "Gamma": st.column_config.NumberColumn(format="%.4f"),
                    "Theta": st.column_config.NumberColumn(format="%.4f"),
                    "Vega": st.column_config.NumberColumn(format="%.4f"),
                    "ExpirationDate": st.column_config.DateColumn(format="YYYY-MM-DD"),
                    "LastTradeDate": st.column_config.DatetimeColumn(format="YYYY-MM-DD HH:mm:ss", timezone=None) # Asumir UTC o sin TZ si no se especifica
                }
                active_column_config = {k: v for k, v in column_config_griegas.items() if k in display_df_griegas_table.columns}

                st.dataframe(display_df_griegas_table, height=400, use_container_width=True, column_config=active_column_config)
            except Exception as e:
                st.error(f"Error al mostrar tabla de cadena de opciones: {e}")


        with tab4:
            st.subheader("Put/Call Ratios por Strike")
            try:
                pc_ratios_strike_df = calculate_put_call_ratio(df_griegas_display, group_by_strike=True)
                if not pc_ratios_strike_df.empty:
                    fig_pc_strike = make_subplots(rows=1, cols=2, subplot_titles=("P/C Ratio Volumen", "P/C Ratio Open Interest"))
                    fig_pc_strike.add_trace(go.Bar(x=pc_ratios_strike_df['Strike'], y=pc_ratios_strike_df['PC_Volume_Ratio'], name='P/C Vol Ratio', hovertemplate='Strike: %{x}<br>P/C Vol: %{y:.2f}<extra></extra>'), row=1, col=1)
                    fig_pc_strike.add_trace(go.Bar(x=pc_ratios_strike_df['Strike'], y=pc_ratios_strike_df['PC_OI_Ratio'], name='P/C OI Ratio', hovertemplate='Strike: %{x}<br>P/C OI: %{y:.2f}<extra></extra>'), row=1, col=2)
                    fig_pc_strike.update_layout(height=400, template="plotly_dark", showlegend=False, xaxis_title="Strike")
                    st.plotly_chart(fig_pc_strike, use_container_width=True)
                    st.dataframe(pc_ratios_strike_df, use_container_width=True, column_config={"Strike": st.column_config.NumberColumn(format="%.2f")})
                else:
                    st.info("No hay suficientes datos para calcular P/C Ratios por strike.")
            except Exception as e:
                st.error(f"Error al generar P/C Ratios por strike: {e}")


    st.markdown("---")
    # --- Sección 2: Análisis de Riesgo y Sentimiento ---
    st.header("Análisis de Riesgo y Sentimiento del Mercado")

    if df_griegas_display.empty:
        st.warning("No hay datos de la cadena de opciones para mostrar análisis de riesgo con el vencimiento seleccionado.")
    else:
        risk_tab1, risk_tab2, risk_tab3, risk_tab4 = st.tabs(["💰 Dinero en Riesgo", "📉 Exposición a Gamma (GEX)", "🌬️ Exposición a Vega", "⏳ Exposición a Theta"])

        with risk_tab1:
            st.subheader("Dinero en Riesgo (Money at Risk) por Strike")
            try:
                money_at_risk_df = calculate_money_at_risk(df_griegas_display.copy())
                if not money_at_risk_df.empty:
                    fig_mar = px.bar(money_at_risk_df, x='Strike', y='MoneyAtRisk', title='Dinero en Riesgo por Strike',
                                     labels={'MoneyAtRisk': 'Dinero en Riesgo ($)'}) # Paréntesis cerrado correctamente
                    fig_mar.update_traces(hovertemplate='Strike: %{x}<br>Dinero en Riesgo: $%{y:,.0f}<extra></extra>')
                    fig_mar.update_layout(height=400, template="plotly_dark", yaxis_tickformat="$,.0f", xaxis_title="Strike")
                    if underlying_price != "N/A" and isinstance(underlying_price, (int, float)):
                        fig_mar.add_vline(x=underlying_price, line_width=2, line_dash="dash", line_color="grey", annotation_text="Precio Subyacente")
                    st.plotly_chart(fig_mar, use_container_width=True)
                    st.dataframe(money_at_risk_df.sort_values(by='MoneyAtRisk', ascending=False), use_container_width=True,
                                 column_config={"MoneyAtRisk": st.column_config.NumberColumn(format="$%d"),
                                                "Strike": st.column_config.NumberColumn(format="%.2f")})
                else:
                    st.info("No hay suficientes datos para calcular Dinero en Riesgo.")
            except Exception as e:
                st.error(f"Error al calcular Dinero en Riesgo: {e}")

        with risk_tab2:
            st.subheader(f"Exposición a Gamma (Dealer GEX)")
            try:
                if not gex_df.empty: # gex_df y gamma_flip_point se calculan arriba en KPIs
                    fig_gex = make_subplots(specs=[[{"secondary_y": True}]])
                    fig_gex.add_trace(go.Bar(x=gex_df['Strike'], y=gex_df['DealerGEX'], name='Dealer GEX por Strike', marker_color='purple', hovertemplate='Strike: %{x}<br>Dealer GEX: %{y:,.0f}<extra></extra>'), secondary_y=False)
                    fig_gex.add_trace(go.Scatter(x=gex_df['Strike'], y=gex_df['CumulativeDealerGEX'], name='GEX Acumulado', mode='lines', line=dict(color='orange'), hovertemplate='Strike: %{x}<br>GEX Acumulado: %{y:,.0f}<extra></extra>'), secondary_y=True)

                    if gamma_flip_point is not None and isinstance(gamma_flip_point, (int,float)):
                         fig_gex.add_vline(x=gamma_flip_point, line_width=2, line_dash="dash", line_color="cyan", annotation_text=f"Gamma Flip: {gamma_flip_point:,.2f}")
                    if underlying_price != "N/A" and isinstance(underlying_price, (int, float)):
                        fig_gex.add_vline(x=underlying_price, line_width=2, line_dash="dash", line_color="grey", annotation_text="Precio Subyacente")

                    fig_gex.update_layout(title='Exposición a Gamma del Dealer (GEX)', height=500, template="plotly_dark", xaxis_title="Strike")
                    fig_gex.update_yaxes(title_text="Dealer GEX por Strike", secondary_y=False, tickformat=",.0f")
                    fig_gex.update_yaxes(title_text="GEX Acumulado del Dealer", secondary_y=True, tickformat=",.0f")
                    st.plotly_chart(fig_gex, use_container_width=True)
                    st.dataframe(gex_df.sort_values(by='DealerGEX', key=abs, ascending=False), use_container_width=True,
                                 column_config={
                                     "DealerGEX": st.column_config.NumberColumn(format="%.0f"),
                                     "CumulativeDealerGEX": st.column_config.NumberColumn(format="%.0f"),
                                     "Strike": st.column_config.NumberColumn(format="%.2f")
                                 })
                else:
                    st.info("No hay suficientes datos para calcular GEX.")
            except Exception as e:
                st.error(f"Error al generar gráfico/tabla de GEX: {e}")

        with risk_tab3:
            st.subheader("Exposición a Vega (Dealer)")
            try:
                vega_exposure_df = calculate_vega_exposure(df_griegas_display.copy().dropna(subset=['Strike', 'Vega', 'OpenInterest']))
                if not vega_exposure_df.empty:
                    fig_vega = px.bar(vega_exposure_df, x='Strike', y='DealerVegaExposure', title='Exposición a Vega del Dealer por Strike',
                                      labels={'DealerVegaExposure': 'Exposición a Vega ($ por 1% cambio IV)'}, color='DealerVegaExposure',
                                      color_continuous_scale=px.colors.diverging.Picnic) # Paréntesis cerrado correctamente
                    fig_vega.update_traces(hovertemplate='Strike: %{x}<br>Exposición Vega: $%{y:,.0f}<extra></extra>')
                    fig_vega.update_layout(height=400, template="plotly_dark", yaxis_tickformat="$,.0f", xaxis_title="Strike")
                    if underlying_price != "N/A" and isinstance(underlying_price, (int, float)):
                        fig_vega.add_vline(x=underlying_price, line_width=2, line_dash="dash", line_color="grey", annotation_text="Precio Subyacente")
                    st.plotly_chart(fig_vega, use_container_width=True)
                    st.dataframe(vega_exposure_df.sort_values(by='DealerVegaExposure', key=abs, ascending=False), use_container_width=True,
                                 column_config={"DealerVegaExposure": st.column_config.NumberColumn(format="$%d"),
                                                "Strike": st.column_config.NumberColumn(format="%.2f")})
                else:
                    st.info("No hay suficientes datos para calcular Exposición a Vega.")
            except Exception as e:
                st.error(f"Error al calcular Exposición a Vega: {e}")

        with risk_tab4:
            st.subheader("Exposición a Theta (Dealer)")
            try:
                theta_exposure_df = calculate_theta_exposure(df_griegas_display.copy().dropna(subset=['Strike', 'Theta', 'OpenInterest']))
                if not theta_exposure_df.empty:
                    fig_theta = px.bar(theta_exposure_df, x='Strike', y='DealerThetaExposure', title='Exposición a Theta del Dealer por Strike',
                                       labels={'DealerThetaExposure': 'Exposición a Theta ($ por día)'}, color='DealerThetaExposure',
                                       color_continuous_scale=px.colors.diverging.Geyser) # Paréntesis cerrado correctamente
                    fig_theta.update_traces(hovertemplate='Strike: %{x}<br>Exposición Theta: $%{y:,.0f}<extra></extra>')
                    fig_theta.update_layout(height=400, template="plotly_dark", yaxis_tickformat="$,.0f", xaxis_title="Strike")
                    if underlying_price != "N/A" and isinstance(underlying_price, (int, float)):
                        fig_theta.add_vline(x=underlying_price, line_width=2, line_dash="dash", line_color="grey", annotation_text="Precio Subyacente")
                    st.plotly_chart(fig_theta, use_container_width=True)
                    st.dataframe(theta_exposure_df.sort_values(by='DealerThetaExposure', ascending=False), use_container_width=True,
                                 column_config={"DealerThetaExposure": st.column_config.NumberColumn(format="$%d"),
                                                "Strike": st.column_config.NumberColumn(format="%.2f")})
                else:
                    st.info("No hay suficientes datos para calcular Exposición a Theta.")
            except Exception as e:
                st.error(f"Error al calcular Exposición a Theta: {e}")

    st.markdown("---")
    # --- Sección 3: Option Flow Inusual ---
    st.header("Análisis de Option Flow Inusual")
    if df_inusual is None:
        st.error("No se pudieron cargar o procesar los datos de Inusual.csv. Por favor, verifique el archivo.")
    elif df_inusual.empty:
        st.info("No hay datos de operaciones inusuales para mostrar (Inusual.csv está vacío o no contiene datos).")
    else:
        st.subheader("Operaciones Inusuales Registradas")

        flow_cols = st.columns(3)

        min_premium_default = 0
        if 'Premium' in df_inusual.columns and df_inusual['Premium'].count() > 0: # count ignora NaNs
            quantile_val = df_inusual['Premium'].quantile(0.25)
            if pd.notna(quantile_val):
                min_premium_default = int(quantile_val)
        min_premium = flow_cols[0].number_input("Premium Mínimo:", value=min_premium_default, step=10000, min_value=0, help="Filtrar operaciones por el premium total mínimo.")

        available_sides = []
        if 'Side' in df_inusual.columns:
            available_sides = sorted(df_inusual['Side'].dropna().unique().tolist())
        selected_sides = flow_cols[1].multiselect("Filtrar por 'Side':", options=available_sides, default=available_sides, help="Seleccionar los 'Side' de las operaciones (ej. bid, ask, mid).")

        available_oc = []
        if 'OpenClose' in df_inusual.columns:
            available_oc = sorted(df_inusual['OpenClose'].dropna().unique().tolist())
        selected_oc = flow_cols[2].multiselect("Filtrar por Apertura/Cierre:", options=available_oc, default=available_oc, help="Filtrar por el tipo de apertura o cierre de la operación (ej. ToOpen, SellToOpen).")

        # Construir condiciones de filtrado
        conditions = pd.Series([True] * len(df_inusual)) # Empezar con todos True
        if 'Premium' in df_inusual.columns:
            conditions &= (df_inusual['Premium'].fillna(0) >= min_premium)
        if selected_sides and 'Side' in df_inusual.columns: # Solo filtrar si hay selecciones y la columna existe
            conditions &= df_inusual['Side'].isin(selected_sides)
        if selected_oc and 'OpenClose' in df_inusual.columns: # Solo filtrar si hay selecciones y la columna existe
            conditions &= df_inusual['OpenClose'].isin(selected_oc)

        df_inusual_filtered = df_inusual[conditions]

        cols_to_display_inusual = ['Symbol', 'Type', 'Strike', 'ExpirationDate', 'TradeTime', 'Side', 'OpenClose',
                                   'Trade', 'Size', 'Premium', 'Volume', 'OpenInterest', 'IV', 'Delta', 'UnderlyingPrice']
        display_df_inusual_table = df_inusual_filtered[[col for col in cols_to_display_inusual if col in df_inusual_filtered.columns]]

        column_config_inusual = {
            "Strike": st.column_config.NumberColumn(format="%.2f"),
            "UnderlyingPrice": st.column_config.NumberColumn(format="$%.2f"),
            "Trade": st.column_config.NumberColumn(format="$%.2f"),
            "Size": st.column_config.NumberColumn(format="%d"),
            "Premium": st.column_config.NumberColumn(format="$%d"),
            "Volume": st.column_config.NumberColumn(format="%d"),
            "OpenInterest": st.column_config.NumberColumn(format="%d"),
            "IV": st.column_config.NumberColumn(format="%.2f%%"),
            "Delta": st.column_config.NumberColumn(format="%.4f"),
            "ExpirationDate": st.column_config.DateColumn(format="YYYY-MM-DD"),
        }
        active_column_config_inusual = {k:v for k,v in column_config_inusual.items() if k in display_df_inusual_table.columns}

        st.dataframe(display_df_inusual_table, height=300, use_container_width=True, column_config=active_column_config_inusual)

        st.subheader("Visualización del Flujo Inusual")
        if not df_inusual_filtered.empty:
            try:
                fig_flow = px.scatter(df_inusual_filtered, x='Strike', y='Premium',
                                      size='Size', color='Type', hover_name='Symbol',
                                      hover_data={ # Personalizar hover data y su formato si es necesario
                                          'ExpirationDate': True, # Mostrar fecha
                                          'Trade': ':.2f', # Formato para Trade Price
                                          'Side': True,
                                          'OpenClose': True,
                                          'Volume': ':,', # Formato para Volume
                                          'OpenInterest': ':,', # Formato para OI
                                          'IV': ':.2%', # Formato para IV
                                          'UnderlyingPrice': ':.2f',
                                          'Premium': ':$,.0f' # Formato para Premium
                                      },
                                      title='Flujo de Opciones Inusuales (Tamaño por Cantidad de Contratos)',
                                      labels={'Premium': 'Premium Total ($)', 'Size': 'Nº Contratos'},
                                      color_discrete_map={'call': 'green', 'put': 'red'})
                fig_flow.update_layout(height=500, template="plotly_dark", xaxis_title="Strike", yaxis_title="Premium Total ($)", yaxis_tickformat="$,.0f")
                if underlying_price != "N/A" and isinstance(underlying_price, (int, float)):
                    fig_flow.add_vline(x=underlying_price, line_width=2, line_dash="dash", line_color="grey", annotation_text="Precio Subyacente (Cadena)")
                st.plotly_chart(fig_flow, use_container_width=True)

                fig_flow_dist = px.histogram(df_inusual_filtered, x='Premium', color='Type',
                                             marginal='box',
                                             title='Distribución del Premium en Operaciones Inusuales',
                                             labels={'Premium': 'Premium Total ($)'},
                                             color_discrete_map={'call': 'green', 'put': 'red'},
                                             hover_data={'Premium': ':$,.0f'})
                fig_flow_dist.update_layout(height=400, template="plotly_dark", xaxis_title="Premium Total ($)", xaxis_tickformat="$,.0f")
                st.plotly_chart(fig_flow_dist, use_container_width=True)
            except Exception as e:
                st.error(f"Error al generar gráficos de flujo inusual: {e}")
        else:
            st.info("No hay operaciones inusuales que coincidan con los filtros actuales para graficar.")

# --- Footer o información adicional (opcional) ---
st.sidebar.markdown("---")
st.sidebar.info("Desarrollado por Jules IA. Todos los datos son de ejemplo y no constituyen asesoramiento financiero.")

# Para ejecutar: streamlit run app.py

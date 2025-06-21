import pandas as pd
import numpy as np

def clean_numeric_column(series):
    """Limpia una columna numérica eliminando comas y convirtiendo a float."""
    if series.dtype == 'object':
        series = series.str.replace(',', '', regex=False)
        series = series.replace(['unch', 'N/A', ''], np.nan, regex=False)
    return pd.to_numeric(series, errors='coerce')

def clean_percentage_column(series):
    """Limpia una columna de porcentaje eliminando '%' y convirtiendo a float."""
    if series.dtype == 'object':
        series = series.str.rstrip('%')
        series = series.replace(['unch', 'N/A', ''], np.nan, regex=False)
    return pd.to_numeric(series, errors='coerce') / 100.0

def load_and_preprocess_griegas(filepath='Griegas.csv'):
    """Carga y preprocesa el archivo Griegas.csv."""
    try:
        df = pd.read_csv(filepath)
    except FileNotFoundError:
        print(f"Error: El archivo {filepath} no fue encontrado.")
        return None
    except Exception as e:
        print(f"Error al leer el archivo {filepath}: {e}")
        return None

    # Renombrar columnas para consistencia y facilidad de uso
    df.rename(columns={
        'Price~': 'UnderlyingPrice',
        'Exp Date': 'ExpirationDate',
        'Open Int': 'OpenInterest',
        'ITM Prob': 'ITMProbability'
    }, inplace=True)

    # Limpieza de columnas numéricas y de porcentaje
    numeric_cols = ['UnderlyingPrice', 'Strike', 'Bid', 'Ask', 'Volume', 'OpenInterest',
                    'Delta', 'Gamma', 'Theta', 'Vega']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = clean_numeric_column(df[col])

    percentage_cols = ['IV', 'ITMProbability']
    for col in percentage_cols:
        if col in df.columns:
            df[col] = clean_percentage_column(df[col])
            if col == 'IV': # IV suele mostrarse como % pero se usa como decimal en cálculos
                 pass # ya está dividido por 100

    # Convertir fechas
    if 'ExpirationDate' in df.columns:
        df['ExpirationDate'] = pd.to_datetime(df['ExpirationDate'], errors='coerce')
    if 'Time' in df.columns: # 'Time' en Griegas.csv parece ser la fecha de última operación
        df['LastTradeDate'] = pd.to_datetime(df['Time'], errors='coerce')
        # df.drop(columns=['Time'], inplace=True)


    # Calcular Mid Price
    if 'Bid' in df.columns and 'Ask' in df.columns:
        df['MidPrice'] = (df['Bid'] + df['Ask']) / 2
    else:
        df['MidPrice'] = np.nan

    # Asegurar que Type (Call/Put) sea consistente (ej. minúsculas)
    if 'Type' in df.columns:
        df['Type'] = df['Type'].str.lower()

    return df

def load_and_preprocess_inusual(filepath='Inusual.csv'):
    """Carga y preprocesa el archivo Inusual.csv."""
    try:
        df = pd.read_csv(filepath)
    except FileNotFoundError:
        print(f"Error: El archivo {filepath} no fue encontrado.")
        return None
    except Exception as e:
        print(f"Error al leer el archivo {filepath}: {e}")
        return None

    df.rename(columns={
        'Price~': 'UnderlyingPrice',
        'Open Int': 'OpenInterest',
        'Expires': 'ExpirationDateTime',
        '*': 'OpenClose'
    }, inplace=True)

    numeric_cols = ['UnderlyingPrice', 'Strike', 'Trade', 'Size', 'Premium', 'Volume', 'OpenInterest', 'Delta']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = clean_numeric_column(df[col])

    percentage_cols = ['IV']
    for col in percentage_cols:
        if col in df.columns:
            df[col] = clean_percentage_column(df[col])

    if 'ExpirationDateTime' in df.columns:
        df['ExpirationDate'] = pd.to_datetime(df['ExpirationDateTime'], errors='coerce').dt.date
        df['ExpirationDate'] = pd.to_datetime(df['ExpirationDate'], errors='coerce')


    if 'Time' in df.columns: # 'Time' en Inusual.csv es la hora de la operación
        df['TradeTime'] = df['Time'] # Mantenerla como string por ahora o parsear si es necesario
        # df.drop(columns=['Time'], inplace=True)

    if 'Type' in df.columns:
        df['Type'] = df['Type'].str.lower()

    # Limpiar DTE y convertir a numérico si existe
    if 'DTE' in df.columns:
        df['DTE'] = clean_numeric_column(df['DTE'])

    return df

if __name__ == '__main__':
    # Prueba de carga de datos
    df_griegas = load_and_preprocess_griegas()
    if df_griegas is not None:
        print("Griegas.csv cargado y preprocesado:")
        print(df_griegas.head().to_markdown(index=False))
        print("\nTipos de datos de Griegas.csv procesado:")
        print(df_griegas.dtypes)
        # Verificar columnas problemáticas de CADENA.csv si se usara como fallback
        # print(df_griegas[['Volume', 'OpenInterest']].head())
        # print(f"Valores nulos en MidPrice: {df_griegas['MidPrice'].isnull().sum()}")
        # print(f"Valores nulos en IV: {df_griegas['IV'].isnull().sum()}")


    df_inusual = load_and_preprocess_inusual()
    if df_inusual is not None:
        print("\nInusual.csv cargado y preprocesado:")
        print(df_inusual.head().to_markdown(index=False))
        print("\nTipos de datos de Inusual.csv procesado:")
        print(df_inusual.dtypes)
        # print(df_inusual[['Premium', 'IV', 'ExpirationDate']].head())

    # Podríamos añadir una función para CADENA.csv si decidimos que es necesaria,
    # pero el plan actual se centra en Griegas.csv
    # def load_and_preprocess_cadena(filepath='CADENA.csv'):
    # ... (similar a las otras, con su limpieza específica)
    # pass

# --- Funciones de Cálculo de Métricas ---

def calculate_put_call_ratio(df_griegas, group_by_strike=True):
    """Calcula el Put/Call ratio para Volumen y Open Interest."""
    if df_griegas is None or df_griegas.empty:
        return pd.DataFrame()

    ratios = []

    if group_by_strike:
        grouped = df_griegas.groupby('Strike')
    else:
        # Para un ratio total, creamos un grupo artificial
        df_griegas['Total'] = 'Total'
        grouped = df_griegas.groupby('Total')

    for name, group in grouped:
        puts_volume = group[group['Type'] == 'put']['Volume'].sum()
        calls_volume = group[group['Type'] == 'call']['Volume'].sum()
        puts_oi = group[group['Type'] == 'put']['OpenInterest'].sum()
        calls_oi = group[group['Type'] == 'call']['OpenInterest'].sum()

        pc_volume_ratio = puts_volume / calls_volume if calls_volume > 0 else np.nan
        pc_oi_ratio = puts_oi / calls_oi if calls_oi > 0 else np.nan

        if group_by_strike:
            ratios.append({'Strike': name, 'PC_Volume_Ratio': pc_volume_ratio, 'PC_OI_Ratio': pc_oi_ratio})
        else:
            ratios.append({'Level': name, 'PC_Volume_Ratio': pc_volume_ratio, 'PC_OI_Ratio': pc_oi_ratio})

    if not group_by_strike:
         df_griegas.drop(columns=['Total'], inplace=True)

    return pd.DataFrame(ratios)

def calculate_money_at_risk(df_griegas):
    """Calcula el Dinero en Riesgo por strike."""
    if df_griegas is None or df_griegas.empty or 'OpenInterest' not in df_griegas.columns or 'MidPrice' not in df_griegas.columns:
        return pd.DataFrame()

    # Asegurarse que MidPrice no sea NaN para el cálculo, o reemplazar por 0 si es apropiado
    df_griegas['MidPriceFilled'] = df_griegas['MidPrice'].fillna(0)
    df_griegas['MoneyAtRisk'] = df_griegas['OpenInterest'] * df_griegas['MidPriceFilled'] * 100 # Multiplicador estándar de opciones

    # Agrupar por strike
    money_at_risk_strike = df_griegas.groupby('Strike')['MoneyAtRisk'].sum().reset_index()
    return money_at_risk_strike

def calculate_max_pain(df_griegas):
    """Calcula el Max Pain strike."""
    if df_griegas is None or df_griegas.empty:
        return None

    strikes = sorted(df_griegas['Strike'].unique())
    max_pain_data = []

    for current_strike_price_at_expiry in strikes:
        total_loss = 0
        # Para Calls: Pérdida si Strike < current_strike_price_at_expiry
        # Valor intrínseco = current_strike_price_at_expiry - CallStrike
        # Para Puts: Pérdida si Strike > current_strike_price_at_expiry
        # Valor intrínseco = PutStrike - current_strike_price_at_expiry

        # Filtrar por tipo y calcular el valor nocional de las opciones que expirarían OTM
        # O más bien, el valor total de las opciones que *no* se ejercen (o se ejercen con pérdida para el comprador si consideramos la prima pagada)
        # El concepto clásico de Max Pain es el strike donde el valor total en dólares de las opciones que expiran sin valor es máximo
        # O, alternativamente, donde los vendedores de opciones (market makers) tienen la máxima ganancia.
        # Esto significa que los compradores pierden la prima pagada.

        # Simplificación: Suma del Open Interest de las opciones que expiran OTM, multiplicado por su prima (MidPrice)
        # No, es el valor nocional de las opciones que expirarían con valor si el precio se mueve.
        # Max Pain es el strike donde el valor total en dólares de las opciones que vencen es el mínimo.

        # Para cada strike, calculamos el valor total de las opciones si el subyacente cierra en ESE strike.
        # Los compradores de calls pierden si K > S. Los compradores de puts pierden si K < S.
        # (K = Strike de la opción, S = Precio de ejercicio supuesto = current_strike_price_at_expiry)

        # Valor total de las opciones en circulación si el precio de ejercicio es 'current_strike_price_at_expiry'
        cash_value_at_strike = 0

        # Calls
        calls = df_griegas[df_griegas['Type'] == 'call']
        # Valor intrínseco de las calls = max(0, S - K) * OI
        cash_value_at_strike += (np.maximum(0, current_strike_price_at_expiry - calls['Strike']) * calls['OpenInterest']).sum()

        # Puts
        puts = df_griegas[df_griegas['Type'] == 'put']
        # Valor intrínseco de las puts = max(0, K - S) * OI
        cash_value_at_strike += (np.maximum(0, puts['Strike'] - current_strike_price_at_expiry) * puts['OpenInterest']).sum()

        max_pain_data.append({'StrikeAtExpiry': current_strike_price_at_expiry, 'TotalCashValue': cash_value_at_strike * 100}) # Multiplicador 100

    if not max_pain_data:
        return None

    df_max_pain = pd.DataFrame(max_pain_data)
    # El Max Pain strike es aquel que minimiza el valor total en efectivo de todas las opciones en circulación
    max_pain_strike = df_max_pain.loc[df_max_pain['TotalCashValue'].idxmin()]['StrikeAtExpiry']

    return max_pain_strike


def calculate_exposure(df_griegas, greek_column, exposure_name):
    """Calcula la exposición para una griega dada (Gamma, Vega, Theta)."""
    if df_griegas is None or df_griegas.empty or greek_column not in df_griegas.columns or 'OpenInterest' not in df_griegas.columns:
        return pd.DataFrame()

    # La exposición a Gamma (GEX) a veces se multiplica por el precio del subyacente y 0.01
    # para obtener el cambio en delta $ por un movimiento del 1% del subyacente.
    # Aquí calculamos la exposición en términos de "acciones equivalentes" o "valor nocional por punto de la griega".
    # GEX = Gamma * OI * 100 (acciones)
    # Vega Exposure = Vega * OI * 100 ($ por 1% cambio en IV)
    # Theta Exposure = Theta * OI * 100 ($ por día)

    df_griegas[exposure_name] = df_griegas[greek_column] * df_griegas['OpenInterest'] * 100

    # Sumar la exposición por strike (considerando calls positivas y puts negativas para Gamma si es Delta Hedging)
    # Para GEX, Gamma de calls es positiva, Gamma de puts también es positiva (ambas aumentan convexidad)
    # Para exposición direccional (Delta), Delta de Calls es +, Delta de Puts es -.
    # Para Theta y Vega, usualmente se suman sus valores absolutos o se miran por separado.
    # Aquí sumaremos directamente la exposición calculada.

    exposure_strike = df_griegas.groupby('Strike')[exposure_name].sum().reset_index()
    return exposure_strike

def calculate_gex(df_griegas):
    """Calcula la Exposición a Gamma (GEX)."""
    # Gamma es positiva para calls y puts.
    # GEX = (Gamma_call * OI_call - Gamma_put * OI_put * UnderlyingPrice^2 * 0.01)
    # O más comúnmente: GEX_strike = sum(Gamma_i * OI_i * 100) for calls and puts at strike_i
    # Y luego se puede considerar el impacto en el hedging de los market makers.
    # Si MM es short gamma, compra cuando sube, vende cuando baja (acelera).
    # Si MM es long gamma, vende cuando sube, compra cuando baja (estabiliza).
    # El GEX que nos interesa es el de los dealers. Asumimos que los dealers son net short calls y net short puts.
    # Entonces, GEX = - sum(Gamma_call * OI_call * 100) - sum(Gamma_put * OI_put * 100)
    # Pero la convención más común es GEX = sum(Gamma * OI * 100 * Multiplicador)
    # donde Gamma de calls es + y Gamma de puts es + (para el dueño de la opción).
    # El GEX que afecta al mercado es el GEX de los market makers.
    # Si OI representa posiciones de clientes, entonces Market Makers tienen la posición opuesta.
    # GEX (Dealer) = Sum(-Gamma_call * OI_call * 100) + Sum(-Gamma_put * OI_put * 100)
    # Esto es: GEX = - Sum(Gamma_option * OI_option * 100) (donde Gamma_option es siempre positivo)
    # O, si se considera Gamma como la del dealer: Gamma_call_dealer = -Gamma_call_holder

    # Vamos a calcular GEX "total" primero, que es la suma de todas las gammas de las opciones en circulación.
    # Esta es la "gamma del mercado".
    # Gamma_total = sum(Gamma * OI * 100)
    if df_griegas is None or df_griegas.empty or 'Gamma' not in df_griegas.columns or 'OpenInterest' not in df_griegas.columns:
        return pd.DataFrame(), None

    # Gamma de Calls y Puts son ambas positivas para el comprador.
    # GEX es la sensibilidad del Delta total del mercado a un movimiento del subyacente.
    # GEX = Gamma * OpenInterest * 100 (en acciones por punto de subyacente)
    # Para obtenerlo en $ por un cambio de 1 punto del subyacente: GEX * UnderlyingPrice
    # Para obtenerlo en $ por un cambio de 1% del subyacente: GEX * UnderlyingPrice * UnderlyingPrice * 0.01
    # Por ahora, calcularemos GEX en "acciones equivalentes".

    df_griegas['GEX_ind'] = df_griegas['Gamma'] * df_griegas['OpenInterest'] * 100
    # Para el GEX que influye en la estabilidad (dealer GEX), se toma negativo si el dealer es short gamma.
    # Asumimos que el OI representa las posiciones de los clientes, y los dealers son la contraparte.
    # Así que el GEX del dealer es el negativo del GEX del cliente.
    # GEX_dealer_per_contract = -Gamma (ya que gamma de la opción es positiva)
    # GEX_dealer_total = sum(-Gamma_i * OI_i * 100)
    df_griegas['DealerGEX'] = -df_griegas['Gamma'] * df_griegas['OpenInterest'] * 100 # Multiplicador 100

    gex_per_strike = df_griegas.groupby('Strike')['DealerGEX'].sum().reset_index()

    # Gamma Flip Point: donde el GEX acumulado o el GEX neto cruza cero.
    # O más simple, el strike donde el GEX cambia de signo de forma más significativa,
    # o donde el GEX total (suma de todos los strikes) es cero.
    # Aquí, buscaremos el punto donde la suma acumulada de DealerGEX (ordenada por strike) cruza cero.

    gex_per_strike_sorted = gex_per_strike.sort_values(by='Strike')
    gex_per_strike_sorted['CumulativeDealerGEX'] = gex_per_strike_sorted['DealerGEX'].cumsum()

    # Encontrar el flip point:
    # El nivel donde la exposición gamma neta (DealerGEX) cambia de signo.
    # O el strike más cercano a donde CumulativeDealerGEX es cero.
    # O el strike donde DealerGEX está más cerca de cero (si no cruza).

    # Un enfoque común es el nivel de strike donde el GEX total (suma de todos los strikes)
    # cambiaría de signo si el subyacente se moviera.
    # O el nivel donde el GEX del dealer es cero.
    # Para el Gamma Flip Point, a menudo se busca el strike donde el GEX *total* (no acumulado) de los dealers cruza cero.
    # O, si el GEX es mayormente de un signo, el punto donde es más débil.

    # SPlotnik define el flip como el strike donde el GEX total (no acumulado) es 0.
    # Si no hay un cruce exacto, puede ser el strike donde el GEX está más cercano a 0.
    # O el strike donde el GEX acumulado cambia de signo.

    gamma_flip_point = None
    # Intentemos encontrar un cruce de cero en DealerGEX por strike
    above_zero = gex_per_strike_sorted[gex_per_strike_sorted['DealerGEX'] > 0]
    below_zero = gex_per_strike_sorted[gex_per_strike_sorted['DealerGEX'] < 0]

    if not above_zero.empty and not below_zero.empty:
        # Si hay GEX positivo y negativo, el flip está entre el strike más alto con GEX negativo
        # y el strike más bajo con GEX positivo (o viceversa).
        # O el strike donde DealerGEX está más cerca de cero.
        closest_to_zero_strike = gex_per_strike_sorted.iloc[(gex_per_strike_sorted['DealerGEX']).abs().argsort()[:1]]
        if not closest_to_zero_strike.empty:
            gamma_flip_point = closest_to_zero_strike['Strike'].iloc[0]

    # Si todos los GEX son del mismo signo, el "flip" es menos claro.
    # Podría ser el strike con el GEX más cercano a cero.
    if gamma_flip_point is None and not gex_per_strike_sorted.empty:
        gamma_flip_point = gex_per_strike_sorted.loc[gex_per_strike_sorted['DealerGEX'].abs().idxmin()]['Strike']


    return gex_per_strike_sorted[['Strike', 'DealerGEX', 'CumulativeDealerGEX']], gamma_flip_point


def calculate_vega_exposure(df_griegas):
    """Calcula la Exposición a Vega."""
    # Vega es positiva para calls y puts (para el comprador).
    # Exposición a Vega = Vega * OI * 100 ($ por cambio de 1 punto porcentual en IV)
    # Si los dealers son short vega, entonces la exposición del dealer es -Vega.
    df_griegas['DealerVegaExposure'] = -df_griegas['Vega'] * df_griegas['OpenInterest'] * 100
    vega_exposure_strike = df_griegas.groupby('Strike')['DealerVegaExposure'].sum().reset_index()
    return vega_exposure_strike

def calculate_theta_exposure(df_griegas):
    """Calcula la Exposición a Theta."""
    # Theta es negativa para calls y puts (para el comprador, el tiempo erosiona el valor).
    # Exposición a Theta (para el comprador) = Theta * OI * 100 ($ por día que pasa)
    # Si los dealers son short opciones (long theta), entonces la exposición del dealer es -Theta (positivo).
    df_griegas['DealerThetaExposure'] = -df_griegas['Theta'] * df_griegas['OpenInterest'] * 100
    theta_exposure_strike = df_griegas.groupby('Strike')['DealerThetaExposure'].sum().reset_index()
    return theta_exposure_strike


if __name__ == '__main__':
    # Prueba de carga de datos
    df_griegas = load_and_preprocess_griegas()
    if df_griegas is not None:
        print("Griegas.csv cargado y preprocesado:")
        # print(df_griegas.head().to_markdown(index=False))
        # print("\nTipos de datos de Griegas.csv procesado:")
        # print(df_griegas.dtypes)

        print("\n--- Calculando Métricas ---")

        pc_ratios_strike = calculate_put_call_ratio(df_griegas, group_by_strike=True)
        print("\nPut/Call Ratios por Strike:")
        print(pc_ratios_strike.head().to_markdown(index=False))

        pc_ratios_total = calculate_put_call_ratio(df_griegas, group_by_strike=False)
        print("\nPut/Call Ratios Total:")
        print(pc_ratios_total.to_markdown(index=False))

        money_at_risk = calculate_money_at_risk(df_griegas)
        print("\nDinero en Riesgo por Strike:")
        print(money_at_risk.head().to_markdown(index=False))

        # Asegurarse de que no haya NaNs en columnas críticas para Max Pain
        # df_griegas_max_pain = df_griegas.dropna(subset=['Strike', 'Type', 'OpenInterest'])
        max_pain_strike = calculate_max_pain(df_griegas.dropna(subset=['Strike', 'Type', 'OpenInterest']))
        print(f"\nMax Pain Strike: {max_pain_strike}")

        gex_exposure, gamma_flip_point = calculate_gex(df_griegas.dropna(subset=['Strike', 'Gamma', 'OpenInterest']))
        print("\nExposición a Gamma (Dealer GEX) por Strike:")
        print(gex_exposure.head().to_markdown(index=False))
        print(f"Gamma Flip Point: {gamma_flip_point}")

        vega_exposure = calculate_vega_exposure(df_griegas.dropna(subset=['Strike', 'Vega', 'OpenInterest']))
        print("\nExposición a Vega (Dealer) por Strike:")
        print(vega_exposure.head().to_markdown(index=False))

        theta_exposure = calculate_theta_exposure(df_griegas.dropna(subset=['Strike', 'Theta', 'OpenInterest']))
        print("\nExposición a Theta (Dealer) por Strike:")
        print(theta_exposure.head().to_markdown(index=False))


    df_inusual = load_and_preprocess_inusual()
    if df_inusual is not None:
        print("\nInusual.csv cargado y preprocesado:")
        # print(df_inusual.head().to_markdown(index=False))
        # print("\nTipos de datos de Inusual.csv procesado:")
        # print(df_inusual.dtypes)

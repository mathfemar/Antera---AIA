import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import os
import requests
import time
import plotly.graph_objects as go
import plotly.express as px

# Função auxiliar para formatar números no padrão brasileiro (ex.: 1.800,00)
def format_brazil(value):
    formatted = f"{value:,.2f}"
    return formatted.replace(',', 'X').replace('.', ',').replace('X', '.')

# Função callback que atualiza o "Múltiplo" na tabela global a partir do number_input
def update_multiplo():
    comp = st.session_state["select_company"]
    new_val = st.session_state[f"num_{comp}"]
    st.session_state.edited_df.loc[st.session_state.edited_df["Empresa"] == comp, "Múltiplo"] = new_val

# Função callback que atualiza o "Múltiplo" na tabela global a partir do slider, com atraso de 1 segundo
def update_multiplo_slider():
    time.sleep(1)
    comp = st.session_state["select_company"]
    new_val = st.session_state[f"slider_{comp}"]
    st.session_state.edited_df.loc[st.session_state.edited_df["Empresa"] == comp, "Múltiplo"] = new_val

# ---------------------------------------------------------------
# Configurações e Funções Auxiliares
# ---------------------------------------------------------------
DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
DIRETORIO_DADOS = os.path.join(DIRETORIO_ATUAL, 'data')

@st.cache_data
def carregar_dados():
    try:
        caminho_fair_value = os.path.join(DIRETORIO_DADOS, 'fair_value.xlsx')
        caminho_investimentos = os.path.join(DIRETORIO_DADOS, 'investimentos.xlsx')
        # Ler fair_value.xlsx
        fair_value = pd.read_excel(caminho_fair_value)
        # Ler investimentos.xlsx; se a coluna "Múltiplo" não existir, cria com valor padrão 1.0
        investimentos = pd.read_excel(caminho_investimentos)
        if 'Múltiplo' not in investimentos.columns:
            investimentos['Múltiplo'] = 1.0
        return fair_value, investimentos
    except FileNotFoundError as e:
        st.error(f"❌ Erro ao carregar os arquivos: {e}")
        return None, None
    except Exception as e:
        st.error(f"❌ Erro inesperado ao carregar os arquivos: {e}")
        return None, None

@st.cache_data
def obter_ipca():
    try:
        url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json"
        response = requests.get(url)
        if response.status_code == 200:
            if not response.text:
                st.error("A API do BCB retornou resposta vazia. Usando valor fixo de IPCA.")
                return None
            try:
                json_data = response.json()
            except ValueError as ve:
                st.error(f"Erro ao decodificar JSON da API do BCB: {ve}. Usando valor fixo de IPCA.")
                return None
            if not json_data:
                st.error("A API do BCB não retornou dados. Usando valor fixo de IPCA.")
                return None
            dados = pd.DataFrame(json_data)
            if 'data' not in dados.columns or 'valor' not in dados.columns:
                st.error("Resposta da API não contém os dados esperados. Usando valor fixo de IPCA.")
                return None
            dados['data'] = pd.to_datetime(dados['data'], format='%d/%m/%Y')
            dados['valor'] = pd.to_numeric(dados['valor'], errors='coerce')
            dados.dropna(subset=['valor'], inplace=True)
            dados.set_index('data', inplace=True)
            dados['variacao_decimal'] = dados['valor'] / 100
            return dados
        else:
            st.error("Erro ao acessar API do BCB. Status code: " + str(response.status_code))
            return None
    except Exception as e:
        st.error(f"Erro ao obter IPCA: {e}. Usando valor fixo de IPCA.")
        return None

def calcular_ipca_acumulado(data_inicial):
    df_ipca = obter_ipca()
    if df_ipca is None:
        return 0.045  # Valor fixo se a API falhar
    data_inicial = pd.to_datetime(data_inicial)
    mask = (df_ipca.index >= data_inicial)
    ipca_periodo = df_ipca[mask]
    ipca_acumulado = np.prod(1 + ipca_periodo['variacao_decimal']) - 1
    return ipca_acumulado

def corrigir_ipca(valor, data_investimento, adicional=0.0):
    data_investimento = pd.to_datetime(data_investimento)
    ipca_acum = calcular_ipca_acumulado(data_investimento)
    anos = (pd.Timestamp.now() - data_investimento).days / 365.25
    valor_corrigido_ipca = valor * (1 + ipca_acum)
    valor_final = valor_corrigido_ipca * (1 + adicional/100) ** anos
    return valor_final

# ---------------------------------------------------------------
# Configurações da Página
# ---------------------------------------------------------------
st.set_page_config(page_title="Primatech Investment Analyzer", layout="wide")
st.title("📊 Primatech Investment Analyzer")

# Slider para Hurdle e IPCA + X%
hurdle = st.slider("Taxa de Correção (IPCA + %)", 0.0, 15.0, 9.0, 0.5)

# ---------------------------------------------------------------
# Carregamento dos Dados
# ---------------------------------------------------------------
fair_value, investimentos = carregar_dados()

if fair_value is not None and investimentos is not None:
    # Cria o DataFrame a partir da planilha (usando a coluna "Múltiplo")
    df_empresas = investimentos[[ 
        'Múltiplo',
        'Empresa',
        'Valor Investido até a presente data (R$ mil)',
        'Participação do Fundo (%)',
        'Data do Primeiro Investimento'
    ]].copy()
    df_empresas.rename(columns={'Valor Investido até a presente data (R$ mil)': 'Valor Investido'}, inplace=True)
    
    # Se ainda não estiver em session_state, inicializa a tabela editável
    if 'edited_df' not in st.session_state:
        st.session_state.edited_df = df_empresas.copy()
    
    # -----------------------------------------------------------
    # COLUNA 1: Tabela (sem scroll) + Configuração de Múltiplo
    # -----------------------------------------------------------
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Empresas do Portfólio")
        # Cria duas colunas lado a lado: a tabela e o configurador
        col_table, col_placeholder = st.columns([1, 1], gap="small")
        
        with col_table:
            edited_df = st.data_editor(
                st.session_state.edited_df,
                column_config={
                    "Múltiplo": st.column_config.NumberColumn("Múltiplo", format="%.2fx", min_value=0.0, max_value=100.0, width=80),
                    "Empresa": st.column_config.TextColumn("Empresa", width=120),
                    "Valor Investido": st.column_config.NumberColumn("Valor Investido", format="%.2f"),
                    "Participação do Fundo (%)": st.column_config.NumberColumn("Participação do Fundo (%)", format="%.2f"),
                    "Data do Primeiro Investimento": st.column_config.TextColumn("Data do Primeiro Investimento")
                },
                use_container_width=True,
                key="table_edit"
            )
            st.session_state.edited_df = edited_df
        
        with col_placeholder:
            st.markdown("## Configurar Múltiplo")
            company_selected = st.selectbox(
                "Selecione a empresa para alterar o múltiplo",
                options=edited_df["Empresa"].unique(),
                key="select_company"
            )
            current_value = float(edited_df.loc[edited_df["Empresa"] == company_selected, "Múltiplo"].iloc[0])
            new_mult = st.number_input(
                f"Múltiplo para {company_selected}",
                min_value=0.0,
                max_value=100.0,
                value=current_value,
                step=0.1,
                key=f"num_{company_selected}",
                format="%.1f",
                on_change=update_multiplo
            )
            slider_val = st.slider(
                f"Ajuste (Slider) para {company_selected}",
                min_value=0.0,
                max_value=50.0,
                value=current_value,
                step=1.0,
                key=f"slider_{company_selected}",
                format="%.1f",
                on_change=update_multiplo_slider
            )
        
        st.markdown("---")
        st.subheader("📈 Crescimento Necessário por Empresa (IPCA+6%)")
        col_table2, col_graph = st.columns([1, 1])
        # Filtra investimentos com Múltiplo > 0
        active_investments = st.session_state.edited_df[st.session_state.edited_df['Múltiplo'] > 0].copy()
        analise_crescimento = pd.DataFrame()
        valor_total_carteira = active_investments['Valor Investido'].sum()
        
        for _, row in active_investments.iterrows():
            valor_investido = row['Valor Investido']
            valor_necessario = corrigir_ipca(valor_investido, row['Data do Primeiro Investimento'], adicional=6.0)
            fair_val_match = fair_value.loc[fair_value['Empresa'].str.upper() == row['Empresa'].strip().upper()]
            if not fair_val_match.empty:
                fair_val_val = fair_val_match.iloc[0]['Valor Primatec (R$ mil)']
            else:
                fair_val_val = np.nan
            uplift_percent = ((valor_necessario - fair_val_val) / fair_val_val * 100) if fair_val_val and fair_val_val != 0 else np.nan
            peso_carteira = (valor_investido / valor_total_carteira * 100) if valor_total_carteira != 0 else 0
            multiplicador = row['Múltiplo']
            
            analise_crescimento = pd.concat([analise_crescimento, pd.DataFrame({
                'Empresa': [row['Empresa']],
                'Valor Investido': [valor_investido],
                'Fair Value': [fair_val_val],
                'IPCA+6%: Valor': [valor_necessario],
                'Crescimento Necessário (%)': [uplift_percent],
                'Peso na Carteira (%)': [peso_carteira],
                'Participação do Fundo (%)': [row['Participação do Fundo (%)']],
                'Múltiplo': [multiplicador]
            })])
        
        with col_table2:
            st.markdown("**Tabela de Crescimento**")
            analise_crescimento = analise_crescimento.round(2)
            st.dataframe(analise_crescimento.set_index('Empresa'))
        
        with col_graph:
            st.markdown("**Análise Gráfica - Uplift Necessário**")
            active_companies = active_investments["Empresa"].tolist()
            if not active_companies:
                st.error("Nenhuma empresa ativa disponível para análise gráfica.")
            else:
                empresa_sel = st.selectbox("Selecione uma empresa", active_companies, key="graph_select")
                filtered = analise_crescimento[analise_crescimento['Empresa'] == empresa_sel]
                if filtered.empty:
                    st.error("Nenhuma empresa encontrada para análise gráfica.")
                else:
                    linha = filtered.iloc[0]
                    investido = linha['Valor Investido']
                    fair_val = linha['Fair Value']
                    necessario = linha['IPCA+6%: Valor']
                    participacao = linha['Participação do Fundo (%)']
                    multiplo = linha['Múltiplo']
                    
                    fair_val_adjusted = fair_val * (participacao / 100)
                    sale = investido * multiplo
                    x_positions = [0, 1, 2, 3]
                    bar_colors = ['#2196F3', '#FF9800', '#4CAF50', '#9C27B0']
                    tick_text = [
                        f"Investido: R$ {format_brazil(investido)}k",
                        f"Fair Value (ajustado): R$ {format_brazil(fair_val_adjusted)}k",
                        f"IPCA+6%: R$ {format_brazil(necessario)}k",
                        f"Sale: R$ {format_brazil(sale)}k"
                    ]
                    
                    if fair_val_adjusted != 0:
                        uplift_adjusted = ((necessario - fair_val_adjusted) / fair_val_adjusted) * 100
                    else:
                        uplift_adjusted = np.nan
                    
                    if pd.notna(uplift_adjusted) and uplift_adjusted >= 0:
                        title_text = f"Uplift de +{uplift_adjusted:.2f}% em relação ao benchmark"
                    elif pd.notna(uplift_adjusted):
                        over = (fair_val_adjusted / necessario) * 100 if necessario != 0 else 0
                        title_text = f"Overperformance de {over:.2f}% em relação ao benchmark"
                    else:
                        title_text = "Sem dados suficientes"
                    
                    fig_uplift = go.Figure([
                        go.Bar(x=x_positions, y=[investido, fair_val_adjusted, necessario, sale], marker_color=bar_colors)
                    ])
                    fig_uplift.update_layout(
                        title=title_text,
                        yaxis_title='Valores (R$ mil)',
                        xaxis=dict(tickmode='array', tickvals=x_positions, ticktext=tick_text),
                        template='plotly_dark'
                    )
                    st.plotly_chart(fig_uplift, use_container_width=True)
        
        # -----------------------------------------------------------
        # NOVA SEÇÃO: Análise Hurdle no Tempo (Gráfico trimestral) - SOMA CUMULATIVA
        # -----------------------------------------------------------
        st.subheader("Análise Hurdle no Tempo")
        try:
            caminho_parcelas = os.path.join(DIRETORIO_DADOS, 'data_investimentos.xlsx')
            df_parcelas = pd.read_excel(caminho_parcelas)
            df_parcelas["Data Investimento"] = pd.to_datetime(df_parcelas["Data Investimento"], format="%d/%m/%Y", errors="coerce")
            min_date = df_parcelas["Data Investimento"].min()
        except Exception as e:
            st.error(f"Erro ao carregar data_investimentos.xlsx: {e}")
            df_parcelas = pd.DataFrame(columns=["Empresa","Setor","Data Investimento","Valor Investido"])
            min_date = datetime(1900, 1, 1)

        current_month_first = pd.to_datetime(datetime.now().strftime("%Y-%m-01"))

        # Se não houver dados, exibimos aviso e não plotamos.
        if df_parcelas.empty:
            st.warning("Não há dados em data_investimentos.xlsx para exibir o gráfico cumulativo de investimentos.")
        else:
            # 1) Converter "Valor Investido" para float
            df_parcelas["Valor Investido"] = (
                df_parcelas["Valor Investido"]
                .astype(str)
                .str.replace("R\\$","", regex=True)
                .str.replace("\\.","", regex=True)
                .str.replace(",",".", regex=True)
            )
            df_parcelas["Valor Investido"] = pd.to_numeric(df_parcelas["Valor Investido"], errors="coerce")

            # 2) Agrupar por data (dia) e somar os aportes nesse dia
            df_agrupado = df_parcelas.groupby("Data Investimento", as_index=False)["Valor Investido"].sum()
            # 3) Ordenar por data e fazer soma cumulativa
            df_agrupado.sort_values("Data Investimento", inplace=True)
            df_agrupado["SomaCumulativa"] = df_agrupado["Valor Investido"].cumsum()

            # 4) Criar um índice diário (ou trimestral?), aqui vamos usar diário para termos a soma exata.
            daily_index = pd.date_range(start=min_date, end=current_month_first, freq='D')

            # 5) Reindexar para ter um valor cumulativo em cada dia (fill forward)
            df_agrupado.set_index("Data Investimento", inplace=True)
            df_agrupado = df_agrupado.reindex(daily_index, method="ffill").fillna(0)
            df_agrupado.index.name = "Data Investimento"

            # 6) Agora temos soma cumulativa dia a dia. Precisamos plotar trimestral no eixo X (dtick="M3").
            #    Faremos um Scatter com x = daily_index e y = df_agrupado["SomaCumulativa"].

            fig_temp = go.Figure()
            fig_temp.add_trace(
                go.Scatter(
                    x=daily_index,
                    y=df_agrupado["SomaCumulativa"],
                    mode='lines+markers',
                    line=dict(color='cyan'),
                    marker=dict(color='cyan'),
                    name='Cumulativo'
                )
            )
            fig_temp.update_layout(
                title="Período de Investimentos (Trimestral) - Soma Cumulativa",
                xaxis_title="Data",
                xaxis=dict(
                    type='date',
                    range=[min_date, current_month_first],
                    dtick="M3",          # 1 tick a cada 3 meses
                    tickformat="%b\n%Y", # Mês e Ano em linhas separadas
                    tickfont=dict(color='cyan')
                ),
                yaxis=dict(
                    visible=False  # oculta os valores no eixo Y
                ),
                template='plotly_dark'
            )
            st.plotly_chart(fig_temp, use_container_width=True)
        
        # -----------------------------------------------------------
        # CONTINUA A SEÇÃO "Análise Hurdle no Tempo" (cálculos existentes)
        # -----------------------------------------------------------
        investimentos_ativos = investimentos[investimentos['Empresa'].isin(st.session_state.edited_df['Empresa'].tolist())].copy()
        investimentos_ativos.rename(columns={'Valor Investido até a presente data (R$ mil)': 'Valor Investido'}, inplace=True)
        
        valor_total_investido = investimentos['Valor Investido até a presente data (R$ mil)'].sum()
        valor_total_ativo = investimentos_ativos['Valor Investido'].sum()
        valor_hurdle = valor_total_ativo * (1 + (hurdle / 100))
        total_investido = valor_total_investido / 1000  # em milhões
        total_corrigido_ipca_6 = investimentos_ativos.apply(
            lambda row: corrigir_ipca(
                row['Valor Investido'],
                row['Data do Primeiro Investimento'],
                adicional=9.0
            ),
            axis=1
        ).sum() / 1000
        variacao_percentual = ((total_corrigido_ipca_6 - total_investido) / total_investido) * 100
        total_ipca = investimentos_ativos.apply(
            lambda row: corrigir_ipca(
                row['Valor Investido'],
                row['Data do Primeiro Investimento']
            ),
            axis=1
        ).sum() / 1000
        total_ipca_6 = investimentos_ativos.apply(
            lambda row: corrigir_ipca(
                row['Valor Investido'],
                row['Data do Primeiro Investimento'],
                adicional=6.0
            ),
            axis=1
        ).sum() / 1000
        total_ipca_hurdle = investimentos_ativos.apply(
            lambda row: corrigir_ipca(
                row['Valor Investido'],
                row['Data do Primeiro Investimento'],
                adicional=hurdle
            ),
            axis=1
        ).sum() / 1000

    # -----------------------------------------------------------
    # COLUNA 2: Resumo da Carteira e Gráficos (mesma lógica)
    # -----------------------------------------------------------
    with col2:
        st.subheader("📊 Gráficos de Investimentos")
        with st.expander("Participação do Fundo por Empresa"):
            df_ativos = st.session_state.edited_df[st.session_state.edited_df['Múltiplo'] > 0]
            fig_port = go.Figure(data=[go.Bar(
                x=df_ativos['Empresa'],
                y=df_ativos['Participação do Fundo (%)'],
                marker_color='#4CAF50'
            )])
            fig_port.update_layout(
                xaxis_title="Empresa",
                yaxis_title="Participação do Fundo (%)",
                template='plotly_dark'
            )
            st.plotly_chart(fig_port, use_container_width=True)
        
        def plot_comparativo(valores_corrigidos, cor_corrigida, label_corrigido):
            empresas = investimentos_ativos['Empresa']
            valores_investidos = investimentos_ativos['Valor Investido']
            fig = go.Figure(data=[
                go.Bar(
                    x=empresas,
                    y=valores_investidos,
                    name='Valor Investido',
                    marker_color='#2196F3'
                ),
                go.Bar(
                    x=empresas,
                    y=valores_corrigidos,
                    name=label_corrigido,
                    marker_color=cor_corrigida
                )
            ])
            fig.update_layout(
                yaxis_title='Valores (R$ mil)',
                xaxis_tickangle=-90,
                barmode='group',
                template='plotly_dark'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with st.expander(f"Comparativo: Valor Aprovado vs Valor Investido (Total Investido: R$ {(investimentos_ativos['Valor Investido'].sum()/1000):.2f} MM)"):
            empresas = investimentos_ativos['Empresa']
            valores_aprovados = investimentos_ativos['Valor Aprovado em CI (R$ mil)']
            valores_investidos = investimentos_ativos['Valor Investido']
            fig = go.Figure(data=[
                go.Bar(x=empresas, y=valores_aprovados, name='Valor Aprovado', marker_color='#4CAF50'),
                go.Bar(x=empresas, y=valores_investidos, name='Valor Investido', marker_color='#2196F3')
            ])
            fig.update_layout(
                yaxis_title='Valores (R$ mil)',
                xaxis_tickangle=-90,
                barmode='group',
                template='plotly_dark'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with st.expander(f"Montante Total Investido Corrigido pelo IPCA (R$ {total_ipca:.2f} MM)"):
            investimentos_ativos['Valor Corrigido IPCA'] = investimentos_ativos.apply(
                lambda row: corrigir_ipca(
                    row['Valor Investido'],
                    row['Data do Primeiro Investimento']
                ),
                axis=1
            )
            plot_comparativo(
                investimentos_ativos['Valor Corrigido IPCA'],
                '#FF5722',
                'Valor Corrigido'
            )
        
        with st.expander(f"Montante Total Investido Corrigido pelo IPCA+6% (R$ {total_ipca_6:.2f} MM)"):
            investimentos_ativos['Valor Corrigido IPCA+6%'] = investimentos_ativos.apply(
                lambda row: corrigir_ipca(
                    row['Valor Investido'],
                    row['Data do Primeiro Investimento'],
                    adicional=6.0
                ),
                axis=1
            ).round(2)
            plot_comparativo(
                investimentos_ativos['Valor Corrigido IPCA+6%'],
                '#9C27B0',
                'Valor Corrigido'
            )
        
        with st.expander(f"Montante Total Investido Corrigido pelo IPCA+{hurdle}% (R$ {total_ipca_hurdle:.2f} MM)"):
            investimentos_ativos['Valor Corrigido IPCA+Hurdle'] = investimentos_ativos.apply(
                lambda row: corrigir_ipca(
                    row['Valor Investido'],
                    row['Data do Primeiro Investimento'],
                    adicional=hurdle
                ),
                axis=1
            ).round(2)
            plot_comparativo(
                investimentos_ativos['Valor Corrigido IPCA+Hurdle'],
                '#3F51B5',
                'Valor Corrigido'
            )
    
    st.subheader("📈 Resultados da Carteira")
    empresas_ativas_graficos = st.session_state.edited_df['Empresa'].tolist()
    if empresas_ativas_graficos:
        investimentos_ativos = investimentos[investimentos['Empresa'].isin(empresas_ativas_graficos)].copy()
        investimentos_ativos.rename(columns={'Valor Investido até a presente data (R$ mil)': 'Valor Investido'}, inplace=True)
        valor_total_ativo = investimentos_ativos['Valor Investido'].sum()
        valor_hurdle = valor_total_ativo * (1 + (hurdle / 100))
        crescimento_necessario = ((valor_hurdle - valor_total_ativo) / valor_total_ativo) * 100
        st.success(f"As empresas precisam crescer {crescimento_necessario:.2f}% para atingir o valor da Hurdle.")
    else:
        st.error("❗ Nenhuma empresa ativa (Múltiplo definido como 0).")

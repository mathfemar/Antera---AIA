import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import os
import requests
import time
import plotly.graph_objects as go
import plotly.express as px

# Função para formatar número no padrão BR
def format_brazil(value):
    formatted = f"{value:,.2f}"
    return formatted.replace(',', 'X').replace('.', ',').replace('X', '.')

def update_multiplo():
    comp = st.session_state["select_company"]
    new_val = st.session_state[f"num_{comp}"]
    st.session_state.edited_df.loc[
        st.session_state.edited_df["Empresa"] == comp, "Múltiplo"
    ] = new_val

def update_multiplo_slider():
    time.sleep(1)
    comp = st.session_state["select_company"]
    new_val = st.session_state[f"slider_{comp}"]
    st.session_state.edited_df.loc[
        st.session_state.edited_df["Empresa"] == comp, "Múltiplo"
    ] = new_val

DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
DIRETORIO_DADOS = os.path.join(DIRETORIO_ATUAL, 'data')

@st.cache_data
def carregar_dados():
    try:
        caminho_fair_value = os.path.join(DIRETORIO_DADOS, 'fair_value.xlsx')
        caminho_investimentos = os.path.join(DIRETORIO_DADOS, 'investimentos.xlsx')
        fair_value = pd.read_excel(caminho_fair_value)
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
                st.error(f"Erro ao decodificar JSON do BCB: {ve}. Usando valor fixo de IPCA.")
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
        # Se der erro, usaremos um valor fixo de ~4,5%
        return 0.045
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
    valor_final = valor_corrigido_ipca * ((1 + adicional/100) ** anos)
    return valor_final

# ---------------------------------------------------------------
# CONFIGURAÇÕES E INÍCIO DO CÓDIGO
# ---------------------------------------------------------------
st.set_page_config(page_title="Primatech Investment Analyzer", layout="wide")

col_title, col_hurdle_val = st.columns([3, 1])
with col_title:
    st.title("📊 Primatech Investment Analyzer")
with col_hurdle_val:
    hurdle_nominal = st.number_input("Hurdle (R$):", value=117000.0, step=1000.0, format="%.0f")
    st.write(f"Hurdle: R$ {format_brazil(hurdle_nominal)}")

# Slider para ajuste de taxa (IPCA + X%)
hurdle = st.slider("Taxa de Correção (IPCA + %)", 0.0, 15.0, 9.0, 0.5)

fair_value, investimentos = carregar_dados()

if fair_value is not None and investimentos is not None:
    # Tabela base
    df_empresas = investimentos[[
        'Múltiplo',
        'Empresa',
        'Valor Investido até a presente data (R$ mil)',
        'Participação do Fundo (%)',
        'Data do Primeiro Investimento'
    ]].copy()
    df_empresas.rename(columns={'Valor Investido até a presente data (R$ mil)': 'Valor Investido'}, inplace=True)
    
    # Adicionamos "Fair Value" total (da planilha fair_value.xlsx)
    if "Fair Value" not in df_empresas.columns:
        df_empresas["Fair Value"] = np.nan
    
    # Preenche Fair Value total do df_empresas
    for i, row in df_empresas.iterrows():
        emp = row["Empresa"]
        match = fair_value.loc[
            fair_value["Empresa"].str.upper() == emp.strip().upper()
        ]
        if not match.empty:
            df_empresas.at[i, "Fair Value"] = match.iloc[0]["Valor Primatec (R$ mil)"]
        else:
            df_empresas.at[i, "Fair Value"] = np.nan
    
    # Se não existir no session_state, criamos; caso exista, não sobrescrevemos
    if 'edited_df' not in st.session_state:
        st.session_state.edited_df = df_empresas.copy()
    
    # Layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Empresas do Portfólio")
        
        col_table, col_placeholder = st.columns([1, 1], gap="small")
        with col_table:
            new_cols = ["Múltiplo", "Empresa", "Valor Investido", "Fair Value", "Participação do Fundo (%)", "Data do Primeiro Investimento"]
            final_cols = [c for c in new_cols if c in st.session_state.edited_df.columns]
            st.session_state.edited_df = st.session_state.edited_df[final_cols]
            
            edited_df = st.data_editor(
                st.session_state.edited_df,
                column_config={
                    "Múltiplo": st.column_config.NumberColumn("Múltiplo", format="%.2fx", min_value=0.0, max_value=100.0, width=80),
                    "Empresa": st.column_config.TextColumn("Empresa", width=120),
                    "Valor Investido": st.column_config.NumberColumn("Valor Investido", format="%.2f"),
                    "Fair Value": st.column_config.NumberColumn("Fair Value", format="%.2f"),
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
        
        active_investments = st.session_state.edited_df[
            st.session_state.edited_df['Múltiplo'] > 0
        ].copy()
        analise_crescimento = pd.DataFrame()
        
        for _, row in active_investments.iterrows():
            valor_investido = row['Valor Investido']
            valor_necessario = corrigir_ipca(
                valor_investido,
                row['Data do Primeiro Investimento'],
                adicional=6.0
            )
            fair_value_total = row["Fair Value"]
            pct_fundo = row['Participação do Fundo (%)']
            if pd.notna(fair_value_total) and pct_fundo > 0:
                fv_part = fair_value_total * (pct_fundo / 100.0)
            else:
                fv_part = np.nan
            
            multiplicador = row['Múltiplo']
            if pd.notna(fv_part) and fv_part != 0:
                uplift_percent = ((valor_necessario - fv_part) / fv_part) * 100
            else:
                uplift_percent = np.nan
            
            sale_value = valor_investido * multiplicador
            
            analise_crescimento = pd.concat([
                analise_crescimento,
                pd.DataFrame({
                    'Empresa': [row['Empresa']],
                    'Valor Investido': [valor_investido],
                    'FV Part.': [fv_part],
                    'IPCA+6%: Valor': [valor_necessario],
                    'Crescimento Necessário (%)': [uplift_percent],
                    'Participação do Fundo (%)': [pct_fundo],
                    'Múltiplo': [multiplicador],
                    'Sale': [sale_value]
                })
            ])
        
        valor_total_fv_part = analise_crescimento["FV Part."].sum()
        if valor_total_fv_part != 0:
            analise_crescimento["Peso na Carteira (%)"] = (
                analise_crescimento["FV Part."] / valor_total_fv_part
            ) * 100
        else:
            analise_crescimento["Peso na Carteira (%)"] = 0
        
        with col_table2:
            st.markdown("**Tabela de Crescimento**")
            analise_crescimento = analise_crescimento.round(2)
            st.dataframe(analise_crescimento.set_index('Empresa'))
        
        with col_graph:
            st.markdown("**Análise Gráfica - Uplift Necessário**")
            active_companies = analise_crescimento["Empresa"].tolist()
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
                    fv_part = linha['FV Part.']
                    necessario = linha['IPCA+6%: Valor']
                    pct_fundo = linha['Participação do Fundo (%)']
                    multiplicador = linha['Múltiplo']
                    sale = linha['Sale']
                    
                    x_positions = [0, 1, 2, 3]
                    bar_colors = ['#2196F3', '#FF9800', '#4CAF50', '#9C27B0']
                    tick_text = [
                        f"Investido: R$ {format_brazil(investido)}k",
                        f"FV Part.: R$ {format_brazil(fv_part if pd.notna(fv_part) else 0)}k",
                        f"IPCA+6%: R$ {format_brazil(necessario)}k",
                        f"Sale: R$ {format_brazil(sale)}k"
                    ]
                    
                    if pd.notna(fv_part) and fv_part != 0:
                        uplift_adjusted = ((necessario - fv_part) / fv_part) * 100
                        if uplift_adjusted >= 0:
                            title_text = f"Uplift de +{uplift_adjusted:.2f}%"
                        else:
                            over = (fv_part / necessario) * 100 if necessario != 0 else 0
                            title_text = f"Overperformance de {over:.2f}%"
                    else:
                        title_text = "Sem dados suficientes"
                    
                    fig_uplift = go.Figure([
                        go.Bar(
                            x=x_positions,
                            y=[investido, fv_part if pd.notna(fv_part) else 0, necessario, sale],
                            marker_color=bar_colors
                        )
                    ])
                    fig_uplift.update_layout(
                        title=title_text,
                        yaxis_title='Valores (R$ mil)',
                        xaxis=dict(
                            tickmode='array',
                            tickvals=x_positions,
                            ticktext=tick_text
                        ),
                        template='plotly_dark'
                    )
                    st.plotly_chart(fig_uplift, use_container_width=True)
        
        # -----------------------------------------------------------
        # Análise de Aportes no Tempo (Gráfico trimestral) - SOMA Cumulativa
        # -----------------------------------------------------------
        st.subheader("Análise de Aportes no Tempo")
        try:
            caminho_parcelas = os.path.join(DIRETORIO_DADOS, 'data_investimentos.xlsx')
            df_parcelas = pd.read_excel(caminho_parcelas)
            df_parcelas["Data Investimento"] = pd.to_datetime(
                df_parcelas["Data Investimento"], 
                format="%d/%m/%Y", 
                errors="coerce"
            )
            min_date = df_parcelas["Data Investimento"].min()
        except Exception as e:
            st.error(f"Erro ao carregar data_investimentos.xlsx: {e}")
            df_parcelas = pd.DataFrame(columns=["Empresa","Setor","Data Investimento","Valor Investido"])
            min_date = datetime(1900, 1, 1)

        current_month_first = pd.to_datetime(datetime.now().strftime("%Y-%m-01"))

        if df_parcelas.empty:
            st.warning("Não há dados em data_investimentos.xlsx para exibir o gráfico cumulativo de investimentos.")
        else:
            df_parcelas["Valor Investido"] = (
                df_parcelas["Valor Investido"]
                .astype(str)
                .str.replace("R\\$","", regex=True)
                .str.replace("\\.","", regex=True)
                .str.replace(",",".", regex=True)
            )
            df_parcelas["Valor Investido"] = pd.to_numeric(df_parcelas["Valor Investido"], errors="coerce")

            df_agrupado = df_parcelas.groupby("Data Investimento", as_index=False)["Valor Investido"].sum()
            df_agrupado.sort_values("Data Investimento", inplace=True)
            df_agrupado["SomaCumulativa"] = df_agrupado["Valor Investido"].cumsum()

            daily_index = pd.date_range(start=min_date, end=current_month_first, freq='D')
            df_agrupado.set_index("Data Investimento", inplace=True)
            df_agrupado = df_agrupado.reindex(daily_index, method="ffill").fillna(0)
            df_agrupado.index.name = "Data Investimento"

            fig_temp = go.Figure()
            fig_temp.add_trace(
                go.Scatter(
                    x=daily_index,
                    y=df_agrupado["SomaCumulativa"],
                    mode='lines+markers',
                    line=dict(color='orange'),
                    marker=dict(color='orange'),
                    name='Cumulativo'
                )
            )
            fig_temp.update_layout(
                title="Período de Investimentos (Trimestral) - Soma Cumulativa",
                xaxis_title="Data",
                xaxis=dict(
                    type='date',
                    range=[min_date, current_month_first],
                    dtick="M3",
                    tickformat="%b\n%Y",
                    tickfont=dict(color='white')
                ),
                yaxis=dict(visible=False),
                template='plotly_dark'
            )
            st.plotly_chart(fig_temp, use_container_width=True)
        
        # -----------------------------------------------------------
        # Seção de Resultados da Carteira
        # -----------------------------------------------------------
        investimentos_ativos = investimentos[
            investimentos['Empresa'].isin(st.session_state.edited_df['Empresa'].tolist())
        ].copy()
        investimentos_ativos.rename(
            columns={'Valor Investido até a presente data (R$ mil)': 'Valor Investido'}, 
            inplace=True
        )
        
        valor_total_investido = investimentos['Valor Investido até a presente data (R$ mil)'].sum()
        valor_total_ativo = investimentos_ativos['Valor Investido'].sum()
        valor_hurdle = valor_total_ativo * (1 + (hurdle / 100))
        total_investido = valor_total_investido / 1000

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

        st.subheader("Resultados da Carteira")

        total_sale = analise_crescimento["Sale"].sum() if "Sale" in analise_crescimento.columns else 0.0
        
        # Invertendo a ordem e dando espaço (bargap) entre as barras
        fig_hurdle = go.Figure(data=[
            go.Bar(name='Realizado', x=['Hurdle vs Realizado'], y=[total_sale], marker_color='light blue'),
            go.Bar(name='Hurdle', x=['Hurdle vs Realizado'], y=[hurdle_nominal], marker_color='light green')
        ])
        fig_hurdle.update_layout(
            barmode='group',
            bargap= 0.4,  # <-- Ajuste do espaçamento entre as barras
            template='plotly_dark',
            title="Hurdle vs Realizado"
        )
        st.plotly_chart(fig_hurdle, use_container_width=True)

    # -----------------------------------------------------------
    # COLUNA 2: Resumo da Carteira e Gráficos
    # -----------------------------------------------------------
    with col2:
        st.subheader("📊 Gráficos de Investimentos")
        
        with st.expander("Participação do Fundo por Empresa", expanded=True):
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
        
        def plot_comparativo(valores_corrigidos, cor_corrigido, label_corrigido):
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
                    marker_color=cor_corrigido
                )
            ])
            fig.update_layout(
                yaxis_title='Valores (R$ mil)',
                xaxis_tickangle=-90,
                barmode='group',
                template='plotly_dark'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with st.expander(f"Comparativo: Valor Aprovado vs Valor Investido (Total Investido: R$ {total_investido:.2f} MM)", expanded=True):
            empresas = investimentos_ativos['Empresa']
            valores_aprovados = investimentos_ativos['Valor Aprovado em CI (R$ mil)']
            valores_investidos = investimentos_ativos['Valor Investido']
            
            fig = go.Figure(data=[
                go.Bar(
                    x=empresas,
                    y=valores_aprovados,
                    name='Valor Aprovado',
                    marker_color='#4CAF50'
                ),
                go.Bar(
                    x=empresas,
                    y=valores_investidos,
                    name='Valor Investido',
                    marker_color='#2196F3'
                )
            ])
            fig.update_layout(
                yaxis_title='Valores (R$ mil)',
                xaxis_tickangle=-90,
                barmode='group',
                template='plotly_dark'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with st.expander(f"Montante Total Investido Corrigido pelo IPCA (R$ {total_ipca:.2f} MM)", expanded=True):
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
        
        with st.expander(f"Montante Total Investido Corrigido pelo IPCA+6% (R$ {total_ipca_6:.2f} MM)", expanded=True):
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
        
        with st.expander(f"Montante Total Investido Corrigido pelo IPCA+{hurdle}% (R$ {total_ipca_hurdle:.2f} MM)", expanded=True):
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

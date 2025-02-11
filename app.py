import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import os
import requests
import plotly.graph_objects as go
import plotly.express as px

# Função auxiliar para formatar números no padrão brasileiro (ex.: 1.800,00)
def format_brazil(value):
    formatted = f"{value:,.2f}"
    return formatted.replace(',', 'X').replace('.', ',').replace('X', '.')

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
        # Ler investimentos.xlsx convertendo a coluna "Write-off" para booleano
        investimentos = pd.read_excel(
            caminho_investimentos, 
            converters={
                'Write-off': lambda x: True if str(x).strip() in ['1', 'True', 'true'] else False
            }
        )
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
        st.error(f"Erro ao obter dados do IPCA: {e}. Usando valor fixo de IPCA.")
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
hurdle = st.slider("Taxa de Correção (IPCA + %)", 0.0, 15.0, 6.0, 0.5)

# ---------------------------------------------------------------
# Carregamento dos Dados
# ---------------------------------------------------------------
fair_value, investimentos = carregar_dados()

if fair_value is not None and investimentos is not None:
    # -----------------------------------------------------------
    # COLUNA 1: Tabela (sem scroll) e Placeholder para novo componente
    # -----------------------------------------------------------
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Empresas do Portfólio")
        
        # Seleciona as colunas desejadas do arquivo de investimentos
        df_empresas = investimentos[[
            'Write-off',
            'Empresa',
            'Valor Investido até a presente data (R$ mil)',
            'Participação do Fundo (%)',
            'Data do Primeiro Investimento'
        ]].copy()
        df_empresas.rename(columns={
            'Valor Investido até a presente data (R$ mil)': 'Valor Investido'
        }, inplace=True)
        
        # Garante que a coluna "Write-off" seja booleana
        df_empresas['Write-off'] = df_empresas['Write-off'].apply(lambda x: bool(x))
        
        # Cria duas colunas internas: uma para a tabela e outra para o placeholder (tabela vazia)
        col_table, col_placeholder = st.columns([2, 2], gap="small")
        
        with col_table:
            edited_df = st.data_editor(
                df_empresas,
                column_config={
                    "Write-off": st.column_config.CheckboxColumn("Write-off", width=80),
                    "Empresa": st.column_config.TextColumn("Empresa", width=120),
                    "Valor Investido": st.column_config.NumberColumn("Valor Investido", format="%.2f"),
                    "Participação do Fundo (%)": st.column_config.NumberColumn("Participação do Fundo (%)", format="%.2f"),
                    "Data do Primeiro Investimento": st.column_config.TextColumn("Data do Primeiro Investimento")
                },
                use_container_width=True
            )
        
        with col_placeholder:
            st.markdown("**Placeholder para nova Tabela/Gráfico**")
            st.dataframe(pd.DataFrame(), height=200)
        
        # -----------------------------------------------------------
        # Crescimento Necessário por Empresa (IPCA+6%) – somente para empresas ativas
        # -----------------------------------------------------------
        st.subheader("📈 Crescimento Necessário por Empresa (IPCA+6%)")
        col_table2, col_graph = st.columns([1, 1])
        
        # Filtra apenas as empresas ativas (sem Write-off)
        active_investments = edited_df[edited_df['Write-off'] == False].copy()
        
        analise_crescimento = pd.DataFrame()
        # Recalcula o valor total investido considerando apenas empresas ativas
        valor_total_carteira = active_investments['Valor Investido'].sum()
        
        # Para cada empresa ativa, calcula os indicadores e busca o Fair Value
        for _, row in active_investments.iterrows():
            valor_investido = row['Valor Investido']
            valor_necessario = corrigir_ipca(valor_investido, row['Data do Primeiro Investimento'], adicional=6.0)
            # Busca o Fair Value da empresa no DataFrame fair_value (comparação em caixa alta)
            fair_val_match = fair_value.loc[fair_value['Empresa'].str.upper() == row['Empresa'].strip().upper()]
            if not fair_val_match.empty:
                fair_val_val = fair_val_match.iloc[0]['Valor Primatec (R$ mil)']
            else:
                fair_val_val = np.nan
            # Calcula o uplift relativo ao Fair Value
            uplift_percent = ((valor_necessario - fair_val_val) / fair_val_val * 100) if fair_val_val and fair_val_val != 0 else np.nan
            peso_carteira = (valor_investido / valor_total_carteira * 100) if valor_total_carteira != 0 else 0
            
            analise_crescimento = pd.concat([analise_crescimento, pd.DataFrame({
                'Empresa': [row['Empresa']],
                'Valor Investido': [valor_investido],
                'Fair Value': [fair_val_val],
                'IPCA+6%: Valor': [valor_necessario],
                'Crescimento Necessário (%)': [uplift_percent],
                'Peso na Carteira (%)': [peso_carteira]
            })])
        
        with col_table2:
            st.markdown("**Tabela de Crescimento**")
            analise_crescimento = analise_crescimento.round(2)
            st.dataframe(analise_crescimento.set_index('Empresa'))
        
        with col_graph:
            st.markdown("**Análise Gráfica - Uplift Necessário**")
            empresa_sel = st.selectbox(
                "Selecione uma empresa",
                analise_crescimento['Empresa']
            )
            linha = analise_crescimento[analise_crescimento['Empresa'] == empresa_sel].iloc[0]
            investido = linha['Valor Investido']
            fair_val = linha['Fair Value']
            necessario = linha['IPCA+6%: Valor']
            uplift = linha['Crescimento Necessário (%)']
            x_positions = [0, 1, 2]
            bar_colors = ['#2196F3', '#FF9800', '#4CAF50']
            tick_text = [
                f"Investido: R$ {format_brazil(investido)}k",
                f"Fair Value: R$ {format_brazil(fair_val)}k",
                f"IPCA+6%: R$ {format_brazil(necessario)}k"
            ]
            
            if uplift >= 0:
                title_text = f"Uplift de +{uplift:.2f}% em relação ao benchmark"
                arrow_dict = dict(x=x_positions[2], y=necessario,
                                  ax=x_positions[1], ay=fair_val,
                                  xref="x", yref="y",
                                  axref="x", ayref="y",
                                  arrowhead=3, arrowcolor="white",
                                  arrowwidth=3,
                                  showarrow=True)
                annotation_text = f"Uplift de +{uplift:.2f}%"
            else:
                overperf = (fair_val / necessario) * 100 if necessario != 0 else np.nan
                title_text = f"Overperformance de {overperf:.2f}% em relação ao benchmark"
                arrow_dict = dict(x=x_positions[1], y=fair_val,
                                  ax=x_positions[2], ay=necessario,
                                  xref="x", yref="y",
                                  axref="x", ayref="y",
                                  arrowhead=3, arrowcolor="white",
                                  arrowwidth=3,
                                  showarrow=True)
                annotation_text = f"Overperformance de {overperf:.2f}%"
            
            fig_uplift = go.Figure([
                go.Bar(x=x_positions, y=[investido, fair_val, necessario], marker_color=bar_colors)
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
            fig_uplift.add_annotation(**arrow_dict)
            mid_x = (x_positions[1] + x_positions[2]) / 2
            mid_y = (fair_val + necessario) / 2
            fig_uplift.add_annotation(
                x=mid_x,
                y=mid_y,
                text=annotation_text,
                showarrow=False,
                font=dict(color="white", size=14),
                bgcolor="rgba(0,0,0,0.8)",
            )
            st.plotly_chart(fig_uplift, use_container_width=True)
    
    # -----------------------------------------------------------
    # Resumo da Carteira e Gráficos (Coluna 2)
    # -----------------------------------------------------------
    valor_total_investido = investimentos['Valor Investido até a presente data (R$ mil)'].sum()
    empresas_ativas_graficos = edited_df.loc[edited_df['Write-off'] == False, 'Empresa'].tolist()
    investimentos_ativos = investimentos[investimentos['Empresa'].isin(empresas_ativas_graficos)].copy()
    
    valor_total_ativo = investimentos_ativos['Valor Investido até a presente data (R$ mil)'].sum()
    valor_hurdle = valor_total_ativo * (1 + (hurdle / 100))
    
    total_investido = valor_total_investido / 1000  # em milhões
    total_corrigido_ipca_6 = investimentos_ativos.apply(
        lambda row: corrigir_ipca(
            row['Valor Investido até a presente data (R$ mil)'],
            row['Data do Primeiro Investimento'],
            adicional=6.0
        ),
        axis=1
    ).sum() / 1000
    
    variacao_percentual = ((total_corrigido_ipca_6 - total_investido) / total_investido) * 100

    # Cálculos adicionais para os gráficos comparativos
    total_ipca = investimentos_ativos.apply(
        lambda row: corrigir_ipca(
            row['Valor Investido até a presente data (R$ mil)'],
            row['Data do Primeiro Investimento']
        ),
        axis=1
    ).sum() / 1000
    
    total_ipca_6 = investimentos_ativos.apply(
        lambda row: corrigir_ipca(
            row['Valor Investido até a presente data (R$ mil)'],
            row['Data do Primeiro Investimento'],
            adicional=6.0
        ),
        axis=1
    ).sum() / 1000
    
    total_ipca_hurdle = investimentos_ativos.apply(
        lambda row: corrigir_ipca(
            row['Valor Investido até a presente data (R$ mil)'],
            row['Data do Primeiro Investimento'],
            adicional=hurdle
        ),
        axis=1
    ).sum() / 1000
    
    with col2:
        st.subheader("📊 Gráficos de Investimentos")
        
        # Primeiro gráfico: Participação do Fundo por Empresa
        st.markdown("**Participação do Fundo por Empresa**")
        df_ativos = edited_df[edited_df['Write-off'] == False]
        fig_port = go.Figure(data=[go.Bar(
            x=df_ativos['Empresa'],
            y=df_ativos['Participação do Fundo (%)'],
            marker_color='#4CAF50'
        )])
        fig_port.update_layout(
            xaxis_title="Empresa",
            yaxis_title="Participação do Fundo (%)",
            template="plotly_dark"
        )
        st.plotly_chart(fig_port, use_container_width=True)
        
        # Função auxiliar para gráficos comparativos
        def plot_comparativo(valores_corrigidos, cor_corrigido, label_corrigido):
            empresas = investimentos_ativos['Empresa']
            valores_investidos = investimentos_ativos['Valor Investido até a presente data (R$ mil)']
            
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
        
        with st.expander(f"Comparativo: Valor Aprovado vs Valor Investido (Total Investido: R$ {total_investido:.2f} MM)"):
            empresas = investimentos_ativos['Empresa']
            valores_aprovados = investimentos_ativos['Valor Aprovado em CI (R$ mil)']
            valores_investidos = investimentos_ativos['Valor Investido até a presente data (R$ mil)']
            
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
        
        with st.expander(f"Montante Total Investido Corrigido pelo IPCA (R$ {total_ipca:.2f} MM)"):
            investimentos_ativos['Valor Corrigido IPCA'] = investimentos_ativos.apply(
                lambda row: corrigir_ipca(
                    row['Valor Investido até a presente data (R$ mil)'],
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
                    row['Valor Investido até a presente data (R$ mil)'],
                    row['Data do Primeiro Investimento'],
                    adicional=6.0
                ),
                axis=1
            )
            plot_comparativo(
                investimentos_ativos['Valor Corrigido IPCA+6%'],
                '#9C27B0',
                'Valor Corrigido'
            )
        
        with st.expander(f"Montante Total Investido Corrigido pelo IPCA+{hurdle}% (R$ {total_ipca_hurdle:.2f} MM)"):
            investimentos_ativos['Valor Corrigido IPCA+Hurdle'] = investimentos_ativos.apply(
                lambda row: corrigir_ipca(
                    row['Valor Investido até a presente data (R$ mil)'],
                    row['Data do Primeiro Investimento'],
                    adicional=hurdle
                ),
                axis=1
            )
            plot_comparativo(
                investimentos_ativos['Valor Corrigido IPCA+Hurdle'],
                '#3F51B5',
                'Valor Corrigido'
            )
    
    # -----------------------------------------------------------
    # Resultados da Carteira
    # -----------------------------------------------------------
    st.subheader("📈 Resultados da Carteira")
    empresas_ativas_graficos = edited_df.loc[edited_df['Write-off'] == False, 'Empresa'].tolist()
    if empresas_ativas_graficos:
        investimentos_ativos = investimentos[investimentos['Empresa'].isin(empresas_ativas_graficos)].copy()
        valor_total_ativo = investimentos_ativos['Valor Investido até a presente data (R$ mil)'].sum()
        valor_hurdle = valor_total_ativo * (1 + (hurdle / 100))
        crescimento_necessario = ((valor_hurdle - valor_total_ativo) / valor_total_ativo) * 100
        st.success(f"As empresas ativas precisam crescer {crescimento_necessario:.2f}% para atingir o valor da Hurdle.")
    else:
        st.error("❗ Nenhuma empresa ativa (Write-off marcado para todas).")

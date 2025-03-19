import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px

def format_brazil(value):
    """
    Formata o número no padrão brasileiro (ex.: 1.234,56).
    """
    formatted = f"{value:,.2f}"
    return formatted.replace(',', 'X').replace('.', ',').replace('X', '.')

def plot_comparativo(empresas, valores_investidos, valores_corrigidos, cor_corrigido, label_corrigido):
    """
    Cria um gráfico comparativo entre valores investidos e corrigidos.
    """
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
    return fig

def criar_grafico_aportes_no_tempo(df_parcelas):
    """
    Cria um gráfico de análise de aportes ao longo do tempo.
    """
    if df_parcelas.empty:
        return None
        
    min_date = df_parcelas["Data Investimento"].min()
    current_month_first = pd.to_datetime(datetime.now().strftime("%Y-%m-01"))
    
    df_agrupado = df_parcelas.groupby("Data Investimento", as_index=False)["Valor Investido"].sum()
    df_agrupado.sort_values("Data Investimento", inplace=True)
    df_agrupado["SomaCumulativa"] = df_agrupado["Valor Investido"].cumsum()

    daily_index = pd.date_range(start=min_date, end=current_month_first, freq='D')
    df_agrupado.set_index("Data Investimento", inplace=True)
    df_agrupado = df_agrupado.reindex(daily_index, method="ffill").fillna(0)
    df_agrupado.index.name = "Data Investimento"

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=daily_index,
            y=df_agrupado["SomaCumulativa"],
            mode='lines+markers',
            line=dict(color='orange'),
            marker=dict(color='orange'),
            name='Cumulativo'
        )
    )
    fig.update_layout(
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
    return fig

def criar_grafico_distribuicao_portfolio(edited_df):
    """
    Cria um gráfico pizza que mostra a distribuição do portfólio entre vendas, write-offs e sem saída.
    """
    # Separar empresas por status
    writeoffs_df = edited_df[edited_df['Write-off'] == True]
    vendas_df = edited_df[(edited_df['Write-off'] == False) & (edited_df['Múltiplo'] > 0)]
    sem_saida_df = edited_df[(edited_df['Write-off'] == False) & (edited_df['Múltiplo'] == 0)]
    
    # Calcular totais
    total_writeoffs = writeoffs_df['Valor Investido'].sum() if not writeoffs_df.empty else 0
    total_vendas = vendas_df.apply(lambda row: row['Valor Investido'] * row['Múltiplo'], axis=1).sum() if not vendas_df.empty else 0
    total_sem_saida = sem_saida_df['Valor Investido'].sum() if not sem_saida_df.empty else 0
    
    # Criar dados para gráfico de pizza
    labels = ['Vendas', 'Write-offs', 'Sem Saída']
    values = [total_vendas, total_writeoffs, total_sem_saida]
    colors = ['#4CAF50', '#F44336', '#2196F3']
    
    # Filtrar valores zerados
    non_zero_indices = [i for i, v in enumerate(values) if v > 0]
    filtered_labels = [labels[i] for i in non_zero_indices]
    filtered_values = [values[i] for i in non_zero_indices]
    filtered_colors = [colors[i] for i in non_zero_indices]
    
    if filtered_values:
        fig = go.Figure(data=[go.Pie(
            labels=filtered_labels,
            values=filtered_values,
            marker_colors=filtered_colors,
            textinfo='value+percent',
            hole=.3,
        )])
        fig.update_layout(
            title="Distribuição do Valor de Portfólio",
            template='plotly_dark'
        )
        return fig, total_vendas, total_writeoffs, total_sem_saida
    else:
        return None, 0, 0, 0

def criar_grafico_participacao_fundo(df_ativos):
    """
    Cria um gráfico de barras da participação do fundo por empresa.
    """
    fig = go.Figure(data=[go.Bar(
        x=df_ativos['Empresa'],
        y=df_ativos['Participação do Fundo (%)'],
        marker_color='#4CAF50'
    )])
    fig.update_layout(
        xaxis_title="Empresa",
        yaxis_title="Participação do Fundo (%)",
        template='plotly_dark'
    )
    return fig

def criar_grafico_hurdle_vs_realizado(total_sale, hurdle_nominal, total_writeoff=0):
    """
    Cria um gráfico comparando o valor de venda realizado versus o hurdle.
    """
    fig = go.Figure(data=[
        go.Bar(name='Realizado', x=['Hurdle vs Realizado'], y=[total_sale], marker_color='light blue'),
        go.Bar(name='Hurdle', x=['Hurdle vs Realizado'], y=[hurdle_nominal], marker_color='light green')
    ])
    fig.update_layout(
        barmode='group',
        bargap=0.4,
        template='plotly_dark',
        title="Hurdle vs Realizado"
    )
    return fig

def criar_grafico_uplift_empresa(empresa, filtered):
    """
    Cria um gráfico de análise de uplift para uma empresa específica.
    """
    if filtered.empty:
        return None
    
    linha = filtered.iloc[0]
    investido = linha['Valor Investido']
    fv_part = linha['FV Part.']
    necessario = linha['IPCA+6%']
    sale = linha['Sale']
    
    x_positions = ['Investido', 'FV Part.', 'IPCA+6%', 'Sale']
    bar_colors = ['#2196F3', '#FF9800', '#4CAF50', '#9C27B0']
    values = [investido, fv_part if pd.notna(fv_part) else 0, necessario, sale]
    
    # Calcula a relação em relação ao IPCA+6% de forma consistente
    fv_to_ipca_percent = "N/A"
    if pd.notna(fv_part) and necessario != 0:
        # Calcula quanto o FV Part. representa do IPCA+6%
        fv_to_ipca_value = (fv_part / necessario) * 100
        fv_to_ipca_percent = f"{fv_to_ipca_value:.2f}%"
    
    sale_to_ipca_percent = "N/A"
    if necessario != 0:
        # Calcula quanto o Sale representa do IPCA+6%
        sale_to_ipca_value = (sale / necessario) * 100
        sale_to_ipca_percent = f"{sale_to_ipca_value:.2f}%"
    
    # Encontrar o valor máximo para ajustar o intervalo do eixo Y
    max_value = max(values)
    
    # Criando um gráfico simplificado
    fig_uplift = go.Figure()
    
    # Adicionando barras com textos em branco e acima das barras
    for i, (x, y, color) in enumerate(zip(x_positions, values, bar_colors)):
        fig_uplift.add_trace(go.Bar(
            x=[x],
            y=[y],
            name=x,
            marker_color=color,
            text=f'R$ {format_brazil(y)}k',
            textposition='outside',  # Posiciona o texto acima da barra
            textfont=dict(color='white')  # Define a cor do texto como branco
        ))
    
    # Título com cálculos consistentes para ambos os indicadores
    title_text = f'<span style="color:white;">Análise de Uplift para {empresa}</span><br>'
    # Agora ambos mostram a relação percentual com IPCA+6%
    title_text += f'<span style="color:#FF9800;">FV Part.</span><span style="color:white;"> → </span><span style="color:#4CAF50;">IPCA+6%</span><span style="color:white;">: {fv_to_ipca_percent}</span><br>'
    title_text += f'<span style="color:#9C27B0;">Sale</span><span style="color:white;"> → </span><span style="color:#4CAF50;">IPCA+6%</span><span style="color:white;">: {sale_to_ipca_percent}</span>'
    
    fig_uplift.update_layout(
        title={
            'text': title_text,
            'y': 0.95,
            'x': 0.5,
            'xanchor': 'center',
            'yanchor': 'top'
        },
        yaxis_title='Valores (R$ mil)',
        template='plotly_dark',
        margin=dict(t=150, r=50, b=100),  # Aumentar margem superior e inferior
        showlegend=False,
        barmode='group',
        height=550,  # Aumentar altura do gráfico
        # Configurar o intervalo do eixo Y para não cortar os valores
        yaxis=dict(
            range=[0, max_value * 1.15]  # Adiciona 15% de espaço acima do valor máximo
        )
    )
    
    return fig_uplift

def criar_comparativo_valores(investimentos_ativos, valores_aprovados=None, valores_corrigidos=None, label_corrigido="", cor_corrigido="#FF5722"):
    """
    Cria um gráfico comparativo entre diferentes valores (aprovado, investido, corrigido, etc).
    """
    empresas = investimentos_ativos['Empresa']
    valores_investidos = investimentos_ativos['Valor Investido']
    
    fig = go.Figure()
    
    # Adiciona barra de valores aprovados se disponível
    if valores_aprovados is not None:
        fig.add_trace(go.Bar(
            x=empresas,
            y=valores_aprovados,
            name='Valor Aprovado',
            marker_color='#4CAF50'
        ))
    
    # Adiciona barra de valores investidos
    fig.add_trace(go.Bar(
        x=empresas,
        y=valores_investidos,
        name='Valor Investido',
        marker_color='#2196F3'
    ))
    
    # Adiciona barra de valores corrigidos se disponível
    if valores_corrigidos is not None:
        fig.add_trace(go.Bar(
            x=empresas,
            y=valores_corrigidos,
            name=label_corrigido,
            marker_color=cor_corrigido
        ))
    
    fig.update_layout(
        yaxis_title='Valores (R$ mil)',
        xaxis_tickangle=-90,
        barmode='group',
        template='plotly_dark'
    )
    return fig

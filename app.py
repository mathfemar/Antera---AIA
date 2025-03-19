import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import os
import requests
import plotly.graph_objects as go
import plotly.express as px

# Importa os módulos personalizados
from modules.portfolio import (
    init_writeoff_status, 
    sincronizar_writeoff_com_multiplos, 
    sincronizar_multiplo_writeoff,
    preparar_dados_iniciais,
    gerar_analise_crescimento
)
from modules.scenarios import (
    carregar_cenarios, 
    salvar_cenario_atual, 
    aplicar_cenario, 
    excluir_cenario,
    inicializar_session_state_cenarios
)
from modules.visualizations import (
    format_brazil,
    criar_grafico_aportes_no_tempo,
    criar_grafico_distribuicao_portfolio,
    criar_grafico_participacao_fundo,
    criar_grafico_hurdle_vs_realizado,
    criar_grafico_uplift_empresa,
    criar_comparativo_valores,
    plot_comparativo
)

# Importa as funções dos arquivos existentes
from callbacks import update_multiplo, update_multiplo_slider, toggle_writeoff
from data_utils import carregar_dados, obter_ipca, calcular_ipca_acumulado, corrigir_ipca, carregar_parcelas_investimento

# Diretórios para localizar arquivos
DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
DIRETORIO_DADOS = os.path.join(DIRETORIO_ATUAL, 'data')

# ---------------------------------------------------------------
# CONFIGURAÇÕES E INÍCIO DO CÓDIGO
# ---------------------------------------------------------------
st.set_page_config(page_title="Primatech Investment Analyzer", layout="wide")

# Inicializa variáveis da sessão para cenários
inicializar_session_state_cenarios()

col_title, col_hurdle_val = st.columns([3, 1])
with col_title:
    st.title("Primatech Investment Analyzer")
with col_hurdle_val:
    hurdle_nominal = st.number_input("Hurdle (R$):", value=117000.0, step=1000.0, format="%.0f")
    st.write(f"Hurdle: R$ {format_brazil(hurdle_nominal)}")

# Slider para ajuste de taxa (IPCA + X%)
hurdle = st.slider("Taxa de Correção (IPCA + %)", 0.0, 15.0, 9.0, 0.5)

fair_value, investimentos = carregar_dados()

if fair_value is not None and investimentos is not None:
    # Prepara os dados iniciais
    df_empresas = preparar_dados_iniciais(fair_value, investimentos)
    
    # Se não existir no session_state, criamos; caso exista, não sobrescrevemos
    if 'edited_df' not in st.session_state:
        st.session_state.edited_df = df_empresas.copy()
    else:
        # Se o dataframe existe mas não tem a coluna Write-off, adicionamos
        if "Write-off" not in st.session_state.edited_df.columns:
            st.session_state.edited_df["Write-off"] = False
    
    sincronizar_writeoff_com_multiplos()
    init_writeoff_status()
    
    # Seção de Cenários - Agora no topo do dashboard
    st.subheader("Gerenciamento de Cenários")
    
    # Layout horizontal para criar, aplicar e excluir cenários
    col_novo, col_carregar = st.columns(2)

    with col_novo:
        st.text_input("Nome do Cenário", key="novo_cenario", placeholder="Digite o nome para salvar")
        # Container para o botão salvar, ocupando toda a largura
        container_salvar = st.container()
        container_salvar.button("Salvar Cenário Atual", on_click=salvar_cenario_atual, use_container_width=True)

    with col_carregar:
        if st.session_state.cenarios_disponiveis:
            st.selectbox(
                "Cenários Disponíveis",
                options=st.session_state.cenarios_disponiveis,
                key="cenario_selecionado"
            )
            
            # Usar container para os botões
            container = st.container()
            # Criar os botões lado a lado sem espaço entre eles
            col1, col2 = container.columns([1, 1], gap="small")
            with col1:
                st.button("Aplicar Cenário", on_click=aplicar_cenario, use_container_width=True)
            with col2:
                st.button("Excluir Cenário", on_click=excluir_cenario, use_container_width=True)
        else:
            st.info("Nenhum cenário salvo.")
    
    st.markdown("---")
    
    # Layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Empresas do Portfólio")
        
        col_table, col_placeholder = st.columns([1, 1], gap="small")
        with col_table:
            new_cols = ["Múltiplo", "Empresa", "Valor Investido", "Fair Value", "Participação do Fundo (%)", "Data do Primeiro Investimento", "Write-off"]
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
                    "Data do Primeiro Investimento": st.column_config.TextColumn("Data do Primeiro Investimento"),
                    "Write-off": st.column_config.CheckboxColumn("Write-off", width=80)
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
            
            # Obtém os valores atuais
            current_row = edited_df.loc[edited_df["Empresa"] == company_selected].iloc[0]
            current_value = float(current_row["Múltiplo"])
            is_writeoff = bool(current_row.get("Write-off", False))
            
            # Adiciona opção de write-off
            writeoff = st.checkbox(
                "Write-off (perda total - múltiplo será 0)",
                value=bool(current_row.get("Write-off", False)),
                key=f"writeoff_{company_selected}",
                on_change=toggle_writeoff,
                help="Marque esta opção caso a empresa tenha sido um write-off (perda total)."
            )
            
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
        st.subheader("Crescimento Necessário por Empresa (IPCA+6%)")
        col_table2, col_graph = st.columns([1, 1])
        
        active_investments = st.session_state.edited_df[
            st.session_state.edited_df['Múltiplo'] > 0
        ].copy()
        
        # Usa a função modularizada para gerar análise de crescimento
        analise_crescimento = gerar_analise_crescimento(active_investments, corrigir_ipca)
        
        with col_table2:
            st.markdown("**Tabela de Crescimento**")
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
                    fig_uplift = criar_grafico_uplift_empresa(empresa_sel, filtered)
                    if fig_uplift:
                        st.plotly_chart(fig_uplift, use_container_width=True)
        
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

        # Calcular total de vendas (excluindo write-offs)
        vendas = analise_crescimento[~analise_crescimento['Write-off']]
        total_sale = vendas["Sale"].sum() if "Sale" in vendas.columns else 0.0
        
        # Calcular total de write-offs
        writeoffs = analise_crescimento[analise_crescimento['Write-off']]
        total_writeoff = writeoffs["Valor Investido"].sum() if not writeoffs.empty else 0.0
        
        # Usar a função modularizada para criar o gráfico
        fig_hurdle = criar_grafico_hurdle_vs_realizado(total_sale, hurdle_nominal, total_writeoff)
        st.plotly_chart(fig_hurdle, use_container_width=True)
        
        # Adiciona informação sobre write-offs
        if total_writeoff > 0:
            st.info(f"**Write-offs não incluídos no cálculo:** R$ {format_brazil(total_writeoff)} mil")

    # -----------------------------------------------------------
    # COLUNA 2: Resumo da Carteira e Gráficos
    # -----------------------------------------------------------
    with col2:
        st.subheader("Gráficos de Investimentos")
        
        # NOVO: Adicionando o gráfico de Análise de Aportes no Tempo como expander na segunda coluna
        with st.expander("Análise de Aportes no Tempo - Soma Cumulativa", expanded=False):
            try:
                # Carrega os dados de parcelas usando a função modularizada
                df_parcelas = carregar_parcelas_investimento()
                
                if not df_parcelas.empty:
                    fig_temp = criar_grafico_aportes_no_tempo(df_parcelas)
                    if fig_temp:
                        st.plotly_chart(fig_temp, use_container_width=True)
                    else:
                        st.warning("Não há dados suficientes para exibir o gráfico cumulativo de investimentos.")
                else:
                    st.warning("Não há dados suficientes para exibir o gráfico cumulativo de investimentos.")
            except Exception as e:
                st.error(f"Erro ao processar dados para o gráfico de aportes: {e}")
        
        # Adiciona gráfico para mostrar distribuição de vendas vs write-offs
        with st.expander("Distribuição de Vendas vs Write-offs", expanded=True):
            fig_distrib, total_vendas, total_writeoffs, total_sem_saida = criar_grafico_distribuicao_portfolio(st.session_state.edited_df)
            
            if fig_distrib:
                st.plotly_chart(fig_distrib, use_container_width=True)
                
                # Adiciona explicação dos valores
                st.markdown(f"""
                **Valores Detalhados:**
                - **Vendas:** R$ {format_brazil(total_vendas)} mil (valor de saída)
                - **Write-offs:** R$ {format_brazil(total_writeoffs)} mil (valor perdido)
                - **Sem Saída:** R$ {format_brazil(total_sem_saida)} mil (valor ainda investido)
                """)
            else:
                st.info("Não há dados suficientes para exibir o gráfico de distribuição.")
        
        with st.expander("Participação do Fundo por Empresa", expanded=False):
            df_ativos = st.session_state.edited_df[st.session_state.edited_df['Múltiplo'] > 0]
            fig_port = criar_grafico_participacao_fundo(df_ativos)
            st.plotly_chart(fig_port, use_container_width=True)
        
        with st.expander(f"Comparativo: Valor Aprovado vs Valor Investido (Total Investido: R$ {total_investido:.2f} MM)", expanded=False):
            valores_aprovados = investimentos_ativos['Valor Aprovado em CI (R$ mil)']
            fig = criar_comparativo_valores(
                investimentos_ativos, 
                valores_aprovados=valores_aprovados
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with st.expander(f"Montante Total Investido Corrigido pelo IPCA (R$ {total_ipca:.2f} MM)", expanded=False):
            investimentos_ativos['Valor Corrigido IPCA'] = investimentos_ativos.apply(
                lambda row: corrigir_ipca(
                    row['Valor Investido'],
                    row['Data do Primeiro Investimento']
                ),
                axis=1
            )
            fig = plot_comparativo(
                investimentos_ativos['Empresa'],
                investimentos_ativos['Valor Investido'],
                investimentos_ativos['Valor Corrigido IPCA'],
                '#FF5722',
                'Valor Corrigido'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with st.expander(f"Montante Total Investido Corrigido pelo IPCA+6% (R$ {total_ipca_6:.2f} MM)", expanded=False):
            investimentos_ativos['Valor Corrigido IPCA+6%'] = investimentos_ativos.apply(
                lambda row: corrigir_ipca(
                    row['Valor Investido'],
                    row['Data do Primeiro Investimento'],
                    adicional=6.0
                ),
                axis=1
            ).round(2)
            fig = plot_comparativo(
                investimentos_ativos['Empresa'],
                investimentos_ativos['Valor Investido'],
                investimentos_ativos['Valor Corrigido IPCA+6%'],
                '#9C27B0',
                'Valor Corrigido'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with st.expander(f"Montante Total Investido Corrigido pelo IPCA+{hurdle}% (R$ {total_ipca_hurdle:.2f} MM)", expanded=False):
            investimentos_ativos['Valor Corrigido IPCA+Hurdle'] = investimentos_ativos.apply(
                lambda row: corrigir_ipca(
                    row['Valor Investido'],
                    row['Data do Primeiro Investimento'],
                    adicional=hurdle
                ),
                axis=1
            ).round(2)
            fig = plot_comparativo(
                investimentos_ativos['Empresa'],
                investimentos_ativos['Valor Investido'],
                investimentos_ativos['Valor Corrigido IPCA+Hurdle'],
                '#3F51B5',
                'Valor Corrigido'
            )
            st.plotly_chart(fig, use_container_width=True)

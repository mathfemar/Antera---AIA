import time
import streamlit as st

# Função callback que atualiza o "Múltiplo" na tabela global a partir do number_input
def update_multiplo():
    comp = st.session_state["select_company"]
    new_val = st.session_state[f"num_{comp}"]
    
    # Atualiza múltiplo no DataFrame
    st.session_state.edited_df.loc[
        st.session_state.edited_df["Empresa"] == comp, "Múltiplo"
    ] = new_val
    
    # Atualiza também o slider para manter sincronizado
    st.session_state[f"slider_{comp}"] = new_val
    
    # Se o múltiplo for 0, marca como write-off automaticamente
    if new_val == 0:
        st.session_state[f"writeoff_{comp}"] = True
        st.session_state.edited_df.loc[
            st.session_state.edited_df["Empresa"] == comp, "Write-off"
        ] = True
    # Se o múltiplo for maior que 0, desmarca write-off automaticamente
    else:
        st.session_state[f"writeoff_{comp}"] = False
        st.session_state.edited_df.loc[
            st.session_state.edited_df["Empresa"] == comp, "Write-off"
        ] = False

# Função callback que atualiza o "Múltiplo" na tabela global a partir do slider
def update_multiplo_slider():
    time.sleep(1)  # Pequeno atraso para melhorar a experiência do usuário
    comp = st.session_state["select_company"]
    new_val = st.session_state[f"slider_{comp}"]
    
    # Atualiza múltiplo no DataFrame
    st.session_state.edited_df.loc[
        st.session_state.edited_df["Empresa"] == comp, "Múltiplo"
    ] = new_val
    
    # Atualiza também o campo numérico para manter sincronizado
    st.session_state[f"num_{comp}"] = new_val
    
    # Se o múltiplo for 0, marca como write-off automaticamente
    if new_val == 0:
        st.session_state[f"writeoff_{comp}"] = True
        st.session_state.edited_df.loc[
            st.session_state.edited_df["Empresa"] == comp, "Write-off"
        ] = True
    # Se o múltiplo for maior que 0, desmarca write-off automaticamente
    else:
        st.session_state[f"writeoff_{comp}"] = False
        st.session_state.edited_df.loc[
            st.session_state.edited_df["Empresa"] == comp, "Write-off"
        ] = False

# Função callback que alterna o status de write-off e ajusta o múltiplo correspondentemente
def toggle_writeoff():
    comp = st.session_state["select_company"]
    is_writeoff = st.session_state[f"writeoff_{comp}"]
    
    # Atualiza a coluna Write-off no DataFrame
    st.session_state.edited_df.loc[
        st.session_state.edited_df["Empresa"] == comp, "Write-off"
    ] = is_writeoff
    
    # Quando marcar write-off, define como 0
    if is_writeoff:
        st.session_state[f"num_{comp}"] = 0.0
        st.session_state[f"slider_{comp}"] = 0.0
        st.session_state.edited_df.loc[
            st.session_state.edited_df["Empresa"] == comp, "Múltiplo"
        ] = 0.0
    # Quando desmarcar write-off, define como 1
    else:
        st.session_state[f"num_{comp}"] = 1.0
        st.session_state[f"slider_{comp}"] = 1.0
        st.session_state.edited_df.loc[
            st.session_state.edited_df["Empresa"] == comp, "Múltiplo"
        ] = 1.0

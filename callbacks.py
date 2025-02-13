import time
import streamlit as st

# Função callback que atualiza o "Múltiplo" na tabela global a partir do number_input
def update_multiplo():
    comp = st.session_state["select_company"]
    new_val = st.session_state[f"num_{comp}"]
    st.session_state.edited_df.loc[
        st.session_state.edited_df["Empresa"] == comp, "Múltiplo"
    ] = new_val

# Função callback que atualiza o "Múltiplo" na tabela global a partir do slider, com atraso de 1 segundo
def update_multiplo_slider():
    time.sleep(1)
    comp = st.session_state["select_company"]
    new_val = st.session_state[f"slider_{comp}"]
    st.session_state.edited_df.loc[
        st.session_state.edited_df["Empresa"] == comp, "Múltiplo"
    ] = new_val

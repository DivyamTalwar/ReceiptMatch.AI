import streamlit as st
import pandas as pd

class UIComponents:
    @staticmethod
    def metric_card(title: str, value: any, delta: str = None, help_text: str = None):
        with st.container():
            st.metric(label=title, value=value, delta=delta, help=help_text)

    @staticmethod
    def progress_tracker(current_step: int, total_steps: int, step_names: list):
        if not 0 <= current_step <= total_steps:
            return

        progress = current_step / total_steps
        st.progress(progress)
        
        cols = st.columns(total_steps)
        for i, (col, step_name) in enumerate(zip(cols, step_names)):
            with col:
                if i < current_step:
                    st.success(f"{step_name}")
                elif i == current_step:
                    st.info(f"{step_name}")
                else:
                    st.write(f"{step_name}")
    
    @staticmethod
    def data_table_with_actions(df: pd.DataFrame, key_column: str, actions: list = None):
        if actions is None:
            actions = ['Edit', 'Delete', 'View']
        
        df_with_actions = df.copy()
        df_with_actions['Actions'] = ''
        
        edited_df = st.data_editor(
            df_with_actions,
            use_container_width=True,
            hide_index=True,
            column_config={
                key_column: st.column_config.Column(
                    "ID",
                    help=f"Unique {key_column}",
                    width="small",
                ),
                "Actions": st.column_config.SelectboxColumn(
                    "Actions",
                    help="Select an action to perform",
                    width="medium",
                    options=actions,
                    required=True
                )
            },
            key=f"data_editor_{key_column}"
        )
        return edited_df

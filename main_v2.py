import pandas as pd
import numpy as np
import streamlit as st
import plotly_express as px
import plotly.graph_objects as go
from io import BytesIO



st.set_page_config(layout='wide')
sx_h, dx_h = st.columns([8,1])
sx_h.title('Analisi Microfermate')
#dx_h.image('logo.png', width=200)

#PATH = 'DB_Fermi_nuovo_modello_form.xlsm'
PATH = st.file_uploader("Carica il file Excel", type=["xlsm", "xlsx"])
if not PATH:
    st.warning("Per favore, carica un file Excel per procedere con l'analisi.")
    st.stop()   

PAUSE = {
    'Pausa10':10,
    'Pausa30':30,
    'Pausa':10
}

MAP_PAUSE = {
    'Pausa10':'Extra-pausa',
    'Pausa30':'Extra-pausa',
    'Pausa':'Extra-pausa'
    }


f_size = 18
f_angle =-45

STILE = {
    'colore_barre':"#246B9E",
    'colore_linea':'#CD3128',
    'name_bar':'Durata',
    'name_cum':'cum_pct',
    'y_name': 'Durata [h]',
    'y2_name': 'pct_cumulativa',
    'tick_size':16,
    'angle':-45
}

STILE2 = {
    'colore_barre':"#DC9661",
    'colore_linea':'#CD3128',
    'name_bar':'Durata',
    'name_cum':'cum_pct',
    'y_name': 'Durata [h]',
    'y2_name': 'pct_cumulativa',
    'tick_size':16,
    'angle':-45
}




def pareto(df, label, value ,stile):
    '''
    - La funzione crea l'aggregazione dei valori per categoria, ordina decrescente e calcola la pct cumulativa
    - Fa il grafico
    - Label è la colonna con la categoria da raggruppare
    - Value è il valore, che viene SOMMATO
    
    '''
    df_work = df[[label, value]].groupby(by=label, as_index=False).sum()

    df_work = df_work.sort_values(by=value, ascending=False)
    df_work['pct'] = df_work[value] / df_work[value].sum()
    df_work['pct_cum'] = df_work['pct'].cumsum()
    pareto = go.Figure()

    pareto.add_trace(go.Bar(
        x=df_work[label],
        y=df_work[value],
        name=stile['name_bar'],
        marker_color=stile['colore_barre']
    ))

    pareto.add_trace(go.Scatter(
        x=df_work[label],
        y=df_work['pct_cum'],
        yaxis='y2',
        name=stile['name_cum'],
        marker_color=stile['colore_linea']
        )
    )

    pareto.update_layout(
        showlegend=False,
        height=500,
        width=800,
        yaxis=dict(
            title=dict(text=stile['y_name'], font = dict(size=stile['tick_size'])),
            side="left",
            tickfont=dict(size=stile['tick_size'])
            
        ),
        margin=dict(l=50, r=50, t=50, b=0),
        yaxis2=dict(
            title=dict(text=stile['y2_name'], font = dict(size=stile['tick_size'])),
            side="right",
            range=[0, 1.2],
            overlaying="y",
            tickmode="sync",
            tickformat=".0%",
            tickfont=dict(size=stile['tick_size'])

        ),
        xaxis=dict(
            tickfont=dict(size=stile['tick_size']),
            tickangle=stile['angle']
        )
    )

    return pareto


df = pd.read_excel(PATH, sheet_name='Database')
df['Standard'] = df['Causale di secondo livello'].map(PAUSE).fillna(0)
df['Cat_adj'] = df['Causale di secondo livello'].replace(MAP_PAUSE)
df['Durata_adj'] = np.round(df['Durata [min]'] - df['Standard'], 2)
# se il codice contiene "goujon" oppure "gujon" allora "SALDATA" altrimenti "NON SALDATA"
df['Saldatura'] = df['Codice'].apply(lambda x: 'SALDATA' if 'goujon' in str(x).lower() or 'gujon' in str(x).lower() else 'NON SALDATA')

# Creare ID_rilevazione
# Estrarre la data da data_ora inizio
df['data'] = pd.to_datetime(df['data_ora inizio']).dt.date

# Identificare le righe con INIZIO per assegnare il blocco
df['is_inizio'] = df['Causale di primo livello'] == 'INIZIO'
df['is_fine'] = df['Causale di primo livello'] == 'FINE'

# Creare un ID blocco progressivo basato su INIZIO
df['blocco_num'] = df['is_inizio'].cumsum()

# Per ogni blocco, prendere la data e il codice dalla riga INIZIO
blocco_info = df[df['is_inizio']].copy()
blocco_info['data_blocco'] = blocco_info['data']
blocco_info['codice_blocco'] = blocco_info['Codice']

# Numerare i blocchi per combinazione data-codice
blocco_info['num_progressivo'] = blocco_info.groupby(['data_blocco', 'codice_blocco']).cumcount() + 1

# Mappare le informazioni del blocco a tutte le righe
blocco_map = blocco_info[['blocco_num', 'data_blocco', 'codice_blocco', 'num_progressivo']].set_index('blocco_num')
df = df.merge(blocco_map, left_on='blocco_num', right_index=True, how='left')

# Creare ID_rilevazione nel formato: data-codice-blocco
df['ID_rilevazione'] = df.apply(
    lambda row: f"{row['data_blocco']} | {row['codice_blocco']} | {int(row['num_progressivo'])}" 
    if pd.notna(row['data_blocco']) and pd.notna(row['codice_blocco']) and pd.notna(row['num_progressivo'])
    else None, 
    axis=1
)

# Rimuovere colonne temporanee
df = df.drop(columns=['is_inizio', 'is_fine', 'blocco_num', 'data_blocco', 'codice_blocco', 'num_progressivo'])

# Creare dataframe raggruppato per blocco
df_blocchi = df.groupby(['ID_rilevazione','Codice']).agg(
    data_inizio_min=('data_ora inizio', 'min'),
    data_inizio_max=('data_ora inizio', 'max'),
    durata_adj_totale=('Durata_adj', 'sum'),
    Saldatura=('Saldatura', 'first')
).reset_index()

# Calcolare la durata della rilevazione in minuti
df_blocchi['durata_rilevazione_min'] = (
    (df_blocchi['data_inizio_max'] - df_blocchi['data_inizio_min']).dt.total_seconds() / 60
).round(2)

# Eliminare le righe INIZIO e FINE dal dataframe principale dopo il calcolo dei blocchi
df = df[~df['Causale di primo livello'].isin(['INIZIO', 'FINE'])]

# Creare dataframe aggregato per codice
df_codice = df_blocchi.groupby('Codice').agg(
    durata_rilevazione_totale=('durata_rilevazione_min', 'sum'),
    durata_adj_totale=('durata_adj_totale', 'sum'),
    numero_blocchi=('ID_rilevazione', 'count'),
    Saldatura=('Saldatura', 'first')
).reset_index()

df_codice = df_codice.round(2)
df_codice['%fermate']=(df_codice['durata_adj_totale'] / df_codice['durata_rilevazione_totale']).round(2)
df_codice['%fermate_pct'] = (df_codice['%fermate'] * 100).round(1)
df_codice = df_codice.sort_values(by='%fermate', ascending=False).reset_index(drop=True)

# Grafico a punti per codice
st.subheader('Grafico % fermate per codice')
st.info('Il grafico mostra la percentuale di fermate rispetto alla durata totale di rilevazione per ogni codice, con la dimensione dei punti che rappresenta la durata totale di rilevazione. I codici sono colorati in base alla presenza o meno di saldatura.')
fig_scatter = px.scatter(
    df_codice, 
    x='Codice', 
    y='%fermate_pct',
    size='durata_rilevazione_totale',
    title='% Fermate per codice',
    labels={'%fermate_pct': '% Fermate', 'Codice': 'Codice', 'durata_rilevazione_totale': 'Durata rilevazione (min)', 'Saldatura': 'Saldatura'},
    color='Saldatura',
    text='%fermate_pct',
    size_max=40
)
fig_scatter.update_layout(showlegend=True, xaxis_tickangle=-45, height=600, width=800)
fig_scatter.update_traces(
    textposition='top center', 
    texttemplate='%{text:.1f}%'
)
fig_scatter.update_yaxes(ticksuffix='%')
st.plotly_chart(fig_scatter, use_container_width=True)

# Sezione Drill Down
st.subheader('Drill Down Analisi')

# Filtro 1: Saldatura
saldature_disponibili = ['Tutti'] + sorted(df['Saldatura'].dropna().unique().tolist())
saldatura_selezionata = st.selectbox('Seleziona Saldatura', options=saldature_disponibili)

# Filtrare per saldatura
if saldatura_selezionata == 'Tutti':
    df_filtrato_saldatura = df.copy()
else:
    df_filtrato_saldatura = df[df['Saldatura'] == saldatura_selezionata]

# Filtro 2: Codice
codici_disponibili = ['Tutti'] + sorted(df_filtrato_saldatura['Codice'].dropna().unique().tolist())
codice_selezionato = st.selectbox('Seleziona Codice', options=codici_disponibili)

# Filtrare per codice
if codice_selezionato == 'Tutti':
    df_filtrato_codice = df_filtrato_saldatura.copy()
else:
    df_filtrato_codice = df_filtrato_saldatura[df_filtrato_saldatura['Codice'] == codice_selezionato]

# Filtro 3: Causale di primo livello
causali_1liv_disponibili = ['Tutti'] + sorted(df_filtrato_codice['Causale di primo livello'].dropna().unique().tolist())
causali_1liv_disponibili = [c for c in causali_1liv_disponibili if c not in ['INIZIO', 'FINE']] 
causale_1liv_selezionata = st.selectbox('Seleziona Causale di Primo Livello', options=causali_1liv_disponibili)

# Filtrare per causale di primo livello
if causale_1liv_selezionata == 'Tutti':
    df_filtrato_causale1 = df_filtrato_codice.copy()
else:
    df_filtrato_causale1 = df_filtrato_codice[df_filtrato_codice['Causale di primo livello'] == causale_1liv_selezionata]

# Prima riga: Pareto Primo Livello
st.subheader('Analisi di primo Livello', divider='blue')
col1_1, col1_2 = st.columns([3, 1])

with col1_1:
    pareto_1liv = pareto(df_filtrato_codice, 'Causale di primo livello', 'Durata_adj', STILE)
    st.plotly_chart(pareto_1liv, use_container_width=False)

with col1_2:
    st.subheader(':blue[*Metriche di primo livello*]')
    # Calcolare metriche per primo livello
    totale_ore_fermo_1 = df_filtrato_codice['Durata_adj'].sum() / 60


    if saldatura_selezionata == 'Tutti':
        df_blocchi = df_blocchi.copy()
    else:
        df_blocchi = df_blocchi[df_blocchi['Saldatura'] == saldatura_selezionata]

    if codice_selezionato == 'Tutti':
        totale_ore_rilievo_1 = df_blocchi['durata_rilevazione_min'].sum() / 60
    else:
        totale_ore_rilievo_1 = df_blocchi[df_blocchi['Codice'] == codice_selezionato]['durata_rilevazione_min'].sum() / 60


    st.metric("Totale ore di rilievo", f"{totale_ore_rilievo_1:.2f} h", border=True)
    st.metric("Totale ore di fermo", f"{totale_ore_fermo_1:.2f} h", border=True)
    #metric impatto %
    if totale_ore_rilievo_1 > 0:
        impatto_pct = (totale_ore_fermo_1 / totale_ore_rilievo_1) * 100
    else:
        impatto_pct = 0
    st.metric("Impatto %", f"{impatto_pct:.2f} %", border=True)
    
st.divider()

# Seconda riga: Pareto Secondo Livello
st.subheader(f'Analisi di secondo Livello di: {causale_1liv_selezionata}',divider='orange')
col2_1, col2_2 = st.columns([3, 1])

with col2_1:
    pareto_2liv = pareto(df_filtrato_causale1, 'Causale di secondo livello', 'Durata_adj', STILE2)
    st.plotly_chart(pareto_2liv, use_container_width=False)

with col2_2:
    st.subheader(':orange[*Metriche di secondo livello*]')
    # Calcolare metriche per secondo livello
    totale_ore_fermo_2 = df_filtrato_causale1['Durata_adj'].sum() / 60
    if len(df_filtrato_causale1) > 0:
        data_min_2 = df_filtrato_causale1['data_ora inizio'].min()
        data_max_2 = df_filtrato_causale1['data_ora inizio'].max()
        totale_ore_rilievo_2 = (data_max_2 - data_min_2).total_seconds() / 3600
    else:
        totale_ore_rilievo_2 = 0
    

    st.metric("Totale ore di fermo", f"{totale_ore_fermo_1:.2f} h", border=True)
    st.metric(f"Totale ore di fermo {causale_1liv_selezionata}", f"{totale_ore_fermo_2:.2f} h", border=True)
    #metric impatto %
    if totale_ore_rilievo_2 > 0:
        impatto_pct_2 = (totale_ore_fermo_2 / totale_ore_fermo_1) * 100
    else:
        impatto_pct_2 = 0
    st.metric(f"Impatto % {causale_1liv_selezionata}", f"{impatto_pct_2:.2f} %", border=True)

st.divider()

# Tabella dettaglio filtrato
st.subheader('Dettaglio dati filtrati')
colonne_da_mostrare = ['data_ora inizio', 'data_ora fine', 'Durata [min]', 'Codice', 'Causale di primo livello', 'Cat_adj', 'Durata_adj']
#rimuovi le righe con causale 1 livello uguale a INIZIO o FINE
df_filtrato_causale1 = df_filtrato_causale1[~df_filtrato_causale1['Causale di primo livello'].isin(['INIZIO', 'FINE'])]
st.dataframe(df_filtrato_causale1[colonne_da_mostrare], use_container_width=True)

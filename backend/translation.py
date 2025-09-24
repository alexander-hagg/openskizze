# backend/translation.py (Final Corrected Version)

T = {
    'DE': {
        'APP_TITLE': "OpenSKIZZE - Interaktiver Städtebau Explorer",
        'NEXT_STEP': "Nächster Schritt",
        'PREV_STEP': "Vorheriger Schritt",

        # Step 1
        'STEP1_TITLE': "Schritt 1: Geltungsbereich und klimatische Parameter festlegen",
        'STEP1_WIND_HEADER': "Klimatische Parameter",
        'STEP1_WIND_SLIDER_LABEL': "Windrichtung (TODO: importieren von Klimamodell)",
        'STEP1_DATA_SOURCE_INFO': "Kartengrundlage: OpenStreetMap. Zukünftig: Anbindung an Geodatenportal NRW.",

        # Step 2
        'STEP2_TITLE': "Schritt 2: Leistungsmerkmale und Optimierungsziele festlegen",
        'STEP2_OBJECTIVES_HEADER': "Leistungsmerkmale",
        'STEP2_MEASURES_LABEL': "Wählen Sie die Merkmale zur Generierung diverser Lösungen:",
        'STEP2_OBJECTIVE_INFO_LABEL': "Zielfunktion Optimierung",
        'STEP2_OBJECTIVE_INFO_TEXT': "Optimierung der Kaltluft-Porosität, basierend auf der in Schritt 1 gewählten Windrichtung.",
        
        'MEASURE_0': 'Bebaute Fläche',
        'MEASURE_1': 'Durchschnittliche Bauhöhe',
        'MEASURE_2': 'Variabilität Bauhöhe',
        'MEASURE_3': 'Anzahl der Gebäude',
        'MEASURE_4': 'Durchschnittliche Gebäudedistanz',
        'MEASURE_5': 'Brutto-Grundfläche',
        'MEASURE_6': 'Gebäudemasse X-Achse',
        'MEASURE_7': 'Gebäudemasse Y-Achse',

        # Step 3
        'STEP3_TITLE': "Schritt 3: Entwurfsvarianten generieren",
        'STEP3_START_BUTTON': "Optimierung starten",
        'STEP3_RESULTS_HEADER': "Ergebnis der Optimierung",

        # Step 4
        'STEP4_TITLE': "Schritt 4: Lösungsraum analysieren",
        'STEP4_X_AXIS_LABEL': "X-Achse auswählen:",
        'STEP4_Y_AXIS_LABEL': "Y-Achse auswählen:",
        'STEP4_GRID_HEADER': "Lösungsarchiv (Bester Entwurf pro Nische)",
        
        # Step 5
        'STEP5_TITLE': "Schritt 5: Varianten vergleichen und Anforderungen exportieren",
        'STEP5_EXPORT_BUTTON': "Planungsanforderungen für Wettbewerb exportieren",
        'STEP5_EXPORT_FILENAME': "planungsanforderungen.txt",
        'STEP5_FILTER_HEADER': "Designs filtern und analysieren",
        'STEP5_ANALYSIS_HEADER': "Analyse der Entwurfstypen (Cluster)",
        'STEP5_RUN_BUTTON': "Analyse starten / neu filtern",
        'STEP5_CLUSTER_CARD_TITLE': "Cluster {id} - Entwurfstyp (Größe: {size})",
        'STEP5_CLUSTER_CARD_TEXT': "Dieser Entwurfstyp ist robust, da er in {size} Varianten gefunden wurde.",
        'STEP5_BEST_SOLUTION_HEADER': "Beste Lösung (Höchste Porosität)",
        'STEP5_CENTRAL_SOLUTION_HEADER': "Zentralste Lösung (Repräsentativste)",
        'STEP5_CONSENSUS_MAP_HEADER': "Konsens-Karte (Bebauungswahrscheinlichkeit)",
        'STEP5_NO_CLUSTERS_FOUND': "Keine Cluster gefunden. Versuchen Sie, die Filter oder die Clustering-Parameter anzupassen.",
        'STEP5_NO_SELECTION': "Zum Starten bitte auf 'Analyse starten' klicken.",
        'STEP5_SELECT_LABEL': "Wählen Sie Designs aus der Analyse unten aus, um sie im Detail zu vergleichen (Zukünftige Funktion).",
        'STEP5_ALGORITHM_LABEL': "Clustering-Algorithmus:",
        'STEP5_KMEDOIDS_K_LABEL': "Anzahl der Cluster (k):",
        'STEP5_HDBSCAN_MINCLUSTER': "Minimale Clustergröße:"
    }
}
# Add English translations if needed
T['EN'] = T['DE']
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
        'STEP2_TITLE': "Schritt 2: Optimierungsziele festlegen",
        'STEP2_OBJECTIVES_HEADER': "Leistungsmerkmale (Measures)",
        'STEP2_MEASURES_LABEL': "Wählen Sie die Merkmale zur Generierung diverser Lösungen:",
        'STEP2_OBJECTIVE_INFO_LABEL': "Zielfunktion (Objective)",
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
        # --- THE MISSING KEY IS ADDED HERE ---
        'STEP3_RESULTS_HEADER': "Ergebnis der Optimierung",

        # Step 4
        'STEP4_TITLE': "Schritt 4: Lösungsraum analysieren",
        'STEP4_X_AXIS_LABEL': "X-Achse auswählen:",
        'STEP4_Y_AXIS_LABEL': "Y-Achse auswählen:",
        'STEP4_GRID_HEADER': "Lösungsarchiv (Bester Entwurf pro Nische)",
        
        # Step 5
        'STEP5_TITLE': "Schritt 5: Varianten vergleichen und Anforderungen exportieren",
        'STEP5_EXPORT_BUTTON': "Planungsanforderungen für Wettbewerb exportieren",
    }
}
# Add English translations if needed
T['EN'] = T['DE']
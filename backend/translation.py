# A simple dictionary for UI translations
# This can be expanded to a more robust i18n library later.

T = {
    'DE': {
        'APP_TITLE': "OpenSKIZZE - Interaktiver Städtebau Explorer",
        'NEXT_STEP': "Nächster Schritt",
        'PREV_STEP': "Vorheriger Schritt",

        # Step 1
        'STEP1_TITLE': "Schritt 1: Geltungsbereich und klimatische Parameter festlegen",
        'STEP1_MAP_HEADER': "Geltungsbereich definieren",
        'STEP1_DRAW_TOOLTIP': "Zeichnen Sie ein Polygon auf der Karte.",
        'STEP1_UPLOAD_SHAPE': "oder Geltungsbereich hochladen (GeoJSON)",
        'STEP1_WIND_HEADER': "Klimatische Parameter",
        'STEP1_WIND_SLIDER_LABEL': "Manuelle Windrichtung",
        'STEP1_UPLOAD_KLAM': "Klimamodell-Daten laden (Zukünftige Funktion)",
        'STEP1_DATA_SOURCE_INFO': "Kartengrundlage: OpenStreetMap. Zukünftig: Anbindung an Geodatenportal NRW für amtliche Daten und erweiterte Analysen.",

        # Step 2
        'STEP2_TITLE': "Schritt 2: Rahmenbedingungen und Planungsziele definieren",
        'STEP2_TABOO_HEADER': "Tabu-Zonen definieren (Bauverbotszonen)",
        'STEP2_OBJECTIVES_HEADER': "Merkmale & Zielfunktion",
        'STEP2_MEASURES_LABEL': "Wählen Sie die Merkmale zur Generierung diverser Lösungen:",
        'STEP2_OBJECTIVE_INFO_LABEL': "Zielfunktion",
        'STEP2_OBJECTIVE_INFO_TEXT': "Optimierung des Kaltluftabflusses, basierend auf einem KI-Modell (trainiert mit KLAM_21 Daten).",
        'MEASURE_FOOTPRINT': "Grundfläche",
        'MEASURE_LIVING_SPACE': "Wohnfläche",
        'MEASURE_DENSITY': "Baudichte",
        'MEASURE_PERMEABILITY': "Permeabilität",
        'MEASURE_OPEN_SPACE': "Frei-/Grünflächenanteil",
        'MEASURE_NUM_BUILDINGS': "Anzahl der Gebäude",

        # Step 3
        'STEP3_TITLE': "Schritt 3: Entwurfsvarianten generieren",
        'STEP3_START_BUTTON': "Optimierung starten",
        'STEP3_PROGRESS_BAR_TEXT': "Fortschritt:",
        'STEP3_RESULTS_HEADER': "Ergebnis der Optimierungsläufe",

        # Step 4
        'STEP4_TITLE': "Schritt 4: Lösungsraum analysieren",
        'STEP4_X_AXIS_LABEL': "X-Achse auswählen:",
        'STEP4_Y_AXIS_LABEL': "Y-Achse auswählen:",
        'STEP4_GRID_HEADER': "Lösungsarchiv (Bester Entwurf pro Nische)",

        # Step 5
        'STEP5_TITLE': "Schritt 5: Varianten vergleichen und Anforderungen exportieren",
        'STEP5_SELECT_LABEL': "Wählen Sie Designs aus dem Lösungsraum zur Analyse aus (Klick im Raster von Schritt 4 - Zukünftige Funktion)",
        'STEP5_COMPARE_HEADER': "Vergleich der ausgewählten Varianten",
        'STEP5_EXPORT_BUTTON': "Planungsanforderungen für Wettbewerb exportieren",
        'STEP5_EXPORT_FILENAME': "Planungsanforderungen_OpenSKIZZE.txt",
        'STEP5_NO_SELECTION': "Keine Variante ausgewählt.",
    }
}

# Add EN translation if needed by copying and translating the DE dictionary.
T['EN'] = T['DE'] # For now, just copy
# backend/translation.py

T = {
    'DE': {
        # App-wide
        'APP_TITLE': "OpenSKIZZE - Generativer Städtebau & Klimaresilienz",
        'NEXT_STEP': "Nächster Schritt",
        'PREV_STEP': "Vorheriger Schritt",
        'FILE_MENU': "Datei",
        'NEW_PROJECT': "Neues Projekt",
        'SAVE_PROJECT': "Projekt speichern",
        'LOAD_PROJECT': "Projekt laden",
        
        # Step 1
        'STEP1_TITLE': "Schritt 1: Geltungsbereich und klimatische Parameter festlegen",
        'STEP1_WIND_HEADER': "Klimatische Parameter",
        'STEP1_WIND_SLIDER_LABEL': "Windrichtung (TODO: importieren von Klimamodell)",
        'STEP1_DATA_SOURCE_INFO': "Kartengrundlage: OpenStreetMap und Geodatenportal NRW.",
        'STEP1_TOOLS_HEADER': "Werkzeuge",
        'STEP1_IMPORT_GEOJSON': "1a. Geltungsbereich aus GeoJSON-Datei importieren",
        'STEP1_UPLOAD_GEOJSON': "GeoJSON-Datei hochladen",
        'STEP1_UPLOAD_LABEL': "Datei auswählen",
        'STEP1_UPLOAD_BUTTON_TEXT': "Datei auswählen",
        'STEP1_OR': "ODER",
        'STEP1_LOAD_PARCELS': "1b. ODER: Flurstücke von OpenData Portal NRW laden",
        'STEP1_LOAD_PARCELS_BUTTON': "Flurstücke für aktuellen Kartenausschnitt laden",
        'STEP1_LOAD_PARCELS_LABEL': "Flurstücke laden",
        'STEP1_MANUAL_ADJUSTMENT_LABEL': "2. Manuelle Anpassung",
        'STEP1_ADD_AREA': "Fläche hinzufügen",
        'STEP1_REMOVE_AREA': "Fläche entfernen",
        'STEP1_EDIT_INSTRUCTIONS': "Nutzen Sie die Werkzeuge links auf der Karte, um die grüne Auswahl anzupassen.",
        'STEP1_PARCEL_INFO_HEADER': "Flurstück-Informationen",
        'STEP1_PARCEL_AREA': "Fläche",
        'STEP1_PARCEL_DIMENSIONS': "Abmessungen (Breite × Länge)",
        'STEP1_NO_PARCEL_SELECTED': "Kein Flurstück ausgewählt",
        
        # Model Diagnostics Button (Step 1)
        'MODEL_DIAG_BUTTON': 'Modelldiagnose öffnen',
        'MODEL_DIAG_BUTTON_INFO': 'Testen und vergleichen Sie Zielfunktionen auf archetypischen städtischen Mustern.',

        # Step 2
        'STEP2_TITLE': "Schritt 2: Leistungsmerkmale und Optimierungsziele festlegen",
        'STEP2_RESET_BUTTON': "Zurücksetzen",
        'STEP2_OBJECTIVES_HEADER': "Leistungsmerkmale",
        'STEP2_MEASURES_LABEL': "Wählen Sie die Merkmale zur Generierung diverser Lösungen:",
        'STEP2_PRESETS_HEADER': "Voreinstellungen (Presets)",
        'STEP2_PRESET_CUSTOM': "Benutzerdefiniert",
        'STEP2_PRESET_SUBURBAN': "Vorstadt (suburban)",
        'STEP2_PRESET_DENSE': "Dichte Stadt (dense urban)",
        'STEP2_TARGET_RANGES_HEADER': "Zielbereiche für Merkmale festlegen",
        'STEP2_TARGET_RANGES_INFO': "Definieren Sie die Wertebereiche, in denen der Optimierer nach diversen Lösungen suchen soll.",
        'STEP2_NO_FEATURES_SELECTED': "Bitte mindestens ein Merkmal auswählen.",
        'STEP2_HARD_CONSTRAINTS_HEADER': "Harte Randbedingungen",
        'STEP2_MAX_HEIGHT_LABEL': "Maximale Bauhöhe (in Geschossen, ca. 3m pro Geschoss):",
        'STEP2_MAX_HEIGHT_PLACEHOLDER': "z.B. 7 (= 21m)",
        'STEP2_MIN_DISTANCE_LABEL': "Minimaler Gebäudeabstand (m):",
        'STEP2_MIN_DISTANCE_PLACEHOLDER': "z.B. 6",
                'STEP2_ADVANCED_MODE': "Erweiterte Optionen anzeigen",
        'STEP2_QD_HYPERPARAMS_HEADER': "Optimierungsparameter (Quality-Diversity)",
        'STEP2_QD_GENERATIONS_LABEL': "Anzahl Generationen:",
        'STEP2_QD_EMITTERS_LABEL': "Anzahl Emitter:",
        'STEP2_QD_NICHES_LABEL': "Anzahl Nischen (Rasterauflösung):",
        'STEP2_QD_BATCH_SIZE_LABEL': "Batch-Größe:",
        'STEP2_QD_HYPERPARAMS_INFO': "Höhere Werte = längere Laufzeit, mehr Lösungen. Standard: 1000 Generationen, 5 Emitter.",

        # Surrogate Model Selection
        'STEP2_SURROGATE_MODEL_HEADER': "Evaluierungsmethode",
        'STEP2_MODEL_TYPE_LABEL': "Wählen Sie die Berechnungsmethode:",
        'STEP2_MODEL_SIMPLE_POROSITY': "Einfache Porosität (Geometrisch)",
        'STEP2_MODEL_STREET_CANYON': "Street Canyon (Geometrisch)",
        'STEP2_MODEL_SVGP': "SVGP (ML + Unsicherheit)",
        'STEP2_MODEL_UNET': "U-Net (ML + Strömung)",
        'STEP2_MODEL_HYBRID': "Hybrid (ML + Beides)",
        'STEP2_UCB_LAMBDA_LABEL': "Explorationsparameter (λ):",
        'STEP2_UCB_LAMBDA_INFO': "Höhere Werte fördern die Erkundung unsicherer Regionen",
        
        # Model Info Cards
        'MODEL_INFO_SIMPLE_POROSITY_TITLE': "Einfache Porosität",
        'MODEL_INFO_SIMPLE_POROSITY_DESC': "Zählt offene horizontale Windkorridore. Schnelle geometrische Berechnung, gut für offene Layouts.",
        'MODEL_INFO_STREET_CANYON_TITLE': "Street Canyon",
        'MODEL_INFO_STREET_CANYON_DESC': "Berücksichtigt Straßenschluchten, Querbelüftung und Höhenvariation. Besser für dichte urbane Umgebungen.",
        'MODEL_INFO_SVGP_TITLE': "SVGP - Sparse Variational Gaussian Process",
        'MODEL_INFO_SVGP_DESC': "Probabilistisches ML-Modell trainiert auf KLAM_21 Simulationen. Liefert Unsicherheitsschätzungen für gezielte Exploration. ~10× schneller.",
        'MODEL_INFO_UNET_TITLE': "U-Net - Neuronales Netz",
        'MODEL_INFO_UNET_DESC': "Tiefes neuronales Netz trainiert auf KLAM_21 Simulationen. Liefert Strömungsfelder für Visualisierung. ~100× schneller.",
        'MODEL_INFO_HYBRID_TITLE': "Hybrid - Kombination aus U-Net und SVGP",
        'MODEL_INFO_HYBRID_DESC': "Nutzt U-Net Fitness (KLAM-genau) und SVGP Unsicherheit. Beste Qualitätsdiversitäts-Ergebnisse mit Strömungsvisualisierung. ~50× schneller.",
        
        'MODEL_INFO_SVGP_SPEED': "~10× schneller, KLAM-Genauigkeit + Unsicherheit",
        'MODEL_INFO_UNET_SPEED': "~100× schneller, KLAM-Genauigkeit + Strömungsfelder",
        'MODEL_INFO_HYBRID_SPEED': "~50× schneller, volle KLAM-Genauigkeit + Unsicherheit + Strömung",
        
        'MODEL_INFO_SPEED': "Geschwindigkeit:",
        'MODEL_INFO_ACCURACY': "Genauigkeit:",
        'MODEL_INFO_UNCERTAINTY': "Unsicherheit:",
        'MODEL_INFO_FLOW': "Strömungsfeld:",
        
        'MODEL_UNAVAILABLE': "Nicht verfügbar",
        'MODEL_SELECT_PARCEL_FIRST': "Bitte wählen Sie zuerst eine Parzelle in Schritt 1.",
        'MODEL_CANNOT_DETERMINE_SIZE': "Parzellengröße konnte nicht ermittelt werden.",
        'MODEL_NONE_AVAILABLE': "Keine Surrogate-Modelle für Parzellengröße {size}m verfügbar.",
        'MODEL_UNET_UNAVAILABLE': "U-Net/Hybrid nicht verfügbar für Parzellengröße {size}m. SVGP kann verwendet werden.",
        
        # Step 4 - Uncertainty Heatmap
        'STEP4_UNCERTAINTY_HEADER': "Modell-Unsicherheit",
        'STEP4_UNCERTAINTY_INFO': "Für SVGP/Hybrid-Modelle zeigt die Unsicherheitskarte, wo das Modell am wenigsten sicher ist.",
        'STEP4_SHOW_UNCERTAINTY': "Unsicherheit anzeigen",
        'STEP4_UNCERTAINTY_OVERLAY': "Unsicherheits-Overlay",
        'STEP4_UNCERTAINTY_HEATMAP_TITLE': "Modell-Unsicherheit",
        'UNCERTAINTY_LABEL': "Unsicherheit (σ)",
        
        # Step 6 - Flow Field
        'STEP6_SHOW_FLOW': "Strömungsfeld anzeigen",
        'STEP6_SHOW_ALL_FLOW': "Alle Strömungsfelder anzeigen",
        'STEP6_FLOW_FIELD_HEADER': "Strömungsfeld",
        'STEP6_FLOW_OVERLAY': "Windströmungs-Overlay",
        'STEP6_FLOW_TITLE': "Kaltluftströmung (U-Net Vorhersage)",
        'FLOW_VECTORS': "Strömungsvektoren",
        'POSITION_X': "Position X (m)",
        'POSITION_Y': "Position Y (m)",
        'FEATURE_X': "Merkmal X",
        'FEATURE_Y': "Merkmal Y",

        # Consolidated feature set (indices 0-7)
        'MEASURE_0': 'GRZ (Grundflächenzahl)',
        'MEASURE_1': 'GFZ (Geschossflächenzahl)',
        'MEASURE_2': 'Durchschnittliche Bauhöhe',
        'MEASURE_3': 'Höhenvariabilität',
        'MEASURE_4': 'Durchschnittliche Gebäudedistanz',
        'MEASURE_5': 'Anzahl der Gebäude',
        'MEASURE_6': 'Kompaktheit (A/V-Verhältnis)',
        'MEASURE_7': 'Park-Faktor (Grünflächenradius)',
        
        # Feature units - Consolidated
        'MEASURE_0_UNIT': '',  # ratio 0-1
        'MEASURE_1_UNIT': '',  # ratio
        'MEASURE_2_UNIT': 'm',
        'MEASURE_3_UNIT': 'm',
        'MEASURE_4_UNIT': 'm',
        'MEASURE_5_UNIT': '',  # count
        'MEASURE_6_UNIT': '',  # ratio
        'MEASURE_7_UNIT': 'm',
        
        # Feature set selector
        'STEP2_FEATURE_SET_HEADER': 'Merkmalsatz',
        'STEP2_FEATURE_SET_LABEL': 'Aktiver Merkmalsatz:',
        'STEP2_FEATURE_SET_CONSOLIDATED': 'Konsolidierte Merkmale (MVP)',
        'STEP2_FEATURE_SET_CONSOLIDATED_DESC': 'GRZ, GFZ, Höhe, Variabilität, Distanz, Anzahl, Kompaktheit, Park-Faktor',
        
        'OBJECTIVE_UNIT': '',  # porosity is dimensionless (0-1)

        # Step 3
        'STEP3_TITLE': "Schritt 3: Entwurfsvarianten generieren",
        'STEP3_START_BUTTON': "Optimierung starten",
        'STEP3_RESULTS_HEADER': "Ergebnis der Optimierung",
        'STEP3_NO_AREA': "Bitte definieren Sie einen Geltungsbereich in Schritt 1.",
        'STEP3_FAILED': "Optimierung fehlgeschlagen:",
        'STEP3_NO_SOLUTIONS': "Optimierung fehlgeschlagen oder es wurden keine Lösungen gefunden.",
        'STEP3_ARCHIVE_VIS_HEADER': "Lösungsarchiv",
        'STEP3_X_AXIS_LABEL': "X-Achse auswählen:",
        'STEP3_Y_AXIS_LABEL': "Y-Achse auswählen:",
        'STEP3_SOLUTION_GRID_HEADER': "Lösungsarchiv (Bester Entwurf pro Nische)",
        'STEP3_PARALLEL_COORDS_HEADER': "Parallel-Koordinaten-Diagramm",

        # Step 4
        'STEP4_TITLE': "Schritt 4: Lösungsraum analysieren",
        'STEP4_X_AXIS_LABEL': "X-Achse auswählen:",
        'STEP4_Y_AXIS_LABEL': "Y-Achse auswählen:",
        'STEP4_GRID_HEADER': "Lösungsarchiv (Bester Entwurf pro Nische)",
        'STEP4_NO_RESULTS': "Optimierungsergebnisse nicht gefunden oder Achsen nicht gewählt.",
        'STEP4_NO_FILE': "Fehler: Große Ergebnisdatei oder Georeferenzierung nicht gefunden.",
        'STEP4_NO_DESIGN': "Kein Entwurf",
        'STEP4_FEATURE_VS_OBJECTIVE_HEADER': "Merkmal vs. Zielfunktion Analyse",
        'STEP4_FEATURE_VS_OBJECTIVE_INFO': "Streudiagramme zeigen die Beziehung zwischen jedem Merkmal und der Zielfunktion. Jeder Punkt repräsentiert eine Lösung im Archiv.",
        
        # Step 2 - Optimization Criteria
        'STEP2_OBJECTIVE_FUNCTION_HEADER': "Optimierungskriterien",
        'STEP2_OBJECTIVE_FUNCTION_LABEL': "Windstrom-Zielfunktion",
        'STEP2_OBJECTIVE_SIMPLE_POROSITY': "Einfache Windporosität",
        'STEP2_OBJECTIVE_SIMPLE_POROSITY_DESC': "Zählt vollständig offene vertikale Durchgänge. Am besten für spärliche Umgebungen.",
        'STEP2_OBJECTIVE_STREET_CANYON': "Straßenschlucht-Ventilation",
        'STEP2_OBJECTIVE_STREET_CANYON_DESC': "Berücksichtigt horizontale Lücken, seitlichen Fluss und teilweise Durchdringung. Besser für dichte städtische Kontexte.",
        
        # Step 3 - Heatmap
        'STEP3_ARCHIVE_HEATMAP_TITLE': "Archiv-Heatmap",
        'STEP3_ARCHIVE_HEATMAP_COVERAGE': "Archivabdeckung (Zielfunktionswerte)",
        'STEP3_HEATMAP_OBJECTIVE_LABEL': "Zielfunktion",
        
        # Step 5
        'STEP5_TITLE': "Schritt 5: Clustering und Entwurfsauswahl",
        'STEP5_EXPORT_BUTTON': "Planungsanforderungen für Wettbewerb exportieren",
        'STEP5_EXPORT_FILENAME': "planungsanforderungen.txt",
        'STEP5_CORRELATION_HEADER': "Korrelation der Merkmale und Zielfunktion",
        'STEP5_CORRELATION_LABEL': "Korrelation",
        'STEP5_NO_RESULTS_TITLE': "Keine Optimierungsergebnisse gefunden",
        'STEP5_NO_RESULTS_TEXT': "Keine Optimierungsergebnisse gefunden.<br>Bitte führen Sie zuerst eine Optimierung in Schritt 3 durch.",
        'STEP5_FILE_NOT_FOUND': "Ergebnisdatei nicht gefunden.<br>Bitte führen Sie die Optimierung erneut aus.",
        'STEP5_LOAD_ERROR': "Fehler beim Laden der Ergebnisdatei:<br>{error}",
        'STEP5_NO_LABELS': "Keine Feature-Labels in den Ergebnissen gefunden.",
        'STEP5_CORRELATION_ERROR': "Fehler beim Berechnen der Korrelationsmatrix:<br>{error}",
        'STEP5_CORRELATION_LEGEND': "Werte nahe +1 = starke positive Korrelation | Werte nahe -1 = starke negative Korrelation | Werte nahe 0 = keine Korrelation",
        'STEP5_FILTER_HEADER': "Designs filtern",
        'STEP5_FILTER_DESC': "Filtern Sie die Lösungen nach ihren Merkmalen.",
        'STEP5_ANALYSIS_HEADER': "Analyse der Entwurfstypen (Cluster)",
        'STEP5_RUN_BUTTON': "Analyse starten / neu filtern",
        'STEP5_CLUSTER_CARD_TITLE': "Cluster {id} - Entwurfstyp (Größe: {size})",
        'STEP5_CLUSTER_CARD_TEXT': "Dieser Entwurfstyp ist robust, da er in {size} Varianten gefunden wurde.",
        'STEP5_BEST_SOLUTION_HEADER': "Beste Lösung (Höchste Porosität)",
        'STEP5_CENTRAL_SOLUTION_HEADER': "Zentralste Lösung (Repräsentativste)",
        'STEP5_CONSENSUS_MAP_HEADER': "Konsens-Karte (Bebauungswahrscheinlichkeit)",
        'STEP5_NO_CLUSTERS_FOUND': "Keine Cluster gefunden. Versuchen Sie, die Filter oder die Clustering-Parameter anzupassen.",
        'STEP5_NO_SELECTION': "Zum Starten bitte auf 'Analyse starten' klicken.",
        'STEP5_SELECT_LABEL': "Zum Vergleich auswählen",
        'STEP5_SIMILARITY_METRIC_LABEL': "Ähnlichkeitsmaß:",
        'STEP5_METRIC_TSNE': "t-SNE (Euklidisch auf Projektion)",
        'STEP5_METRIC_SSIM': "SSIM (Strukturelle Ähnlichkeit)",
        'STEP5_ALGORITHM_LABEL': "Clustering-Algorithmus:",
        'STEP5_KMEDOIDS_K_LABEL': "Anzahl der Cluster (k):",
        'STEP5_N_CLUSTERS_LABEL': "Anzahl der Cluster:",
        'STEP5_HDBSCAN_MINCLUSTER': "Minimale Clustergröße:",
        'STEP5_DBSCAN_EPS': "DBSCAN eps (Nachbarschaftsradius):",
        'STEP5_DBSCAN_MINSAMPLES': "DBSCAN min_samples (Min. Clustergröße):",
        'STEP5_COMPARE_BTN': "Ausgewählte Designs vergleichen",
        'STEP5_NO_OPTIMIZATION': "Bitte zuerst in Schritt 3 eine Optimierung durchführen.",
        'STEP5_ALG_KMEDOIDS': "K-Medoids (Fuzzy Konsens-Karten)",
        'STEP5_ALG_HDBSCAN': "HDBSCAN (Klarere Entwürfe in Konsens-Karten)",
        'STEP5_ALG_HIERARCHICAL': "Hierarchisch (Ward)",
        'STEP5_HDBSCAN_AUTO_NOTE': "HDBSCAN verwendet eine minimale Clustergröße von 5.",
        'STEP5_FILTER_INFO': "Filtern Sie die Lösungen nach ihren Merkmalen und passen Sie die Clustering-Parameter an, um Entwurfstypen zu identifizieren.",
        'STEP5_COMPARE_BUTTON': "Ausgewählte Designs vergleichen",
        'STEP5_NO_RESULTS_ERROR': "Ergebnisdatei oder Georeferenzierung nicht gefunden.",
        'STEP5_SELECT_FOR_COMPARISON': "Zum Vergleich auswählen",
        
        # Step 6
        'STEP6_TITLE': "Schritt 6: Detailvergleich der ausgewählten Entwürfe",
        'STEP6_NO_SELECTION': "Keine Entwürfe zum Vergleich ausgewählt. Bitte gehen Sie zu Schritt 4 zurück und wählen Sie mindestens einen Entwurf aus.",
        'STEP6_NO_DATA': "Die Ergebnisdaten konnten nicht geladen werden.",
        'STEP6_NO_FILE': "Ergebnisdatei oder Georeferenzierung nicht gefunden.",
        'STEP6_IDS_NOT_FOUND': "Fehler: Die ausgewählten Entwurfs-IDs wurden in der aktuellen Ergebnisdatei nicht gefunden. Dies kann passieren, wenn nach der Auswahl eine neue Optimierung gestartet wurde. Bitte gehen Sie zu Schritt 5 zurück und treffen Sie eine neue Auswahl.",
        'STEP6_EXPORT_PDF': "PDF-Bericht exportieren",
        'STEP6_DESIGN': "Entwurf",
        'STEP6_OBJECTIVE': "Zielfunktion:",
        'STEP6_FEATURES': "Leistungsmerkmale",
        'STEP6_FEATURE': "Merkmal",
        'STEP6_VALUE': "Wert",
        'STEP6_NO_RESULTS': "Die Ergebnisdaten konnten nicht geladen werden.",
        'STEP6_FILE_NOT_FOUND': "Ergebnisdatei oder Georeferenzierung nicht gefunden.",
        'STEP6_FEATURE_LABEL': "Merkmal",
        'STEP6_VALUE_LABEL': "Wert",
        'STEP6_DESIGN_TITLE': "Entwurf {num}",
        'STEP6_OBJECTIVE_LABEL': "Zielfunktion: {value:.4f}",
        'STEP6_METRICS_HEADER': "Leistungsmerkmale",
        
        # Breadcrumbs
        'BREADCRUMB_HOME': 'Start',
        'BREADCRUMB_STEP1': 'Geltungsbereich',
        'BREADCRUMB_STEP2': 'Merkmale & Ziele',
        'BREADCRUMB_STEP3': 'Optimierung',
        'BREADCRUMB_STEP4': 'Analyse',
        'BREADCRUMB_STEP5': 'Clustering',
        'BREADCRUMB_STEP6': 'Archetypen vergleichen',
        
        # Next step navigation
        'NEXT_STEP_LABEL': 'Weiter zu',
        'NEXT_STEP_STEP1': 'Geltungsbereich festlegen',
        'NEXT_STEP_STEP2': 'Merkmale & Ziele definieren',
        'NEXT_STEP_STEP3': 'Optimierung starten',
        'NEXT_STEP_STEP4': 'Ergebnisse analysieren',
        'NEXT_STEP_STEP5': 'Entwürfe clustern',
        'NEXT_STEP_STEP6': 'Archetypen vergleichen',
        
        # Model Diagnostics Page
        'MODEL_DIAG_TITLE': 'Modelldiagnose',
        'MODEL_DIAG_BACK_TO_STEP1': 'Zurück zu Schritt 1',
        'MODEL_DIAG_GALLERY_HEADER': 'Archetypische Stadtbausteine (81m × 81m)',
        'MODEL_DIAG_GALLERY_INFO': 'Sechs vordefinierte Gebäudelayouts zum Testen und Vergleichen der Zielfunktionen.',
        'MODEL_DIAG_RUN_BTN': 'Alle Bewertungen ausführen',
        'MODEL_DIAG_RANKING': 'Bewertungsranking',
        'MODEL_DIAG_RANKING_INFO': 'Fitness-Scores für alle Archetypen. Höhere Werte = bessere Kaltluftproduktion.',
        'MODEL_DIAG_CORRELATION': 'Korrelationsmatrix',
        'MODEL_DIAG_CORRELATION_INFO': 'Pearson-Korrelation zwischen Zielfunktionen über alle Archetypen.',
        'MODEL_DIAG_CORRELATION_LABEL': 'Korrelation',
        'MODEL_DIAG_FLOW_VIZ': 'Strömungsvisualisierung (U-Net)',
        'MODEL_DIAG_FLOW_VIZ_INFO': 'Windgeschwindigkeitsfeld und Stromlinien vom U-Net-Modell vorhergesagt.',
        'MODEL_DIAG_SELECT_ARCH': 'Archetyp auswählen:',
        'MODEL_DIAG_STREAMLINE_DENSITY': 'Stromliniendichte:',
        'MODEL_DIAG_VELOCITY_HEATMAP': 'Geschwindigkeitsfeld',
        'MODEL_DIAG_STREAMLINES': 'Stromlinien',
        'MODEL_DIAG_VELOCITY_MS': 'Geschwindigkeit (m/s)',
        'MODEL_DIAG_EVAL_COMPLETE': 'Bewertung abgeschlossen!',
        'MODEL_DIAG_EVAL_ERROR': 'Fehler bei der Bewertung',
        'MODEL_DIAG_TABLE_ARCHETYPE': 'Archetyp',
        'MODEL_DIAG_TABLE_POROSITY': 'Porosität',
        'MODEL_DIAG_TABLE_STREET_CANYON': 'Straßenschlucht',
        'MODEL_DIAG_TABLE_SVGP': 'SVGP',
        'MODEL_DIAG_TABLE_UNET': 'U-Net',
        
        # Archetype names and descriptions
        'ARCHETYPE_EMPTY': 'Leer',
        'ARCHETYPE_SQUARE': 'Quadrat',
        'ARCHETYPE_TWO_SQUARES': 'Zwei Quadrate',
        'ARCHETYPE_TWO_SQUARES_ROTATED': 'Zwei Quadrate (90° gedreht)',
        'ARCHETYPE_U_SHAPE': 'U-Form',
        'ARCHETYPE_U_SHAPE_ROTATED': 'U-Form (90° gedreht)',
        'ARCHETYPE_GRID': 'Raster',
        'ARCHETYPE_STREET_CANYON': 'Straßenschlucht',
        'ARCHETYPE_STREET_CANYON_ROTATED': 'Straßenschlucht (90° gedreht)',
    },
    'EN': {
        # App-wide
        'APP_TITLE': "OpenSKIZZE - Generative Urban Design & Climate Resilience",
        'NEXT_STEP': "Next Step",
        'PREV_STEP': "Previous Step",
        'FILE_MENU': "File",
        'NEW_PROJECT': "New Project",
        'SAVE_PROJECT': "Save Project",
        'LOAD_PROJECT': "Load Project",
        
        # Step 1
        'STEP1_TITLE': "Step 1: Define Scope and Climatic Parameters",
        'STEP1_WIND_HEADER': "Climatic Parameters",
        'STEP1_WIND_SLIDER_LABEL': "Wind Direction (TODO: import from climate model)",
        'STEP1_DATA_SOURCE_INFO': "Map data: OpenStreetMap and Geodata Portal NRW.",
        'STEP1_TOOLS_HEADER': "Tools",
        'STEP1_IMPORT_GEOJSON': "1a. Import Scope from GeoJSON File",
        'STEP1_UPLOAD_GEOJSON': "Upload GeoJSON File",
        'STEP1_UPLOAD_LABEL': "Select File",
        'STEP1_UPLOAD_BUTTON_TEXT': "Select File",
        'STEP1_OR': "OR",
        'STEP1_LOAD_PARCELS': "1b. OR: Load Parcels from OpenData Portal NRW",
        'STEP1_LOAD_PARCELS_BUTTON': "Load Parcels for Current Map View",
        'STEP1_LOAD_PARCELS_LABEL': "Load Parcels",
        'STEP1_MANUAL_ADJUSTMENT_LABEL': "2. Manual Adjustment",
        'STEP1_ADD_AREA': "Add Area",
        'STEP1_REMOVE_AREA': "Remove Area",
        'STEP1_EDIT_INSTRUCTIONS': "Use the tools on the left of the map to adjust the green selection.",
        'STEP1_PARCEL_INFO_HEADER': "Parcel Information",
        'STEP1_PARCEL_AREA': "Area",
        'STEP1_PARCEL_DIMENSIONS': "Dimensions (Width × Length)",
        'STEP1_NO_PARCEL_SELECTED': "No parcel selected",
        
        # Model Diagnostics Button (Step 1)
        'MODEL_DIAG_BUTTON': 'Open Model Diagnostics',
        'MODEL_DIAG_BUTTON_INFO': 'Test and compare objective functions on archetypical urban patterns.',

        # Step 2
        'STEP2_TITLE': "Step 2: Define Performance Metrics and Optimization Goals",
        'STEP2_RESET_BUTTON': "Reset All",
        'STEP2_OBJECTIVES_HEADER': "Performance Metrics",
        'STEP2_MEASURES_LABEL': "Select metrics to generate diverse solutions:",
        'STEP2_PRESETS_HEADER': "Presets",
        'STEP2_PRESET_CUSTOM': "Custom",
        'STEP2_PRESET_SUBURBAN': "Suburban",
        'STEP2_PRESET_DENSE': "Dense Urban",
        'STEP2_TARGET_RANGES_HEADER': "Define Target Ranges for Metrics",
        'STEP2_TARGET_RANGES_INFO': "Define the value ranges in which the optimizer should search for diverse solutions.",
        'STEP2_NO_FEATURES_SELECTED': "Please select at least one feature.",
        'STEP2_HARD_CONSTRAINTS_HEADER': "Hard Constraints",
        'STEP2_MAX_HEIGHT_LABEL': "Maximum Building Height (in floors, approx. 3m per floor):",
        'STEP2_MAX_HEIGHT_PLACEHOLDER': "e.g. 7 (= 21m)",
        'STEP2_MIN_DISTANCE_LABEL': "Minimum Building Distance (m):",
        'STEP2_MIN_DISTANCE_PLACEHOLDER': "e.g. 6",
        'STEP2_ADVANCED_MODE': "Show Advanced Options",
        'STEP2_QD_HYPERPARAMS_HEADER': "Optimization Parameters (Quality-Diversity)",
        'STEP2_QD_GENERATIONS_LABEL': "Number of Generations:",
        'STEP2_QD_EMITTERS_LABEL': "Number of Emitters:",
        'STEP2_QD_NICHES_LABEL': "Archive Size (Niches per Dimension):",
        'STEP2_QD_BATCH_SIZE_LABEL': "Batch Size:",
        'STEP2_QD_HYPERPARAMS_INFO': "Higher values = longer runtime, more solutions. Default: 1000 generations, 5 emitters.",
        
        # Surrogate Model Selection
        'STEP2_SURROGATE_MODEL_HEADER': "Evaluation Method",
        'STEP2_MODEL_TYPE_LABEL': "Choose calculation method:",
        'STEP2_MODEL_SIMPLE_POROSITY': "Simple Porosity (Geometric)",
        'STEP2_MODEL_STREET_CANYON': "Street Canyon (Geometric)",
        'STEP2_MODEL_SVGP': "SVGP (ML + Uncertainty)",
        'STEP2_MODEL_UNET': "U-Net (ML + Flow)",
        'STEP2_MODEL_HYBRID': "Hybrid (ML + Both)",
        'STEP2_UCB_LAMBDA_LABEL': "Exploration Parameter (λ):",
        'STEP2_UCB_LAMBDA_INFO': "Higher values encourage exploring uncertain regions",
        
        # Model Info Cards
        'MODEL_INFO_SIMPLE_POROSITY_TITLE': "Simple Porosity",
        'MODEL_INFO_SIMPLE_POROSITY_DESC': "Counts open horizontal wind corridors. Fast geometric calculation, good for open layouts.",
        'MODEL_INFO_STREET_CANYON_TITLE': "Street Canyon",
        'MODEL_INFO_STREET_CANYON_DESC': "Considers street canyons, cross-ventilation, and height variation. Better for dense urban environments.",
        'MODEL_INFO_SVGP_TITLE': "SVGP - Sparse Variational Gaussian Process",
        'MODEL_INFO_SVGP_DESC': "Probabilistic ML model trained on KLAM_21 simulations. Provides uncertainty estimates for targeted exploration. ~10× faster.",
        'MODEL_INFO_UNET_TITLE': "U-Net - Neural Network",
        'MODEL_INFO_UNET_DESC': "Deep neural network trained on KLAM_21 simulations. Provides flow fields for visualization. ~100× faster.",
        'MODEL_INFO_HYBRID_TITLE': "Hybrid - Combination of U-Net and SVGP",
        'MODEL_INFO_HYBRID_DESC': "Uses U-Net fitness (KLAM-accurate) and SVGP uncertainty. Best quality-diversity results with flow visualization. ~50× faster.",
        
        'MODEL_INFO_SVGP_SPEED': "~10× faster, KLAM accuracy + uncertainty",
        'MODEL_INFO_UNET_SPEED': "~100× faster, KLAM accuracy + flow fields",
        'MODEL_INFO_HYBRID_SPEED': "~50× faster, full KLAM accuracy + uncertainty + flow",
        
        'MODEL_INFO_SPEED': "Speed:",
        'MODEL_INFO_ACCURACY': "Accuracy:",
        'MODEL_INFO_UNCERTAINTY': "Uncertainty:",
        'MODEL_INFO_FLOW': "Flow field:",
        
        'MODEL_UNAVAILABLE': "Not available",
        'MODEL_SELECT_PARCEL_FIRST': "Please select a parcel in Step 1 first.",
        'MODEL_CANNOT_DETERMINE_SIZE': "Could not determine parcel size.",
        'MODEL_NONE_AVAILABLE': "No surrogate models available for parcel size {size}m.",
        'MODEL_UNET_UNAVAILABLE': "U-Net/Hybrid not available for parcel size {size}m. SVGP can be used.",
        
        # Step 4 - Uncertainty Heatmap
        'STEP4_UNCERTAINTY_HEADER': "Model Uncertainty",
        'STEP4_UNCERTAINTY_INFO': "For SVGP/Hybrid models, the uncertainty map shows where the model is least confident.",
        'STEP4_SHOW_UNCERTAINTY': "Show Uncertainty",
        'STEP4_UNCERTAINTY_OVERLAY': "Uncertainty Overlay",
        'STEP4_UNCERTAINTY_HEATMAP_TITLE': "Model Uncertainty",
        'UNCERTAINTY_LABEL': "Uncertainty (σ)",
        
        # Step 6 - Flow Field
        'STEP6_SHOW_FLOW': "Show Flow Field",
        'STEP6_SHOW_ALL_FLOW': "Show All Flow Fields",
        'STEP6_FLOW_FIELD_HEADER': "Flow Field",
        'STEP6_FLOW_OVERLAY': "Wind Flow Overlay",
        'STEP6_FLOW_TITLE': "Cold Air Flow (U-Net Prediction)",
        'FLOW_VECTORS': "Flow Vectors",
        'POSITION_X': "Position X (m)",
        'POSITION_Y': "Position Y (m)",
        'FEATURE_X': "Feature X",
        'FEATURE_Y': "Feature Y",
        
        # Consolidated feature set (indices 0-7)
        'MEASURE_0': 'GRZ (Site Coverage Ratio)',
        'MEASURE_1': 'GFZ (Floor Area Ratio)',
        'MEASURE_2': 'Average Building Height',
        'MEASURE_3': 'Height Variability',
        'MEASURE_4': 'Average Building Distance',
        'MEASURE_5': 'Number of Buildings',
        'MEASURE_6': 'Compactness (A/V Ratio)',
        'MEASURE_7': 'Park Factor (Green Space Radius)',
        
        # Feature units - Consolidated
        'MEASURE_0_UNIT': '',  # ratio 0-1
        'MEASURE_1_UNIT': '',  # ratio
        'MEASURE_2_UNIT': 'm',
        'MEASURE_3_UNIT': 'm',
        'MEASURE_4_UNIT': 'm',
        'MEASURE_5_UNIT': '',  # count
        'MEASURE_6_UNIT': '',  # ratio
        'MEASURE_7_UNIT': 'm',
        
        # Feature set selector
        'STEP2_FEATURE_SET_HEADER': 'Feature Set',
        'STEP2_FEATURE_SET_LABEL': 'Active Feature Set:',
        'STEP2_FEATURE_SET_CONSOLIDATED': 'Consolidated Features (MVP)',
        'STEP2_FEATURE_SET_CONSOLIDATED_DESC': 'GRZ, GFZ, Height, Var, Dist, Count, Compactness, Park Factor',
        
        'OBJECTIVE_UNIT': '',  # porosity is dimensionless (0-1)

        # Step 3
        'STEP3_TITLE': "Step 3: Generate Design Variants",
        'STEP3_START_BUTTON': "Start Optimization",
        'STEP3_RESULTS_HEADER': "Optimization Results",
        'STEP3_NO_AREA': "Please define a scope in Step 1.",
        'STEP3_FAILED': "Optimization failed:",
        'STEP3_NO_SOLUTIONS': "Optimization failed or no solutions were found.",
        'STEP3_ARCHIVE_VIS_HEADER': "Solution Archive",
        'STEP3_X_AXIS_LABEL': "Select X-Axis:",
        'STEP3_Y_AXIS_LABEL': "Select Y-Axis:",
        'STEP3_SOLUTION_GRID_HEADER': "Solution Archive (Best Design per Niche)",
        'STEP3_PARALLEL_COORDS_HEADER': "Parallel Coordinates Plot",
        'STEP3_ARCHIVE_HEATMAP_TITLE': "Archive Heatmap",
        'STEP3_ARCHIVE_HEATMAP_COVERAGE': "Archive Coverage (Objective Values)",
        'STEP3_HEATMAP_OBJECTIVE_LABEL': "Objective",

        # Step 4
        'STEP4_TITLE': "Step 4: Analyze Solution Space",
        'STEP4_FEATURE_VS_OBJECTIVE_HEADER': "Feature vs Objective Analysis",
        'STEP4_FEATURE_VS_OBJECTIVE_INFO': "Scatter plots showing the relationship between each feature and the objective function. Each point represents one solution in the archive.",
        
        # Step 2 - Optimization Criteria
        'STEP2_OBJECTIVE_FUNCTION_HEADER': "Optimization Criteria",
        'STEP2_OBJECTIVE_FUNCTION_LABEL': "Wind Flow Objective",
        'STEP2_OBJECTIVE_SIMPLE_POROSITY': "Simple Wind Porosity",
        'STEP2_OBJECTIVE_SIMPLE_POROSITY_DESC': "Counts completely open vertical passages. Best for sparse environments.",
        'STEP2_OBJECTIVE_STREET_CANYON': "Street Canyon Ventilation",
        'STEP2_OBJECTIVE_STREET_CANYON_DESC': "Considers horizontal gaps, lateral flow, and partial penetration. Better for dense urban contexts.",

        # Step 5
        'STEP5_TITLE': "Step 5: Clustering and Design Selection",
        'STEP5_EXPORT_BUTTON': "Export Planning Requirements for Competition",
        'STEP5_EXPORT_FILENAME': "planning_requirements.txt",
        'STEP5_CORRELATION_HEADER': "Feature and Objective Correlation",
        'STEP5_CORRELATION_LABEL': "Correlation",
        'STEP5_NO_RESULTS_TITLE': "No optimization results found",
        'STEP5_NO_RESULTS_TEXT': "No optimization results found.<br>Please run an optimization in Step 3 first.",
        'STEP5_FILE_NOT_FOUND': "Results file not found.<br>Please run the optimization again.",
        'STEP5_LOAD_ERROR': "Error loading results file:<br>{error}",
        'STEP5_NO_LABELS': "No feature labels found in results.",
        'STEP5_CORRELATION_ERROR': "Error calculating correlation matrix:<br>{error}",
        'STEP5_CORRELATION_LEGEND': "Values near +1 = strong positive correlation | Values near -1 = strong negative correlation | Values near 0 = no correlation",
        'STEP5_FILTER_HEADER': "Filter Designs",
        'STEP5_FILTER_DESC': "Filter solutions by their features.",
        'STEP5_ANALYSIS_HEADER': "Analysis of Design Types (Clusters)",
        'STEP5_RUN_BUTTON': "Start Analysis / Re-filter",
        'STEP5_CLUSTER_CARD_TITLE': "Cluster {id} - Design Type (Size: {size})",
        'STEP5_CLUSTER_CARD_TEXT': "This design type is robust as it was found in {size} variants.",
        'STEP5_BEST_SOLUTION_HEADER': "Best Solution (Highest Porosity)",
        'STEP5_CENTRAL_SOLUTION_HEADER': "Most Central Solution (Most Representative)",
        'STEP5_CONSENSUS_MAP_HEADER': "Consensus Map (Building Probability)",
        'STEP5_NO_CLUSTERS_FOUND': "No clusters found. Try adjusting the filters or clustering parameters.",
        'STEP5_NO_SELECTION': "Click 'Start Analysis' to begin.",
        'STEP5_SELECT_LABEL': "Select for Comparison",
        'STEP5_SIMILARITY_METRIC_LABEL': "Similarity Metric:",
        'STEP5_METRIC_TSNE': "t-SNE (Euclidean on Projection)",
        'STEP5_METRIC_SSIM': "SSIM (Structural Similarity)",
        'STEP5_ALGORITHM_LABEL': "Clustering Algorithm:",
        'STEP5_KMEDOIDS_K_LABEL': "Number of Clusters (k):",
        'STEP5_N_CLUSTERS_LABEL': "Number of Clusters:",
        'STEP5_HDBSCAN_MINCLUSTER': "Minimum Cluster Size:",
        'STEP5_DBSCAN_EPS': "DBSCAN eps (Neighborhood Radius):",
        'STEP5_DBSCAN_MINSAMPLES': "DBSCAN min_samples (Min. Cluster Size):",
        'STEP5_COMPARE_BTN': "Compare Selected Designs",
        'STEP5_NO_OPTIMIZATION': "Please run an optimization in Step 3 first.",
        'STEP5_ALG_KMEDOIDS': "K-Medoids (Fuzzy Consensus Maps)",
        'STEP5_ALG_HDBSCAN': "HDBSCAN (Clearer Designs in Consensus Maps)",
        'STEP5_ALG_HIERARCHICAL': "Hierarchical (Ward)",
        'STEP5_HDBSCAN_AUTO_NOTE': "HDBSCAN uses a minimum cluster size of 5.",
        'STEP5_FILTER_INFO': "Filter solutions by their metrics and adjust clustering parameters to identify design types.",
        'STEP5_COMPARE_BUTTON': "Compare Selected Designs",
        'STEP5_NO_RESULTS_ERROR': "Results file or georeferencing not found.",
        'STEP5_SELECT_FOR_COMPARISON': "Select for Comparison",
        
        # Common labels
        'OBJECTIVE_FUNCTION': 'Objective Function',
        'COUNT': 'Count',
        'OBJECTIVE_DISTRIBUTION': 'Objective Distribution',
        
        # Model Diagnostics Page
        'MODEL_DIAG_TITLE': 'Model Diagnostics',
        'MODEL_DIAG_BACK_TO_STEP1': 'Back to Step 1',
        'MODEL_DIAG_GALLERY_HEADER': 'Archetypical Urban Patterns (81m × 81m)',
        'MODEL_DIAG_GALLERY_INFO': 'Six predefined building layouts for testing and comparing objective functions.',
        'MODEL_DIAG_RUN_BTN': 'Run All Evaluations',
        'MODEL_DIAG_RANKING': 'Evaluation Ranking',
        'MODEL_DIAG_RANKING_INFO': 'Fitness scores for all archetypes. Higher values = better cold air production.',
        'MODEL_DIAG_CORRELATION': 'Correlation Matrix',
        'MODEL_DIAG_CORRELATION_INFO': 'Pearson correlation between objective functions across all archetypes.',
        'MODEL_DIAG_CORRELATION_LABEL': 'Correlation',
        'MODEL_DIAG_FLOW_VIZ': 'Flow Visualization (U-Net)',
        'MODEL_DIAG_FLOW_VIZ_INFO': 'Wind velocity field and streamlines predicted by U-Net model.',
        'MODEL_DIAG_SELECT_ARCH': 'Select Archetype:',
        'MODEL_DIAG_STREAMLINE_DENSITY': 'Streamline Density:',
        'MODEL_DIAG_VELOCITY_HEATMAP': 'Velocity Field',
        'MODEL_DIAG_STREAMLINES': 'Streamlines',
        'MODEL_DIAG_VELOCITY_MS': 'Velocity (m/s)',
        'MODEL_DIAG_EVAL_COMPLETE': 'Evaluation complete!',
        'MODEL_DIAG_EVAL_ERROR': 'Error during evaluation',
        'MODEL_DIAG_TABLE_ARCHETYPE': 'Archetype',
        'MODEL_DIAG_TABLE_POROSITY': 'Porosity',
        'MODEL_DIAG_TABLE_STREET_CANYON': 'Street Canyon',
        'MODEL_DIAG_TABLE_SVGP': 'SVGP',
        'MODEL_DIAG_TABLE_UNET': 'U-Net',
        
        # Archetype names and descriptions
        'ARCHETYPE_EMPTY': 'Empty',
        'ARCHETYPE_SQUARE': 'Square',
        'ARCHETYPE_TWO_SQUARES': 'Two Squares',
        'ARCHETYPE_TWO_SQUARES_ROTATED': 'Two Squares (90° rotated)',
        'ARCHETYPE_U_SHAPE': 'U-Shape',
        'ARCHETYPE_U_SHAPE_ROTATED': 'U-Shape (90° rotated)',
        'ARCHETYPE_GRID': 'Grid',
        'ARCHETYPE_STREET_CANYON': 'Street Canyon',
        'ARCHETYPE_STREET_CANYON_ROTATED': 'Street Canyon (90° rotated)',
        
        # Step 6
        'STEP6_TITLE': "Step 6: Detailed Comparison of Selected Designs",
        'STEP6_NO_SELECTION': "No designs selected for comparison. Please return to Step 4 and select at least one design.",
        'STEP6_NO_DATA': "The results data could not be loaded.",
        'STEP6_NO_FILE': "Results file or georeferencing not found.",
        'STEP6_IDS_NOT_FOUND': "Error: The selected design IDs were not found in the current results file. This can happen if a new optimization was started after selection. Please return to Step 5 and make a new selection.",
        'STEP6_EXPORT_PDF': "Export PDF Report",
        'STEP6_DESIGN': "Design",
        'STEP6_OBJECTIVE': "Objective Function:",
        'STEP6_FEATURES': "Performance Metrics",
        'STEP6_FEATURE': "Metric",
        'STEP6_VALUE': "Value",
        'STEP6_NO_RESULTS': "The results data could not be loaded.",
        'STEP6_FILE_NOT_FOUND': "Results file or georeferencing not found.",
        'STEP6_FEATURE_LABEL': "Metric",
        'STEP6_VALUE_LABEL': "Value",
        'STEP6_DESIGN_TITLE': "Design {num}",
        'STEP6_OBJECTIVE_LABEL': "Objective Function: {value:.4f}",
        'STEP6_METRICS_HEADER': "Performance Metrics",
        
        # Breadcrumbs
        'BREADCRUMB_HOME': 'Home',
        'BREADCRUMB_STEP1': 'Scope',
        'BREADCRUMB_STEP2': 'Features & Goals',
        'BREADCRUMB_STEP3': 'Optimization',
        'BREADCRUMB_STEP4': 'Analysis',
        'BREADCRUMB_STEP5': 'Clustering',
        'BREADCRUMB_STEP6': 'Compare Archetypes',

        # Next step navigation
        'NEXT_STEP_LABEL': 'Go to',
        'NEXT_STEP_STEP1': 'Define Scope',
        'NEXT_STEP_STEP2': 'Set Features & Objectives',
        'NEXT_STEP_STEP3': 'Run Optimization',
        'NEXT_STEP_STEP4': 'Analyze Results',
        'NEXT_STEP_STEP5': 'Cluster Designs',
        'NEXT_STEP_STEP6': 'Compare Archetypes',
        
    }
}

def get_translation(lang='DE'):
    """Helper function to get translations for a specific language"""
    return T.get(lang, T['DE'])

def translate_feature_labels(feature_indices, lang='DE', feature_set='consolidated'):
    """
    Translate feature indices to labels based on language and feature set.
    
    Args:
        feature_indices: List of feature indices (0-7)
        lang: Language code ('DE' or 'EN')
        feature_set: 'consolidated' (default)
    
    Returns:
        List of translated feature labels
    """
    translations = T.get(lang, T['DE'])
    # Always use MEASURE_X keys for the consolidated set
    return [translations.get(f'MEASURE_{idx}', f'Feature {idx}') for idx in feature_indices]

def create_breadcrumb(current_step, lang='DE'):
    """
    Create breadcrumb navigation component with next step button.
    All steps are always visible, with unvisited steps shown in grey.
    
    Args:
        current_step: Current step number (1-6) or 'home'
        lang: Language code ('DE' or 'EN')
    
    Returns:
        Dash Bootstrap Components container with Breadcrumb and next step button
    """
    import dash_bootstrap_components as dbc
    from dash import html
    
    translations = T.get(lang, T['DE'])
    
    steps = [
        ('/', 'BREADCRUMB_HOME'),
        ('/step1', 'BREADCRUMB_STEP1'),
        ('/step2', 'BREADCRUMB_STEP2'),
        ('/step3', 'BREADCRUMB_STEP3'),
        ('/step4', 'BREADCRUMB_STEP4'),
        ('/step5', 'BREADCRUMB_STEP5'),
        ('/step6', 'BREADCRUMB_STEP6'),
    ]
    
    # Map step number to index
    step_map = {
        'home': 0,
        1: 1,
        2: 2,
        3: 3,
        4: 4,
        5: 5,
        6: 6
    }
    
    current_index = step_map.get(current_step, 0)
    
    # Build breadcrumb items - ALL steps are always visible and clickable
    items = []
    for idx, (href, key) in enumerate(steps):
        label = translations[key]
        
        if idx == current_index:
            # Current page - active (no link)
            items.append({
                "label": label,
                "active": True,
            })
        else:
            # All other pages - with link (visited=normal color, unvisited=will style via CSS)
            items.append({
                "label": label,
                "href": href,
                "external_link": False,
                "class_name": "text-muted" if idx > current_index else "",
            })
    
    # Create breadcrumb
    breadcrumb = dbc.Breadcrumb(items=items, className="mb-0")
    
    # Create next step button (if not on last step)
    next_button = None
    if current_index < 6:
        next_step_num = current_index + 1
        next_step_label_key = f'NEXT_STEP_STEP{next_step_num}'
        next_step_href = f'/step{next_step_num}'
        
        next_button = dbc.Button(
            [
                f"{translations['NEXT_STEP_LABEL']}: {translations[next_step_label_key]}",
                html.I(className="bi bi-arrow-right ms-2")
            ],
            href=next_step_href,
            color="primary",
            outline=True,
            size="sm",
            className="ms-3",
            style={"whiteSpace": "nowrap"}
        )
    
    # Return container with breadcrumb and next button aligned horizontally at baseline
    return html.Div(
        [
            breadcrumb,
            next_button if next_button else html.Div()
        ],
        className="d-flex align-items-baseline mb-3",
        style={"flexWrap": "wrap"}
    )

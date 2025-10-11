# Feature Set Update - README

## What's New?

OpenSKIZZE now supports **two feature sets** for urban design optimization:

1. **Original Features** - Geometric metrics (built area, height, GFA, mass distribution)
2. **Planning Features (BACKLOG)** - Planning-focused metrics (GRZ, GFZ, H/W ratio, SVF)

Users can switch between feature sets in the GUI (Step 2) and the system will automatically:
- Update feature labels and units
- Calculate appropriate dynamic ranges
- Use the correct feature calculations during optimization
- Maintain all results with proper metadata

---

## Quick Start

### Running the Application
```bash
# No changes needed - just run as before
python run.py
```

### Running Tests
```bash
# Run visual feature validation tests
python tests/test_features_visual.py

# Check output visualizations
ls debug_plots/feature_test_*.png
```

### Using the GUI
1. Start the app: `python run.py`
2. Navigate to **Step 2: Constraints**
3. Find "Merkmalsatz auswählen" (Feature Set Selection)
4. Choose your preferred feature set:
   - **Original-Merkmale** - Traditional metrics
   - **Planungs-Merkmale (BACKLOG)** - GRZ/GFZ/planning metrics
5. Continue with optimization as usual

---

## File Organization

```
openskizze/
├── backend/
│   ├── config.py              # ✨ Feature set definitions
│   ├── evaluation.py          # ✨ New planning feature calculations
│   ├── translation.py         # ✨ New feature labels (DE/EN)
│   ├── units.py              # ✨ New feature units
│   └── optimization_process.py # ✨ Feature set support
├── pages/
│   ├── step2_constraints.py  # ✨ GUI feature set selector
│   └── step3_optimize.py     # ✨ Pass feature set to optimization
├── tests/
│   └── test_features_visual.py # ✨ NEW: Visual validation tests
├── debug_plots/               # Test visualizations output here
├── FEATURE_SET_IMPLEMENTATION.md  # ✨ NEW: Detailed implementation docs
├── PLANNING_FEATURES_REFERENCE.md # ✨ NEW: Feature reference guide
└── README.md                  # This file

✨ = Modified or new in this update
```

---

## Feature Sets Explained

### Original Features (8)
Focus on geometric and spatial properties:
- Built Area (m²)
- Average Height (m)
- Height Variability (m)
- Number of Buildings
- Average Distance (m)
- Gross Floor Area (m²)
- Building Mass X/Y (normalized position)

### Planning Features (BACKLOG - 8)
Focus on planning regulations and urban design metrics:
- **GRZ** (Grundflächenzahl) - Site coverage ratio
- **GFZ** (Geschossflächenzahl) - Floor area ratio
- Average Height (m)
- Height Variability (m)
- Number of Buildings
- Average Distance (m)
- **H/W Ratio** - Street canyon aspect ratio
- **SVF** - Sky view factor (simplified)

---

## Key Improvements

### 1. Planning Compliance
- GRZ/GFZ directly correspond to German planning regulations (BauNVO)
- Enables direct comparison with zoning requirements
- Export to planning documentation

### 2. Urban Design Metrics
- Street canyon aspect ratio (H/W) for microclimate analysis
- Sky view factor (SVF) for heat island assessment
- Better alignment with urban planning practice

### 3. User Flexibility
- Choose features most relevant to your project
- Switch between sets without code changes
- Both sets available in all optimization workflows

### 4. Backward Compatibility
- Existing projects continue to work
- Default is 'original' feature set
- No breaking changes to API

---

## Technical Details

### Feature Calculation
```python
# Original features
from backend.evaluation import calculate_all_features
features = calculate_all_features(heightmap, buildable_mask, buildable_area_m2)

# Planning features
from backend.evaluation import calculate_all_features_planning
features = calculate_all_features_planning(heightmap, buildable_mask, buildable_area_m2)
```

### Feature Set Selection
```python
# In session data (Step 2)
session_data['feature_set'] = 'original'  # or 'planning'

# Passed through optimization pipeline
env_config = create_environment(..., feature_set='planning')
```

### Dynamic Range Calculation
```python
# Automatically calculates appropriate ranges based on feature set
ranges, area = _calculate_dynamic_feat_ranges(
    buildable_mask, 
    max_height_meters, 
    min_distance_meters,
    feature_set='planning'  # or 'original'
)
```

---

## Testing

All feature calculations have been validated with comprehensive visual tests:

### Test Scenarios
1. **Single Building** - Basic functionality
2. **Two Buildings** - Height variability, distance
3. **Street Canyon** - H/W ratio validation
4. **Dense Urban** - Complex multi-building scenario
5. **Sparse Suburban** - Low-density configuration

### Test Results
```
✓ All 5 test scenarios passed
✓ GRZ calculations verified mathematically
✓ GFZ calculations verified mathematically
✓ Height consistency between feature sets
✓ Building count accuracy
✓ Street canyon H/W ratio within expected range
```

### Visualizations
Check `debug_plots/` for:
- Heightmap visualizations
- Building footprint plots
- Feature comparison charts
- Street canyon analysis

---

## Known Limitations & Future Work

### SVF (Sky View Factor)
**Current:** Simplified approximation based on GRZ and height  
**Future:** Implement full ray-tracing or hemisphere projection
- More accurate representation
- Point-based calculations
- Consider using UMEP or similar tools

### Additional Metrics
Potential future additions:
- Actual daylight/shadow calculations
- Advanced wind flow metrics (beyond H/W)
- Energy performance indicators
- Accessibility and walkability metrics

---

## Documentation

- **FEATURE_SET_IMPLEMENTATION.md** - Complete technical documentation
- **PLANNING_FEATURES_REFERENCE.md** - Feature definitions and usage guide
- **tests/test_features_visual.py** - Commented test code with examples

---

## Support & Contribution

### Questions?
- Check the reference guides in this directory
- Review test visualizations for examples
- See inline code comments for implementation details

### Contributing
- Feature calculations are in `backend/evaluation.py`
- Add new feature sets by updating `backend/config.py`
- Add tests to `tests/test_features_visual.py`
- Update translations in `backend/translation.py`

---

## Version Info

**Version:** 1.1.0  
**Date:** October 11, 2025  
**Branch:** featureupdate  
**Compatibility:** Full backward compatibility with v1.0.x

---

## Changelog

### v1.1.0 (2025-10-11)
- ✨ Added planning-focused feature set (GRZ, GFZ, H/W, SVF)
- ✨ GUI selector for switching between feature sets
- ✨ Comprehensive visual test suite
- ✨ Full German and English translations
- ✨ Dynamic range calculation for both feature sets
- 📚 Complete documentation and reference guides
- ✅ All tests passing
- 🔄 Full backward compatibility

---

## License

Same as main OpenSKIZZE project.
